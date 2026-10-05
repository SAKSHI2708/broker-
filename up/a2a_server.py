from dotenv import load_dotenv
load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from .agent import root_agent

a2a_app = to_a2a(
    root_agent,
    host="127.0.0.1",
    port=8002,
)
# from dotenv import load_dotenv

# load_dotenv()

# from google.adk.a2a.utils.agent_to_a2a import to_a2a
# from .agent import root_agent

# a2a_app = to_a2a(
#     root_agent,
#     host="0.0.0.0",
#     port=8080,
# )


# from dotenv import load_dotenv

# load_dotenv()

# from google.adk.a2a.utils.agent_to_a2a import to_a2a
# from a2a.types import AgentCard, AgentInterface

# from .agent import root_agent


# agent_card = AgentCard(
#     name="update_agent",
#     description=(
#         "Specialist agent responsible for updating "
#         "existing homeowners insurance policies."
#     ),
#     version="0.0.1",
#     capabilities={
#         "streaming": True,
#     },
#     default_input_modes=["text/plain"],
#     default_output_modes=["text/plain"],
#     skills=[],
#     supported_interfaces=[
#         AgentInterface(
#             url="https://broker-update-a2a-905482569530.us-central1.run.app",
#             protocol_binding="JSONRPC",
#             protocol_version="1.0",
#         )
#     ],
# )


# a2a_app = to_a2a(
#     root_agent,
#     host="0.0.0.0",
#     port=8080,
#     agent_card=agent_card,
# )