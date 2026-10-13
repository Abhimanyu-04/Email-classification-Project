import json
import logging
from datetime import datetime
from database import get_connection

logger = logging.getLogger(__name__)


def email_exists(message_id: str) -> bool:
    """Checks whether an email with the given message_id already exists in the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM emails WHERE message_id = ? LIMIT 1", (message_id,))
        row = cursor.fetchone()
        return row is not None
    finally:
        conn.close()


def save_email(email: dict) -> None:
    """Inserts a new email row into the emails table with default pending status."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        fetched_at = datetime.now().isoformat()
        recipients_json = json.dumps(email.get("to", []))
        cursor.execute(
            """
            INSERT OR IGNORE INTO emails (
                message_id, mailpit_id, sender, recipients, subject, body, received_at, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.get("message_id", ""),
                email.get("mailpit_id", ""),
                email.get("sender", ""),
                recipients_json,
                email.get("subject", ""),
                email.get("body", ""),
                email.get("received_at", ""),
                fetched_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    logger.debug("Saved email: %s", email.get("subject", ""))


def get_emails_to_analyze(max_attempts: int) -> list[dict]:
    """Retrieves pending or retryable failed emails ordered oldest first."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM emails
            WHERE analysis_status = 'pending'
               OR (analysis_status = 'failed' AND analysis_attempts < ?)
            ORDER BY fetched_at ASC
            """,
            (max_attempts,),
        )
        rows = cursor.fetchall()
        emails = [dict(row) for row in rows]
    finally:
        conn.close()

    logger.debug("Retrieved %d emails to analyze.", len(emails))
    return emails


def save_analysis(
    message_id: str,
    analysis: dict,
    model_name: str,
    email: dict | None = None,
) -> None:
    """Updates an email row with structured analysis results and optionally refreshes raw email fields."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        analyzed_at = datetime.now().isoformat()
        proposed_actions_json = json.dumps(analysis.get("proposed_actions", []))
        todo_items_json = json.dumps(analysis.get("todo_items", []))

        # Handle date values whether passed as string or date object
        due_date_val = analysis.get("due_date")
        event_date_val = analysis.get("event_date")

        if email is not None:
            recipients_val = email.get("to") or email.get("recipients")
            if isinstance(recipients_val, list):
                recipients_json = json.dumps(recipients_val)
            elif isinstance(recipients_val, str):
                recipients_json = recipients_val
            else:
                recipients_json = "[]"

            cursor.execute(
                """
                UPDATE emails
                SET analysis_status = 'analyzed',
                    analyzed_at = ?,
                    model_name = ?,
                    analysis_error = NULL,
                    category = ?,
                    work_type = ?,
                    priority = ?,
                    summary = ?,
                    proposed_actions = ?,
                    due_date = ?,
                    due_time = ?,
                    event_title = ?,
                    event_date = ?,
                    event_time = ?,
                    event_location = ?,
                    todo_items = ?,
                    date_phrase = ?,
                    confidence = ?,
                    sender = COALESCE(?, sender),
                    recipients = COALESCE(?, recipients),
                    subject = COALESCE(?, subject),
                    body = COALESCE(?, body),
                    received_at = COALESCE(?, received_at)
                WHERE message_id = ?
                """,
                (
                    analyzed_at,
                    model_name,
                    analysis.get("category"),
                    analysis.get("work_type"),
                    analysis.get("priority"),
                    analysis.get("summary"),
                    proposed_actions_json,
                    str(due_date_val) if due_date_val is not None else None,
                    analysis.get("due_time"),
                    analysis.get("event_title"),
                    str(event_date_val) if event_date_val is not None else None,
                    analysis.get("event_time"),
                    analysis.get("event_location"),
                    todo_items_json,
                    analysis.get("date_phrase"),
                    analysis.get("confidence"),
                    email.get("sender"),
                    recipients_json,
                    email.get("subject"),
                    email.get("body"),
                    email.get("received_at"),
                    message_id,
                ),
            )
        else:
            cursor.execute(
                """
                UPDATE emails
                SET analysis_status = 'analyzed',
                    analyzed_at = ?,
                    model_name = ?,
                    analysis_error = NULL,
                    category = ?,
                    work_type = ?,
                    priority = ?,
                    summary = ?,
                    proposed_actions = ?,
                    due_date = ?,
                    due_time = ?,
                    event_title = ?,
                    event_date = ?,
                    event_time = ?,
                    event_location = ?,
                    todo_items = ?,
                    date_phrase = ?,
                    confidence = ?
                WHERE message_id = ?
                """,
                (
                    analyzed_at,
                    model_name,
                    analysis.get("category"),
                    analysis.get("work_type"),
                    analysis.get("priority"),
                    analysis.get("summary"),
                    proposed_actions_json,
                    str(due_date_val) if due_date_val is not None else None,
                    analysis.get("due_time"),
                    analysis.get("event_title"),
                    str(event_date_val) if event_date_val is not None else None,
                    analysis.get("event_time"),
                    analysis.get("event_location"),
                    todo_items_json,
                    analysis.get("date_phrase"),
                    analysis.get("confidence"),
                    message_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    logger.debug("Saved analysis for message_id: %s", message_id)


def mark_analysis_failed(message_id: str, error: str) -> None:
    """Marks an email analysis as failed, recording the error and incrementing attempt count."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE emails
            SET analysis_status = 'failed',
                analysis_error = ?,
                analysis_attempts = analysis_attempts + 1
            WHERE message_id = ?
            """,
            (error, message_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.debug("Marked analysis failed for message_id: %s with error: %s", message_id, error)


def get_emails_by_ids(message_ids: list[str]) -> list[dict]:
    """Retrieves full email rows for the specified message IDs, returning empty list if empty."""
    if not message_ids:
        return []

    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in message_ids)
        cursor.execute(
            f"SELECT * FROM emails WHERE message_id IN ({placeholders})",
            message_ids,
        )
        rows = cursor.fetchall()
        emails = [dict(row) for row in rows]
    finally:
        conn.close()

    logger.debug("Retrieved %d emails for %d requested IDs.", len(emails), len(message_ids))
    return emails


def get_all_analyzed_emails() -> list[dict]:
    """Retrieves all email rows with analysis_status = 'analyzed'."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM emails
            WHERE analysis_status = 'analyzed'
            ORDER BY fetched_at ASC
            """
        )
        rows = cursor.fetchall()
        emails = [dict(row) for row in rows]
    finally:
        conn.close()

    logger.debug("Retrieved %d analyzed emails.", len(emails))
    return emails
