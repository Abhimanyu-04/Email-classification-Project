import json
import logging
import os
import time
from datetime import date

import groq
import logfire
from langgraph.types import interrupt

from email_assistant.actions.handlers import ACTION_HANDLERS
from email_assistant.analysis.analyzer import analyze_email
from email_assistant.config import get_settings
from email_assistant.mail.fetcher import fetch_new_emails
from email_assistant.reporting.flags import compute_flags
from email_assistant.reporting.report import build_report
from email_assistant.storage.action_store import (
    get_actions_by_ids,
    get_actions_by_status,
    get_approved_actions,
    plan_actions_for_emails,
    set_action_statuses,
    update_action_result,
)
from email_assistant.storage.email_store import (
    get_all_analyzed_emails,
    get_emails_by_ids,
    get_emails_to_analyze,
    mark_analysis_failed,
    save_analysis,
)
from email_assistant.graph.state import AgentState

logger = logging.getLogger(__name__)
settings = get_settings()

def fetch_emails(state: AgentState) -> dict:
    """Node: fetches new emails from Mailpit and commits initial rows to SQLite."""
    logger.info("Node started: fetch_emails")
    new_emails = fetch_new_emails()
    new_ids = [e["message_id"] for e in new_emails]
    logger.info("Node finished: fetch_emails with %d new email(s)", len(new_ids))
    return {"new_email_ids": new_ids}

def analyze_emails(state: AgentState) -> dict:
    """Node: analyzes pending emails one by one, immediately updating the database with raw contents & analysis results."""
    logger.info("Node started: analyze_emails")
    pending_emails = get_emails_to_analyze(settings.max_analysis_attempts)
    analyzed_ids = []
    errors = []

    for email in pending_emails:
        msg_id = email["message_id"]
        subject = email.get("subject", "")

        with logfire.span("analyze_email", message_id=msg_id):
            try:
                analysis = analyze_email(email)
                # Save structured analysis AND ensure raw email fields (body, sender, etc.) are up-to-date
                save_analysis(
                    msg_id,
                    analysis.model_dump(mode="json"),
                    settings.groq_model,
                    email=email,
                )
                analyzed_ids.append(msg_id)
                logger.info(
                    "Analyzed: '%s' | Category: %s | Priority: %s | Actions: %s",
                    subject,
                    analysis.category,
                    analysis.priority,
                    analysis.proposed_actions,
                )
            except groq.RateLimitError:
                logger.warning("Rate limit hit while analyzing '%s'. Halting loop for next run.", subject)
                break
            except Exception as exc:
                logger.exception("Error analyzing email '%s' (%s)", subject, msg_id)
                mark_analysis_failed(msg_id, str(exc))
                errors.append({"message_id": msg_id, "subject": subject, "error": str(exc)})

        time.sleep(settings.llm_call_delay_seconds)

    logger.info(
        "Node finished: analyze_emails. Analyzed: %d, Failed: %d",
        len(analyzed_ids),
        len(errors),
    )
    return {"analyzed_ids": analyzed_ids, "errors": errors}

def plan_actions(state: AgentState) -> dict:
    """Node: creates proposed action rows in the actions table for analyzed emails."""
    logger.info("Node started: plan_actions")
    created_count = plan_actions_for_emails(state.get("analyzed_ids", []))
    logger.info("Node finished: plan_actions. Created %d action row(s).", created_count)
    return {}

def flag_deadlines(state: AgentState) -> dict:
    """Node: computes upcoming deadlines and events, writes to JSON calendar file, and returns flags."""
    logger.info("Node started: flag_deadlines")
    all_analyzed = get_all_analyzed_emails()
    today = date.today()
    flags = compute_flags(all_analyzed, today)

    # Ensure directory exists and write JSON file
    cal_dir = os.path.dirname(settings.flag_calendar_path)
    if cal_dir:
        os.makedirs(cal_dir, exist_ok=True)

    with open(settings.flag_calendar_path, "w", encoding="utf-8") as f:
        json.dump(flags, f, indent=2)

    today_count = sum(1 for item in flags if item.get("flag") == "today")
    week_count = sum(1 for item in flags if item.get("flag") == "this_week")
    logger.info(
        "Node finished: flag_deadlines. Saved %d flag(s) (today: %d, this_week: %d) to %s",
        len(flags),
        today_count,
        week_count,
        settings.flag_calendar_path,
    )
    return {"flags": flags}

def generate_report(state: AgentState) -> dict:
    """Node: compiles this run's emails, flags, and actions into a markdown report."""
    logger.info("Node started: generate_report")
    run_emails = get_emails_by_ids(state.get("analyzed_ids", []))
    proposed_actions = get_actions_by_status("proposed")
    report = build_report(
        run_emails=run_emails,
        flags=state.get("flags", []),
        proposed_actions=proposed_actions,
        errors=state.get("errors", []),
        today=date.today(),
    )
    report_dir = os.path.dirname(settings.report_path)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
    with open(settings.report_path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False)

    logger.info("Saved report to %s", settings.report_path)
    logger.info("Node finished: generate_report.")
    return {"report": report}

def human_approval(state: AgentState) -> dict:
    """Pauses for a decision on each proposed action, then records the results."""
    proposed = get_actions_by_status("proposed")
    emails = get_emails_by_ids([item["message_id"] for item in proposed])
    email_by_id = {email["message_id"]: email for email in emails}
    approved_ids = []

    for action in proposed:
        email = email_by_id.get(action["message_id"], {})
        decision = interrupt(
            {
                "id": action["id"],
                "action_type": action["action_type"],
                "subject": action.get("subject", ""),
                "sender": email.get("sender", ""),
                "summary": email.get("summary", ""),
            }
        )
        if isinstance(decision, str) and decision.strip().lower() in {"accept", "y"}:
            approved_ids.append(action["id"])

    set_action_statuses(approved_ids)
    approved_count = sum(item["id"] in approved_ids for item in proposed)
    rejected_count = len(proposed) - approved_count
    logger.info("Human approval complete: %d approved, %d rejected.", approved_count, rejected_count)
    return {"approved_action_ids": approved_ids}

def make_action_node(action_type: str):
    """Creates a node that executes approved rows of one action type."""
    # The node logic is identical for each action type; only the handler changes.
    def action_node(state: AgentState) -> dict:
        """Runs the selected action handler for each approved row."""
        actions = get_approved_actions(action_type)
        for action in actions:
            action_id = action["id"]
            try:
                emails = get_emails_by_ids([action["message_id"]])
                if not emails:
                    raise ValueError(f"Email not found for action id {action_id}")
                with logfire.span("action", action_type=action_type, action_id=action_id):
                    result = ACTION_HANDLERS[action_type](emails[0])
                update_action_result(action_id, "executed", result)
                logger.info("Action %d (%s) executed.", action_id, action_type)
            except NotImplementedError as exc:
                update_action_result(action_id, "not_implemented", {"reason": str(exc)})
                logger.info("Action %d (%s) is not implemented.", action_id, action_type)
            except Exception as exc:
                logger.exception("Action %d (%s) failed.", action_id, action_type)
                update_action_result(action_id, "failed", {"error": str(exc)})
        return {}

    return action_node

def final_summary(state: AgentState) -> dict:
    """Summarizes completed and incomplete approved actions."""
    actions = get_actions_by_ids(state["approved_action_ids"])
    done = []
    not_done = []
    for action in actions:
        description = f"{action['action_type']} - {action.get('subject', '')}"
        if action["status"] == "executed":
            done.append(description)
        elif action["status"] in {"failed", "not_implemented"}:
            result = json.loads(action["result"] or "{}")
            reason = result.get("error") or result.get("reason") or action["status"]
            not_done.append(f"{description} ({reason})")

    summary = f"Done: {', '.join(done) if done else 'none'}. Not done: {', '.join(not_done) if not_done else 'none'}."
    logger.info("%s", summary)
    return {"final_summary": summary}


ACTION_NODES = {
    f"act_{action_type}": make_action_node(action_type)
    for action_type in ACTION_HANDLERS
}
