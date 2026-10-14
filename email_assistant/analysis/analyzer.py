import logging
import time
from datetime import date

import groq
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import ValidationError

from email_assistant.analysis.models import EmailAnalysis
from email_assistant.analysis.prompts import SYSTEM_PROMPT, build_user_message, parse_received_date
from email_assistant.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Groq chat model and bind structured output
llm = ChatGroq(
    model=settings.groq_model,
    temperature=0,
    groq_api_key=settings.groq_api_key or None,
)
structured_llm = llm.with_structured_output(EmailAnalysis)
logger.info("ChatGroq initialized with model: %s", settings.groq_model)


def invoke_analysis(messages: list, attempt: int) -> EmailAnalysis:
    """Invokes structured analysis and logs its duration and token usage."""
    usage_callback = UsageMetadataCallbackHandler()
    started_at = time.perf_counter()
    try:
        analysis = structured_llm.invoke(
            messages,
            config={"callbacks": [usage_callback]},
        )
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "LLM analysis failed: model=%s attempt=%d elapsed_ms=%.1f",
            settings.groq_model,
            attempt,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    usage = next(iter(usage_callback.usage_metadata.values()), {})
    logger.info(
        "LLM analysis completed: model=%s attempt=%d elapsed_ms=%.1f "
        "input_tokens=%s output_tokens=%s total_tokens=%s",
        settings.groq_model,
        attempt,
        elapsed_ms,
        usage.get("input_tokens", "unavailable"),
        usage.get("output_tokens", "unavailable"),
        usage.get("total_tokens", "unavailable"),
    )
    return analysis


def check_dates(analysis: EmailAnalysis, received_date: date) -> None:
    """Logs a warning if extracted due or event dates fall outside a realistic window."""
    for field_name, d_val in [("due_date", analysis.due_date), ("event_date", analysis.event_date)]:
        if d_val is not None:
            delta = (d_val - received_date).days
            if delta < -1 or delta > 730:
                logger.warning(
                    "Extracted %s '%s' is %d days relative to received date %s",
                    field_name,
                    d_val,
                    delta,
                    received_date,
                )


def analyze_email(email: dict) -> EmailAnalysis:
    """Analyzes a single email dictionary, allowing one retry on validation errors."""
    user_msg_text = build_user_message(email)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_msg_text),
    ]

    try:
        analysis = invoke_analysis(messages, attempt=1)
    except (ValidationError, OutputParserException, groq.BadRequestError) as err:
        logger.warning("Initial LLM response failed validation (%s). Retrying with error feedback...", type(err).__name__)
        retry_messages = list(messages) + [
            HumanMessage(content=f"Your previous answer was invalid: {err}. Return a corrected answer.")
        ]
        analysis = invoke_analysis(retry_messages, attempt=2)

    received_date = parse_received_date(email)
    check_dates(analysis, received_date)
    logger.debug("Analysis result: %s", analysis.model_dump_json())
    return analysis
