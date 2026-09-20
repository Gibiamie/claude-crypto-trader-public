"""Paper broker — spot, kaldıraçsız, fee + slippage simülasyonlu."""

import json
from dataclasses import asdict, dataclass, field

from config import MIN_TRADE_USD, SLIPPAGE, START_CASH, STATE_DIR, TAKER_FEE


def _atomic_write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


@dataclass
class Portfolio:
    cash: float = START_CASH
    positions: dict[str, float] = field(default_factory=dict)
    cost_basis: dict[str, float] = field(default_factory=dict)
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    trades: int = 0

    def value(self, prices: dict[str, float]) -> float:
        return self.cash + sum(qty * prices[label] for label, qty in self.positions.items())

    def avg_cost(self, label: str) -> float | None:
        qty = self.positions.get(label, 0.0)
        if qty <= 0:
            return None
        return self.cost_basis.get(label, 0.0) / qty

    def snapshot(self) -> dict:
        return asdict(self)

    def buy(self, label: str, usd: float, price: float) -> dict:
        if usd < MIN_TRADE_USD:
            return {"ok": False, "why": f"min emir {MIN_TRADE_USD} USD", "coin": label}
        usd = min(usd, self.cash)
        if usd < MIN_TRADE_USD:
            return {"ok": False, "why": "yetersiz nakit", "coin": label}

        fill = price * (1 + SLIPPAGE)
        fee = usd * TAKER_FEE
        qty = (usd - fee) / fill

        self.cash -= usd
        self.positions[label] = self.positions.get(label, 0.0) + qty
        self.cost_basis[label] = self.cost_basis.get(label, 0.0) + usd
        self.fees_paid += fee
        self.trades += 1
        return {
            "ok": True, "side": "BUY", "coin": label, "usd": round(usd, 2),
            "qty": qty, "fill": fill, "fee": round(fee, 4),
        }

    def sell(self, label: str, usd: float, price: float) -> dict:
        held = self.positions.get(label, 0.0)
        if held <= 0:
            return {"ok": False, "why": "pozisyon yok (açığa satış kapalı)", "coin": label}

        fill = price * (1 - SLIPPAGE)
        qty = min(usd / fill, held)
        gross = qty * fill
        if gross < MIN_TRADE_USD:
            return {"ok": False, "why": f"min emir {MIN_TRADE_USD} USD", "coin": label}

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
        return {
            "ok": True, "side": "SELL", "coin": label, "usd": round(gross, 2),
            "qty": qty, "fill": fill, "fee": round(fee, 4),
        }

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
        _atomic_write(self.path(agent_id), json.dumps(asdict(self), indent=2))


HODL_PATH = STATE_DIR / "_hodl.json"


def hodl_restore(snap: dict) -> None:
    _atomic_write(HODL_PATH, json.dumps(snap, indent=2))


def hodl_init(prices: dict[str, float]) -> dict:
    if HODL_PATH.exists():
        return json.loads(HODL_PATH.read_text())
    per = START_CASH / len(prices)
    snap = {
        "t0_prices": prices,
        "qty": {
            label: (per * (1 - TAKER_FEE)) / (px * (1 + SLIPPAGE))
            for label, px in prices.items()
        },
    }
    hodl_restore(snap)
    return snap


def hodl_value(prices: dict[str, float]) -> float:
    snap = json.loads(HODL_PATH.read_text())
    return sum(q * prices[label] for label, q in snap["qty"].items())
