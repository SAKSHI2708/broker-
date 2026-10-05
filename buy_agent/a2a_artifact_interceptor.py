from google.adk.agents import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.plugins.base_plugin import BasePlugin


class A2AFileArtifactPlugin(BasePlugin):

    def __init__(self):
        super().__init__(name="a2a_file_artifact_plugin")

    async def on_user_message_callback(
        self,
        *,
        invocation_context,
        user_message,
    ):
        if not invocation_context.artifact_service:
            print("❌ Artifact service is missing")
            return None

        if not user_message or not user_message.parts:
            return None

        modified_parts = []

        for index, part in enumerate(user_message.parts):

            if not part.inline_data:
                modified_parts.append(part)
                continue

            inline_data = part.inline_data

            # IMPORTANT:
            # FilePart ka original filename
            filename = inline_data.display_name

            if not filename:
                filename = f"uploaded_file_{index}"

            print(f"📥 A2A file received: {filename}")

            await invocation_context.artifact_service.save_artifact(
                app_name=invocation_context.app_name,
                user_id=invocation_context.user_id,
                session_id=invocation_context.session.id,
                filename=filename,
                artifact=part,
            )

            print(f"✅ A2A artifact saved: {filename}")

            # Agent ko artifact ka reference do
            modified_parts.append(
                type(part)(
                    text=f'[Uploaded Artifact: "{filename}"]'
                )
            )

        from google.genai import types

        return types.Content(
            role=user_message.role,
            parts=modified_parts,
        )

    async def before_agent_callback(
        self,
        *,
        agent: BaseAgent,
        callback_context: CallbackContext,
    ):
        return None