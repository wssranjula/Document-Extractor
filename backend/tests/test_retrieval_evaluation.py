import pytest

from evaluation.evaluate_retrieval import score


def test_retrieval_metrics_include_false_positives_and_unsupported_queries():
    cases = [
        {
            "relevant_sections": ["Velantine"],
            "retrieved_sections": ["Velantine"],
        },
        {
            "relevant_sections": ["Quintaxin"],
            "retrieved_sections": ["Floranase", "Quintaxin"],
        },
        {
            "relevant_sections": [],
            "retrieved_sections": ["Mirosartan"],
        },
        {
            "relevant_sections": [],
            "retrieved_sections": [],
        },
    ]

    metrics = score(cases)

    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == 1
    assert metrics["precision_at_1"] == 0.5
    assert metrics["mrr"] == 0.75
    assert metrics["unsupported_rejection_rate"] == 0.5
