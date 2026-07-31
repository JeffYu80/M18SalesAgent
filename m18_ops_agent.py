"""
Unified agent dispatcher for current M18 business capabilities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.business_config import load_business_config  # noqa: E402
from services.customer_service import M18CustomerService  # noqa: E402
from services.product_service import M18ProductService  # noqa: E402
from services.quotation_service import M18QuotationService  # noqa: E402
from services.sales_order_service import M18SalesOrderService  # noqa: E402


class M18OpsAgent:
    """Action dispatcher that routes business actions to service methods."""

    ACTION_MAP = {
        "customer.search": "_customer_search",
        "customer.load": "_customer_load",
        "customer.contacts": "_customer_contacts",
        "product.search": "_product_search",
        "product.load": "_product_load",
        "product.units": "_product_units",
        "product.customer_item_codes": "_product_customer_item_codes",
        "quotation.search": "_quotation_search",
        "quotation.load": "_quotation_load",
        "quotation.create_draft": "_quotation_create_draft",
        "quotation.save": "_quotation_save",
        "sales_order.search": "_sales_order_search",
        "sales_order.load": "_sales_order_load",
        "sales_order.create_draft": "_sales_order_create_draft",
        "sales_order.save": "_sales_order_save",
    }

    def __init__(
        self,
        customer_service: Optional[M18CustomerService] = None,
        product_service: Optional[M18ProductService] = None,
        quotation_service: Optional[M18QuotationService] = None,
        sales_order_service: Optional[M18SalesOrderService] = None,
    ):
        self.business_config = load_business_config()
        self.customer_service = customer_service or M18CustomerService()
        self.product_service = product_service or M18ProductService()
        self.quotation_service = quotation_service or M18QuotationService()
        self.sales_order_service = sales_order_service or M18SalesOrderService()

    def supported_actions(self) -> list[str]:
        return sorted(self.ACTION_MAP.keys())

    def handle(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        method_name = self.ACTION_MAP.get(action)
        if not method_name:
            return self._error_result(
                action=action,
                error_type="UnsupportedAction",
                message=f"Unsupported action: {action}",
            )

        try:
            method: Callable[[Dict[str, Any]], Dict[str, Any]] = getattr(self, method_name)
            data = method(params)
            return {
                "action": action,
                "ok": True,
                "data": data,
            }
        except Exception as exc:
            return self._error_result(
                action=action,
                error_type=exc.__class__.__name__,
                message=str(exc),
            )

    def _required(self, params: Dict[str, Any], key: str) -> Any:
        if key not in params or params[key] in (None, ""):
            raise ValueError(f"Missing required parameter: {key}")
        return params[key]

    def _required_be_id(self, params: Dict[str, Any]) -> Any:
        return self._required(params, "beId")

    def _required_be_code(self, params: Dict[str, Any]) -> Any:
        return self._required(params, "beCode")

    def _error_result(self, action: str, error_type: str, message: str) -> Dict[str, Any]:
        return {
            "action": action,
            "ok": False,
            "error": {
                "type": error_type,
                "message": message,
            },
        }

    def _customer_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.customer_service.search_customers(
            be_id=self._required_be_id(params),
            quick_search=params.get("quickSearchStr"),
            start_row=params.get("startRow", 0),
            end_row=params.get("endRow", 20),
        )

    def _customer_load(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.customer_service.load_customer(
            customer_id=self._required(params, "customerId"),
            irev=params.get("iRev"),
        )

    def _customer_contacts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.customer_service.get_customer_contacts(
            customer_id=params.get("customerId"),
            customer_code=params.get("customerCode"),
            be_id=self._required_be_id(params),
            name=params.get("name"),
            email=params.get("email"),
            phone=params.get("phone"),
            department=params.get("department"),
        )

    def _product_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.product_service.search_products(
            be_id=self._required_be_id(params),
            quick_search=params.get("quickSearchStr"),
            start_row=params.get("startRow", 0),
            end_row=params.get("endRow", 20),
        )

    def _product_load(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.product_service.load_product(
            product_id=self._required(params, "productId"),
            irev=params.get("iRev"),
        )

    def _product_units(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.product_service.get_product_units(
            product_code=self._required(params, "productCode"),
            be_id=self._required_be_id(params),
        )

    def _product_customer_item_codes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.product_service.query_customer_item_codes(
            customer_code=self._required(params, "customerCode"),
            product_code=self._required(params, "productCode"),
            be_id=self._required_be_id(params),
        )

    def _quotation_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.quotation_service.search_quotations(
            be_id=self._required_be_id(params),
            quick_search=params.get("quickSearchStr"),
            start_row=params.get("startRow", 0),
            end_row=params.get("endRow", 20),
        )

    def _quotation_load(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.quotation_service.load_quotation(
            record_id=self._required(params, "recordId"),
            irev=params.get("iRev"),
        )

    def _quotation_create_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        extra_fields = dict(params.get("extraFields", {}))
        if "staffCode" in params and "staffCode" not in extra_fields:
            extra_fields["staffCode"] = params["staffCode"]
        if "currency" in params and "currency" not in extra_fields:
            extra_fields["currency"] = params["currency"]
        if "tDate" not in extra_fields:
            t_date = params.get("tDate", params.get("t_date"))
            if t_date:
                extra_fields["tDate"] = t_date
        return self.quotation_service.create_draft_from_codes(
            be_code=self._required_be_code(params),
            be_id=self._required_be_id(params),
            cus_code=self._required(params, "customerCode"),
            lines=self._required(params, "lines"),
            extra_fields=extra_fields,
        )

    def _quotation_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        header = dict(self._required(params, "header"))
        if "staffCode" not in header and "staffCode" in params:
            header["staffCode"] = params["staffCode"]
        if "currency" not in header and "currency" in params:
            header["currency"] = params["currency"]
        if "tDate" not in header:
            t_date = params.get("tDate", params.get("t_date"))
            if t_date:
                header["tDate"] = t_date
        return self.quotation_service.save_quotation(
            be_id=self._required_be_id(params),
            header=header,
            lines=self._required(params, "lines"),
            remark_values=params.get("remarkValues"),
        )

    def _sales_order_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.sales_order_service.search_sales_orders(
            be_id=self._required_be_id(params),
            quick_search=params.get("quickSearchStr"),
            start_row=params.get("startRow", 0),
            end_row=params.get("endRow", 20),
        )

    def _sales_order_load(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.sales_order_service.load_sales_order(
            record_id=self._required(params, "recordId"),
            irev=params.get("iRev"),
        )

    def _sales_order_create_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        extra_fields = dict(params.get("extraFields", {}))
        if "staffCode" in params and "staffCode" not in extra_fields:
            extra_fields["staffCode"] = params["staffCode"]
        if "currency" in params and "currency" not in extra_fields:
            extra_fields["currency"] = params["currency"]
        if "tDate" not in extra_fields:
            t_date = params.get("tDate", params.get("t_date"))
            if t_date:
                extra_fields["tDate"] = t_date
        return self.sales_order_service.create_draft_from_codes(
            be_code=self._required_be_code(params),
            be_id=self._required_be_id(params),
            cus_code=self._required(params, "customerCode"),
            lines=self._required(params, "lines"),
            extra_fields=extra_fields,
        )

    def _sales_order_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        header = dict(self._required(params, "header"))
        if "staffCode" not in header and "staffCode" in params:
            header["staffCode"] = params["staffCode"]
        if "currency" not in header and "currency" in params:
            header["currency"] = params["currency"]
        if "tDate" not in header:
            t_date = params.get("tDate", params.get("t_date"))
            if t_date:
                header["tDate"] = t_date
        return self.sales_order_service.save_sales_order(
            be_id=self._required_be_id(params),
            header=header,
            lines=self._required(params, "lines"),
            remark_values=params.get("remarkValues"),
        )
