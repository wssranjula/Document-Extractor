from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk
from app.pipeline.verify import Passage

TOP_K = 4
MAX_COSINE_DISTANCE = 0.55


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
    return OpenAI(api_key=settings.openai_api_key)


def complete(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
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
    response = _client().embeddings.create(model=settings.openai_embedding_model, input=texts)
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


def search_passages(session: Session, reference_id: str, vector: list[float]) -> list[Passage]:
    distance = Chunk.embedding.cosine_distance(vector)
    rows = session.execute(
        select(Chunk, distance.label("distance"))
        .where(Chunk.reference_id == reference_id, Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(TOP_K)
    ).all()
    passages = []
    for chunk, score in rows:
        if score is None or score > MAX_COSINE_DISTANCE:
            continue
        passages.append(Passage(section=chunk.section, page=chunk.page, content=chunk.content))
    return passages
