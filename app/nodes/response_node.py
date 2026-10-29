def response_node(state):
    parts = []

    if (state.get("risk_result") or {}).get("level") == "urgent":
        parts.append("🚨 当前数据达到高危范围，请尽快联系急救或前往急诊；不要自行调整药物。")

    if state.get("record_result"):
        parts.append("✅ 已记录数据")

    if state.get("advice"):
        parts.append(f"💡 建议：{state['advice']}")

    if state.get("confirmed_plan"):
        parts.append("📋 已生成健康计划")

    if state.get("reminder_created"):
        parts.append("⏰ 已创建提醒")

    state["final_response"] = "\n".join(parts) or "处理完成"
    return state
