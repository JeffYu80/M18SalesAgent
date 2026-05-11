"""
M18 LLM Agent — 自然语言 → 自动调 MCP tool

用法：
  1. 设置环境变量 OPENAI_API_KEY（或 .env 文件）
  2. python llm_agent.py

支持任何 OpenAI 兼容 API（可设置 OPENAI_BASE_URL）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai import OpenAI
from mcp_server import mcp

# ── 配置 ──

# 优先从 .env 加载
env_path = ROOT_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL") or os.environ.get("OPENAI_MODEL", "deepseek-v4-flash")

if not API_KEY:
    print("错误：请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量")
    print("或在项目目录创建 .env 文件：")
    print('  DEEPSEEK_API_KEY=sk-your-key')
    print('  DEEPSEEK_BASE_URL=https://api.deepseek.com/v1  (可选)')
    print('  DEEPSEEK_MODEL=deepseek-v4  (可选)')
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ── 加载 Agent 定义 ──

def load_context() -> str:
    parts = []
    # AGENT.md
    agent_path = ROOT_DIR / "agents" / "m18-sales-quotation-agent" / "AGENT.md"
    if agent_path.exists():
        parts.append(agent_path.read_text(encoding="utf-8"))
    # SKILL.md
    skill_path = ROOT_DIR / "skills" / "M18SalesQuotation" / "SKILL.md"
    if skill_path.exists():
        parts.append(skill_path.read_text(encoding="utf-8"))
    # Sales Order Skill
    so_skill_path = ROOT_DIR / "skills" / "M18SalesOrder" / "SKILL.md"
    if so_skill_path.exists():
        parts.append(so_skill_path.read_text(encoding="utf-8"))

    return "\n\n---\n\n".join(parts)


# ── MCP Tool → OpenAI Function Tool ──

import asyncio

TOOLS: List[Dict] = []

def _build_openai_tools():
    global TOOLS
    mcp_tools = asyncio.run(mcp.list_tools())
    for t in mcp_tools:
        schema = t.inputSchema if hasattr(t, 'inputSchema') else {}
        TOOLS.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": (t.description or "").split("\n\n")[0][:200],
                "parameters": schema,
            },
        })

_build_openai_tools()


TOOL_MAP: Dict[str, Any] = {}

def _build_tool_map():
    mcp_tools = asyncio.run(mcp.list_tools())
    for t in mcp_tools:
        TOOL_MAP[t.name] = t

_build_tool_map()


def call_mcp_tool(name: str, args: Dict[str, Any]) -> str:
    try:
        result = asyncio.run(mcp.call_tool(name, args))
        # result = ([TextContent(...)], {'result': '...'})
        content_list = result[0] if isinstance(result, tuple) and result else result
        if isinstance(content_list, list):
            texts = []
            for item in content_list:
                if hasattr(item, 'text'):
                    texts.append(item.text)
                elif isinstance(item, dict) and 'text' in item:
                    texts.append(item['text'])
            if texts:
                return texts[0]
        return str(result)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)


# ── 对话主循环 ──

SYSTEM_PROMPT = f"""你是 M18 ERP 销售助手。你通过 MCP tool 操作 M18 系统。

以下是你的角色定义和业务规则：

{load_context()}

## 行为准则
1. 分析用户的自然语言需求
2. 选择合适的 MCP tool 来执行
3. 调用 tool 后将结果用自然语言总结给用户
4. 如果缺少必要参数，参考 AGENT.md 和 SKILL.md 的规则，主动询问用户
5. 用中文回复
6. 回复中不要使用 emoji"""


def _format_tool_result(tool_name: str, raw: str) -> str:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            if data.get("ok") is False:
                return "操作失败: " + str(data.get('error', '未知错误'))
            inner = data.get("data", data)
            if "create_draft" in tool_name:
                status = inner.get("status", inner)
                if status is True or status == "true":
                    parts = []
                    if inner.get("tranCode"):
                        parts.append("单据编号: " + inner['tranCode'])
                    if inner.get("tranId"):
                        parts.append("tranId=" + str(inner['tranId']))
                    return "创建成功! " + ", ".join(parts) if parts else "创建成功!"
                return "创建失败: " + str(inner.get('message', inner))
            if "save" in tool_name:
                if inner.get("status") is True:
                    return "保存成功! recordId=" + str(inner.get('recordId'))
                msgs = inner.get("messages", [])
                if msgs:
                    return "保存失败: " + str(msgs[0].get('msgDetail', str(msgs[0])))
                return "保存失败: " + json.dumps(inner, ensure_ascii=False)
        return raw
    except json.JSONDecodeError:
        return raw


def main() -> None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    print("=" * 60)
    print("  M18 LLM Agent (" + MODEL + " @ " + BASE_URL + ")")
    print("  输入自然语言，自动调 MCP tool")
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
        if user_input in ("/quit", "/exit", "quit", "exit"):
            print("Bye.")
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            # 清理历史消息中的 reasoning_content（思考模式已禁用，不应出现）
            clean_msgs = []
            for m in messages:
                cm = dict(m)
                cm.pop("reasoning_content", None)
                clean_msgs.append(cm)

            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=clean_msgs,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=2000,
                    extra_body={"thinking": {"type": "disabled"}},
                )
            except Exception as e:
                print(f"LLM 调用失败：{e}")
                break

            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                print(f"\n{msg.content}")
                messages.append({"role": "assistant", "content": msg.content})
                break

            # LLM 要求调工具
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            messages.append(assistant_msg)

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                print(f"\n  → 调用 {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")
                raw_result = call_mcp_tool(tool_name, tool_args)
                formatted = _format_tool_result(tool_name, raw_result)
                print(f"  ← {formatted}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": raw_result,
                })


if __name__ == "__main__":
    main()
