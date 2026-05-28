"""
LLM-driven M18 terminal agent.

Natural language input is translated into MCP tool calls through an OpenAI-
compatible chat completion API.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List
import sys


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai import OpenAI  # noqa: E402
from mcp_sales import mcp  # noqa: E402


def _load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.strip().split("=", 1)
        os.environ.setdefault(key, value)


_load_dotenv()

API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL") or os.environ.get("OPENAI_MODEL", "deepseek-v4-flash")


def _require_api_key() -> None:
    if API_KEY:
        return
    print("错误：请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。")
    print("也可以在项目根目录放置 .env 文件，例如：")
    print("  DEEPSEEK_API_KEY=sk-your-key")
    print("  DEEPSEEK_BASE_URL=https://api.deepseek.com")
    print("  DEEPSEEK_MODEL=deepseek-v4-flash")
    sys.exit(1)


def load_context() -> str:
    parts: List[str] = []
    for path in [
        ROOT_DIR / "agents" / "m18-sales-quotation-agent" / "AGENT.md",
        ROOT_DIR / "skills" / "M18SalesQuotation" / "SKILL.md",
        ROOT_DIR / "skills" / "M18SalesOrder" / "SKILL.md",
    ]:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


TOOLS: List[Dict[str, Any]] = []


def _build_openai_tools() -> None:
    global TOOLS
    mcp_tools = asyncio.run(mcp.list_tools())
    TOOLS = []
    for tool in mcp_tools:
        schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}
        TOOLS.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": (tool.description or "").split("\n\n")[0][:200],
                    "parameters": schema,
                },
            }
        )


_build_openai_tools()


def call_mcp_tool(name: str, args: Dict[str, Any]) -> str:
    try:
        result = asyncio.run(mcp.call_tool(name, args))
        content_list = result[0] if isinstance(result, tuple) and result else result
        if isinstance(content_list, list):
            texts = []
            for item in content_list:
                if hasattr(item, "text"):
                    texts.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
            if texts:
                return texts[0]
        return str(result)
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)


SYSTEM_PROMPT = f"""你是 M18 ERP 销售助手。你通过 MCP tool 操作 M18 系统。
以下是你的角色定义和业务规则：
{load_context()}

行为准则：
1. 分析用户的自然语言需求。
2. 选择合适的 MCP tool 来执行。
3. 调用 tool 后，将结果用简洁中文总结给用户。
4. 如果缺少必要参数，要主动追问用户。
5. 不使用 emoji。
"""


def _format_tool_result(tool_name: str, raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if not isinstance(data, dict):
        return raw

    if data.get("ok") is False:
        return "操作失败: " + str(data.get("error", "未知错误"))

    inner = data.get("data", data)
    if "create_draft" in tool_name:
        if isinstance(inner, dict) and inner.get("status") is True:
            parts = []
            if inner.get("tranCode"):
                parts.append("单据编号: " + str(inner["tranCode"]))
            if inner.get("tranId"):
                parts.append("tranId=" + str(inner["tranId"]))
            return "创建成功，" + "，".join(parts) if parts else "创建成功。"
        return "创建结果: " + json.dumps(inner, ensure_ascii=False)

    if "save" in tool_name and isinstance(inner, dict):
        if inner.get("status") is True:
            return "保存成功，recordId=" + str(inner.get("recordId"))
        messages = inner.get("messages", [])
        if messages:
            return "保存失败: " + str(messages[0].get("msgDetail", messages[0]))
        return "保存失败: " + json.dumps(inner, ensure_ascii=False)

    return raw


def main() -> None:
    _require_api_key()
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("=" * 60)
    print(f"  M18 LLM Agent ({MODEL} @ {BASE_URL})")
    print("  输入自然语言，程序会自动调用 MCP tool")
    print("  输入 /quit 退出")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input in {"/quit", "/exit", "quit", "exit"}:
            print("Bye.")
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            clean_msgs = []
            for message in messages:
                clean = dict(message)
                clean.pop("reasoning_content", None)
                clean_msgs.append(clean)

            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=clean_msgs,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=2000,
                    extra_body={"thinking": {"type": "disabled"}},
                )
            except Exception as exc:
                print(f"LLM 调用失败: {exc}")
                break

            choice = response.choices[0]
            message = choice.message

            if not message.tool_calls:
                print(f"\n{message.content}")
                messages.append({"role": "assistant", "content": message.content})
                break

            assistant_msg = {"role": "assistant", "content": message.content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]
            messages.append(assistant_msg)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                print(f"\n  -> 调用 {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")
                raw_result = call_mcp_tool(tool_name, tool_args)
                print(f"  -> {_format_tool_result(tool_name, raw_result)}")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": raw_result,
                    }
                )


if __name__ == "__main__":
    main()
