import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Medication, Reference
from app.retrieval import passages_for_medication

GOLDEN_PATH = Path(__file__).with_name("retrieval_golden.json")


def score(cases: list[dict]) -> dict[str, float]:
    positive = [case for case in cases if case["relevant_sections"]]
    negative = [case for case in cases if not case["relevant_sections"]]
    retrieved_total = sum(len(case["retrieved_sections"]) for case in cases)
    relevant_retrieved = sum(
        len(set(case["retrieved_sections"]) & set(case["relevant_sections"]))
        for case in positive
    )
    relevant_total = sum(len(case["relevant_sections"]) for case in positive)
    top_one_hits = sum(
        bool(case["retrieved_sections"] and case["retrieved_sections"][0] in case["relevant_sections"])
        for case in positive
    )
    reciprocal_ranks = []
    for case in positive:
        relevant = set(case["relevant_sections"])
        rank = next(
            (index for index, section in enumerate(case["retrieved_sections"], start=1) if section in relevant),
            None,
        )
        reciprocal_ranks.append(1 / rank if rank else 0)
    rejected = sum(not case["retrieved_sections"] for case in negative)
    return {
        "precision": relevant_retrieved / retrieved_total if retrieved_total else 0,
        "recall": relevant_retrieved / relevant_total if relevant_total else 0,
        "precision_at_1": top_one_hits / len(positive) if positive else 0,
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0,
        "unsupported_rejection_rate": rejected / len(negative) if negative else 0,
    }


def evaluate() -> tuple[list[dict], dict[str, float]]:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        reference = session.scalar(
            select(Reference)
            .where(Reference.indexed_at.is_not(None))
            .order_by(Reference.name)
            .limit(1)
        )
        if reference is None:
            raise RuntimeError("No indexed reference found. Run a document job before this evaluation.")
        cases = []
        for item in golden:
            medication = Medication(job_id="evaluation", drug_name=item["query"])
            passages = passages_for_medication(session, reference.id, medication)
            cases.append(
                {
                    **item,
                    "retrieved_sections": [passage.section for passage in passages],
                }
            )
    return cases, score(cases)


def main() -> None:
    cases, metrics = evaluate()
    for case in cases:
        expected = ", ".join(case["relevant_sections"]) or "<none>"
        retrieved = ", ".join(case["retrieved_sections"]) or "<none>"
        print(f"{case['query']}: expected [{expected}] retrieved [{retrieved}]")
    print()
    for name, value in metrics.items():
        print(f"{name}: {value:.3f}")


if __name__ == "__main__":
    main()
