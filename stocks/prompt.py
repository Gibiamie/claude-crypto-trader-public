"""Stock agent prompt'u: karar alanları modelden, gerekçe snapshot'tan."""

import json


def build_prompt(market, agent, portfolio, snapshot: dict, prices: dict, tick: int) -> str:
    positions = []
    for symbol, qty in portfolio.positions.items():
        px = prices.get(symbol)
        if px is None:
            continue
        positions.append({
            "symbol": symbol,
            "qty": round(qty, 6),
            "price": px,
            "value": round(qty * px, 2),
            "avg_cost": round(portfolio.avg_cost(symbol), 4),
        })

    payload = {
        "market": market.name,
        "currency": market.currency,
        "tick": tick,
        "benchmark": snapshot["benchmark"],
        "portfolio": {
            "cash": round(portfolio.cash, 2),
            "equity": round(portfolio.value(prices), 2),
            "positions": positions,
        },
        "risk_limits": {
            "min_cash_pct": agent["min_cash_pct"],
            "max_position_pct": agent["max_position_pct"],
            "max_orders": agent["max_orders"],
            "short_selling": False,
        },
        "candidates": snapshot["candidates"],
    }

    first = (
        "Bu ilk giriş turudur. En az bir BUY emri vermelisin."
        if not portfolio.positions and portfolio.trades == 0
        else "İşlem yapmak zorunda değilsin; uygun değilse orders boş liste olabilir."
    )

    return f"""Sen {agent['name']} isimli paper portföy yöneticisisin.
Karakter: {agent['persona']}

AMAÇ
- Yalnız aşağıdaki snapshot ve mevcut portföye göre BUY/SELL kararı ver.
- Bu gerçek para değil, kontrollü paper-trading deneyidir.
- {first}

KESİN KURALLAR
1. Dış bilgi, haber, bilanço, analist görüşü veya snapshot'ta olmayan gösterge KULLANMA.
2. SELL yalnız mevcut pozisyonlar için olabilir. Açığa satış yok.
3. BUY yalnız candidates veya mevcut pozisyon sembollerinden olabilir.
4. Risk limitlerini ihlal edecek büyüklük isteme; execution motoru ayrıca limit uygular.
5. BUY/SELL notional değeri {market.currency} cinsindendir.
6. HOLD için emir yazma; işlem yoksa orders=[] kullan.
7. Her emir için yalnız kararında gerçekten kullandığın 1-4 signal alan adını seç.
8. signals yalnız şu alanlardan seçilebilir:
   last, sma20, rsi14, change_5_pct, change_20_pct, rel_20_pct,
   volume_ratio, volatility_20_pct, score
9. Değeri null olan bir signal seçme.
10. reason, thesis, yorum, haber veya serbest metin üretme.
   Sistem gerekçeyi seçtiğin signals alanlarının GERÇEK snapshot değerlerinden oluşturacak.

GİRDİ
{json.dumps(payload, ensure_ascii=False, indent=2)}

YALNIZ şu JSON şemasında cevap ver:
{{
  "orders": [
    {{
      "symbol": "AAPL",
      "action": "BUY",
      "notional": 1000,
      "confidence": 0.70,
      "signals": ["rel_20_pct", "score"]
    }}
  ]
}}
"""
