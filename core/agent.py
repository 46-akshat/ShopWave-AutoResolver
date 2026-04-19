from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated, Sequence
import operator
import os
import json
from dotenv import load_dotenv
import inspect

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, ToolMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing import Literal
from langgraph.graph import StateGraph, START, END

# Import phase 1 tools
from core.tools import (
    get_order, get_customer, get_product, search_knowledge_base,
    check_refund_eligibility, issue_refund, send_reply, escalate
)

load_dotenv()


# LOAD SYSTEM PROMPT 
def load_system_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompts.md")
    try:
        with open(prompt_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print("\n[CRITICAL WARNING] system_prompts.md NOT FOUND! Using default chat prompt.\n")
        return "You are a helpful support agent."

SYSTEM_INSTRUCTION = load_system_prompt()+"""
CRITICAL FINAL STEP:
When you have finished evaluating the logic and using tools, you MUST provide your final output in the following JSON format. Do not add any text before or after this JSON block.

```json
{
  "final_status": "ESCALATED" | "RESOLVED",
  "formatted_response": "The exact email message to send the customer OR the exact escalation summary."
}
"""

# Injected when the agent returns a blank response to force it to finish
NUDGE_MESSAGE = (
    "You have gathered all necessary information but did not take a final action. "
    "You MUST now call one of the following tools to close this ticket:\n"
    "- `send_reply`  → to respond directly to the customer\n"
    "- `escalate`    → to hand off to a human agent\n"
    "Do NOT return an empty response. Pick the correct action now."
)


# ── GRAPH STATE AND LLM SETUP ─────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    llm_calls: Annotated[int, operator.add]


llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0
)

tools_list = [
    get_order, get_customer, get_product, search_knowledge_base,
    check_refund_eligibility, issue_refund, send_reply, escalate
]
TOOL_MAP = {
    (tool.name if hasattr(tool, "name") else tool.__name__): tool
    for tool in tools_list
}
agent_brain = llm.bind_tools(tools_list)


# ── NODES ─────────────────────────────────────────────────────────────────────
async def agent_node(state: AgentState):
    """LLM decides whether to call a tool or produce a final reply."""
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_INSTRUCTION)] + list(messages)

    response = await agent_brain.ainvoke(messages)
    return {"messages": [response], "llm_calls": 1}


async def tool_node(state: AgentState):
    """Executes every tool call requested by the last AI message."""
    last_message = state["messages"][-1]
    tool_messages = []

    for tool_call in last_message.tool_calls:
        try:
            tool_obj = TOOL_MAP[tool_call["name"]]
            args = tool_call["args"]

            if hasattr(tool_obj, "ainvoke"):
                result = await tool_obj.ainvoke(args)
            elif inspect.iscoroutinefunction(tool_obj):
                result = await tool_obj(**args)
            else:
                result = tool_obj(**args)

            tool_messages.append(ToolMessage(
                content=json.dumps(result),
                tool_call_id=tool_call["id"]
            ))
        except TimeoutError as e:
            tool_messages.append(ToolMessage(
                content=f"TOOL ERROR: {str(e)}. Please retry or escalate per policy.",
                tool_call_id=tool_call["id"],
                status="error"
            ))

    return {"messages": tool_messages}


async def nudge_node(state: AgentState):
    """
    Injected when the agent returns a blank response with no tool calls.
    Appends a HumanMessage reminder so the agent is forced to finish
    with send_reply or escalate on its next turn.
    """
    print("[NUDGE] Agent returned blank response — injecting reminder.")
    return {"messages": [HumanMessage(content=NUDGE_MESSAGE)]}


# ── ROUTING ───────────────────────────────────────────────────────────────────
def should_continue(state: AgentState) -> str:
    """Route after every agent turn."""
    last_message = state["messages"][-1]

    # Circuit breaker
    if state.get("llm_calls", 0) > 5:
        print("[WARNING] Circuit breaker triggered — forcing END.")
        return END

    # Agent wants to call a tool
    if last_message.tool_calls:
        return "tool"

    # Agent returned blank — nudge instead of silently exiting
    if not last_message.content or not str(last_message.content).strip():
        return "nudge"

    # Agent produced a real reply — we're done
    return END


# ── BUILD AND COMPILE THE GRAPH ───────────────────────────────────────────────
agent_builder = StateGraph(AgentState)

agent_builder.add_node("agent", agent_node)
agent_builder.add_node("tool",  tool_node)
agent_builder.add_node("nudge", nudge_node)

agent_builder.add_edge(START, "agent")
agent_builder.add_conditional_edges(
    "agent",
    should_continue,
    ["tool", "nudge", END]
)
agent_builder.add_edge("tool",  "agent")
agent_builder.add_edge("nudge", "agent")

app = agent_builder.compile()


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
async def run_agent(ticket_input: str):
    """Entry point for a single ticket."""
    inputs = {
        "messages": [HumanMessage(content=ticket_input)],
        "llm_calls": 0
    }
    cfg = {"recursion_limit": 30}
    return await app.ainvoke(inputs, cfg)