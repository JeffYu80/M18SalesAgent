import unittest

from services.customer_service import M18CustomerService
from scripts.m18_customer_api import extract_default_currency_id


class FakeCustomerAPI:
    def search(self, **kwargs):
        return {
            "values": [
                {
                    "id": 101,
                    "code": "C001",
                    "desc__lang": "ACME",
                    "lastModifyDate": "2026-05-07 10:00:00",
                }
            ]
        }

    def load(self, customer_id, irev=None):
        return {
            "cus": {"values": [{"id": customer_id, "code": "C001", "desc": "ACME"}]},
            "cusacc": {"values": [{"curId": 3}]},
            "cuscontact": {
                "values": [
                    {
                        "name": "Alice",
                        "email": "alice@example.com",
                        "phone": "12345678",
                        "dept": "Sales",
                    },
                    {
                        "name": "Bob",
                        "email": "bob@example.com",
                        "phone": "87654321",
                        "dept": "Finance",
                    },
                ]
            },
        }

    def extract_contact_rows(self, payload):
        return payload["cuscontact"]["values"]


class FakeResolver:
    def resolve_customer_code(self, code, be_id):
        return 101


class CustomerServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = M18CustomerService(
            client=object(),
            customer_api=FakeCustomerAPI(),
            resolver=FakeResolver(),
        )

    def test_search_customers_adds_summaries(self):
        result = self.service.search_customers(be_id=1, quick_search="ACME")

        self.assertIn("summaries", result)
        self.assertEqual(result["summaries"][0]["code"], "C001")
        self.assertEqual(result["summaries"][0]["name"], "ACME")

    def test_get_customer_by_code_loads_customer(self):
        result = self.service.get_customer_by_code("C001", be_id=1)

        self.assertEqual(result["cus"]["values"][0]["id"], 101)

    def test_get_customer_default_currency_reads_cusacc(self):
        result = self.service.get_customer_default_currency(customer_code="C001", be_id=1)

        self.assertEqual(result, {"customerId": 101, "curId": 3})

    def test_customer_currency_rejects_missing_cusacc_value(self):
        with self.assertRaisesRegex(ValueError, "no default currency"):
            extract_default_currency_id({"cusacc": {"values": [{}]}})

    def test_customer_currency_rejects_ambiguous_cusacc_values(self):
        with self.assertRaisesRegex(ValueError, "multiple account currencies"):
            extract_default_currency_id({"cusacc": {"values": [{"curId": 1}, {"curId": 3}]}})

    def test_get_customer_contacts_filters_rows(self):
        result = self.service.get_customer_contacts(
            customer_code="C001",
            be_id=1,
            email="alice@example.com",
        )

        self.assertEqual(result["customerId"], 101)
        self.assertEqual(result["contactCount"], 1)
        self.assertEqual(result["contacts"][0]["name"], "Alice")

    def test_get_customer_contacts_requires_identifier(self):
        with self.assertRaises(ValueError):
            self.service.get_customer_contacts()


if __name__ == "__main__":
    unittest.main()
