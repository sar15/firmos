"""Workflow graph assembly; task logic is kept in its own small module."""
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from workflows import t1_vendor_bill as t1, t2_reconciliation as t2, t3_gstr2b as t3, t4_manual_filing as t4, t5_itr as t5
from workflows.state import WorkflowState


async def get_checkpointer(conn=None):
    """Use Postgres persistence only when its optional checkpoint driver is available."""
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from core.config import get_settings

        return AsyncPostgresSaver.from_conn_string(str(get_settings().database_url))
    except ImportError:
        return MemorySaver()


def build_t1_workflow() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("extract", t1.extract)
    graph.add_node("validate", t1.validate)
    graph.add_node("review_gate", t1.review_gate)
    graph.add_node("post_to_books", t1.post_to_books)
    graph.set_entry_point("extract")
    graph.add_conditional_edges("extract", t1.after_extract, {"failed": END, "validate": "validate"})
    graph.add_edge("validate", "review_gate")
    graph.add_edge("review_gate", "post_to_books")
    graph.add_edge("post_to_books", END)
    return graph


def build_t2_workflow() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("reconcile", t2.reconcile)
    graph.add_node("unmatched_gate", t2.unmatched_gate)
    graph.set_entry_point("reconcile")
    graph.add_edge("reconcile", "unmatched_gate")
    graph.add_edge("unmatched_gate", END)
    return graph


def build_t3_workflow() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("fetch_2b", t3.fetch_2b)
    graph.add_node("reconcile_2b", t3.reconcile_2b)
    graph.add_node("mismatch_gate", t3.mismatch_gate)
    graph.set_entry_point("fetch_2b")
    graph.add_edge("fetch_2b", "reconcile_2b")
    graph.add_edge("reconcile_2b", "mismatch_gate")
    graph.add_edge("mismatch_gate", END)
    return graph


def build_t4_workflow() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("compute", t4.compute)
    graph.add_node("approve_gate", t4.approve_gate)
    graph.add_node("manual_handoff", t4.manual_handoff)
    graph.set_entry_point("compute")
    graph.add_edge("compute", "approve_gate")
    graph.add_edge("approve_gate", "manual_handoff")
    graph.add_edge("manual_handoff", END)
    return graph


def build_t5_workflow() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("compute", t5.compute)
    graph.add_node("approve_gate", t5.approve_gate)
    graph.add_node("file", t5.file)
    graph.set_entry_point("compute")
    graph.add_edge("compute", "approve_gate")
    graph.add_edge("approve_gate", "file")
    graph.add_edge("file", END)
    return graph
