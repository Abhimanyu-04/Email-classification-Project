import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Tracks fetched and analyzed emails, flags, approval, and final results."""

    new_email_ids: list[str]
    analyzed_ids: list[str]
    flags: list[dict]
    report: dict
    errors: list[dict]
    approved_action_ids: list[int]
    final_summary: str
