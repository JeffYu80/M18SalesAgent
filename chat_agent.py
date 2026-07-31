"""
Simple terminal chat entrypoint for current M18 actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import re
import sys


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from m18_ops_agent import M18OpsAgent  # noqa: E402


HELP_TEXT = """Commands:
  /help
  /actions
  /json on
  /json off
  /customer <beId> <customerCode>
  /customer-contacts <beId> <customerCode>
  /product <beId> <productCode>
  /product-units <beId> <productCode>
  /customer-item <beId> <customerCode> <productCode>
  /quotation-draft <beId> <beCode> <customerCode> <productCode> <qty> <up> <staffCode> [currency=USD] [tDate=YYYY-MM-DD]
  /sales-order-draft <beId> <beCode> <customerCode> <productCode> <qty> <up> <staffCode> [currency=USD] [tDate=YYYY-MM-DD]
  /run <action> <json-params>
  /quit

Examples:
  /customer 7 320
  /customer-contacts 7 320
  /customer-item 7 320 PGD798MB
  /quotation-draft 7 PUS 320 PGD798MB 1 130 000001
  /quotation-draft 7 PUS 320 PGD798MB 1 130 000001 tDate=2026-07-31
  /quotation-draft 7 PUS 320 PGD798MB 1 130 000001 USD 2026-07-31
  /sales-order-draft 7 PUS 320 PGD798MB 1 130 000001 USD 2026-07-31
  /run product.customer_item_codes {"beId":7,"customerCode":"320","productCode":"PGD798MB"}
  beId=7 客户 320 的联系人
  beId=7 客户 320 的 PGD798MB 客户料号
"""


def parse_user_input(text: str) -> Dict[str, Any]:
    raw = text.strip()
    if not raw:
        return {"kind": "empty"}

    if raw in {"/help", "help", "?"}:
        return {"kind": "help"}
    if raw == "/actions":
        return {"kind": "actions"}
    if raw == "/json on":
        return {"kind": "json_mode", "enabled": True}
    if raw == "/json off":
        return {"kind": "json_mode", "enabled": False}
    if raw in {"/quit", "/exit", "quit", "exit"}:
        return {"kind": "quit"}

    if raw.startswith("/run "):
        parts = raw.split(" ", 2)
        if len(parts) < 3:
            raise ValueError("Usage: /run <action> <json-params>")
        return {
            "kind": "action",
            "action": parts[1],
            "params": json.loads(parts[2]),
        }

    if raw.startswith("/"):
        return _parse_slash_command(raw)

    return _parse_natural_language(raw)


def _parse_slash_command(raw: str) -> Dict[str, Any]:
    parts = raw.split()
    command = parts[0]

    if command == "/customer" and len(parts) >= 3:
        return {
            "kind": "action",
            "action": "customer.search",
            "params": {"beId": int(parts[1]), "quickSearchStr": parts[2]},
        }
    if command == "/customer-contacts" and len(parts) >= 3:
        return {
            "kind": "action",
            "action": "customer.contacts",
            "params": {"beId": int(parts[1]), "customerCode": parts[2]},
        }
    if command == "/product" and len(parts) >= 3:
        return {
            "kind": "action",
            "action": "product.search",
            "params": {"beId": int(parts[1]), "quickSearchStr": parts[2]},
        }
    if command == "/product-units" and len(parts) >= 3:
        return {
            "kind": "action",
            "action": "product.units",
            "params": {"beId": int(parts[1]), "productCode": parts[2]},
        }
    if command == "/customer-item" and len(parts) >= 4:
        return {
            "kind": "action",
            "action": "product.customer_item_codes",
            "params": {"beId": int(parts[1]), "customerCode": parts[2], "productCode": parts[3]},
        }
    if command == "/quotation-draft" and len(parts) >= 8:
        extra_fields = _parse_draft_options(parts[8:])
        return {
            "kind": "action",
            "action": "quotation.create_draft",
            "params": {
                "beId": int(parts[1]),
                "beCode": parts[2],
                "customerCode": parts[3],
                "staffCode": parts[7],
                "extraFields": extra_fields,
                "lines": [
                    {
                        "proCode": parts[4],
                        "qty": float(parts[5]),
                        "up": float(parts[6]),
                        "disc": 0,
                    }
                ],
            },
        }
    if command == "/sales-order-draft" and len(parts) >= 8:
        extra_fields = _parse_draft_options(parts[8:])
        return {
            "kind": "action",
            "action": "sales_order.create_draft",
            "params": {
                "beId": int(parts[1]),
                "beCode": parts[2],
                "customerCode": parts[3],
                "staffCode": parts[7],
                "extraFields": extra_fields,
                "lines": [
                    {
                        "proCode": parts[4],
                        "qty": float(parts[5]),
                        "up": float(parts[6]),
                        "disc": 0,
                    }
                ],
            },
        }

    raise ValueError("Unsupported command. Use /help to see supported commands.")


def _parse_draft_options(options: list[str]) -> Dict[str, str]:
    """Parse optional named draft fields without requiring a currency first."""
    extra_fields: Dict[str, str] = {}
    for option in options:
        if option == "-":
            continue
        if "=" in option:
            key, value = option.split("=", 1)
            normalized_key = {"currency": "currency", "tDate": "tDate", "t_date": "tDate"}.get(key)
            if normalized_key and value:
                extra_fields[normalized_key] = value
                continue
            raise ValueError(f"Unsupported draft option: {option}")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", option):
            extra_fields["tDate"] = option
        elif "currency" not in extra_fields:
            extra_fields["currency"] = option
        else:
            raise ValueError(f"Unsupported draft option: {option}")
    return extra_fields


def _extract_be_id(raw: str) -> int:
    match = re.search(r"be[_ ]?id\s*[:=]\s*(\d+)", raw, re.IGNORECASE)
    if not match:
        raise ValueError("Natural-language input must include beId, for example: beId=7 客户 320 的联系人")
    return int(match.group(1))


def _parse_natural_language(raw: str) -> Dict[str, Any]:
    be_id = _extract_be_id(raw)
    customer_code_match = re.search(r"(?:客户|customer)\s*([A-Za-z0-9_-]+)", raw, re.IGNORECASE)
    product_code_match = re.search(r"(?:产品|product)\s*([A-Za-z0-9_-]+)", raw, re.IGNORECASE)
    customer_item_match = re.search(
        r"(?:客户|customer)\s*([A-Za-z0-9_-]+)\s*的\s*([A-Za-z0-9_-]+)\s*(?:客户料号|customer part)",
        raw,
        re.IGNORECASE,
    )

    if customer_code_match and ("联系人" in raw or re.search(r"\bcontacts?\b", raw, re.IGNORECASE)):
        return {
            "kind": "action",
            "action": "customer.contacts",
            "params": {"beId": be_id, "customerCode": customer_code_match.group(1)},
        }

    if customer_item_match:
        return {
            "kind": "action",
            "action": "product.customer_item_codes",
            "params": {
                "beId": be_id,
                "customerCode": customer_item_match.group(1),
                "productCode": customer_item_match.group(2),
            },
        }

    if customer_code_match:
        return {
            "kind": "action",
            "action": "customer.search",
            "params": {"beId": be_id, "quickSearchStr": customer_code_match.group(1)},
        }

    if product_code_match and ("产品" in raw or re.search(r"\bproduct\b", raw, re.IGNORECASE)):
        return {
            "kind": "action",
            "action": "product.search",
            "params": {"beId": be_id, "quickSearchStr": product_code_match.group(1)},
        }

    raise ValueError("Could not understand input. Use /help to see supported commands.")


def format_result(result: Dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"失败: {error.get('type', 'Error')} - {error.get('message', 'Unknown error')}"

    action = result.get("action")
    data = result.get("data", {})

    if action == "customer.search":
        summaries = data.get("summaries", [])
        if not summaries:
            return "没有找到客户。"
        lines = [f"找到 {len(summaries)} 个客户："]
        for row in summaries[:5]:
            lines.append(f"- {row.get('code')} | {row.get('name')}")
        return "\n".join(lines)

    if action == "customer.contacts":
        contacts = data.get("contacts", [])
        if not contacts:
            return "没有找到联系人。"
        lines = [f"找到 {len(contacts)} 个联系人："]
        for row in contacts[:5]:
            name = row.get("man") or row.get("name") or row.get("code") or "(未命名)"
            position = row.get("position") or row.get("dept") or ""
            tel = row.get("tel") or row.get("phone") or ""
            email = row.get("email") or ""
            parts = [name]
            if position:
                parts.append(position)
            if tel:
                parts.append(tel)
            if email:
                parts.append(email)
            lines.append("- " + " | ".join(parts))
        return "\n".join(lines)

    if action == "product.search":
        summaries = data.get("summaries", [])
        if not summaries:
            return "没有找到产品。"
        lines = [f"找到 {len(summaries)} 个产品："]
        for row in summaries[:5]:
            lines.append(f"- {row.get('code')} | {row.get('name')}")
        return "\n".join(lines)

    if action == "product.units":
        units = data.get("units", {})
        return (
            f"产品 {data.get('productCode')} 的单位信息："
            f" unitId={units.get('unitId')}, saleUnitId={units.get('saleUnitId')}, "
            f"stkUnitId={units.get('stkUnitId')}, "
            f"defaultSalesPriceId={units.get('defaultSalesPriceId')}（标准报价/订单行 unitId）"
        )

    if action == "product.customer_item_codes":
        matches = data.get("customerPartMatches", [])
        customer = data.get("customer", {})
        product = data.get("product", {})
        if not matches:
            return f"客户 {customer.get('code')} 的产品 {product.get('code')} 没有找到客户料号。"
        lines = [
            f"客户 {customer.get('code')} ({customer.get('name')}) 的产品 "
            f"{product.get('code')} ({product.get('name')}) 找到 {len(matches)} 条客户料号："
        ]
        for row in matches[:5]:
            lines.append(
                f"- 客户料号: {row.get('customerPartCode')} | "
                f"客户: {row.get('customerCode')} | 产品: {row.get('productCode')}"
            )
        return "\n".join(lines)

    if action == "quotation.create_draft":
        return f"销售报价草稿创建成功: tranId={data.get('tranId')}, tranCode={data.get('tranCode')}"

    if action == "quotation.save":
        return f"销售报价保存成功: recordId={data.get('recordId')}"

    if action == "sales_order.create_draft":
        return f"销售订单草稿创建成功: tranId={data.get('tranId')}, tranCode={data.get('tranCode')}"

    if action == "sales_order.save":
        return f"销售订单保存成功: recordId={data.get('recordId')}"

    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def main() -> None:
    agent = M18OpsAgent()
    json_mode = False
    print("M18 Chat Agent")
    print(HELP_TEXT)

    while True:
        try:
            text = input("\nYou> ").strip()
            parsed = parse_user_input(text)
        except KeyboardInterrupt:
            print("\nBye.")
            break
        except Exception as exc:
            print(f"Error: {exc}")
            continue

        if parsed["kind"] == "empty":
            continue
        if parsed["kind"] == "help":
            print(HELP_TEXT)
            continue
        if parsed["kind"] == "actions":
            print(json.dumps(agent.supported_actions(), ensure_ascii=False, indent=2))
            continue
        if parsed["kind"] == "json_mode":
            json_mode = parsed["enabled"]
            print(f"JSON mode {'on' if json_mode else 'off'}.")
            continue
        if parsed["kind"] == "quit":
            print("Bye.")
            break

        result = agent.handle(parsed["action"], parsed.get("params"))
        print(format_result(result))
        if json_mode:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
