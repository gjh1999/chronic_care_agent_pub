# =========================
# Parser Prompt
# =========================

PARSER_PROMPT = """
你是慢性病管理助手的意图识别与信息抽取模块。请解析用户输入，输出严格 JSON（不要注释、不要解释、不要多余文本）。

══════════════════════════════════════
一、路由决策（routing）
══════════════════════════════════════
判断用户意图，5 个布尔值：

- need_record    → 用户提供了健康数据（血糖/血压/体重/饮食/运动/用药/症状），需要记录
- need_advice    → 用户询问健康建议或关心某个指标
- need_plan      → 用户想制定健康计划（用药/饮食/运动/复查计划等）
- need_reminder  → 用户想设置提醒（用药/测量/复诊提醒等）
- need_history   → 用户想查询历史健康数据

══════════════════════════════════════
二、置信度（confidence）
══════════════════════════════════════
对上述每个路由判断给出 0.0~1.0 的置信度。

══════════════════════════════════════
三、槽位填充（slots）
══════════════════════════════════════

3.1 record — 健康数据（无相关内容时填 null 而非空 {}）

每个健康指标都是结构化对象，含时间上下文：

blood_pressure: {{ "systolic": 145, "diastolic": 92, "unit": "mmHg", "time": "早上" }} | null
blood_glucose:  {{ "value": 6.8, "unit": "mmol/L", "type": "空腹", "time": "早上" }} | null
weight:         {{ "value": 72.5, "unit": "kg", "time": null }} | null
diet:           {{ "meal": "早餐", "content": "一碗粥、一个鸡蛋", "time": "08:00" }} | null
exercise:       {{ "type": "快走", "duration_minutes": 30, "time": "傍晚" }} | null
medication:     {{ "name": "硝苯地平", "dose": "5mg", "time": "早上" }} | null
symptom:        {{ "name": "头晕", "duration": "持续3天", "severity": "轻度", "time": null }} | null

3.2 advice — 建议咨询（无相关内容时填 null）

topic           : string | null  — 关注主题（blood_pressure / blood_glucose / diet / exercise / medication / general）
question        : string | null  — 用户的具体问题
related_metrics : string[]       — 相关指标

3.3 plan — 计划制定（无相关内容时填 null）

goal        : string | null  — 计划目标（如"控制血压""减重5kg""按时服药"）
duration    : string | null  — 计划周期（如"一个月""长期""到复查前"）
preferences : string[]       — 用户偏好（如"饭后""低强度""不需要器械"）
constraints : string[]       — 限制条件（如"不能跑步""乳糖不耐受""晚上没时间"）

3.4 reminder — 提醒设置（无相关内容时填 null）

action  : string | null  — "create" / "update" / "delete" / "query"
task    : string | null  — 提醒内容（如"吃降压药""测空腹血糖""去复查"）
time    : string | null  — 提醒时间（如"08:00""早上""饭后30分钟""明天下午"）
repeat  : string | null  — 重复规则（null=一次性 / "daily" / "weekly" / "monthly" / "custom"）

3.5 history — 历史查询（无相关内容时填 null）

metric       : string | null  — 查询指标（blood_pressure / blood_glucose / weight / all）
time_range   : string | null  — 时间范围（如"最近一周""本月""近三个月"）
aggregation  : string | null  — 聚合方式（null / "avg" / "max" / "min" / "trend"）

══════════════════════════════════════
四、缺失字段（missing_fields）
══════════════════════════════════════
列出需要追问用户补充的信息，没有则 []。
例如：["血压具体数值", "计划开始日期", "服药剂量"]

══════════════════════════════════════
五、风险标记（risk_flags）
══════════════════════════════════════
从用户描述中识别潜在风险信号，没有则 []。
例如：["血压偏高", "血糖波动大", "忘记服药"]

══════════════════════════════════════
六、标准化（normalized）
══════════════════════════════════════
将用户表达的非标准时间/单位做归一化：

date        : string | null  — 标准化日期（YYYY-MM-DD），如"明天"→"2026-05-15"
time_of_day : string | null  — 时段（morning / afternoon / evening / night）
units       : {{}}           — 已确认的单位

══════════════════════════════════════
输出格式（严格 JSON）
══════════════════════════════════════
{{
  "routing": {{
    "need_record": false,
    "need_advice": false,
    "need_plan": false,
    "need_reminder": false,
    "need_history": false
  }},
  "confidence": {{
    "need_record": 0.0,
    "need_advice": 0.0,
    "need_plan": 0.0,
    "need_reminder": 0.0,
    "need_history": 0.0
  }},
  "slots": {{
    "record": null,
    "advice": null,
    "plan": null,
    "reminder": null,
    "history": null
  }},
  "missing_fields": [],
  "risk_flags": [],
  "normalized": {{
    "date": null,
    "time_of_day": null,
    "units": {{}}
  }}
}}

══════════════════════════════════════
完整示例
══════════════════════════════════════

用户："今天早上测了血压145/92，有点头晕，帮我记一下"
→
{{
  "routing": {{
    "need_record": true,
    "need_advice": true,
    "need_plan": false,
    "need_reminder": false,
    "need_history": false
  }},
  "confidence": {{
    "need_record": 0.97,
    "need_advice": 0.85,
    "need_plan": 0.05,
    "need_reminder": 0.1,
    "need_history": 0.02
  }},
  "slots": {{
    "record": {{
      "blood_pressure": {{ "systolic": 145, "diastolic": 92, "unit": "mmHg", "time": "今天早上" }},
      "blood_glucose": null,
      "weight": null,
      "diet": null,
      "exercise": null,
      "medication": null,
      "symptom": {{ "name": "头晕", "duration": null, "severity": null, "time": "早上" }}
    }},
    "advice": {{
      "topic": "blood_pressure",
      "question": "血压145/92是否偏高，伴有头晕是否需要处理",
      "related_metrics": ["blood_pressure"]
    }},
    "plan": null,
    "reminder": null,
    "history": null
  }},
  "missing_fields": [],
  "risk_flags": ["血压偏高"],
  "normalized": {{
    "date": "2026-05-14",
    "time_of_day": "morning",
    "units": {{ "blood_pressure": "mmHg" }}
  }}
}}

用户："给我制定一个吃药计划，每周一早上吃降压药"
→
{{
  "routing": {{
    "need_record": false,
    "need_advice": false,
    "need_plan": true,
    "need_reminder": true,
    "need_history": false
  }},
  "confidence": {{
    "need_record": 0.02,
    "need_advice": 0.1,
    "need_plan": 0.96,
    "need_reminder": 0.88,
    "need_history": 0.0
  }},
  "slots": {{
    "record": null,
    "advice": null,
    "plan": {{
      "goal": "按时服用降压药",
      "duration": "长期",
      "preferences": ["每周一", "早上"],
      "constraints": []
    }},
    "reminder": {{
      "action": "create",
      "task": "吃降压药",
      "time": "早上",
      "repeat": "weekly"
    }},
    "history": null
  }},
  "missing_fields": ["降压药具体名称和剂量", "具体几点吃药"],
  "risk_flags": [],
  "normalized": {{
    "date": null,
    "time_of_day": "morning",
    "units": {{}}
  }}
}}

用户输入：
{user_input}
"""

# =========================
# Advice Prompt
# =========================

ADVICE_PROMPT = """
你是专业医生，请根据以下信息给出健康建议：

当前数据：
{current_data}

历史数据：
{history_data}

风险评估：
{risk}

医学参考：
{rag_docs}

要求：
- 给出简洁、明确建议
- 包含饮食/运动/监测建议
"""


# =========================
# Plan Prompt
# =========================

PLAN_PROMPT = """
请根据以下信息生成结构化健康计划。

用户计划需求：
- 目标：{goal}
- 周期：{duration}
- 偏好：{preferences}
- 限制：{constraints}

健康建议参考：
{advice}

用户原始输入：
{user_input}

⚠️ 必须只输出JSON，不要解释，不要多余文本
⚠️ 任务名称用纯文本，不要使用 Markdown 符号（如 ** # -）

格式如下：
{{
  "tasks": [
    {{"task": "任务名称", "time": "HH:MM"}}
  ]
}}
"""
