"""Runs the eight check steps in a fixed order.

Nothing branches. The screen does not watch this graph. It reads the stage
rows in the database. The only thing passed from one step to the next is
the text of the discharge, page by page.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.models import STAGE_NAMES
from app.workflow.steps import build_nodes


class PipelineState(TypedDict, total=False):
    job_id: str
    pages: list  # discharge text, filled in by the first step


def build_graph(session: Session):
    nodes = build_nodes(session)
    graph = StateGraph(PipelineState)
    order = list(STAGE_NAMES)
    for name in order:
        graph.add_node(name, nodes[name])
    # parsed -> chunked -> embedded -> ... -> done
    graph.add_edge(START, order[0])
    for current, nxt in zip(order, order[1:], strict=False):
        graph.add_edge(current, nxt)
    graph.add_edge(order[-1], END)
    return graph.compile()
