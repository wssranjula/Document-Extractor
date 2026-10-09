import os

from app.config import settings
from app.pipeline.tracing import configure_tracing


def test_tracing_stays_off_without_a_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setattr(settings, "langsmith_tracing", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "")
    monkeypatch.setattr("app.pipeline.tracing._configured", False)

    assert configure_tracing() is False
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_tracing_uses_the_project_name(monkeypatch):
    for name in (
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
        "LANGSMITH_ENDPOINT",
    ):
        monkeypatch.setenv(name, "")
    monkeypatch.setattr(settings, "langsmith_tracing", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "lsv2-test")
    monkeypatch.setattr(settings, "langsmith_project", "formulary-check")
    monkeypatch.setattr(settings, "langsmith_endpoint", "https://api.smith.langchain.com")
    monkeypatch.setattr("app.pipeline.tracing._configured", False)

    assert configure_tracing() is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "formulary-check"
    assert os.environ["LANGCHAIN_PROJECT"] == "formulary-check"
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2-test"
