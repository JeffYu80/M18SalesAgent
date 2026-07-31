"""Currency and exchange-rate policy for M18 sales documents."""

from __future__ import annotations

from typing import Any, Dict, Optional

from m18_api import M18Client
from services.business_config import load_business_config
from services.customer_service import M18CustomerService


class M18CurrencyService:
    """Resolve a customer's document currency and its M18 exchange rate."""

    def __init__(
        self,
        client: Optional[M18Client] = None,
        customer_service: Optional[M18CustomerService] = None,
        business_config: Optional[Dict[str, Any]] = None,
    ):
        self.client = client or M18Client()
        self.customer_service = customer_service or M18CustomerService(client=self.client)
        self.business_config = business_config or load_business_config()

    def resolve_customer_document_currency(
        self,
        be_id: int,
        customer_code: Optional[str],
        t_date: str,
        customer_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not t_date:
            raise ValueError("t_date is required to resolve a document exchange rate.")

        return self.resolve_document_currency(
            be_id=be_id,
            t_date=t_date,
            customer_code=customer_code,
            customer_id=customer_id,
        )

    def resolve_document_currency(
        self,
        be_id: int,
        t_date: str,
        customer_code: Optional[str] = None,
        customer_id: Optional[int] = None,
        currency_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve an explicit currency code or a customer's default currency."""
        if currency_code:
            cur_id = self.resolve_currency_code(currency_code)
        else:
            customer_currency = self.customer_service.get_customer_default_currency(
                customer_id=customer_id,
                customer_code=customer_code,
                be_id=be_id,
            )
            cur_id = int(customer_currency["curId"])
        return self.resolve_currency_rate(be_id=be_id, cur_id=cur_id, t_date=t_date)

    def resolve_currency_code(self, currency_code: str) -> int:
        """Resolve an M18 currency code or symbol (for example, ``USD``)."""
        code = str(currency_code).strip()
        if not code:
            raise ValueError("currency is required when specified.")
        result = self.client.search_by_code("cur", code)
        rows = result.get("values", []) if isinstance(result, dict) else []
        matches = [
            row for row in rows
            if isinstance(row, dict)
            and code.upper() in {str(row.get("code", "")).upper(), str(row.get("sym", "")).upper()}
        ]
        if len(matches) != 1 or matches[0].get("id") is None:
            raise ValueError(f"Unable to resolve currency code '{currency_code}'.")
        return int(matches[0]["id"])

    def resolve_currency_rate(self, be_id: int, cur_id: int, t_date: str) -> Dict[str, Any]:
        """Resolve one document currency's rate against an entity currency."""
        if not t_date:
            raise ValueError("t_date is required to resolve a document exchange rate.")
        entity_currency_by_be_id = self.business_config.get("entity_currency_by_be_id", {})
        dom_cur_id = entity_currency_by_be_id.get(be_id, entity_currency_by_be_id.get(str(be_id)))
        if dom_cur_id is None and self.business_config.get("require_entity_currency_mapping", False):
            raise ValueError(f"No entity currency is configured for beId={be_id}.")
        if dom_cur_id is None:
            dom_cur_id = self.business_config.get("default_cur_id")
        if dom_cur_id is None:
            raise ValueError(f"No entity currency is configured for beId={be_id}.")
        dom_cur_id = int(dom_cur_id)
        rate_field = self.business_config.get("exchange_rate_field", "openRate")
        rate = self.client.get_exchange_rate(cur_id, dom_cur_id, t_date, rate_field=rate_field)
        return {"curId": cur_id, "rate": rate, "domCurId": dom_cur_id, "rateField": rate_field}
