import logging
from datetime import date

logger = logging.getLogger(__name__)


def build_report(
    run_emails: list[dict],
    flags: list[dict],
    proposed_actions: list[dict],
    errors: list[dict],
    today: date,
) -> dict:
    """Builds a JSON-friendly report containing only emails, flags, and actions."""
    del errors, today

    email_details = {
        email["message_id"]: {
            "subject": email.get("subject", ""),
            "sender": email.get("sender", ""),
            "priority": email.get("priority", ""),
            "category": email.get("category", ""),
            "summary": email.get("summary", ""),
        }
        for email in run_emails
    }

    emails = list(email_details.values())
    flagged_emails = [
        {
            "subject": flag.get("subject", ""),
            "kind": flag.get("kind", ""),
            "date": flag.get("date", ""),
            "time": flag.get("time"),
            "flag": flag.get("flag", ""),
            "priority": flag.get("priority", ""),
            "summary": flag.get("summary", ""),
        }
        for flag in flags
    ]
    actions = [
        {
            "id": action.get("id"),
            "action_type": action.get("action_type", ""),
            **email_details.get(action.get("message_id", ""), {
                "subject": action.get("subject", ""),
                "sender": "",
                "priority": "",
                "category": "",
                "summary": "",
            }),
        }
        for action in proposed_actions
    ]

    return {
        "emails": emails,
        "flagged_emails": flagged_emails,
        "proposed_actions": actions,
    }


def format_report(report: dict) -> str:
    """Formats report sections as readable Markdown in the requested order."""
    lines = ["## Emails"]
    emails = report.get("emails", [])
    if emails:
        for email in emails:
            lines.extend(
                [
                    f"- **{email.get('subject') or '(no subject)'}**",
                    f"  Sender: {email.get('sender') or '(unknown)'}",
                    f"  Priority: {email.get('priority') or '(not set)'}"
                    f" | Category: {email.get('category') or '(not set)'}",
                    f"  Summary: {email.get('summary') or '(no summary)'}",
                ]
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Flagged emails"])
    flagged_emails = report.get("flagged_emails", [])
    if flagged_emails:
        for email in flagged_emails:
            event_time = f" at {email['time']}" if email.get("time") else ""
            lines.append(
                f"- **{email.get('subject') or '(no subject)'}** - "
                f"{email.get('kind') or 'item'} on "
                f"{email.get('date') or '(no date)'}{event_time} "
                f"({email.get('flag') or 'flagged'}, "
                f"{email.get('priority') or 'priority not set'})"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Proposed actions"])
    actions = report.get("proposed_actions", [])
    if actions:
        for action in actions:
            lines.append(
                f"- [{action.get('id')}] {action.get('action_type')} - "
                f"{action.get('subject') or '(no subject)'}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)
