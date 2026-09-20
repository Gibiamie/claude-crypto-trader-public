import unittest
from datetime import datetime, timezone

from stocks.agent import validate_payload
from stocks.config import MARKETS
from stocks.grounding import ground_orders
from stocks.indicators import sma, summarize
from stocks.paper import Portfolio
from stocks.tick import apply_orders, market_open_now, snapshot_is_current_session


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
        self.assertIsNotNone(s["volume_ratio"])

    def test_zero_latest_volume_uses_last_nonzero_bar(self):
        bars = []
        for i in range(30):
            bars.append({
                "ts": 1_700_000_000 + i * 3600,
                "close": 100 + i,
                "volume": 0 if i == 29 else 1000 + i * 10,
            })
        s = summarize({"bars": bars, "price": 129.0}, benchmark_change20=10.0)
        self.assertIsNotNone(s["volume_ratio"])
        self.assertGreater(s["volume_ratio"], 0)

    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3), 4)


class AgentValidationTests(unittest.TestCase):
    def test_reject_sell_without_position(self):
        payload = {
            "orders": [{
                "symbol": "AAPL",
                "action": "SELL",
                "notional": 100,
                "confidence": 0.5,
                "signals": ["score"],
            }],
        }
        with self.assertRaisesRegex(ValueError, "elde olmayan"):
            validate_payload(payload, {"AAPL"}, set(), 3, False)

    def test_first_entry_requires_buy(self):
        with self.assertRaisesRegex(ValueError, "en az bir BUY"):
            validate_payload({"orders": []}, {"AAPL"}, set(), 3, True)

    def test_rejects_model_free_text_fields(self):
        payload = {
            "orders": [{
                "symbol": "AAPL",
                "action": "BUY",
                "notional": 100,
                "confidence": 0.5,
                "signals": ["score"],
                "reason": "SMA200 says buy",
            }],
        }
        with self.assertRaisesRegex(ValueError, "izin verilmeyen alan"):
            validate_payload(payload, {"AAPL"}, set(), 3, True)


class GroundingTests(unittest.TestCase):
    def test_reason_is_built_from_snapshot_values(self):
        snapshot = {
            "all_symbols": [{
                "symbol": "AAPL",
                "last": 100.0,
                "sma20": 98.0,
                "rsi14": 61.25,
                "change_5_pct": 2.5,
                "change_20_pct": 5.0,
                "rel_20_pct": 3.0,
                "volume_ratio": 1.25,
                "volatility_20_pct": 1.1,
                "score": 8.125,
            }]
        }
        orders, thesis = ground_orders(
            [{
                "symbol": "AAPL",
                "action": "BUY",
                "notional": 1000.0,
                "confidence": 0.75,
                "signals": ["rel_20_pct", "score"],
            }],
            snapshot,
            "USD",
        )
        self.assertEqual(orders[0]["reason"], "rel_20_pct=3.00%; score=8.125")
        self.assertIn("BUY AAPL 1000.00 USD", thesis)
        self.assertNotIn("SMA50", thesis)


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
        self.assertTrue(market_open_now(
            MARKETS["bist"],
            datetime(2026, 9, 21, 7, 30, tzinfo=timezone.utc),
        ))
        self.assertFalse(market_open_now(
            MARKETS["bist"],
            datetime(2026, 9, 20, 7, 30, tzinfo=timezone.utc),
        ))

    def test_stale_bar_is_rejected(self):
        now = datetime(2026, 9, 21, 8, 30, tzinfo=timezone.utc)
        current_bar = int(datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc).timestamp())
        stale_bar = int(datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc).timestamp())

        self.assertTrue(snapshot_is_current_session(
            MARKETS["bist"],
            {"benchmark": {"bar_ts": current_bar}},
            now,
        ))
        self.assertFalse(snapshot_is_current_session(
            MARKETS["bist"],
            {"benchmark": {"bar_ts": stale_bar}},
            now,
        ))


if __name__ == "__main__":
    unittest.main()
