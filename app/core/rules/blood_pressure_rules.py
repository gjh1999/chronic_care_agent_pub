from app.config.constants import (
    BP_SYSTOLIC_HIGH,
    BP_DIASTOLIC_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_URGENT,
)


def parse_bp(bp_str: str):
    try:
        systolic, diastolic = bp_str.split("/")
        return int(systolic), int(diastolic)
    except:
        return None, None


def evaluate_blood_pressure(bp_str: str | None):
    if not bp_str:
        return None

    systolic, diastolic = parse_bp(bp_str)

    if systolic is None:
        return None

    if systolic >= 180 or diastolic >= 120:
        return {
            "level": RISK_URGENT,
            "reason": "血压达到高危范围，需要立即进行线下医疗评估",
        }

    if systolic >= 160 or diastolic >= 100:
        return {
            "level": RISK_HIGH,
            "reason": "血压明显偏高",
        }

    if systolic >= BP_SYSTOLIC_HIGH or diastolic >= BP_DIASTOLIC_HIGH:
        return {
            "level": RISK_MEDIUM,
            "reason": "血压偏高",
        }

    return {
        "level": RISK_LOW,
        "reason": "血压正常",
    }
