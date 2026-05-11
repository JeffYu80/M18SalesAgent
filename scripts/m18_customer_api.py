"""
Customer-focused API wrapper for M18 customer master (`cus`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402


MENU_CUSTOMER = "cus"

# Common candidate child tables seen in customer payloads across deployments.
CUSTOMER_CONTACT_TABLE_CANDIDATES = (
    "contact",
    "contactt",
    "cuscontact",
    "cuscont",
    "cust",
    "cont",
    "ocf",
)


class M18CustomerAPI:
    """Customer-focused wrapper around the shared M18 client."""

    def __init__(self, client: Optional[M18Client] = None):
        self.client = client or M18Client()

    def search(
        self,
        be_id: int,
        start_row: int = 0,
        end_row: int = 100,
        quick_search: Optional[str] = None,
        format_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search customer master records."""
        return self.client.search_entities(
            menu_code=MENU_CUSTOMER,
            be_id=be_id,
            start_row=start_row,
            end_row=end_row,
            quick_search=quick_search,
            format_id=format_id,
        )

    def load(self, customer_id: int, irev: Optional[int] = None) -> Dict[str, Any]:
        """Load one customer master record."""
        return self.client.read_entity(MENU_CUSTOMER, customer_id, irev=irev)

    def search_by_code(self, code: str, be_id: Optional[int] = None) -> Dict[str, Any]:
        """Search customers by code using the generic customer search endpoint."""
        result = self.search(
            be_id=be_id or 0,
            start_row=0,
            end_row=20,
            quick_search=code,
        )
        if be_id is None:
            result["_resolver_without_beid"] = True
        return result

    def extract_contact_rows(self, customer_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract contact rows from likely child tables in a customer payload."""
        rows: List[Dict[str, Any]] = []
        container = customer_payload.get("data", customer_payload)

        for table_name in CUSTOMER_CONTACT_TABLE_CANDIDATES:
            table_data = container.get(table_name) if isinstance(container, dict) else None
            if isinstance(table_data, list):
                values = table_data
            elif isinstance(table_data, dict):
                values = table_data.get("values")
            else:
                continue
            if isinstance(values, list):
                rows.extend(row for row in values if isinstance(row, dict))

        return rows


def normalize_customer_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a consistent customer summary shape from a search row."""
    return {
        "id": row.get("id"),
        "code": row.get("code"),
        "name": row.get("desc__lang") or row.get("desc"),
        "lastModifyDate": row.get("lastModifyDate"),
        "raw": row,
    }


def filter_contact_rows(rows: List[Dict[str, Any]], **filters: Any) -> List[Dict[str, Any]]:
    """Apply simple contains-based filters to contact rows."""
    active_filters = {
        key: str(value).strip().lower()
        for key, value in filters.items()
        if value is not None and str(value).strip()
    }

    if not active_filters:
        return rows

    def row_matches(row: Dict[str, Any]) -> bool:
        haystack = {key: str(value).lower() for key, value in row.items() if value is not None}
        for filter_value in active_filters.values():
            if not any(filter_value in value for value in haystack.values()):
                return False
        return True

    return [row for row in rows if row_matches(row)]
