# app/core/tools/stats_tool.py

from typing import List, Dict, Any, Optional


def safe_float(value: Any) -> Optional[float]:
    """
    安全转换 float。
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def average(values: List[float]) -> Optional[float]:
    """
    计算平均值。
    """

    valid_values = [v for v in values if isinstance(v, (int, float))]

    if not valid_values:
        return None

    return round(sum(valid_values) / len(valid_values), 2)


def glucose_trend(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析血糖趋势。

    records 示例：
    [
        {"date": "2026-04-28", "glucose": 8.5},
        {"date": "2026-04-29", "glucose": 9.2}
    ]
    """

    values = []

    for record in records:
        value = (
            record.get("glucose")
            or record.get("blood_glucose")
            or record.get("value")
        )

        value = safe_float(value)

        if value is not None:
            values.append(value)

    if not values:
        return {
            "count": 0,
            "average": None,
            "trend": "unknown",
            "latest": None,
        }

    latest = values[-1]
    avg = average(values)

    if len(values) < 2:
        trend = "stable"
    elif values[-1] > values[0]:
        trend = "up"
    elif values[-1] < values[0]:
        trend = "down"
    else:
        trend = "stable"

    return {
        "count": len(values),
        "average": avg,
        "trend": trend,
        "latest": latest,
        "min": min(values),
        "max": max(values),
    }


def blood_pressure_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析血压记录。
    """

    systolic_values = []
    diastolic_values = []

    for record in records:
        bp = record.get("blood_pressure")

        if isinstance(bp, str) and "/" in bp:
            parts = bp.split("/")
            if len(parts) == 2:
                systolic = safe_float(parts[0])
                diastolic = safe_float(parts[1])

                if systolic is not None:
                    systolic_values.append(systolic)

                if diastolic is not None:
                    diastolic_values.append(diastolic)

        elif isinstance(bp, dict):
            systolic = safe_float(bp.get("systolic"))
            diastolic = safe_float(bp.get("diastolic"))

            if systolic is not None:
                systolic_values.append(systolic)

            if diastolic is not None:
                diastolic_values.append(diastolic)

    return {
        "count": min(len(systolic_values), len(diastolic_values)),
        "avg_systolic": average(systolic_values),
        "avg_diastolic": average(diastolic_values),
        "latest_systolic": systolic_values[-1] if systolic_values else None,
        "latest_diastolic": diastolic_values[-1] if diastolic_values else None,
    }


def build_health_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    汇总健康数据统计。
    """

    return {
        "glucose": glucose_trend(records),
        "blood_pressure": blood_pressure_summary(records),
    }