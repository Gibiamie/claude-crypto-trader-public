import unittest

from agents import validate_payload


def payload(actions, reasons=True, thesis="ok"):
    coins = ["BTC", "ETH", "HYPE"]
    return {
        "decisions": [
            {
                "coin": coin,
                "action": action,
                "usd": 1000 if action in ("BUY", "SELL") else 0,
                "confidence": 0.5,
                "reason": "test" if reasons else "",
            }
            for coin, action in zip(coins, actions)
        ],
        "thesis": thesis,
    }


class ValidationTests(unittest.TestCase):
    def test_first_entry_requires_buy(self):
        with self.assertRaisesRegex(ValueError, "en az bir BUY"):
            validate_payload(payload(["SELL", "HOLD", "HOLD"]), require_buy=True)

    def test_first_entry_accepts_buy(self):
        result = validate_payload(payload(["BUY", "HOLD", "HOLD"]), require_buy=True)
        self.assertEqual(result["decisions"][0]["action"], "BUY")

    def test_reason_must_not_be_empty(self):
        with self.assertRaisesRegex(ValueError, "reason boş"):
            validate_payload(payload(["BUY", "HOLD", "HOLD"], reasons=False), require_buy=True)

    def test_thesis_must_not_be_empty(self):
        with self.assertRaisesRegex(ValueError, "thesis boş"):
            validate_payload(payload(["BUY", "HOLD", "HOLD"], thesis=""), require_buy=True)


if __name__ == "__main__":
    unittest.main()
