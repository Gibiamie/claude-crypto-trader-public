"""Anahtarsız prototip market-data adapter'ı.

Bu endpoint resmi/lisanslı BIST feed'i değildir. Paper simülasyon ve entegrasyon
testi içindir; provider katmanı daha sonra Alpaca/lisanslı BIST feed'i ile değişebilir.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request


class MarketDataError(RuntimeError):
    pass


def fetch_chart(symbol: str, interval: str = "60m", range_: str = "10d") -> dict:
    encoded = urllib.parse.quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?interval={urllib.parse.quote(interval)}&range={urllib.parse.quote(range_)}"
        "&includePrePost=false&events=div%2Csplits"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 paper-market-lab/1.0",
            "Accept": "application/json",
        },
    )

    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == 2:
                raise MarketDataError(f"{symbol}: data fetch failed: {e}") from e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise MarketDataError(f"{symbol}: data fetch failed: {last_error}")

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise MarketDataError(f"{symbol}: {chart['error']}")

    results = chart.get("result") or []
    if not results:
        raise MarketDataError(f"{symbol}: empty chart result")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    bars = []
    for i, ts in enumerate(timestamps):
        try:
            c = closes[i]
        except IndexError:
            continue
        if c is None:
            continue
        bars.append({
            "ts": int(ts),
            "open": opens[i] if i < len(opens) else None,
            "high": highs[i] if i < len(highs) else None,
            "low": lows[i] if i < len(lows) else None,
            "close": float(c),
            "volume": float(volumes[i] or 0) if i < len(volumes) else 0.0,
        })

    if len(bars) < 25:
        raise MarketDataError(f"{symbol}: insufficient bars ({len(bars)})")

    meta = result.get("meta") or {}
    current = meta.get("regularMarketPrice")
    return {
        "symbol": symbol,
        "meta": meta,
        "bars": bars,
        "price": float(current) if current is not None else bars[-1]["close"],
    }
