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

from app.tools.chat_tools import (
    get_fixtures_by_date,
    find_team_fixture,
    get_teams_by_tournament,
    get_odds_for_match,
    get_daily_odds_analysis, # Add the new tool
    get_match_recommendation, # Add new tool
    get_betting_recommendation, # Add new tool
    calculate_winnings_for_match, # Add new tool
    get_odds_for_outcome, # Add new tool
    place_simulated_bet, # Add the new tool
)
from app.prompts.system_prompts import BASE_SYSTEM_PROMPT

# --- State Definition ---
# Define a simple state, as user context is handled by the API client
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    # This will hold the JSON response from the get_odds_for_match tool
    match_context: Optional[dict]
    simulated_balance: Optional[float]
    bets: List[dict]

# --- Tools and Model Setup ---
tools = [
    get_fixtures_by_date,
    find_team_fixture,
    get_teams_by_tournament,
    get_odds_for_match,
    get_daily_odds_analysis, # Add the new tool
    get_match_recommendation, # Add new tool
    get_betting_recommendation, # Add new tool
    calculate_winnings_for_match, # Add new tool
    get_odds_for_outcome, # Add new tool
    place_simulated_bet, # Add the new tool
]
tool_executor = ToolExecutor(tools)

# Define the model and bind the tools
# The model name is now configurable via environment variable
model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
model = ChatGoogleGenerativeAI(model=model_name, temperature=0)
model = model.bind_tools(tools)


# --- Graph Nodes ---
def call_model(state: AgentState):
    messages = state["messages"]
    match_context = state.get("match_context")
    simulated_balance = state.get("simulated_balance")
    bets = state.get("bets")
    
    system_prompt = BASE_SYSTEM_PROMPT
    
    # Add dynamic context to the prompt
    if simulated_balance is not None:
        system_prompt += f"\\n\\n## SESSION STATE\\n- Current Simulated Balance: ${simulated_balance:.2f}"
    if bets:
        system_prompt += "\\n- Bets Placed This Session:"
        for bet in bets:
            system_prompt += f"\\n  - Bet ${bet['amount_bet']:.2f} on {bet['outcome_bet_on']} in '{bet['match']}'"
    
    if match_context:
        if "match_result" in match_context and match_context.get("match"):
            system_prompt += (
                "\\n\\n## CONTEXT: LAST MATCH ODDS\\n"
                "You are currently discussing the following match, and you have its odds data. "
                "Use this data for any follow-up questions.\\n"
                f"```json\\n{json.dumps(match_context, indent=2)}\\n```"
            )
        elif "team_one" in match_context and "team_two" in match_context:
            team_one = match_context.get('team_one', 'Unknown')
            team_two = match_context.get('team_two', 'Unknown')
            if team_one and team_two:
                system_prompt += (
                    "\\n\\n## CONTEXT: CURRENT MATCH\\n"
                    f"You are currently discussing the match between **{team_one}** and **{team_two}**. "
                    "Use these teams for any follow-up questions (like calculating winnings)."
                )

    system_message = SystemMessage(content=system_prompt)
    
    response = model.invoke([system_message] + messages)
    return {"messages": [response]}


def call_tool(state: AgentState):
    last_message = state["messages"][-1]
    action_dict = last_message.tool_calls[0]

    # Special handling for place_simulated_bet to inject the current balance
    tool_name = action_dict["name"]
    tool_input = action_dict["args"]
    if tool_name == "place_simulated_bet":
        tool_input["current_balance"] = state.get("simulated_balance")

    tool_invocation = ToolInvocation(tool=tool_name, tool_input=tool_input)
    
    tool_output = tool_executor.invoke(tool_invocation)
    tool_output_content = str(tool_output)
    context_update = {}

    try:
        parsed_output = json.loads(tool_output)
        if isinstance(parsed_output, dict):
            new_context = None
            if "context" in parsed_output and parsed_output["context"]:
                new_context = parsed_output["context"]
                if "display" in parsed_output:
                    tool_output_content = parsed_output["display"]
            elif "match" in parsed_output and "error" not in parsed_output:
                new_context = parsed_output

            if new_context:
                current_context = state.get("match_context") or {}
                current_context.update(new_context)
                context_update["match_context"] = current_context

                # Handle simulation updates
                if "balance_change" in new_context:
                    current_balance = state.get("simulated_balance", 0.0)
                    context_update["simulated_balance"] = current_balance + new_context["balance_change"]
                if "new_bet" in new_context:
                    current_bets = state.get("bets", [])
                    context_update["bets"] = current_bets + [new_context["new_bet"]]
    except (json.JSONDecodeError, TypeError):
        pass

    tool_message = ToolMessage(content=tool_output_content, tool_call_id=action_dict["id"])
    return {"messages": [tool_message], **context_update}


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
