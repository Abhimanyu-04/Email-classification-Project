import logging

import requests

from email_assistant.config import get_settings

logger = logging.getLogger(__name__)


def list_messages() -> list[dict]:
    """Fetches message list from Mailpit and returns dicts with mailpit_id and message_id."""
    settings = get_settings()
    url = f"{settings.api_base_url}/messages"

    logger.debug("Requesting message list from %s", url)
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to fetch message list from %s", url)
        raise

    data = response.json()
    messages = data.get("messages", [])
    result = []
    for msg in messages:
        mailpit_id = msg.get("ID") or msg.get("id") or ""
        message_id = msg.get("MessageID") or ""
        result.append({
            "mailpit_id": mailpit_id,
            "message_id": message_id,
        })
    return result


def get_message(mailpit_id: str) -> dict:
    """Fetches details for a single message from Mailpit by its Mailpit ID."""
    settings = get_settings()
    url = f"{settings.api_base_url}/message/{mailpit_id}"

    logger.debug("Requesting message details from %s", url)
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to fetch message details for ID %s", mailpit_id)
        raise

    data = response.json()

    # Extract sender address
    from_field = data.get("From")
    if isinstance(from_field, dict):
        sender = from_field.get("Address", "")
    elif isinstance(from_field, str):
        sender = from_field
    else:
        sender = ""

    # Extract recipient addresses
    to_field = data.get("To") or []
    to_list = []
    for recipient in to_field:
        if isinstance(recipient, dict):
            addr = recipient.get("Address")
            if addr:
                to_list.append(addr)
        elif isinstance(recipient, str):
            to_list.append(recipient)

    return {
        "message_id": data.get("MessageID", ""),
        "mailpit_id": mailpit_id,
        "sender": sender,
        "to": to_list,
        "subject": data.get("Subject", ""),
        "body": data.get("Text", ""),
        "received_at": str(data.get("Date", "")),
    }


def find_mailpit_id(message_id: str) -> str | None:
    """Returns the CURRENT Mailpit internal ID for the given RFC message_id.

    Stored mailpit_ids can go stale after reseeding, so we always resolve
    fresh from the live message list instead of relying on the database value.
    Returns None if the message is not found in Mailpit.
    """
    messages = list_messages()
    for msg in messages:
        if msg.get("message_id") == message_id:
            return msg.get("mailpit_id") or None
    return None


def tag_message(mailpit_id: str, tag: str) -> None:
    """Applies a tag to a single Mailpit message.

    Uses PUT /api/v1/tags which OVERWRITES existing tags; we pass a single
    tag so the message ends up with exactly that label.
    Payload format confirmed from the Mailpit API v1 documentation:
      {"IDs": [<id>], "Tags": [<tag>]}
    """
    settings = get_settings()
    url = f"{settings.api_base_url}/tags"

    logger.debug("Tagging mailpit_id=%s with tag='%s'", mailpit_id, tag)
    try:
        response = requests.put(url, json={"IDs": [mailpit_id], "Tags": [tag]})
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to tag mailpit_id=%s with tag='%s'", mailpit_id, tag)
        raise


def mark_read(mailpit_id: str) -> None:
    """Marks a single Mailpit message as read.

    Uses PUT /api/v1/messages with {"IDs": [<id>], "Read": true}.
    Payload format confirmed from the Mailpit API v1 documentation.
    """
    settings = get_settings()
    url = f"{settings.api_base_url}/messages"

    logger.debug("Marking mailpit_id=%s as read", mailpit_id)
    try:
        response = requests.put(url, json={"IDs": [mailpit_id], "Read": True})
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to mark mailpit_id=%s as read", mailpit_id)
        raise
