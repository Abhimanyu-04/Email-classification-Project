import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

def compute_flags(emails: list[dict], today: date) -> list[dict]:
    """Computes upcoming deadline and event flags (today or this_week) for non-junk emails."""
    # Week is defined as Monday through Sunday containing today
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    flags = []

    for email in emails:
        if email.get("category") == "junk":
            continue

        date_pairs = [
            (email.get("due_date"), email.get("due_time"), "deadline"),
            (email.get("event_date"), email.get("event_time"), "event"),
        ]

        for d_val, t_val, kind in date_pairs:
            if not d_val:
                continue

            try:
                if isinstance(d_val, date):
                    parsed_d = d_val
                else:
                    parsed_d = date.fromisoformat(str(d_val).strip())
            except Exception:
                continue

            flag = None
            if parsed_d == today:
                flag = "today"
            elif today < parsed_d <= end_of_week:
                flag = "this_week"

            if flag:
                flags.append(
                    {
                        "message_id": email.get("message_id", ""),
                        "subject": email.get("subject", ""),
                        "kind": kind,
                        "date": parsed_d.isoformat(),
                        "time": t_val if t_val else None,
                        "flag": flag,
                        "priority": email.get("priority", ""),
                        "summary": email.get("summary", ""),
                    }
                )

    # Sort flags chronologically by date and then time
    flags.sort(key=lambda x: (x["date"], x["time"] or ""))
    return flags
