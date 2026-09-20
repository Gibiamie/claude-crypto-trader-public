import unittest

from broker import Portfolio
from tick import apply_decisions


class ExecutionTests(unittest.TestCase):
    def test_oversubscribed_buys_are_scaled_proportionally(self):
        pf = Portfolio()
        prices = {"BTC": 100.0, "ETH": 100.0, "HYPE": 100.0}
        decisions = [
            {"coin": "BTC", "action": "BUY", "usd": 5000.0},
            {"coin": "ETH", "action": "BUY", "usd": 4000.0},
            {"coin": "HYPE", "action": "BUY", "usd": 2000.0},
        ]
        fills = apply_decisions(pf, decisions, prices)
        executed = [f["usd"] for f in fills if f.get("ok")]
        self.assertLessEqual(abs(sum(executed) - 10000.0), 0.02)
        self.assertAlmostEqual(fills[0]["allocation_scale"], 10000 / 11000, places=7)
        self.assertAlmostEqual(pf.cash, 0.0, places=6)

    def test_sells_execute_before_buys(self):
        pf = Portfolio()
        prices = {"BTC": 100.0, "ETH": 100.0, "HYPE": 100.0}
        pf.buy("HYPE", 5000.0, 100.0)
        decisions = [
            {"coin": "BTC", "action": "BUY", "usd": 6500.0},
            {"coin": "ETH", "action": "HOLD", "usd": 0.0},
            {"coin": "HYPE", "action": "SELL", "usd": 2000.0},
        ]
        fills = apply_decisions(pf, decisions, prices)
        self.assertEqual(fills[0]["side"], "SELL")
        self.assertEqual(fills[1]["side"], "BUY")
        self.assertGreater(fills[1]["usd"], 6000)

    def test_buy_fee_is_in_cost_basis(self):
        pf = Portfolio()
        pf.buy("BTC", 1000.0, 100.0)
        self.assertAlmostEqual(pf.cost_basis["BTC"], 1000.0, places=8)
        pf.sell("BTC", 100000.0, 100.0)
        self.assertLess(pf.realized_pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
