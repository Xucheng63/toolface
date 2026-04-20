"""
airline_agent.py — TAU2 Airline 独立集成脚本

功能：
  1. 加载 db.json 初始化 AirlineTools
  2. 把工具 schema 发给 LLM（Anthropic 或 OpenAI）
  3. LLM 返回 tool_use → 真实调用 AirlineTools → 结果返回 LLM → 最终回答

用法：
  export ANTHROPIC_API_KEY=sk-ant-...
  python airline_agent.py                                        # 交互模式
  python airline_agent.py --query "What is reservation Q69X3R?" # 单次查询
  python airline_agent.py --model openai                        # 使用 OpenAI
  python airline_agent.py --tool get_reservation_details        # 查看单个工具 schema
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── 本地模块（当前目录） ─────────────────────────────────────────
from data_model import FlightDB
from tools import AirlineTools

# ── 加载数据库 ───────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "db.json"
POLICY_PATH = Path(__file__).parent / "policy.md"


def load_env():
    """加载数据库和工具，返回 AirlineTools 实例。"""
    db = FlightDB.load(str(DB_PATH))
    return AirlineTools(db)


def get_policy() -> str:
    if POLICY_PATH.exists():
        return POLICY_PATH.read_text()
    return "You are an airline customer service agent."


# ── Schema 生成 ──────────────────────────────────────────────────

def get_anthropic_schemas(airline_tools: AirlineTools) -> list[dict]:
    """把 AirlineTools 的所有工具转为 Anthropic tool schema 格式。"""
    schemas = []
    for name, tool in airline_tools.get_tools().items():
        raw = tool.openai_schema  # {"type":"function","function":{name,description,parameters}}
        fn = raw["function"]
        schemas.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
        })
    return schemas


def get_openai_schemas(airline_tools: AirlineTools) -> list[dict]:
    """把 AirlineTools 的所有工具转为 OpenAI tool schema 格式。"""
    return [tool.openai_schema for tool in airline_tools.get_tools().values()]


# ── 工具执行 ─────────────────────────────────────────────────────

def execute_tool(airline_tools: AirlineTools, tool_name: str, tool_input: dict) -> str:
    """
    执行工具调用，返回 JSON 字符串结果。
    对应 Environment.get_response() 的逻辑。
    """
    import json
    from datetime import date, datetime
    from pydantic import BaseModel

    def serialize(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, list):
            return [serialize(i) for i in obj]
        elif isinstance(obj, tuple):
            return [serialize(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        return obj

    try:
        result = airline_tools.use_tool(tool_name, **tool_input)
        return json.dumps(serialize(result), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Anthropic Agent Loop ─────────────────────────────────────────

def run_anthropic(query: str, airline_tools: AirlineTools, verbose: bool = True) -> str:
    try:
        import anthropic
    except ImportError:
        print("请安装: pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    schemas = get_anthropic_schemas(airline_tools)
    policy = get_policy()

    messages = [{"role": "user", "content": query}]

    if verbose:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"Tools available: {len(schemas)}")
        print('='*60)

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=policy,
            tools=schemas,
            messages=messages,
        )

        if verbose:
            print(f"\nstop_reason: {response.stop_reason}")

        # Collect tool uses and text
        tool_results = []
        has_tool_use = False

        for block in response.content:
            if block.type == "tool_use":
                has_tool_use = True
                if verbose:
                    print(f"\n→ Tool call: {block.name}")
                    print(f"  input: {json.dumps(block.input, ensure_ascii=False)}")

                result = execute_tool(airline_tools, block.name, block.input)

                if verbose:
                    result_preview = result[:200] + ("..." if len(result) > 200 else "")
                    print(f"  result: {result_preview}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            elif block.type == "text" and block.text:
                if verbose and not has_tool_use:
                    print(f"\n← Response: {block.text}")

        if not has_tool_use:
            # Final text response — extract and return
            final = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            return final

        # Add assistant turn + tool results and continue
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


# ── OpenAI Agent Loop ─────────────────────────────────────────────

def run_openai(query: str, airline_tools: AirlineTools, verbose: bool = True) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        print("请安装: pip install openai")
        sys.exit(1)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    schemas = get_openai_schemas(airline_tools)
    policy = get_policy()

    messages = [
        {"role": "system", "content": policy},
        {"role": "user", "content": query},
    ]

    if verbose:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"Tools available: {len(schemas)}")
        print('='*60)

    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            tools=schemas,
            tool_choice="auto",
            messages=messages,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if verbose:
            print(f"\nfinish_reason: {finish_reason}")

        if finish_reason == "tool_calls" and msg.tool_calls:
            messages.append(msg)

            for tc in msg.tool_calls:
                tool_input = json.loads(tc.function.arguments)
                if verbose:
                    print(f"\n→ Tool call: {tc.function.name}")
                    print(f"  input: {json.dumps(tool_input, ensure_ascii=False)}")

                result = execute_tool(airline_tools, tc.function.name, tool_input)

                if verbose:
                    result_preview = result[:200] + ("..." if len(result) > 200 else "")
                    print(f"  result: {result_preview}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            final = msg.content or ""
            if verbose:
                print(f"\n← Response: {final}")
            return final


# ── Print tool schema ────────────────────────────────────────────

def print_tool_schema(airline_tools: AirlineTools, tool_name: str):
    """打印单个工具的 Anthropic 和 OpenAI schema。"""
    tools = airline_tools.get_tools()
    if tool_name not in tools:
        print(f"Tool '{tool_name}' not found.")
        print(f"Available: {list(tools.keys())}")
        return

    tool = tools[tool_name]
    fn = tool.openai_schema["function"]

    anthropic_schema = {
        "name": fn["name"],
        "description": fn["description"],
        "input_schema": fn["parameters"],
    }
    openai_schema = tool.openai_schema

    print(f"\n{'='*60}")
    print(f"Tool: {tool_name}")
    print('='*60)
    print("\n// ── Anthropic Schema")
    print(json.dumps(anthropic_schema, indent=2, ensure_ascii=False))
    print("\n// ── OpenAI Schema")
    print(json.dumps(openai_schema, indent=2, ensure_ascii=False))


# ── Interactive mode ──────────────────────────────────────────────

def interactive_mode(model: str, airline_tools: AirlineTools):
    print(f"\nAirline Agent ({model}) — 输入 'exit' 退出, 'schema <tool>' 查看工具 schema")
    print(f"DB loaded: {airline_tools.db.get_statistics()}")
    print(f"Tools: {list(airline_tools.get_tools().keys())}\n")

    runner = run_anthropic if model == "anthropic" else run_openai

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() == "exit":
            break
        if query.lower().startswith("schema "):
            tool_name = query[7:].strip()
            print_tool_schema(airline_tools, tool_name)
            continue

        try:
            response = runner(query, airline_tools, verbose=True)
            print(f"\nAgent: {response}\n")
        except Exception as e:
            print(f"Error: {e}")


# ── Entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TAU2 Airline Agent (standalone)")
    parser.add_argument("--model",  default="anthropic", choices=["anthropic", "openai"],
                        help="LLM backend (default: anthropic)")
    parser.add_argument("--query",  default=None,
                        help="Single query to run (non-interactive)")
    parser.add_argument("--tool",   default=None,
                        help="Print schema for a specific tool and exit")
    args = parser.parse_args()

    # Check API key
    if args.tool is None:
        if args.model == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            print("Error: set ANTHROPIC_API_KEY"); sys.exit(1)
        if args.model == "openai" and not os.environ.get("OPENAI_API_KEY"):
            print("Error: set OPENAI_API_KEY"); sys.exit(1)

    # Load tools
    airline_tools = load_env()

    if args.tool:
        print_tool_schema(airline_tools, args.tool)
    elif args.query:
        runner = run_anthropic if args.model == "anthropic" else run_openai
        result = runner(args.query, airline_tools, verbose=True)
        print(f"\nFinal answer: {result}")
    else:
        interactive_mode(args.model, airline_tools)
