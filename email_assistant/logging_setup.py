import logging

import logfire

from email_assistant.config import get_settings

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configures application logging using Python standard library logging and Logfire."""
    settings = get_settings()

    # Logfire is an observability tool that captures traces and logs.
    # Setting send_to_logfire='if-token-present' means it works locally without error
    # even if no Logfire API token is set.
    logfire.configure(send_to_logfire="if-token-present")


    # Set up root logging handler so standard logging calls flow into Logfire
    log_level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    logging.basicConfig(
        level=log_level,
        handlers=[
            logfire.LogfireLoggingHandler(),  # Ships every logger.info/debug call to Logfire
            logging.StreamHandler(),          # Prints cleanly to your terminal/stdout
        ],
        force=True,
    )

    cli_logger = logging.getLogger("cli")
    cli_logger.setLevel(logging.INFO)
    if not cli_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        cli_logger.addHandler(console_handler)

    logger.info("Logging is initialised.")
