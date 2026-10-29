def user_confirm_node(state):
    """保留调用方提供的确认状态；未确认时必须停在草稿态。

    持久化 interrupt/resume 由 conversation service 管理。禁止默认同意，
    否则生成计划会在用户看到之前就产生副作用。
    """
    return {**state, "user_confirmed": state.get("user_confirmed")}
