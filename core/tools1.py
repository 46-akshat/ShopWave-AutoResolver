import asyncio
import random
import json
import os
import datetime
from enum import Enum
from typing import Dict, Any
from langchain.tools import tool



# ==========================================
# 1. ENUMS & DATABASE SETUP
# ==========================================
# class CustomerTier(str, Enum):
#     STANDARD = "standard"
#     PREMIUM = "premium"
#     VIP = "vip"



BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "mockdata")

def load_mock_db(filename: str, key_field: str = None) -> dict:
    """Loads JSON data and transforms lists into O(1) lookup dictionaries."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            if isinstance(data, list) and key_field:
                return {item[key_field]: item for item in data if key_field in item}
            return data
    except Exception as e:
        print(f"Warning: {filename} not found. Error: {e}")
        return {}

# Key mappings verified for your JSON structure
ORDERS_DB = load_mock_db("orders.json", key_field="order_id")
PRODUCTS_DB = load_mock_db("products.json", key_field="product_id")
CUSTOMERS_DB = load_mock_db("customers.json", key_field="email")


# 2. LOOKUP TOOLS (READ)

@tool
async def get_order(order_id: str) -> Dict[str, Any]:
    """Mock tool: Fetches order details. Injects fallback date if missing."""
    await asyncio.sleep(random.uniform(0.2, 0.4))
    if order_id not in ORDERS_DB:
        return {"status": "error", "message": f"Order {order_id} not found."}
    
    order_data = ORDERS_DB[order_id].copy()
    if "order_date" not in order_data:
        # Reference date: April 17, 2026. Fallback is 10 days prior.
        fake_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)
        order_data["order_date"] = fake_date.strftime("%Y-%m-%d")
    return order_data

@tool
async def get_customer(email: str) -> Dict[str, Any]:
    """Mock tool: Retrieves customer profile and history."""
    await asyncio.sleep(0.2)
    return CUSTOMERS_DB.get(email, {"status": "error", "message": "Customer not found."})
@tool
async def get_product(product_id: str) -> Dict[str, Any]:
    """Mock tool: Retrieves product metadata (category, warranty)."""
    await asyncio.sleep(0.2)
    return PRODUCTS_DB.get(product_id, {"status": "error", "message": "Product not found."})

@tool
async def search_knowledge_base(query: str) -> str:
    """Mock tool: Semantic search over the ShopWave Support KB."""
    await asyncio.sleep(0.4)
    q = query.lower()
    # --- Existing Policy Logic ---
    if "warranty" in q:
        return "KB: Warranty covers manufacturing defects. AI MUST NOT resolve; MUST escalate to Warranty Team."
    
    if "refund" in q or "return" in q:
        # Combined return windows and the $200 limit for efficiency
        return "KB: Window: Standard 30d, Access. 60d, Electronics 15d. Max refund $200. Standard returns must be unused/original packaging."
    
    if "tier" in q or "vip" in q:
        return "KB: VIP/Premium may have leniency. Always check customer notes for exceptions."

    # --- New FAQ Logic ---
    if any(word in q for word in ["how long", "timing", "status"]):
        return "FAQ: Refunds take 5–7 business days after approval. Arrival depends on the customer's bank."

    if "no order" in q or "forgot" in q:
        return "FAQ: You can look up orders using the customer's email address via the get_customer tool."

    if "fee" in q or "shipping" in q or "free" in q:
        return "FAQ: Returns are free for wrong/damaged items. Standard returns may incur a shipping fee."

    if "exchange" in q:
        return "FAQ: Exchanges for size/color are available subject to stock. Otherwise, a refund is issued."

    # --- Default Fallback ---
    return "Standard policy applies. Escalate for fraud, replacements, or items > $200."


# 3. ACTION TOOLS (WRITE/SAFEGUARD)

@tool
async def check_refund_eligibility(order_id: str, customer_email: str = None) -> Dict[str, Any]:
    """
    Mock tool: Verifies system-level eligibility. 
    Flags fraud/conflicts based on order state and customer history.
     CRITICAL: This tool must ONLY be called if 'check_refund_eligibility' has 
    already returned 'eligible=True' for this specific order.
    """
    await asyncio.sleep(random.uniform(1.0, 1.5))
    
    # 20% Chaos Failure (Hackathon Constraint)
    if random.random() < 0.20:
        raise TimeoutError("Legacy Billing API failed to respond.")

    order = ORDERS_DB.get(order_id)
    if not order:
        return {"eligible": False, "reason": "Order not found."}

    # CONFLICT CHECK: Already refunded?
    if order.get("refund_status") == "refunded":
        return {"eligible": False, "reason": "FRAUD/CONFLICT: Order already refunded in system."}

    # FRAUD CHECK: History analysis
    if customer_email and customer_email in CUSTOMERS_DB:
        hist = CUSTOMERS_DB[customer_email].get("notes", "")
        # if "4 refund requests" in hist.lower():
        #     return {"eligible": True, "warning": "HIGH REFUND FREQUENCY: Potential fraud pattern detected. Consider escalation."}
        if "refund" in hist:
    # If they've done it before, we don't block them, but we WARN the agent
         return {
        "eligible": True, 
        "warning": "Customer has a history of prior refunds. Verify item condition strictly.",
        "escalate_recommended": True # Hint to the AI to pass this to a human
    }

    return {"eligible": True, "reason": "System check passed. Verified delivered and non-refunded."}

@tool
async def issue_refund(order_id: str, amount: float) -> str:
    """
    Mock tool: IRREVERSIBLE ACTION. Enforces $200 safety limit.
    """
    await asyncio.sleep(1.0)
    
    # KB MANDATE: Refund > $200
    if amount > 200:
        return f"ERROR: Refund of ${amount} exceeds the $200 limit. Process Blocked. You MUST escalate."

    if order_id in ORDERS_DB:
        ORDERS_DB[order_id]["refund_status"] = "refunded"
        note = f" [REFUNDED: ${amount} by AI]"
        ORDERS_DB[order_id]["notes"] = ORDERS_DB[order_id].get("notes", "") + note

    return f"SUCCESS: Refund of ${amount} initiated for order {order_id}."

async def escalate(
    ticket_id: str, 
    reason: str, 
    attempts_made: str, 
    suggested_resolution: str, 
    priority: str = "medium"
) -> str:
    """
    Mock tool: Structured hand-off to human support.
    Required for: Warranty, replacements, $200+ refunds, or policy ambiguity.
    """
    await asyncio.sleep(0.3)
    # The return string provides the "Verified" and "Recommended" data points you requested
    return (
        f"ESCALATION SUCCESSFUL for Ticket {ticket_id}.\n"
        f"Priority: {priority.upper()}\n"
        f"Summary: {reason}\n"
        f"Actions Taken: {attempts_made}\n"
        f"Next Steps: {suggested_resolution}"
    )

@tool
async def send_reply(ticket_id: str, message: str) -> str:
    """Mock tool: Dispatches the final message to the customer."""
    await asyncio.sleep(0.3)
    return f"REPLY SENT: Ticket {ticket_id} has been messaged."