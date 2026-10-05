from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin

from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)
from google.adk.models.google_llm import Gemini
from google.genai import types

from .instruction import (
    # ROOT_AGENT_INSTRUCTION,
    BUY_POLICY_INSTRUCTION,
    # UPDATE_POLICY_INSTRUCTION,
    # CLAIM_INSTRUCTION,
    RISK_SEARCH_INSTRUCTION,
)
# from .tools import (
#     get_customer_by_id,
#     get_customer_by_query_id,
#     get_properties_by_customer,
#     create_customer,
#     create_property,
#     generate_query_id,
#     create_query_customer,
#     get_query_customer_by_query_id,
#     create_query_property,
#     get_query_property_by_query_id,
#     create_policy,
#     calculate_homeowners_quotes,
#     reserve_policy_id,
#     upload_property_photos,
#     get_risk_snapshot,
#     save_risk_snapshot,
# )

from .tools.customer_lookup import (
    get_customer_by_id,
    get_customer_by_query_id,
)

from .tools.property_lookup import (
    get_properties_by_customer,
)

from .tools.customer_insert import (
    create_customer,
)

from .tools.property_insert import (
    create_property,
)

from .tools.query_id import (
    generate_query_id,
)

from .tools.query_customer_insert import (
    create_query_customer,
)

from .tools.query_customer_lookup import (
    get_query_customer_by_query_id,
)

from .tools.query_property_insert import (
    create_query_property,
)

from .tools.query_property_lookup import (
    get_query_property_by_query_id,
)

from .tools.policy_insert import (
    create_policy,
)

from .tools.premium_calculator import (
    calculate_homeowners_quotes,
)

from .tools.property_photo_upload import (
    reserve_policy_id,
)

from .tools.property_photo_upload import (
    upload_property_photos,
)

from .tools.risk_snapshot import (
    get_risk_snapshot,
    save_risk_snapshot,
)
MODEL = "gemini-3.5-flash"

risk_search_agent = Agent(
    name="risk_search_agent",
    model=MODEL,
    description=(
        "Uses Google Search to estimate homeowners insurance risk "
        "(flood, wind, hail, wildfire, earthquake, tornado, lightning, crime) for a US property "
        "based on its address / state / ZIP."
    ),
    instruction=RISK_SEARCH_INSTRUCTION,
    tools=[google_search],
)

# ----------------------------------------------------------
# Specialist Sub-Agents
# ----------------------------------------------------------

buy_policy_agent = Agent(
    name="buy_policy_agent",
    # name="root_agent",
    model=MODEL,
    description=(
        "Handles the end-to-end journey for a customer who wants to "
        "purchase a new US homeowners insurance policy (quote, risk "
        "assessment via Google Search, coverage recommendation, "
        "policy creation)."
    ),
    instruction=BUY_POLICY_INSTRUCTION,
    tools=[
        get_customer_by_id,
        get_customer_by_query_id,
        get_properties_by_customer,
        create_customer,
        create_property,
        generate_query_id,
        create_query_customer,
        get_query_customer_by_query_id,
        create_query_property,
        get_query_property_by_query_id,
        create_policy,
        calculate_homeowners_quotes,
        reserve_policy_id,
        upload_property_photos,
        get_risk_snapshot,
        save_risk_snapshot,
        AgentTool(agent=risk_search_agent),
    ],
)

# update_policy_agent = Agent(
#     name="update_policy_agent",
#     model=MODEL,
#     description=(
#         "Handles updates to an existing homeowners insurance policy: "
#         "coverage / deductible changes, address updates, adding or "
#         "removing insured members, renewals, and personal detail edits."
#     ),
#     instruction=UPDATE_POLICY_INSTRUCTION,
# )

# claim_agent = Agent(
#     name="claim_agent",
#     model=MODEL,
#     description=(
#         "Handles homeowners insurance claims: filing a new claim and "
#         "checking the status of an existing claim."
#     ),
#     instruction=CLAIM_INSTRUCTION,
# )

# ----------------------------------------------------------
# Root Intake & Routing Agent (Step 1)
# ----------------------------------------------------------



root_router_agent = RemoteA2aAgent(
    name="root_agent",
    description=(
        "Root intake and routing agent for US homeowners insurance."
    ),
    agent_card=(
        "http://127.0.0.1:8003"
        f"{AGENT_CARD_WELL_KNOWN_PATH}"
    ),
    use_legacy=False,
)

# buy_agent = Agent(
#     name="root_agent",
#     model=MODEL,
#     description=(
#         "Intake & Routing Agent for the US Homeowners Insurance Broker "
#         "Platform. Greets the customer and routes to the Buy, Update, "
#         "or Claim specialist agent based on detected intent."
#     ),
#     instruction=BUY_POLICY_INSTRUCTION,
#     sub_agents=[buy_policy_agent, 
#                 # update_policy_agent,
#                 # claim_agent,
#                 root_router_agent,
#                 ],
           
# )


app = App(
    root_agent=buy_policy_agent,
    name="buy_app",
    plugins=[
        SaveFilesAsArtifactsPlugin()
    ],
)










# buy_agent = Agent(
#     name="buy_policy_agent",

#     model=Gemini(
#         model="gemini-3-flash-preview",
#         retry_options=types.HttpRetryOptions(
#             attempts=3,
#         ),
#     ),

#     description=(
#         "Specialist agent responsible for buying new "
#         "US homeowners insurance policies."
#     ),

#     instruction=BUY_AGENT_INSTRUCTION,

#     sub_agents=[
#         root_router_agent,
#     ],
# )


# app = App(
#     root_agent=buy_agent,
#     name="buy_app",
# )