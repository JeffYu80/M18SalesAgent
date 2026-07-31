import unittest

from services.quotation_service import M18QuotationService


class FakeQuotationAPI:
    def __init__(self):
        self.last_draft_call = None
        self.last_save_call = None

    def search(self, **kwargs):
        return {"values": [{"id": 1, "code": "QU001"}], "size": 1}

    def load(self, record_id, irev=None):
        return {"mainqu": {"values": [{"id": record_id, "code": "QU001"}]}}

    def create_draft_by_codes(self, be_code, cus_code, lines, extra_fields=None):
        self.last_draft_call = {
            "be_code": be_code,
            "cus_code": cus_code,
            "lines": lines,
            "extra_fields": extra_fields,
        }
        return {"tranId": 1001, "tranCode": "QU1001", "status": True}

    def save(self, header_values, line_values, remark_values=None):
        self.last_save_call = {
            "header_values": header_values,
            "line_values": line_values,
            "remark_values": remark_values,
        }
        return {"recordId": 5001, "status": True, "messages": []}

class FakeResolver:
    def resolve_customer_code(self, code, be_id):
        return 101

    def resolve_product_code(self, code, be_id):
        return 201

    def resolve_staff_code(self, code, be_id):
        return 200

    def resolve_standard_quote_unit_id(self, pro_id, unit_code=None, strategy="product_price", be_id=None, document_date=None):
        self.unit_resolution = {
            "pro_id": pro_id,
            "unit_code": unit_code,
            "strategy": strategy,
            "be_id": be_id,
            "document_date": document_date,
        }
        return 401

    def validate_standard_sales_price_id(self, pro_id, price_id, document_date=None):
        self.validated_price_id = {"pro_id": pro_id, "price_id": price_id, "document_date": document_date}
        return price_id

    def resolve_sales_unit(self, pro_id, unit_code=None, be_id=None, document_date=None):
        return {"globalUnitId": 301, "unitCode": unit_code or "BOX", "priceId": 401}


class FakeCurrencyService:
    def resolve_customer_document_currency(self, be_id, customer_code, t_date, customer_id=None):
        return {"curId": 3, "rate": 1.25, "domCurId": 1, "rateField": "openRate"}

    def resolve_document_currency(self, be_id, t_date, customer_code=None, customer_id=None, currency_code=None):
        return {"curId": 3, "rate": 1.25, "domCurId": 1, "rateField": "openRate"}


class QuotationServiceTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeQuotationAPI()
        self.service = M18QuotationService(
            client=object(),
            quotation_api=self.api,
            resolver=FakeResolver(),
            currency_service=FakeCurrencyService(),
        )
        self.service.business_config["quotation_standard_unit_mode"] = "product_price"

    def test_search_quotations_delegates_to_api(self):
        result = self.service.search_quotations(be_id=1, quick_search="QU")

        self.assertEqual(result["size"], 1)
        self.assertEqual(result["values"][0]["code"], "QU001")

    def test_create_draft_from_codes_uses_bsflow_shape(self):
        result = self.service.create_draft_from_codes(
            be_code="BE01",
            be_id=7,
            cus_code="C001",
            lines=[
                {
                    "proCode": "P001",
                    "unitCode": "PCS",
                    "qty": 2,
                    "up": 100,
                    "disc": 5,
                }
            ],
            extra_fields={"staffCode": "000001"},
        )

        self.assertTrue(result["status"])
        self.assertEqual(self.api.last_draft_call["cus_code"], "C001")
        self.assertEqual(self.api.last_draft_call["lines"][0]["proCode"], "P001")
        self.assertEqual(self.api.last_draft_call["lines"][0]["unitCode"], "PCS")
        self.assertEqual(self.api.last_draft_call["extra_fields"]["staffId"], 200)
        self.assertEqual(self.api.last_draft_call["extra_fields"]["curId"], 3)
        self.assertEqual(self.api.last_draft_call["extra_fields"]["rate"], 1.25)

    def test_create_draft_uses_product_default_unit_when_code_is_omitted(self):
        self.service.create_draft_from_codes(
            be_code="BE01", be_id=7, cus_code="C001",
            lines=[{"proCode": "P001", "qty": 1, "up": 1}],
            extra_fields={"staffCode": "000001"},
        )
        self.assertEqual(self.api.last_draft_call["lines"][0]["unitCode"], "BOX")

    def test_create_draft_ignores_caller_currency_id_and_rate(self):
        self.service.create_draft_from_codes(
            be_code="BE01", be_id=7, cus_code="C001",
            lines=[{"proCode": "P001", "unitCode": "PCS", "qty": 1, "up": 1}],
            extra_fields={"staffCode": "000001", "curId": 99, "rate": 999},
        )
        self.assertEqual(self.api.last_draft_call["extra_fields"]["curId"], 3)
        self.assertEqual(self.api.last_draft_call["extra_fields"]["rate"], 1.25)

    def test_save_quotation_resolves_codes_to_ids(self):
        result = self.service.save_quotation(
            be_id=1,
            header={
                "cusCode": "C001",
                "curId": 1,
                "flowTypeId": 10,
                "staffCode": "000001",
                "tDate": "2026-05-07",
            },
            lines=[
                {
                    "proCode": "P001",
                    "unitCode": "PCS",
                    "qty": 3,
                    "up": 88,
                }
            ],
        )

        self.assertTrue(result["status"])
        header_row = self.api.last_save_call["header_values"][0]
        line_row = self.api.last_save_call["line_values"][0]
        self.assertEqual(header_row["cusId"], 101)
        self.assertEqual(header_row["curId"], 3)
        self.assertEqual(header_row["rate"], 1.25)
        self.assertEqual(line_row["proId"], 201)
        self.assertEqual(line_row["unitId"], 401)
        self.assertEqual(self.service.resolver.unit_resolution["unit_code"], "PCS")
        self.assertEqual(self.service.resolver.unit_resolution["document_date"], "2026-05-07")

    def test_save_quotation_uses_product_default_sales_unit_when_code_is_omitted(self):
        self.service.save_quotation(
            be_id=1,
            header={"cusCode": "C001", "curId": 1, "flowTypeId": 10, "staffCode": "000001", "tDate": "2026-05-07"},
            lines=[{"proCode": "P001", "qty": 1, "up": 88}],
        )
        self.assertIsNone(self.service.resolver.unit_resolution["unit_code"])
        self.assertEqual(self.api.last_save_call["line_values"][0]["unitId"], 401)

    def test_save_quotation_validates_caller_supplied_price_id(self):
        self.service.save_quotation(
            be_id=1,
            header={"cusCode": "C001", "curId": 1, "flowTypeId": 10, "staffCode": "000001", "tDate": "2026-05-07"},
            lines=[{"proCode": "P001", "unitId": 401, "qty": 1, "up": 88}],
        )
        self.assertEqual(self.service.resolver.validated_price_id["price_id"], 401)

if __name__ == "__main__":
    unittest.main()
