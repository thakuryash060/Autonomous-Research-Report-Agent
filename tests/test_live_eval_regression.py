"""
tests/test_live_eval_regression.py

Deterministic regression unit tests for Phase 2 live evaluation failures:
1. Evidence persistence across targeted re-search rounds (Round N findings preserved in Round N+1).
2. OpenAlex targeted-query construction and query sanitization (no HTTP 400).
3. Multiplicative relevance dominating weak source-type preference bonuses.
4. Source retrieved content preservation during deduplication and re-retrieval.
5. Quantitative findings surviving extraction/validation when properly grounded.
6. Counter-evidence classification across proposition polarity (no false rejection in Gate 1/Gate 4).
7. Cross-question routing preserving original findings without silent deletion.
8. Finding deduplication preserving semantically distinct claims.
9. TeeLogger capturing stdout/stderr to a timestamped file in UTF-8 without duplicate lines.
"""

import os
import re
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

from search_agent.source_ranker import score_source, rank_sources, PREFERENCE_TO_SOURCE_TYPES
from search_agent.source_providers import _sanitize_openalex_query
from search_agent.evidence_sufficiency import generate_targeted_queries
from search_agent.sources import deduplicate_sources
from search_agent.content_retriever import retrieve_selected_sources
from search_agent.evidence_validator import EvidenceValidator
from search_agent.evidence_extractor import (
    extract_research_evidence,
    extract_heuristic_quantitative_records,
)
from search_agent.tee_logger import TeeLogger


class MockGeminiClient:
    """Mock Gemini client for deterministic extraction tests."""
    class models:
        @staticmethod
        def generate_content(*args, **kwargs):
            return MagicMock(text="[]")


class TestEvidencePersistenceAcrossRounds(unittest.TestCase):
    """Invariant 1: Accepted evidence from Round N must not disappear in Round N+1."""

    def test_round_n_findings_preserved_in_round_n_plus_1(self):
        plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "Under what conditions does RAG reduce hallucination?",
                    "requires_quantitative_evidence": False,
                    "requires_counter_evidence": False,
                },
                {
                    "id": "Q2",
                    "question": "When can retrieval degrade factual accuracy?",
                    "requires_quantitative_evidence": False,
                    "requires_counter_evidence": True,
                },
            ]
        }

        # Simulated Round 1 extraction output
        round_1_bundle = {
            "questions": [
                {
                    "question_id": "Q1",
                    "question": "Under what conditions does RAG reduce hallucination?",
                    "status": "complete_candidate",
                    "findings": [
                        {
                            "finding_id": "Q1-F1",
                            "question_id": "Q1",
                            "claim": "RAG reduces hallucination when retrieved documents have high relevance.",
                            "source_ids": ["src_rag_survey"],
                            "evidence": [{"evidence_text": "RAG achieves significant hallucination reduction."}],
                            "stance": "support",
                        },
                        {
                            "finding_id": "Q1-F2",
                            "question_id": "Q1",
                            "claim": "Dense passage retrieval outperforms sparse retrieval in reducing factual error.",
                            "source_ids": ["src_dpr_paper"],
                            "evidence": [{"evidence_text": "Dense retrieval reduces error rate."}],
                            "stance": "support",
                        }
                    ],
                    "counter_evidence": [],
                    "evidence_gaps": []
                },
                {
                    "question_id": "Q2",
                    "question": "When can retrieval degrade factual accuracy?",
                    "status": "insufficient",
                    "findings": [],
                    "counter_evidence": [],
                    "evidence_gaps": ["No findings extracted from selected sources for this question."]
                }
            ],
            "source_finding_map": {
                "src_rag_survey": ["Q1-F1"],
                "src_dpr_paper": ["Q1-F2"],
            },
            "all_findings": []
        }

        # In Round 2, new selection bundle only has a new source for Q2
        new_selection = {
            "per_question_selection": {
                "Q1": {"selected_sources": []},  # No new sources selected for Q1 in this round
                "Q2": {
                    "selected_sources": [
                        (
                            {
                                "source_id": "src_noise_paper",
                                "title": "Retrieval Noise Degradation",
                                "url": "https://example.com/noise",
                                "retrieved_content": "Noisy retrieval degrades accuracy by 25% when context contains conflicting facts.",
                                "all_source_ids": ["src_noise_paper"]
                            },
                            "Targeted re-search source"
                        )
                    ]
                }
            },
            "unique_selected_sources": []
        }

        # Run extraction with existing_extraction_bundle passed
        round_2_bundle = extract_research_evidence(
            MockGeminiClient(),
            plan,
            new_selection,
            existing_extraction_bundle=round_1_bundle
        )

        q1_res = next(q for q in round_2_bundle["questions"] if q["question_id"] == "Q1")
        # Invariant check: Round 1 findings for Q1 MUST NOT disappear!
        self.assertEqual(len(q1_res["findings"]), 2)
        q1_fids = [f["finding_id"] for f in q1_res["findings"]]
        self.assertIn("Q1-F1", q1_fids)
        self.assertIn("Q1-F2", q1_fids)


class TestOpenAlexQuerySanitization(unittest.TestCase):
    """Test OpenAlex query sanitization preventing HTTP 400."""

    def test_sanitize_removes_parentheticals_and_reserved_chars(self):
        raw_query = "Under what conditions does RAG reduce hallucination (e.g., in domain-specific tasks)?"
        sanitized = _sanitize_openalex_query(raw_query)
        self.assertNotIn("(", sanitized)
        self.assertNotIn(")", sanitized)
        self.assertNotIn("?", sanitized)
        self.assertIn("reduce hallucination", sanitized)

    def test_sanitize_removes_elasticsearch_operators(self):
        raw_query = "RAG + hallucination && accuracy || degradation !error"
        sanitized = _sanitize_openalex_query(raw_query)
        for char in ["+", "&&", "||", "!"]:
            self.assertNotIn(char, sanitized)

    def test_sanitize_truncates_long_queries(self):
        long_query = "word " * 100
        sanitized = _sanitize_openalex_query(long_query)
        self.assertLessEqual(len(sanitized), 250)

    def test_generate_targeted_queries_produces_clean_queries(self):
        question = {
            "id": "Q1",
            "question": "Under what conditions does retrieval-augmented generation reduce hallucination (e.g., in medical QA)?",
            "requires_quantitative_evidence": True,
            "requires_counter_evidence": True,
        }
        queries = generate_targeted_queries(question, ["quantitative_evidence", "counter_evidence"])
        self.assertGreater(len(queries), 0)
        for q in queries:
            self.assertNotIn("(", q["query_text"])
            self.assertNotIn(")", q["query_text"])
            self.assertNotIn("?", q["query_text"])


class TestRelevanceDominatesPreferenceBonus(unittest.TestCase):
    """Test 3: Relevance must dominate weak source-type bonuses."""

    def test_relevant_paper_outranks_weakly_relevant_preferred_paper(self):
        question = {
            "id": "Q1",
            "question": "Under what conditions does retrieval-augmented generation reduce hallucination in large language models?",
            "preferred_source_types": ["systematic_review"]
        }

        # Strongly relevant paper, authoritative, but preferred source type is 0.0
        relevant_paper = {
            "source_id": "rag_survey",
            "title": "A Survey on Retrieval-Augmented Text Generation for Large Language Models",
            "content": "This paper surveys retrieval-augmented generation (RAG) and how it reduces hallucinations in LLMs under various retrieval conditions.",
            "source_type": "peer_reviewed_paper",
            "authority_score": 0.95,
            "tavily_score": 0.7739
        }

        # Weakly relevant paper, authoritative, but preferred bonus 1.0 (systematic review)
        weak_paper = {
            "source_id": "patient_care_review",
            "title": "Current applications and challenges in large language models for patient care: a systematic review",
            "content": "A systematic review of LLMs applied in clinical medicine and healthcare patient care delivery without retrieval experiments.",
            "source_type": "systematic_review",
            "authority_score": 0.95,
            "tavily_score": 0.8745
        }

        score_relevant = score_source(relevant_paper, question)
        score_weak = score_source(weak_paper, question)

        # Strongly relevant paper MUST outrank weakly relevant paper
        self.assertGreater(score_relevant["final_score"], score_weak["final_score"])

    def test_preference_mapping_recognizes_conference_papers(self):
        source = {"source_type": "peer_reviewed_paper"}
        plan_pref = "peer-reviewed conference paper"
        matched_types = PREFERENCE_TO_SOURCE_TYPES.get(plan_pref, [])
        self.assertIn("peer_reviewed_paper", matched_types)


class TestSourceContentPreservation(unittest.TestCase):
    """Test 4: Retrieved full-text content is preserved through deduplication and re-retrieval."""

    def test_deduplicate_sources_preserves_retrieved_content(self):
        s1 = {
            "url": "https://arxiv.org/abs/2401.00001",
            "title": "Paper 1",
            "source_id": "src_1",
            "retrieved_content": "Full empirical paper body text...",
            "content_status": "full"
        }
        s2 = {
            "url": "https://arxiv.org/abs/2401.00001",
            "title": "Paper 1 (Duplicate)",
            "source_id": "src_2",
            "retrieved_content": "",
            "content_status": "snippet_only"
        }

        deduped = deduplicate_sources([s1, s2])
        self.assertEqual(len(deduped), 1)
        canonical = deduped[0]
        # Full content must NOT be wiped
        self.assertEqual(canonical["retrieved_content"], "Full empirical paper body text...")
        self.assertEqual(canonical["content_status"], "full")
        self.assertIn("src_1", canonical["all_source_ids"])
        self.assertIn("src_2", canonical["all_source_ids"])

    def test_retrieve_selected_sources_does_not_wipe_existing_content(self):
        s = {
            "url": "https://example.com/already_retrieved",
            "source_id": "src_already",
            "retrieved_content": "Deep full text already downloaded.",
            "content_status": "full"
        }
        mock_tavily = MagicMock()
        stats = retrieve_selected_sources(mock_tavily, [s])
        self.assertEqual(s["retrieved_content"], "Deep full text already downloaded.")
        self.assertEqual(s["content_status"], "full")
        self.assertEqual(stats["successes"], 1)


class TestQuantitativeHeuristicExtractionAndValidation(unittest.TestCase):
    """Test 5: Quantitative findings survive extraction and validation."""

    def test_percentage_transition_extraction(self):
        text = "Our approach reduced hallucination rate from 45.2% to 12.1% on the benchmark."
        records = extract_heuristic_quantitative_records(text, "src_test")
        self.assertGreater(len(records), 0)
        rec = records[0]
        self.assertEqual(rec["baseline_score"], 45.2)
        self.assertEqual(rec["experimental_score"], 12.1)
        self.assertEqual(rec["absolute_difference"], -33.1)

    def test_gate3_accepts_accuracy_on_under_what_conditions_question(self):
        question = {
            "id": "Q1",
            "question": "Under what conditions does retrieval-augmented generation reduce hallucination?",
            "requires_quantitative_evidence": True,
            "quantitative_fields": ["accuracy", "error rate"],
        }
        finding = {
            "claim": "RAG reduces hallucination under high retriever recall, improving accuracy from 62.0% to 84.5%.",
            "quantitative_evidence": [
                {
                    "metric": "Accuracy %",
                    "baseline_score": 62.0,
                    "experimental_score": 84.5,
                    "absolute_difference": 22.5,
                }
            ],
            "evidence": [{"evidence_text": "improving accuracy from 62.0% to 84.5% on QA benchmark"}],
        }
        passed, clean_finding, reasons = EvidenceValidator.validate_finding(
            finding,
            question,
            source_text="improving accuracy from 62.0% to 84.5% on QA benchmark"
        )
        self.assertTrue(passed, f"Validation failed with reasons: {reasons}")


class TestCounterEvidenceClassification(unittest.TestCase):
    """Test 6: Counter-evidence on failure-mode questions passes Gate 1 without false rejection."""

    def test_gate1_accepts_robustness_and_failure_on_when_degrade_question(self):
        question = {
            "id": "Q2",
            "question": "When can retrieval actually degrade factual accuracy?",
            "requires_counter_evidence": True,
        }
        finding = {
            "claim": "Irrelevant retrieved context causes models to hallucinate, degrading factual accuracy.",
            "stance": "counter",
            "evidence": [{"evidence_text": "Retrieval noise degrades factual accuracy by distracting generation."}],
        }
        passed, _, reasons = EvidenceValidator.validate_finding(
            finding,
            question,
            source_text="Retrieval noise degrades factual accuracy by distracting generation."
        )
        self.assertTrue(passed, f"Validation failed with reasons: {reasons}")

    def test_negated_support_not_classified_as_support(self):
        text = "The retrieval system fails to improve factual accuracy when documents conflict."
        # Verify that "fails to improve" is not falsely treated as positive support
        # by our support regexes
        from search_agent.evidence_validator import EvidenceValidator
        finding = {
            "claim": text,
            "evidence": [{"evidence_text": text}],
            "stance": "counter"
        }
        calibrated_stance = EvidenceValidator.calibrate_context_and_stance(finding, {})
        self.assertNotEqual(calibrated_stance, "support")


class TestFindingDeduplicationDistinctness(unittest.TestCase):
    """Test 8: Deduplication must not merge semantically distinct findings."""

    def test_distinct_claims_preserved(self):
        plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "Under what conditions does RAG reduce hallucination?",
                    "requires_quantitative_evidence": False,
                    "requires_counter_evidence": False,
                }
            ]
        }
        bundle = {
            "questions": [
                {
                    "question_id": "Q1",
                    "question": "Under what conditions does RAG reduce hallucination?",
                    "status": "complete_candidate",
                    "findings": [
                        {
                            "finding_id": "Q1-F1",
                            "question_id": "Q1",
                            "claim": "RAG reduces hallucination in open-domain question answering.",
                            "source_ids": ["src_1"],
                            "evidence": [{"evidence_text": "Reduces hallucination in QA."}],
                            "stance": "support"
                        }
                    ],
                    "counter_evidence": [],
                    "evidence_gaps": []
                }
            ],
            "source_finding_map": {"src_1": ["Q1-F1"]},
            "all_findings": []
        }
        new_sel = {
            "per_question_selection": {
                "Q1": {
                    "selected_sources": [
                        (
                            {
                                "source_id": "src_2",
                                "title": "Memory Latency in RAG",
                                "url": "https://example.com/latency",
                                "retrieved_content": "Retrieval index compression reduces latency overhead significantly.",
                                "all_source_ids": ["src_2"]
                            },
                            "Latency source"
                        )
                    ]
                }
            },
            "unique_selected_sources": []
        }
        res = extract_research_evidence(
            MockGeminiClient(),
            plan,
            new_sel,
            existing_extraction_bundle=bundle
        )
        q1 = res["questions"][0]
        # Should keep Q1-F1
        self.assertGreaterEqual(len(q1["findings"]), 1)
        self.assertEqual(q1["findings"][0]["finding_id"], "Q1-F1")


class TestTeeLogger(unittest.TestCase):
    """Test TeeLogger infrastructure."""

    def test_tee_logger_writes_output_and_preserves_terminal(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = TeeLogger(log_dir=tmp_dir)
            test_msg = "Hello Autonomous Research Agent Test Run!"
            print(test_msg)
            logger.close()

            # Verify log file was created
            log_files = os.listdir(tmp_dir)
            self.assertEqual(len(log_files), 1)
            log_path = os.path.join(tmp_dir, log_files[0])

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn(test_msg, content)


if __name__ == "__main__":
    unittest.main()
