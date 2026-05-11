"""
Product domain service for product lookup and customer item code style queries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402
from scripts.m18_product_api import (  # noqa: E402
    M18ProductAPI,
    extract_default_units,
    extract_external_product_codes,
    normalize_product_summary,
)
from services.business_config import load_business_config  # noqa: E402
from services.customer_service import M18CustomerService  # noqa: E402
from services.reference_resolver import M18ReferenceResolver  # noqa: E402


CUSTOMER_PART_REPORT_CODE = "Jeff-CustomerPartAPI"
_cfg = load_business_config()
CUSTOMER_PART_REPORT_ID = _cfg.get("customer_part_report_id", 102)


def _first_non_empty(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _row_matches_text(row: Dict[str, Any], text: str) -> bool:
    needle = str(text).strip().lower()
    if not needle:
        return True
    return any(needle in str(value).lower() for value in row.values() if value is not None)


def _filter_ebi_rows(rows: list[Dict[str, Any]], customer_code: str, product_code: str) -> list[Dict[str, Any]]:
    filtered = rows
    if customer_code:
        customer_exact = [row for row in filtered if _row_matches_text(row, customer_code)]
        filtered = customer_exact
    if product_code:
        product_exact = [row for row in filtered if _row_matches_text(row, product_code)]
        filtered = product_exact
    return filtered


def _normalize_customer_part_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "customerCode": _first_non_empty(row, "CUS_A_code", "customerCode"),
        "customerId": _first_non_empty(row, "CUS_A_id", "customerId"),
        "customerName": _first_non_empty(row, "CUS_A_desc__lang", "customerName", "customerDesc"),
        "productCode": _first_non_empty(row, "PRO_A_code", "productCode"),
        "productId": _first_non_empty(row, "PRO_A_id", "productId"),
        "productName": _first_non_empty(row, "PRO_A_desc__lang", "productName", "productDesc"),
        "customerPartCode": _first_non_empty(row, "F_A_refCode", "customerPartCode", "customerPartNo"),
        "raw": row,
    }


class M18ProductService:
    """Business service for product master and customer item code queries."""

    def __init__(
        self,
        client: Optional[M18Client] = None,
        product_api: Optional[M18ProductAPI] = None,
        resolver: Optional[M18ReferenceResolver] = None,
        customer_service: Optional[M18CustomerService] = None,
    ):
        self.client = client or M18Client()
        self.product_api = product_api or M18ProductAPI(self.client)
        self.resolver = resolver or M18ReferenceResolver(self.client)
        self.customer_service = customer_service or M18CustomerService(self.client)

    def search_products(
        self,
        be_id: int,
        quick_search: Optional[str] = None,
        start_row: int = 0,
        end_row: int = 100,
    ) -> Dict[str, Any]:
        result = self.product_api.search(
            be_id=be_id,
            quick_search=quick_search,
            start_row=start_row,
            end_row=end_row,
        )
        rows = result.get("values", result.get("rows", result.get("data", [])))
        result["summaries"] = [
            normalize_product_summary(row)
            for row in rows
            if isinstance(row, dict)
        ]
        return result

    def load_product(self, product_id: int, irev: Optional[int] = None) -> Dict[str, Any]:
        return self.product_api.load(product_id, irev=irev)

    def get_product_by_code(self, code: str, be_id: int) -> Dict[str, Any]:
        product_id = self.resolver.resolve_product_code(code, be_id)
        return self.load_product(product_id)

    def get_product_units(self, product_code: str, be_id: int) -> Dict[str, Any]:
        payload = self.get_product_by_code(product_code, be_id)
        return {
            "productCode": product_code,
            "productId": self.resolver.resolve_product_code(product_code, be_id),
            "units": extract_default_units(payload),
        }

    def query_customer_item_codes(
        self,
        customer_code: str,
        product_code: str,
        be_id: int,
    ) -> Dict[str, Any]:
        customer = self.customer_service.get_customer_by_code(customer_code, be_id)
        product = self.get_product_by_code(product_code, be_id)
        customer_row = customer.get("data", {}).get("cus", [{}])[0]
        product_row = product.get("data", {}).get("pro", [{}])[0]
        report = self.client.get_ebi_report(CUSTOMER_PART_REPORT_ID, be_id=be_id)
        report_rows = report.get("rows", report.get("values", []))
        report_rows = [row for row in report_rows if isinstance(row, dict)]
        matched_rows = _filter_ebi_rows(report_rows, customer_code=customer_code, product_code=product_code)
        normalized_matches = [_normalize_customer_part_row(row) for row in matched_rows]

        return {
            "report": {
                "formatId": CUSTOMER_PART_REPORT_ID,
                "code": CUSTOMER_PART_REPORT_CODE,
                "rowCount": len(matched_rows),
            },
            "customer": {
                "id": customer_row.get("id"),
                "code": customer_row.get("code"),
                "name": (
                    customer_row.get("desc")
                    or customer_row.get("desc__lang")
                    or (normalized_matches[0]["customerName"] if normalized_matches else None)
                ),
            },
            "product": {
                "id": product_row.get("id"),
                "code": product_row.get("code"),
                "name": (
                    product_row.get("desc")
                    or product_row.get("desc__lang")
                    or (normalized_matches[0]["productName"] if normalized_matches else None)
                ),
            },
            "units": extract_default_units(product),
            "customerPartMatches": normalized_matches,
            "customerPartRows": matched_rows,
            "externalCodes": extract_external_product_codes(product),
            "note": (
                "Primary results come from EBI report 102 (Jeff-CustomerPartAPI). "
                "External product codes are provided as supplemental reference data."
            ),
        }
