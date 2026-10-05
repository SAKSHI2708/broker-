import os

from dotenv import load_dotenv, find_dotenv

from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)
from google.adk.apps import App
from google.adk.tools import google_search
from google.genai import types
from .handoff import TaskHandoffResult
load_dotenv(find_dotenv())


MODEL = os.getenv(
    "GEMINI_MODEL_PRO",
    "gemini-3.5-flash",
)


from .instruction import (
    ROOT_AGENT_INSTRUCTION,
    # CLAIM_AGENT_INSTRUCTION,
    CLAIM_INTAKE_AGENT_INSTRUCTION,
    COVERAGE_VALIDATION_AGENT_INSTRUCTION,
    WEATHER_EVENT_VERIFICATION_AGENT_INSTRUCTION,
    DAMAGE_ASSESSMENT_AGENT_INSTRUCTION,
    CLAIM_CALCULATION_AGENT_INSTRUCTION,
)

from .tools.claim_intake_tools.database_tools import (
    get_claim_context,
    create_claim,
    update_claim,
)

from .tools.coverage_tools.coverage_tools import (
    validate_coverage,
)

from .tools.damage_assessment_agent.fetch import (
    fetch_reference_images,
)

from .tools.damage_assessment_agent.vision_tools import (
    analyze_damage_images,
)

from .tools.claim_calculation_tools.estimation_tools import (
    calculate_claim_from_damage,
)


# # ----------------------------------------------------------
# # Claim Intake Agent
# # ----------------------------------------------------------

# claim_intake_agent = Agent(
#     name="claim_intake_agent",
#     model=MODEL,
#     description="Collects customer claim information.",
#     instruction=CLAIM_INTAKE_AGENT_INSTRUCTION,
#     tools=[
#         get_claim_context,
#         create_claim,
#         update_claim,
#     ],
# )


# # ----------------------------------------------------------
# # Coverage Validation Agent
# # ----------------------------------------------------------

# coverage_validation_agent = Agent(
#     name="coverage_validation_agent",
#     model=MODEL,
#     description="Performs preliminary coverage validation.",
#     instruction=COVERAGE_VALIDATION_AGENT_INSTRUCTION,
#     tools=[
#         validate_coverage,
#     ],
# )


# # ----------------------------------------------------------
# # Damage Assessment Agent
# # ----------------------------------------------------------

# damage_assessment_agent = Agent(
#     name="damage_assessment_agent",
#     model=MODEL,
#     description="Analyzes uploaded property damage photographs.",
#     instruction=DAMAGE_ASSESSMENT_AGENT_INSTRUCTION,
#     tools=[
#         fetch_reference_images,
#         analyze_damage_images,
#     ],
#     generate_content_config=types.GenerateContentConfig(
#         temperature=0.0,
#     ),
# )


# # ----------------------------------------------------------
# # Weather Event Verification Agent
# # ----------------------------------------------------------

# weather_event_verification_agent = Agent(
#     name="weather_event_verification_agent",
#     model=MODEL,
#     description=(
#         "Verifies whether reported wind or hail events occurred "
#         "near the insured property and incident date."
#     ),
#     instruction=WEATHER_EVENT_VERIFICATION_AGENT_INSTRUCTION,
#     tools=[
#         google_search,
#     ],
#     disallow_transfer_to_parent=True,
#     disallow_transfer_to_peers=True,
# )


# # ----------------------------------------------------------
# # Claim Calculation Agent
# # ----------------------------------------------------------

# claim_calculation_agent = Agent(
#     name="claim_calculation_agent",
#     model=MODEL,
    
#     description=(
#         "Calculates preliminary claim estimate from damage assessment."
#     ),
#     instruction=CLAIM_CALCULATION_AGENT_INSTRUCTION,
#     tools=[
#         calculate_claim_from_damage,
#         update_claim,
#     ],
# )


# # ----------------------------------------------------------
# # ROOT CLAIM AGENT
# # ----------------------------------------------------------

# root_claim_agent = Agent(
#     name="root_claim_agent",
#     model=MODEL,
#     mode="task",
#     description="Insurance Claim Orchestrator.",
#     instruction=ROOT_AGENT_INSTRUCTION,
#     sub_agents=[
#         claim_intake_agent,
#         coverage_validation_agent,
#         weather_event_verification_agent,
#         damage_assessment_agent,
#         claim_calculation_agent,
#     ],
# )


# # ----------------------------------------------------------
# # ROOT ROUTER - A2A
# # ----------------------------------------------------------

# root_router_agent = RemoteA2aAgent(
#     name="root_agent",
#     description=(
#         "Root intake and routing agent for US homeowners insurance."
#     ),
#     agent_card=(
#         "http://127.0.0.1:8003"
#         f"{AGENT_CARD_WELL_KNOWN_PATH}"
#     ),
#     use_legacy=False,
# )


# claim_agent = Agent(
#     name="claim_agent",
#     model=MODEL,
#     mode="task",
#     output_schema=TaskHandoffResult,

#     description=(
#         "Specialist agent responsible for filing and handling "
#         "US homeowners insurance claims."
#     ),

#     instruction=ROOT_AGENT_INSTRUCTION,

#     sub_agents=[
#         root_claim_agent,
#     ],

#     generate_content_config=types.GenerateContentConfig(
#         thinking_config=types.ThinkingConfig(
#             include_thoughts=False
#         )
#     ),
# )

# # # ----------------------------------------------------------
# # # CLAIM AGENT
# # # ----------------------------------------------------------

# # claim_agent = Agent(
# #     name="claim_agent",
# #     model=MODEL,
# #     description=(
# #         "Specialist agent responsible for filing and handling "
# #         "US homeowners insurance claims."
# #     ),
# #     instruction=ROOT_AGENT_INSTRUCTION,
# #     sub_agents=[
# #         root_router_agent,
# #         root_claim_agent,
# #     ],
# # )


# # ----------------------------------------------------------
# # APP
# # ----------------------------------------------------------

# app = App(
#     root_agent=claim_agent,
#     name="claim_app",
# )


# __all__ = ["claim_agent"]
# ----------------------------------------------------------
# Claim Intake Agent
# ----------------------------------------------------------

claim_intake_agent = Agent(
    name="claim_intake_agent",
    model=MODEL,
    description="Collects customer claim information.",
    instruction=CLAIM_INTAKE_AGENT_INSTRUCTION,
    tools=[
        get_claim_context,
        create_claim,
        update_claim,
    ],
)


# ----------------------------------------------------------
# Coverage Validation Agent
# ----------------------------------------------------------

coverage_validation_agent = Agent(
    name="coverage_validation_agent",
    model=MODEL,
    description="Performs preliminary coverage validation.",
    instruction=COVERAGE_VALIDATION_AGENT_INSTRUCTION,
    tools=[
        validate_coverage,
    ],
)


# ----------------------------------------------------------
# Damage Assessment Agent
# ----------------------------------------------------------

damage_assessment_agent = Agent(
    name="damage_assessment_agent",
    model=MODEL,
    description="Analyzes uploaded property damage photographs.",
    instruction=DAMAGE_ASSESSMENT_AGENT_INSTRUCTION,
    tools=[
        fetch_reference_images,
        analyze_damage_images,
    ],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.0,
    ),
)


# ----------------------------------------------------------
# Weather Event Verification Agent
# ----------------------------------------------------------

weather_event_verification_agent = Agent(
    name="weather_event_verification_agent",
    model=MODEL,
    description=(
        "Verifies whether reported wind or hail events occurred "
        "near the insured property and incident date."
    ),
    instruction=WEATHER_EVENT_VERIFICATION_AGENT_INSTRUCTION,
    tools=[
        google_search,
    ],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)


# ----------------------------------------------------------
# Claim Calculation Agent
# ----------------------------------------------------------

claim_calculation_agent = Agent(
    name="claim_calculation_agent",
    model=MODEL,
    description=(
        "Calculates preliminary claim estimate from damage assessment."
    ),
    instruction=CLAIM_CALCULATION_AGENT_INSTRUCTION,
    tools=[
        calculate_claim_from_damage,
        update_claim,
    ],
)


# ----------------------------------------------------------
# ROOT CLAIM AGENT
# ----------------------------------------------------------

root_claim_agent = Agent(
    name="root_claim_agent",
    model=MODEL,
    mode="task",
    description="Insurance Claim Orchestrator.",
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[
        claim_intake_agent,
        coverage_validation_agent,
        weather_event_verification_agent,
        damage_assessment_agent,
        claim_calculation_agent,
    ],
)


# ----------------------------------------------------------
# ROOT ROUTER - A2A
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


# ----------------------------------------------------------
# CLAIM SPECIALIST
# ----------------------------------------------------------

claim_agent = Agent(
    name="claim_agent",
    model=MODEL,
    mode="task",
    output_schema=TaskHandoffResult,
    description=(
        "Specialist agent responsible for filing and handling "
        "US homeowners insurance claims."
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[
        root_claim_agent,
    ],
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False
        )
    ),
)


# ----------------------------------------------------------
# APP
# ----------------------------------------------------------

app = App(
    root_agent=claim_agent,
    name="claim_app",
)

__all__ = ["claim_agent"]