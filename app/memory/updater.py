from typing import List

from app.memory.schemas import MemoryCandidate, MemoryUpdateResult
from app.memory import store

# 关键词过滤：长期偏好/习惯才写入
_ALLOW_ZH = ["一般", "通常", "习惯", "不喜欢", "喜欢", "长期", "目标", "经常", "偏好"]
_DENY_ZH = ["今天", "明天", "今晚", "这次", "提醒我", "血压是", "血糖是", "记录"]

_ALLOW_EN = ["usually", "generally", "prefer", "does not like", "often", "habit", "long-term"]
_DENY_EN = ["today", "tomorrow", "this morning", "remind me at", "blood pressure reading"]

_CATEGORY_MAP = {
    "profile": "profile",
    "preferences": "preferences",
    "care_context": "care_context",
}


def _passes_policy(content: str) -> bool:
    for kw in _DENY_ZH + _DENY_EN:
        if kw in content:
            return False
    for kw in _ALLOW_ZH + _ALLOW_EN:
        if kw in content:
            return True
    return False


def extract_candidates(session_summary: str) -> List[MemoryCandidate]:
    """把对话摘要按行拆分，每行作为一个候选。"""
    candidates = []
    for line in session_summary.splitlines():
        line = line.strip().lstrip("- ").strip()
        if not line:
            continue
        # 简单分类：含偏好词 → preferences，含背景词 → care_context，其余 → profile
        if any(kw in line for kw in ["喜欢", "不喜欢", "偏好", "prefer", "does not like"]):
            category = "preferences"
        elif any(kw in line for kw in ["关注", "管理", "目标", "goal", "focus"]):
            category = "care_context"
        else:
            category = "profile"
        candidates.append(MemoryCandidate(category=category, content=line))
    return candidates


def update_from_candidates(
    user_id: str,
    candidates: List[MemoryCandidate],
) -> MemoryUpdateResult:
    result = MemoryUpdateResult()
    for c in candidates:
        if not _passes_policy(c.content):
            result.skipped += 1
            continue
        key = _CATEGORY_MAP.get(c.category, "profile")
        store.append_to(user_id, key, c.content)
        result.added += 1
    return result
