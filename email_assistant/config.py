import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load the project settings even when Python starts in another folder.
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Settings:
    """Stores all application configuration settings."""

    mailpit_host: str
    smtp_port: int
    api_port: int
    user_email: str
    user_name: str
    log_level: str
    db_path: str
    groq_api_key: str
    groq_model: str
    max_analysis_attempts: int
    body_char_limit: int
    llm_call_delay_seconds: float
    flag_calendar_path: str
    report_path: str
    calendar_path: str
    todo_path: str
    mail_actions_path: str
    drafts_path: str

    @property
    def api_base_url(self) -> str:
        """Returns the base URL for the Mailpit REST API endpoints."""
        return f"http://{self.mailpit_host}:{self.api_port}/api/v1"


def get_settings() -> Settings:
    """Reads environment variables and returns a Settings object with safe defaults."""
    def project_path(variable: str, default: str) -> str:
        """Resolves relative file paths from the project root."""
        path = Path(os.getenv(variable, default))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path)

    return Settings(
        mailpit_host=os.getenv("MAILPIT_HOST", "localhost"),
        smtp_port=int(os.getenv("MAILPIT_SMTP_PORT", "1025")),
        api_port=int(os.getenv("MAILPIT_API_PORT", "8025")),
        user_email=os.getenv("USER_EMAIL", "abhimanyu@example.com"),
        user_name=os.getenv("USER_NAME", "Abhimanyu"),
        log_level=os.getenv("LOG_LEVEL", "DEBUG"),
        db_path=project_path("DB_PATH", "data/emails.db"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        # groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        max_analysis_attempts=int(os.getenv("MAX_ANALYSIS_ATTEMPTS", "3")),
        body_char_limit=int(os.getenv("BODY_CHAR_LIMIT", "4000")),
        llm_call_delay_seconds=float(os.getenv("LLM_CALL_DELAY_SECONDS", "2")),
        flag_calendar_path=project_path("FLAG_CALENDAR_PATH", "data/flag_calendar.json"),
        report_path=project_path("REPORT_PATH", "data/report.json"),
        calendar_path=project_path("CALENDAR_PATH", "data/calendar.json"),
        todo_path=project_path("TODO_PATH", "data/todo.json"),
        mail_actions_path=project_path("MAIL_ACTIONS_PATH", "data/mail_actions.json"),
        drafts_path=project_path("DRAFTS_PATH", "data/drafts.json"),
    )
