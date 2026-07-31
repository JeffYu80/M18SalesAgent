"""
Shared business-code resolver for M18 master references.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
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

    def resolve_unit_code(self, code: str, be_id: Optional[int] = None) -> int:
        """Resolve a global ``unit.id`` through the permitted search endpoint."""
        return self._expect_single_id(
            "unit",
            code,
            self._search_menu_code("unit", code=code, be_id=be_id),
        )

    def resolve_standard_quote_unit_id(
        self,
        pro_id: int,
        unit_code: Optional[str] = None,
        strategy: str = "product_price",
        be_id: Optional[int] = None,
        document_date: Optional[str] = None,
    ) -> int:
        """Resolve standard sales-line ``unitId`` to the product ``price.id``.

        M18's ``qut.unitId`` and ``sot.unitId`` reference ``price.id`` rather
        than the global ``unit.id``.  A supplied unit code selects the product
        price row for that unit; without one, the product's default sales unit
        is used.
        """
        if strategy == "pro_id":
            raise ResolverError(
                "The pro_id unit strategy is invalid: standard sales-line unitId must be price.id."
            )
        if strategy != "product_price":
            raise ResolverError(f"Unsupported standard sales unit strategy: {strategy!r}")

        return self.resolve_sales_unit(
            pro_id=pro_id,
            unit_code=unit_code,
            be_id=be_id,
            document_date=document_date,
        )["priceId"]

    def resolve_sales_unit(
        self,
        pro_id: int,
        unit_code: Optional[str] = None,
        be_id: Optional[int] = None,
        document_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve a sales unit into both bsFlow and standard-save values."""
        payload = self.client.read_entity("pro", int(pro_id))
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        product_rows = data.get("pro", []) if isinstance(data, dict) else []
        product = next((row for row in product_rows if isinstance(row, dict)), None)
        if not product:
            raise ReferenceNotFoundError(f"Unable to load product id={pro_id} for sales unit resolution.")

        supplied_unit_code = str(unit_code or "").strip()
        unit_id = self.resolve_unit_code(supplied_unit_code, be_id=be_id) if supplied_unit_code else product.get("saleUnitId")
        if unit_id is None:
            raise ReferenceNotFoundError(f"Product id={pro_id} has no default sales unit.")

        target_date = self._parse_date(document_date) if document_date else None
        matches = [
            row
            for row in data.get("price", [])
            if isinstance(row, dict)
            and int(row.get("hId", -1)) == int(pro_id)
            and int(row.get("unitId", -1)) == int(unit_id)
            and self._is_truthy(row.get("saleUnit"))
            and self._is_active_price_row(row, target_date)
        ]
        if not matches:
            requested = unit_code or f"default sales unit id={unit_id}"
            raise ReferenceNotFoundError(
                f"Product id={pro_id} has no active sales price unit for {requested}."
            )
        if len(matches) > 1:
            raise AmbiguousReferenceError(
                f"Product id={pro_id} has multiple active sales price units for unit id={unit_id}."
            )
        price_id = matches[0].get("id")
        if price_id is None:
            raise ReferenceNotFoundError(f"Matched sales price unit for product id={pro_id} has no ID.")
        resolved_unit_code = supplied_unit_code or self._resolve_unit_id_code(int(unit_id), be_id=be_id)
        return {"globalUnitId": int(unit_id), "unitCode": resolved_unit_code, "priceId": int(price_id)}

    def _resolve_unit_id_code(self, unit_id: int, be_id: Optional[int]) -> str:
        result = self.client.search_entities(
            menu_code="unit", be_id=be_id, start_row=0, end_row=5000,
        )
        match = next(
            (row for row in self._coerce_rows(result) if row.get("id") == unit_id),
            None,
        )
        code = match.get("code") if match else None
        if not code:
            raise ReferenceNotFoundError(f"Unable to resolve unit code for global unit id={unit_id}.")
        return str(code)

    def validate_standard_sales_price_id(
        self,
        pro_id: int,
        price_id: int,
        document_date: Optional[str] = None,
    ) -> int:
        """Ensure a caller-supplied standard sales ``unitId`` is a valid ``price.id``.

        This prevents a global ``unit.id`` or a price row belonging to another
        product from being written directly to a quotation or order line.
        """
        payload = self.client.read_entity("pro", int(pro_id))
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        target_date = self._parse_date(document_date) if document_date else None
        matches = [
            row
            for row in data.get("price", [])
            if isinstance(row, dict)
            and int(row.get("id", -1)) == int(price_id)
            and int(row.get("hId", -1)) == int(pro_id)
            and self._is_truthy(row.get("saleUnit"))
            and self._is_active_price_row(row, target_date)
        ]
        if len(matches) != 1:
            raise ReferenceNotFoundError(
                f"unitId={price_id} is not an active sales price.id for product id={pro_id}."
            )
        return int(price_id)

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        return value is True or value == 1 or str(value).strip().lower() in {"1", "true", "y", "yes"}

    @staticmethod
    def _parse_date(value: Any) -> date:
        text = str(value).strip()
        # M18 product ``price`` detail can return effective dates as epoch
        # milliseconds, while document dates use ISO strings.
        try:
            numeric = float(text)
            if abs(numeric) >= 10_000_000_000:
                return (datetime(1970, 1, 1) + timedelta(milliseconds=numeric)).date()
        except (TypeError, ValueError, OverflowError):
            pass
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ResolverError(f"Unsupported document date for price-unit resolution: {value!r}")

    @classmethod
    def _is_active_price_row(cls, row: Dict[str, Any], target_date: Optional[date]) -> bool:
        if cls._is_truthy(row.get("expired")):
            return False
        if target_date is None:
            return True
        eff_date = row.get("effDate")
        end_date = row.get("endDate")
        return (
            (not eff_date or cls._parse_date(eff_date) <= target_date)
            and (not end_date or cls._parse_date(end_date) >= target_date)
        )

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
