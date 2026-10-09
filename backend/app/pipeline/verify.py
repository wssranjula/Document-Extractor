from dataclasses import dataclass


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
