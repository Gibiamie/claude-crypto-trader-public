"""Broker-nötr paper portfolio ve state persistansı."""

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    cost_basis: dict[str, float] = field(default_factory=dict)
    realized_pnl: float = 0.0
    friction_paid: float = 0.0
    trades: int = 0

    @classmethod
    def fresh(cls, start_cash: float):
        return cls(cash=float(start_cash))

    def value(self, prices: dict[str, float]) -> float:
        return self.cash + sum(qty * prices.get(symbol, 0.0) for symbol, qty in self.positions.items())

    def position_value(self, symbol: str, prices: dict[str, float]) -> float:
        return self.positions.get(symbol, 0.0) * prices.get(symbol, 0.0)

    def snapshot(self) -> dict:
        return asdict(self)

    def avg_cost(self, symbol: str) -> float:
        qty = self.positions.get(symbol, 0.0)
        return (self.cost_basis.get(symbol, 0.0) / qty) if qty > 0 else 0.0

    def buy(self, symbol: str, cash_budget: float, mid: float, unit_step: float, friction_rate: float) -> dict:
        budget = min(max(float(cash_budget), 0.0), self.cash)
        fill = mid * (1 + friction_rate)
        if fill <= 0 or budget <= 0:
            return {"ok": False, "symbol": symbol, "why": "geçersiz fiyat/bütçe"}

        raw_qty = budget / fill
        if unit_step >= 1:
            qty = math.floor(raw_qty / unit_step) * unit_step
        else:
            qty = math.floor(raw_qty / unit_step) * unit_step
        if qty <= 0:
            return {"ok": False, "symbol": symbol, "why": "minimum işlem biriminin altında"}

        cost = qty * fill
        friction = qty * mid * friction_rate
        self.cash -= cost
        self.positions[symbol] = self.positions.get(symbol, 0.0) + qty
        self.cost_basis[symbol] = self.cost_basis.get(symbol, 0.0) + cost
        self.friction_paid += friction
        self.trades += 1
        return {
            "ok": True,
            "side": "BUY",
            "symbol": symbol,
            "qty": qty,
            "mid": mid,
            "fill": fill,
            "cash": round(cost, 2),
            "friction": round(friction, 4),
        }

    def sell(self, symbol: str, notional: float, mid: float, unit_step: float, friction_rate: float) -> dict:
        held = self.positions.get(symbol, 0.0)
        if held <= 0:
            return {"ok": False, "symbol": symbol, "why": "pozisyon yok"}

        fill = mid * (1 - friction_rate)
        desired_qty = max(float(notional), 0.0) / mid if mid > 0 else 0.0
        desired_qty = min(desired_qty, held)
        if unit_step >= 1:
            qty = math.floor(desired_qty / unit_step) * unit_step
        else:
            qty = math.floor(desired_qty / unit_step) * unit_step
        if qty <= 0:
            return {"ok": False, "symbol": symbol, "why": "minimum işlem biriminin altında"}

        gross_mid = qty * mid
        proceeds = qty * fill
        friction = gross_mid * friction_rate
        avg = self.avg_cost(symbol)

        self.cash += proceeds
        self.positions[symbol] = held - qty
        self.cost_basis[symbol] = max(self.cost_basis.get(symbol, 0.0) - qty * avg, 0.0)
        if self.positions[symbol] <= max(unit_step / 2, 1e-10):
            self.positions.pop(symbol, None)
            self.cost_basis.pop(symbol, None)
        self.realized_pnl += proceeds - qty * avg
        self.friction_paid += friction
        self.trades += 1
        return {
            "ok": True,
            "side": "SELL",
            "symbol": symbol,
            "qty": qty,
            "mid": mid,
            "fill": fill,
            "cash": round(proceeds, 2),
            "friction": round(friction, 4),
        }


def load_state(path: Path, start_cash: float) -> Portfolio:
    if not path.exists():
        return Portfolio.fresh(start_cash)
    return Portfolio(**json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, portfolio: Portfolio) -> None:
    _atomic_write(path, json.dumps(portfolio.snapshot(), indent=2, ensure_ascii=False))


def save_json(path: Path, value: dict) -> None:
    _atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False))
