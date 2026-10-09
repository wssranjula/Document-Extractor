from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.pipeline.nodes import build_nodes


class PipelineState(TypedDict, total=False):
    job_id: str
    pages: list


def build_graph(session: Session):
    nodes = build_nodes(session)
    graph = StateGraph(PipelineState)
    for name, node in nodes.items():
        graph.add_node(name, node)
    order = list(nodes)
    graph.add_edge(START, order[0])
    for current, nxt in zip(order, order[1:], strict=False):
        graph.add_edge(current, nxt)
    graph.add_edge(order[-1], END)
    return graph.compile()
