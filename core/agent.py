from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated,Sequence
import operator
import os
import json
from dotenv import load_dotenv
import inspect

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage,ToolMessage,BaseMessage,HumanMessage
from langgraph.graph.message import add_messages
from typing import Literal
from langgraph.graph import StateGraph, START, END


#import phase 1 tools
from core.tools1 import (
    get_order,get_customer,get_product,search_knowledge_base,check_refund_eligibility,issue_refund,
    send_reply,escalate
)

load_dotenv()


#LOAD SYSTEM PROMPT
def load_system_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompts.md")
    try:
        with open(prompt_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print("\n[CRITICAL WARNING] system_prompts.md NOT FOUND! Using default chat prompt.\n")
        return "You are a helpful support agent."
    
SYSTEM_INSTRUCTION=load_system_prompt()


#GRAPH STATE AND LLM SETUP
class AgentState(TypedDict):
    messages:Annotated[Sequence[BaseMessage],add_messages]
    llm_calls:Annotated[int,operator.add]
    
    


llm=ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL","gemini-2.5-flash-lite"),
    temperature=0
)

#augment the llm with tools
tools_list=[get_order,get_customer,get_product,search_knowledge_base,
            check_refund_eligibility,issue_refund,send_reply,escalate]
TOOL_MAP = {(tool.name if hasattr(tool, "name") else tool.__name__): tool for tool in tools_list}
agent_brain=llm.bind_tools(tools_list)



async def agent_node(state:AgentState):
     """LLM decides whether to call a tool or not"""
     messages=state["messages"]
     if not any(isinstance(m,SystemMessage) for m in messages):
        messages=[SystemMessage(content=SYSTEM_INSTRUCTION)]+list(messages)
        
     response=await agent_brain.ainvoke(messages)
     # Increment our circuit breaker by 1 for every call
     return{"messages":[response],"llm_calls":1}
    
    
async def tool_node(state:AgentState):
     """Performs the tool call"""
     last_message = state["messages"][-1]
     tool_messages = []
    
     for tool_call in last_message.tool_calls:
        try:
            tool_obj = TOOL_MAP[tool_call["name"]]
            args = tool_call["args"]
            
            # Check if it's a LangChain Tool (has .ainvoke)
            if hasattr(tool_obj, "ainvoke"):
                result = await tool_obj.ainvoke(args)
            # Otherwise, handle it as a raw Python function
            else:
                # Check if it's an async function or a sync function
                if inspect.iscoroutinefunction(tool_obj):
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
         
     
def should_continue(state:AgentState):
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""
    last_message=state["messages"][-1] #it returns the newest message out of the memory state
    
    # CIRCUIT BREAKER: If the LLM has looped more than 5 times, force an escalation
    if(state.get("llm_calls",0)>5):
        print("[WARNING] Infinite loop detected. Forcing stop.")
        return END
    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:
        return "tool"
     # Otherwise, we stop (reply to the user)
    return END

#COMPILE THE GRAPH

# Build workflow
agent_builder=StateGraph(AgentState)

# Add nodes
agent_builder.add_node("agent",agent_node)
agent_builder.add_node("tool",tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START,"agent")
agent_builder.add_conditional_edges(
    "agent",
    should_continue,
    ["tool",END]
)
agent_builder.add_edge("tool","agent")

# Compile the agent
app=agent_builder.compile()

# Invoke
async def run_agent(ticket_input:str):
    """Entry point for a single ticket."""
    inputs={
        "messages":[HumanMessage(content=ticket_input)],
        "llm_calls":0
    }
    return await app.ainvoke(inputs)