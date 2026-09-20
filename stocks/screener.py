"""Aynı universe ve aynı market snapshot'tan deterministik aday seçimi."""

from .config import CANDIDATE_COUNT, DATA_SOURCE, INTERVAL, MIN_VALID_SYMBOLS, RANGE
from .indicators import pct_change, summarize
from .provider_yahoo import fetch_chart


def build_market_snapshot(market) -> dict:
    benchmark_chart = fetch_chart(market.benchmark_symbol, INTERVAL, RANGE)
    benchmark_closes = [b["close"] for b in benchmark_chart["bars"]]
    benchmark_change20 = pct_change(benchmark_closes, 20)

    rows = []
    errors = []
    for symbol in market.universe:
        try:
            chart = fetch_chart(symbol, INTERVAL, RANGE)
            metrics = summarize(chart, benchmark_change20)
            rows.append({"symbol": symbol, **metrics})
        except Exception as e:
            errors.append({"symbol": symbol, "error": str(e)[:220]})

    if len(rows) < MIN_VALID_SYMBOLS:
        raise RuntimeError(f"yalnız {len(rows)} geçerli sembol; minimum {MIN_VALID_SYMBOLS}")

    rows.sort(key=lambda x: x["score"], reverse=True)
    candidates = rows[:CANDIDATE_COUNT]

    return {
        "source": DATA_SOURCE,
        "interval": INTERVAL,
        "universe_size": len(market.universe),
        "valid_symbols": len(rows),
        "errors": errors,
        "benchmark": {
            "symbol": market.benchmark_symbol,
            "name": market.benchmark_name,
            "price": round(benchmark_chart["price"], 6),
            "change_20_pct": round(benchmark_change20, 2),
            "bar_ts": benchmark_chart["bars"][-1]["ts"],
        },
        "candidates": candidates,
        "all_symbols": rows,
        "prices": {r["symbol"]: r["last"] for r in rows},
    }
