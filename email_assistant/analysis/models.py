import logging
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Allowed classification categories
Category = Literal[
    "family",
    "friends",
    "work",
    "subscriptions",
    "shopping",
    "bills_finance",
    "appointments",
    "travel",
    "account_security",
    "junk",
    "other",
]

# Allowed work types describing what is requested of the user
WorkType = Literal[
    "reply_required",
    "upcoming_event",
    "payment_due",
    "task_assigned",
    "fyi",
    "promotional",
]

# Allowed discrete agent actions
AgentAction = Literal[
    "draft_reply",
    "add_to_calendar",
    "add_todo",
    "archive",
    "unsubscribe",
    "mark_spam",
    "pay_bill",
]

class EmailAnalysis(BaseModel):
    """Structured analysis output model for an email message."""

    category: Category = Field(description="Primary category classification of the sender and message.")
    work_type: WorkType = Field(description="Primary demand or action requested of the user.")
    priority: Literal["high", "medium", "low"] = Field(description="Importance of the email (high, medium, or low).")
    summary: str = Field(description="One neutral sentence at most 25 words summarizing the email.")
    proposed_actions: list[AgentAction] = Field(default_factory=list, description="Conservative list of suggested actions.")
    due_date: date | None = Field(default=None, description="Deadline ISO date (YYYY-MM-DD) for user response or action.")
    due_time: str | None = Field(default=None, description="Deadline time in 24-hour HH:MM format.")
    event_title: str | None = Field(default=None, description="Title of the upcoming event or meeting.")
    event_date: date | None = Field(default=None, description="ISO date (YYYY-MM-DD) when the event occurs.")
    event_time: str | None = Field(default=None, description="Start time of the event in 24-hour HH:MM format.")
    event_location: str | None = Field(default=None, description="Venue or virtual link for the event.")
    todo_items: list[str] = Field(default_factory=list, description="Self-contained tasks for the user, each naming the specific thing and the recipient (e.g. 'Share the health report with HR'). No bare 'the report'.")
    date_phrase: str | None = Field(default=None, description="Verbatim date phrasing copied directly from email text.")
    confidence: float = Field(ge=0, le=1, description="Confidence score between 0.0 and 1.0.")

    @field_validator("proposed_actions", mode="after")
    @classmethod
    def deduplicate_actions(cls, actions: list[AgentAction]) -> list[AgentAction]:
        """Removes duplicate proposed actions while preserving original order."""
        seen = set()
        deduped = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                deduped.append(action)
        return deduped

    @field_validator("due_time", "event_time", mode="after")
    @classmethod
    def validate_time_format(cls, value: str | None) -> str | None:
        """Ensures times adhere to 24-hour HH:MM format when specified."""
        if value is not None and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value):
            raise ValueError(f"Time '{value}' must be in 24-hour HH:MM format (00:00 to 23:59).")
        return value

    @model_validator(mode="after")
    def validate_relational_rules(self) -> "EmailAnalysis":
        """Validates cross-field logical rules between dates, actions, and work types."""
        # Times require corresponding dates
        if self.due_time is not None and self.due_date is None:
            raise ValueError("due_time requires due_date to be set.")
        if self.event_time is not None and self.event_date is None:
            raise ValueError("event_time requires event_date to be set.")

        # Calendar action requirements
        if "add_to_calendar" in self.proposed_actions:
            if self.event_date is None or not self.event_title:
                raise ValueError("'add_to_calendar' requires both event_date and event_title to be set.")

        # Todo action requirements
        if "add_todo" in self.proposed_actions and len(self.todo_items) == 0:
            raise ValueError("'add_todo' requires at least one task in todo_items.")
        if len(self.todo_items) > 0 and "add_todo" not in self.proposed_actions:
            raise ValueError("todo_items is non-empty, so 'add_todo' must be included in proposed_actions.")

        # Pay bill requirements
        if "pay_bill" in self.proposed_actions and self.work_type != "payment_due":
            raise ValueError("'pay_bill' is only valid when work_type is 'payment_due'.")

        # Reply required requirements
        if self.work_type == "reply_required" and "draft_reply" not in self.proposed_actions:
            raise ValueError("work_type 'reply_required' requires 'draft_reply' in proposed_actions.")

        # Junk email and mark_spam constraints
        if "mark_spam" in self.proposed_actions and self.category != "junk":
            raise ValueError("'mark_spam' is only permitted when category is 'junk'.")
        if self.category == "junk":
            if self.proposed_actions != ["mark_spam"]:
                raise ValueError("When category is 'junk', proposed_actions must strictly be ['mark_spam'].")

        return self
