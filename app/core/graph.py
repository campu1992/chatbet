from typing import TypedDict, Annotated, Sequence, Optional, List
import operator
import json
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from langgraph.prebuilt import ToolInvocation, ToolExecutor
from langgraph.graph import StateGraph, END

import json

from app.core.agent import (
    get_fixtures_by_date,
    find_team_fixture,
    get_teams_by_tournament,
    get_user_balance,
    place_real_bet,
    get_odds_for_match,
    get_daily_odds_analysis, # Add the new tool
    get_betting_recommendation, # Add new tool
    calculate_winnings_for_match, # Add new tool
    get_odds_for_outcome, # Add new tool
)

# --- State Definition ---
# Define a simple state, as user context is handled by the API client
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    # This will hold the JSON response from the get_odds_for_match tool
    match_context: Optional[dict]

# --- Tools and Model Setup ---
tools = [
    get_fixtures_by_date,
    find_team_fixture,
    get_teams_by_tournament,
    get_user_balance,
    place_real_bet,
    get_odds_for_match,
    get_daily_odds_analysis, # Add the new tool
    get_betting_recommendation, # Add new tool
    calculate_winnings_for_match, # Add new tool
    get_odds_for_outcome, # Add new tool
]
tool_executor = ToolExecutor(tools)

# Define the model and bind the tools
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
model = model.bind_tools(tools)


# --- Graph Nodes ---
def call_model(state: AgentState):
    messages = state["messages"]
    match_context = state.get("match_context")
    
    system_prompt = """You are a helpful sports betting assistant. Use the provided tools to answer user questions accurately.

Key instructions:
- If a user asks for the odds of a specific outcome (e.g., "how much does a draw pay?") but does NOT provide an amount, you MUST use the `get_odds_for_outcome` tool.
- For any user question that involves calculating winnings (e.g., "How much would I win if..."), you MUST use the `calculate_winnings_for_match` tool. Do not perform calculations yourself.
- The `calculate_winnings_for_match` tool returns a complete, user-ready answer. You MUST present its output directly to the user without rephrasing, preserving all markdown formatting.
- If you need to call `calculate_winnings_for_match` but don't know the teams, ask the user for them first.
- If a user asks for a general betting recommendation with an amount (e.g., "What should I bet with $100?") and does NOT specify a match, you MUST use the `get_betting_recommendation` tool.
- After presenting the recommendation from the tool, ALWAYS ask the user a follow-up question like: "This recommendation is based on today's matches. Are you interested in a specific match instead?"
- When you receive output from `get_betting_recommendation`, present it clearly to the user. You can rephrase it slightly to be more conversational, but you MUST preserve the markdown formatting (bolding, lists, and line breaks) for readability.
- For broad questions like "best odds today" or "safest bet" for a specific date/range, use the `get_daily_odds_analysis` tool.
- When asked for odds on a specific match, ALWAYS use the `get_odds_for_match` tool.
- Use the `match_context` to answer follow-up questions about a specific match that has already been looked up.
- Keep responses natural, friendly, and concise.
"""
    
    # If there's match context, add it to the system prompt for the LLM
    if match_context:
        system_prompt += f"\n\n## CONTEXT: LAST MATCH ODDS\nYou are currently discussing the following match, and you have its odds data. Use this data for any follow-up questions.\n```json\n{json.dumps(match_context, indent=2)}\n```"

    system_message = SystemMessage(content=system_prompt)
    
    response = model.invoke([system_message] + messages)
    return {"messages": [response]}


def call_tool(state: AgentState):
    last_message = state["messages"][-1]
    # The model can return multiple tool calls, we'll handle the first one.
    action_dict = last_message.tool_calls[0]
    
    # Wrap the action dictionary in a ToolInvocation object that the executor expects.
    tool_invocation = ToolInvocation(
        tool=action_dict["name"],
        tool_input=action_dict["args"],
    )
    
    # All tools are now stateless from the graph's perspective
    tool_output = tool_executor.invoke(tool_invocation)
    
    # Check if the tool call is from our odds tool
    tool_name = tool_invocation.tool
    if tool_name == "get_odds_for_match":
        # The output is a JSON string, so we parse it
        try:
            tool_output_dict = json.loads(tool_output)
            # If there's no error, save it to the context
            if "error" not in tool_output_dict:
                state["match_context"] = tool_output_dict
        except json.JSONDecodeError:
            # Handle cases where the output is not valid JSON
            pass # Or log an error

    return {"messages": [ToolMessage(content=str(tool_output), tool_call_id=action_dict["id"])]}

# --- Graph Logic ---
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    return "continue_to_tool" if last_message.tool_calls else END

# --- Graph Construction ---
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tool", call_tool)
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"continue_to_tool": "tool", END: END}
)
workflow.add_edge("tool", "agent")
app = workflow.compile()
