from app.graph.state import ClinicalState


def normalize_intent_node(state: ClinicalState) -> ClinicalState:
    """
    根据 Parser Node 输出的 intent，补全依赖关系。
    """

    intent = state.get("intent", {})

    flags = {
        "need_record": bool(intent.get("need_record", False)),
        "need_advice": bool(intent.get("need_advice", False)),
        "need_plan": bool(intent.get("need_plan", False)),
        "need_reminder": bool(intent.get("need_reminder", False)),

        "need_history": bool(intent.get("need_history", False)),
        "need_risk": bool(intent.get("need_risk", False)),
        "need_rag": bool(intent.get("need_rag", False)),
    }

    # 计划必须基于建议
    if flags["need_plan"]:
        flags["need_advice"] = True

    # 建议需要历史、风险、RAG
    if flags["need_advice"]:
        flags["need_history"] = True
        flags["need_risk"] = True
        flags["need_rag"] = True

    # 判断提醒来源
    reminder_source = None
    if flags["need_reminder"]:
        if flags["need_plan"]:
            reminder_source = "plan"
        else:
            reminder_source = "direct"

    state["intent_flags"] = flags
    state["reminder_source"] = reminder_source

    return state