import unittest

from chat_agent import format_result, parse_user_input
from m18_ops_agent import M18OpsAgent


class FakeCustomerService:
    def search_customers(self, **kwargs):
        return {"kind": "customer.search", "params": kwargs}

    def load_customer(self, customer_id, irev=None):
        return {"kind": "customer.load", "customerId": customer_id, "iRev": irev}

    def get_customer_contacts(self, **kwargs):
        return {"kind": "customer.contacts", "params": kwargs}


class FakeProductService:
    def search_products(self, **kwargs):
        return {"kind": "product.search", "params": kwargs}

    def load_product(self, product_id, irev=None):
        return {"kind": "product.load", "productId": product_id, "iRev": irev}

    def get_product_units(self, product_code, be_id):
        return {"kind": "product.units", "productCode": product_code, "beId": be_id}

    def query_customer_item_codes(self, customer_code, product_code, be_id):
        return {
            "kind": "product.customer_item_codes",
            "customerCode": customer_code,
            "productCode": product_code,
            "beId": be_id,
        }


class FakeQuotationService:
    def search_quotations(self, **kwargs):
        return {"kind": "quotation.search", "params": kwargs}

    def load_quotation(self, record_id, irev=None):
        return {"kind": "quotation.load", "recordId": record_id, "iRev": irev}

    def create_draft_from_codes(self, be_code, cus_code, lines, extra_fields=None, be_id=None):
        return {
            "kind": "quotation.create_draft",
            "beCode": be_code,
            "customerCode": cus_code,
            "lines": lines,
            "extraFields": extra_fields,
            "beId": be_id,
        }

    def save_quotation(self, be_id, header, lines, remark_values=None):
        return {
            "kind": "quotation.save",
            "beId": be_id,
            "header": header,
            "lines": lines,
            "remarkValues": remark_values,
        }


class FakeSalesOrderService:
    def search_sales_orders(self, **kwargs):
        return {"kind": "sales_order.search", "params": kwargs}

    def load_sales_order(self, record_id, irev=None):
        return {"kind": "sales_order.load", "recordId": record_id, "iRev": irev}

    def create_draft_from_codes(self, be_code, cus_code, lines, extra_fields=None, be_id=None):
        return {
            "kind": "sales_order.create_draft",
            "beCode": be_code,
            "customerCode": cus_code,
            "lines": lines,
            "extraFields": extra_fields,
            "beId": be_id,
        }

    def save_sales_order(self, be_id, header, lines, remark_values=None):
        return {
            "kind": "sales_order.save",
            "beId": be_id,
            "header": header,
            "lines": lines,
            "remarkValues": remark_values,
        }


class M18OpsAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = M18OpsAgent(
            customer_service=FakeCustomerService(),
            product_service=FakeProductService(),
            quotation_service=FakeQuotationService(),
            sales_order_service=FakeSalesOrderService(),
        )

    def test_customer_contacts_requires_be_id(self):
        result = self.agent.handle("customer.contacts", {"customerCode": "320"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "ValueError")
        self.assertIn("beId", result["error"]["message"])

    def test_customer_contacts_routes_with_explicit_be_id(self):
        result = self.agent.handle("customer.contacts", {"beId": 7, "customerCode": "320"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"]["customer_code"], "320")
        self.assertEqual(result["data"]["params"]["be_id"], 7)

    def test_customer_item_lookup_routes_to_product_service(self):
        result = self.agent.handle(
            "product.customer_item_codes",
            {"beId": 7, "customerCode": "320", "productCode": "PGD798MB"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["customerCode"], "320")
        self.assertEqual(result["data"]["productCode"], "PGD798MB")
        self.assertEqual(result["data"]["beId"], 7)

    def test_quotation_create_draft_requires_be_code(self):
        result = self.agent.handle(
            "quotation.create_draft",
            {
                "beId": 7,
                "customerCode": "320",
                "staffCode": "000001",
                "lines": [{"proCode": "PGD798MB", "unitCode": "PCS", "qty": 1, "up": 130}],
            },
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "ValueError")
        self.assertIn("beCode", result["error"]["message"])

    def test_quotation_create_draft_passes_explicit_be_values(self):
        result = self.agent.handle(
            "quotation.create_draft",
            {
                "beId": 7,
                "beCode": "PUS",
                "customerCode": "320",
                "staffCode": "000001",
                "lines": [{"proCode": "PGD798MB", "unitCode": "PCS", "qty": 1, "up": 130}],
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["beCode"], "PUS")
        self.assertEqual(result["data"]["beId"], 7)
        self.assertEqual(result["data"]["extraFields"]["staffCode"], "000001")

    def test_unsupported_action_returns_error(self):
        result = self.agent.handle("unknown.action", {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "UnsupportedAction")

    def test_missing_required_parameter_returns_error(self):
        result = self.agent.handle("product.customer_item_codes", {"beId": 7, "customerCode": "320"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "ValueError")


class ChatAgentParserTests(unittest.TestCase):
    def test_parse_customer_contacts_command(self):
        parsed = parse_user_input("/customer-contacts 7 320")
        self.assertEqual(parsed["action"], "customer.contacts")
        self.assertEqual(parsed["params"]["beId"], 7)
        self.assertEqual(parsed["params"]["customerCode"], "320")

    def test_parse_customer_item_command(self):
        parsed = parse_user_input("/customer-item 7 320 PGD798MB")
        self.assertEqual(parsed["action"], "product.customer_item_codes")
        self.assertEqual(parsed["params"]["beId"], 7)
        self.assertEqual(parsed["params"]["productCode"], "PGD798MB")

    def test_parse_quotation_draft_command(self):
        parsed = parse_user_input("/quotation-draft 7 PUS 320 PGD798MB 1 130 000001")
        self.assertEqual(parsed["action"], "quotation.create_draft")
        self.assertEqual(parsed["params"]["beId"], 7)
        self.assertEqual(parsed["params"]["beCode"], "PUS")
        self.assertEqual(parsed["params"]["lines"][0]["proCode"], "PGD798MB")
        self.assertEqual(parsed["params"]["staffCode"], "000001")

    def test_parse_run_command(self):
        parsed = parse_user_input('/run customer.search {"beId":7,"quickSearchStr":"320"}')
        self.assertEqual(parsed["action"], "customer.search")
        self.assertEqual(parsed["params"]["beId"], 7)
        self.assertEqual(parsed["params"]["quickSearchStr"], "320")

    def test_parse_natural_language_requires_be_id(self):
        with self.assertRaises(ValueError):
            parse_user_input("客户 320 的联系人")

    def test_parse_chinese_customer_contacts(self):
        parsed = parse_user_input("beId=7 客户 320 的联系人")
        self.assertEqual(parsed["action"], "customer.contacts")
        self.assertEqual(parsed["params"]["beId"], 7)
        self.assertEqual(parsed["params"]["customerCode"], "320")

    def test_parse_chinese_customer_item_phrase(self):
        parsed = parse_user_input("beId=7 客户 320 的 PGD798MB 客户料号")
        self.assertEqual(parsed["action"], "product.customer_item_codes")
        self.assertEqual(parsed["params"]["beId"], 7)
        self.assertEqual(parsed["params"]["customerCode"], "320")
        self.assertEqual(parsed["params"]["productCode"], "PGD798MB")


class ChatAgentFormattingTests(unittest.TestCase):
    def test_format_customer_item_result(self):
        text = format_result(
            {
                "action": "product.customer_item_codes",
                "ok": True,
                "data": {
                    "customer": {"code": "320", "name": "The Home Depot"},
                    "product": {"code": "PGD798MB", "name": "Lockly Vision"},
                    "customerPartMatches": [
                        {
                            "customerPartCode": "ABC798",
                            "customerCode": "320",
                            "productCode": "PGD798MB",
                        }
                    ],
                },
            }
        )
        self.assertIn("ABC798", text)
        self.assertIn("The Home Depot", text)

    def test_format_error_result(self):
        text = format_result(
            {
                "action": "product.customer_item_codes",
                "ok": False,
                "error": {"type": "ValueError", "message": "Missing required parameter: beId"},
            }
        )
        self.assertIn("失败", text)
        self.assertIn("beId", text)


if __name__ == "__main__":
    unittest.main()
