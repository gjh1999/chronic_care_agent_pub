"""
全局常量定义
用于：
- intent key
- workflow node 名称
- plan / reminder 状态
- 风险等级
- 提醒来源
- 默认参数
"""

# Intent Keys

INTENT_NEED_RECORD = "need_record"
INTENT_NEED_ADVICE = "need_advice"
INTENT_NEED_PLAN = "need_plan"
INTENT_NEED_REMINDER = "need_reminder"
INTENT_NEED_HISTORY = "need_history"
INTENT_NEED_RISK = "need_risk"
INTENT_NEED_RAG = "need_rag"


# =========================
# Plan Status
# =========================

PLAN_STATUS_DRAFT = "draft"
PLAN_STATUS_ACTIVE = "active"
PLAN_STATUS_ARCHIVED = "archived"
PLAN_STATUS_REPLACED = "replaced"
PLAN_STATUS_CANCELLED = "cancelled"
PLAN_STATUS_EXPIRED = "expired"


# =========================
# Risk Level
# =========================

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_URGENT = "urgent"


# Workflow Node Names

NODE_PARSER = "parser_node"
NODE_NORMALIZE = "normalize_node"
NODE_RECORD = "record_node"

NODE_HISTORY = "history_node"
NODE_RISK = "risk_node"
NODE_RAG = "rag_node"
NODE_ADVICE = "advice_node"

NODE_PLAN_DRAFT = "plan_draft_node"
NODE_PLAN_CONFLICT = "plan_conflict_node"
NODE_USER_CONFIRM = "user_confirm_node"
NODE_PLAN_ARCHIVE = "plan_archive_node"

NODE_REMINDER_ROUTER = "reminder_router_node"
NODE_DIRECT_REMINDER = "direct_reminder_node"
NODE_REMINDER_CREATE = "reminder_create_node"

NODE_RESPONSE = "response_node"


# =========================
# User Confirm Result
# =========================

CONFIRM_ACCEPT = "confirm"
CONFIRM_REJECT = "reject"
CONFIRM_MODIFY = "modify"


# =========================
# Default Config
# =========================

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 1024


# =========================
# 健康指标阈值（可用于 rule engine）
# =========================

# 血糖（mmol/L）
GLUCOSE_NORMAL_MAX = 7.8
GLUCOSE_HIGH = 10.0
GLUCOSE_DANGEROUS = 16.0

# 血压（mmHg）
BP_SYSTOLIC_HIGH = 140
BP_DIASTOLIC_HIGH = 90


# =========================
# Reminder Defaults
# =========================

DEFAULT_REMINDER_REPEAT = False


# =========================
# 错误信息
# =========================

ERROR_PARSE_FAILED = "解析失败"
ERROR_PLAN_CONFLICT = "计划冲突"
ERROR_CONFIRM_REQUIRED = "需要用户确认"
