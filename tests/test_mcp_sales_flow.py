import json
import unittest
from unittest.mock import patch

import mcp_sales


class FakeCurrencyService:
    def resolve_document_currency(self, **kwargs):
        return {"curId": 2, "rate": 0.1}


class FakeQuotationService:
    def __init__(self):
        self.currency_service = FakeCurrencyService()
        self.calls = []

    def create_draft_from_codes(self, **kwargs):
        self.calls.append(kwargs)
        return {"tranId": 10, "tranCode": "QU10", "status": True}


class FakeSalesOrderService:
    def __init__(self):
        self.calls = []

    def create_draft_from_codes(self, **kwargs):
        self.calls.append(kwargs)
        return {"tranId": 20, "tranCode": "SO20", "status": True}


class FakeClient:
    def save_entity(self, menu_code, payload):
        self.saved = (menu_code, payload)
        return {"status": True, "recordId": 11}

    def read_entity(self, menu_code, record_id):
        return {"mainqu": {"values": [{"curId": 2, "rate": 0.1}]}}


class FakeRateService:
    def __init__(self, client=None):
        self.client = client

    def resolve_currency_rate(self, be_id, cur_id, t_date):
        return {"curId": cur_id, "rate": 0.2}


class QuotationToOrderFlowTests(unittest.TestCase):
    def test_order_keeps_quotation_currency_and_refreshes_rate_for_order_date(self):
        quotation_service = FakeQuotationService()
        order_service = FakeSalesOrderService()
        client = FakeClient()

        with (
            patch.object(mcp_sales, "_auth_svc", side_effect=[quotation_service, order_service]),
            patch.object(mcp_sales, "_biz_config", {"be_mapping": {"SHK": 4}, "quotation_to_order_rate_policy": "refresh"}),
            patch.object(mcp_sales, "M18Client", return_value=client),
            patch.object(mcp_sales, "M18CurrencyService", FakeRateService),
            patch.object(mcp_sales, "_resolve_staff", return_value=200),
            patch.object(mcp_sales, "_load_customer_terms", return_value={"payTerm": "", "tradeTerm": ""}),
            patch.object(mcp_sales, "_get_part_info", return_value={}),
            patch.object(mcp_sales, "M18ReferenceResolver") as resolver_class,
        ):
            resolver_class.return_value.resolve_customer_code.return_value = 101
            resolver_class.return_value.resolve_product_code.return_value = 201
            resolver_class.return_value.resolve_unit_code.return_value = 301
            result = mcp_sales.create_quotation_and_order(
                customer_code="C001", product_code="P001", qty=1, up=10,
                username="user", password="password", be_code="SHK", be_id=4,
                customer_po="PO-1", t_date="2026-07-31", order_t_date="2026-08-15",
            )

        self.assertEqual(quotation_service.calls[0]["resolved_currency"], {"curId": 2, "rate": 0.1})
        self.assertEqual(order_service.calls[0]["extra_fields"]["tDate"], "2026-08-15")
        self.assertEqual(order_service.calls[0]["resolved_currency"], {"curId": 2, "rate": 0.2})
        self.assertEqual(json.loads(result)["sales_order"]["tranCode"], "SO20")

    def test_confirmation_failure_does_not_attempt_sales_order_creation(self):
        quotation_service = FakeQuotationService()
        order_service = FakeSalesOrderService()
        client = FakeClient()
        client.save_entity = lambda *args: {"status": False, "recordId": 0, "messages": ["not approved"]}

        with (
            patch.object(mcp_sales, "_auth_svc", side_effect=[quotation_service, order_service]),
            patch.object(mcp_sales, "_biz_config", {"be_mapping": {"SHK": 4}, "quotation_to_order_rate_policy": "refresh"}),
            patch.object(mcp_sales, "M18Client", return_value=client),
            patch.object(mcp_sales, "M18CurrencyService", FakeRateService),
            patch.object(mcp_sales, "_resolve_staff", return_value=200),
            patch.object(mcp_sales, "_load_customer_terms", return_value={"payTerm": "", "tradeTerm": ""}),
            patch.object(mcp_sales, "_get_part_info", return_value={}),
            patch.object(mcp_sales, "M18ReferenceResolver") as resolver_class,
        ):
            resolver_class.return_value.resolve_customer_code.return_value = 101
            resolver_class.return_value.resolve_product_code.return_value = 201
            resolver_class.return_value.resolve_unit_code.return_value = 301
            with self.assertRaisesRegex(ValueError, "Quotation confirmation failed"):
                mcp_sales.create_quotation_and_order(
                    customer_code="C001", product_code="P001", qty=1, up=10,
                    username="user", password="password", be_code="SHK", be_id=4,
                    customer_po="PO-1", t_date="2026-07-31", order_t_date="2026-08-15",
                )

        self.assertEqual(order_service.calls, [])

    def test_mismatched_business_entity_fails_before_creating_quotation(self):
        quotation_service = FakeQuotationService()
        with (
            patch.object(mcp_sales, "_auth_svc", return_value=quotation_service),
            patch.object(mcp_sales, "_biz_config", {"be_mapping": {"SHK": 4}}),
        ):
            with self.assertRaisesRegex(ValueError, "Business entity mismatch"):
                mcp_sales.create_quotation_and_order(
                    customer_code="C001", product_code="P001", qty=1, up=10,
                    username="user", password="password", be_code="SHK", be_id=7,
                    customer_po="PO-1", t_date="2026-07-31",
                )

        self.assertEqual(quotation_service.calls, [])


if __name__ == "__main__":
    unittest.main()
