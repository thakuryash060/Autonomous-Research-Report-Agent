"""
Tests for search_agent.evidence_sufficiency.

These tests are pure unit tests: no network/API calls, no Gemini/Tavily/OpenAlex
dependencies, no production code changes.
"""
import sys
import os

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

from search_agent.evidence_sufficiency import (
    evaluate_evidence_sufficiency,
    generate_targeted_queries,
    check_all_sufficiency,
)


# ---------------------------------------------------------------------------
# Minimal synthetic fixtures
# ---------------------------------------------------------------------------

QUESTION_WITH_REQS = {
    "id": "Q2",
    "type": "performance",
    "question": "What is the empirical impact of RAG on reducing hallucination rates?",
    "source_requirements": {
        "minimum_sources": 4,
        "minimum_primary_sources": 3,
        "minimum_quantitative_sources": 3,
        "minimum_counter_evidence_sources": 1,
    },
    "requires_quantitative_evidence": True,
    "requires_counter_evidence": True,
}

SELECTION_BUNDLE_INSUFFICIENT = {
    "per_question_selection": {
        "Q2": {
            "selected_sources": [
                ({"source_id": "S1", "source_type": "conference_paper", "content_status": "full"}, "top_ranked"),
                ({"source_id": "S2", "source_type": "academic", "content_status": "full"}, "top_ranked"),
            ]
        }
    }
}

FINDINGS_INSUFFICIENT = [
    {"finding_id": "Q2-F1", "stance": "support", "quantitative_evidence": []},
    {"finding_id": "Q2-F2", "stance": "support", "quantitative_evidence": []},
]

QUESTION_SUFFICIENT = {
    "id": "Q1",
    "type": "definition",
    "question": "What are hallucinations in LLMs?",
    "source_requirements": {
        "minimum_sources": 2,
        "minimum_primary_sources": 1,
        "minimum_quantitative_sources": 1,
        "minimum_counter_evidence_sources": 0,
    },
    "requires_quantitative_evidence": True,
    "requires_counter_evidence": False,
}

SELECTION_BUNDLE_SUFFICIENT = {
    "per_question_selection": {
        "Q1": {
            "selected_sources": [
                ({"source_id": "S1", "source_type": "conference_paper", "content_status": "full"}, "top_ranked"),
                ({"source_id": "S2", "source_type": "peer_reviewed_paper", "content_status": "full"}, "top_ranked"),
            ]
        }
    }
}

FINDINGS_SUFFICIENT = [
    {"finding_id": "Q1-F1", "stance": "support", "quantitative_evidence": [{"metric": "accuracy"}]},
    {"finding_id": "Q1-F2", "stance": "context", "quantitative_evidence": []},
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInsufficientQuantitativeAndCounter:
    """Test A: insufficient quantitative + counter evidence."""

    def test_insufficient_returns_false(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_WITH_REQS,
            FINDINGS_INSUFFICIENT,
            SELECTION_BUNDLE_INSUFFICIENT,
        )
        assert result["sufficient"] is False

    def test_missing_quantitative_requirement(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_WITH_REQS,
            FINDINGS_INSUFFICIENT,
            SELECTION_BUNDLE_INSUFFICIENT,
        )
        assert "quantitative_evidence" in result["missing_requirements"]

    def test_missing_counter_requirement(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_WITH_REQS,
            FINDINGS_INSUFFICIENT,
            SELECTION_BUNDLE_INSUFFICIENT,
        )
        assert "counter_evidence" in result["missing_requirements"]

    def test_evidence_gaps_populated(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_WITH_REQS,
            FINDINGS_INSUFFICIENT,
            SELECTION_BUNDLE_INSUFFICIENT,
        )
        assert len(result["evidence_gaps"]) > 0

    def test_counts_reflect_inputs(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_WITH_REQS,
            FINDINGS_INSUFFICIENT,
            SELECTION_BUNDLE_INSUFFICIENT,
        )
        assert result["finding_count"] == 2
        assert result["support_count"] == 2
        assert result["counter_count"] == 0
        assert result["quantitative_count"] == 0
        assert result["selected_source_count"] == 2
        assert result["successful_retrieval_count"] == 2


class TestSufficientEvidence:
    """Test B: sufficient evidence."""

    def test_sufficient_returns_true(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_SUFFICIENT,
            FINDINGS_SUFFICIENT,
            SELECTION_BUNDLE_SUFFICIENT,
        )
        assert result["sufficient"] is True

    def test_no_missing_requirements(self):
        result = evaluate_evidence_sufficiency(
            QUESTION_SUFFICIENT,
            FINDINGS_SUFFICIENT,
            SELECTION_BUNDLE_SUFFICIENT,
        )
        assert result["missing_requirements"] == []


class TestTargetedQuantitativeQueryGeneration:
    """Test C: targeted quantitative query generation."""

    def test_generates_at_least_one_query(self):
        queries = generate_targeted_queries(
            QUESTION_WITH_REQS,
            ["quantitative_evidence"],
        )
        assert len(queries) >= 1

    def test_query_is_targeted_toward_quantitative_evidence(self):
        queries = generate_targeted_queries(
            QUESTION_WITH_REQS,
            ["quantitative_evidence"],
        )
        query_texts = [q["query_text"].lower() for q in queries]
        assert any("quantitative" in qt or "benchmark" in qt or "empirical" in qt for qt in query_texts)

    def test_query_has_required_fields(self):
        queries = generate_targeted_queries(
            QUESTION_WITH_REQS,
            ["quantitative_evidence"],
        )
        for q in queries:
            assert "query_text" in q
            assert "query_type" in q


class TestTargetedCounterEvidenceQueryGeneration:
    """Test D: targeted counter-evidence query generation."""

    def test_generates_at_least_one_query(self):
        queries = generate_targeted_queries(
            QUESTION_WITH_REQS,
            ["counter_evidence"],
        )
        assert len(queries) >= 1

    def test_counter_query_type(self):
        queries = generate_targeted_queries(
            QUESTION_WITH_REQS,
            ["counter_evidence"],
        )
        assert all(q["query_type"] == "counter" for q in queries)

    def test_counter_query_is_targeted(self):
        queries = generate_targeted_queries(
            QUESTION_WITH_REQS,
            ["counter_evidence"],
        )
        query_texts = [q["query_text"].lower() for q in queries]
        assert any("fail" in qt or "limitation" in qt or "noise" in qt for qt in query_texts)


class TestNoRetryWhenSufficient:
    """Test E: no retry when evidence is already sufficient."""

    def test_zero_insufficient_questions(self):
        questions = [QUESTION_SUFFICIENT]
        extraction_bundle = {
            "questions": [
                {
                    "question_id": "Q1",
                    "findings": FINDINGS_SUFFICIENT,
                }
            ]
        }
        results, insufficient = check_all_sufficiency(
            questions, extraction_bundle, SELECTION_BUNDLE_SUFFICIENT
        )
        assert len(insufficient) == 0
        assert len(results) == 1
        assert results[0]["sufficient"] is True


class TestDeterministicQueryGeneration:
    """Test F: deterministic query generation."""

    def test_same_inputs_produce_identical_output(self):
        q1 = generate_targeted_queries(
            {"question": "RAG hallucination", "type": "performance"},
            ["quantitative_evidence", "counter_evidence"],
        )
        q2 = generate_targeted_queries(
            {"question": "RAG hallucination", "type": "performance"},
            ["quantitative_evidence", "counter_evidence"],
        )
        assert q1 == q2


class TestCheckAllSufficiency:
    """Integration-style tests for check_all_sufficiency."""

    def test_mixed_sufficiency(self):
        questions = [QUESTION_SUFFICIENT, QUESTION_WITH_REQS]
        extraction_bundle = {
            "questions": [
                {
                    "question_id": "Q1",
                    "findings": FINDINGS_SUFFICIENT,
                },
                {
                    "question_id": "Q2",
                    "findings": FINDINGS_INSUFFICIENT,
                },
            ]
        }
        results, insufficient = check_all_sufficiency(
            questions, extraction_bundle, {
                "per_question_selection": {
                    "Q1": SELECTION_BUNDLE_SUFFICIENT["per_question_selection"]["Q1"],
                    "Q2": SELECTION_BUNDLE_INSUFFICIENT["per_question_selection"]["Q2"],
                }
            }
        )
        assert len(results) == 2
        assert len(insufficient) == 1
        assert insufficient[0][0]["id"] == "Q2"

    def test_empty_findings_is_insufficient(self):
        question = QUESTION_WITH_REQS
        extraction_bundle = {
            "questions": [
                {
                    "question_id": "Q2",
                    "findings": [],
                }
            ]
        }
        results, insufficient = check_all_sufficiency(
            [question], extraction_bundle, SELECTION_BUNDLE_INSUFFICIENT
        )
        assert len(insufficient) == 1
        assert not results[0]["sufficient"]
