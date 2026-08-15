"""Tek tick: tüm agent'lar için piyasa çek → karar al → uygula → journal'a yaz.

Cron'dan saatlik çalışır. Üst üste binmeyi flock engeller (bkz. README).

Kritik: bir agent hata alırsa (Claude limiti, network, bozuk JSON) portföyü
DEĞİŞMEZ ve journal'a açık bir gap satırı yazılır. Sessiz atlama yok — grafikte
delik olduğu görülebilsin diye.
"""

import json
import sys
import time
from datetime import datetime, timezone

import hl
from agents import call
from broker import Portfolio, hodl_init, hodl_value
from config import AGENTS, ASSETS, CANDLE_LOOKBACK, INTERVAL, JOURNAL_DIR
from prompt import build

VALID_ACTIONS = {"BUY", "SELL", "HOLD"}


def journal_path(agent_id: str):
    return JOURNAL_DIR / f"{agent_id}.jsonl"


def read_history(agent_id: str, n: int = 40) -> list[dict]:
    p = journal_path(agent_id)
    if not p.exists():
        return []
    lines = p.read_text().strip().splitlines()[-n:]
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for d in row.get("decisions", []):
            if d.get("action") in ("BUY", "SELL"):
                out.append({"tick": row["tick"], **d})
    return out


def tick_number(agent_id: str) -> int:
    p = journal_path(agent_id)
    return sum(1 for _ in p.open()) if p.exists() else 0


def write_journal(agent_id: str, row: dict) -> None:
    """Journal'a append — tek kaynak-of-truth. Site bu dosyaları okur."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    with journal_path(agent_id).open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def fetch_market() -> tuple[dict, dict]:
    """(model için özet, etiket→canlı mid fiyat)"""
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
    fills = []
    for d in decisions:
        if not isinstance(d, dict):
            continue
        coin = str(d.get("coin", "")).upper()
        action = str(d.get("action", "")).upper()

        if coin not in prices:
            fills.append({"ok": False, "coin": coin, "why": "bilinmeyen varlık"})
            continue
        if action not in VALID_ACTIONS:
            fills.append({"ok": False, "coin": coin, "why": f"geçersiz action: {action}"})
            continue
        if action == "HOLD":
            continue

        try:
            usd = float(d.get("usd") or 0)
        except (TypeError, ValueError):
            fills.append({"ok": False, "coin": coin, "why": "usd sayı değil"})
            continue
        if usd <= 0:
            fills.append({"ok": False, "coin": coin, "why": "usd <= 0"})
            continue

        px = prices[coin]
        fills.append(pf.buy(coin, usd, px) if action == "BUY" else pf.sell(coin, usd, px))
    return fills


def run_agent(agent: dict, market: dict, prices: dict, hodl: float, ts: str) -> dict:
    agent_id = agent["id"]
    pf = Portfolio.load(agent_id)
    n = tick_number(agent_id)

    prompt = build(pf, market, prices, read_history(agent_id), n,
                   persona=agent.get("persona", ""))
    res = call(agent, prompt)

    row = {
        "ts": ts, "tick": n, "agent": agent_id, "label": agent["label"],
        # Kimlik alanları journal'a yazılır ki site config'e bağımlı olmasın —
        # bir tick'in hangi persona ile alındığı kaydın kendisinde dursun.
        "name": agent.get("name"), "tagline": agent.get("tagline"),
        "persona": agent.get("persona"),
        "model": agent.get("model"), "effort": agent.get("effort"),
        "ok": res["ok"], "error": res["error"],
        "prices": prices, "hodl": round(hodl, 2),
        "decisions": res["decisions"], "thesis": res["thesis"],
        "usage": res["usage"],
    }

    if not res["ok"]:
        # Gap: portföye dokunma, ama deliği açıkça kaydet.
        row.update({
            "fills": [], "equity": round(pf.value(prices), 2),
            "cash": round(pf.cash, 2), "positions": pf.positions, "gap": True,
        })
        write_journal(agent_id, row)
        return row

    fills = apply_decisions(pf, res["decisions"], prices)
    pf.save(agent_id)

    row.update({
        "fills": fills, "gap": False,
        "equity": round(pf.value(prices), 2),
        "cash": round(pf.cash, 2),
        "positions": {k: round(v, 8) for k, v in pf.positions.items()},
        "fees_paid": round(pf.fees_paid, 2),
        "trades": pf.trades,
        "raw": res["raw"][:4000],
    })
    write_journal(agent_id, row)
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
        # Piyasa verisi yoksa hiçbir agent karar veremez — hepsine gap yaz.
        print(f"[market] HATA — {e}")
        for a in agents:
            write_journal(a["id"], {"ts": ts, "tick": tick_number(a["id"]),
                                    "agent": a["id"], "ok": False, "gap": True,
                                    "error": f"market: {e}"})
        return 1

    hodl_init(prices)
    hodl = hodl_value(prices)
    print(f"[market] {ts} " + " ".join(f"{k}={v}" for k, v in prices.items()))
    print(f"[hodl]   {hodl:.2f}")

    if dry:
        for agent in agents:
            pf = Portfolio.load(agent["id"])
            n = tick_number(agent["id"])
            p = build(pf, market, prices, read_history(agent["id"]), n,
                      persona=agent.get("persona", ""))
            print(f"\n===== {agent['id']} · tick {n} · ~{len(p)//3.5:.0f} token =====")
            print(p)
        return 0

    failures = 0
    for agent in agents:
        try:
            row = run_agent(agent, market, prices, hodl, ts)
        except Exception as e:  # bir agent diğerlerini düşürmesin
            print(f"[{agent['id']}] BEKLENMEDİK — {e}")
            write_journal(agent["id"], {"ts": ts, "agent": agent["id"], "ok": False,
                                        "gap": True, "error": f"crash: {e}"})
            failures += 1
            continue

        if row["ok"]:
            acted = [f"{f['side']} {f['coin']} ${f['usd']}" for f in row["fills"] if f.get("ok")]
            print(f"[{agent['id']:16s}] eq={row['equity']:>9.2f} "
                  f"{'· '.join(acted) if acted else 'HOLD'}")
        else:
            failures += 1
            print(f"[{agent['id']:16s}] GAP — {row['error']}")

    print(f"[done] {len(agents) - failures}/{len(agents)} agent tamam")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
