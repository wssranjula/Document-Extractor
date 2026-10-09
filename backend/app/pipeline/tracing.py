import logging
import os

from app.config import settings

logger = logging.getLogger("app.pipeline")

_configured = False


def configure_tracing() -> bool:
    """Turn LangSmith on only when a key is present.

    LangGraph and the OpenAI wrapper both read these environment variables.
    An empty key disables tracing so a missing account does not fail the job.
    """
    global _configured
    enabled = bool(settings.langsmith_tracing and settings.langsmith_api_key)
    if enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        if not _configured:
            logger.info("LangSmith tracing enabled for project %s", settings.langsmith_project)
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        if settings.langsmith_tracing and not settings.langsmith_api_key and not _configured:
            logger.info("LangSmith tracing was requested, but LANGSMITH_API_KEY is empty")
    _configured = True
    return enabled
