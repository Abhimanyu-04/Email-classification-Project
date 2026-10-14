import json
import logging
from datetime import datetime

from email_assistant.database import get_connection

logger = logging.getLogger(__name__)


def plan_actions_for_emails(message_ids: list[str]) -> int:
    """Inserts proposed action rows for analyzed emails, returning count of newly created rows."""
    if not message_ids:
        return 0

    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in message_ids)
        cursor.execute(
            f"""
            SELECT message_id, proposed_actions
            FROM emails
            WHERE message_id IN ({placeholders})
              AND analysis_status = 'analyzed'
            """,
            message_ids,
        )
        rows = cursor.fetchall()

        now_iso = datetime.now().isoformat()
        created_count = 0

        for row in rows:
            msg_id = row["message_id"]
            raw_actions = row["proposed_actions"]
            if not raw_actions:
                continue

            try:
                actions_list = json.loads(raw_actions)
            except Exception:
                actions_list = []

            for action_type in actions_list:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO actions (
                        message_id, action_type, status, created_at, updated_at
                    ) VALUES (?, ?, 'proposed', ?, ?)
                    """,
                    (msg_id, action_type, now_iso, now_iso),
                )
                if cursor.rowcount > 0:
                    created_count += 1

        conn.commit()
    finally:
        conn.close()

    logger.debug("Planned %d new actions for %d emails.", created_count, len(message_ids))
    return created_count


def get_actions_by_status(status: str) -> list[dict]:
    """Retrieves actions with the specified status joined with the corresponding email subject."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT actions.*, emails.subject
            FROM actions
            JOIN emails ON actions.message_id = emails.message_id
            WHERE actions.status = ?
            ORDER BY actions.id ASC
            """,
            (status,),
        )
        rows = cursor.fetchall()
        actions = [dict(row) for row in rows]
    finally:
        conn.close()

    logger.debug("Retrieved %d actions with status '%s'.", len(actions), status)
    return actions


def set_action_statuses(approved_ids: list[int]) -> None:
    """Approves or rejects all proposed actions in one transaction.

    Every row whose id is in approved_ids gets status 'approved';
    every other 'proposed' row becomes 'rejected'.
    This is called AFTER interrupt() resumes, so no side-effects happen before
    the user has answered.
    """
    conn = get_connection()
    try:
        now_iso = datetime.now().isoformat()
        cursor = conn.cursor()
        # If there are approved ids, mark them approved
        if approved_ids:
            placeholders = ",".join("?" for _ in approved_ids)
            cursor.execute(
                f"""
                UPDATE actions
                SET status = 'approved', updated_at = ?
                WHERE id IN ({placeholders}) AND status = 'proposed'
                """,
                [now_iso, *approved_ids],
            )
        # Reject everything else that is still 'proposed'
        cursor.execute(
            """
            UPDATE actions
            SET status = 'rejected', updated_at = ?
            WHERE status = 'proposed'
            """,
            (now_iso,),
        )
        conn.commit()
    finally:
        conn.close()

    logger.debug("set_action_statuses: approved=%d ids.", len(approved_ids))


def get_approved_actions(action_type: str) -> list[dict]:
    """Returns all approved actions of the given type, joined with the email subject."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT actions.*, emails.subject
            FROM actions
            JOIN emails ON actions.message_id = emails.message_id
            WHERE actions.status = 'approved' AND actions.action_type = ?
            ORDER BY actions.id ASC
            """,
            (action_type,),
        )
        rows = cursor.fetchall()
        actions = [dict(row) for row in rows]
    finally:
        conn.close()

    logger.debug("Retrieved %d approved actions of type '%s'.", len(actions), action_type)
    return actions


def update_action_result(action_id: int, status: str, result: dict | None) -> None:
    """Records the execution outcome (executed / failed / not_implemented) for one action row."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        result_json = json.dumps(result) if result is not None else None
        now_iso = datetime.now().isoformat()
        cursor.execute(
            """
            UPDATE actions
            SET status = ?, result = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, result_json, now_iso, action_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.debug("Updated action id=%d to status='%s'.", action_id, status)


def get_actions_by_ids(ids: list[int]) -> list[dict]:
    """Returns action rows for the given primary-key ids, joined with email subject."""
    if not ids:
        return []

    conn = get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(
            f"""
            SELECT actions.*, emails.subject
            FROM actions
            JOIN emails ON actions.message_id = emails.message_id
            WHERE actions.id IN ({placeholders})
            ORDER BY actions.id ASC
            """,
            ids,
        )
        rows = cursor.fetchall()
        actions = [dict(row) for row in rows]
    finally:
        conn.close()

    logger.debug("Retrieved %d actions by ids.", len(actions))
    return actions
