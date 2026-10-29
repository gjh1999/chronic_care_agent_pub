from langgraph.graph import StateGraph, END

from app.graph.state import ClinicalState
from app.graph.plan_reminder_graph import build_plan_reminder_subgraph

from app.config.constants import (
    NODE_PARSER,
    NODE_NORMALIZE,
    NODE_RECORD,
    NODE_HISTORY,
    NODE_RISK,
    NODE_RAG,
    NODE_ADVICE,
    NODE_RESPONSE,
)

from app.nodes.parser_node import parser_node
from app.graph.normalizer import normalize_intent_node
from app.nodes.record_node import record_node
from app.nodes.history_node import history_node
from app.nodes.risk_node import risk_node
from app.nodes.rag_node import rag_node
from app.nodes.advice_node import advice_node
from app.nodes.response_node import response_node

from app.graph.routing import (
    route_after_normalize,
    route_after_record,
    route_after_advice,
)

# 子图挂载的节点名
NODE_PLAN_REMINDER_SUB = "plan_reminder_sub"


def build_graph():
    graph = StateGraph(ClinicalState)

    plan_reminder_subgraph = build_plan_reminder_subgraph()

    # -----------------------------------------------------------------------
    # 注册节点
    # -----------------------------------------------------------------------

    graph.add_node(NODE_PARSER, parser_node)
    graph.add_node(NODE_NORMALIZE, normalize_intent_node)
    graph.add_node(NODE_RECORD, record_node)
    graph.add_node(NODE_HISTORY, history_node)
    graph.add_node(NODE_RISK, risk_node)
    graph.add_node(NODE_RAG, rag_node)
    graph.add_node(NODE_ADVICE, advice_node)
    graph.add_node(NODE_PLAN_REMINDER_SUB, plan_reminder_subgraph)
    graph.add_node(NODE_RESPONSE, response_node)

    # -----------------------------------------------------------------------
    # 入口
    # -----------------------------------------------------------------------

    graph.set_entry_point(NODE_PARSER)
    graph.add_edge(NODE_PARSER, NODE_NORMALIZE)

    # -----------------------------------------------------------------------
    # normalize 之后路由
    # -----------------------------------------------------------------------

    graph.add_conditional_edges(
        NODE_NORMALIZE,
        route_after_normalize,
        {
            NODE_RECORD: NODE_RECORD,
            NODE_HISTORY: NODE_HISTORY,
            NODE_PLAN_REMINDER_SUB: NODE_PLAN_REMINDER_SUB,
            NODE_RESPONSE: NODE_RESPONSE,
        },
    )

    # -----------------------------------------------------------------------
    # record 之后路由
    # -----------------------------------------------------------------------

    graph.add_conditional_edges(
        NODE_RECORD,
        route_after_record,
        {
            NODE_HISTORY: NODE_HISTORY,
            NODE_PLAN_REMINDER_SUB: NODE_PLAN_REMINDER_SUB,
            NODE_RESPONSE: NODE_RESPONSE,
        },
    )

    # -----------------------------------------------------------------------
    # 健康分析链
    # -----------------------------------------------------------------------

    graph.add_edge(NODE_HISTORY, NODE_RISK)
    graph.add_edge(NODE_RISK, NODE_RAG)
    graph.add_edge(NODE_RAG, NODE_ADVICE)

    # -----------------------------------------------------------------------
    # advice 之后路由
    # -----------------------------------------------------------------------

    graph.add_conditional_edges(
        NODE_ADVICE,
        route_after_advice,
        {
            NODE_PLAN_REMINDER_SUB: NODE_PLAN_REMINDER_SUB,
            NODE_RESPONSE: NODE_RESPONSE,
        },
    )

    # -----------------------------------------------------------------------
    # 子图结束后回到 response
    # -----------------------------------------------------------------------

    graph.add_edge(NODE_PLAN_REMINDER_SUB, NODE_RESPONSE)
    graph.add_edge(NODE_RESPONSE, END)

    return graph.compile()
