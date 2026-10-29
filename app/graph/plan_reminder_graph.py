from langgraph.graph import StateGraph, END

from app.graph.state import ClinicalState
from app.config.constants import (
    NODE_PLAN_DRAFT,
    NODE_PLAN_CONFLICT,
    NODE_USER_CONFIRM,
    NODE_PLAN_ARCHIVE,
    NODE_REMINDER_ROUTER,
    NODE_DIRECT_REMINDER,
    NODE_REMINDER_CREATE,
)

from app.nodes.plan_draft_node import plan_draft_node
from app.nodes.plan_conflict_node import plan_conflict_node
from app.nodes.user_confirm_node import user_confirm_node
from app.nodes.plan_archive_node import plan_archive_node
from app.nodes.reminder_router_node import reminder_router_node
from app.nodes.direct_reminder_node import direct_reminder_node
from app.nodes.reminder_create_node import reminder_create_node


# ---------------------------------------------------------------------------
# 子图内部路由
#
# 计划提醒在 plan_archive_node 确认计划时由 confirm_plan 服务创建,
# 子图内不再有独立的 plan_reminder 链;REMINDER_ROUTER 之后只处理直接提醒。
# ---------------------------------------------------------------------------

def _route_after_user_confirm(state: ClinicalState) -> str:
    if state.get("user_confirmed") is True:
        return NODE_PLAN_ARCHIVE
    flags = state.get("intent_flags", {})
    intent = state.get("intent", {})
    if flags.get("need_reminder") or intent.get("need_reminder"):
        return NODE_REMINDER_ROUTER
    return END


# ---------------------------------------------------------------------------
# 子图入口路由（决定从 plan 链还是 reminder 链进入）
# ---------------------------------------------------------------------------

_NODE_ENTRY = "plan_reminder_entry"


def _entry_node(state: ClinicalState) -> ClinicalState:
    return state


def _route_entry(state: ClinicalState) -> str:
    flags = state.get("intent_flags", {})
    intent = state.get("intent", {})
    if flags.get("need_plan") or intent.get("need_plan"):
        return NODE_PLAN_DRAFT
    return NODE_REMINDER_ROUTER


# ---------------------------------------------------------------------------
# 子图 builder
# ---------------------------------------------------------------------------

def build_plan_reminder_subgraph():
    g = StateGraph(ClinicalState)

    g.add_node(_NODE_ENTRY, _entry_node)
    g.add_node(NODE_PLAN_DRAFT, plan_draft_node)
    g.add_node(NODE_PLAN_CONFLICT, plan_conflict_node)
    g.add_node(NODE_USER_CONFIRM, user_confirm_node)
    g.add_node(NODE_PLAN_ARCHIVE, plan_archive_node)
    g.add_node(NODE_REMINDER_ROUTER, reminder_router_node)
    g.add_node(NODE_DIRECT_REMINDER, direct_reminder_node)
    g.add_node(NODE_REMINDER_CREATE, reminder_create_node)

    g.set_entry_point(_NODE_ENTRY)

    g.add_conditional_edges(
        _NODE_ENTRY,
        _route_entry,
        {
            NODE_PLAN_DRAFT: NODE_PLAN_DRAFT,
            NODE_REMINDER_ROUTER: NODE_REMINDER_ROUTER,
        },
    )

    # plan 链:确认后由 plan_archive_node 落库并创建计划提醒,直接结束
    g.add_edge(NODE_PLAN_DRAFT, NODE_PLAN_CONFLICT)
    g.add_edge(NODE_PLAN_CONFLICT, NODE_USER_CONFIRM)

    g.add_conditional_edges(
        NODE_USER_CONFIRM,
        _route_after_user_confirm,
        {
            NODE_PLAN_ARCHIVE: NODE_PLAN_ARCHIVE,
            NODE_REMINDER_ROUTER: NODE_REMINDER_ROUTER,
            END: END,
        },
    )

    g.add_edge(NODE_PLAN_ARCHIVE, END)

    # reminder 链:仅处理直接提醒
    g.add_edge(NODE_REMINDER_ROUTER, NODE_DIRECT_REMINDER)
    g.add_edge(NODE_DIRECT_REMINDER, NODE_REMINDER_CREATE)
    g.add_edge(NODE_REMINDER_CREATE, END)

    return g.compile()
