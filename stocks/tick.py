"""US/BIST saatlik paper-trading tick motoru."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .agent import call
from .config import AGENTS, JOURNAL_ROOT, MARKETS, NVIDIA_MODEL, STATE_ROOT
from .paper import Portfolio, load_state, save_json, save_state
from .prompt import build_prompt
from .screener import build_market_snapshot


def market_open_now(market, now_utc: datetime | None = None) -> bool:
    now_utc = now_utc or datetime.now(timezone.utc)
    local = now_utc.astimezone(ZoneInfo(market.timezone))
    if local.weekday() >= 5:
        return False
    minute = local.hour * 60 + local.minute
    start = market.open_hour * 60 + market.open_minute
    end = market.close_hour * 60 + market.close_minute
    return start <= minute < end


def journal_path(market, agent_id: str) -> Path:
    return JOURNAL_ROOT / market.id / f"{agent_id}.jsonl"


def state_dir(market) -> Path:
    return STATE_ROOT / market.id / market.experiment_id


def state_path(market, agent_id: str) -> Path:
    return state_dir(market) / f"{agent_id}.json"


def benchmark_path(market) -> Path:
    return state_dir(market) / "_benchmark.json"


def read_rows(market, agent_id: str) -> list[dict]:
    p = journal_path(market, agent_id)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def experiment_rows(market, agent_id: str) -> list[dict]:
    return [r for r in read_rows(market, agent_id) if r.get("experiment_id") == market.experiment_id]


def tick_number(market, agent_id: str) -> int:
    return len(experiment_rows(market, agent_id))


def write_journal(market, agent_id: str, row: dict) -> None:
    p = journal_path(market, agent_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_portfolio(market, agent_id: str) -> Portfolio:
    # Journal authoritative; state file persistent cache.
    for row in reversed(experiment_rows(market, agent_id)):
        snap = row.get("portfolio_state")
        if isinstance(snap, dict):
            return Portfolio(**snap)
    return load_state(state_path(market, agent_id), market.start_cash)


def init_benchmark(market, snapshot: dict) -> dict:
    p = benchmark_path(market)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))

    # State kaybolursa journal'dan kurtar.
    for agent in AGENTS:
        for row in reversed(experiment_rows(market, agent["id"])):
            b = row.get("benchmark_state")
            if isinstance(b, dict):
                save_json(p, b)
                return b

    px = float(snapshot["benchmark"]["price"])
    state = {
        "symbol": market.benchmark_symbol,
        "name": market.benchmark_name,
        "t0_price": px,
        "units": market.start_cash / px,
    }
    save_json(p, state)
    return state


def benchmark_value(state: dict, current_price: float) -> float:
    return state["units"] * current_price


def apply_orders(portfolio: Portfolio, orders: list[dict], prices: dict, market, agent) -> list[dict]:
    fills = []

    # 1) SELL önce.
    for o in orders:
        if o["action"] != "SELL":
            continue
        symbol = o["symbol"]
        mid = prices.get(symbol)
        if mid is None:
            fills.append({"ok": False, "symbol": symbol, "why": "fiyat yok"})
            continue
        f = portfolio.sell(
            symbol,
            o["notional"],
            mid,
            market.unit_step,
            market.friction_rate,
        )
        f["requested_notional"] = o["notional"]
        fills.append(f)

    # 2) BUY risk budget.
    buys = [o for o in orders if o["action"] == "BUY"]
    if not buys:
        return fills

    equity = portfolio.value(prices)
    min_cash = agent["min_cash_pct"] * equity
    investable = max(0.0, portfolio.cash - min_cash)
    planned = []

    for o in buys:
        symbol = o["symbol"]
        mid = prices.get(symbol)
        if mid is None:
            fills.append({"ok": False, "symbol": symbol, "why": "fiyat yok"})
            continue
        current = portfolio.position_value(symbol, prices)
        cap = max(0.0, agent["max_position_pct"] * equity - current)
        amount = min(float(o["notional"]), cap)
        if amount <= 0:
            fills.append({"ok": False, "symbol": symbol, "why": "pozisyon risk limiti"})
            continue
        planned.append((o, amount, mid))

    total = sum(amount for _, amount, _ in planned)
    scale = min(1.0, investable / total) if total > 0 else 0.0

    for o, amount, mid in planned:
        scaled = amount * scale
        if scaled <= 0:
            fills.append({"ok": False, "symbol": o["symbol"], "why": "nakit risk tabanı"})
            continue
        f = portfolio.buy(
            o["symbol"],
            scaled,
            mid,
            market.unit_step,
            market.friction_rate,
        )
        f["requested_notional"] = o["notional"]
        f["risk_scaled_notional"] = round(scaled, 2)
        f["allocation_scale"] = round(scale, 8)
        fills.append(f)

    return fills


def run_agent(market, agent, snapshot: dict, benchmark_state: dict, ts: str) -> dict:
    agent_id = agent["id"]
    portfolio = load_portfolio(market, agent_id)
    prices = snapshot["prices"]
    tick = tick_number(market, agent_id)
    allowed = {c["symbol"] for c in snapshot["candidates"]} | set(portfolio.positions)
    held = set(portfolio.positions)
    require_buy = portfolio.trades == 0 and not portfolio.positions

    prompt = build_prompt(market, agent, portfolio, snapshot, prices, tick)
    res = call(
        prompt,
        allowed_symbols=allowed,
        held_symbols=held,
        max_orders=agent["max_orders"],
        require_buy=require_buy,
    )

    benchmark_px = float(snapshot["benchmark"]["price"])
    row = {
        "ts": ts,
        "tick": tick,
        "market": market.id,
        "market_name": market.name,
        "currency": market.currency,
        "start_cash": market.start_cash,
        "experiment_id": market.experiment_id,
        "agent": agent_id,
        "name": agent["name"],
        "risk_profile": {
            "min_cash_pct": agent["min_cash_pct"],
            "max_position_pct": agent["max_position_pct"],
            "max_orders": agent["max_orders"],
        },
        "model": NVIDIA_MODEL,
        "temperature": 0.0,
        "git_sha": os.environ.get("GITHUB_SHA"),
        "data_source": snapshot["source"],
        "market_snapshot": snapshot,
        "benchmark_state": benchmark_state,
        "benchmark_value": round(benchmark_value(benchmark_state, benchmark_px), 2),
        "benchmark_name": market.benchmark_name,
        "orders": res["orders"],
        "thesis": res["thesis"],
        "usage": res["usage"],
        "repaired": res.get("repaired", False),
        "ok": res["ok"],
        "error": res["error"],
    }

    if not res["ok"]:
        row.update({
            "gap": True,
            "fills": [],
            "equity": round(portfolio.value(prices), 2),
            "cash": round(portfolio.cash, 2),
            "positions": portfolio.positions,
            "trades": portfolio.trades,
            "friction_paid": round(portfolio.friction_paid, 2),
            "portfolio_state": portfolio.snapshot(),
        })
        write_journal(market, agent_id, row)
        return row

    fills = apply_orders(portfolio, res["orders"], prices, market, agent)
    row.update({
        "gap": False,
        "fills": fills,
        "equity": round(portfolio.value(prices), 2),
        "cash": round(portfolio.cash, 2),
        "positions": {k: round(v, 8) for k, v in portfolio.positions.items()},
        "trades": portfolio.trades,
        "friction_paid": round(portfolio.friction_paid, 2),
        "realized_pnl": round(portfolio.realized_pnl, 2),
        "portfolio_state": portfolio.snapshot(),
        "raw": res["raw"][:5000],
    })

    write_journal(market, agent_id, row)
    save_state(state_path(market, agent_id), portfolio)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", required=True, choices=sorted(MARKETS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    market = MARKETS[args.market]
    if not args.force and not market_open_now(market):
        print(f"[{market.id}] market kapalı; tick atlandı")
        return 0

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{market.id}] snapshot hazırlanıyor · {market.experiment_id}")
    try:
        snapshot = build_market_snapshot(market)
    except Exception as e:
        print(f"[{market.id}] MARKET DATA HATA: {e}")
        return 1

    benchmark_state = init_benchmark(market, snapshot)
    print(
        f"[{market.id}] benchmark {market.benchmark_name}="
        f"{snapshot['benchmark']['price']} · candidates="
        + ",".join(x["symbol"] for x in snapshot["candidates"])
    )

    if args.dry_run:
        for agent in AGENTS:
            pf = load_portfolio(market, agent["id"])
            p = build_prompt(market, agent, pf, snapshot, snapshot["prices"], tick_number(market, agent["id"]))
            print(f"\n===== {agent['name']} =====\n{p}")
        return 0

    failures = 0
    for agent in AGENTS:
        try:
            row = run_agent(market, agent, snapshot, benchmark_state, ts)
        except Exception as e:
            failures += 1
            print(f"[{market.id}:{agent['id']}] CRASH: {e}")
            continue

        if row["ok"]:
            actions = [
                f"{f.get('side')} {f.get('symbol')} {f.get('cash')}"
                for f in row["fills"] if f.get("ok")
            ]
            print(
                f"[{market.id}:{agent['id']}] tick={row['tick']} "
                f"eq={row['equity']} cash={row['cash']} "
                f"{' · '.join(actions) if actions else 'HOLD'}"
            )
        else:
            failures += 1
            print(f"[{market.id}:{agent['id']}] GAP {row['error']}")

    print(f"[{market.id}] done {len(AGENTS)-failures}/{len(AGENTS)}")
    return 0 if failures < len(AGENTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
