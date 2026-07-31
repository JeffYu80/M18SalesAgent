import unittest

from services.currency_service import M18CurrencyService


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_exchange_rate(self, cur_id, dom_cur_id, t_date, rate_field="openRate"):
        self.calls.append((cur_id, dom_cur_id, t_date, rate_field))
        return 0.1275

    def search_by_code(self, table_name, code):
        return {"values": [{"id": 3, "code": "USD", "sym": "USD"}]}


class FakeCustomerService:
    def get_customer_default_currency(self, **kwargs):
        return {"customerId": 100, "curId": 2}


class CurrencyServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.service = M18CurrencyService(
            client=self.client,
            customer_service=FakeCustomerService(),
            business_config={
                "entity_currency_by_be_id": {7: 3},
                "exchange_rate_field": "openRate",
            },
        )

    def test_customer_currency_uses_entity_mapping_and_document_date(self):
        result = self.service.resolve_customer_document_currency(7, "C001", "2026-08-15")

        self.assertEqual(result["curId"], 2)
        self.assertEqual(result["rate"], 0.1275)
        self.assertEqual(self.client.calls, [(2, 3, "2026-08-15", "openRate")])

    def test_source_currency_can_refresh_rate_without_customer_lookup(self):
        result = self.service.resolve_currency_rate(7, 2, "2026-08-15")

        self.assertEqual(result["curId"], 2)
        self.assertEqual(self.client.calls, [(2, 3, "2026-08-15", "openRate")])

    def test_explicit_currency_code_overrides_customer_default(self):
        result = self.service.resolve_document_currency(7, "2026-08-15", customer_code="C001", currency_code="USD")

        self.assertEqual(result["curId"], 3)
        self.assertEqual(self.client.calls, [(3, 3, "2026-08-15", "openRate")])

    def test_strict_entity_mapping_rejects_unknown_entity(self):
        service = M18CurrencyService(
            client=self.client,
            customer_service=FakeCustomerService(),
            business_config={"entity_currency_by_be_id": {}, "default_cur_id": 3, "require_entity_currency_mapping": True},
        )

        with self.assertRaisesRegex(ValueError, "beId=99"):
            service.resolve_currency_rate(99, 2, "2026-08-15")


if __name__ == "__main__":
    unittest.main()
