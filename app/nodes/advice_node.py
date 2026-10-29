from typing import Any, Dict

from app.core.llm.client import llm_client
from app.graph.state import ClinicalState
from app.service.stream import current_sink, emit_status, emit_token
from app.utils.text import strip_markdown


def advice_node(state: ClinicalState) -> Dict[str, Any]:
    user_input = state.get("user_input", "")
    extracted_data = state.get("extracted_data", {})
    history_data = state.get("history_data", [])
    risk_result = state.get("risk_result", {})
    risk_level = risk_result.get("level", "low") if risk_result else "low"
    risk_reasons = risk_result.get("reason", "") if risk_result else ""
    rag_context = state.get("rag_context", "")
    memory_context = state.get("memory_context", "")

    # Urgent local rules always win and must not wait for RAG or an LLM.
    if risk_level == "urgent":
        return {
            "advice": (
                "当前数据达到高危范围。请停止依赖在线建议，尽快联系急救或前往急诊；"
                "如伴胸痛、呼吸困难、意识异常、严重头痛等症状，请立即呼叫急救。"
                "不要自行加减药。"
            ),
            "messages": state.get("messages", []) + ["高风险规则已拦截 LLM 建议"],
        }

    rag_action = state.get("rag_suggested_action") or (
        "continue" if rag_context else "evidence_insufficient"
    )
    rag_needs_human = state.get("rag_needs_human_confirmation", False)
    rag_quality_passed = state.get("rag_quality_passed")

    if rag_needs_human or rag_action == "need_human_confirmation":
        return {
            "advice": (
                "检索到的信息需要医生进一步确认，目前不能据此给出诊断或调整用药。"
                "请携带近期测量记录咨询医生；在获得专业意见前，请勿自行增减或停用药物。"
            ),
            "messages": state.get("messages", []) + ["RAG 结果需人工确认，已跳过 LLM 医学建议"],
        }

    if rag_action == "ask_user_clarification":
        return {
            "advice": (
                "现有信息不足以检索到可靠依据。请补充具体症状、测量数值与单位、"
                "测量时间，以及正在使用的药物；如症状明显或持续加重，请及时就医。"
            ),
            "messages": state.get("messages", []) + ["需要补充信息，已跳过 LLM 医学建议"],
        }

    if rag_action == "external_service_unavailable":
        return {
            "advice": (
                "医学知识检索服务暂时不可用，因此本次无法提供有指南依据的个体化建议。"
                "请稍后重试；如症状明显、持续加重或对用药有疑问，请咨询医生，勿自行调整用药。"
            ),
            "messages": state.get("messages", []) + ["RAG 不可用，已跳过 LLM 医学建议"],
        }

    if rag_action not in {"continue", "retry_done"} or not rag_context or rag_quality_passed is False:
        return {
            "advice": (
                "当前知识库没有找到足够可靠的依据，暂时不能给出确定的医学建议。"
                "你可以补充具体症状、测量数值与时间后重试；涉及诊断或用药请咨询医生。"
            ),
            "messages": state.get("messages", []) + ["RAG 证据不足，已跳过 LLM 医学建议"],
        }

    slots = extracted_data or {}
    advice_slots = slots.get("advice") or {}
    advice_question = advice_slots.get("question", "") if isinstance(advice_slots, dict) else ""

    prompt = f"""
你是一个慢性病管理助手，不是医生，不能替代线下诊断。
请仅基于以下用户数据、规则评估和已放行的 RAG 证据生成健康建议。

【用户长期上下文】{memory_context}

【用户问题】{user_input}
{advice_question}

【当前健康数据】{extracted_data}

【历史健康数据】{history_data}

【规则风险评估】风险等级：{risk_level}
风险原因：{risk_reasons}

【RAG 证据状态】
suggested_action={rag_action}
quality_passed={rag_quality_passed}
needs_human_confirmation={rag_needs_human}

【RAG 检索医学证据】{rag_context}

回答要求：
1. 先给出简短结论。
2. 依据只能来自用户数据、规则风险评估或上面的 RAG 证据。
3. 不要编造 RAG 证据中没有的医学结论。
4. 区分健康管理建议和需要医生判断的部分。
5. 不提供诊断、处方或自行调整用药的指令。
6. 给出可执行的下一步建议。
7. 总字数控制在 300 字以内，重点是结论与可执行步骤，不要使用 Markdown 语法。
"""

    emit_status("正在生成建议…")
    sink = current_sink()
    if sink is not None:
        advice = llm_client.invoke_stream(
            prompt,
            system_prompt="你是慢性病健康管理助手，不做诊断或处方。",
            max_tokens=800,
            on_token=emit_token,
        )
    else:
        advice = llm_client.invoke(
            prompt,
            system_prompt="你是慢性病健康管理助手，不做诊断或处方。",
            max_tokens=800,
        )
    advice = strip_markdown(advice)
    return {
        "advice": advice,
        "messages": state.get("messages", []) + ["已基于通过质量检查的 RAG 证据生成健康建议"],
    }
