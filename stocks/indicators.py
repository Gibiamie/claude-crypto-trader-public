"""Basit, denetlenebilir teknik özetler."""

from statistics import pstdev


def sma(values: list[float], n: int) -> float:
    if len(values) < n:
        raise ValueError(f"SMA{n} için yetersiz veri")
    return sum(values[-n:]) / n


def rsi(values: list[float], n: int = 14) -> float:
    if len(values) < n + 1:
        raise ValueError("RSI için yetersiz veri")
    diffs = [values[i] - values[i - 1] for i in range(len(values) - n, len(values))]
    gains = sum(max(d, 0) for d in diffs) / n
    losses = sum(max(-d, 0) for d in diffs) / n
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))


def pct_change(values: list[float], bars: int) -> float:
    if len(values) <= bars:
        raise ValueError("change için yetersiz veri")
    base = values[-bars - 1]
    return ((values[-1] / base) - 1) * 100 if base else 0.0


def _volume_ratio(volumes: list[float]) -> float | None:
    positive = [float(v) for v in volumes if v is not None and float(v) > 0]
    if len(positive) < 4:
        return None

    latest = positive[-1]
    baseline = positive[:-1][-20:]
    if not baseline:
        return None
    avg = sum(baseline) / len(baseline)
    return latest / avg if avg > 0 else None


def summarize(chart: dict, benchmark_change20: float | None = None) -> dict:
    bars = chart["bars"]
    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]
    last20_returns = [
        ((closes[i] / closes[i - 1]) - 1) * 100
        for i in range(max(1, len(closes) - 20), len(closes))
        if closes[i - 1]
    ]

    volume_ratio = _volume_ratio(volumes)
    c5 = pct_change(closes, 5)
    c20 = pct_change(closes, 20)
    rel20 = c20 - benchmark_change20 if benchmark_change20 is not None else 0.0
    trend = 1.0 if chart["price"] >= sma(closes, 20) else -1.0
    volume_bonus = min(volume_ratio, 3.0) if volume_ratio is not None else 0.0

    # Ranking amaçlı basit ve tamamen gözlemlenebilir kompozit skor.
    score = c20 + 0.50 * c5 + 0.75 * rel20 + 1.5 * trend + volume_bonus

    return {
        "last": round(chart["price"], 6),
        "sma20": round(sma(closes, 20), 6),
        "rsi14": round(rsi(closes, 14), 2),
        "change_5_pct": round(c5, 2),
        "change_20_pct": round(c20, 2),
        "rel_20_pct": round(rel20, 2),
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "volatility_20_pct": round(pstdev(last20_returns) if len(last20_returns) > 1 else 0.0, 2),
        "score": round(score, 3),
        "bar_ts": bars[-1]["ts"],
    }
