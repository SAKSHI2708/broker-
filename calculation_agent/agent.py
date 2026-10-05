# from google.adk.agents import Agent
# from google.adk.apps import App
# from google.adk.models.google_llm import Gemini
# from google.genai import types

# from .instruction import CALCULATION_AGENT_INSTRUCTION

# from .tools.premium_calculator_tool import calculate_premium
# from .tools.renewal_premium_tool import calculate_renewal_premium
# from .tools.pre_renewal_tool import calculate_pre_renewal


# calculation_agent = Agent(
#     name="calculation_agent",

#     model=Gemini(
#         model="gemini-3-flash-preview",
#         retry_options=types.HttpRetryOptions(
#             attempts=3,
#         ),
#     ),

#     description=(
#         "Specialized insurance calculation agent responsible for "
#         "premium calculation, renewal calculation, and pre-renewal "
#         "calculation for US homeowners insurance."
#     ),

#     instruction=CALCULATION_AGENT_INSTRUCTION,

#     tools=[
#         calculate_premium,
#         calculate_renewal_premium,
#         calculate_pre_renewal,
#     ],
# )


# app = App(
#     root_agent=calculation_agent,
#     name="calculation_app",
# )
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models.google_llm import Gemini
from google.genai import types

from .instruction import CALCULATION_AGENT_INSTRUCTION
from .handoff import CalculationResult

from .tools.premium_calculator_tool import calculate_premium
from .tools.renewal_premium_tool import calculate_renewal_premium
from .tools.pre_renewal_tool import calculate_pre_renewal


calculation_agent = Agent(
    name="calculation_agent",

    model=Gemini(
        model="gemini-3-flash-preview",
        retry_options=types.HttpRetryOptions(
            attempts=3,
        ),
    ),

    mode="task",

    output_schema=CalculationResult,

    description=(
        "Specialized insurance calculation agent responsible for "
        "premium calculation, renewal calculation, and "
        "pre-renewal calculation for US homeowners insurance."
    ),

    instruction=CALCULATION_AGENT_INSTRUCTION,

    tools=[
        calculate_premium,
        calculate_renewal_premium,
        calculate_pre_renewal,
    ],

    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False
        )
    ),
)


app = App(
    root_agent=calculation_agent,
    name="calculation_app",
)