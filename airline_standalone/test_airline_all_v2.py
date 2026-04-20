"""
test_airline_all_v2.py — TAU2 Airline 全工具 Benchmark（修复版）

修复说明：
  WRITE 工具需要多轮对话历史（先验证用户身份/查询详情，再确认操作）。
  本脚本为每个 WRITE 工具预构建好正确的多轮历史，让 LLM 直接处于
  "信息已收集完毕，等待执行操作"的状态，从而触发正确的工具调用。

用法：
  export ANTHROPIC_API_KEY=sk-ant-...
  python test_airline_all_v2.py                        # 测全部 14 个工具
  python test_airline_all_v2.py --model openai         # 使用 OpenAI
  python test_airline_all_v2.py --model both           # 两个都测
  python test_airline_all_v2.py --tool cancel_reservation
  python test_airline_all_v2.py --domain read
  python test_airline_all_v2.py --domain write
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from data_model import FlightDB
from tools import AirlineTools

DB_PATH    = Path(__file__).parent / "db.json"
POLICY_PATH = Path(__file__).parent / "policy.md"


def load_tools() -> AirlineTools:
    db = FlightDB.load(str(DB_PATH))
    return AirlineTools(db)


def get_policy() -> str:
    return POLICY_PATH.read_text() if POLICY_PATH.exists() else \
        "You are an airline customer service agent."


# ══════════════════════════════════════════════════════════════════
# 预构建的多轮对话历史（用于 WRITE 工具）
# 格式: list of {"role": "user"/"assistant", "content": "..."}
# 最后一条必须是 user 的确认消息，触发写操作
# ══════════════════════════════════════════════════════════════════

# ── Shared tool result stubs ──────────────────────────────────────
# 这些是 get_user_details / get_reservation_details 的返回值，
# 预填在历史里让 Claude 直接看到上下文

_USER_RAJ = json.dumps({
    "user_id": "raj_sanchez_7340",
    "name": {"first_name": "Raj", "last_name": "Sanchez"},
    "membership": "silver",
    "payment_methods": {
        "credit_card_7891819": {"source": "credit_card", "id": "credit_card_7891819", "brand": "visa", "last_four": "1234"},
        "gift_card_4964153":   {"source": "gift_card",   "id": "gift_card_4964153",   "amount": 163.0},
        "gift_card_3226531":   {"source": "gift_card",   "id": "gift_card_3226531",   "amount": 0.0},
        "certificate_4594761": {"source": "certificate", "id": "certificate_4594761", "amount": 200.0},
        "gift_card_1591784":   {"source": "gift_card",   "id": "gift_card_1591784",   "amount": 50.0},
    },
    "reservations": ["MZDDS4", "60RX9E", "S5IK51", "OUEA45", "Q69X3R"],
})

_USER_MIA = json.dumps({
    "user_id": "mia_li_3668",
    "name": {"first_name": "Mia", "last_name": "Li"},
    "membership": "gold",
    "payment_methods": {
        "credit_card_4421486": {"source": "credit_card", "id": "credit_card_4421486", "brand": "visa", "last_four": "7447"},
        "certificate_4856383": {"source": "certificate", "id": "certificate_4856383", "amount": 100.0},
        "certificate_7504069": {"source": "certificate", "id": "certificate_7504069", "amount": 100.0},
        "credit_card_1955700": {"source": "credit_card", "id": "credit_card_1955700", "brand": "mastercard", "last_four": "5678"},
    },
    "saved_passengers": [{"first_name": "Amelia", "last_name": "Ahmed", "dob": "1957-03-21"}],
    "reservations": ["NO6JO3", "AIXC49", "HKEG34"],
})

_USER_CHEN = json.dumps({
    "user_id": "chen_jackson_3290",
    "name": {"first_name": "Chen", "last_name": "Jackson"},
    "membership": "silver",
    "payment_methods": {
        "gift_card_3576581": {"source": "gift_card", "id": "gift_card_3576581", "amount": 245.0},
    },
    "reservations": ["4WQ150", "DDHPNX", "Y69PCE"],
})

_RES_MZDDS4 = json.dumps({
    "reservation_id": "MZDDS4",
    "user_id": "raj_sanchez_7340",
    "origin": "ORD", "destination": "BOS",
    "flight_type": "round_trip",
    "cabin": "business",
    "flights": [
        {"flight_number": "HAT050", "origin": "ORD", "destination": "BOS", "date": "2024-05-17", "price": 800},
        {"flight_number": "HAT228", "origin": "BOS", "destination": "ORD", "date": "2024-05-22", "price": 750},
        {"flight_number": "HAT202", "origin": "BOS", "destination": "ORD", "date": "2024-05-23", "price": 700},
    ],
    "passengers": [{"first_name": "Raj", "last_name": "Sanchez", "dob": "1965-09-13"}],
    "payment_history": [{"payment_id": "credit_card_7891819", "amount": 2250}],
    "created_at": "2024-05-14T11:06:55",
    "total_baggages": 0, "nonfree_baggages": 0,
    "insurance": "no", "status": None,
})

_RES_Q69X3R = json.dumps({
    "reservation_id": "Q69X3R",
    "user_id": "raj_sanchez_7340",
    "origin": "PHL", "destination": "LGA",
    "flight_type": "round_trip",
    "cabin": "economy",
    "flights": [
        {"flight_number": "HAT243", "origin": "PHL", "destination": "CLT", "date": "2024-05-20", "price": 166},
        {"flight_number": "HAT024", "origin": "CLT", "destination": "LGA", "date": "2024-05-20", "price": 162},
        {"flight_number": "HAT206", "origin": "LGA", "destination": "PHL", "date": "2024-05-23", "price": 102},
    ],
    "passengers": [{"first_name": "Raj", "last_name": "Sanchez", "dob": "1965-09-13"}],
    "payment_history": [{"payment_id": "gift_card_3226531", "amount": 430}],
    "created_at": "2024-05-14T09:52:38",
    "total_baggages": 0, "nonfree_baggages": 0,
    "insurance": "no", "status": None,
})

_RES_4WQ150 = json.dumps({
    "reservation_id": "4WQ150",
    "user_id": "chen_jackson_3290",
    "origin": "DFW", "destination": "LAX",
    "flight_type": "round_trip",
    "cabin": "business",
    "flights": [
        {"flight_number": "HAT170", "origin": "DFW", "destination": "LAX", "date": "2024-05-22", "price": 883},
        {"flight_number": "HAT022", "origin": "LAX", "destination": "DFW", "date": "2024-05-26", "price": 779},
    ],
    "passengers": [
        {"first_name": "Chen",   "last_name": "Jackson", "dob": "1956-07-07"},
        {"first_name": "Raj",    "last_name": "Smith",   "dob": "1967-04-01"},
        {"first_name": "Fatima", "last_name": "Martin",  "dob": "1970-01-20"},
    ],
    "payment_history": [{"payment_id": "gift_card_3576581", "amount": 4986}],
    "created_at": "2024-05-02T03:10:19",
    "total_baggages": 5, "nonfree_baggages": 0,
    "insurance": "no", "status": None,
})

_FLIGHT_HAT001_0517 = json.dumps([{
    "flight_number": "HAT001",
    "origin": "PHL", "destination": "LGA",
    "status": "available",
    "scheduled_departure_time_est": "06:00:00",
    "scheduled_arrival_time_est": "07:00:00",
    "date": "2024-05-17",
    "available_seats": {"basic_economy": 16, "economy": 13, "business": 9},
    "prices": {"basic_economy": 76, "economy": 189, "business": 498},
}])


# ══════════════════════════════════════════════════════════════════
# 14 个工具测试用例
# ══════════════════════════════════════════════════════════════════

TEST_CASES = {

    # ── READ (单轮，直接可触发) ────────────────────────────────────

    "get_user_details": {
        "type": "read",
        "messages": [
            {"role": "user", "content": "I am raj_sanchez_7340. Can you look up my account details?"},
        ],
        "expected_tool": "get_user_details",
        "expected_args": {"user_id": "raj_sanchez_7340"},
        "note": "直接触发，无需多轮",
    },

    "get_reservation_details": {
        "type": "read",
        "messages": [
            {"role": "user", "content": "I am raj_sanchez_7340. What are the details of my reservation Q69X3R?"},
            # 给出用户验证结果，让 Claude 知道身份已确认，直接查预订
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_7340"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content": "I've verified your identity. Let me look up reservation Q69X3R for you."},
            {"role": "user", "content": "Yes, please show me reservation Q69X3R."},
        ],
        "expected_tool": "get_reservation_details",
        "expected_args": {"reservation_id": "Q69X3R"},
        "note": "用户身份已验证，直接查预订",
    },

    "list_all_airports": {
        "type": "read",
        "messages": [
            {"role": "user", "content": "What airports are available in your system?"},
        ],
        "expected_tool": "list_all_airports",
        "expected_args": {},
        "note": "无参数，直接触发",
    },

    "search_direct_flight": {
        "type": "read",
        "messages": [
            {"role": "user", "content": "Search for direct flights from PHL to LGA on 2024-05-16."},
        ],
        "expected_tool": "search_direct_flight",
        "expected_args": {"origin": "PHL", "destination": "LGA", "date": "2024-05-16"},
        "note": "直接触发",
    },

    "search_onestop_flight": {
        "type": "read",
        "messages": [
            {"role": "user", "content": "Search for one-stop connecting flights from PHL to PHX on 2024-05-16."},
        ],
        "expected_tool": "search_onestop_flight",
        "expected_args": {"origin": "PHL", "destination": "PHX", "date": "2024-05-16"},
        "note": "直接触发",
    },

    "get_flight_status": {
        "type": "read",
        "messages": [
            {"role": "user", "content": "What is the status of flight HAT243 on 2024-05-20?"},
        ],
        "expected_tool": "get_flight_status",
        "expected_args": {"flight_number": "HAT243", "date": "2024-05-20"},
        "note": "直接触发",
    },

    # ── GENERIC ───────────────────────────────────────────────────

    "calculate": {
        "type": "generic",
        "messages": [
            {"role": "user", "content": "Calculate (450 + 162 + 166) * 1.1 for me."},
        ],
        "expected_tool": "calculate",
        "expected_args": {"expression": "(450 + 162 + 166) * 1.1"},
        "note": "直接触发",
    },

    "transfer_to_human_agents": {
        "type": "generic",
        "messages": [
            {"role": "user", "content":
             "I am raj_sanchez_7340. I need to speak with a human agent immediately. "
             "I have a complex unresolvable issue with my reservation."},
        ],
        "expected_tool": "transfer_to_human_agents",
        "expected_args": {},
        "note": "明确要求转人工，summary 由 LLM 生成",
    },

    # ── WRITE (多轮，预构建历史到确认阶段) ────────────────────────

    "book_reservation": {
        "type": "write",
        # mia_li_3668: gold, credit_card_4421486
        # HAT001 PHL->LGA 2024-05-17, economy $189, 1 passenger
        "messages": [
            {"role": "user", "content":
             "I am mia_li_3668. I want to book a one-way economy flight from PHL to LGA "
             "on 2024-05-17 for one passenger: Amelia Ahmed, DOB 1957-03-21. "
             "Pay with credit_card_4421486. No extra bags, no insurance."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "mia_li_3668"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_MIA},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "search_direct_flight",
                 "input": {"origin": "PHL", "destination": "LGA", "date": "2024-05-17"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _FLIGHT_HAT001_0517},
            ]},
            {"role": "assistant", "content":
             "I found flight HAT001 from PHL to LGA on 2024-05-17, economy class at $189. "
             "Here are the booking details:\n"
             "- Flight: HAT001, PHL → LGA, 2024-05-17\n"
             "- Cabin: Economy, $189\n"
             "- Passenger: Amelia Ahmed, DOB 1957-03-21\n"
             "- Payment: credit_card_4421486 (Visa ending 7447), $189\n"
             "- Baggage: 0 checked bags (3 free included as gold member)\n"
             "- Insurance: No\n"
             "Shall I proceed with this booking?"},
            {"role": "user", "content": "Yes, please proceed."},
        ],
        "expected_tool": "book_reservation",
        "expected_args": {
            "user_id": "mia_li_3668",
            "origin": "PHL",
            "destination": "LGA",
            "flight_type": "one_way",
            "cabin": "economy",
        },
        "note": "Gold member, credit card, 1 passenger, after full confirmation",
    },

    "cancel_reservation": {
        "type": "write",
        # MZDDS4: raj_sanchez_7340, business cabin → eligible to cancel
        "messages": [
            {"role": "user", "content":
             "I am raj_sanchez_7340. I want to cancel reservation MZDDS4. "
             "My plans have changed."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_7340"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_reservation_details",
                 "input": {"reservation_id": "MZDDS4"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _RES_MZDDS4},
            ]},
            {"role": "assistant", "content":
             "I can cancel reservation MZDDS4. It's a business class round trip (ORD ↔ BOS). "
             "The refund of $2,250 will go back to your credit_card_7891819 within 5-7 business days. "
             "Would you like to proceed with the cancellation?"},
            {"role": "user", "content": "Yes, please cancel it."},
        ],
        "expected_tool": "cancel_reservation",
        "expected_args": {"reservation_id": "MZDDS4"},
        "note": "Business cabin, eligible for cancellation, full multi-turn history",
    },

    "update_reservation_baggages": {
        "type": "write",
        # 4WQ150: chen_jackson_3290, business, nonfree=0, gift_card $245
        # Adding 1 nonfree bag = $50
        "messages": [
            {"role": "user", "content":
             "I am chen_jackson_3290. I want to add 1 non-free checked bag to reservation 4WQ150. "
             "Please charge it to gift_card_3576581."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "chen_jackson_3290"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_CHEN},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_reservation_details",
                 "input": {"reservation_id": "4WQ150"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _RES_4WQ150},
            ]},
            {"role": "assistant", "content":
             "I'll update reservation 4WQ150 to add 1 non-free checked bag:\n"
             "- Current: 5 total bags, 0 non-free\n"
             "- Updated: 6 total bags, 1 non-free\n"
             "- Additional charge: $50 to gift_card_3576581 (current balance: $245)\n"
             "Shall I proceed?"},
            {"role": "user", "content": "Yes, go ahead."},
        ],
        "expected_tool": "update_reservation_baggages",
        "expected_args": {
            "reservation_id": "4WQ150",
            "total_baggages": 6,
            "nonfree_baggages": 1,
            "payment_id": "gift_card_3576581",
        },
        "note": "Business, add 1 non-free bag $50, gift card payment",
    },

    "update_reservation_flights": {
        "type": "write",
        # Q69X3R: economy (not basic), change HAT243+HAT024 to HAT001 on 2024-05-17
        # keep return HAT206 on 2024-05-23
        # new price $189 vs old $328, refund $139
        "messages": [
            {"role": "user", "content":
             "I am raj_sanchez_7340. I want to change the outbound flights on reservation Q69X3R "
             "to flight HAT001 on 2024-05-17, and keep the return flight HAT206 on 2024-05-23. "
             "Please use gift_card_4964153 for any payment difference."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_7340"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_reservation_details",
                 "input": {"reservation_id": "Q69X3R"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _RES_Q69X3R},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_003", "name": "search_direct_flight",
                 "input": {"origin": "PHL", "destination": "LGA", "date": "2024-05-17"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_003", "content": _FLIGHT_HAT001_0517},
            ]},
            {"role": "assistant", "content":
             "Here are the updated flight details for reservation Q69X3R:\n"
             "- New outbound: HAT001, PHL → LGA, 2024-05-17, economy $189\n"
             "- Return (unchanged): HAT206, LGA → PHL, 2024-05-23, $102\n"
             "- Price difference: $189 - $328 = -$139 (refund to gift_card_4964153)\n"
             "Shall I proceed with this change?"},
            {"role": "user", "content": "Yes, please update the flights."},
        ],
        "expected_tool": "update_reservation_flights",
        "expected_args": {
            "reservation_id": "Q69X3R",
            "cabin": "economy",
            "payment_id": "gift_card_4964153",
        },
        "note": "Economy reservation, swap outbound flight, refund $139",
    },

    "update_reservation_passengers": {
        "type": "write",
        # 4WQ150: 3 passengers, correct Raj Smith DOB from 1967-04-01 to 1967-04-02
        "messages": [
            {"role": "user", "content":
             "I am chen_jackson_3290. I need to correct a passenger DOB on reservation 4WQ150. "
             "Raj Smith's DOB should be 1967-04-02, not 1967-04-01."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "chen_jackson_3290"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_CHEN},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_reservation_details",
                 "input": {"reservation_id": "4WQ150"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _RES_4WQ150},
            ]},
            {"role": "assistant", "content":
             "I'll update the passengers on reservation 4WQ150 with the corrected DOB:\n"
             "1. Chen Jackson - DOB: 1956-07-07 (unchanged)\n"
             "2. Raj Smith    - DOB: 1967-04-02 (corrected from 1967-04-01)\n"
             "3. Fatima Martin - DOB: 1970-01-20 (unchanged)\n"
             "Shall I proceed?"},
            {"role": "user", "content": "Yes, please update the passenger information."},
        ],
        "expected_tool": "update_reservation_passengers",
        "expected_args": {"reservation_id": "4WQ150"},
        "note": "Correct passenger DOB, must keep same count (3)",
    },

    "send_certificate": {
        "type": "write",
        # raj_sanchez_7340, silver member, flight cancelled by airline → eligible
        "messages": [
            {"role": "user", "content":
             "I am raj_sanchez_7340. My flight HAT050 on reservation MZDDS4 was cancelled "
             "by the airline. I'd like compensation."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_7340"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_reservation_details",
                 "input": {"reservation_id": "MZDDS4"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _RES_MZDDS4},
            ]},
            {"role": "assistant", "content":
             "I've verified that flight HAT050 on reservation MZDDS4 was cancelled by the airline. "
             "As a silver member, you are eligible for compensation of $100 per passenger. "
             "Your reservation has 1 passenger, so I can send a $100 travel certificate. "
             "Shall I proceed?"},
            {"role": "user", "content": "Yes, please send the $100 certificate."},
        ],
        "expected_tool": "send_certificate",
        "expected_args": {"user_id": "raj_sanchez_7340", "amount": 100},
        "note": "Silver member, airline cancelled, $100 per passenger compensation",
    },

}


# ══════════════════════════════════════════════════════════════════
# Schema generation
# ══════════════════════════════════════════════════════════════════

def get_schemas_anthropic(tools: AirlineTools) -> list[dict]:
    schemas = []
    for name, tool in tools.get_tools().items():
        fn = tool.openai_schema["function"]
        schemas.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
        })
    return schemas


def get_schemas_openai(tools: AirlineTools) -> list[dict]:
    return [tool.openai_schema for tool in tools.get_tools().values()]


# ══════════════════════════════════════════════════════════════════
# Tool execution
# ══════════════════════════════════════════════════════════════════

def execute_tool(tools: AirlineTools, tool_name: str, tool_input: dict) -> str:
    from datetime import date, datetime
    from pydantic import BaseModel

    def serialize(obj):
        if isinstance(obj, BaseModel):    return obj.model_dump()
        elif isinstance(obj, (datetime, date)): return obj.isoformat()
        elif isinstance(obj, list):       return [serialize(i) for i in obj]
        elif isinstance(obj, tuple):      return [serialize(i) for i in obj]
        elif isinstance(obj, dict):       return {k: serialize(v) for k, v in obj.items()}
        return obj

    try:
        result = tools.use_tool(tool_name, **tool_input)
        return json.dumps(serialize(result), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ══════════════════════════════════════════════════════════════════
# Single API call — send messages, get first tool call
# ══════════════════════════════════════════════════════════════════

def run_anthropic(messages: list, tools: AirlineTools) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=get_policy(),
        tools=get_schemas_anthropic(tools),
        messages=messages,
    )
    for block in response.content:
        if block.type == "tool_use":
            return {"called": True, "name": block.name, "input": block.input, "id": block.id}
    return {"called": False, "stop_reason": response.stop_reason}


def run_openai(messages: list, tools: AirlineTools) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Convert Anthropic-style tool_use blocks to OpenAI format
    oai_messages = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, list):
            # Check if it's a tool_use block (assistant) or tool_result (user)
            tool_uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
            tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
            if tool_uses:
                oai_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": b["id"], "type": "function",
                        "function": {"name": b["name"], "arguments": json.dumps(b["input"])}
                    } for b in tool_uses]
                })
            elif tool_results:
                for tr in tool_results:
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_use_id"],
                        "content": tr["content"],
                    })
        else:
            oai_messages.append({"role": role, "content": content})

    # Prepend system
    oai_messages.insert(0, {"role": "system", "content": get_policy()})

    response = client.chat.completions.create(
        model="gpt-4o",
        tools=get_schemas_openai(tools),
        tool_choice="auto",
        messages=oai_messages,
    )
    msg = response.choices[0].message
    if msg.tool_calls:
        tc = msg.tool_calls[0]
        return {"called": True, "name": tc.function.name,
                "input": json.loads(tc.function.arguments), "id": tc.id}
    return {"called": False, "finish_reason": response.choices[0].finish_reason}


# ══════════════════════════════════════════════════════════════════
# Verification
# ══════════════════════════════════════════════════════════════════

def verify(result: dict, expected_tool: str, expected_args: dict) -> tuple[bool, list[str]]:
    if not result.get("called"):
        return False, [f"No tool called (stop: {result.get('stop_reason') or result.get('finish_reason','?')})"]

    issues = []
    if result["name"] != expected_tool:
        return False, [f"Wrong tool: got '{result['name']}', expected '{expected_tool}'"]

    for key, val in expected_args.items():
        if key not in result["input"]:
            issues.append(f"Missing arg '{key}'")
        elif val is not None and result["input"][key] != val:
            issues.append(f"Arg '{key}': got {result['input'][key]!r}, expected {val!r}")

    return len(issues) == 0, issues


# ══════════════════════════════════════════════════════════════════
# Main runner
# ══════════════════════════════════════════════════════════════════

def run_all(model: str = "anthropic", tool_filter=None, domain_filter=None):
    tools = load_tools()
    runner = run_anthropic if model == "anthropic" else run_openai

    cases = {
        k: v for k, v in TEST_CASES.items()
        if (tool_filter is None or k == tool_filter)
        and (domain_filter is None or v["type"] == domain_filter)
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file  = f"airline_results_{model}_{timestamp}.json"

    print(f"\n{'='*65}")
    print(f"Airline Tool Benchmark v2 — {model.upper()}  ({len(cases)} tools)")
    if tool_filter:   print(f"Tool:   {tool_filter}")
    if domain_filter: print(f"Domain: {domain_filter}")
    print(f"{'='*65}\n")

    results = []
    total = passed = failed = errored = 0

    for i, (name, case) in enumerate(cases.items(), 1):
        total += 1
        turns = len([m for m in case["messages"] if m["role"] == "user"])
        print(f"[{i:02d}/{len(cases)}] {case['type'].upper():7} | {name}  ({turns}-turn)")
        print(f"  note: {case['note']}")

        try:
            result = runner(case["messages"], tools)
            ok, issues = verify(result, case["expected_tool"], case["expected_args"])

            if ok:
                passed += 1
                print(f"  ✅ Called: {result['name']}")
                preview = dict(list(result["input"].items())[:3])
                more = " ..." if len(result["input"]) > 3 else ""
                print(f"  input: {json.dumps(preview, ensure_ascii=False)}{more}")
            else:
                failed += 1
                print(f"  ❌ FAIL")
                for issue in issues:
                    print(f"     → {issue}")
                if result.get("called"):
                    print(f"     actual: {result['name']}({json.dumps(result.get('input',{}))[:120]})")

            results.append({
                "tool": name, "type": case["type"],
                "ok": ok, "issues": issues, "result": result,
            })

        except Exception as e:
            errored += 1
            print(f"  ⚠️  Error: {e}")
            results.append({"tool": name, "type": case["type"], "ok": False, "error": str(e)})

        time.sleep(0.4)
        print()

    # Summary
    pct = 100 * passed // total if total else 0
    print(f"{'='*65}")
    print(f"RESULTS — {model.upper()}")
    print(f"  Total:    {total}")
    print(f"  ✅ Pass:  {passed}  ({pct}%)")
    print(f"  ❌ Fail:  {failed}")
    print(f"  ⚠️  Error: {errored}")
    for ttype in ["read", "write", "generic"]:
        grp = [r for r in results if r.get("type") == ttype]
        ok  = sum(1 for r in grp if r.get("ok"))
        if grp: print(f"  {ttype.upper():8} {ok}/{len(grp)}")
    print(f"{'='*65}")

    failed_results = [r for r in results if not r.get("ok")]
    if failed_results:
        print(f"\nFailed: {[r['tool'] for r in failed_results]}")

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump({
            "model": model, "timestamp": timestamp,
            "summary": {"total": total, "passed": passed, "failed": failed, "errored": errored},
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults → {log_file}")
    return results


# ══════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Airline Tool Benchmark v2")
    parser.add_argument("--model",  default="anthropic", choices=["anthropic","openai","both"])
    parser.add_argument("--tool",   default=None, help=f"Single tool: {list(TEST_CASES.keys())}")
    parser.add_argument("--domain", default=None, choices=["read","write","generic"])
    args = parser.parse_args()

    if args.model in ("anthropic","both") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: set ANTHROPIC_API_KEY"); sys.exit(1)
    if args.model in ("openai","both") and not os.environ.get("OPENAI_API_KEY"):
        print("Error: set OPENAI_API_KEY"); sys.exit(1)

    if args.model == "both":
        run_all("anthropic", args.tool, args.domain)
        print()
        run_all("openai",    args.tool, args.domain)
    else:
        run_all(args.model, args.tool, args.domain)
