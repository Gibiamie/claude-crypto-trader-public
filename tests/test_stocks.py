import unittest
from datetime import datetime, timezone

from stocks.agent import validate_payload
from stocks.config import MARKETS
from stocks.indicators import rsi, sma, summarize
from stocks.paper import Portfolio
from stocks.tick import apply_orders, market_open_now


class IndicatorTests(unittest.TestCase):
    def test_summary_has_expected_fields(self):
        bars = []
        for i in range(30):
            bars.append({
                "ts": 1_700_000_000 + i * 3600,
                "close": 100 + i,
                "volume": 1000 + i * 10,
            })
        s = summarize({"bars": bars, "price": 129.0}, benchmark_change20=10.0)
        self.assertIn("rsi14", s)
        self.assertIn("rel_20_pct", s)
        self.assertGreater(s["score"], 0)

    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3), 4)


class AgentValidationTests(unittest.TestCase):
    def test_reject_sell_without_position(self):
        payload = {
            "orders": [{
                "symbol": "AAPL", "action": "SELL", "notional": 100,
                "confidence": 0.5, "signals": ["score"], "reason": "test",
            }],
            "thesis": "test",
        }
        with self.assertRaisesRegex(ValueError, "elde olmayan"):
            validate_payload(payload, {"AAPL"}, set(), 3, False)

    def test_first_entry_requires_buy(self):
        with self.assertRaisesRegex(ValueError, "en az bir BUY"):
            validate_payload(
                {"orders": [], "thesis": "bekle"},
                {"AAPL"}, set(), 3, True,
            )


class RiskEngineTests(unittest.TestCase):
    def test_cash_floor_scales_buys(self):
        market = MARKETS["us"]
        agent = {
            "min_cash_pct": 0.70,
            "max_position_pct": 0.12,
        }
        pf = Portfolio.fresh(10_000)
        fills = apply_orders(
            pf,
            [
                {"symbol": "AAPL", "action": "BUY", "notional": 3000},
                {"symbol": "MSFT", "action": "BUY", "notional": 3000},
            ],
            {"AAPL": 100.0, "MSFT": 100.0},
            market,
            agent,
        )
        self.assertGreaterEqual(pf.cash, 6990)
        self.assertLessEqual(sum(f.get("cash", 0) for f in fills if f.get("ok")), 3005)

    def test_bist_whole_share(self):
        market = MARKETS["bist"]
        pf = Portfolio.fresh(100_000)
        f = pf.buy("TEST.IS", 1000, 333.0, market.unit_step, market.friction_rate)
        self.assertTrue(f["ok"])
        self.assertEqual(f["qty"], int(f["qty"]))


class SessionTests(unittest.TestCase):
    def test_bist_session(self):
        # 10:00 Europe/Istanbul = 07:00 UTC.
        self.assertTrue(market_open_now(
            MARKETS["bist"],
            datetime(2026, 9, 21, 7, 30, tzinfo=timezone.utc),
        ))
        self.assertFalse(market_open_now(
            MARKETS["bist"],
            datetime(2026, 9, 20, 7, 30, tzinfo=timezone.utc),  # Sunday
        ))


if __name__ == "__main__":
    unittest.main()
