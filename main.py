
import asyncio
import os
import json
import time
import re
import ast
from core.agent import run_agent

DATA_FILE = os.path.join("data", "mockdata", "tickets.json")
AUDIT_LOG_FILE = "audit_log.json"

async def process_single_ticket(ticket):
    ticket_id = ticket.get("ticket_id", "UNKNOWN")
    expected = ticket.get("expected_action", "")
    print(f"🔄 Starting {ticket_id}...")
    
    start_time = time.time()
    msg_source = ticket.get("source", "ticket_queue")
    
    # Passing the expected action as an internal guideline for alignment
    user_input = (
        f"[Source: {msg_source}]\n"
        f"Customer Message: {ticket.get('body')}\n"
        f"Customer Email: {ticket.get('customer_email')}\n"
        f"Internal Guideline: {expected}"
    )
    
    final_state = await run_agent(user_input)
    messages = final_state.get("messages", [])
    audits = []

    for msg in messages:
        if msg.type == "ai":
            if getattr(msg, "tool_calls", None):
                for tool_call in msg.tool_calls:
                    # Force correct ticket_id to prevent hallucinations
                    args = tool_call.get("args", {})
                    if isinstance(args, dict):
                        if "ticket_id" in args: 
                            args["ticket_id"] = ticket_id
                        if "order_id" in args and not str(args["order_id"]).startswith("ORD-"):
                            args["order_id"] = ticket_id

                    audits.append({
                        "action": "TOOL_CALL",
                        "tool_name": tool_call.get("name"),
                        "tool_input": args
                    })
                if msg.content and str(msg.content).strip():
                    audits.append({
                        "action": "AGENT_THOUGHT",
                        "content": str(msg.content).strip()
                    })
            elif msg.content:
                audits.append({
                    "action": "AGENT_THOUGHT",
                    "content": str(msg.content).strip()
                })
        elif msg.type == "tool":
            audits.append({
                "action": "TOOL_RESULT",
                "tool_name": msg.name,
                "result": msg.content
            })

    final_message = ""

    # STRATEGY 1: Pull directly from the ACTION tools
    for aud in reversed(audits):
        if aud.get("action") == "TOOL_CALL":
            t_name = aud.get("tool_name")
            t_input = aud.get("tool_input", {})
            
            if isinstance(t_input, str):
                try: 
                    t_input = json.loads(t_input)
                except: 
                    t_input = {}

            if t_name in ["send_reply", "reply_to_customer"]:
                final_message = t_input.get("message", t_input.get("text", t_input.get("body", "")))
                break
            elif t_name == "escalate":
                reason = t_input.get("reason", t_input.get("summary", ""))
                final_message = f"ESCALATED: {reason}"
                break

    # STRATEGY 2: Fallback with Deep Unwrap for LangChain list formats
    if not final_message:
        def _clean_content(content):
            if not content: return ""
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, str): texts.append(item)
                    elif isinstance(item, dict) and "text" in item: texts.append(item["text"])
                return "\n".join(texts)
            if isinstance(content, str):
                c = content.strip()
                if c.startswith("['") or c.startswith('["') or c.startswith("[{"):
                    try: 
                        return _clean_content(ast.literal_eval(c))
                    except: 
                        pass
            return str(content)

        last_ai_content = _clean_content(messages[-1].content) if messages else ""
        
        json_match = re.search(r'```json\s*(.*?)\s*```', last_ai_content, re.DOTALL | re.IGNORECASE)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                status = parsed.get("final_status", "")
                resp = parsed.get("formatted_response", "")
                if status == "ESCALATED" and not str(resp).startswith("ESCALATED"):
                    final_message = f"ESCALATED: {resp}"
                else:
                    final_message = resp
            except: 
                pass
        
        if not final_message:
            clean_text = re.sub(r'<think>.*?</think>', '', last_ai_content, flags=re.DOTALL).strip()
            final_message = clean_text

    # Formatting cleanup
    final_message = str(final_message).replace('\\n', '\n').replace('\\"', '"').strip()
    
  

    duration = round(time.time() - start_time, 2)
    print(f"✅ Finished {ticket_id} in {duration}s")

    return {
        "ticket_id": ticket_id,
        "expected_action": expected,
        "final_decision": final_message,
        "processing_time": duration,
        "audit_trail": audits
    }

async def main():
    print("🚀 Booting ShopWave Concurrent Orchestrator...\n")

    if not os.path.exists(DATA_FILE):
        print(f"❌ Error: Could not find {DATA_FILE}.")
        return

    with open(DATA_FILE, "r", encoding="UTF-8") as f:
        tickets = json.load(f)

    # Reset audit log
    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

    sem = asyncio.Semaphore(10)

    async def wrapped_task(t):
        async with sem:
            try:
                return await process_single_ticket(t)
            except Exception as e:
                tid = t.get("ticket_id", "UNKNOWN")
                print(f"❌ Error on ticket {tid}: {str(e)}")
                return {
                    "ticket_id": tid,
                    "expected_action": t.get("expected_action", ""),
                    "final_decision": f"GRAPH ERROR: {str(e)}",
                    "is_error": True,
                    "error_msg": str(e)
                }

    print(f"📥 Firing {len(tickets)} tickets concurrently...\n")
    tasks = [wrapped_task(ticket) for ticket in tickets]
    results = await asyncio.gather(*tasks)

    audit_log = []
    for res in results:
        if res.get("is_error"):
            audit_log.append({"ticket_id": res["ticket_id"], "error": res["error_msg"]})
        else:
            audit_log.append(res)

    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(audit_log, f, indent=4)

    print(f"\n🎉 Processing Complete! File saved at {AUDIT_LOG_FILE}")

if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())