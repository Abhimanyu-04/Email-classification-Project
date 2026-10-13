import logging
import logfire
from config import get_settings

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

    logger.info("Logging is initialised.")
