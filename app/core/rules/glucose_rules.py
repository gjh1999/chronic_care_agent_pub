from app.config.constants import (
    GLUCOSE_NORMAL_MAX,
    GLUCOSE_HIGH,
    GLUCOSE_DANGEROUS,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_URGENT,
)


def evaluate_glucose(glucose: float | None):
    if glucose is None:
        return None

    if glucose >= GLUCOSE_DANGEROUS:
        return {
            "level": RISK_URGENT,
            "reason": "血糖严重升高，存在危险风险",
        }

    if glucose >= GLUCOSE_HIGH:
        return {
            "level": RISK_HIGH,
            "reason": "血糖明显偏高，需要干预",
        }

    if glucose >= GLUCOSE_NORMAL_MAX:
        return {
            "level": RISK_MEDIUM,
            "reason": "血糖略高",
        }

    return {
        "level": RISK_LOW,
        "reason": "血糖正常",
    }