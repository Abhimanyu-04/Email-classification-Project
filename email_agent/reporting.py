from datetime import date, timedelta


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


def build_report(
    run_emails: list[dict],
    flags: list[dict],
    proposed_actions: list[dict],
    errors: list[dict],
    today: date,
) -> str:
    """Builds a formatted markdown report summarizing analyzed emails, flags, and actions."""
    lines = []

    # 1. Header
    lines.append(f"# Email Report ({today.isoformat()})")
    lines.append(f"Analyzed: {len(run_emails)} | Failed: {len(errors)}")
    lines.append("")

    # 2. Flagged
    lines.append("## Flagged")
    today_flags = [f for f in flags if f.get("flag") == "today"]
    week_flags = [f for f in flags if f.get("flag") == "this_week"]

    if not today_flags and not week_flags:
        lines.append("Nothing flagged")
    else:
        lines.append("### Today")
        if today_flags:
            for item in today_flags:
                dt_str = f"{item['date']} {item['time']}" if item.get("time") else item["date"]
                lines.append(f"- [{item['kind']}] {item['subject']} ({dt_str}) - {item['priority']}")
        else:
            lines.append("Nothing flagged")

        lines.append("")
        lines.append("### This week")
        if week_flags:
            for item in week_flags:
                dt_str = f"{item['date']} {item['time']}" if item.get("time") else item["date"]
                lines.append(f"- [{item['kind']}] {item['subject']} ({dt_str}) - {item['priority']}")
        else:
            lines.append("Nothing flagged")
    lines.append("")

    # 3. Needs attention (by type)
    lines.append("## Needs attention (by type)")
    counts = {}
    for email in run_emails:
        wt = email.get("work_type")
        if wt:
            counts[wt] = counts.get(wt, 0) + 1
    if counts:
        counts_str = ", ".join(f"{k}: {v}" for k, v in counts.items())
    else:
        counts_str = "None"
    lines.append(counts_str)
    lines.append("")

    # 4. Emails table
    lines.append("## Emails")
    lines.append("| Priority | Category | Subject | Summary |")
    lines.append("| --- | --- | --- | --- |")

    priority_map = {"high": 1, "medium": 2, "low": 3}
    sorted_emails = sorted(
        run_emails,
        key=lambda e: priority_map.get(str(e.get("priority", "")).lower(), 4),
    )

    for email in sorted_emails:
        prio = email.get("priority", "")
        cat = email.get("category", "")
        conf = email.get("confidence")
        try:
            if conf is not None and float(conf) < 0.6:
                cat = f"{cat} (?)"
        except Exception:
            pass

        subj = str(email.get("subject", "")).replace("|", "/")
        summ = str(email.get("summary", "")).replace("|", "/")
        lines.append(f"| {prio} | {cat} | {subj} | {summ} |")
    lines.append("")

    # 5. Proposed actions
    lines.append("## Proposed actions")
    if proposed_actions:
        for action in proposed_actions:
            lines.append(f"[{action.get('id')}] {action.get('action_type')} - {action.get('subject')}")
    else:
        lines.append("No actions proposed")
    lines.append("")

    # 6. Failures (only included if errors exist)
    if errors:
        lines.append("## Failures")
        for err in errors:
            subj = err.get("subject", "Unknown")
            err_msg = err.get("error", "")
            lines.append(f"{subj} - {err_msg}")
        lines.append("")

    return "\n".join(lines).strip()
