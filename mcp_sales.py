"""
MCP server for the M18 sales agent.

This module exposes Customer, Product, Sales Quotation, and Sales Order
operations as MCP tools for agent consumption.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.func_metadata import _create_wrapped_model as _orig_create
from pydantic import BaseModel, create_model as _pydantic_create_model


def _patched_create(func_name: str, annotation: Any):
    if annotation is str:
        return _pydantic_create_model(func_name + "Out", output=(str, ...))
    return _orig_create(func_name, annotation)


import mcp.server.fastmcp.utilities.func_metadata as _fm
_fm._create_wrapped_model = _patched_create

from m18_api import M18Client
from services.business_config import load_business_config
from services.customer_service import M18CustomerService
from services.product_service import M18ProductService
from services.quotation_service import M18QuotationService
from services.sales_order_service import M18SalesOrderService
from services.reference_resolver import M18ReferenceResolver


_biz_config = load_business_config()
BE_MAPPING: Dict[str, int] = _biz_config.get("be_mapping", {})

mcp = FastMCP(
    "M18 ERP",
    instructions="""
M18 ERP integration server.

Use these tools to search, load, and create sales quotations, sales orders,
customers, and products in the Multiable M18 ERP system.

All operations require:
- username
- password
- be_id where applicable

Notes:
- remarks = 备注
- l_time = 交货期文字说明，不是日期
- d_date = 去货日期，格式 YYYY-MM-DD
""",
)


def _auth_svc(service_cls, username: str, password: str):
    return service_cls(client=M18Client(username=username, password=password))


def _resolve_contact(cus_code: str, contact_name: str, username: str, password: str, be_id: int) -> int:
    svc = _auth_svc(M18CustomerService, username, password)
    result = svc.get_customer_contacts(customer_code=cus_code, be_id=be_id)
    contacts = result.get("contacts", [])
    exact = [c for c in contacts if c.get("man", "").strip() == contact_name.strip()]
    if exact:
        return int(exact[0].get("id", 0))
    fuzzy = [c for c in contacts if contact_name.strip().lower() in c.get("man", "").lower()]
    if fuzzy:
        return int(fuzzy[0].get("id", 0))
    if contacts:
        return int(contacts[0].get("id", 0))
    return 0


def _get_part_info(product_code: str, cus_code: str, username: str, password: str, be_id: int):
    """查客户料号表(EBI 102)取 refCode/dDesc_en，bDesc 系列从产品主档取。"""
    client = M18Client(username=username, password=password)
    result: Dict[str, Any] = {"refCode": "", "dDesc_en": ""}

    # 先查客户料号表
    report_id = _biz_config.get("customer_part_report_id", 102)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    if rows:
        for r in rows:
            if not isinstance(r, dict):
                continue
            if r.get("CUS_A_code", "").strip().lower() == cus_code.strip().lower() and \
               r.get("PRO_A_code", "").strip().lower() == product_code.strip().lower():
                result["refCode"] = r.get("F_A_refCode", "").strip()
                result["dDesc_en"] = r.get("PRO_A_dDesc_en", "").strip()
                break

    # 从产品主档取 bDesc 系列
    try:
        pro_id = M18ReferenceResolver(client=client).resolve_product_code(product_code, be_id)
        pro = client.read_entity("pro", pro_id)
        rows_list = pro.get("data", {}).get("pro", [])
        if rows_list:
            r = rows_list[0]
            result.setdefault("bDesc_en", (r.get("desc_en") or r.get("desc") or "").strip())
            result.setdefault("bDesc_zh-CN", (r.get("desc_zh-CN") or "").strip())
            result.setdefault("bDesc_zh-TW", (r.get("desc_zh-TW") or "").strip())
            if not result["dDesc_en"]:
                result["dDesc_en"] = (r.get("dDesc_en") or r.get("dDesc") or "").strip()
        return result
    except Exception:
        return result


def _get_declaration_type(product_code: str, client: M18Client, be_id: int) -> str:
    """读取产品主档 pro_udffields 的 udfdeclarationtype。"""
    try:
        pro_id = M18ReferenceResolver(client=client).resolve_product_code(product_code, be_id)
        pro = client.read_entity("pro", pro_id)
        rows_list = pro.get("data", {}).get("pro_udffields", [])
        if rows_list:
            return rows_list[0].get("udfdeclarationtype", "").strip()
    except Exception:
        pass
    return ""


def _load_customer_staff_id(cus_code: str, username: str, password: str, be_id: int) -> int:
    svc = _auth_svc(M18CustomerService, username, password)
    customer_id = svc.resolver.resolve_customer_code(cus_code, be_id)
    payload = svc.load_customer(customer_id)
    rows = payload.get("data", {}).get("cus", [])
    if rows:
        staff_id = rows[0].get("staffId", 0)
        return int(staff_id) if staff_id else 0
    return 0


def _resolve_staff(cus_code: str, staff_code: str, username: str, password: str, be_id: int) -> int:
    if staff_code:
        return M18ReferenceResolver(client=M18Client(username=username, password=password)).resolve_staff_code(
            staff_code, be_id
        )
    return _load_customer_staff_id(cus_code, username, password, be_id)


def _load_customer_terms(cus_code: str, username: str, password: str, be_id: int) -> Dict[str, str]:
    svc = _auth_svc(M18CustomerService, username, password)
    payload = svc.load_customer(svc.resolver.resolve_customer_code(cus_code, be_id))
    rows = payload.get("data", {}).get("remcus", [])
    result = {"payTerm": "", "tradeTerm": ""}
    if rows:
        row = rows[0]
        result["payTerm"] = row.get("payTerm_en") or row.get("payTerm") or ""
        result["tradeTerm"] = row.get("tradeTerm_en") or row.get("tradeTerm") or ""
    return result


@mcp.tool()
def business_entity_lookup(be_code: str):
    """Look up local be_code -> be_id mapping."""
    be_id = BE_MAPPING.get(be_code.upper())
    if be_id:
        return json.dumps({"be_code": be_code.upper(), "be_id": be_id}, ensure_ascii=False)
    candidates = {k: v for k, v in BE_MAPPING.items() if be_code.upper() in k}
    if candidates:
        return json.dumps({"be_code": be_code, "candidates": candidates}, ensure_ascii=False)
    return json.dumps(
        {"be_code": be_code, "error": "未找到该业务实体，请检查 config/m18.uat.yaml 中的 be_mapping"},
        ensure_ascii=False,
    )


@mcp.tool()
def customer_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None):
    svc = _auth_svc(M18CustomerService, username, password)
    return json.dumps(svc.search_customers(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def customer_load(customer_id: int, username: str, password: str):
    svc = _auth_svc(M18CustomerService, username, password)
    return json.dumps(svc.load_customer(customer_id), ensure_ascii=False)


@mcp.tool()
def customer_search_by_name(customer_name: str, username: str, password: str, be_id: Optional[int] = None):
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_list_report_id", 103)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    if not rows:
        return json.dumps({"matches": [], "count": 0}, ensure_ascii=False)

    needle = customer_name.strip().lower()
    matches = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = (row.get("MAIN_A_desc__lang") or "").strip().lower()
        code = (row.get("MAIN_A_code") or "").strip().lower()
        if needle in name or needle in code:
            matches.append(
                {
                    "customerCode": row.get("MAIN_A_code", ""),
                    "customerName": row.get("MAIN_A_desc__lang", ""),
                    "customerId": row.get("MAIN_A_id", ""),
                    "beId": row.get("MAIN_A_beId", ""),
                    "beCode": row.get("MAIN_A_beId_code", ""),
                }
            )

    matches.sort(key=lambda item: (item.get("beCode", ""), item.get("customerCode", "")))
    return json.dumps({"matches": matches, "count": len(matches)}, ensure_ascii=False)


@mcp.tool()
def customer_list_all(username: str, password: str, be_id: Optional[int] = None):
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_list_report_id", 103)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False)


@mcp.tool()
def customer_part_list_all(username: str, password: str, be_id: int = 7):
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_part_report_id", 102)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False)


@mcp.tool()
def customer_part_lookup(customer_code: str, part_code: str, be_id: int, username: str, password: str):
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_part_report_id", 102)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = [row for row in report.get("rows", report.get("values", [])) if isinstance(row, dict)]
    if not rows:
        return json.dumps({"matches": [], "count": 0}, ensure_ascii=False)

    needle_cus = customer_code.strip().lower()
    needle_part = part_code.strip().lower()
    matches = []
    for row in rows:
        haystack = {k.lower(): str(v).lower() for k, v in row.items() if v is not None}
        if needle_cus in str(haystack) and needle_part in str(haystack):
            matches.append(
                {
                    "customerCode": row.get("CUS_A_code", ""),
                    "customerName": row.get("CUS_A_desc__lang", ""),
                    "productCode": row.get("PRO_A_code", ""),
                    "productName": row.get("PRO_A_desc__lang", ""),
                    "customerPartCode": row.get("F_A_refCode", ""),
                }
            )
    return json.dumps({"matches": matches, "count": len(matches)}, ensure_ascii=False)


@mcp.tool()
def customer_contacts(customer_code: str, be_id: int, username: str, password: str):
    svc = _auth_svc(M18CustomerService, username, password)
    return json.dumps(svc.get_customer_contacts(customer_code=customer_code, be_id=be_id), ensure_ascii=False)


@mcp.tool()
def product_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None):
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.search_products(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def product_load(product_id: int, username: str, password: str):
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.load_product(product_id), ensure_ascii=False)


@mcp.tool()
def product_units(product_code: str, be_id: int, username: str, password: str):
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.get_product_units(product_code=product_code, be_id=be_id), ensure_ascii=False)


@mcp.tool()
def product_customer_item_codes(customer_code: str, product_code: str, be_id: int, username: str, password: str):
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(
        svc.query_customer_item_codes(customer_code=customer_code, product_code=product_code, be_id=be_id),
        ensure_ascii=False,
    )


@mcp.tool()
def quotation_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None):
    svc = _auth_svc(M18QuotationService, username, password)
    return json.dumps(svc.search_quotations(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def quotation_load(record_id: int, username: str, password: str):
    svc = _auth_svc(M18QuotationService, username, password)
    return json.dumps(svc.load_quotation(record_id), ensure_ascii=False)


@mcp.tool()
def quotation_create_draft(
    customer_code: str,
    product_code: str,
    qty: float,
    up: float,
    username: str,
    password: str,
    be_code: str,
    be_id: int,
    customer_po: str,
    staff_code: str = "",
    unit_code: str = "PCS",
    disc: float = 0,
    contact_name: str = "",
    t_date: str = "",
    d_date: str = "",
    packing: str = "",
    l_time: str = "",
    remarks: str = "",
    extra_fields: str = "{}",
):
    svc = _auth_svc(M18QuotationService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))

    staff_id = _resolve_staff(customer_code, staff_code, username, password, be_id)
    if staff_id:
        extras["staffId"] = staff_id
    if not t_date:
        t_date = date.today().isoformat()
    extras.setdefault("tDate", t_date)
    if d_date:
        extras.setdefault("dDate", d_date)
    if packing:
        extras.setdefault("packing", packing)
    if l_time:
        extras.setdefault("lTime", l_time)
    if contact_name:
        contact_id = _resolve_contact(customer_code, contact_name, username, password, be_id)
        if contact_id:
            extras["manId"] = contact_id
    if customer_po:
        extras["udfcmpo"] = customer_po

    terms = _load_customer_terms(customer_code, username, password, be_id)
    if terms["payTerm"]:
        extras.setdefault("payTerm", terms["payTerm"])
    if terms["tradeTerm"]:
        extras.setdefault("tradeTerm", terms["tradeTerm"])
    if remarks:
        extras.setdefault("remarks", remarks)

    line = {"proCode": product_code, "unitCode": unit_code, "qty": qty, "up": up, "disc": disc}
    part_info = _get_part_info(product_code, customer_code, username, password, be_id)
    if part_info:
        if part_info.get("refCode"):
            line["refCode"] = part_info["refCode"]
        if part_info.get("bDesc_en"):
            line["bDesc_en"] = part_info["bDesc_en"]
        if part_info.get("bDesc_zh-CN"):
            line["bDesc_zh-CN"] = part_info["bDesc_zh-CN"]
        if part_info.get("bDesc_zh-TW"):
            line["bDesc_zh-TW"] = part_info["bDesc_zh-TW"]
        if part_info.get("dDesc_en"):
            line["dDesc_en"] = part_info["dDesc_en"]

    return json.dumps(
        svc.create_draft_from_codes(
            be_code=be_code,
            be_id=be_id,
            cus_code=customer_code,
            lines=[line],
            extra_fields=extras,
        ),
        ensure_ascii=False,
    )


@mcp.tool()
def quotation_save(
    cus_code: str,
    product_code: str,
    qty: float,
    up: float,
    username: str,
    password: str,
    customer_po: str,
    be_id: int = 7,
    staff_code: str = "",
    t_date: str = "",
    cur_id: int = 3,
    flow_type_id: int = 5,
    unit_code: str = "PCS",
    disc: float = 0,
    contact_name: str = "",
    d_date: str = "",
    packing: str = "",
    l_time: str = "",
    remarks: str = "",
    extra_fields: str = "{}",
):
    svc = _auth_svc(M18QuotationService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
    if not t_date:
        t_date = date.today().isoformat()
    if d_date:
        extras.setdefault("dDate", d_date)
    if packing:
        extras.setdefault("packing", packing)
    if l_time:
        extras.setdefault("lTime", l_time)
    if contact_name:
        contact_id = _resolve_contact(cus_code, contact_name, username, password, be_id)
        if contact_id:
            extras["manId"] = contact_id
    if customer_po:
        extras["udfcmpo"] = customer_po

    terms = _load_customer_terms(cus_code, username, password, be_id)
    if terms["payTerm"]:
        extras.setdefault("payTerm", terms["payTerm"])
    if terms["tradeTerm"]:
        extras.setdefault("tradeTerm", terms["tradeTerm"])

    staff_id = _resolve_staff(cus_code, staff_code, username, password, be_id)
    if staff_id:
        extras["staffId"] = staff_id

    part_info = _get_part_info(product_code, cus_code, username, password, be_id)

    amt = qty * up
    header = {
        "cusCode": cus_code,
        "curId": cur_id,
        "flowTypeId": flow_type_id,
        "tDate": t_date,
        "rate": 1,
        "amt": amt,
        **extras,
    }
    line = {
        "proCode": product_code,
        "unitCode": unit_code,
        "qty": qty,
        "up": up,
        "disc": disc,
        "amt": amt,
        **extras,
    }
    if part_info:
        if part_info.get("refCode"):
            line["refCode"] = part_info["refCode"]
        if part_info.get("bDesc_en"):
            line["bDesc_en"] = part_info["bDesc_en"]
        if part_info.get("bDesc_zh-CN"):
            line["bDesc_zh-CN"] = part_info["bDesc_zh-CN"]
        if part_info.get("bDesc_zh-TW"):
            line["bDesc_zh-TW"] = part_info["bDesc_zh-TW"]
        if part_info.get("dDesc_en"):
            line["dDesc_en"] = part_info["dDesc_en"]
    remark_values = [{"remarks": remarks}] if remarks else None
    return json.dumps(svc.save_quotation(be_id=be_id, header=header, lines=[line], remark_values=remark_values), ensure_ascii=False)


@mcp.tool()
def sales_order_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None):
    svc = _auth_svc(M18SalesOrderService, username, password)
    return json.dumps(svc.search_sales_orders(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def sales_order_load(record_id: int, username: str, password: str):
    svc = _auth_svc(M18SalesOrderService, username, password)
    return json.dumps(svc.load_sales_order(record_id), ensure_ascii=False)


@mcp.tool()
def sales_order_create_draft(
    customer_code: str,
    product_code: str,
    qty: float,
    up: float,
    username: str,
    password: str,
    be_code: str,
    be_id: int,
    customer_po: str,
    staff_code: str = "",
    unit_code: str = "PCS",
    disc: float = 0,
    contact_name: str = "",
    t_date: str = "",
    d_date: str = "",
    cus_ddate: str = "",
    extra_fields: str = "{}",
):
    svc = _auth_svc(M18SalesOrderService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))

    staff_id = _resolve_staff(customer_code, staff_code, username, password, be_id)
    if staff_id:
        extras["staffId"] = staff_id
    if not t_date:
        t_date = date.today().isoformat()
    extras.setdefault("tDate", t_date)
    if d_date:
        extras["dDate"] = d_date
    if cus_ddate:
        extras["cusDDate"] = cus_ddate
    if contact_name:
        contact_id = _resolve_contact(customer_code, contact_name, username, password, be_id)
        if contact_id:
            extras["manId"] = contact_id
    if customer_po:
        extras["cuspono"] = customer_po
    terms = _load_customer_terms(customer_code, username, password, be_id)
    if terms["payTerm"]:
        extras["payTerm"] = terms["payTerm"]
    if terms["tradeTerm"]:
        extras["tradeTerm"] = terms["tradeTerm"]

    line = {"proCode": product_code, "unitCode": unit_code, "qty": qty, "up": up, "disc": disc}
    part_info = _get_part_info(product_code, customer_code, username, password, be_id)
    if part_info:
        if part_info.get("refCode"):
            line["refCode"] = part_info["refCode"]
        if part_info.get("bDesc_en"):
            line["bDesc_en"] = part_info["bDesc_en"]
        if part_info.get("bDesc_zh-CN"):
            line["bDesc_zh-CN"] = part_info["bDesc_zh-CN"]
        if part_info.get("bDesc_zh-TW"):
            line["bDesc_zh-TW"] = part_info["bDesc_zh-TW"]
        if part_info.get("dDesc_en"):
            line["dDesc_en"] = part_info["dDesc_en"]

    return json.dumps(
        svc.create_draft_from_codes(
            be_code=be_code,
            be_id=be_id,
            cus_code=customer_code,
            lines=[line],
            extra_fields=extras,
        ),
        ensure_ascii=False,
    )


@mcp.tool()
def sales_order_save(
    cus_code: str,
    product_code: str,
    qty: float,
    up: float,
    username: str,
    password: str,
    customer_po: str,
    be_id: int = 7,
    staff_code: str = "",
    t_date: str = "",
    d_date: str = "",
    cus_ddate: str = "",
    cur_id: int = 3,
    flow_type_id: int = 5,
    unit_code: str = "PCS",
    disc: float = 0,
    contact_name: str = "",
    extra_fields: str = "{}",
):
    svc = _auth_svc(M18SalesOrderService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
    if not t_date:
        t_date = date.today().isoformat()

    staff_id = _resolve_staff(cus_code, staff_code, username, password, be_id)
    if staff_id:
        extras["staffId"] = staff_id
    if contact_name:
        contact_id = _resolve_contact(cus_code, contact_name, username, password, be_id)
        if contact_id:
            extras["manId"] = contact_id
    if customer_po:
        extras["cuspono"] = customer_po
    if d_date:
        extras["dDate"] = d_date
    if cus_ddate:
        extras["cusDDate"] = cus_ddate
    terms = _load_customer_terms(cus_code, username, password, be_id)
    if terms["payTerm"]:
        extras["payTerm"] = terms["payTerm"]
    if terms["tradeTerm"]:
        extras.setdefault("tradeTerm", terms["tradeTerm"])
    part_info = _get_part_info(product_code, cus_code, username, password, be_id)
    remark_values = [{"remarks": remarks}] if remarks else None
    amt = qty * up
    header = {
        "cusCode": cus_code,
        "curId": cur_id,
        "flowTypeId": flow_type_id,
        "tDate": t_date,
        "rate": 1,
        "amt": amt,
        **extras,
    }
    line = {
        "proCode": product_code,
        "unitCode": unit_code,
        "qty": qty,
        "up": up,
        "disc": disc,
        "amt": amt,
        **extras,
    }
    if part_info:
        if part_info.get("refCode"):
            line["refCode"] = part_info["refCode"]
        if part_info.get("bDesc_en"):
            line["bDesc_en"] = part_info["bDesc_en"]
        if part_info.get("bDesc_zh-CN"):
            line["bDesc_zh-CN"] = part_info["bDesc_zh-CN"]
        if part_info.get("bDesc_zh-TW"):
            line["bDesc_zh-TW"] = part_info["bDesc_zh-TW"]
        if part_info.get("dDesc_en"):
            line["dDesc_en"] = part_info["dDesc_en"]
    return json.dumps(svc.save_sales_order(be_id=be_id, header=header, lines=[line]), ensure_ascii=False)


@mcp.tool()
def create_sales_orders_by_declaration(
    customer_code: str,
    items: str,
    username: str,
    password: str,
    be_code: str,
    be_id: int,
    customer_po: str,
    staff_code: str = "",
    t_date: str = "",
) -> Any:
    """创建销售订单，按产品 udfdeclarationtype 自动分单。

    Trading 产品创建一张订单，其他所有类型（Customs / 空 / 其他值）合并创建另一张订单。

    Args:
        customer_code: 客户代码
        items: JSON 字符串，产品列表，格式:
               '[{"proCode":"PGD798MB","qty":2,"up":100,"unitCode":"PCS","disc":0}, {...}]'
        username: M18 登录用户名
        password: M18 登录密码
        be_code: 业务实体代码
        be_id: 业务实体 ID
        customer_po: 客户采购订单号
        staff_code: 员工代码（可选，不填则从客户主档获取）
        t_date: 交易日期（YYYY-MM-DD，默认当天）
    """
    client = M18Client(username=username, password=password)
    item_list = json.loads(items)

    # 读取每个产品的 DeclarationType，按 Trading / 其他分组
    trading_items: list = []
    other_items: list = []
    for item in item_list:
        pro_code = item["proCode"]
        dt = _get_declaration_type(pro_code, client, be_id)
        if dt == "Trading":
            trading_items.append(item)
        else:
            other_items.append(item)

    # 按组分单创建
    groups: Dict[str, list] = {}
    if trading_items:
        groups["Trading"] = trading_items
    if other_items:
        groups["Others"] = other_items
    so_svc = _auth_svc(M18SalesOrderService, username, password)
    out: Dict[str, Any] = {}
    for dt in list(groups.keys()):
        items_dt = groups[dt]
        if not items_dt:
            continue
        so_lines = [
            {"proCode": i["proCode"], "unitCode": i.get("unitCode", "PCS"),
             "qty": i["qty"], "up": i["up"], "disc": i.get("disc", 0)}
            for i in items_dt
        ]
        extras: Dict[str, Any] = {}
        extras.setdefault("udfapp", _biz_config.get("app_name", ""))
        extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
        if not t_date:
            t_date = date.today().isoformat()
        extras.setdefault("tDate", t_date)
        if customer_po:
            extras["cuspono"] = customer_po
        staff_id = _resolve_staff(customer_code, staff_code, username, password, be_id)
        if staff_id:
            extras["staffId"] = staff_id
        terms = _load_customer_terms(customer_code, username, password, be_id)
        if terms["payTerm"]:
            extras["payTerm"] = terms["payTerm"]
        if terms["tradeTerm"]:
            extras["tradeTerm"] = terms["tradeTerm"]
        # 为每条记录加 refCode/dDesc 等信息
        for so_line in so_lines:
            info = _get_part_info(so_line["proCode"], customer_code, username, password, be_id)
            if info:
                if info.get("refCode"):
                    so_line["refCode"] = info["refCode"]
                if info.get("bDesc_en"):
                    so_line["bDesc_en"] = info["bDesc_en"]
                if info.get("bDesc_zh-CN"):
                    so_line["bDesc_zh-CN"] = info["bDesc_zh-CN"]
                if info.get("bDesc_zh-TW"):
                    so_line["bDesc_zh-TW"] = info["bDesc_zh-TW"]
                if info.get("dDesc_en"):
                    so_line["dDesc_en"] = info["dDesc_en"]

        resp = so_svc.create_draft_from_codes(
            be_code=be_code, be_id=be_id, cus_code=customer_code,
            lines=so_lines, extra_fields=extras,
        )
        out[dt] = {"tranId": resp.get("tranId"), "tranCode": resp.get("tranCode")}

    return json.dumps(out, ensure_ascii=False)


if __name__ == "__main__":
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
