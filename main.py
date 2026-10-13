import logging
from database import init_db
from email_agent.email_fetcher import fetch_new_emails
from logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Sets up logging, initializes the database, and fetches newly arrived emails."""
    setup_logging()
    init_db()
    new_emails = fetch_new_emails()
    logger.info("New emails returned: %d", len(new_emails))


if __name__ == "__main__":
    main()
