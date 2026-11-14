from functools import lru_cache

from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from parse import parse_payload
from memory.session import get_memory_session_manager
from tools.claims_tools import ALL_TOOLS

DEFAULT_SYSTEM_PROMPT = """You are a claims adjudication copilot for adjusters at a property and casualty insurer.

For any question about a specific claim:
1. Call adjudicate_claim to get the coverage decision, payout calculation, fraud signals and required approval.
2. Use get_claim, get_policy and get_claim_history when you need supporting detail.

Rules:
- Coverage decisions and payout amounts come only from adjudicate_claim. Never calculate or estimate them yourself.
- You recommend; a human decides. State who must approve (adjuster or supervisor) and never say a claim has been paid or denied.
- Fraud signals are indicators for review, not findings of fraud. Describe them neutrally.
- If a record cannot be found, say so and ask for the correct ID. Do not guess.

Answer with: the recommendation, the amount, the reasons (citing policy terms and dates), any fraud signals, and the required approver."""

tools = list(ALL_TOOLS)

def _make_conversation_manager():
    return NullConversationManager()

@lru_cache(maxsize=128)
def _get_agent(session_id: str, actor_id: str) -> Agent:
    """Given a session_id and actor_id, return or construct the corresponding Strands agent.
    Note: caching helps avoid repeated identity fetches on non-bedrock model loads
    and supports in-memory session management for local dev."""
    return Agent(
        model=load_model(),
        session_manager=get_memory_session_manager(session_id, actor_id),
        conversation_manager=_make_conversation_manager(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=tools,
    )

def create_app():
    app = BedrockAgentCoreApp()
    log = app.logger

    @app.entrypoint
    async def invoke(payload, context):
        log.info("Invoking Agent.....")

        session_id = getattr(context, "session_id", None) or "default-session"
        prompt, actor_id = parse_payload(payload)

        log.info(f"Invoking with session_id={session_id} and actor_id={actor_id}")
        agent = _get_agent(session_id, actor_id)

        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict) or "event" not in event:
                continue
            cbs = event["event"].get("contentBlockStart")
            if cbs is not None and not cbs.get("start"):
                continue
            yield event

    return app

app = create_app()
if __name__ == "__main__":
    app.run()
