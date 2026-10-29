def detect_plan_conflicts(new_plan: dict, existing_plans: list):
    """
    检查计划冲突
    """
    conflicts = []

    new_tasks = new_plan.get("tasks", [])

    for task in new_tasks:
        new_time = task.get("time")
        new_name = task.get("task")

        for plan in existing_plans:
            for old_task in plan.get("tasks", []):
                old_time = old_task.get("time")
                old_name = old_task.get("task")

                # 时间冲突
                if new_time == old_time:
                    conflicts.append({
                        "type": "time_conflict",
                        "msg": f"{new_time} 时间冲突",
                    })

                # 重复任务
                if new_name == old_name:
                    conflicts.append({
                        "type": "duplicate_task",
                        "msg": f"任务重复: {new_name}",
                    })

    return conflicts