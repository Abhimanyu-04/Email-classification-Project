import logging

from langgraph.graph import END

from email_assistant.actions.handlers import ACTION_HANDLERS
from email_assistant.graph.state import AgentState
from email_assistant.storage.action_store import get_actions_by_status, get_approved_actions

logger = logging.getLogger(__name__)

def has_proposed_actions(state: AgentState) -> str:
    """Routes to approval only when proposed actions remain."""
    if get_actions_by_status("proposed"):
        return "human_approval"
    return END

def route_actions(state: AgentState) -> list[str]:
    """Returns one action node for each action type with approved rows."""
    action_nodes = []
    for action_type in ACTION_HANDLERS:
        if get_approved_actions(action_type):
            action_nodes.append(f"act_{action_type}")
    return action_nodes or ["final_summary"]
