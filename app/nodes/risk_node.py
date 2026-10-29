from app.core.rules.risk_engine import evaluate_risk


def _adapt_for_risk_engine(slots: dict) -> dict:
    """将 slots.record 结构化数据转为风险引擎所需的扁平格式。"""
    flat: dict = {}

    record = slots.get("record") or {}

    glucose = record.get("blood_glucose")
    if isinstance(glucose, dict):
        flat["blood_glucose"] = glucose.get("value")

    bp = record.get("blood_pressure")
    if isinstance(bp, dict) and bp.get("systolic") is not None:
        flat["blood_pressure"] = f"{bp['systolic']}/{bp.get('diastolic', 0)}"

    return flat


def risk_node(state):
    slots = state.get("extracted_data") or {}
    adapted = _adapt_for_risk_engine(slots)
    risk = evaluate_risk(adapted)

    state["risk_result"] = risk
    return state
