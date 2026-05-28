"""
MCP Server for M18 Sales Agent.

Exposes Customer, Product, Sales Quotation, and Sales Order operations
as MCP tools for AI agent consumption.

Usage:
    python mcp_sales.py          # stdio mode
    python mcp_sales.py --sse    # SSE mode (for remote access)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.fastmcp import FastMCP
from m18_api import M18Client
from services.customer_service import M18CustomerService
from services.product_service import M18ProductService
from services.quotation_service import M18QuotationService
from services.sales_order_service import M18SalesOrderService
from services.business_config import load_business_config

# 加载业务实体映射（支持按环境切换）
_biz_config = load_business_config()
BE_MAPPING: Dict[str, int] = _biz_config.get("be_mapping", {})

mcp = FastMCP("M18 ERP", instructions="""
M18 ERP integration server. Use these tools to search, load, and create
sales quotations, sales orders, customers, and products in the Multiable M18 ERP system.

All operations require `username`, `password`, and `be_id` (business entity / company).
Password is plain text (converted to SHA1 automatically).

字段说明（重要）：
- remarks = 备注（独立字段，不要把其他字段内容放进去）
- l_time = 交货期（纯文字说明，不是日期）
- d_date = 去货日期（YYYY-MM-DD 格式）
""")


def _auth_svc(service_cls, username: str, password: str):
    """Create an authenticated service instance with per-transaction credentials."""
    return service_cls(client=M18Client(username=username, password=password))


def _resolve_contact(cus_code: str, contact_name: str, username: str, password: str, be_id: int) -> int:
    """Look up a contact by name (man field) for a customer. Returns the contact ID (manId)."""
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


def _load_customer_staff_id(cus_code: str, username: str, password: str, be_id: int) -> int:
    """从客户主数据获取 staffId (cus[0].staffId)."""
    svc = _auth_svc(M18CustomerService, username, password)
    customer_id = svc.resolver.resolve_customer_code(cus_code, be_id)
    payload = svc.load_customer(customer_id)
    rows = payload.get("data", {}).get("cus", [])
    if rows:
        sid = rows[0].get("staffId", 0)
        return int(sid) if sid else 0
    return 0


def _resolve_staff(cus_code: str, staff_code: str, username: str, password: str, be_id: int) -> int:
    """解析 staffCode → staffId，如果没传 staffCode 则从客户主档获取。"""
    if staff_code:
        from services.reference_resolver import M18ReferenceResolver
        return M18ReferenceResolver(client=M18Client(username=username, password=password)).resolve_staff_code(staff_code, be_id)
    return _load_customer_staff_id(cus_code, username, password, be_id)


def _load_customer_terms(cus_code: str, username: str, password: str, be_id: int):
    """从客户主数据中获取贸易条款和付款条款 (remcus)."""
    svc = _auth_svc(M18CustomerService, username, password)
    payload = svc.load_customer(svc.resolver.resolve_customer_code(cus_code, be_id))
    rows = payload.get("data", {}).get("remcus", [])
    result = {"payTerm": "", "tradeTerm": ""}
    if rows:
        r = rows[0]
        result["payTerm"] = r.get("payTerm_en") or r.get("payTerm") or ""
        result["tradeTerm"] = r.get("tradeTerm_en") or r.get("tradeTerm") or ""
    return result


# ── Business Entity ──

@mcp.tool()
def business_entity_lookup(be_code: str) -> str:
    """查找业务实体 be_code 对应的 be_id（从本地配置读取）。

    Args:
        be_code: 业务实体代码，如 "PUS", "SHK"
    """
    be_id = BE_MAPPING.get(be_code.upper())
    if be_id:
        return json.dumps({"be_code": be_code.upper(), "be_id": be_id}, ensure_ascii=False)
    candidates = {k: v for k, v in BE_MAPPING.items() if be_code.upper() in k}
    if candidates:
        return json.dumps({"be_code": be_code, "candidates": candidates}, ensure_ascii=False)
    return json.dumps({"be_code": be_code, "error": "未找到该业务实体，请在 config/m18_business.yaml 的 be_mapping 中添加"}, ensure_ascii=False)


# ── Customer ──

@mcp.tool()
def customer_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None) -> str:
    """Search customers by code or name."""
    svc = _auth_svc(M18CustomerService, username, password)
    return json.dumps(svc.search_customers(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def customer_load(customer_id: int, username: str, password: str) -> str:
    """Load full customer master data by ID."""
    svc = _auth_svc(M18CustomerService, username, password)
    return json.dumps(svc.load_customer(customer_id), ensure_ascii=False)


@mcp.tool()
@mcp.tool()
def customer_search_by_name(customer_name: str, username: str, password: str, be_id: Optional[int] = None) -> str:
    """根据客户名称模糊搜索，跨实体查找客户代码和ID。

    使用 EBI 客户列表报表搜索，支持模糊匹配。
    如果指定 be_id 则只搜该实体，不指定则搜所有实体。

    Args:
        customer_name: 客户名称（支持模糊搜索）
        username: M18 登录用户名
        password: M18 登录密码
        be_id: 业务实体 ID（可选，不填则搜索所有实体）
    """
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_list_report_id", 103)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    if not rows:
        return json.dumps({"error": "未找到客户数据"}, ensure_ascii=False)

    needle = customer_name.strip().lower()
    matches = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = (r.get("MAIN_A_desc__lang") or "").strip().lower()
        code = (r.get("MAIN_A_code") or "").strip().lower()
        if needle in name or needle in code:
            matches.append({
                "customerCode": r.get("MAIN_A_code", ""),
                "customerName": r.get("MAIN_A_desc__lang", ""),
                "customerId": r.get("MAIN_A_id", ""),
                "beId": r.get("MAIN_A_beId", ""),
                "beCode": r.get("MAIN_A_beId_code", ""),
            })

    matches.sort(key=lambda x: (x.get("beCode", ""), x.get("customerCode", "")))
    return json.dumps({"matches": matches, "count": len(matches)}, ensure_ascii=False)


@mcp.tool()
def customer_list_all(username: str, password: str, be_id: Optional[int] = None) -> str:
    """返回 EBI 客户列表报表的全部数据，包含所有实体的客户信息。

    数据量约 500 行，包含客户代码、名称、ID、所属实体等信息。
    可根据 be_id 筛选指定实体。

    Args:
        username: M18 登录用户名
        password: M18 登录密码
        be_id: 业务实体 ID（可选，不填则返回所有实体）
    """
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_list_report_id", 103)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False)


@mcp.tool()
def customer_part_list_all(username: str, password: str, be_id: int = 7) -> str:
    """返回 EBI 客户料号报表的全部数据。

    包含所有客户的产品代码与客户料号映射关系。

    Args:
        username: M18 登录用户名
        password: M18 登录密码
        be_id: 业务实体 ID
    """
    client = M18Client(username=username, password=password)
    report_id = _biz_config.get("customer_part_report_id", 102)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False)


@mcp.tool()
def customer_part_lookup(customer_code: str, part_code: str, be_id: int, username: str, password: str) -> str:
    """根据客户料号查找对应的内部产品代码。

    Args:
        customer_code: 客户代码（如 "320"）
        part_code: 客户料号（customer part number），如 "ABC798"
        be_id: 业务实体 ID
        username: M18 登录用户名
        password: M18 登录密码
    """
    client = M18Client(username=username, password=password)
    from services.product_service import M18ProductService
    svc = M18ProductService(client=client)
    report_id = _biz_config.get("customer_part_report_id", 102)
    report = client.get_ebi_report(report_id, be_id=be_id)
    rows = report.get("rows", report.get("values", []))
    if not rows:
        return json.dumps({"error": "未找到客户料号数据"}, ensure_ascii=False)
    rows = [r for r in rows if isinstance(r, dict)]
    # 按客户代码 + 料号过滤
    needle_cus = customer_code.strip().lower()
    needle_part = part_code.strip().lower()
    matched = []
    for r in rows:
        vals = {k.lower(): str(v).lower() for k, v in r.items() if v is not None}
        if needle_cus in str(vals) and needle_part in str(vals):
            matched.append({
                "customerCode": r.get("CUS_A_code", ""),
                "customerName": r.get("CUS_A_desc__lang", ""),
                "productCode": r.get("PRO_A_code", ""),
                "productName": r.get("PRO_A_desc__lang", ""),
                "customerPartCode": r.get("F_A_refCode", ""),
            })
    return json.dumps({"matches": matched, "count": len(matched)}, ensure_ascii=False)


@mcp.tool()
def customer_contacts(customer_code: str, be_id: int, username: str, password: str) -> str:
    """Get contact persons for a customer."""
    svc = _auth_svc(M18CustomerService, username, password)
    return json.dumps(svc.get_customer_contacts(customer_code=customer_code, be_id=be_id), ensure_ascii=False)


# ── Product ──

@mcp.tool()
def product_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None) -> str:
    """Search products by code or name."""
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.search_products(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def product_load(product_id: int, username: str, password: str) -> str:
    """Load full product master data by ID."""
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.load_product(product_id), ensure_ascii=False)


@mcp.tool()
def product_units(product_code: str, be_id: int, username: str, password: str) -> str:
    """Get unit information for a product."""
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.get_product_units(product_code=product_code, be_id=be_id), ensure_ascii=False)


@mcp.tool()
def product_customer_item_codes(customer_code: str, product_code: str, be_id: int, username: str, password: str) -> str:
    """Look up customer-specific part/item codes for a product."""
    svc = _auth_svc(M18ProductService, username, password)
    return json.dumps(svc.query_customer_item_codes(customer_code=customer_code, product_code=product_code, be_id=be_id), ensure_ascii=False)


# ── Sales Quotation ──

@mcp.tool()
def quotation_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None) -> str:
    """Search sales quotations."""
    svc = _auth_svc(M18QuotationService, username, password)
    return json.dumps(svc.search_quotations(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def quotation_load(record_id: int, username: str, password: str) -> str:
    """Load a sales quotation by record ID."""
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
) -> str:
    """Create a sales quotation draft using auto-completion.

    Args:
        customer_code: Customer business code (e.g. "320")
        product_code: Product business code (e.g. "PGD798MB")
        qty: Quantity
        up: Unit price
        staff_code: Staff code (可选，不填则从客户主档获取)
        username: M18 login username for authentication
        password: M18 login password (plain text, converted to SHA1 automatically)
        be_code: Business entity code (e.g. "PUS") — which company to create for
        be_id: Business entity ID (for staff resolution)
        unit_code: Unit code (default "PCS")
        disc: Discount percentage
        contact_name: Contact person name (resolved from customer's contact list)
        customer_po: Customer purchase order number (必填，报价单存入 udfcmpo)
        t_date: Transaction date (YYYY-MM-DD, 默认当天)
        d_date: 去货日期 (可选，如 "2026-06-15")
        packing: 包装说明 (可选)
        l_time: 交货期 (可选，如 "30 days"，纯文字说明，不是日期)
        remarks: 备注 (可选)
        extra_fields: Additional fields as JSON string. See SKILL.md Field Reference.
    """
    q_svc = _auth_svc(M18QuotationService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
    extras.setdefault("descOrigin", "CUSREF")
    sid = _resolve_staff(customer_code, staff_code, username, password, be_id)
    if sid:
        extras["staffId"] = sid
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
        ctc = _resolve_contact(customer_code, contact_name, username, password, be_id)
        if ctc:
            extras["manId"] = ctc
    if customer_po:
        extras["udfcmpo"] = customer_po
    # 贸易条款 + 银行备注
    terms = _load_customer_terms(customer_code, username, password, be_id)
    if terms["payTerm"]:
        extras.setdefault("payTerm", terms["payTerm"])
    if terms["tradeTerm"]:
        extras.setdefault("tradeTerm", terms["tradeTerm"])
    if remarks:
        extras.setdefault("remarks", remarks)
    return json.dumps(q_svc.create_draft_from_codes(
        be_code=be_code,
        be_id=be_id,
        cus_code=customer_code,
        lines=[{"proCode": product_code, "unitCode": unit_code, "qty": qty, "up": up, "disc": disc}],
        extra_fields=extras,
    ), ensure_ascii=False)


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
) -> str:
    """Save a sales quotation using standard save (resolves codes to IDs).

    Args:
        cus_code: Customer business code
        product_code: Product business code
        qty: Quantity
        up: Unit price
        username: M18 login username
        password: M18 login password (plain text, converted to SHA1 automatically)
        customer_po: Customer purchase order number (必填，报价单存入 udfcmpo)
        be_id: Business entity ID
        staff_code: Staff code (可选，不填则从客户主档获取)
        t_date: Transaction date (YYYY-MM-DD, 默认当天)
        d_date: 去货日期 (可选，如 "2026-06-15")
        packing: 包装说明 (可选)
        l_time: 交货期 (可选，如 "30 days"，纯文字说明，不是日期)
        remarks: 备注 (可选)
        cur_id: Currency ID
        flow_type_id: Flow type ID
        unit_code: Unit code
        disc: Discount percentage
        contact_name: Contact person name (resolved from customer's contact list)
        extra_fields: Additional fields as JSON string. See SKILL.md Field Reference.
    """
    q_svc = _auth_svc(M18QuotationService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
    extras.setdefault("descOrigin", "CUSREF")
    if not t_date:
        t_date = date.today().isoformat()
    if d_date:
        extras.setdefault("dDate", d_date)
    if packing:
        extras.setdefault("packing", packing)
    if l_time:
        extras.setdefault("lTime", l_time)
    if contact_name:
        ctc = _resolve_contact(cus_code, contact_name, username, password, be_id)
        if ctc:
            extras["manId"] = ctc
    if customer_po:
        extras["udfcmpo"] = customer_po
    # 贸易条款 + 银行备注
    terms = _load_customer_terms(cus_code, username, password, be_id)
    if terms["payTerm"]:
        extras.setdefault("payTerm", terms["payTerm"])
    if terms["tradeTerm"]:
        extras.setdefault("tradeTerm", terms["tradeTerm"])
    sid = _resolve_staff(cus_code, staff_code, username, password, be_id)
    if sid:
        extras["staffId"] = sid
    remark_values = [{"remarks": remarks}] if remarks else None
    amt = qty * up
    header = {
        "cusCode": cus_code, "curId": cur_id, "flowTypeId": flow_type_id,
        "tDate": t_date, "rate": 1, "amt": amt,
        **extras,
    }
    line = {
        "proCode": product_code, "unitCode": unit_code,
        "qty": qty, "up": up, "disc": disc, "amt": amt,
        **extras,
    }
    return json.dumps(q_svc.save_quotation(
        be_id=be_id, header=header, lines=[line], remark_values=remark_values,
    ), ensure_ascii=False)


# ── Sales Order ──

@mcp.tool()
def sales_order_search(be_id: int, username: str, password: str, quick_search: Optional[str] = None) -> str:
    """Search sales orders."""
    svc = _auth_svc(M18SalesOrderService, username, password)
    return json.dumps(svc.search_sales_orders(be_id=be_id, quick_search=quick_search), ensure_ascii=False)


@mcp.tool()
def sales_order_load(record_id: int, username: str, password: str) -> str:
    """Load a sales order by record ID."""
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
) -> str:
    """Create a sales order draft using auto-completion.

    Args:
        customer_code: Customer business code
        product_code: Product business code
        qty: Quantity
        up: Unit price
        staff_code: Staff code (e.g. "000001")
        username: M18 login username
        password: M18 login password (plain text, converted to SHA1 automatically)
        be_code: Business entity code (e.g. "PUS") — which company to create for
        be_id: Business entity ID
        customer_po: Customer purchase order number (必填，销售订单存入 cuspono)
        unit_code: Unit code
        disc: Discount percentage
        contact_name: Contact person name (resolved from customer's contact list)
        t_date: Transaction date (YYYY-MM-DD, 默认当天)
        d_date: Delivery date / 去货日 (可选)
        cus_ddate: Customer required delivery date / 客户要求到货日期 (可选)
        extra_fields: Additional fields as JSON string. See SKILL.md Field Reference.
    """
    so_svc = _auth_svc(M18SalesOrderService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
    extras.setdefault("descOrigin", "CUSREF")
    sid = _resolve_staff(customer_code, staff_code, username, password, be_id)
    if sid:
        extras["staffId"] = sid
    if not t_date:
        t_date = date.today().isoformat()
    extras.setdefault("tDate", t_date)
    if d_date:
        extras["dDate"] = d_date
    if cus_ddate:
        extras["cusDDate"] = cus_ddate
    if contact_name:
        ctc = _resolve_contact(customer_code, contact_name, username, password, be_id)
        if ctc:
            extras["manId"] = ctc
    if customer_po:
        extras["cuspono"] = customer_po
    return json.dumps(so_svc.create_draft_from_codes(
        be_code=be_code,
        be_id=be_id,
        cus_code=customer_code,
        lines=[{"proCode": product_code, "unitCode": unit_code, "qty": qty, "up": up, "disc": disc}],
        extra_fields=extras,
    ), ensure_ascii=False)


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
) -> str:
    """Save a sales order using standard save (resolves codes to IDs).

    Args:
        cus_code: Customer business code
        product_code: Product business code
        qty: Quantity
        up: Unit price
        username: M18 login username
        password: M18 login password (plain text, converted to SHA1 automatically)
        customer_po: Customer purchase order number (必填，销售订单存入 cuspono)
        be_id: Business entity ID
        staff_code: Staff code (可选，不填则从客户主档获取)
        t_date: Transaction date (YYYY-MM-DD, 默认当天)
        d_date: Delivery date / 去货日 (可选)
        cus_ddate: Customer required delivery date / 客户要求到货日期 (可选)
        cur_id: Currency ID
        flow_type_id: Flow type ID
        unit_code: Unit code
        disc: Discount percentage
        contact_name: Contact person name (resolved from customer's contact list)
        extra_fields: Additional fields as JSON string. See SKILL.md Field Reference.
    """
    so_svc = _auth_svc(M18SalesOrderService, username, password)
    extras = json.loads(extra_fields) if extra_fields else {}
    extras.setdefault("udfapp", _biz_config.get("app_name", ""))
    extras.setdefault("udfappversion", _biz_config.get("app_version", ""))
    extras.setdefault("descOrigin", "CUSREF")
    if not t_date:
        t_date = date.today().isoformat()
    sid = _resolve_staff(cus_code, staff_code, username, password, be_id)
    if sid:
        extras["staffId"] = sid
    if contact_name:
        ctc = _resolve_contact(cus_code, contact_name, username, password, be_id)
        if ctc:
            extras["manId"] = ctc
    if customer_po:
        extras["cuspono"] = customer_po
    if d_date:
        extras["dDate"] = d_date
    if cus_ddate:
        extras["cusDDate"] = cus_ddate
    amt = qty * up
    header = {
        "cusCode": cus_code, "curId": cur_id, "flowTypeId": flow_type_id,
        "tDate": t_date, "rate": 1, "amt": amt,
        **extras,
    }
    line = {
        "proCode": product_code, "unitCode": unit_code,
        "qty": qty, "up": up, "disc": disc, "amt": amt,
        **extras,
    }
    return json.dumps(so_svc.save_sales_order(
        be_id=be_id, header=header, lines=[line],
    ), ensure_ascii=False)


# ── Main ──

if __name__ == "__main__":
    mode = "--sse" in sys.argv
    if mode:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
