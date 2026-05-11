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
  /customer <customerCode>
  /customer-contacts <customerCode>
  /product <productCode>
  /product-units <productCode>
  /customer-item <customerCode> <productCode>
  /quotation-draft <customerCode> <productCode> <qty> <up> <staffCode>
  /sales-order-draft <customerCode> <productCode> <qty> <up> <staffCode>
  /run <action> <json-params>
  /quit

Examples:
  /customer 320
  /customer-contacts 320
  /customer-item 320 PGD798MB
  /quotation-draft 320 PGD798MB 1 130 000001
  /run product.customer_item_codes {"customerCode":"320","productCode":"PGD798MB"}
  客户 320 的联系人
  客户 320 的 PGD798MB 客户料号
"""


def parse_user_input(text: str) -> Dict[str, Any]:
    raw = text.strip()
    if not raw:
        return {"kind": "empty"}

    if raw in {"/help", "help", "?"}:
        return {"kind": "help"}
    if raw in {"/actions"}:
        return {"kind": "actions"}
    if raw in {"/json on"}:
        return {"kind": "json_mode", "enabled": True}
    if raw in {"/json off"}:
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

    lowered = raw.lower()

    customer_contacts = re.search(r"(客户|customer)\s*([A-Za-z0-9_-]+).*(联系人|contacts?)", raw, re.IGNORECASE)
    if customer_contacts:
        return {
            "kind": "action",
            "action": "customer.contacts",
            "params": {"customerCode": customer_contacts.group(2)},
        }

    customer_item = re.search(
        r"(客户|customer)\s*([A-Za-z0-9_-]+).*(料号|customer part).*(产品|product)?\s*([A-Za-z0-9_-]+)",
        raw,
        re.IGNORECASE,
    )
    if customer_item:
        return {
            "kind": "action",
            "action": "product.customer_item_codes",
            "params": {
                "customerCode": customer_item.group(2),
                "productCode": customer_item.group(4),
            },
        }

    customer_item_alt = re.search(
        r"(客户|customer)\s*([A-Za-z0-9_-]+)\s*的\s*([A-Za-z0-9_-]+)\s*(客户料号|customer part)",
        raw,
        re.IGNORECASE,
    )
    if customer_item_alt:
        return {
            "kind": "action",
            "action": "product.customer_item_codes",
            "params": {
                "customerCode": customer_item_alt.group(2),
                "productCode": customer_item_alt.group(3),
            },
        }

    quotation_draft = re.search(
        r"(报价|quotation).*(客户|customer)\s*([A-Za-z0-9_-]+).*(产品|product)\s*([A-Za-z0-9_-]+).*(数量|qty)\s*(\d+(?:\.\d+)?).*(单价|price|up)\s*(\d+(?:\.\d+)?)",
        raw,
        re.IGNORECASE,
    )
    if quotation_draft:
        return {
            "kind": "action",
            "action": "quotation.create_draft",
            "params": {
                "customerCode": quotation_draft.group(3),
                "lines": [
                    {
                        "proCode": quotation_draft.group(5),
                        "unitCode": "PCS",
                        "qty": float(quotation_draft.group(7)),
                        "up": float(quotation_draft.group(9)),
                        "disc": 0,
                    }
                ],
            },
        }

    if "客户" in raw or "customer" in lowered:
        match = re.search(r"([A-Za-z0-9_-]+)", raw)
        if match:
            return {
                "kind": "action",
                "action": "customer.search",
                "params": {"quickSearchStr": match.group(1)},
            }

    if "产品" in raw or "product" in lowered:
        match = re.search(r"([A-Za-z0-9_-]+)", raw)
        if match:
            return {
                "kind": "action",
                "action": "product.search",
                "params": {"quickSearchStr": match.group(1)},
            }

    raise ValueError("Could not understand input. Use /help to see supported commands.")


def _parse_slash_command(raw: str) -> Dict[str, Any]:
    parts = raw.split()
    command = parts[0]

    if command == "/customer" and len(parts) >= 2:
        return {
            "kind": "action",
            "action": "customer.search",
            "params": {"quickSearchStr": parts[1]},
        }
    if command == "/customer-contacts" and len(parts) >= 2:
        return {
            "kind": "action",
            "action": "customer.contacts",
            "params": {"customerCode": parts[1]},
        }
    if command == "/product" and len(parts) >= 2:
        return {
            "kind": "action",
            "action": "product.search",
            "params": {"quickSearchStr": parts[1]},
        }
    if command == "/product-units" and len(parts) >= 2:
        return {
            "kind": "action",
            "action": "product.units",
            "params": {"productCode": parts[1]},
        }
    if command == "/customer-item" and len(parts) >= 3:
        return {
            "kind": "action",
            "action": "product.customer_item_codes",
            "params": {"customerCode": parts[1], "productCode": parts[2]},
        }
    if command == "/quotation-draft" and len(parts) >= 6:
        return {
            "kind": "action",
            "action": "quotation.create_draft",
            "params": {
                "customerCode": parts[1],
                "staffCode": parts[5],
                "lines": [
                    {
                        "proCode": parts[2],
                        "unitCode": "PCS",
                        "qty": float(parts[3]),
                        "up": float(parts[4]),
                        "disc": 0,
                    }
                ],
            },
        }
    if command == "/sales-order-draft" and len(parts) >= 6:
        return {
            "kind": "action",
            "action": "sales_order.create_draft",
            "params": {
                "customerCode": parts[1],
                "staffCode": parts[5],
                "lines": [
                    {
                        "proCode": parts[2],
                        "unitCode": "PCS",
                        "qty": float(parts[3]),
                        "up": float(parts[4]),
                        "disc": 0,
                    }
                ],
            },
        }

    raise ValueError("Unsupported command. Use /help to see supported commands.")


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
            return f"客户 {data.get('customerId')} 没有找到联系人。"
        lines = [f"找到 {len(contacts)} 个联系人："]
        for row in contacts[:5]:
            name = row.get("man") or row.get("name") or row.get("code") or "(未命名)"
            position = row.get("position") or row.get("dept") or ""
            tel = row.get("tel") or row.get("phone") or ""
            email = row.get("email") or ""
            pieces = [name]
            if position:
                pieces.append(position)
            if tel:
                pieces.append(tel)
            if email:
                pieces.append(email)
            lines.append("- " + " | ".join(pieces))
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
            f"stkUnitId={units.get('stkUnitId')}"
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
        return (
            f"销售报价草稿创建成功: tranId={data.get('tranId')}, "
            f"tranCode={data.get('tranCode')}"
        )

    if action == "quotation.save":
        return f"销售报价保存成功: recordId={data.get('recordId')}"

    if action == "sales_order.create_draft":
        return (
            f"销售订单草稿创建成功: tranId={data.get('tranId')}, "
            f"tranCode={data.get('tranCode')}"
        )

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
