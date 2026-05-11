"""
Quotation domain service for the Sales Quotation (`oldqu`) flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402
from scripts.m18_sales_quotation_api import (  # noqa: E402
    M18SalesQuotationAPI,
    build_draft_line,
    build_standard_header,
    build_standard_line,
)
from services.business_config import load_business_config  # noqa: E402
from services.reference_resolver import M18ReferenceResolver  # noqa: E402


class M18QuotationService:
    """Business service for sales quotation actions."""

    def __init__(
        self,
        client: Optional[M18Client] = None,
        quotation_api: Optional[M18SalesQuotationAPI] = None,
        resolver: Optional[M18ReferenceResolver] = None,
    ):
        self.client = client or M18Client()
        self.quotation_api = quotation_api or M18SalesQuotationAPI(self.client)
        self.resolver = resolver or M18ReferenceResolver(self.client)
        self.business_config = load_business_config()

    def search_quotations(
        self,
        be_id: int,
        quick_search: Optional[str] = None,
        start_row: int = 0,
        end_row: int = 100,
    ) -> Dict[str, Any]:
        return self.quotation_api.search(
            be_id=be_id,
            quick_search=quick_search,
            start_row=start_row,
            end_row=end_row,
        )

    def load_quotation(self, record_id: int, irev: Optional[int] = None) -> Dict[str, Any]:
        return self.quotation_api.load(record_id, irev=irev)

    def create_draft_from_codes(
        self,
        be_code: Optional[str],
        cus_code: str,
        lines: List[Dict[str, Any]],
        extra_fields: Optional[Dict[str, Any]] = None,
        be_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not be_code:
            raise ValueError("be_code is required")
        if not be_id:
            raise ValueError("be_id is required")
        merged_extra_fields = dict(extra_fields or {})
        if "staffCode" in merged_extra_fields:
            merged_extra_fields["staffId"] = self.resolver.resolve_staff_code(
                merged_extra_fields.pop("staffCode"), be_id,
            )
        if "staffId" not in merged_extra_fields:
            raise ValueError("staffCode (or staffId) is required")

        draft_lines = [
            build_draft_line(
                pro_code=line["proCode"],
                unit_code=line["unitCode"],
                qty=line["qty"],
                up=line["up"],
                disc=line.get("disc", 0),
                **{k: v for k, v in line.items() if k not in {"proCode", "unitCode", "qty", "up", "disc"}},
            )
            for line in lines
        ]
        return self.quotation_api.create_draft_by_codes(
            be_code=be_code,
            cus_code=cus_code,
            lines=draft_lines,
            extra_fields=merged_extra_fields,
        )

    def save_quotation(
        self,
        be_id: int,
        header: Dict[str, Any],
        lines: List[Dict[str, Any]],
        remark_values: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Save a quotation, resolving business codes into IDs when needed."""
        normalized_header = dict(header)
        if not be_id:
            raise ValueError("be_id is required")
        normalized_header.setdefault("curId", self.business_config.get("default_cur_id"))
        normalized_header.setdefault("flowTypeId", self.business_config.get("default_flow_type_id"))
        if "staffCode" in normalized_header:
            normalized_header["staffId"] = self.resolver.resolve_staff_code(
                normalized_header.pop("staffCode"), be_id,
            )
        if "staffId" not in normalized_header:
            raise ValueError("staffCode (or staffId) is required")
        if "cusId" not in normalized_header and "cusCode" in normalized_header:
            normalized_header["cusId"] = self.resolver.resolve_customer_code(normalized_header["cusCode"], be_id)

        header_row = build_standard_header(
            be_id=be_id,
            cus_id=normalized_header["cusId"],
            cur_id=normalized_header["curId"],
            flow_type_id=normalized_header["flowTypeId"],
            staff_id=normalized_header["staffId"],
            t_date=normalized_header["tDate"],
            rate=normalized_header.get("rate", 1),
            amt=normalized_header.get("amt"),
            **{
                k: v
                for k, v in normalized_header.items()
                if k not in {"cusCode", "cusId", "curId", "flowTypeId", "staffId", "tDate", "rate", "amt"}
            },
        )

        line_rows = []
        for line in lines:
            normalized_line = dict(line)
            if "proId" not in normalized_line and "proCode" in normalized_line:
                normalized_line["proId"] = self.resolver.resolve_product_code(normalized_line["proCode"], be_id)
            if "unitId" not in normalized_line and "unitCode" in normalized_line:
                normalized_line["unitId"] = self.resolver.resolve_standard_quote_unit_id(
                    pro_id=normalized_line["proId"],
                    unit_code=normalized_line["unitCode"],
                    strategy=self.business_config.get("quotation_standard_unit_mode", "unit_master"),
                )

            line_rows.append(
                build_standard_line(
                    pro_id=normalized_line["proId"],
                    unit_id=normalized_line["unitId"],
                    qty=normalized_line["qty"],
                    up=normalized_line["up"],
                    source_type=normalized_line.get("sourceType", "pro"),
                    disc=normalized_line.get("disc", 0),
                    amt=normalized_line.get("amt", normalized_line["qty"] * normalized_line["up"]),
                    **{
                        k: v
                        for k, v in normalized_line.items()
                        if k not in {"proCode", "unitCode", "proId", "unitId", "qty", "up", "sourceType", "disc", "amt"}
                    },
                )
            )

        return self.quotation_api.save(
            header_values=[header_row],
            line_values=line_rows,
            remark_values=remark_values,
        )


