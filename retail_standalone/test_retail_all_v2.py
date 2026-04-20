"""
test_retail_all_v2.py — TAU2 Retail 全工具 Benchmark（修复版）

修复说明（相比 v1）：
  1. get_product/item_details — 加入邮箱认证历史
  2. calculate / transfer — 加入认证上下文
  3. modify_pending_order_payment — 换用余额充足的用户 (omar_kim_3528)
  4. modify_pending_order_items / exchange — 在历史里预包含 get_item_details 结果
  5. modify_user_address / return_delivered — 补充完整历史

用法：
  export ANTHROPIC_API_KEY=sk-ant-...
  python test_retail_all_v2.py
  python test_retail_all_v2.py --model openai
  python test_retail_all_v2.py --model both
  python test_retail_all_v2.py --domain read
  python test_retail_all_v2.py --domain write
  python test_retail_all_v2.py --tool cancel_pending_order
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from data_model import RetailDB
from tools import RetailTools

DB_PATH     = Path(__file__).parent / "db.json"
POLICY_PATH = Path(__file__).parent / "policy.md"


def load_tools() -> RetailTools:
    db = RetailDB.load(str(DB_PATH))
    return RetailTools(db)


def get_policy() -> str:
    return POLICY_PATH.read_text() if POLICY_PATH.exists() else \
        "You are a retail customer service agent."


# ══════════════════════════════════════════════════════════════════
# Pre-built tool result stubs (all data from real db.json)
# ══════════════════════════════════════════════════════════════════

_USER_RAJ = json.dumps({
    "user_id": "raj_sanchez_2970",
    "name": {"first_name": "Raj", "last_name": "Sanchez"},
    "email": "raj.sanchez2046@example.com",
    "address": {
        "address1": "557 Sunset Drive", "address2": "Suite 454",
        "city": "San Diego", "state": "CA", "country": "USA", "zip": "92147"
    },
    "payment_methods": {
        "credit_card_3362387": {
            "source": "credit_card", "id": "credit_card_3362387",
            "brand": "mastercard", "last_four": "2130"
        },
        "gift_card_2259499": {
            "source": "gift_card", "id": "gift_card_2259499", "balance": 30.0
        }
    },
    "orders": ["#W4566809", "#W7736708", "#W1067251"]
})

# omar_kim_3528: gift_card balance $91 > order $53.43 → enough for modify_payment
_USER_OMAR = json.dumps({
    "user_id": "omar_kim_3528",
    "name": {"first_name": "Omar", "last_name": "Kim"},
    "email": "omar.kim8981@example.com",
    "address": {
        "address1": "542 Lakeview Drive", "address2": "Suite 811",
        "city": "Jacksonville", "state": "FL", "country": "USA", "zip": "32214"
    },
    "payment_methods": {
        "gift_card_3749819": {
            "source": "gift_card", "id": "gift_card_3749819", "balance": 91.0
        },
        "credit_card_3577130": {
            "source": "credit_card", "id": "credit_card_3577130",
            "brand": "visa", "last_four": "5678"
        }
    },
    "orders": ["#W1080318"]
})

_ORDER_PENDING = json.dumps({
    "order_id": "#W4566809",
    "user_id": "raj_sanchez_2970",
    "status": "pending",
    "address": {
        "address1": "557 Sunset Drive", "address2": "Suite 454",
        "city": "San Diego", "state": "CA", "country": "USA", "zip": "92147"
    },
    "items": [
        {
            "item_id": "1569829406", "product_id": "2985987096",
            "name": "Indoor Security Camera", "price": 320.55,
            "options": {"resolution": "1080p", "field of view": "160 degrees", "connectivity": "Ethernet"}
        },
        {
            "item_id": "5826601160", "product_id": "2941248747",
            "name": "Air Purifier", "price": 506.15,
            "options": {"room size": "medium", "filter type": "carbon", "features": "night mode"}
        }
    ],
    "payment_history": [
        {"transaction_type": "payment", "amount": 826.70, "payment_method_id": "credit_card_3362387"}
    ],
    "fulfillments": [],
    "cancel_reason": None,
})

# Omar's small T-Shirt order — credit card, $53.43
_ORDER_OMAR_PENDING = json.dumps({
    "order_id": "#W1080318",
    "user_id": "omar_kim_3528",
    "status": "pending",
    "address": {
        "address1": "542 Lakeview Drive", "address2": "Suite 811",
        "city": "Jacksonville", "state": "FL", "country": "USA", "zip": "32214"
    },
    "items": [
        {
            "item_id": "8349118980", "product_id": "9523456873",
            "name": "T-Shirt", "price": 53.43,
            "options": {"color": "blue", "size": "S", "material": "cotton", "style": "v-neck"}
        }
    ],
    "payment_history": [
        {"transaction_type": "payment", "amount": 53.43, "payment_method_id": "credit_card_3577130"}
    ],
    "fulfillments": [],
    "cancel_reason": None,
})

_ORDER_DELIVERED = json.dumps({
    "order_id": "#W7736708",
    "user_id": "raj_sanchez_2970",
    "status": "delivered",
    "address": {
        "address1": "557 Sunset Drive", "address2": "Suite 454",
        "city": "San Diego", "state": "CA", "country": "USA", "zip": "92147"
    },
    "items": [
        {
            "item_id": "3104857380", "product_id": "6992792935",
            "name": "Headphones", "price": 377.97,
            "options": {"type": "on-ear", "connectivity": "wireless", "color": "red"}
        },
        {
            "item_id": "9692325258", "product_id": "9016994464",
            "name": "Luggage Set", "price": 528.63,
            "options": {"piece count": "3-piece", "color": "black", "material": "softshell"}
        },
        {
            "item_id": "6574183535", "product_id": "8756423718",
            "name": "Notebook", "price": 28.14,
            "options": {"cover type": "hardcover", "pages": "200", "ruled": "yes"}
        },
        {
            "item_id": "1096508426", "product_id": "5327985468",
            "name": "Jigsaw Puzzle", "price": 46.13,
            "options": {"pieces": "1000", "theme": "nature", "difficulty": "medium"}
        }
    ],
    "payment_history": [
        {"transaction_type": "payment", "amount": 980.87, "payment_method_id": "credit_card_3362387"}
    ],
    "fulfillments": [{"tracking_id": ["TRK123456"],
                      "item_ids": ["3104857380", "9692325258", "6574183535", "1096508426"]}],
    "cancel_reason": None,
})

# Pre-verified item stubs to include in modify/exchange histories
_ITEM_8470360507 = json.dumps({
    "item_id": "8470360507",
    "options": {"resolution": "2K", "field of view": "130 degrees", "connectivity": "Ethernet"},
    "available": True, "price": 291.31
})

_ITEM_3374679624 = json.dumps({
    "item_id": "3374679624",
    "options": {"type": "over-ear", "connectivity": "wired", "color": "black"},
    "available": True, "price": 370.53
})


# ══════════════════════════════════════════════════════════════════
# 16 个工具测试用例（修复版）
# ══════════════════════════════════════════════════════════════════

TEST_CASES = {

    # ── READ ──────────────────────────────────────────────────────

    "find_user_id_by_email": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Can you find my account?"},
        ],
        "expected_tool": "find_user_id_by_email",
        "expected_args": {"email": "raj.sanchez2046@example.com"},
        "note": "Auth step 1: lookup by email",
    },

    "find_user_id_by_name_zip": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "I can't remember my email. My name is Raj Sanchez and my zip code is 92147."},
        ],
        "expected_tool": "find_user_id_by_name_zip",
        "expected_args": {"first_name": "Raj", "last_name": "Sanchez", "zip": "92147"},
        "note": "Auth step 1 alt: lookup by name + zip",
    },

    "get_user_details": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Show me my account details."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": "Identity verified. Let me pull up your full account."},
            {"role": "user", "content": "Yes, show me."},
        ],
        "expected_tool": "get_user_details",
        "expected_args": {"user_id": "raj_sanchez_2970"},
        "note": "After email auth, fetch full user profile",
    },

    "get_order_details": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. What is the status of order #W4566809?"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_2970"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content": "Identity verified. Let me look up order #W4566809."},
            {"role": "user", "content": "Yes please."},
        ],
        "expected_tool": "get_order_details",
        "expected_args": {"order_id": "#W4566809"},
        "note": "Lookup pending order after full auth",
    },

    "get_product_details": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Show me the details for product 9523456873 (T-Shirt)."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": "Identity verified. Let me pull up the T-Shirt product details."},
            {"role": "user", "content": "Yes, show me product 9523456873."},
        ],
        "expected_tool": "get_product_details",
        "expected_args": {"product_id": "9523456873"},
        "note": "Product catalog lookup after auth",
    },

    "get_item_details": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Check if item 9612497925 (T-Shirt blue M) is available."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": "Identity verified. Let me check item 9612497925."},
            {"role": "user", "content": "Yes, check it."},
        ],
        "expected_tool": "get_item_details",
        "expected_args": {"item_id": "9612497925"},
        "note": "Item availability check after auth",
    },

    "list_all_product_types": {
        "type": "read",
        "messages": [
            {"role": "user", "content":
             "What types of products do you sell? Show me the full list."},
        ],
        "expected_tool": "list_all_product_types",
        "expected_args": {},
        "note": "General catalog query, no auth needed",
    },

    # ── GENERIC ───────────────────────────────────────────────────

    "calculate": {
        "type": "generic",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Calculate 320.55 + 506.15 for me."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": "Identity verified. Let me calculate that."},
            {"role": "user", "content": "Please calculate 320.55 + 506.15."},
        ],
        "force_tool": "calculate",
        "expected_tool": "calculate",
        "expected_args": {"expression": "320.55 + 506.15"},
        "note": "Math in auth context",
    },

    "transfer_to_human_agents": {
        "type": "generic",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. I need a human agent. "
             "I have a billing dispute that your system cannot handle."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content":
             "Identity verified. A billing dispute is outside my scope. "
             "I will transfer you to a human agent now."},
            {"role": "user", "content": "Yes, transfer me now."},
        ],
        "expected_tool": "transfer_to_human_agents",
        "expected_args": {},
        "note": "Billing dispute, explicitly outside scope, transfer after auth",
    },

    # ── WRITE ─────────────────────────────────────────────────────

    "cancel_pending_order": {
        "type": "write",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Cancel order #W4566809 — ordered by mistake."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_order_details",
                 "input": {"order_id": "#W4566809"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _ORDER_PENDING},
            ]},
            {"role": "assistant", "content":
             "Cancelling order #W4566809 (Indoor Security Camera + Air Purifier). "
             "Reason: ordered by mistake. Refund $826.70 to mastercard 2130 in 5-7 business days. Proceed?"},
            {"role": "user", "content": "Yes, cancel it."},
        ],
        "force_tool": "cancel_pending_order",
        "expected_tool": "cancel_pending_order",
        "expected_args": {"order_id": "#W4566809", "reason": "ordered by mistake"},
        "note": "Cancel pending order",
    },

    "modify_pending_order_address": {
        "type": "write",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Change shipping address for order #W4566809 "
             "to 100 New Street, Apt 5, Los Angeles, CA, USA, 90001."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_order_details",
                 "input": {"order_id": "#W4566809"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _ORDER_PENDING},
            ]},
            {"role": "assistant", "content":
             "Updating shipping address for #W4566809 to: 100 New Street, Apt 5, Los Angeles, CA, USA 90001. Proceed?"},
            {"role": "user", "content": "Yes, update it."},
        ],
        "force_tool": "modify_pending_order_address",
        "expected_tool": "modify_pending_order_address",
        "expected_args": {
            "order_id": "#W4566809",
            "address1": "100 New Street",
            "city": "Los Angeles",
            "state": "CA",
            "country": "USA",
            "zip": "90001",
        },
        "note": "Change shipping address of pending order",
    },

    "modify_pending_order_payment": {
        "type": "write",
        # omar_kim_3528: order #W1080318 total $53.43, gift_card_3749819 balance $91 >= total
        "messages": [
            {"role": "user", "content":
             "My email is omar.kim8981@example.com. Change the payment for order #W1080318 "
             "to gift card gift_card_3749819."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "omar.kim8981@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"omar_kim_3528"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_order_details",
                 "input": {"order_id": "#W1080318"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _ORDER_OMAR_PENDING},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_003", "name": "get_user_details",
                 "input": {"user_id": "omar_kim_3528"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_003", "content": _USER_OMAR},
            ]},
            {"role": "assistant", "content":
             "Changing payment for #W1080318 (T-Shirt $53.43) from Visa 5678 "
             "to gift_card_3749819 (balance $91.00 >= $53.43). Proceed?"},
            {"role": "user", "content": "Yes, change the payment."},
        ],
        "force_tool": "modify_pending_order_payment",
        "expected_tool": "modify_pending_order_payment",
        "expected_args": {"order_id": "#W1080318", "payment_method_id": "gift_card_3749819"},
        "note": "Change payment: credit → gift card ($91 >= $53.43 order total)",
    },

    "modify_pending_order_items": {
        "type": "write",
        # Swap 1569829406 → 8470360507, new item already verified in history
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. In order #W4566809, change the Indoor Security Camera "
             "(item 1569829406) to the 2K version (item 8470360507). Use credit_card_3362387 for the price difference."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_order_details",
                 "input": {"order_id": "#W4566809"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _ORDER_PENDING},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_003", "name": "get_item_details",
                 "input": {"item_id": "8470360507"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_003", "content": _ITEM_8470360507},
            ]},
            {"role": "assistant", "content":
             "Modifying order #W4566809:\n"
             "- Indoor Security Camera 1080p (1569829406, $320.55) → 2K (8470360507, $291.31)\n"
             "- Refund $29.24 to mastercard 2130\n"
             "Is this the only item you want to change?"},
            {"role": "user", "content": "Yes, that is the only item. I have no other changes."},
            {"role": "assistant", "content": "Confirmed — only item 1569829406 will be changed to 8470360507. Shall I proceed with this modification?"},
            {"role": "user", "content": "Yes, proceed now."},
            {"role": "assistant", "content": "Please note: this action will change the order status to 'pending (item modified)' and the order cannot be modified or cancelled afterwards. Do you still want to proceed?"},
            {"role": "user", "content": "Yes, I understand. Please proceed with the modification now."},
        ],
        "force_tool": "modify_pending_order_items",
        "expected_tool": "modify_pending_order_items",
        "expected_args": {
            "order_id": "#W4566809",
            "item_ids": ["1569829406"],
            "new_item_ids": ["8470360507"],
            "payment_method_id": "credit_card_3362387",
        },
        "note": "Swap 1 item, new item pre-verified in history",
    },

    "modify_user_address": {
        "type": "write",
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Update my default address "
             "to 200 Ocean Ave, Unit 3B, Santa Monica, CA, USA, 90401."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_2970"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content":
             "I will update your default address to:\n"
             "200 Ocean Ave, Unit 3B, Santa Monica, CA, USA 90401\n"
             "Shall I proceed with this change?"},
            {"role": "user", "content": "Yes, that is correct. Please update my address now."},
        ],
        "force_tool": "modify_user_address",
        "expected_tool": "modify_user_address",
        "expected_args": {
            "user_id": "raj_sanchez_2970",
            "address1": "200 Ocean Ave",
            "city": "Santa Monica",
            "state": "CA",
            "country": "USA",
            "zip": "90401",
        },
        "note": "Update user default address, get_user_details in history",
    },

    "return_delivered_order_items": {
        "type": "write",
        # Headphones 3104857380, refund to credit_card_3362387 = original payment → policy OK
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Return the Headphones from order #W7736708. "
             "Refund to credit_card_3362387."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_order_details",
                 "input": {"order_id": "#W7736708"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _ORDER_DELIVERED},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_003", "name": "get_user_details",
                 "input": {"user_id": "raj_sanchez_2970"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_003", "content": _USER_RAJ},
            ]},
            {"role": "assistant", "content":
             "Processing return for order #W7736708:\n"
             "- Returning: Headphones (item 3104857380, $377.97)\n"
             "- Refund: $377.97 to mastercard 2130 (original payment, 5-7 business days)\n"
             "Is this the only item you want to return?"},
            {"role": "user", "content": "Yes, that is the only item. I have no other items to return."},
            {"role": "assistant", "content": "Confirmed — only item 3104857380 will be returned, refund $377.97 to mastercard 2130. Shall I proceed?"},
            {"role": "user", "content": "Yes, proceed now."},
        ],
        "force_tool": "return_delivered_order_items",
        "expected_tool": "return_delivered_order_items",
        "expected_args": {
            "order_id": "#W7736708",
            "item_ids": ["3104857380"],
            "payment_method_id": "credit_card_3362387",
        },
        "note": "Return 1 item, refund to original credit card",
    },

    "exchange_delivered_order_items": {
        "type": "write",
        # Exchange 3104857380 → 3374679624, new item pre-verified
        "messages": [
            {"role": "user", "content":
             "My email is raj.sanchez2046@example.com. Exchange the Headphones in order #W7736708 "
             "for the over-ear wired black version (item 3374679624). Use credit_card_3362387."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "find_user_id_by_email",
                 "input": {"email": "raj.sanchez2046@example.com"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "content": '"raj_sanchez_2970"'},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "get_order_details",
                 "input": {"order_id": "#W7736708"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_002", "content": _ORDER_DELIVERED},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_003", "name": "get_item_details",
                 "input": {"item_id": "3374679624"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_003", "content": _ITEM_3374679624},
            ]},
            {"role": "assistant", "content":
             "Exchanging in order #W7736708:\n"
             "- Headphones on-ear wireless red (3104857380, $377.97) → over-ear wired black (3374679624, $370.53)\n"
             "- Refund $7.44 to mastercard 2130\n"
             "Is this the only item you want to exchange?"},
            {"role": "user", "content": "Yes, that is the only item. I have no other items to exchange."},
            {"role": "assistant", "content": "Confirmed — only item 3104857380 will be exchanged for 3374679624. Please note this action can only be done once per order. Shall I proceed?"},
            {"role": "user", "content": "Yes, I understand this can only be done once. Please proceed with the exchange now."},
        ],
        "force_tool": "exchange_delivered_order_items",
        "expected_tool": "exchange_delivered_order_items",
        "expected_args": {
            "order_id": "#W7736708",
            "item_ids": ["3104857380"],
            "new_item_ids": ["3374679624"],
            "payment_method_id": "credit_card_3362387",
        },
        "note": "Exchange 1 item, new item pre-verified in history",
    },

}


# ══════════════════════════════════════════════════════════════════
# Schema generation
# ══════════════════════════════════════════════════════════════════

def get_schemas_anthropic(tools: RetailTools) -> list[dict]:
    schemas = []
    for name, tool in tools.get_tools().items():
        fn = tool.openai_schema["function"]
        schemas.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
        })
    return schemas


def get_schemas_openai(tools: RetailTools) -> list[dict]:
    return [tool.openai_schema for tool in tools.get_tools().values()]


# ══════════════════════════════════════════════════════════════════
# Tool execution
# ══════════════════════════════════════════════════════════════════

def execute_tool(tools: RetailTools, tool_name: str, tool_input: dict) -> str:
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
        result = tools.use_tool(tool_name, **tool_input)
        return json.dumps(serialize(result), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ══════════════════════════════════════════════════════════════════
# API runners
# ══════════════════════════════════════════════════════════════════

def run_anthropic(messages: list, tools: RetailTools, force_tool: str = None) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs = dict(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=get_policy(),
        tools=get_schemas_anthropic(tools),
        messages=messages,
    )
    if force_tool:
        kwargs["tool_choice"] = {"type": "tool", "name": force_tool}
    response = client.messages.create(**kwargs)
    for block in response.content:
        if block.type == "tool_use":
            return {"called": True, "name": block.name, "input": block.input, "id": block.id}
    return {"called": False, "stop_reason": response.stop_reason}


def run_openai(messages: list, tools: RetailTools, force_tool: str = None) -> dict:
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
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_use_id"],
                        "content": tr["content"],
                    })
        else:
            oai_messages.append({"role": msg["role"], "content": content})

    oai_messages.insert(0, {"role": "system", "content": get_policy()})

    tc = {"type": "function", "function": {"name": force_tool}} if force_tool else "auto"
    response = client.chat.completions.create(
        model="gpt-4o",
        tools=get_schemas_openai(tools),
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

def run_all(model: str = "anthropic", tool_filter=None, domain_filter=None):
    tools = load_tools()
    runner = run_anthropic if model == "anthropic" else run_openai

    cases = {
        k: v for k, v in TEST_CASES.items()
        if (tool_filter is None or k == tool_filter)
        and (domain_filter is None or v["type"] == domain_filter)
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file  = f"retail_results_{model}_{timestamp}.json"

    print(f"\n{'='*65}")
    print(f"Retail Tool Benchmark v2 — {model.upper()}  ({len(cases)} tools)")
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
            result = runner(case["messages"], tools, force_tool=case.get("force_tool"))
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
    parser = argparse.ArgumentParser(description="Retail Tool Benchmark v2")
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
