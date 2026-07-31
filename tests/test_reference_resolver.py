import unittest

from services.reference_resolver import (
    AmbiguousReferenceError,
    M18ReferenceResolver,
    ReferenceNotFoundError,
)


class FakeCustomerAPI:
    def __init__(self, result):
        self.result = result

    def search(self, **kwargs):
        return self.result


class FakeClient:
    def __init__(self, product_result=None, unit_result=None):
        self.product_result = product_result or {"values": []}
        self.unit_result = unit_result or {"values": []}

    def search_entities(self, **kwargs):
        if kwargs.get("menu_code") == "pro":
            return self.product_result
        if kwargs.get("menu_code") == "unit":
            return self.unit_result
        return {"values": []}

    def search_by_code(self, table_name, code):
        if table_name == "unit":
            return self.unit_result
        return {"values": []}

    def read_entity(self, menu_code, record_id, irev=None):
        return {"data": {}}


class ReferenceResolverTests(unittest.TestCase):
    def test_resolve_customer_code_returns_single_id(self):
        resolver = M18ReferenceResolver(client=FakeClient())
        resolver.customer_api = FakeCustomerAPI(
            {"values": [{"id": 101, "code": "C001", "desc__lang": "Customer 1"}]}
        )

        result = resolver.resolve_customer_code("C001", be_id=1)

        self.assertEqual(result, 101)

    def test_resolve_customer_code_raises_not_found(self):
        resolver = M18ReferenceResolver(client=FakeClient())
        resolver.customer_api = FakeCustomerAPI({"values": []})

        with self.assertRaises(ReferenceNotFoundError):
            resolver.resolve_customer_code("C404", be_id=1)

    def test_resolve_customer_code_raises_ambiguous(self):
        resolver = M18ReferenceResolver(client=FakeClient())
        resolver.customer_api = FakeCustomerAPI(
            {
                "values": [
                    {"id": 101, "code": "C001", "desc__lang": "Customer A"},
                    {"id": 102, "code": "C001", "desc__lang": "Customer B"},
                ]
            }
        )

        with self.assertRaises(AmbiguousReferenceError):
            resolver.resolve_customer_code("C001", be_id=1)

    def test_resolve_product_code_returns_single_id(self):
        resolver = M18ReferenceResolver(
            client=FakeClient(product_result={"values": [{"id": 201, "code": "P001"}]})
        )

        result = resolver.resolve_product_code("P001", be_id=1)

        self.assertEqual(result, 201)

    def test_resolve_unit_code_returns_single_id(self):
        resolver = M18ReferenceResolver(
            client=FakeClient(unit_result={"values": [{"id": 301, "code": "PCS"}]})
        )

        result = resolver.resolve_unit_code("PCS")

        self.assertEqual(result, 301)

    def test_standard_sales_unit_resolves_product_price_id(self):
        client = FakeClient(unit_result={"values": [{"id": 301, "code": "PCS"}]})
        client.read_entity = lambda menu_code, record_id, irev=None: {
            "data": {
                "pro": [{"id": 201, "saleUnitId": 301}],
                "price": [{"id": 401, "hId": 201, "unitId": 301, "saleUnit": True, "expired": False}],
            }
        }
        resolver = M18ReferenceResolver(client=client)

        self.assertEqual(
            resolver.resolve_standard_quote_unit_id(
                pro_id=201, unit_code="PCS", strategy="product_price", be_id=1, document_date="2026-07-31"
            ),
            401,
        )

    def test_standard_sales_unit_uses_product_default_when_code_omitted(self):
        client = FakeClient(unit_result={"values": [{"id": 301, "code": "BOX"}]})
        client.read_entity = lambda menu_code, record_id, irev=None: {
            "data": {
                "pro": [{"id": 201, "saleUnitId": 301}],
                "price": [{"id": 401, "hId": 201, "unitId": 301, "saleUnit": True, "expired": False}],
            }
        }
        resolver = M18ReferenceResolver(client=client)

        self.assertEqual(resolver.resolve_standard_quote_unit_id(201), 401)
        self.assertEqual(resolver.resolve_sales_unit(201)["unitCode"], "BOX")

    def test_standard_sales_unit_validates_explicit_price_id(self):
        client = FakeClient()
        client.read_entity = lambda menu_code, record_id, irev=None: {
            "data": {"price": [{"id": 401, "hId": 201, "unitId": 301, "saleUnit": True, "expired": False}]}
        }
        resolver = M18ReferenceResolver(client=client)
        self.assertEqual(resolver.validate_standard_sales_price_id(201, 401), 401)
        with self.assertRaises(ReferenceNotFoundError):
            resolver.validate_standard_sales_price_id(201, 301)

    def test_standard_sales_unit_accepts_m18_epoch_millisecond_effective_date(self):
        client = FakeClient(unit_result={"values": [{"id": 301, "code": "BOX"}]})
        client.read_entity = lambda menu_code, record_id, irev=None: {
            "data": {
                "pro": [{"id": 201, "saleUnitId": 301}],
                "price": [{"id": 401, "hId": 201, "unitId": 301, "saleUnit": True, "expired": False, "effDate": -2209017600000}],
            }
        }
        resolver = M18ReferenceResolver(client=client)

        self.assertEqual(resolver.resolve_standard_quote_unit_id(201, document_date="2026-07-31"), 401)


if __name__ == "__main__":
    unittest.main()
