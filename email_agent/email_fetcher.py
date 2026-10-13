import logging
from email_agent.email_store import email_exists, save_email
from email_agent.mail_client import get_message, list_messages

logger = logging.getLogger(__name__)


def fetch_new_emails() -> list[dict]:
    """Coordinates fetching from Mailpit, filtering out duplicates, and saving new emails."""
    messages = list_messages()
    total_count = len(messages)
    already_stored_count = 0
    new_emails = []

    for msg_info in messages:
        message_id = msg_info.get("message_id", "")
        if email_exists(message_id):
            already_stored_count += 1
            continue

        email = get_message(msg_info["mailpit_id"])
        save_email(email)
        new_emails.append(email)

    new_count = len(new_emails)
    logger.info(
        "Mailpit total: %d, already stored: %d, new: %d",
        total_count,
        already_stored_count,
        new_count,
    )

    for email in new_emails:
        logger.debug(
            "New email stored: message_id=%s, sender=%s, subject=%s",
            email.get("message_id", ""),
            email.get("sender", ""),
            email.get("subject", ""),
        )

    return new_emails
