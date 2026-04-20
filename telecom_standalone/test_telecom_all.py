"""
test_telecom_all.py — TAU2 Telecom 全工具 Benchmark 测试脚本

测试 Agent Tools (13) + User Tools (30) = 43 个工具的 schema。
所有数据来自真实 db.toml / user_db.toml。

用法：
  export ANTHROPIC_API_KEY=sk-ant-...
  python test_telecom_all.py                          # 测全部 43 个
  python test_telecom_all.py --model openai           # 使用 OpenAI
  python test_telecom_all.py --model both             # 两个都测
  python test_telecom_all.py --group agent            # 只测 Agent 工具
  python test_telecom_all.py --group user             # 只测 User 工具
  python test_telecom_all.py --tool get_customer_by_phone
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from data_model import TelecomDB
from user_data_model import TelecomUserDB
from tools import TelecomTools
from user_tools import TelecomUserTools

DB_PATH      = Path(__file__).parent / "db.toml"
USER_DB_PATH = Path(__file__).parent / "user_db.toml"
POLICY_PATH  = Path(__file__).parent / "main_policy.md"


def load_tools():
    db      = TelecomDB.load(str(DB_PATH))
    user_db = TelecomUserDB.load(str(USER_DB_PATH))
    return TelecomTools(db), TelecomUserTools(user_db)


def get_policy() -> str:
    if POLICY_PATH.exists():
        return POLICY_PATH.read_text()
    return "You are a telecom customer service agent."


# ══════════════════════════════════════════════════════════════════
# Real data from db.toml / user_db.toml
# ══════════════════════════════════════════════════════════════════

_CUSTOMER_C1001 = json.dumps({
    "customer_id": "C1001",
    "full_name": "John Smith",
    "date_of_birth": "1985-06-15",
    "email": "john.smith@example.com",
    "phone_number": "555-123-2002",
    "account_status": "Active",
    "line_ids": ["L1001", "L1002", "L1003"],
    "bill_ids": ["B1001", "B1002", "B1003"],
    "payment_methods": [{"method_type": "Credit Card", "account_number_last_4": "1235", "expiration_date": "12/2026"}]
})

_LINE_L1002 = json.dumps({
    "line_id": "L1002",
    "phone_number": "555-123-2002",
    "status": "Active",
    "plan_id": "P1002",
    "device_id": "D1002",
    "data_used_gb": 8.7,
    "data_refueling_gb": 0.0,
    "roaming_enabled": True,
    "contract_end_date": "2026-12-31"
})

_BILL_B1002 = json.dumps({
    "bill_id": "B1002",
    "customer_id": "C1001",
    "period_start": "2025-02-01",
    "period_end": "2025-02-28",
    "issue_date": "2025-02-05",
    "total_due": 150.0,
    "due_date": "2025-02-19",
    "status": "Issued"
})

# C1002 has overdue bill B1005
_CUSTOMER_C1002 = json.dumps({
    "customer_id": "C1002",
    "full_name": "Sarah Johnson",
    "date_of_birth": "1990-11-22",
    "email": "sarah.j@example.com",
    "phone_number": "555-123-1002",
    "account_status": "Active",
    "line_ids": ["L1004", "L1005", "L1006", "L1007", "L1008"],
    "bill_ids": ["B1004", "B1005"],
    "payment_methods": [
        {"method_type": "Debit Card", "account_number_last_4": "1234", "expiration_date": "12/2026"},
        {"method_type": "Credit Card", "account_number_last_4": "5678", "expiration_date": "06/2027"},
    ]
})

_BILL_B1005_OVERDUE = json.dumps({
    "bill_id": "B1005",
    "customer_id": "C1002",
    "total_due": 425.0,
    "due_date": "2025-02-26",
    "status": "Overdue"
})


# ══════════════════════════════════════════════════════════════════
# Test cases — 43 tools
# ══════════════════════════════════════════════════════════════════

TEST_CASES = {

    # ── Agent READ ────────────────────────────────────────────────

    "get_customer_by_phone": {
        "group": "agent", "type": "read",
        "messages": [
            {"role": "user", "content": "Look up the customer with phone number 555-123-2002."},
        ],
        "expected_tool": "get_customer_by_phone",
        "expected_args": {"phone_number": "555-123-2002"},
        "note": "Customer lookup by phone",
    },

    "get_customer_by_id": {
        "group": "agent", "type": "read",
        "messages": [
            {"role": "user", "content": "Pull up the account for customer ID C1001."},
        ],
        "expected_tool": "get_customer_by_id",
        "expected_args": {"customer_id": "C1001"},
        "note": "Customer lookup by ID",
    },

    "get_customer_by_name": {
        "group": "agent", "type": "read",
        "messages": [
            {"role": "user", "content": "Find customer John Smith with date of birth 1985-06-15."},
        ],
        "expected_tool": "get_customer_by_name",
        "expected_args": {"full_name": "John Smith", "dob": "1985-06-15"},
        "note": "Customer lookup by name + DOB",
    },

    "get_details_by_id": {
        "group": "agent", "type": "read",
        "force_tool": "get_details_by_id",
        "messages": [
            {"role": "user", "content": "Use the get_details_by_id tool to fetch the full details for ID L1002."},
        ],
        "expected_tool": "get_details_by_id",
        "expected_args": {"id": "L1002"},
        "note": "Generic detail lookup by ID",
    },

    "get_bills_for_customer": {
        "group": "agent", "type": "read",
        "force_tool": "get_bills_for_customer",
        "messages": [
            {"role": "user", "content": "Show me the last 3 bills for customer C1001."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_id",
                 "input": {"customer_id": "C1001"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1001},
            ]},
            {"role": "assistant", "content": "I verified the customer. Let me pull up their bills."},
            {"role": "user", "content": "Yes, show the last 3 bills."},
        ],
        "expected_tool": "get_bills_for_customer",
        "expected_args": {"customer_id": "C1001"},
        "note": "Get billing history, customer pre-verified",
    },

    "get_data_usage": {
        "group": "agent", "type": "read",
        "messages": [
            {"role": "user", "content": "How much data has customer C1001 used on line L1002 this month?"},
        ],
        "expected_tool": "get_data_usage",
        "expected_args": {"customer_id": "C1001", "line_id": "L1002"},
        "note": "Check data usage for a line",
    },

    # ── Agent WRITE ───────────────────────────────────────────────

    "suspend_line": {
        "group": "agent", "type": "write",
        "force_tool": "suspend_line",
        "messages": [
            {"role": "user", "content": "The customer with phone 555-123-2002 wants to suspend line L1002. Reason: lost phone."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_phone",
                 "input": {"phone_number": "555-123-2002"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1001},
            ]},
            {"role": "assistant", "content":
             "I'll suspend line L1002 for customer C1001. Reason: lost phone. Proceed?"},
            {"role": "user", "content": "Yes, suspend it."},
        ],
        "expected_tool": "suspend_line",
        "expected_args": {"customer_id": "C1001", "line_id": "L1002"},
        "note": "Suspend an active line",
    },

    "resume_line": {
        "group": "agent", "type": "write",
        "force_tool": "resume_line",
        "messages": [
            {"role": "user", "content": "Resume line L1002 for customer C1001 after they paid their bill."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_id",
                 "input": {"customer_id": "C1001"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1001},
            ]},
            {"role": "assistant", "content": "I'll resume line L1002 for customer C1001. Proceed?"},
            {"role": "user", "content": "Yes, resume it."},
        ],
        "expected_tool": "resume_line",
        "expected_args": {"customer_id": "C1001", "line_id": "L1002"},
        "note": "Resume a suspended line",
    },

    "send_payment_request": {
        "group": "agent", "type": "write",
        "force_tool": "send_payment_request",
        "messages": [
            {"role": "user", "content": "Send a payment request to customer C1002 for overdue bill B1005."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_id",
                 "input": {"customer_id": "C1002"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1002},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_bills_for_customer",
                 "input": {"customer_id": "C1002"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": json.dumps([
                    {"bill_id": "B1005", "status": "Overdue", "total_due": 425.0, "due_date": "2025-02-26"},
                    {"bill_id": "B1004", "status": "Paid", "total_due": 425.0},
                ])},
            ]},
            {"role": "assistant", "content":
             "Bill B1005 is overdue for $425.00. Sending payment request to customer C1002. Proceed?"},
            {"role": "user", "content": "Yes, send it."},
        ],
        "expected_tool": "send_payment_request",
        "expected_args": {"customer_id": "C1002", "bill_id": "B1005"},
        "note": "Send payment request for overdue bill",
    },

    "enable_roaming": {
        "group": "agent", "type": "write",
        "force_tool": "enable_roaming",
        "messages": [
            {"role": "user", "content": "Customer C1001 is traveling abroad. Enable roaming on line L1001."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_id",
                 "input": {"customer_id": "C1001"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1001},
            ]},
            {"role": "assistant", "content": "I'll enable roaming on line L1001 for customer C1001 at no charge. Proceed?"},
            {"role": "user", "content": "Yes, enable it."},
        ],
        "expected_tool": "enable_roaming",
        "expected_args": {"customer_id": "C1001", "line_id": "L1001"},
        "note": "Enable international roaming",
    },

    "disable_roaming": {
        "group": "agent", "type": "write",
        "force_tool": "disable_roaming",
        "messages": [
            {"role": "user", "content": "Customer C1001 is back home. Disable roaming on line L1002."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_id",
                 "input": {"customer_id": "C1001"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1001},
            ]},
            {"role": "assistant", "content": "I'll disable roaming on line L1002 for customer C1001. Proceed?"},
            {"role": "user", "content": "Yes, disable it."},
        ],
        "expected_tool": "disable_roaming",
        "expected_args": {"customer_id": "C1001", "line_id": "L1002"},
        "note": "Disable international roaming",
    },

    "refuel_data": {
        "group": "agent", "type": "write",
        "force_tool": "refuel_data",
        "messages": [
            {"role": "user", "content": "Add 2 GB of data to line L1002 for customer C1001."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_data_usage",
                 "input": {"customer_id": "C1001", "line_id": "L1002"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": json.dumps({
                    "line_id": "L1002", "data_used_gb": 8.7, "data_limit_gb": 15.0,
                    "data_refueling_gb": 0.0
                })},
            ]},
            {"role": "assistant", "content":
             "Adding 2 GB of data to line L1002. Premium Plan rate: $2.00/GB = $4.00 total. Proceed?"},
            {"role": "user", "content": "Yes, add the data."},
        ],
        "expected_tool": "refuel_data",
        "expected_args": {"customer_id": "C1001", "line_id": "L1002", "gb_amount": 2.0},
        "note": "Refuel 2GB data, Premium Plan $2/GB",
    },

    "transfer_to_human_agents": {
        "group": "agent", "type": "generic",
        "messages": [
            {"role": "user", "content":
             "I am John Smith, phone 555-123-2002. I need to speak with a human agent. "
             "I have a complex billing dispute that cannot be resolved automatically."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "get_customer_by_phone",
                 "input": {"phone_number": "555-123-2002"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": _CUSTOMER_C1001},
            ]},
            {"role": "assistant", "content":
             "I've verified your identity. A billing dispute is outside my scope. "
             "Transferring you to a human agent now."},
            {"role": "user", "content": "Yes, please transfer me."},
        ],
        "expected_tool": "transfer_to_human_agents",
        "expected_args": {},
        "note": "Transfer to human agent",
    },

    # ── User READ ─────────────────────────────────────────────────

    "check_status_bar": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "What does your phone's status bar show right now?"},
        ],
        "expected_tool": "check_status_bar",
        "expected_args": {},
        "note": "Read status bar icons",
    },

    "check_network_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check your phone's current network connection status."},
        ],
        "expected_tool": "check_network_status",
        "expected_args": {},
        "note": "Check cellular + WiFi status",
    },

    "check_network_mode_preference": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "What network mode is your phone currently set to prefer?"},
        ],
        "expected_tool": "check_network_mode_preference",
        "expected_args": {},
        "note": "Check preferred network mode (5G/4G/3G/2G)",
    },

    "run_speed_test": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Run a speed test on your phone to check the internet speed."},
        ],
        "expected_tool": "run_speed_test",
        "expected_args": {},
        "note": "Measure current connection speed",
    },

    "check_sim_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check the SIM card status on your phone."},
        ],
        "expected_tool": "check_sim_status",
        "expected_args": {},
        "note": "Check SIM active/missing/locked",
    },

    "check_data_restriction_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check if data saver mode is currently active on your phone."},
        ],
        "expected_tool": "check_data_restriction_status",
        "expected_args": {},
        "note": "Check data saver status",
    },

    "check_apn_settings": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check the APN settings on your phone."},
        ],
        "expected_tool": "check_apn_settings",
        "expected_args": {},
        "note": "Read APN / MMSC configuration",
    },

    "check_wifi_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check your phone's WiFi connection status."},
        ],
        "expected_tool": "check_wifi_status",
        "expected_args": {},
        "note": "Check WiFi on/off and connected network",
    },

    "check_wifi_calling_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Is WiFi Calling enabled on your phone?"},
        ],
        "expected_tool": "check_wifi_calling_status",
        "expected_args": {},
        "note": "Check WiFi Calling setting",
    },

    "check_vpn_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check if a VPN is currently active on your phone."},
        ],
        "expected_tool": "check_vpn_status",
        "expected_args": {},
        "note": "Check VPN connected/disconnected",
    },

    "check_installed_apps": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "List all the apps installed on your phone."},
        ],
        "expected_tool": "check_installed_apps",
        "expected_args": {},
        "note": "List installed apps",
    },

    "check_app_status": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Check the status and permissions for the messaging app on your phone."},
        ],
        "expected_tool": "check_app_status",
        "expected_args": {"app_name": "messaging"},
        "note": "Check messaging app permissions",
    },

    "check_app_permissions": {
        "group": "user", "type": "read",
        "force_tool": "check_app_permissions",
        "messages": [
            {"role": "user", "content": "Use check_app_permissions to check what permissions the messaging app has on your phone."},
        ],
        "expected_tool": "check_app_permissions",
        "expected_args": {"app_name": "messaging"},
        "note": "Check app permission details",
    },

    "can_send_mms": {
        "group": "user", "type": "read",
        "messages": [
            {"role": "user", "content": "Can your messaging app currently send MMS (picture) messages?"},
        ],
        "expected_tool": "can_send_mms",
        "expected_args": {},
        "note": "Check MMS capability",
    },

    "check_payment_request": {
        "group": "user", "type": "read",
        "force_tool": "check_payment_request",
        "messages": [
            {"role": "user", "content": "Use check_payment_request to see if the agent has sent you a payment request."},
        ],
        "expected_tool": "check_payment_request",
        "expected_args": {},
        "note": "Check pending payment request",
    },

    # ── User WRITE ────────────────────────────────────────────────

    "set_network_mode_preference": {
        "group": "user", "type": "write",
        "force_tool": "set_network_mode_preference",
        "messages": [
            {"role": "user", "content": "Set your phone's preferred network mode to 4G/5G."},
            {"role": "assistant", "content": "I'll set your phone to prefer 4G/5G networks. Proceed?"},
            {"role": "user", "content": "Yes, set it to 4G/5G preferred."},
        ],
        "expected_tool": "set_network_mode_preference",
        "expected_args": {"mode": "4g_5g_preferred"},
        "note": "Change network mode preference",
    },

    "toggle_airplane_mode": {
        "group": "user", "type": "write",
        "force_tool": "toggle_airplane_mode",
        "messages": [
            {"role": "user", "content": "Toggle airplane mode on your phone to refresh the connection."},
            {"role": "assistant", "content": "I'll toggle airplane mode to refresh your network connection. Proceed?"},
            {"role": "user", "content": "Yes, toggle it."},
        ],
        "expected_tool": "toggle_airplane_mode",
        "expected_args": {},
        "note": "Toggle airplane mode on/off",
    },

    "toggle_data": {
        "group": "user", "type": "write",
        "force_tool": "toggle_data",
        "messages": [
            {"role": "user", "content": "Toggle mobile data on your phone."},
            {"role": "assistant", "content": "I'll toggle mobile data. This will turn it off then back on. Proceed?"},
            {"role": "user", "content": "Yes, toggle it."},
        ],
        "expected_tool": "toggle_data",
        "expected_args": {},
        "note": "Toggle mobile data on/off",
    },

    "toggle_roaming": {
        "group": "user", "type": "write",
        "force_tool": "toggle_roaming",
        "messages": [
            {"role": "user", "content": "Toggle data roaming on your phone."},
            {"role": "assistant", "content": "I'll toggle data roaming on your device. Proceed?"},
            {"role": "user", "content": "Yes, toggle roaming."},
        ],
        "expected_tool": "toggle_roaming",
        "expected_args": {},
        "note": "Toggle data roaming setting",
    },

    "toggle_data_saver_mode": {
        "group": "user", "type": "write",
        "force_tool": "toggle_data_saver_mode",
        "messages": [
            {"role": "user", "content": "Toggle data saver mode on your phone."},
            {"role": "assistant", "content": "I'll toggle data saver mode. Proceed?"},
            {"role": "user", "content": "Yes, toggle it."},
        ],
        "expected_tool": "toggle_data_saver_mode",
        "expected_args": {},
        "note": "Toggle data saver mode",
    },

    "reset_apn_settings": {
        "group": "user", "type": "write",
        "force_tool": "reset_apn_settings",
        "messages": [
            {"role": "user", "content": "Reset the APN settings on your phone to carrier defaults."},
            {"role": "assistant", "content": "I'll reset your APN settings to defaults. Proceed?"},
            {"role": "user", "content": "Yes, reset them."},
        ],
        "expected_tool": "reset_apn_settings",
        "expected_args": {},
        "note": "Reset APN to carrier defaults",
    },

    "set_apn_settings": {
        "group": "user", "type": "write",
        "force_tool": "set_apn_settings",
        "messages": [
            {"role": "user", "content":
             "Set the APN settings on your phone: apn_name='internet', "
             "mmsc_url='http://mms.carrier.com/mms/wapenc', reset_at_reboot=False."},
            {"role": "assistant", "content":
             "I'll set the APN to 'internet' with MMSC URL 'http://mms.carrier.com/mms/wapenc'. Proceed?"},
            {"role": "user", "content": "Yes, set those APN settings."},
        ],
        "expected_tool": "set_apn_settings",
        "expected_args": {},
        "note": "Configure APN settings manually",
    },

    "toggle_wifi": {
        "group": "user", "type": "write",
        "force_tool": "toggle_wifi",
        "messages": [
            {"role": "user", "content": "Toggle WiFi on your phone."},
            {"role": "assistant", "content": "I'll toggle WiFi on your device. Proceed?"},
            {"role": "user", "content": "Yes, toggle WiFi."},
        ],
        "expected_tool": "toggle_wifi",
        "expected_args": {},
        "note": "Toggle WiFi radio",
    },

    "toggle_wifi_calling": {
        "group": "user", "type": "write",
        "force_tool": "toggle_wifi_calling",
        "messages": [
            {"role": "user", "content": "Toggle WiFi Calling on your phone."},
            {"role": "assistant", "content": "I'll toggle WiFi Calling on your device. Proceed?"},
            {"role": "user", "content": "Yes, toggle WiFi Calling."},
        ],
        "expected_tool": "toggle_wifi_calling",
        "expected_args": {},
        "note": "Toggle WiFi Calling feature",
    },

    "connect_vpn": {
        "group": "user", "type": "write",
        "force_tool": "connect_vpn",
        "messages": [
            {"role": "user", "content": "Connect to VPN on your phone."},
            {"role": "assistant", "content": "I'll connect your phone to the VPN. Proceed?"},
            {"role": "user", "content": "Yes, connect VPN."},
        ],
        "expected_tool": "connect_vpn",
        "expected_args": {},
        "note": "Connect to VPN",
    },

    "disconnect_vpn": {
        "group": "user", "type": "write",
        "force_tool": "disconnect_vpn",
        "messages": [
            {"role": "user", "content": "Disconnect the VPN on your phone."},
            {"role": "assistant", "content": "I'll disconnect the VPN on your device. Proceed?"},
            {"role": "user", "content": "Yes, disconnect VPN."},
        ],
        "expected_tool": "disconnect_vpn",
        "expected_args": {},
        "note": "Disconnect active VPN",
    },

    "grant_app_permission": {
        "group": "user", "type": "write",
        "force_tool": "grant_app_permission",
        "messages": [
            {"role": "user", "content": "Grant SMS permission to the messaging app on your phone."},
            {"role": "assistant", "content": "I'll grant SMS permission to the messaging app. Proceed?"},
            {"role": "user", "content": "Yes, grant it."},
        ],
        "expected_tool": "grant_app_permission",
        "expected_args": {"app_name": "messaging", "permission": "sms"},
        "note": "Grant SMS permission to messaging app",
    },

    "reseat_sim_card": {
        "group": "user", "type": "write",
        "force_tool": "reseat_sim_card",
        "messages": [
            {"role": "user", "content": "Try reseating the SIM card in your phone."},
            {"role": "assistant", "content": "I'll reseat your SIM card to fix any recognition issues. Proceed?"},
            {"role": "user", "content": "Yes, reseat the SIM."},
        ],
        "expected_tool": "reseat_sim_card",
        "expected_args": {},
        "note": "Remove and reinsert SIM card",
    },

    "reboot_device": {
        "group": "user", "type": "write",
        "force_tool": "reboot_device",
        "messages": [
            {"role": "user", "content": "Please restart your phone."},
            {"role": "assistant", "content": "I'll restart your phone to refresh all connections. Proceed?"},
            {"role": "user", "content": "Yes, restart the phone."},
        ],
        "expected_tool": "reboot_device",
        "expected_args": {},
        "note": "Restart device",
    },

    "make_payment": {
        "group": "user", "type": "write",
        "force_tool": "make_payment",
        "messages": [
            {"role": "user", "content": "Pay the bill that the agent sent you."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "check_payment_request",
                 "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001",
                 "content": "You have a payment request for bill B1005 of 425.0 USD."},
            ]},
            {"role": "assistant", "content": "There is a payment request for $425.00 (bill B1005). Pay now?"},
            {"role": "user", "content": "Yes, make the payment now."},
        ],
        "expected_tool": "make_payment",
        "expected_args": {},
        "note": "Make payment for pending bill",
    },

}


# ══════════════════════════════════════════════════════════════════
# Schema generation — agent + user schemas combined
# ══════════════════════════════════════════════════════════════════

def get_schemas_anthropic(agent: TelecomTools, user: TelecomUserTools) -> list[dict]:
    schemas = []
    for name, tool in agent.get_tools().items():
        fn = tool.openai_schema["function"]
        schemas.append({"name": fn["name"], "description": fn["description"],
                         "input_schema": fn["parameters"]})
    for name, tool in user.get_tools().items():
        fn = tool.openai_schema["function"]
        schemas.append({"name": fn["name"], "description": fn["description"],
                         "input_schema": fn["parameters"]})
    return schemas


def get_schemas_openai(agent: TelecomTools, user: TelecomUserTools) -> list[dict]:
    schemas = []
    for tool in agent.get_tools().values():
        schemas.append(tool.openai_schema)
    for tool in user.get_tools().values():
        schemas.append(tool.openai_schema)
    return schemas


# ══════════════════════════════════════════════════════════════════
# Tool execution
# ══════════════════════════════════════════════════════════════════

def execute_tool(agent: TelecomTools, user: TelecomUserTools,
                 tool_name: str, tool_input: dict) -> str:
    from datetime import date, datetime
    from pydantic import BaseModel

    def serialize(obj):
        if isinstance(obj, BaseModel):          return obj.model_dump()
        elif isinstance(obj, (datetime, date)): return obj.isoformat()
        elif isinstance(obj, list):             return [serialize(i) for i in obj]
        elif isinstance(obj, tuple):            return [serialize(i) for i in obj]
        elif isinstance(obj, dict):             return {k: serialize(v) for k, v in obj.items()}
        return obj

    try:
        if agent.has_tool(tool_name):
            result = agent.use_tool(tool_name, **tool_input)
        else:
            result = user.use_tool(tool_name, **tool_input)
        return json.dumps(serialize(result), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ══════════════════════════════════════════════════════════════════
# API runners
# ══════════════════════════════════════════════════════════════════

def run_anthropic(messages: list, agent: TelecomTools, user: TelecomUserTools,
                  force_tool: str = None) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs = dict(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=get_policy(),
        tools=get_schemas_anthropic(agent, user),
        messages=messages,
    )
    if force_tool:
        kwargs["tool_choice"] = {"type": "tool", "name": force_tool}
    response = client.messages.create(**kwargs)
    for block in response.content:
        if block.type == "tool_use":
            return {"called": True, "name": block.name, "input": block.input, "id": block.id}
    return {"called": False, "stop_reason": response.stop_reason}


def run_openai(messages: list, agent: TelecomTools, user: TelecomUserTools,
               force_tool: str = None) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    oai_messages = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, list):
            tool_uses    = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
            tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
            if tool_uses:
                oai_messages.append({
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": b["id"], "type": "function",
                        "function": {"name": b["name"], "arguments": json.dumps(b["input"])}
                    } for b in tool_uses]
                })
            elif tool_results:
                for tr in tool_results:
                    oai_messages.append({"role": "tool", "tool_call_id": tr["tool_use_id"],
                                         "content": tr["content"]})
        else:
            oai_messages.append({"role": msg["role"], "content": content})
    oai_messages.insert(0, {"role": "system", "content": get_policy()})

    tc = {"type": "function", "function": {"name": force_tool}} if force_tool else "auto"
    response = client.chat.completions.create(
        model="gpt-4o",
        tools=get_schemas_openai(agent, user),
        tool_choice=tc,
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

def run_all(model: str = "anthropic", tool_filter=None, group_filter=None):
    agent, user = load_tools()

    if model == "anthropic":
        runner = lambda msgs, ft: run_anthropic(msgs, agent, user, ft)
    else:
        runner = lambda msgs, ft: run_openai(msgs, agent, user, ft)

    cases = {
        k: v for k, v in TEST_CASES.items()
        if (tool_filter is None or k == tool_filter)
        and (group_filter is None or v["group"] == group_filter)
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file  = f"telecom_results_{model}_{timestamp}.json"

    print(f"\n{'='*65}")
    print(f"Telecom Tool Benchmark — {model.upper()}  ({len(cases)} tools)")
    print(f"Agent: {len(agent.get_tools())}  User: {len(user.get_tools())}")
    if tool_filter:   print(f"Tool:  {tool_filter}")
    if group_filter:  print(f"Group: {group_filter}")
    print(f"{'='*65}\n")

    results = []
    total = passed = failed = errored = 0

    for i, (name, case) in enumerate(cases.items(), 1):
        total += 1
        turns = len([m for m in case["messages"] if m["role"] == "user"])
        print(f"[{i:02d}/{len(cases)}] [{case['group']:5}/{case['type']:7}] {name}  ({turns}-turn)")
        print(f"  note: {case['note']}")

        try:
            result = runner(case["messages"], case.get("force_tool"))
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
                    print(f"     actual: {result['name']}({json.dumps(result.get('input',{}))[:100]})")

            results.append({"tool": name, "group": case["group"], "type": case["type"],
                             "ok": ok, "issues": issues, "result": result})
        except Exception as e:
            errored += 1
            print(f"  ⚠️  Error: {e}")
            results.append({"tool": name, "group": case["group"], "type": case["type"],
                             "ok": False, "error": str(e)})

        time.sleep(0.4)
        print()

    pct = 100 * passed // total if total else 0
    print(f"{'='*65}")
    print(f"RESULTS — {model.upper()}")
    print(f"  Total:    {total}")
    print(f"  ✅ Pass:  {passed}  ({pct}%)")
    print(f"  ❌ Fail:  {failed}")
    print(f"  ⚠️  Error: {errored}")
    for grp in ["agent", "user"]:
        g = [r for r in results if r.get("group") == grp]
        ok = sum(1 for r in g if r.get("ok"))
        if g: print(f"  {grp.upper():6} {ok}/{len(g)}")
    print(f"{'='*65}")

    failed_list = [r for r in results if not r.get("ok")]
    if failed_list:
        print(f"\nFailed: {[r['tool'] for r in failed_list]}")

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
    parser = argparse.ArgumentParser(description="Telecom Tool Benchmark")
    parser.add_argument("--model",  default="anthropic", choices=["anthropic","openai","both"])
    parser.add_argument("--tool",   default=None, help=f"Single tool")
    parser.add_argument("--group",  default=None, choices=["agent","user"])
    args = parser.parse_args()

    if args.model in ("anthropic","both") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: set ANTHROPIC_API_KEY"); sys.exit(1)
    if args.model in ("openai","both") and not os.environ.get("OPENAI_API_KEY"):
        print("Error: set OPENAI_API_KEY"); sys.exit(1)

    if args.model == "both":
        run_all("anthropic", args.tool, args.group)
        print()
        run_all("openai",    args.tool, args.group)
    else:
        run_all(args.model, args.tool, args.group)
