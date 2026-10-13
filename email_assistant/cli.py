import logging
from datetime import datetime

from langgraph.types import Command

from email_assistant.database import init_db
from email_assistant.graph.builder import build_graph
from email_assistant.graph.state import AgentState
from email_assistant.logging_setup import setup_logging
from email_assistant.reporting.report import format_report

logger = logging.getLogger(__name__)
cli_logger = logging.getLogger("cli")


def run() -> None:
    """Initializes the app, runs the graph, and handles an approval pause."""
    setup_logging()
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": f"run-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"}}
    initial_state: AgentState = {
        "new_email_ids": [],
        "analyzed_ids": [],
        "flags": [],
        "report": {},
        "errors": [],
        "approved_action_ids": [],
        "final_summary": "",
    }
    result = graph.invoke(initial_state, config)
    report = result.get("report", {})
    if report:
        cli_logger.info("%s", format_report(report))

    while "__interrupt__" in result:
        action = result["__interrupt__"][0].value
        cli_logger.info(
            "Action ID: %s\nAction: %s\nSubject: %s\nSender: %s\nSummary: %s",
            action["id"],
            action["action_type"],
            action["subject"],
            action["sender"],
            action["summary"],
        )
        answer = input("Accept this action? (accept/y to approve; anything else to reject): ")
        result = graph.invoke(Command(resume=answer), config)

    if result.get("final_summary"):
        cli_logger.info("%s", result["final_summary"])
