from app.core.rules.glucose_rules import evaluate_glucose
from app.core.rules.blood_pressure_rules import evaluate_blood_pressure


RISK_PRIORITY = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "urgent": 3,
}


def merge_risk(results):
    """
    多个风险合并 → 取最高等级
    """
    final = {"level": "low", "reason": ""}

    for r in results:
        if not r:
            continue

        if RISK_PRIORITY[r["level"]] > RISK_PRIORITY[final["level"]]:
            final = r

    return final


def evaluate_risk(extracted_data: dict):
    glucose = extracted_data.get("blood_glucose")
    bp = extracted_data.get("blood_pressure")

    results = []

    glucose_risk = evaluate_glucose(glucose)
    if glucose_risk:
        results.append(glucose_risk)

    bp_risk = evaluate_blood_pressure(bp)
    if bp_risk:
        results.append(bp_risk)

    if not results:
        return {
            "level": "low",
            "reason": "无明显风险",
        }

    return merge_risk(results)