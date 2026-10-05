# import truststore

# truststore.inject_into_ssl()
# from google.adk.agents import Agent
# from google.adk.agents.remote_a2a_agent import (
#     RemoteA2aAgent,
#     AGENT_CARD_WELL_KNOWN_PATH,
# )
# from google.adk.apps import App
# from google.adk.models.google_llm import Gemini
# from google.genai import types

# from .instruction import ROOT_AGENT_INSTRUCTION
# from .session_manager import session_manager



# # ============================================================
# # UPDATE AGENT
# # ============================================================

# update_policy_agent = RemoteA2aAgent(
#     name="update_policy_agent",
#     description=(
#         "Specialist agent responsible for updating "
#         "existing homeowners insurance policies."
#     ),
#     agent_card=(
#         "http://127.0.0.1:8002"
#         # "https://broker-update-a2a-905482569530.us-central1.run.app"
#         f"{AGENT_CARD_WELL_KNOWN_PATH}"
#     ),
#     use_legacy=False,
# )


# # ============================================================
# # BUY AGENT
# # ============================================================

# buy_policy_agent = RemoteA2aAgent(
#     name="buy_policy_agent",
#     description=(
#         "Specialist agent responsible for buying "
#         "new US homeowners insurance policies."
#     ),
#     agent_card=(
#         "http://127.0.0.1:8004"
#         f"{AGENT_CARD_WELL_KNOWN_PATH}"
#     ),
#     use_legacy=False,
# )


# # ============================================================
# # CLAIM AGENT
# # ============================================================

# claim_agent = RemoteA2aAgent(
#     name="claim_agent",
#     description=(
#         "Specialist agent responsible for filing "
#         "and handling US homeowners insurance claims."
#     ),
#     agent_card=(
#         "http://127.0.0.1:8005"
#         f"{AGENT_CARD_WELL_KNOWN_PATH}"
#     ),
#     use_legacy=False,
# )



# # ============================================================
# # SESSION STATE HELPERS
# # ============================================================

# async def update_session_state(callback_context, agent_name: str):
#     """
#     Saves the active sub-agent name into the ADK session state.
#     """
#     session_state = callback_context.session.state
#     session_state["active_sub_agent"] = agent_name
#     print(f"[Session State Updated] Active sub-agent locked to: {agent_name}")


# async def get_active_session_agent(callback_context):
#     """
#     Retrieves the currently locked sub-agent from session state if it exists.
#     """
#     session_state = callback_context.session.state
#     return session_state.get("active_sub_agent", None)

# # ============================================================
# # ROOT AGENT
# # ============================================================

# root_agent = Agent(
#     name="root_agent",
#     model=Gemini(
#         model="gemini-3-flash-preview", # ya apna model naam jo aap use kar rahe hain
#         retry_options=types.HttpRetryOptions(
#             attempts=3,
#         ),
#     ),
#     description=(
#         "Intake and routing agent for US homeowners insurance."
#     ),
#     instruction=ROOT_AGENT_INSTRUCTION,
#     sub_agents=[
#         update_policy_agent,
#         buy_policy_agent,
#         claim_agent,
#     ],
#     # Yahan hook register karein taaki har turn par yeh function pehle chale
#     # before_turn_callback=route_based_on_session, 
# )


# # ============================================================
# # APP
# # ============================================================

# app = App(
#     root_agent=root_agent,
#     name="root_app",
# )

from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)
from google.adk.apps import App
from google.genai import types

from .instruction import ROOT_AGENT_INSTRUCTION


MODEL = "gemini-3-flash-preview"


# ============================================================
# UPDATE AGENT
# ============================================================

update_policy_agent = RemoteA2aAgent(
    name="update_policy_agent",
    description=(
        "Specialist agent responsible for updating "
        "existing homeowners insurance policies."
    ),
    agent_card=(
        "http://127.0.0.1:8002"
        + AGENT_CARD_WELL_KNOWN_PATH
    ),
    use_legacy=False,
)


# ============================================================
# BUY AGENT
# ============================================================

buy_policy_agent = RemoteA2aAgent(
    name="buy_policy_agent",
    description=(
        "Specialist agent responsible for buying "
        "new US homeowners insurance policies."
    ),
    agent_card=(
        "http://127.0.0.1:8004"
        + AGENT_CARD_WELL_KNOWN_PATH
    ),
    use_legacy=False,
    mode="task",
)


# ============================================================
# CLAIM AGENT
# ============================================================

claim_agent = RemoteA2aAgent(
    name="claim_agent",
    description=(
        "Specialist agent responsible for filing "
        "and handling US homeowners insurance claims."
    ),
    agent_card=(
        "http://127.0.0.1:8005"
        + AGENT_CARD_WELL_KNOWN_PATH
    ),
    use_legacy=False,
    mode="task",
)


# ============================================================
# ROOT AGENT
# ============================================================

root_agent = Agent(
    name="root_agent",
    model=MODEL,
    description=(
        "Intake and routing agent for US homeowners insurance."
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[
        buy_policy_agent,
        update_policy_agent,
        claim_agent,
    ],
)


# ============================================================
# APP
# ============================================================

app = App(
    root_agent=root_agent,
    name="root_app",
)