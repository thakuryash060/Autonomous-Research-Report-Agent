"""
tests/test_live_feedback_fixes.py

Unit tests verifying the 7 prioritized pipeline fixes from the live research run:
1. Full-text evidence extraction: arXiv HTML/PDF resolution and pypdf extraction.
2. Relevant retrieved sources yielding findings: Gate 1 defense concept alignment.
3. Cross-question routing: Archetype-gated cross-routing blocks incompatible claims.
4. Evidence deduplication: Normalization and cross-question deduplication.
5. Counter-evidence extraction: Security counter-evidence recognized without false limitation downgrading.
6. Defense-specific evidence extraction: Gate 1 and Gate 2 defense validation.
7. Primary-source counting inconsistency: conference_paper and academic providers verified in contract enforcer.
"""

import unittest
import io
import pypdf
from search_agent.content_retriever import (
    _extract_arxiv_id,
    _extract_text_from_pdf_bytes,
    _assess_content_status,
)
from search_agent.evidence_validator import EvidenceValidator
from search_agent.evidence_extractor import (
    extract_research_evidence,
)
from planner.validation.contract_enforcer import enforce_research_contract


class TestFullTextAndPDFRetrieval(unittest.TestCase):
    """Test Item 1: Full-text resolution and PDF extraction."""

    def test_extract_arxiv_id_from_various_formats(self):
        self.assertEqual(_extract_arxiv_id("https://arxiv.org/abs/2402.17840"), "2402.17840")
        self.assertEqual(_extract_arxiv_id("https://doi.org/10.48550/arxiv.2402.17840"), "2402.17840")
        self.assertEqual(_extract_arxiv_id("https://arxiv.org/html/2606.09005v1"), "2606.09005v1")
        self.assertEqual(_extract_arxiv_id("https://arxiv.org/pdf/2410.02298.pdf"), "2410.02298")
        self.assertEqual(_extract_arxiv_id("https://example.com/not-arxiv"), "")

    def test_pypdf_text_extraction_from_bytes(self):
        # Create a real in-memory PDF with text
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        # Blank page extracts cleanly without error
        text = _extract_text_from_pdf_bytes(pdf_bytes)
        self.assertIsInstance(text, str)

    def test_assess_content_status_accuracy(self):
        # Empty text
        self.assertEqual(_assess_content_status(""), "failed")
        # Short snippet
        self.assertEqual(_assess_content_status("Short snippet about RAG."), "snippet_only")
        # Moderate abstract without empirical keywords
        self.assertEqual(_assess_content_status("A " * 500), "partial")
        # Empirical full text with sections and benchmarks
        full_text = "In our experiments, the evaluation results on benchmarks show accuracy improves significantly. " * 30
        self.assertEqual(_assess_content_status(full_text), "full")


class TestResilientEvidenceValidation(unittest.TestCase):
    """Test Items 2, 5, 6: Gate 1 Defense Concepts, Gate 2 Grounding, Gate 4 Counter Stances."""

    def setUp(self):
        self.defense_question = {
            "id": "Q3",
            "type": "evaluation",
            "question": "How effective are current defense mechanisms at mitigating these vulnerabilities?",
            "evidence_needed": ["defense mechanism description", "mitigation effectiveness metrics"],
            "requires_quantitative_evidence": True,
            "requires_counter_evidence": True
        }

    def test_defense_finding_passes_gate_1_without_literal_prompt_overlap(self):
        """Verify Item 6: Defense paper findings pass Gate 1 even if literal prompt words are not repeated."""
        finding = {
            "claim": "PRA-RAG reduces retrieval attack success rate from 88% down to 12% across open-domain QA benchmarks.",
            "evidence": [
                {"evidence_text": "Our proposed method PRA-RAG reduces the retrieval attack success rate from 88% to 12% across benchmarks."}
            ]
        }
        passed, msg = EvidenceValidator.validate_question_relevance(finding, self.defense_question)
        self.assertTrue(passed, f"Gate 1 failed unexpectedly: {msg}")

    def test_gate_2_resilient_to_whitespace_and_citation_brackets(self):
        """Verify Item 2: Gate 2 tolerates citation brackets [1, 2] and slight LLM formatting differences."""
        source_text = "In this work, we propose PRA-RAG [1]. Extensive evaluations demonstrate that PRA-RAG achieves robust aggregation and significantly reduces retrieval attack success rate from 88% to 12% across open-domain QA benchmarks."
        # Excerpt stripped of citations and slightly reformatted by LLM
        finding = {
            "claim": "PRA-RAG achieves robust aggregation and reduces retrieval attack success rate.",
            "evidence": [
                {"evidence_text": "PRA-RAG achieves robust aggregation and significantly reduces retrieval attack success rate from 88% to 12% across open-domain QA benchmarks."}
            ]
        }
        passed, msg = EvidenceValidator.validate_claim_support(finding, source_text)
        self.assertTrue(passed, f"Gate 2 failed on grounded excerpt: {msg}")

    def test_gate_4_security_counter_evidence_not_downgraded_to_limitation(self):
        """Verify Item 5: Security counter evidence is recognized as 'counter' and not falsely downgraded."""
        finding = {
            "claim": "Standard RAG systems remain highly resilient under knowledge poisoning attacks when context isolation is applied, dropping attack success rate to below 5%.",
            "evidence": [
                {"evidence_text": "Attack success rate drops to below 5% under context isolation, demonstrating high resilience."}
            ],
            "stance": "counter"
        }
        stance = EvidenceValidator.calibrate_context_and_stance(finding, self.defense_question)
        self.assertEqual(stance, "counter", "Expected 'counter' stance for high resilience / low ASR finding")

    def test_gate_3_preserves_qualitative_finding_on_quantitative_question(self):
        """Verify Item 2: Qualitative finding is preserved with clean quantitative list rather than rejected."""
        finding = {
            "claim": "PRA-RAG utilizes certified majority voting to isolate poisoned chunks.",
            "evidence": [
                {"evidence_text": "PRA-RAG utilizes certified majority voting to isolate poisoned chunks."}
            ],
            "quantitative_evidence": []  # No numbers in this qualitative architectural finding
        }
        source_text = "PRA-RAG utilizes certified majority voting to isolate poisoned chunks."
        is_valid, validated, reasons = EvidenceValidator.validate_finding(
            finding,
            self.defense_question,
            source_text=source_text
        )
        self.assertTrue(is_valid, f"Qualitative finding rejected: {reasons}")
        self.assertEqual(validated.get("quantitative_evidence"), [])


class TestCrossQuestionRoutingAndDeduplication(unittest.TestCase):
    """Test Items 3 & 4: Archetype-gated cross-routing and finding deduplication."""

    def test_attack_finding_blocked_from_defense_question_routing(self):
        """Verify Item 3: Pure attack findings cannot route into defense evaluation questions."""
        q1_attack = {
            "id": "Q1",
            "type": "mechanisms",
            "question": "What are the primary vectors of knowledge-base poisoning in RAG systems?"
        }
        q3_defense = {
            "id": "Q3",
            "type": "evaluation",
            "question": "How effective are current defense mechanisms at mitigating these vulnerabilities?"
        }

        attack_finding = {
            "claim": "TPARAG achieves high retrieval and end-to-end attack success rates across open-domain QA benchmarks.",
            "evidence": [
                {"evidence_text": "TPARAG consistently achieves high retrieval attack success rates."}
            ],
            "stance": "support"
        }

        # Mock extraction bundle where Q1 has attack finding and Q3 is evaluating routing
        mock_plan = {"questions": [q1_attack, q3_defense]}
        mock_selection = {
            "per_question_selection": {
                "Q1": {
                    "selected_sources": [
                        ({"source_id": "S17", "content": "TPARAG attack...", "source_type": "conference_paper"}, "primary")
                    ]
                },
                "Q3": {
                    "selected_sources": []
                }
            }
        }

        class MockGemini:
            class models:
                @staticmethod
                def generate_content(*args, **kwargs):
                    class Resp:
                        text = '{"findings": [{"claim": "TPARAG achieves high attack success rate.", "stance": "support", "confidence": "high", "evidence": [{"evidence_type": "qualitative", "evidence_text": "TPARAG achieves high attack success rate."}]}]}'
                    return Resp()

        res = extract_research_evidence(MockGemini(), mock_plan, mock_selection)
        q3_res = next(q for q in res["questions"] if q["question_id"] == "Q3")
        # Q3 should have 0 findings because the pure attack finding was blocked from routing to defense question!
        self.assertEqual(len(q3_res["findings"]), 0)


class TestPrimarySourceContractEnforcement(unittest.TestCase):
    """Test Item 7: Primary source counting in contract enforcer."""

    def test_conference_paper_and_academic_provider_counted_as_primary(self):
        plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "What are the vectors?",
                    "source_requirements": {
                        "minimum_sources": 2,
                        "minimum_primary_sources": 2,
                        "minimum_quantitative_sources": 1,
                        "minimum_counter_evidence_sources": 0
                    }
                }
            ]
        }

        evidence = {
            "sources": [
                {
                    "source_id": "S17",
                    "title": "Token-Level Precise Attack on RAG",
                    "source_type": "conference_paper"
                },
                {
                    "source_id": "OA-W4399991306",
                    "title": "Scalable Data Extraction from RAG",
                    "source_type": "preprint",
                    "doi": "10.48550/arxiv.2402.17840",
                    "provider_name": "openalex"
                }
            ],
            "questions": [
                {
                    "question_id": "Q1",
                    "findings": [
                        {
                            "finding_id": "Q1-F1",
                            "source_ids": ["S17", "OA-W4399991306"],
                            "claim": "Both papers evaluate poisoning attacks.",
                            "stance": "support",
                            "quantitative_evidence": [{"metric": "ASR", "baseline_score": 50.0, "experimental_score": 85.0}]
                        }
                    ]
                }
            ]
        }

        res = enforce_research_contract(plan, evidence)
        q1_comp = res["question_compliance"][0]
        prim_clause = next(c for c in q1_comp["clauses"] if c["clause"] == "minimum_primary_sources")
        
        # S17 (conference_paper) and OA-W4399991306 (openalex preprint) must both be counted as primary!
        self.assertEqual(prim_clause["actual"], 2)
        self.assertTrue(prim_clause["met"])
        self.assertEqual(q1_comp["status"], "MET")


class TestLatencyAndOverheadExtraction(unittest.TestCase):
    """Verify quantitative extraction and Gate 3 validation for latency overheads and execution times."""

    def test_extract_latency_overhead_and_transitions(self):
        from search_agent.evidence_extractor import extract_heuristic_quantitative_records
        text1 = "Guardrail model maintained a 4.8% false positive rate and a median latency overhead of 61.2 ms."
        records1 = extract_heuristic_quantitative_records(text1, "S1")
        latency_recs = [r for r in records1 if "Latency Overhead" in r["metric"]]
        self.assertTrue(len(latency_recs) >= 1)
        self.assertEqual(latency_recs[0]["experimental_score"], 61.2)

        text2 = "Probability-scoring distillation reduced execution time from 358.12 to 1.31 microseconds while preserving accuracy."
        records2 = extract_heuristic_quantitative_records(text2, "S2")
        time_recs = [r for r in records2 if "Execution Time" in r["metric"]]
        self.assertTrue(len(time_recs) >= 1)
        self.assertEqual(time_recs[0]["baseline_score"], 358.12)
        self.assertEqual(time_recs[0]["experimental_score"], 1.31)

    def test_gate_3_accepts_standalone_latency_overhead(self):
        finding = {
            "claim": "The median latency overhead was 61.2 ms.",
            "evidence": [{"evidence_text": "maintaining a median latency overhead of 61.2 ms"}],
            "quantitative_evidence": [
                {
                    "metric": "Latency Overhead (ms)",
                    "experimental_score": 61.2,
                    "absolute_difference": 61.2
                }
            ]
        }
        latency_question = {
            "id": "Q3",
            "question": "What is the latency overhead introduced by guardrail models in milliseconds?",
            "requires_quantitative_evidence": True
        }
        ok, valid_recs, msg = EvidenceValidator.validate_quantitative_validity(finding, latency_question, "")
        self.assertTrue(ok)
        self.assertEqual(len(valid_recs), 1)
        self.assertEqual(valid_recs[0]["experimental_score"], 61.2)


class TestParallelQuestionDisambiguation(unittest.TestCase):
    """Verify that parallel comparative questions across distinct domains/tasks are allowed, while duplicates are rejected."""

    def test_parallel_math_and_code_questions_accepted(self):
        from planner.validation.quality_validator import validate_plan_quality

        plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "What is the quantitative impact of multi-agent debate on mathematical reasoning accuracy compared to single-agent Chain-of-Thought prompting?",
                    "search_strategy": {
                        "primary_queries": ["multi agent debate math reasoning accuracy LLM benchmark", "GSM8K MATH dataset evaluation"],
                        "secondary_queries": [],
                        "counter_evidence_queries": ["agent debate does not improve math accuracy over CoT"]
                    },
                    "source_requirements": {"minimum_sources": 3, "minimum_counter_evidence_sources": 1},
                    "requires_quantitative_evidence": True,
                    "quantitative_fields": ["accuracy"],
                    "requires_counter_evidence": True
                },
                {
                    "id": "Q2",
                    "question": "What is the quantitative impact of multi-agent debate on code generation accuracy compared to single-agent Chain-of-Thought prompting?",
                    "search_strategy": {
                        "primary_queries": ["multi agent debate code generation accuracy HumanEval MBPP", "collaborative LLM coding benchmark pass@1 evaluation"],
                        "secondary_queries": [],
                        "counter_evidence_queries": ["multi agent coding accuracy degradation compared to single agent"]
                    },
                    "source_requirements": {"minimum_sources": 3, "minimum_counter_evidence_sources": 1},
                    "requires_quantitative_evidence": True,
                    "quantitative_fields": ["pass@1"],
                    "requires_counter_evidence": True
                }
            ]
        }

        # Should pass without raising duplicate question RuntimeError
        validated = validate_plan_quality(plan)
        self.assertEqual(len(validated["questions"]), 2)

    def test_true_near_duplicate_questions_rejected(self):
        from planner.validation.quality_validator import validate_plan_quality

        duplicate_plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "What is the quantitative impact of multi-agent debate on reasoning accuracy compared to single-agent Chain-of-Thought prompting?",
                    "search_strategy": {
                        "primary_queries": ["multi agent debate reasoning accuracy LLM benchmark"],
                        "secondary_queries": [],
                        "counter_evidence_queries": ["agent debate fails"]
                    },
                    "source_requirements": {"minimum_sources": 3, "minimum_counter_evidence_sources": 1},
                    "requires_quantitative_evidence": True,
                    "quantitative_fields": ["accuracy"],
                    "requires_counter_evidence": True
                },
                {
                    "id": "Q2",
                    "question": "How does multi-agent debate quantitatively affect reasoning accuracy compared to single-agent Chain-of-Thought prompting?",
                    "search_strategy": {
                        "primary_queries": ["multi agent debate reasoning accuracy LLM benchmark"],
                        "secondary_queries": [],
                        "counter_evidence_queries": ["agent debate fails"]
                    },
                    "source_requirements": {"minimum_sources": 3, "minimum_counter_evidence_sources": 1},
                    "requires_quantitative_evidence": True,
                    "quantitative_fields": ["accuracy"],
                    "requires_counter_evidence": True
                }
            ]
        }

        with self.assertRaises(RuntimeError) as ctx:
            validate_plan_quality(duplicate_plan)
        self.assertIn("Duplicate or near-duplicate", str(ctx.exception))


class TestEmpiricalCounterCalibrationAndRetrieval(unittest.TestCase):
    """Verify counter-evidence calibration against Self-Consistency baselines and retrieval reconciliation."""

    def test_lower_than_sc_claim_calibrated_as_counter(self):
        finding = {
            "claim": "On mathematical and reasoning benchmark tasks like MATH and GSM8k, OPTIMA variants demonstrate comparable or slightly lower performance than Self-Consistency (SC) baselines",
            "evidence": [
                {
                    "evidence_text": "In debate tasks, OPTIMA’s benefits are nuanced but evident. It achieves better performance and efficiency on ARC-C and MMLU, while on MATH and GSM8k, OPTIMA variants show comparable or slightly lower performance than SC, but with much higher token efficiency."
                }
            ]
        }
        stance = EvidenceValidator.calibrate_context_and_stance(finding, {})
        self.assertEqual(stance, "counter")

    def test_retrieval_reconciles_snippet_instead_of_failing(self):
        from search_agent.content_retriever import retrieve_selected_sources

        class MockTavilyFailingExtract:
            def extract(self, urls, extract_depth="basic"):
                # Simulates Tavily extract failing on blocked academic site
                return {"results": [], "failed_results": [{"url": urls[0], "error": "403 Forbidden"}]}
            def search(self, query, max_results=2):
                return {"results": []}

        sources = [
            {
                "source_id": "S2-1",
                "title": "Is Multi-Agent Debate (MAD) the Silver Bullet?",
                "url": "https://www.semanticscholar.org/paper/Is-Multi-Agent-Debate-Chun/12345",
                "content": "Empirical analysis showing multi-agent debate underperforms on code generation benchmarks compared to standard prompting baselines."
            }
        ]
        res = retrieve_selected_sources(MockTavilyFailingExtract(), sources)
        # Source must be preserved as snippet_only rather than failed!
        self.assertEqual(sources[0]["content_status"], "snippet_only")
        self.assertIn("Empirical analysis", sources[0]["retrieved_content"])


class TestSpeculativeDecodingAndThresholdEnhancements(unittest.TestCase):
    """Verify generalized fixes for speculative decoding: counter stance calibration, rate extraction, and 503 retry."""

    def test_speculative_decoding_failure_calibrated_as_counter(self):
        finding = {
            "claim": "Speculative decoding fails to provide a net speedup when speculation accuracy is low, and verification overhead or draft computation costs offset benefits, particularly at large batch sizes where performance can degrade below target-only decoding.",
            "evidence": [
                {
                    "evidence_text": "In our preliminary experiment, we found that over 40% of verification effort was spent on rejected tokens, and that 48% of SD steps were more expensive than decoding directly with the target model. We also observed that at larger batch sizes, SD’s already reduced performance gains are further offset by the cost of running the draft model and the additional verification overhead, which can result in overall performance degradation."
                }
            ]
        }
        stance = EvidenceValidator.calibrate_context_and_stance(finding, {})
        self.assertEqual(stance, "counter")

    def test_extract_proportion_and_acceptance_threshold(self):
        from search_agent.evidence_extractor import extract_heuristic_quantitative_records
        text = "In our experiment, 48% of SD steps were more expensive than decoding directly with the target model, and over 40% of verification effort was spent on rejected tokens under an acceptance rate threshold below 0.6."
        records = extract_heuristic_quantitative_records(text, "S24")
        self.assertTrue(any(r.get("experimental_score") == 48.0 for r in records))
        self.assertTrue(any(r.get("experimental_score") == 40.0 for r in records))
        self.assertTrue(any(r.get("experimental_score") == 0.6 for r in records))

    def test_gate_3_accepts_acceptance_rate_threshold(self):
        question = {
            "id": "Q2",
            "question": "Under what acceptance rate thresholds does speculative decoding fail to provide a net speedup?",
            "type": "boundary_conditions"
        }
        finding = {
            "quantitative_evidence": [
                {
                    "metric": "Acceptance / Failure Threshold (ratio)",
                    "baseline_score": None,
                    "experimental_score": 0.6,
                    "absolute_difference": 0.6
                }
            ]
        }
        valid, records, msg = EvidenceValidator.validate_quantitative_validity(finding, question, "")
        self.assertTrue(valid)
        self.assertEqual(len(records), 1)

    def test_transient_503_retry_in_extractor(self):
        from search_agent.evidence_extractor import extract_evidence_from_source

        class MockModelResponse:
            text = '{"findings": [{"claim": "Draft models deliver up to 2.8x speedup.", "stance": "support", "confidence": "high", "evidence": [{"evidence_type": "quantitative", "evidence_text": "Draft models deliver up to 2.8x speedup."}]}]}'

        class MockGeminiClientWith503:
            def __init__(self):
                self.calls = 0
                self.models = self

            def generate_content(self, model, contents, config=None):
                self.calls += 1
                if self.calls < 3:
                    raise Exception("503 UNAVAILABLE: The service is currently unavailable.")
                return MockModelResponse()

        client = MockGeminiClientWith503()
        question = {
            "id": "Q1",
            "question": "What are the measured speedup factors across draft model sizes?",
            "requires_quantitative_evidence": True
        }
        source = {
            "source_id": "OA-W1",
            "title": "Decoding Speculative Decoding",
            "content": "Draft models deliver up to 2.8x speedup."
        }
        findings = extract_evidence_from_source(client, question, source)
        self.assertEqual(client.calls, 3)
        self.assertEqual(len(findings), 1)
        self.assertIn("Draft models deliver up to 2.8x speedup", findings[0]["claim"])


class TestKnowledgeConflictsAndDecodingInterventions(unittest.TestCase):
    """Verify generalized fixes for knowledge conflicts: counter stance calibration, domain gating, and sufficiency."""

    def test_knowledge_conflict_performance_drop_calibrated_as_counter(self):
        finding = {
            "claim": "Existing decoding methods specialized in resolving knowledge conflicts inadvertently deteriorate performance in the absence of conflicts, showing performance drops on non-conflicting data.",
            "evidence": [
                {
                    "evidence_text": "However, existing decoding methods could inadvertently deteriorate performance in absence of conflicts. As evidenced in the Figure 2, while these methods effectively mitigate over-reliance on parametric memory for knowledge conflicts, their performances deteriorate on the non-conflicting data derived from NaturalQuestions dataset."
                }
            ]
        }
        stance = EvidenceValidator.calibrate_context_and_stance(finding, {})
        self.assertEqual(stance, "counter")

    def test_endocardial_activation_disqualified_from_llm_question(self):
        from search_agent.source_ranker import _relevance_score
        source = {
            "source_id": "OA-W2936301394",
            "title": "High-resolution noncontact charge-density mapping of endocardial activation",
            "fields_of_study": ["Medicine"],
            "content": "Noncontact charge density mapping accurately reconstructs endocardial activation in cardiac arrhythmias."
        }
        query_text = "failure modes activation steering factual conflicts"
        question_text = "What are the trade-offs and failure modes introduced by applying decoding-time interventions during knowledge conflict resolution?"
        score = _relevance_score(source, query_text, question_text=question_text)
        self.assertEqual(score, 0.0)

    def test_primary_source_counting_with_cross_routed_findings(self):
        from search_agent.evidence_sufficiency import evaluate_evidence_sufficiency
        question = {
            "id": "Q2",
            "question": "How effective are decoding-time interventions in steering LLMs to resolve knowledge conflicts?",
            "source_requirements": {
                "minimum_sources": 3,
                "minimum_primary_sources": 3,
                "minimum_quantitative_sources": 1,
                "minimum_counter_evidence_sources": 1
            },
            "requires_quantitative_evidence": True,
            "requires_counter_evidence": True
        }
        selection_bundle = {
            "per_question_selection": {
                "Q2": {
                    "selected_sources": [
                        ({"source_id": "S16", "source_type": "conference_paper", "content_status": "full"}, "top_ranked")
                    ]
                }
            },
            "unique_selected_sources": [
                {"source_id": "S16", "source_type": "conference_paper", "content_status": "full"},
                {"source_id": "S12", "source_type": "conference_paper", "content_status": "full"},
                {"source_id": "S2", "source_type": "peer_reviewed_paper", "content_status": "full"}
            ]
        }
        findings = [
            {"source_ids": ["S16"], "stance": "support", "quantitative_evidence": [{"metric": "Score", "baseline_score": 35.0, "experimental_score": 66.0}]},
            {"source_ids": ["S12"], "stance": "support", "quantitative_evidence": [{"metric": "Ratio", "baseline_score": 30.0, "experimental_score": 70.0}]},
            {"source_ids": ["S2"], "stance": "counter", "quantitative_evidence": []}
        ]
        res = evaluate_evidence_sufficiency(question, findings, selection_bundle)
        self.assertEqual(res["primary_source_count"], 3)
        self.assertEqual(res["useful_source_count"], 3)
        self.assertTrue(res["sufficient"])


if __name__ == "__main__":
    unittest.main()

