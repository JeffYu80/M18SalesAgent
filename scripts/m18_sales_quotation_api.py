"""
Quotation-specific API wrapper for M18 Sales Quotation (`oldqu`).

This file is the first vertical slice of the larger M18 architecture:

- Agent: user-facing reasoning and conversation
- Skill: quotation domain rules
- API script: concrete M18 calls and payload builders
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_api import M18Client  # noqa: E402


MENU_SALES_QUOTATION = "oldqu"
TABLE_SALES_QUOTATION_MAIN = "mainqu"
TABLE_SALES_QUOTATION_LINE = "qut"
TABLE_SALES_QUOTATION_REMARK = "remqu"


class M18SalesQuotationAPI:
    """Quotation-focused wrapper around the shared M18 client."""

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
        """Search quotation headers through the common search endpoint."""
        return self.client.search_entities(
            menu_code=MENU_SALES_QUOTATION,
            be_id=be_id,
            start_row=start_row,
            end_row=end_row,
            quick_search=quick_search,
            format_id=format_id,
        )

    def load(self, record_id: int, irev: Optional[int] = None) -> Dict[str, Any]:
        """Load one sales quotation by record ID."""
        return self.client.read_entity(MENU_SALES_QUOTATION, record_id, irev=irev)

    def create_draft_by_codes(
        self,
        be_code: str,
        cus_code: str,
        lines: List[Dict[str, Any]],
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a quotation with bsFlow using business codes instead of IDs."""
        payload: Dict[str, Any] = {
            "beCode": be_code,
            "cusCode": cus_code,
            TABLE_SALES_QUOTATION_LINE: lines,
            "descOrigin": "CUSREF",
        }
        if extra_fields:
            payload.update(extra_fields)
        return self.client.save_entity_auto(MENU_SALES_QUOTATION, payload)

    def save(
        self,
        header_values: List[Dict[str, Any]],
        line_values: List[Dict[str, Any]],
        remark_values: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create or update a quotation with explicit internal IDs."""
        payload: Dict[str, Any] = {
            TABLE_SALES_QUOTATION_MAIN: {"values": header_values},
            TABLE_SALES_QUOTATION_LINE: {"values": line_values},
        }
        if remark_values:
            payload[TABLE_SALES_QUOTATION_REMARK] = {"values": remark_values}
        return self.client.save_entity(MENU_SALES_QUOTATION, payload)




def build_draft_line(
    pro_code: str,
    unit_code: str,
    qty: float,
    up: float,
    disc: float = 0,
    **extra_fields: Any,
) -> Dict[str, Any]:
    """Build one bsFlow quotation line using business codes."""
    line: Dict[str, Any] = {
        "proCode": pro_code,
        "unitCode": unit_code,
        "qty": qty,
        "up": up,
        "disc": disc,
    }
    line.update(extra_fields)
    return line


def build_standard_header(
    be_id: int,
    cus_id: int,
    cur_id: int,
    flow_type_id: int,
    staff_id: int,
    t_date: str,
    rate: float = 1,
    amt: Optional[float] = None,
    **extra_fields: Any,
) -> Dict[str, Any]:
    """Build one standard quotation header row."""
    header: Dict[str, Any] = {
        "beId": be_id,
        "cusId": cus_id,
        "curId": cur_id,
        "flowTypeId": flow_type_id,
        "staffId": staff_id,
        "tDate": t_date,
        "rate": rate,
        "descOrigin": "CUSREF",
    }
    if amt is not None:
        header["amt"] = amt
    header.update(extra_fields)
    return header


def build_standard_line(
    pro_id: int,
    unit_id: int,
    qty: float,
    up: float,
    source_type: str = "pro",
    disc: float = 0,
    amt: Optional[float] = None,
    **extra_fields: Any,
) -> Dict[str, Any]:
    """Build one standard quotation line row."""
    line: Dict[str, Any] = {
        "sourceType": source_type,
        "proId": pro_id,
        "unitId": unit_id,
        "qty": qty,
        "up": up,
        "disc": disc,
    }
    if amt is not None:
        line["amt"] = amt
    line.update(extra_fields)
    return line
