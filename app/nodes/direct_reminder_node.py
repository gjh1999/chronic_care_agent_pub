def direct_reminder_node(state):
    extracted_data = state.get("extracted_data") or {}
    reminder_slots = extracted_data.get("reminder") or {}
    if not isinstance(reminder_slots, dict):
        reminder_slots = {}

    task = reminder_slots.get("task") or "健康提醒"
    time = reminder_slots.get("time") or "21:00"
    repeat = reminder_slots.get("repeat")

    state["direct_reminder"] = {
        "task": task,
        "time": time,
        "repeat": repeat,
    }
    return state
