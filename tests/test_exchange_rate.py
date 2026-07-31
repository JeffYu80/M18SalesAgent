import unittest

from m18_api import M18APIError, M18Client


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class ExchangeRateTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(M18Client)
        self.request_args = None

    def _respond_with(self, payload):
        def request(*args, **kwargs):
            self.request_args = (args, kwargs)
            return FakeResponse(payload)

        self.client._request = request

    def test_same_currency_returns_one_without_request(self):
        self.assertEqual(self.client.get_exchange_rate(3, 3, "2026-07-31"), 1.0)

    def test_uses_documented_headers_and_open_rate(self):
        self._respond_with({"values": [{"openRate": 7.25, "closeRate": 7.3}]})

        rate = self.client.get_exchange_rate(2, 3, "2026-07-31")

        self.assertEqual(rate, 7.25)
        self.assertEqual(
            self.request_args[1]["extra_headers"],
            {"curId": "2", "domCurId": "3", "tDate": "2026-07-31"},
        )

    def test_rejects_missing_rate_data(self):
        self._respond_with({"values": []})

        with self.assertRaisesRegex(M18APIError, "no openRate"):
            self.client.get_exchange_rate(2, 3, "2026-07-31")


if __name__ == "__main__":
    unittest.main()
