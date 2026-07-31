"""
Product-focused API wrapper for M18 product master (`pro`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402


MENU_PRODUCT = "pro"


class M18ProductAPI:
    """Product-focused wrapper around the shared M18 client."""

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
        return self.client.search_entities(
            menu_code=MENU_PRODUCT,
            be_id=be_id,
            start_row=start_row,
            end_row=end_row,
            quick_search=quick_search,
            format_id=format_id,
        )

    def load(self, product_id: int, irev: Optional[int] = None) -> Dict[str, Any]:
        return self.client.read_entity(MENU_PRODUCT, product_id, irev=irev)


def normalize_product_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "code": row.get("code"),
        "name": row.get("desc__lang") or row.get("desc"),
        "lastModifyDate": row.get("lastModifyDate"),
        "raw": row,
    }


def extract_default_units(product_payload: Dict[str, Any]) -> Dict[str, Any]:
    data = product_payload.get("data", {})
    pro_rows = data.get("pro", [])
    dual_rows = data.get("produalunit", [])
    price_rows = data.get("price", [])

    product_row = pro_rows[0] if pro_rows and isinstance(pro_rows[0], dict) else {}
    default_dual_row = None
    for row in dual_rows:
        if isinstance(row, dict) and row.get("default"):
            default_dual_row = row
            break

    default_price_row = next(
        (
            row for row in price_rows
            if isinstance(row, dict)
            and row.get("hId") == product_row.get("id")
            and row.get("unitId") == product_row.get("saleUnitId")
            and row.get("saleUnit") in (True, 1, "true", "1")
            and not row.get("expired")
        ),
        None,
    )

    return {
        "unitId": product_row.get("unitId"),
        "stkUnitId": product_row.get("stkUnitId"),
        "saleUnitId": product_row.get("saleUnitId"),
        "purUnitId": product_row.get("purUnitId"),
        "pickUnitId": product_row.get("pickUnitId"),
        "defaultDualUnitId": default_dual_row.get("unitId") if default_dual_row else None,
        # Global unit ID selected by the product's default sales unit.
        "defaultSalesUnitId": product_row.get("saleUnitId"),
        # Product price/unit-detail ID required by standard qut/sot.unitId.
        "defaultSalesPriceId": default_price_row.get("id") if default_price_row else None,
    }


def extract_external_product_codes(product_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = product_payload.get("data", {})
    results: List[Dict[str, Any]] = []

    for row in data.get("ediconnsku", []):
        if isinstance(row, dict) and row.get("ediPlatformSku"):
            results.append(
                {
                    "source": "ediconnsku",
                    "externalCode": row.get("ediPlatformSku"),
                    "configId": row.get("ediconnConfigId"),
                    "row": row,
                }
            )

    for row in data.get("ecomprorefer", []):
        if isinstance(row, dict):
            if row.get("refer"):
                results.append(
                    {
                        "source": "ecomprorefer.refer",
                        "externalCode": row.get("refer"),
                        "shopId": row.get("ecomshopId"),
                        "row": row,
                    }
                )
            if row.get("msmtReferSku"):
                results.append(
                    {
                        "source": "ecomprorefer.msmtReferSku",
                        "externalCode": row.get("msmtReferSku"),
                        "shopId": row.get("ecomshopId"),
                        "row": row,
                    }
                )

    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in results:
        key = (item["source"], item["externalCode"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
