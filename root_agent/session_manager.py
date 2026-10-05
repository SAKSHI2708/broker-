from typing import Optional

from google.adk.agents.callback_context import CallbackContext


class SessionManager:
    """
    Manages routing state inside the ADK session.

    State stored in ADK session:

        session_id
        active_agent
        user_intent
    """

    ACTIVE_AGENTS = {
        "buy_agent",
        "update_agent",
        "claim_agent",
    }

    def _get_session_state(self, callback_context: CallbackContext):
        return callback_context.session.state

    def initialize_session(
        self,
        callback_context: CallbackContext,
    ) -> str:
        """
        Initialize session state if it does not already exist.

        Returns the ADK session ID.
        """

        session = callback_context.session
        state = session.state

        session_id = session.id

        if "session_id" not in state:
            state["session_id"] = session_id

        if "active_agent" not in state:
            state["active_agent"] = "root"

        if "user_intent" not in state:
            state["user_intent"] = None

        print(
            "[SESSION INIT] "
            f"session_id={state['session_id']} "
            f"active_agent={state['active_agent']} "
            f"user_intent={state['user_intent']}"
        )

        return state["session_id"]

    def lock_agent(
        self,
        callback_context: CallbackContext,
        active_agent: str,
        user_intent: str,
    ) -> None:
        """
        Lock the current ADK session to a specialist agent.
        """

        state = self._get_session_state(callback_context)

        state["session_id"] = callback_context.session.id
        state["active_agent"] = active_agent
        state["user_intent"] = user_intent

        print(
            "[SESSION LOCK] "
            f"session_id={state['session_id']} "
            f"active_agent={active_agent} "
            f"user_intent={user_intent}"
        )

    def get_session_id(
        self,
        callback_context: CallbackContext,
    ) -> str:
        """
        Return the current ADK session ID.
        """

        state = self._get_session_state(callback_context)

        if "session_id" not in state:
            self.initialize_session(callback_context)

        return state["session_id"]

    def get_active_agent(
        self,
        callback_context: CallbackContext,
    ) -> str:
        """
        Return currently active agent.
        """

        state = self._get_session_state(callback_context)

        if "active_agent" not in state:
            self.initialize_session(callback_context)

        return state["active_agent"]

    def get_user_intent(
        self,
        callback_context: CallbackContext,
    ) -> Optional[str]:
        """
        Return current user intent.
        """

        state = self._get_session_state(callback_context)

        if "user_intent" not in state:
            self.initialize_session(callback_context)

        return state["user_intent"]

    def is_locked(
        self,
        callback_context: CallbackContext,
    ) -> bool:
        """
        Check whether the session is already locked
        to a specialist agent.
        """

        active_agent = self.get_active_agent(callback_context)

        return active_agent in self.ACTIVE_AGENTS

    def reset(
        self,
        callback_context: CallbackContext,
    ) -> None:
        """
        Reset routing state back to Root.

        The session_id is intentionally preserved.
        """

        state = self._get_session_state(callback_context)

        state["session_id"] = callback_context.session.id
        state["active_agent"] = "root"
        state["user_intent"] = None

        print(
            "[SESSION RESET] "
            f"session_id={state['session_id']}"
        )

    def get_state(
        self,
        callback_context: CallbackContext,
    ) -> dict:
        """
        Return current routing state.
        """

        state = self._get_session_state(callback_context)

        if "session_id" not in state:
            self.initialize_session(callback_context)

        return {
            "session_id": state["session_id"],
            "active_agent": state["active_agent"],
            "user_intent": state["user_intent"],
        }


session_manager = SessionManager()