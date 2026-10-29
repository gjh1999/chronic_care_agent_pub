from app.core.rules.plan_conflict_rules import detect_plan_conflicts


def plan_conflict_node(state):
    new_plan = state.get("plan_draft", {})

    # mock已有计划（后面换DB）
    existing_plans = [
        {
            "tasks": [
                {"task": "测血糖", "time": "08:00"}
            ]
        }
    ]

    conflicts = detect_plan_conflicts(new_plan, existing_plans)

    state["plan_conflicts"] = conflicts
    return state