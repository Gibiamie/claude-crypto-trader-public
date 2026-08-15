"""Hyperliquid read-only istemcisi.

Cüzdan, private key, KYC yok — sadece public /info endpoint'i.
"""

import json
import urllib.error
import urllib.request

INFO_URL = "https://api.hyperliquid.xyz/info"


class HLError(RuntimeError):
    pass


def _post(payload: dict, timeout: int = 20):
    req = urllib.request.Request(
        INFO_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise HLError(f"hyperliquid {payload.get('type')}: {e}") from e


def mids() -> dict[str, float]:
    """Canlı mid fiyatlar, spot pair `name` ile anahtarlanmış (@142 gibi)."""
    return {k: float(v) for k, v in _post({"type": "allMids"}).items()}


def closed_candles(coin: str, interval: str, count: int, now_ms: int) -> list[dict]:
    """Son `count` KAPALI mum.

    Son mum daima açıktır; modele verilirse lookahead bias yaratır — atılır.
    """
    span = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}[interval]
    start = now_ms - span * (count + 3)
    raw = _post({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": start, "endTime": now_ms},
    })
    closed = [c for c in raw if c["T"] < now_ms]
    if not closed:
        raise HLError(f"{coin}: kapalı mum yok")
    return closed[-count:]


def summarize(candles: list[dict]) -> dict:
    """Modele verilecek özet — ham mum yığını yerine okunabilir sinyaller."""
    closes = [float(c["c"]) for c in candles]
    vols = [float(c["v"]) for c in candles]
    n = len(closes)

    def sma(k: int) -> float | None:
        return sum(closes[-k:]) / k if n >= k else None

    gains = losses = 0.0
    for a, b in zip(closes[-15:], closes[-14:]):
        d = b - a
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    rsi = 100.0 if losses == 0 else 100 - 100 / (1 + (gains / 14) / (losses / 14))

    recent_vol = sum(vols[-6:]) / min(6, n)
    avg_vol = sum(vols) / n

    return {
        "closes": [round(c, 6) for c in closes[-24:]],
        "last": closes[-1],
        "sma20": round(sma(20), 6) if sma(20) else None,
        "sma50": round(sma(50), 6) if sma(50) else None,
        "rsi14": round(rsi, 1),
        "change_24c_pct": round((closes[-1] / closes[-24] - 1) * 100, 2) if n >= 24 else None,
        "change_all_pct": round((closes[-1] / closes[0] - 1) * 100, 2),
        "vol_ratio": round(recent_vol / avg_vol, 2) if avg_vol else None,
    }
