from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models.google_llm import Gemini
from google.adk.tools import LongRunningFunctionTool
from google.genai import types
from .instruction import BROKER_AGENT_INSTRUCTION
# from .instructions import BROKER_AGENT_INSTRUCTION
from .handoff import TaskHandoffResult
from .tools.fetch_tool import fetch_table_data
from .tools.update_tool import update_table_data
from .tools.insert_tool import insert_table_data
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)
# from .tools.premium_calculator_tool import calculate_premium
# from .tools.renewal_premium_tool import calculate_renewal_premium 

# ============================================================
# REQUEST USER INPUT
# ============================================================

def request_user_input(
    question: str,
) -> str:
    """
    Ask the customer for missing information
    or confirmation.
    """
    return question




# ============================================================
# CALCULATION AGENT
# ============================================================

calculation_agent = RemoteA2aAgent(
    name="calculation_agent",
    description=(
        "Specialized agent responsible for premium, "
        "renewal, and pre-renewal calculations."
    ),
    agent_card=(
        "http://127.0.0.1:8001"
        + AGENT_CARD_WELL_KNOWN_PATH
    ),
    use_legacy=False,
    mode="task",
)


# ============================================================
# ROOT ROUTER AGENT (FOR SWITCHING TO BUY / CLAIM)
# ============================================================

root_router_agent = RemoteA2aAgent(
    name="root_agent",
    description=(
        "Root intake and routing agent responsible for routing "
        "customers between homeowners insurance specialists (Buy, Update, Claim)."
    ),
    agent_card=(
        "http://127.0.0.1:8003"
        + AGENT_CARD_WELL_KNOWN_PATH
    ),
    use_legacy=False,
)


# ============================================================
# ROOT AGENT (UPDATE SPECIALIST)
# ============================================================

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-3-flash-preview",
        retry_options=types.HttpRetryOptions(
            attempts=3,
        ),
    ),
    description=(
        "Broker Productivity Update Assistant "
        "that fetches, calculates premiums, and updates "
        "US homeowners insurance information."
    ),
    instruction=BROKER_AGENT_INSTRUCTION,
    sub_agents=[
        calculation_agent,
        root_router_agent,
    ],
    tools=[
        fetch_table_data,
        update_table_data,
        insert_table_data,
    ],
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False
        )
    ),
)


# ============================================================
# APP
# ============================================================

app = App(
    root_agent=root_agent,
    name="app",
)