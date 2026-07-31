import unittest

from services.product_service import M18ProductService


class FakeProductAPI:
    def search(self, **kwargs):
        return {
            "values": [
                {
                    "id": 497,
                    "code": "PGD798MB",
                    "desc__lang": "Lockly Vision",
                    "lastModifyDate": "2025-11-20 11:55:11",
                }
            ]
        }

    def load(self, product_id, irev=None):
        return {
            "data": {
                "pro": [
                    {
                        "id": product_id,
                        "code": "PGD798MB",
                        "desc": "Lockly Vision",
                        "unitId": 1,
                        "stkUnitId": 1,
                        "saleUnitId": 1,
                        "purUnitId": 1,
                        "pickUnitId": 1,
                    }
                ],
                "produalunit": [
                    {"unitId": 1, "default": True},
                ],
                "price": [
                    {"id": 39151, "hId": product_id, "unitId": 1, "saleUnit": True, "expired": False},
                ],
                "ediconnsku": [
                    {"ediconnConfigId": 5, "ediPlatformSku": "PGD798MB"},
                ],
                "ecomprorefer": [
                    {"ecomshopId": 3, "refer": "PGD_798_MB", "msmtReferSku": "B083BBHRPJ"},
                ],
            }
        }


class FakeResolver:
    def resolve_product_code(self, code, be_id):
        return 497


class FakeClient:
    def get_ebi_report(self, report_id, **kwargs):
        return {
            "rows": [
                {
                    "CUS_A_code": "320",
                    "CUS_A_id": 24,
                    "CUS_A_desc__lang": "The Home Depot",
                    "PRO_A_code": "PGD798MB",
                    "PRO_A_id": 497,
                    "PRO_A_desc__lang": "Lockly Vision",
                    "F_A_refCode": "ABC798",
                },
                {
                    "CUS_A_code": "999",
                    "PRO_A_code": "OTHER",
                    "F_A_refCode": "OTHER",
                },
            ]
        }


class FakeCustomerService:
    def get_customer_by_code(self, code, be_id):
        return {
            "data": {
                "cus": [
                    {"id": 24, "code": code, "desc": "The Home Depot"},
                ]
            }
        }


class ProductServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = M18ProductService(
            client=FakeClient(),
            product_api=FakeProductAPI(),
            resolver=FakeResolver(),
            customer_service=FakeCustomerService(),
        )

    def test_search_products_adds_summaries(self):
        result = self.service.search_products(be_id=7, quick_search="PGD798MB")
        self.assertIn("summaries", result)
        self.assertEqual(result["summaries"][0]["code"], "PGD798MB")

    def test_get_product_units_returns_default_unit_info(self):
        result = self.service.get_product_units("PGD798MB", be_id=7)
        self.assertEqual(result["productId"], 497)
        self.assertEqual(result["units"]["unitId"], 1)
        self.assertEqual(result["units"]["defaultSalesPriceId"], 39151)

    def test_query_customer_item_codes_normalizes_ebi_rows(self):
        result = self.service.query_customer_item_codes(
            customer_code="320",
            product_code="PGD798MB",
            be_id=7,
        )
        self.assertEqual(result["report"]["formatId"], 102)
        self.assertEqual(result["report"]["code"], "Jeff-CustomerPartAPI")
        self.assertEqual(result["customer"]["code"], "320")
        self.assertEqual(result["product"]["code"], "PGD798MB")
        self.assertEqual(result["customerPartRows"][0]["F_A_refCode"], "ABC798")
        self.assertEqual(result["customerPartMatches"][0]["customerCode"], "320")
        self.assertEqual(result["customerPartMatches"][0]["productCode"], "PGD798MB")
        self.assertEqual(result["customerPartMatches"][0]["customerPartCode"], "ABC798")
        self.assertEqual(result["customerPartMatches"][0]["customerName"], "The Home Depot")
        self.assertTrue(result["externalCodes"])
        sources = {item["source"] for item in result["externalCodes"]}
        self.assertIn("ediconnsku", sources)
        self.assertIn("ecomprorefer.refer", sources)


if __name__ == "__main__":
    unittest.main()
