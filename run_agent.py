"""
M18 Sales Agent — 通过 MCP 调用的终端助手

从 AGENT.md 加载角色定义，通过 MCP tool 执行操作。
不需要 LLM API Key，直接交互式对话。
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_server import mcp

# ── 加载 Agent 定义 ──

AGENT_DIR = ROOT_DIR / "agents"

def load_agent_context(agent_name: str) -> str:
    path = AGENT_DIR / agent_name / "AGENT.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent not found: {agent_name}")
    return path.read_text(encoding="utf-8")


# ── 工具注册 ──

TOOL_REGISTRY: Dict[str, Any] = {}

def _register_tools():
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        TOOL_REGISTRY[t.name] = t

_register_tools()


def list_tools() -> None:
    print("\n可用工具：")
    for name in sorted(TOOL_REGISTRY):
        t = TOOL_REGISTRY[name]
        desc = t.description.split("\n")[0] if t.description else ""
        required = []
        if hasattr(t, 'inputSchema') and 'required' in t.inputSchema:
            required = t.inputSchema['required']
        print(f"  {name} ({', '.join(required)})")
        print(f"    {desc}")


def call_tool(tool_name: str, kwargs: Dict[str, Any]) -> str:
    """调用 MCP tool 并返回结果。"""
    import asyncio
    try:
        result = asyncio.run(mcp.call_tool(tool_name, kwargs))
        if isinstance(result, list) and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                data = json.loads(content.text)
                return _format_result(tool_name, data)
            return str(content)
        return str(result)
    except Exception as e:
        return f"❌ 调用失败：{type(e).__name__}: {e}"


def _format_result(tool_name: str, data: Any) -> str:
    if isinstance(data, dict):
        if data.get("ok") is False:
            return f"❌ {data.get('error', '未知错误')}"
        d = data.get("data", data)
        if tool_name == "customer_search":
            summaries = d.get("summaries", [])
            if not summaries:
                return "没有找到客户。"
            lines = [f"找到 {len(summaries)} 个客户："]
            for row in summaries[:5]:
                lines.append(f"  {row.get('code')} | {row.get('name')}")
            return "\n".join(lines)
        if tool_name == "customer_contacts":
            contacts = d.get("contacts", [])
            if not contacts:
                return f"没有找到联系人。"
            lines = [f"找到 {len(contacts)} 个联系人："]
            for row in contacts[:5]:
                name = row.get("man") or row.get("name") or "(未命名)"
                tel = row.get("tel") or row.get("phone") or ""
                email = row.get("email") or ""
                parts = [name]
                if tel: parts.append(tel)
                if email: parts.append(email)
                lines.append(f"  {' | '.join(parts)}")
            return "\n".join(lines)
        if tool_name == "product_search":
            summaries = d.get("summaries", [])
            if not summaries:
                return "没有找到产品。"
            lines = [f"找到 {len(summaries)} 个产品："]
            for row in summaries[:5]:
                lines.append(f"  {row.get('code')} | {row.get('name')}")
            return "\n".join(lines)
        if "create_draft" in tool_name:
            status = d.get("status", d)
            tran_id = d.get("tranId") if isinstance(d, dict) else None
            tran_code = d.get("tranCode") if isinstance(d, dict) else None
            if isinstance(d, dict) and d.get("status"):
                return f"✅ 创建成功：tranId={tran_id}, tranCode={tran_code}"
            return f"结果：{json.dumps(d, ensure_ascii=False)}"
        if "save" in tool_name:
            if isinstance(d, dict):
                rid = d.get("recordId")
                status = d.get("status")
                return f"✅ 保存成功：recordId={rid}" if status else f"保存失败：{d.get('messages', d)}"
        return json.dumps(d, ensure_ascii=False, indent=2)
    return str(data)


# ── 交互主循环 ──

def main() -> None:
    context = load_agent_context("m18-sales-quotation-agent")
    print("=" * 60)
    print("  M18 Sales Agent")
    print("  System Prompt: agents/m18-sales-quotation-agent/AGENT.md")
    print("  MCP Tools: 15 tools available")
    print("=" * 60)
    print()
    print(context.split("## Input Shapes")[0].strip())
    print()
    print("可用命令：")
    print("  /tools           — 列出所有 MCP tool")
    print("  /tool <name>     — 查看 tool 参数")
    print("  /call <tool> <json> — 直接调用 tool")
    print("  自然语言按格式输入即可调用")
    print("  /quit            — 退出")
    print()

    while True:
        try:
            text = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not text:
            continue

        if text in ("/quit", "/exit", "quit", "exit"):
            print("Bye.")
            break

        if text == "/tools":
            list_tools()
            continue

        if text.startswith("/tool "):
            name = text.split(" ", 1)[1]
            t = TOOL_REGISTRY.get(name)
            if not t:
                print(f"未知 tool: {name}")
                continue
            print(f"\n{t.name}:")
            print(f"  {t.description}")
            if hasattr(t, 'inputSchema'):
                schema = t.inputSchema
                for field, props in schema.get("properties", {}).items():
                    req = "required" if field in schema.get("required", []) else "optional"
                    default = props.get("default", "")
                    print(f"  {field}: {props.get('type', '?')} [{req}] (default={default})")
            continue

        if text.startswith("/call "):
            try:
                # /call tool_name {"key":"val"}
                parts = shlex.split(text)
                if len(parts) < 3:
                    print("用法：/call tool_name {\"key\":\"val\"}")
                    continue
                tool_name = parts[1]
                params = json.loads(parts[2]) if len(parts) > 2 else {}
                print(call_tool(tool_name, params))
            except Exception as e:
                print(f"解析错误：{e}")
            continue

        # 自然语言 → 尝试匹配命令
        lowered = text.lower()
        try:
            if text.startswith("/"):
                print("未知命令。用 /tools 查看可用 tool。")
                continue

            # 简化自然语言匹配
            if "报价" in lowered or "quotation" in lowered:
                if "查" in lowered or "搜索" in lowered or "search" in lowered:
                    print(call_tool("quotation_search", {"be_id": 7}))
                    continue
                if "创建" in lowered or "create" in lowered or "下单" in lowered:
                    print("要创建报价，请提供：客户代码、产品代码、数量、单价、员工代码")
                    print("用 /call quotation_create_draft 直接调用")
                    continue

            if "订单" in lowered or "sales_order" in lowered or "order" in lowered:
                if "查" in lowered or "搜索" in lowered or "search" in lowered:
                    print(call_tool("sales_order_search", {"be_id": 7}))
                    continue

            if "客户" in lowered or "customer" in lowered:
                import re
                m = re.search(r"([A-Za-z0-9_-]+)", text)
                if m:
                    code = m.group(1)
                    if "联系人" in lowered or "contact" in lowered:
                        print(call_tool("customer_contacts", {"customer_code": code}))
                    else:
                        print(call_tool("customer_search", {"quick_search": code}))
                    continue

            if "产品" in lowered or "product" in lowered:
                import re
                m = re.search(r"([A-Za-z0-9_-]+)", text)
                if m:
                    print(call_tool("product_search", {"quick_search": m.group(1)}))
                    continue

            print("我没理解你的意思。试试：")
            print("  /tools                  — 查看所有可用工具")
            print('  /call quotation_search  — 搜索报价')
            print('  /call customer_search {"quick_search":"320"}')

        except Exception as e:
            print(f"错误：{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
