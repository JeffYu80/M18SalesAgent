"""
Customer domain service for customer and customer-contact lookup flows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402
from scripts.m18_customer_api import (  # noqa: E402
    M18CustomerAPI,
    extract_default_currency_id,
    filter_contact_rows,
    normalize_customer_summary,
)
from services.reference_resolver import M18ReferenceResolver  # noqa: E402


class M18CustomerService:
    """Business service for customer master and customer-contact queries."""

    def __init__(
        self,
        client: Optional[M18Client] = None,
        customer_api: Optional[M18CustomerAPI] = None,
        resolver: Optional[M18ReferenceResolver] = None,
    ):
        self.client = client or M18Client()
        self.customer_api = customer_api or M18CustomerAPI(self.client)
        self.resolver = resolver or M18ReferenceResolver(self.client)

    def search_customers(
        self,
        be_id: int,
        quick_search: Optional[str] = None,
        start_row: int = 0,
        end_row: int = 100,
    ) -> Dict[str, Any]:
        """Search customers and normalize row summaries."""
        result = self.customer_api.search(
            be_id=be_id,
            quick_search=quick_search,
            start_row=start_row,
            end_row=end_row,
        )
        rows = result.get("values", result.get("rows", result.get("data", [])))
        result["summaries"] = [
            normalize_customer_summary(row)
            for row in rows
            if isinstance(row, dict)
        ]
        return result

    def load_customer(self, customer_id: int, irev: Optional[int] = None) -> Dict[str, Any]:
        """Load one customer."""
        return self.customer_api.load(customer_id, irev=irev)

    def get_customer_by_code(self, code: str, be_id: int) -> Dict[str, Any]:
        """Resolve customer code, then load the full customer master record."""
        customer_id = self.resolver.resolve_customer_code(code, be_id)
        return self.load_customer(customer_id)

    def get_customer_default_currency(
        self,
        customer_id: Optional[int] = None,
        customer_code: Optional[str] = None,
        be_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Load the single currency configured for a customer account."""
        if customer_id is None:
            if customer_code is None or be_id is None:
                raise ValueError("Either customer_id or both customer_code and be_id are required.")
            customer_id = self.resolver.resolve_customer_code(customer_code, be_id)

        payload = self.load_customer(customer_id)
        return {
            "customerId": int(customer_id),
            "curId": extract_default_currency_id(payload),
        }

    def get_customer_contacts(
        self,
        customer_id: Optional[int] = None,
        customer_code: Optional[str] = None,
        be_id: Optional[int] = None,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Load customer contacts and optionally apply business filters."""
        if customer_id is None:
            if customer_code is None or be_id is None:
                raise ValueError("Either customer_id or both customer_code and be_id are required.")
            customer_id = self.resolver.resolve_customer_code(customer_code, be_id)

        payload = self.load_customer(customer_id)
        rows = self.customer_api.extract_contact_rows(payload)
        filtered = filter_contact_rows(rows, **filters)

        return {
            "customerId": customer_id,
            "contactCount": len(filtered),
            "contacts": filtered,
            "contactSourceFound": bool(rows),
        }
