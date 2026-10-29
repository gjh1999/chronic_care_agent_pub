from typing import TypedDict, Optional, List, Dict, Any


class ClinicalState(TypedDict, total=False):
    user_id: str
    user_input: str
    conversation_id: str

    # memory
    memory_context: str
    task_preferences: str

    # parser output
    intent: Dict[str, Any]              # routing 路由标志
    intent_flags: Dict[str, bool]       # 兼容旧代码
    confidence: Dict[str, float]        # 各路由决策置信度
    extracted_data: Dict[str, Any]      # slots 槽位（对应 SchemaReadme）
    missing_fields: List[str]           # 需要追问的信息
    risk_flags: List[str]               # 风险标记
    normalized: Dict[str, Any]          # 标准化时间/单位

    # record
    record_result: Dict[str, Any]

    # advice
    history_data: List[Dict[str, Any]]
    risk_result: Dict[str, Any]
    rag_docs: List[Dict[str, Any]]
    advice: str

    # RAG subgraph
    rag_query: str
    rag_queries: List[str]
    rag_context: str
    rag_evidence: Dict[str, Any]
    rag_cache_hit: bool
    rag_error: Optional[str]
    rag_suggested_action: str
    rag_needs_human_confirmation: bool
    rag_quality_passed: Optional[bool]

    # plan
    plan_draft: Dict[str, Any]
    plan_conflicts: List[Dict[str, Any]]
    user_confirmed: Optional[bool]
    confirmed_plan: List[Dict[str, Any]]
    plan_archive_result: Dict[str, Any]

    # reminder
    reminder_source: Optional[str]
    direct_reminder: Dict[str, Any]
    reminder_created: bool
    reminder_result: Dict[str, Any]

    # output
    final_response: str
    error: Optional[str]
