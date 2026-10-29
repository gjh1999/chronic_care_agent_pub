from app.graph.builder import build_graph
from app.graph.state import ClinicalState
from app.memory.service import memory_service

_graph = build_graph()


def _build_session_summary(result: ClinicalState) -> str:
    parts = []
    if result.get("advice"):
        parts.append(result["advice"])
    if result.get("final_response"):
        parts.append(result["final_response"])
    return "\n".join(parts)


def run_workflow(
    user_input: str,
    user_id: str,
    conversation_id: str | None = None,
    user_confirmed: bool | None = None,
) -> ClinicalState:
    if not user_id:
        raise ValueError("user_id is required")
    memory_context = memory_service.load_user_memory(user_id)
    task_preferences = memory_service.get_task_preferences(user_id)

    initial_state: ClinicalState = {
        "user_id": user_id,
        "user_input": user_input,
        "conversation_id": conversation_id or "",
        "user_confirmed": user_confirmed,
        "memory_context": memory_context,
        "task_preferences": task_preferences,
    }

    result = _graph.invoke(initial_state)

    session_summary = _build_session_summary(result)
    if session_summary:
        memory_service.update_from_session_summary(user_id, session_summary)

    return result
