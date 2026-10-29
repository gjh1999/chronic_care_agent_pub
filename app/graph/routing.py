from app.graph.state import ClinicalState
from app.config.constants import (
    NODE_RECORD,
    NODE_HISTORY,
    NODE_RESPONSE,
)

# 子图节点名（避免循环导入，直接用字符串常量）
_NODE_PLAN_REMINDER_SUB = "plan_reminder_sub"


def route_after_normalize(state: ClinicalState) -> str:
    flags = state.get("intent_flags", {})
    intent = state.get("intent", {})

    if flags.get("need_record"):
        return NODE_RECORD

    if flags.get("need_advice"):
        return NODE_HISTORY

    if flags.get("need_reminder") or flags.get("need_plan") \
            or intent.get("need_reminder") or intent.get("need_plan"):
        return _NODE_PLAN_REMINDER_SUB

    return NODE_RESPONSE


def route_after_record(state: ClinicalState) -> str:
    flags = state.get("intent_flags", {})
    intent = state.get("intent", {})

    if flags.get("need_advice"):
        return NODE_HISTORY

    if flags.get("need_reminder") or flags.get("need_plan") \
            or intent.get("need_reminder") or intent.get("need_plan"):
        return _NODE_PLAN_REMINDER_SUB

    return NODE_RESPONSE


def route_after_advice(state: ClinicalState) -> str:
    flags = state.get("intent_flags", {})
    intent = state.get("intent", {})

    if (state.get("risk_result") or {}).get("level") == "urgent":
        return NODE_RESPONSE

    if flags.get("need_plan") or flags.get("need_reminder") \
            or intent.get("need_plan") or intent.get("need_reminder"):
        return _NODE_PLAN_REMINDER_SUB

    return NODE_RESPONSE
