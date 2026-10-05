from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import buy_policy_agent

a2a_app = to_a2a(
    buy_policy_agent,
    host="127.0.0.1",
    port=8004,
)