import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from email_assistant.graph.nodes import ACTION_NODES, fetch_emails, analyze_emails, plan_actions, flag_deadlines, generate_report, human_approval, final_summary
from email_assistant.graph.routing import has_proposed_actions, route_actions
from email_assistant.graph.state import AgentState

logger = logging.getLogger(__name__)


def build_graph():
    """Builds and returns the compiled email assistant graph."""
    workflow = StateGraph(AgentState)
    workflow.add_node("fetch_emails", fetch_emails)
    workflow.add_node("analyze_emails", analyze_emails)
    workflow.add_node("plan_actions", plan_actions)
    workflow.add_node("flag_deadlines", flag_deadlines)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("human_approval", human_approval)
    workflow.add_node("final_summary", final_summary)
    for name, node in ACTION_NODES.items():
        workflow.add_node(name, node)

    workflow.add_edge(START, "fetch_emails")
    workflow.add_edge("fetch_emails", "analyze_emails")
    workflow.add_edge("analyze_emails", "plan_actions")
    workflow.add_edge("plan_actions", "flag_deadlines")
    workflow.add_edge("flag_deadlines", "generate_report")
    workflow.add_conditional_edges(
        "generate_report",
        has_proposed_actions,
        {"human_approval": "human_approval", END: END},
    )
    workflow.add_conditional_edges(
        "human_approval",
        route_actions,
        {
            **{name: name for name in ACTION_NODES},
            "final_summary": "final_summary",
        },
    )
    for name in ACTION_NODES:
        workflow.add_edge(name, "final_summary")
    workflow.add_edge("final_summary", END)
    return workflow.compile(checkpointer=MemorySaver())
