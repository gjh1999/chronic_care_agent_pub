from app.config.settings import settings
from app.graph.state import ClinicalState
from app.intent_client.client import ExternalIntentClient
from app.intent_client.schemas import IntentRequest


intent_client = ExternalIntentClient(
    base_url=settings.intent_base_url,
    api_key=settings.intent_api_key,
    timeout=settings.intent_timeout,
)


def parser_node(state: ClinicalState) -> ClinicalState:
    """Use the external Medical_Lora service for routing and slot extraction."""
    from app.service.stream import emit_status

    emit_status("正在识别意图…")
    parsed = intent_client.parse(
        IntentRequest(
            text=state["user_input"],
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
        )
    )

    routing = parsed.routing.model_dump()
    state["intent"] = routing
    state["intent_flags"] = routing.copy()
    state["extracted_data"] = parsed.slots
    state["confidence"] = parsed.confidence.model_dump()
    state["missing_fields"] = parsed.missing_fields
    state["risk_flags"] = parsed.risk_flags
    state["normalized"] = parsed.normalized
    return state
