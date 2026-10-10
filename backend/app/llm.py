"""Chat and embedding calls.

The classes below are the answers we ask the model to fill in: a summary,
critical points, medications, or a verdict. Looking up formulary text
happens in retrieval.py.
"""

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.workflow.tracing import configure_tracing


class SummaryResult(BaseModel):
    summary: str


class CriticalPointResult(BaseModel):
    text: str
    source_page: int | None = None
    source_quote: str


class CriticalPointsResult(BaseModel):
    points: list[CriticalPointResult]


class MedicationResult(BaseModel):
    drug_name: str
    dose: str | None = None
    unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    indication: str | None = None
    source_page: int | None = None


class MedicationsResult(BaseModel):
    medications: list[MedicationResult]


class VerdictResult(BaseModel):
    status: str = Field(description="supported, contradicted, or unsupported")
    explanation: str
    citation_quote: str | None = None
    citation_section: str | None = None
    citation_page: int | None = None


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=settings.openai_api_key)
    if not configure_tracing():
        return client
    from langsmith.wrappers import wrap_openai

    return wrap_openai(client)


def structured_completion(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """Ask the chat model for one object matching `schema`."""
    from langsmith import trace

    with trace(name=schema.__name__, run_type="chain"):
        response = _client().beta.chat.completions.parse(
            model=settings.openai_chat_model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema,
        )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("The model returned no structured result")
    return parsed


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    from langsmith import trace

    with trace(name="embed_texts", run_type="embedding", inputs={"count": len(texts)}):
        response = _client().embeddings.create(model=settings.openai_embedding_model, input=texts)
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]
