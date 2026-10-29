from app.core.llm.client import llm_client
from app.core.llm.prompts import PLAN_PROMPT
from app.core.llm.output_parser import parse_json
from app.service.stream import emit_status
from app.utils.text import strip_markdown


def plan_draft_node(state):
    extracted_data = state.get("extracted_data") or {}
    plan_slots = extracted_data.get("plan") or {}
    if not isinstance(plan_slots, dict):
        plan_slots = {}

    prompt = PLAN_PROMPT.format(
        goal=plan_slots.get("goal") or "未指定",
        duration=plan_slots.get("duration") or "未指定",
        preferences=", ".join(plan_slots.get("preferences", [])) or "无特殊偏好",
        constraints=", ".join(plan_slots.get("constraints", [])) or "无限制",
        advice=state.get("advice") or "无建议",
        user_input=state.get("user_input", ""),
    )

    emit_status("正在生成计划草稿…")
    raw = llm_client.invoke(prompt, max_tokens=700)
    parsed = parse_json(raw)

    tasks = parsed.get("tasks") if isinstance(parsed, dict) else None
    if isinstance(tasks, list):
        for item in tasks:
            if isinstance(item, dict) and isinstance(item.get("task"), str):
                item["task"] = strip_markdown(item["task"])

    state["plan_draft"] = parsed
    return state
