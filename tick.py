"""Tek V2 tick: market → karar → stateful paper execution → journal."""

import json
import os
import sys
import time
from datetime import datetime, timezone

import hl
from agents import call
from broker import Portfolio, hodl_init, hodl_restore, hodl_value
from config import (
    AGENTS,
    ASSETS,
    CANDLE_LOOKBACK,
    EXPERIMENT_ID,
    INTERVAL,
    JOURNAL_DIR,
    MODEL_TEMPERATURE,
    SCHEMA_VERSION,
    STRATEGY_VERSION,
)
from prompt import build


def journal_path(agent_id: str):
    return JOURNAL_DIR / f"{agent_id}.jsonl"


def _read_rows(agent_id: str) -> list[dict]:
    p = journal_path(agent_id)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def experiment_rows(agent_id: str) -> list[dict]:
    return [r for r in _read_rows(agent_id) if r.get("experiment_id") == EXPERIMENT_ID]


def read_history(agent_id: str, n: int = 40) -> list[dict]:
    rows = experiment_rows(agent_id)[-n:]
    out = []
    for row in rows:
        for d in row.get("decisions", []):
            if d.get("action") in ("BUY", "SELL"):
                out.append({"tick": row.get("tick"), **d})
    return out[-8:]


def tick_number(agent_id: str) -> int:
    return len(experiment_rows(agent_id))


def write_journal(agent_id: str, row: dict) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    with journal_path(agent_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_portfolio(agent_id: str) -> Portfolio:
    """Journal source-of-truth; state dosyası yalnız kalıcı cache/backup."""
    for row in reversed(experiment_rows(agent_id)):
        snap = row.get("portfolio_state")
        if isinstance(snap, dict):
            return Portfolio(**snap)
    if Portfolio.path(agent_id).exists():
        return Portfolio.load(agent_id)
    return Portfolio()


def recover_hodl_from_journal() -> bool:
    """_hodl.json kaybolursa journal içindeki son benchmark snapshot'ını geri yükle."""
    for agent in AGENTS:
        for row in reversed(experiment_rows(agent["id"])):
            snap = row.get("hodl_state")
            if isinstance(snap, dict) and snap.get("qty") and snap.get("t0_prices"):
                hodl_restore(snap)
                return True
    return False


def fetch_market() -> tuple[dict, dict]:
    now_ms = int(time.time() * 1000)
    all_mids = hl.mids()
    market, prices = {}, {}
    for label, pair in ASSETS.items():
        if pair not in all_mids:
            raise hl.HLError(f"{label} ({pair}) allMids'te yok")
        prices[label] = all_mids[pair]
        candles = hl.closed_candles(pair, INTERVAL, CANDLE_LOOKBACK, now_ms)
        market[label] = hl.summarize(candles)
        market[label]["mid_simdi"] = all_mids[pair]
    return market, prices


def apply_decisions(pf: Portfolio, decisions: list, prices: dict) -> list[dict]:
    """SELL'leri önce uygula; BUY'ları mevcut nakde oransal ölçekle."""
    fills = []

    for d in decisions:
        if d["action"] != "SELL":
            continue
        coin = d["coin"]
        requested = float(d["usd"])
        f = pf.sell(coin, requested, prices[coin])
        f["requested_usd"] = round(requested, 2)
        fills.append(f)

    buys = [d for d in decisions if d["action"] == "BUY"]
    requested_total = sum(float(d["usd"]) for d in buys)
    available = max(pf.cash, 0.0)
    scale = min(1.0, available / requested_total) if requested_total > 0 else 1.0

    for d in buys:
        coin = d["coin"]
        requested = float(d["usd"])
        executed = requested * scale
        f = pf.buy(coin, executed, prices[coin])
        f["requested_usd"] = round(requested, 2)
        f["allocation_scale"] = round(scale, 8)
        fills.append(f)

    return fills


def meta(ts: str, agent: dict, tick: int) -> dict:
    return {
        "ts": ts,
        "tick": tick,
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "git_sha": os.environ.get("GITHUB_SHA"),
        "agent": agent["id"],
        "label": agent["label"],
        "name": agent.get("name"),
        "tagline": agent.get("tagline"),
        "persona": agent.get("persona"),
        "model": agent.get("model"),
        "effort": agent.get("effort"),
        "temperature": MODEL_TEMPERATURE,
    }


def run_agent(agent: dict, market: dict, prices: dict, hodl: float, hodl_state: dict, ts: str) -> dict:
    agent_id = agent["id"]
    pf = load_portfolio(agent_id)
    # İlk V2 tick'i model hatası verse bile başlangıç state'i kalıcı olsun.
    pf.save(agent_id)
    n = tick_number(agent_id)

    first_entry = pf.trades == 0 and not pf.positions
    prompt_tick = 0 if first_entry else n
    prompt = build(pf, market, prices, read_history(agent_id), prompt_tick, persona=agent.get("persona", ""))
    res = call(agent, prompt, require_buy=first_entry)

    row = {
        **meta(ts, agent, n),
        "ok": res["ok"],
        "error": res["error"],
        "prices": prices,
        "market_snapshot": market,
        "hodl": round(hodl, 2),
        "hodl_state": hodl_state,
        "benchmark": "BTC/ETH/HYPE equal-weight buy-and-hold",
        "decisions": res["decisions"],
        "thesis": res["thesis"],
        "usage": res["usage"],
        "repaired": res.get("repaired", False),
    }

    if not res["ok"]:
        row.update({
            "fills": [],
            "equity": round(pf.value(prices), 2),
            "cash": round(pf.cash, 2),
            "positions": {k: round(v, 8) for k, v in pf.positions.items()},
            "fees_paid": round(pf.fees_paid, 2),
            "trades": pf.trades,
            "portfolio_state": pf.snapshot(),
            "gap": True,
        })
        write_journal(agent_id, row)
        return row

    fills = apply_decisions(pf, res["decisions"], prices)

    row.update({
        "fills": fills,
        "gap": False,
        "equity": round(pf.value(prices), 2),
        "cash": round(pf.cash, 2),
        "positions": {k: round(v, 8) for k, v in pf.positions.items()},
        "fees_paid": round(pf.fees_paid, 2),
        "trades": pf.trades,
        "realized_pnl": round(pf.realized_pnl, 2),
        "portfolio_state": pf.snapshot(),
        "raw": res["raw"][:4000],
    })
    # Journal transaction kaydıdır. State journal'dan sonra yazılır; yarıda kesilirse
    # sonraki run load_portfolio() ile journal snapshot'ından toparlar.
    write_journal(agent_id, row)
    pf.save(agent_id)
    return row


def main(argv: list[str]) -> int:
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    dry = "--dry-run" in argv
    agents = [a for a in AGENTS if only is None or a["id"] == only]
    if not agents:
        print(f"agent bulunamadı: {only}")
        return 2

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        market, prices = fetch_market()
    except hl.HLError as e:
        print(f"[market] HATA — {e}")
        for a in agents:
            write_journal(a["id"], {
                **meta(ts, a, tick_number(a["id"])),
                "ok": False,
                "gap": True,
                "error": f"market: {e}",
            })
        return 1

    recover_hodl_from_journal()
    hodl_state = hodl_init(prices)
    hodl = hodl_value(prices)
    print(f"[experiment] {EXPERIMENT_ID}")
    print(f"[market] {ts} " + " ".join(f"{k}={v}" for k, v in prices.items()))
    print(f"[hodl]   {hodl:.2f}")

    if dry:
        for agent in agents:
            pf = load_portfolio(agent["id"])
            n = tick_number(agent["id"])
            prompt_tick = 0 if pf.trades == 0 and not pf.positions else n
            p = build(pf, market, prices, read_history(agent["id"]), prompt_tick, persona=agent.get("persona", ""))
            print(f"\n===== {agent['id']} · tick {n} · ~{len(p)//3.5:.0f} token =====")
            print(p)
        return 0

    failures = 0
    for agent in agents:
        try:
            row = run_agent(agent, market, prices, hodl, hodl_state, ts)
        except Exception as e:
            print(f"[{agent['id']}] BEKLENMEDİK — {e}")
            pf = load_portfolio(agent["id"])
            write_journal(agent["id"], {
                **meta(ts, agent, tick_number(agent["id"])),
                "ok": False,
                "gap": True,
                "error": f"crash: {e}",
                "equity": round(pf.value(prices), 2),
                "cash": round(pf.cash, 2),
                "positions": {k: round(v, 8) for k, v in pf.positions.items()},
                "fees_paid": round(pf.fees_paid, 2),
                "trades": pf.trades,
                "portfolio_state": pf.snapshot(),
            })
            failures += 1
            continue

        if row["ok"]:
            acted = [
                f"{f.get('side')} {f.get('coin')} ${f.get('usd')}"
                for f in row["fills"] if f.get("ok")
            ]
            print(f"[{agent['id']:16s}] eq={row['equity']:>9.2f} "
                  f"{' · '.join(acted) if acted else 'HOLD'}")
        else:
            failures += 1
            print(f"[{agent['id']:16s}] GAP — {row['error']}")

    print(f"[done] {len(agents) - failures}/{len(agents)} agent tamam")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
