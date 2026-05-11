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
        return {"values": []}

    def search_by_code(self, table_name, code):
        if table_name == "unit":
            return self.unit_result
        return {"values": []}

    def read_entity(self, menu_code, record_id, irev=None):
        if menu_code == "unit" and record_id == 1:
            return {"data": {"unit": self.unit_result.get("values", [])}}
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


if __name__ == "__main__":
    unittest.main()
