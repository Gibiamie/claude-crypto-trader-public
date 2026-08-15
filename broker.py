"""Paper broker — spot, kaldıraçsız, ücret + slippage simülasyonlu.

Fill fiyatı karar anındaki canlı mid'den alınır (allMids), kapanmamış mumun
close'undan DEĞİL. Bu lookahead bias'ı engeller.
"""

import json
from dataclasses import dataclass, field, asdict

from config import MIN_TRADE_USD, SLIPPAGE, START_CASH, STATE_DIR, TAKER_FEE


@dataclass
class Portfolio:
    cash: float = START_CASH
    positions: dict[str, float] = field(default_factory=dict)   # etiket -> adet
    cost_basis: dict[str, float] = field(default_factory=dict)  # etiket -> toplam USD
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    trades: int = 0

    # ---- değerleme ----

    def value(self, prices: dict[str, float]) -> float:
        v = self.cash
        for label, qty in self.positions.items():
            v += qty * prices[label]
        return v

    def avg_cost(self, label: str) -> float | None:
        qty = self.positions.get(label, 0.0)
        if qty <= 0:
            return None
        return self.cost_basis.get(label, 0.0) / qty

    # ---- emirler ----

    def buy(self, label: str, usd: float, price: float) -> dict:
        if usd < MIN_TRADE_USD:
            return {"ok": False, "why": f"min emir {MIN_TRADE_USD} USD"}
        usd = min(usd, self.cash)
        if usd < MIN_TRADE_USD:
            return {"ok": False, "why": "yetersiz nakit"}

        fill = price * (1 + SLIPPAGE)
        fee = usd * TAKER_FEE
        qty = (usd - fee) / fill

        self.cash -= usd
        self.positions[label] = self.positions.get(label, 0.0) + qty
        self.cost_basis[label] = self.cost_basis.get(label, 0.0) + (usd - fee)
        self.fees_paid += fee
        self.trades += 1
        return {"ok": True, "side": "BUY", "coin": label, "usd": round(usd, 2),
                "qty": qty, "fill": fill, "fee": round(fee, 4)}

    def sell(self, label: str, usd: float, price: float) -> dict:
        held = self.positions.get(label, 0.0)
        if held <= 0:
            return {"ok": False, "why": "pozisyon yok (açığa satış kapalı)"}

        fill = price * (1 - SLIPPAGE)
        qty = min(usd / fill, held)
        gross = qty * fill
        if gross < MIN_TRADE_USD:
            return {"ok": False, "why": f"min emir {MIN_TRADE_USD} USD"}

        fee = gross * TAKER_FEE
        net = gross - fee
        avg = self.avg_cost(label) or 0.0

        self.cash += net
        self.positions[label] = held - qty
        self.cost_basis[label] = max(self.cost_basis.get(label, 0.0) - qty * avg, 0.0)
        if self.positions[label] <= 1e-12:
            self.positions.pop(label, None)
            self.cost_basis.pop(label, None)
        self.realized_pnl += net - qty * avg
        self.fees_paid += fee
        self.trades += 1
        return {"ok": True, "side": "SELL", "coin": label, "usd": round(gross, 2),
                "qty": qty, "fill": fill, "fee": round(fee, 4)}

    # ---- kalıcılık ----

    @staticmethod
    def path(agent_id: str):
        return STATE_DIR / f"{agent_id}.json"

    @classmethod
    def load(cls, agent_id: str) -> "Portfolio":
        p = cls.path(agent_id)
        if not p.exists():
            return cls()
        return cls(**json.loads(p.read_text()))

    def save(self, agent_id: str) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.path(agent_id).write_text(json.dumps(asdict(self), indent=2))


# ---- HODL benchmark ----------------------------------------------------
# t0'da eşit ağırlık alınıp hiç dokunulmayan portföy. Deney başında bir kez
# sabitlenir; sonradan değiştirilirse kıyas anlamını yitirir.

HODL_PATH = STATE_DIR / "_hodl.json"


def hodl_init(prices: dict[str, float]) -> dict:
    if HODL_PATH.exists():
        return json.loads(HODL_PATH.read_text())
    per = START_CASH / len(prices)
    snap = {
        "t0_prices": prices,
        "qty": {label: (per * (1 - TAKER_FEE)) / (px * (1 + SLIPPAGE))
                for label, px in prices.items()},
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    HODL_PATH.write_text(json.dumps(snap, indent=2))
    return snap


def hodl_value(prices: dict[str, float]) -> float:
    snap = json.loads(HODL_PATH.read_text())
    return sum(q * prices[label] for label, q in snap["qty"].items())
