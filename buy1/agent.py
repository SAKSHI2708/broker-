from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)
from .handoff import TaskHandoffResult
from google.adk.models.google_llm import Gemini
from google.genai import types
from .instruction import (

    BUY_POLICY_INSTRUCTION,
    RISK_SEARCH_INSTRUCTION,
)
from .tools import (
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
    calculate_optional_coverage_options,
    calculate_final_premium,
    # reserve_staging_key,
    # check_staged_photo_clarity,
    # promote_staging_photos_to_policy,
    get_query_photo_folder,
    upload_property_photo_artifact,
    check_photo_clarity,
    promote_query_photos_to_policy,
    get_risk_snapshot,
    save_risk_snapshot,
    create_payment_session,
    record_payment_result,
    simulate_payment_outcome,
    verify_payment_token,
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
    model=MODEL,
    mode="task",

    output_schema=TaskHandoffResult,

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
        calculate_optional_coverage_options,
        calculate_final_premium,
        get_query_photo_folder,
        upload_property_photo_artifact,
        check_photo_clarity,
        promote_query_photos_to_policy,
        get_risk_snapshot,
        save_risk_snapshot,
        create_payment_session,
        record_payment_result,
        simulate_payment_outcome,
        verify_payment_token,
        AgentTool(agent=risk_search_agent),
    ],
)

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




app = App(
    root_agent=buy_policy_agent,
    name="buy_app",
    plugins=[SaveFilesAsArtifactsPlugin()],
)