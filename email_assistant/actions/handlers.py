"""Plain Python functions that carry out user-approved actions."""

import json
import logging
from datetime import datetime

from email_assistant.actions.drafting import generate_draft_body
from email_assistant.actions.json_files import read_json_list, write_json_list
from email_assistant.config import get_settings
from email_assistant.mail.client import find_mailpit_id, mark_read, tag_message

logger = logging.getLogger(__name__)

def add_to_calendar(email: dict) -> dict:
    """Appends one calendar entry to calendar.json.

    Skips silently if an entry with the same message_id AND title already exists
    (idempotent: safe to call twice on the same email).
    """
    settings = get_settings()
    msg_id = email["message_id"]
    title = email.get("event_title")

    entries = read_json_list(settings.calendar_path)

    # Deduplication check
    for entry in entries:
        if entry.get("message_id") == msg_id and entry.get("title") == title:
            logger.info("add_to_calendar: duplicate skipped for '%s'", title)
            return {"skipped": "duplicate"}

    entry = {
        "message_id": msg_id,
        "title": title,
        "date": email.get("event_date"),
        "time": email.get("event_time"),
        "location": email.get("event_location"),
        "added_at": datetime.now().isoformat(),
    }
    entries.append(entry)
    write_json_list(settings.calendar_path, entries)
    logger.info("add_to_calendar: added '%s' on %s", title, entry["date"])
    return {"saved": True}

def add_todo(email: dict) -> dict:
    """Appends todo items from the email's todo_items field to todo.json.

    Each task is added as a separate row; tasks that already exist
    (same message_id and text) are skipped.
    Returns {"added": N} where N is the number of new items written.
    """
    settings = get_settings()
    msg_id = email["message_id"]

    tasks = json.loads(email.get("todo_items") or "[]")
    if not isinstance(tasks, list):
        raise ValueError("todo_items must contain a JSON list")

    existing = read_json_list(settings.todo_path)
    # Build a set of (message_id, text) pairs already in the file for fast lookup
    existing_keys = {(t.get("message_id"), t.get("text")) for t in existing}

    added = 0
    for text in tasks:
        if (msg_id, text) in existing_keys:
            logger.debug("add_todo: skipping duplicate task '%s'", text)
            continue
        item = {
            "message_id": msg_id,
            "text": text,
            "due_date": email.get("due_date"),
            "due_time": email.get("due_time"),
            "priority": email.get("priority"),
            "status": "open",
            "added_at": datetime.now().isoformat(),
        }
        existing.append(item)
        existing_keys.add((msg_id, text))
        added += 1

    if added:
        write_json_list(settings.todo_path, existing)

    logger.info("add_todo: added %d task(s) for message_id=%s", added, msg_id)
    return {"added": added}

def archive(email: dict) -> dict:
    """Tags the Mailpit message as 'Archive' and marks it read.

    Raises ValueError if the message no longer exists in Mailpit.
    Records the action in mail_actions.json.
    """
    settings = get_settings()
    msg_id = email["message_id"]

    # Resolve the live Mailpit ID (the stored one can be stale after reseeding)
    mailpit_id = find_mailpit_id(msg_id)
    if mailpit_id is None:
        raise ValueError("message not found in Mailpit")

    tag_message(mailpit_id, "Archive")
    mark_read(mailpit_id)

    record = {
        "message_id": msg_id,
        "action": "archived",
        "sender": email.get("sender", ""),
        "timestamp": datetime.now().isoformat(),
    }
    items = read_json_list(settings.mail_actions_path)
    items.append(record)
    write_json_list(settings.mail_actions_path, items)

    logger.info("archive: archived message_id=%s", msg_id)
    return {"archived": True}

def mark_spam(email: dict) -> dict:
    """Tags the Mailpit message as 'Junk' and marks it read.

    Raises ValueError if the message no longer exists in Mailpit.
    Records the action in mail_actions.json.
    """
    settings = get_settings()
    msg_id = email["message_id"]

    mailpit_id = find_mailpit_id(msg_id)
    if mailpit_id is None:
        raise ValueError("message not found in Mailpit")

    tag_message(mailpit_id, "Junk")
    mark_read(mailpit_id)

    record = {
        "message_id": msg_id,
        "action": "spam",
        "sender": email.get("sender", ""),
        "timestamp": datetime.now().isoformat(),
    }
    items = read_json_list(settings.mail_actions_path)
    items.append(record)
    write_json_list(settings.mail_actions_path, items)

    logger.info("mark_spam: marked junk message_id=%s", msg_id)
    return {"marked_spam": True}

def unsubscribe(email: dict) -> dict:
    """MOCK unsubscribe — appends a record to mail_actions.json but visits no links.

    Skips if the same sender has already been unsubscribed (deduplication by sender).
    """
    settings = get_settings()
    sender = email.get("sender", "")

    items = read_json_list(settings.mail_actions_path)

    # Deduplication: skip if this sender is already recorded as unsubscribed
    for item in items:
        if item.get("action") == "unsubscribed" and item.get("sender") == sender:
            logger.info("unsubscribe: duplicate skipped for sender '%s'", sender)
            return {"skipped": "duplicate", "sender": sender}

    record = {
        "action": "unsubscribed",
        "sender": sender,
        "timestamp": datetime.now().isoformat(),
    }
    items.append(record)
    write_json_list(settings.mail_actions_path, items)

    logger.info("unsubscribe: recorded mock unsubscribe for sender '%s'", sender)
    return {"saved": True}

def pay_bill(email: dict) -> dict:
    """Not implemented — raises so the node records status 'not_implemented'."""
    logger.info("pay_bill: not implemented for '%s'", email.get("subject", ""))
    raise NotImplementedError("pay_bill is not implemented yet")


def draft_reply(email: dict) -> dict:
    """Creates a reply draft and saves it locally without sending it."""
    settings = get_settings()
    message_id = email["message_id"]
    subject = email.get("subject") or ""
    sender = email.get("sender") or ""
    drafts = read_json_list(settings.drafts_path)
    for draft in drafts:
        if draft.get("message_id") == message_id:
            logger.info("draft_reply: draft already exists for '%s', skipping", subject)
            return {"skipped": "duplicate"}

    body_text = generate_draft_body(email)
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    drafts.append(
        {
            "message_id": message_id,
            "to": sender,
            "subject": reply_subject,
            "body": body_text,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
        }
    )
    write_json_list(settings.drafts_path, drafts)
    logger.info("draft_reply: draft saved for subject='%s'", reply_subject)
    return {"saved": True}


ACTION_HANDLERS: dict = {
    "add_to_calendar": add_to_calendar,
    "add_todo": add_todo,
    "archive": archive,
    "mark_spam": mark_spam,
    "unsubscribe": unsubscribe,
    "pay_bill": pay_bill,
    "draft_reply": draft_reply,
}
