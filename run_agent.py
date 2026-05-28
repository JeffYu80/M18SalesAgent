"""
Interactive terminal helper for MCP-based M18 tools.

This is a lightweight diagnostic runner that exposes raw MCP tools without
requiring an external LLM API key.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict
import sys


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_sales import mcp  # noqa: E402


AGENT_DIR = ROOT_DIR / "agents"
TOOL_REGISTRY: Dict[str, Any] = {}


def load_agent_context(agent_name: str) -> str:
    path = AGENT_DIR / agent_name / "AGENT.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent not found: {agent_name}")
    return path.read_text(encoding="utf-8")


def _register_tools() -> None:
    import asyncio

    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        TOOL_REGISTRY[tool.name] = tool


def list_tools() -> None:
    print("\n可用工具：")
    for name in sorted(TOOL_REGISTRY):
        tool = TOOL_REGISTRY[name]
        desc = tool.description.split("\n")[0] if tool.description else ""
        required = []
        if hasattr(tool, "inputSchema") and "required" in tool.inputSchema:
            required = tool.inputSchema["required"]
        print(f"  {name} ({', '.join(required)})")
        print(f"    {desc}")


def call_tool(tool_name: str, kwargs: Dict[str, Any]) -> str:
    import asyncio

    try:
        result = asyncio.run(mcp.call_tool(tool_name, kwargs))
        if isinstance(result, list) and result:
            content = result[0]
            if hasattr(content, "text"):
                try:
                    parsed = json.loads(content.text)
                    return _format_result(tool_name, parsed)
                except json.JSONDecodeError:
                    return content.text
            return str(content)
        return str(result)
    except Exception as exc:
        return f"调用失败: {type(exc).__name__}: {exc}"


def _format_result(tool_name: str, data: Any) -> str:
    if not isinstance(data, dict):
        return str(data)

    if data.get("ok") is False:
        return f"失败: {data.get('error', '未知错误')}"

    payload = data.get("data", data)

    if tool_name == "customer_search":
        summaries = payload.get("summaries", [])
        if not summaries:
            return "没有找到客户。"
        lines = [f"找到 {len(summaries)} 个客户："]
        for row in summaries[:5]:
            lines.append(f"  {row.get('code')} | {row.get('name')}")
        return "\n".join(lines)

    if tool_name == "customer_contacts":
        contacts = payload.get("contacts", [])
        if not contacts:
            return "没有找到联系人。"
        lines = [f"找到 {len(contacts)} 个联系人："]
        for row in contacts[:5]:
            name = row.get("man") or row.get("name") or row.get("code") or "(未命名)"
            tel = row.get("tel") or row.get("phone") or ""
            email = row.get("email") or ""
            parts = [name]
            if tel:
                parts.append(tel)
            if email:
                parts.append(email)
            lines.append("  " + " | ".join(parts))
        return "\n".join(lines)

    if tool_name == "product_search":
        summaries = payload.get("summaries", [])
        if not summaries:
            return "没有找到产品。"
        lines = [f"找到 {len(summaries)} 个产品："]
        for row in summaries[:5]:
            lines.append(f"  {row.get('code')} | {row.get('name')}")
        return "\n".join(lines)

    if "create_draft" in tool_name:
        if isinstance(payload, dict) and payload.get("status"):
            return f"创建成功: tranId={payload.get('tranId')}, tranCode={payload.get('tranCode')}"
        return f"创建结果: {json.dumps(payload, ensure_ascii=False)}"

    if "save" in tool_name and isinstance(payload, dict):
        if payload.get("status"):
            return f"保存成功: recordId={payload.get('recordId')}"
        return f"保存失败: {payload.get('messages', payload)}"

    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    _register_tools()
    context = load_agent_context("m18-sales-quotation-agent")

    print("=" * 60)
    print("  M18 Sales Agent")
    print("  System Prompt: agents/m18-sales-quotation-agent/AGENT.md")
    print(f"  MCP Tools: {len(TOOL_REGISTRY)} tools available")
    print("=" * 60)
    print()
    print(context.split("## Input Shapes")[0].strip())
    print()
    print("可用命令：")
    print("  /tools")
    print("  /tool <name>")
    print("  /call <tool> <json>")
    print("  /quit")
    print()

    while True:
        try:
            text = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not text:
            continue
        if text in {"/quit", "/exit", "quit", "exit"}:
            print("Bye.")
            break

        if text == "/tools":
            list_tools()
            continue

        if text.startswith("/tool "):
            name = text.split(" ", 1)[1]
            tool = TOOL_REGISTRY.get(name)
            if not tool:
                print(f"未知 tool: {name}")
                continue
            print(f"\n{tool.name}:")
            print(f"  {tool.description}")
            if hasattr(tool, "inputSchema"):
                schema = tool.inputSchema
                for field, props in schema.get("properties", {}).items():
                    req = "required" if field in schema.get("required", []) else "optional"
                    default = props.get("default", "")
                    print(f"  {field}: {props.get('type', '?')} [{req}] (default={default})")
            continue

        if text.startswith("/call "):
            try:
                parts = shlex.split(text)
                if len(parts) < 3:
                    print('用法: /call tool_name {"key":"value"}')
                    continue
                tool_name = parts[1]
                params = json.loads(parts[2])
                print(call_tool(tool_name, params))
            except Exception as exc:
                print(f"解析错误: {exc}")
            continue

        print("这个入口只做工具调试。请使用 /tools 查看可用工具，或 /call 直接调用。")


if __name__ == "__main__":
    main()
