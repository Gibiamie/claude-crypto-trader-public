"""Piyasa anlık görüntüsü + portföy → model promptu.

Tüm agent'lar aynı model, aynı effort ve aynı veriyi alır. **Tek değişken risk
profili (persona).** Başka hiçbir şeyi agent'a göre değiştirme — aksi halde
leaderboard "risk iştahı ne değiştiriyor" sorusunu ölçmez.
"""

import json

from config import MIN_TRADE_USD, SLIPPAGE, TAKER_FEE
from broker import Portfolio

SYSTEM = (
    "Kripto alıp satan bir yatırımcısın.\n"
    "Sadece elindeki nakitle (USDC) alabilir, sadece elindeki coini satabilirsin. "
    "Kaldıraç yok, açığa satış yok.\n"
    "Verdiğin karar bir saat geçerli olacak.\n"
    "Cevabın sadece JSON olsun. Açıklama, markdown veya kod bloğu yazma."
)

SCHEMA = (
    '{"decisions":[{"coin":"<varlık>","action":"BUY|SELL|HOLD",'
    '"usd":<sayı>,"confidence":<0-1>,"reason":"<en fazla 2 cümle>"}],'
    '"thesis":"<portföyün geneline dair en fazla 3 cümle>"}'
)


def build(portfolio: Portfolio, market: dict, prices: dict[str, float],
          history: list[dict], tick: int, persona: str = "") -> str:
    equity = portfolio.value(prices)

    holdings = {}
    for label in market:
        qty = portfolio.positions.get(label, 0.0)
        holdings[label] = {
            "adet": round(qty, 8),
            "usd_deger": round(qty * prices[label], 2),
            "ort_maliyet": round(portfolio.avg_cost(label), 4) if portfolio.avg_cost(label) else None,
            "guncel_fiyat": prices[label],
        }

    recent = [
        {"tick": h["tick"], "coin": h["coin"], "action": h["action"],
         "usd": h.get("usd"), "reason": h.get("reason", "")[:120]}
        for h in history[-8:]
    ]

    payload = {
        "tick": tick,
        "portfoy": {
            "nakit_usdc": round(portfolio.cash, 2),
            "varliklar": holdings,
            "toplam_deger": round(equity, 2),
            "baslangic": 10000.0,
            "pnl_pct": round((equity / 10000.0 - 1) * 100, 2),
            "gerceklesen_pnl": round(portfolio.realized_pnl, 2),
            "odenen_ucret": round(portfolio.fees_paid, 2),
            "islem_sayisi": portfolio.trades,
        },
        "piyasa": market,
        "son_kararlarin": recent,
        "kurallar": {
            "taker_ucreti_pct": round(TAKER_FEE * 100, 4),
            "slippage_pct": round(SLIPPAGE * 100, 4),
            "min_emir_usd": MIN_TRADE_USD,
            "not": (
                "Her saat işlem yapmak zorunda değilsin. Boşuna alıp satmak "
                "ücret olarak birikir ve kazancını yer. Beklemek de bir karardır."
            ),
            "hedef": (
                "Karakterin, paranın ne kadarını yatıracağını belirler. "
                "Sürekli nakitte oturmak hiçbir karakterin işi değil."
            ),
        },
    }

    head = f"{SYSTEM}\n\n"
    if persona:
        head += f"{persona}\n\n"

    # Tick 0'da portföy %100 nakit. Kurulum tick'i olduğu için giriş zorunlu:
    # deneyin amacı "işlem yapmalı mı" değil, "hangi risk oranıyla girmeli".
    if tick == 0:
        head += (
            "Bu ilk saat. Elinde sadece nakit var, hiç coin yok.\n"
            "İlk alımını şimdi yap. Üç varlık için birden BEKLE deme.\n"
            "Ne kadar alacağına ve ne kadar nakit bırakacağına sen karar ver. "
            "Karakterine uygun davran.\n\n"
        )

    return (
        head
        + f"VERİ:\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n\n"
        + f"Her varlık için bir karar ver. Sadece şu şemada JSON döndür:\n{SCHEMA}"
    )
