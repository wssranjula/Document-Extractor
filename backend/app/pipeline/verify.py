from dataclasses import dataclass
import re


@dataclass
class Passage:
    section: str
    page: int | None
    content: str


@dataclass
class FlagDecision:
    status: str
    explanation: str
    citation_quote: str | None = None
    citation_section: str | None = None
    citation_page: int | None = None


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def quote_is_grounded(quote: str | None, passages: list[Passage]) -> bool:
    if not quote or not quote.strip():
        return False
    needle = _normalize(quote)
    return any(needle in _normalize(passage.content) for passage in passages)


def remove_unsupported_duration_conflict(
    prescription_duration: str | None,
    passages: list[Passage],
    verdict: FlagDecision,
) -> FlagDecision:
    """Do not treat an open-ended prescription as a conflict without a duration rule.

    A model may interpret the absence of a maximum duration as a prohibition.
    Absence is not contradictory evidence. Other grounded conflicts, such as a
    wrong dose, are preserved.
    """
    duration = _normalize(prescription_duration or "")
    if verdict.status != "contradicted" or not any(term in duration for term in ("indefinite", "ongoing", "continue")):
        return verdict
    reference = _normalize(" ".join(passage.content for passage in passages))
    if _has_duration_rule(reference):
        return verdict
    sentences = re.split(r"(?<=[.!?])\s+", verdict.explanation.strip())
    kept = [sentence for sentence in sentences if not _claims_duration_conflict(sentence)]
    if any(_describes_conflict(sentence) for sentence in kept):
        verdict.explanation = " ".join(kept)
        return verdict
    return FlagDecision(
        status="supported",
        explanation=(
            "The stated dose, route, and frequency match the formulary. "
            "The formulary does not state a maximum treatment duration."
        ),
        citation_quote=verdict.citation_quote,
        citation_section=verdict.citation_section,
        citation_page=verdict.citation_page,
    )


def _has_duration_rule(reference: str) -> bool:
    return any(
        phrase in reference
        for phrase in (
            "treatment duration",
            "short-term use",
            "long-term use",
            "duration beyond",
            "reassessment of continued indication",
            "reassessed for continued need",
            "continuation beyond",
        )
    )


def _claims_duration_conflict(sentence: str) -> bool:
    text = _normalize(sentence)
    duration_terms = ("duration", "indefinite", "longer than", "ongoing")
    conflict_terms = ("conflict", "contradict", "not support", "not specify", "longer", "exceed")
    return any(term in text for term in duration_terms) and any(term in text for term in conflict_terms)


def _describes_conflict(sentence: str) -> bool:
    text = _normalize(sentence)
    return any(
        term in text
        for term in ("above", "exceeds", "wrong", "conflict", "contradict", "instead of", "does not match")
    )


def verify_one(passages: list[Passage], verdict: FlagDecision | None) -> FlagDecision:
    """Turn retrieved passages and a model verdict into a stored flag.

    An empty retrieval, or a verdict whose quote is not in those passages,
    is unsupported. The citation is kept only when the quote is present.
    """
    if not passages:
        return FlagDecision(
            status="unsupported",
            explanation="No relevant formulary passage was retrieved.",
        )
    if verdict is None or verdict.status not in {"supported", "contradicted", "unsupported"}:
        return FlagDecision(
            status="unsupported",
            explanation="The model did not return a usable verdict.",
        )
    if verdict.status == "unsupported":
        return FlagDecision(
            status="unsupported",
            explanation=verdict.explanation or "The reference does not contain this medication.",
        )
    if not quote_is_grounded(verdict.citation_quote, passages):
        return FlagDecision(
            status="unsupported",
            explanation="No grounded formulary passage was available for this verdict.",
        )
    return verdict
