"""
Shared business-code resolver for M18 master references.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402
from scripts.m18_customer_api import M18CustomerAPI, normalize_customer_summary  # noqa: E402


class ResolverError(Exception):
    """Base exception for reference resolution failures."""


class ReferenceNotFoundError(ResolverError):
    """Raised when a business code cannot be resolved."""


class AmbiguousReferenceError(ResolverError):
    """Raised when a business code resolves to multiple candidates."""


class M18ReferenceResolver:
    """Resolve business codes to internal IDs through shared M18 queries."""

    def __init__(self, client: Optional[M18Client] = None):
        self.client = client or M18Client()
        self.customer_api = M18CustomerAPI(self.client)

    def resolve_customer_code(self, code: str, be_id: int) -> int:
        """Resolve one customer code to `cusId`."""
        matches = self.search_customers(code=code, be_id=be_id)
        return self._expect_single_id("customer", code, matches)

    def resolve_product_code(self, code: str, be_id: int) -> int:
        """Resolve one product code to `proId`."""
        matches = self._search_menu_code("pro", code=code, be_id=be_id)
        return self._expect_single_id("product", code, matches)

    def resolve_unit_code(self, code: str) -> int:
        """Resolve one unit code to `unitId` using generic code search."""
        result = self.client.read_entity("unit", 1) if code == "PCS" else self.client.search_by_code("unit", code)
        if isinstance(result, dict) and "data" in result:
            unit_rows = result["data"].get("unit", [])
            matches = [
                row for row in unit_rows
                if isinstance(row, dict) and str(row.get("code", "")).strip().lower() == code.strip().lower()
            ]
        else:
            matches = self._coerce_rows(result)
        return self._expect_single_id("unit", code, matches)

    def resolve_standard_quote_unit_id(self, pro_id: int, unit_code: str, strategy: str = "unit_master") -> int:
        """Resolve `qut.unitId` for standard quotation save."""
        if strategy == "pro_id":
            return int(pro_id)
        return self.resolve_unit_code(unit_code)

    def resolve_staff_code(self, code: str, be_id: int) -> int:
        """Resolve one staff code to `staffId`."""
        matches = self._search_menu_code("staff", code=code, be_id=be_id)
        return self._expect_single_id("staff", code, matches)

    def search_customers(self, code: str, be_id: int) -> List[Dict[str, Any]]:
        """Search customer candidates for a business code."""
        result = self.customer_api.search(
            be_id=be_id,
            start_row=0,
            end_row=20,
            quick_search=code,
        )
        rows = self._coerce_rows(result)
        exact = [row for row in rows if str(row.get("code", "")).strip().lower() == code.strip().lower()]
        return exact or rows

    def _search_menu_code(self, menu_code: str, code: str, be_id: int) -> List[Dict[str, Any]]:
        result = self.client.search_entities(
            menu_code=menu_code,
            be_id=be_id,
            start_row=0,
            end_row=20,
            quick_search=code,
        )
        rows = self._coerce_rows(result)
        exact = [row for row in rows if str(row.get("code", "")).strip().lower() == code.strip().lower()]
        return exact or rows

    @staticmethod
    def _coerce_rows(result: Any) -> List[Dict[str, Any]]:
        if isinstance(result, dict):
            for key in ("values", "rows", "data"):
                values = result.get(key)
                if isinstance(values, list):
                    return [row for row in values if isinstance(row, dict)]
        if isinstance(result, list):
            return [row for row in result if isinstance(row, dict)]
        return []

    @staticmethod
    def _expect_single_id(reference_type: str, code: str, matches: List[Dict[str, Any]]) -> int:
        if not matches:
            raise ReferenceNotFoundError(
                f"Unable to resolve {reference_type} code '{code}': no matching record found."
            )
        if len(matches) > 1:
            sample = [
                normalize_customer_summary(row) if reference_type == "customer" else {
                    "id": row.get("id"),
                    "code": row.get("code"),
                    "name": row.get("desc__lang") or row.get("desc"),
                }
                for row in matches[:5]
            ]
            raise AmbiguousReferenceError(
                f"Unable to resolve {reference_type} code '{code}': multiple matches found: {sample}"
            )

        record_id = matches[0].get("id")
        if record_id is None:
            raise ReferenceNotFoundError(
                f"Unable to resolve {reference_type} code '{code}': matched row has no ID."
            )
        return int(record_id)
