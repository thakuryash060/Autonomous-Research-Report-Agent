"""
Unit tests for the Evidence Validation Layer (EVL) and Research Hardening.

Verifies:
1. Gate 1: Question Relevance & Target Variable Alignment (rejects wrong sub-question routing).
2. Gate 2: Claim Support & Entailment (rejects ungrounded excerpts or hallucinated claims).
3. Gate 3: Quantitative Metric Validity (rejects sample size, year, metadata; validates true contrasts).
4. Gate 4: Context Compatibility & Stance Nuance (support vs counter vs limitation vs trade_off).
5. Gate 5: Source Independence & Cluster Consolidation (prevents 1 paper from faking consensus).
6. Useful vs Idle Source Tracking.
7. Ambiguity & Clarification Gate.
"""

import unittest
from search_agent.evidence_validator import EvidenceValidator
from planner.validation.ambiguity_detector import detect_topic_ambiguity
from search_agent.evidence_sufficiency import evaluate_evidence_sufficiency


class TestGate1QuestionRelevance(unittest.TestCase):

    def setUp(self):
        self.q_latency = {
            "id": "Q3",
            "question": "What are the computational overheads, token costs, and latency penalties in multi-agent architectures?",
            "type": "comparison"
        }
        self.q_failure = {
            "id": "Q2",
            "question": "What are the primary failure modes, error propagation bottlenecks, and cascading hallucinations in multi-agent systems?",
            "type": "limitations"
        }
        self.q_accuracy = {
            "id": "Q1",
            "question": "How do multi-agent systems compare quantitatively on complex reasoning benchmarks?",
            "type": "comparison"
        }

    def test_wrong_subquestion_routing_rejected(self):
        # An autism ML classification finding routed to a latency/overhead question
        autism_finding = {
            "claim": "Autism classification accuracy negatively correlates with log-transformed sample size.",
            "evidence": [{"evidence_text": "Sample size analysis of autism studies showed 88 participants."}],
            "quantitative_evidence": []
        }
        valid, msg = EvidenceValidator.validate_question_relevance(autism_finding, self.q_latency)
        self.assertFalse(valid)
        self.assertIn("Missing required latency/cost/overhead metric", msg)

        # Pure accuracy finding routed to latency question
        accuracy_finding = {
            "claim": "Multi-agent debate achieves 84.2% pass rate on GSM8K reasoning benchmark.",
            "evidence": [{"evidence_text": "GSM8K accuracy reached 84.2% on math benchmarks."}],
            "quantitative_evidence": [{"metric": "Accuracy", "experimental_score": 84.2}]
        }
        valid_acc, msg_acc = EvidenceValidator.validate_question_relevance(accuracy_finding, self.q_latency)
        self.assertFalse(valid_acc)
        self.assertIn("Missing required latency/cost/overhead metric", msg_acc)

    def test_off_domain_markers_disqualified(self):
        bio_finding = {
            "claim": "Systematic reviews on sugar-sweetened beverages and weight gain exhibit reporting bias.",
            "evidence": [{"evidence_text": "Reviews disclosing financial conflicts with the food industry found no link."}],
            "quantitative_evidence": []
        }
        valid, msg = EvidenceValidator.validate_question_relevance(bio_finding, self.q_accuracy)
        self.assertFalse(valid)
        self.assertIn("Disqualified biological/medical marker", msg)

    def test_correct_target_variable_passes(self):
        latency_finding = {
            "claim": "Multi-agent debate increases token cost overhead by 3.5x and introduces 450ms latency delay.",
            "evidence": [{"evidence_text": "Token cost overhead was 3.5x higher with 450ms latency delay."}],
            "quantitative_evidence": [{"metric": "Token Overhead", "multiplier": "3.5x"}]
        }
        valid, msg = EvidenceValidator.validate_question_relevance(latency_finding, self.q_latency)
        self.assertTrue(valid)


class TestGate2ClaimSupport(unittest.TestCase):

    def test_ungrounded_excerpt_rejected(self):
        source_text = "In this work, we evaluated single-agent baseline prompting on MATH."
        finding = {
            "claim": "Multi-agent systems achieve 95% accuracy.",
            "evidence": [{"evidence_text": "Multi-agent systems achieve 95% accuracy on MATH."}],
            "quantitative_evidence": []
        }
        valid, msg = EvidenceValidator.validate_claim_support(finding, source_text)
        self.assertFalse(valid)
        self.assertIn("not grounded in source text", msg)

    def test_unsubstantiated_claim_rejected(self):
        source_text = "We evaluated baseline temperature scaling on GSM8K benchmark datasets."
        finding = {
            "claim": "Quantum algorithms achieve exponential speedup over classical transformers.",
            "evidence": [{"evidence_text": "We evaluated baseline temperature scaling on GSM8K benchmark datasets."}],
            "quantitative_evidence": []
        }
        valid, msg = EvidenceValidator.validate_claim_support(finding, source_text)
        self.assertFalse(valid)
        self.assertIn("shares zero substantive concepts", msg)


class TestGate3QuantitativeMetricValidity(unittest.TestCase):

    def setUp(self):
        self.q_accuracy = {
            "id": "Q1",
            "question": "How do multi-agent systems compare quantitatively on benchmark accuracy?",
            "requires_quantitative_evidence": True
        }
        self.q_latency = {
            "id": "Q3",
            "question": "What is the token cost and latency overhead of multi-agent systems?",
            "requires_quantitative_evidence": True
        }

    def test_metadata_numbers_rejected_as_quantitative_evidence(self):
        # Sample size N=88 and publication year treated as quantitative evidence
        finding = {
            "claim": "Studies surveyed neuroimaging classification with median 88 subjects published in 2021.",
            "evidence": [{"evidence_text": "Survey of studies showed median sample size of 88 subjects."}],
            "quantitative_evidence": [
                {"metric": "Sample Size", "baseline_score": None, "experimental_score": 88.0},
                {"metric": "Publication Year", "baseline_score": None, "experimental_score": 2021.0}
            ]
        }
        valid, clean_quant, msg = EvidenceValidator.validate_quantitative_validity(finding, self.q_accuracy, "")
        self.assertFalse(valid)
        self.assertEqual(len(clean_quant), 0)

    def test_valid_benchmark_accuracy_contrast_accepted(self):
        finding = {
            "claim": "Multi-agent debate improved accuracy on GSM8K.",
            "evidence": [{"evidence_text": "Accuracy rose from 78.5% to 84.2%."}],
            "quantitative_evidence": [
                {
                    "metric": "Accuracy",
                    "baseline_score": 78.5,
                    "experimental_score": 84.2,
                    "absolute_difference": 5.7
                }
            ]
        }
        valid, clean_quant, msg = EvidenceValidator.validate_quantitative_validity(finding, self.q_accuracy, "")
        self.assertTrue(valid)
        self.assertEqual(len(clean_quant), 1)

    def test_multiplier_accepted_for_latency_question(self):
        finding = {
            "claim": "Multi-agent system incurred 3.5x token cost overhead.",
            "evidence": [{"evidence_text": "Token cost overhead was 3.5x higher."}],
            "quantitative_evidence": [
                {
                    "metric": "Token Cost Overhead",
                    "multiplier": "3.5x"
                }
            ]
        }
        valid, clean_quant, msg = EvidenceValidator.validate_quantitative_validity(finding, self.q_latency, "")
        self.assertTrue(valid)
        self.assertEqual(clean_quant[0]["multiplier"], "3.5x")


class TestGate4ContextAndStanceNuance(unittest.TestCase):

    def test_tradeoff_is_not_counter(self):
        tradeoff_finding = {
            "claim": "Multi-agent debate achieves superior accuracy on complex tasks, but at the expense of 4x token overhead.",
            "evidence": [{"evidence_text": "Debate improves math accuracy but incurs 4x token overhead."}]
        }
        calibrated = EvidenceValidator.calibrate_context_and_stance(tradeoff_finding, {})
        self.assertEqual(calibrated, "trade_off")
        self.assertNotEqual(calibrated, "counter")

    def test_limitation_is_not_counter(self):
        limitation_finding = {
            "claim": "The multi-agent framework was evaluated only on English GSM8K benchmarks and requires high GPU memory.",
            "evidence": [{"evidence_text": "Evaluated only on English GSM8K with high memory requirements."}]
        }
        calibrated = EvidenceValidator.calibrate_context_and_stance(limitation_finding, {})
        self.assertEqual(calibrated, "limitation")
        self.assertNotEqual(calibrated, "counter")

    def test_true_counter_detected(self):
        counter_finding = {
            "claim": "Under normalized compute budgets, single-agent prompting matches multi-agent accuracy with zero communication errors.",
            "evidence": [{"evidence_text": "Normalized compute single-agent matches multi-agent accuracy."}]
        }
        calibrated = EvidenceValidator.calibrate_context_and_stance(counter_finding, {})
        self.assertEqual(calibrated, "counter")

    def test_counter_quota_not_satisfied_by_tradeoffs_or_limitations(self):
        question = {
            "id": "Q1",
            "question": "Evaluation of multi-agent LLMs",
            "requires_counter_evidence": True,
            "source_requirements": {
                "minimum_sources": 2,
                "minimum_counter_evidence_sources": 1
            }
        }
        selection_bundle = {
            "per_question_selection": {
                "Q1": {"selected_sources": [({"source_id": "S1", "content_status": "full"}, "top")]}
            }
        }
        # Findings contain only limitations and trade-offs, ZERO true counters
        findings = [
            {"source_ids": ["S1"], "claim": "Accuracy trade-off", "stance": "trade_off", "evidence": []},
            {"source_ids": ["S1"], "claim": "Evaluation limitation", "stance": "limitation", "evidence": []}
        ]
        result = evaluate_evidence_sufficiency(question, findings, selection_bundle)
        self.assertFalse(result["sufficient"])
        self.assertEqual(result["counter_count"], 0)
        self.assertEqual(result["limitation_count"], 1)
        self.assertEqual(result["trade_off_count"], 1)
        self.assertIn("counter_evidence", result["missing_requirements"])


class TestGate5SourceIndependenceAndClustering(unittest.TestCase):

    def test_multiple_findings_from_single_source_do_not_fake_sufficiency(self):
        question = {
            "id": "Q1",
            "question": "Evaluation of multi-agent LLMs",
            "requires_quantitative_evidence": True,
            "source_requirements": {
                "minimum_sources": 3,
                "minimum_quantitative_sources": 2
            }
        }
        selection_bundle = {
            "per_question_selection": {
                "Q1": {"selected_sources": [({"source_id": "S1", "content_status": "full"}, "top")]}
            }
        }
        # 6 findings from the same paper S1
        single_paper_findings = [
            {
                "finding_id": f"Q1-F{i}",
                "source_ids": ["S1"],
                "claim": f"Benchmark observation {i}",
                "stance": "support",
                "quantitative_evidence": [{"metric": "Accuracy", "experimental_score": 80.0 + i}]
            }
            for i in range(1, 7)
        ]

        metrics = EvidenceValidator.enforce_source_independence(single_paper_findings)
        self.assertEqual(metrics["unique_source_count"], 1)
        self.assertTrue(metrics["high_concentration"])
        self.assertEqual(metrics["concentration_ratio"], 1.0)

        suff = evaluate_evidence_sufficiency(question, single_paper_findings, selection_bundle)
        self.assertFalse(suff["sufficient"])
        self.assertEqual(suff["quantitative_source_count"], 1)
        self.assertIn("quantitative_evidence", suff["missing_requirements"])


class TestUsefulVsIdleSources(unittest.TestCase):

    def test_sources_without_findings_marked_idle(self):
        selected_sources = [
            ({"source_id": "S1", "title": "Useful Paper"}, "top"),
            ({"source_id": "S2", "title": "Idle Paper"}, "top"),
            ({"source_id": "S3", "title": "Another Useful Paper"}, "top")
        ]
        validated_findings = [
            {"source_ids": ["S1"], "claim": "Claim 1"},
            {"source_ids": ["S3"], "claim": "Claim 2"}
        ]
        useful, idle = EvidenceValidator.filter_useful_sources(selected_sources, validated_findings)
        useful_ids = [s["source_id"] for s in useful]
        idle_ids = [s["source_id"] for s in idle]

        self.assertEqual(useful_ids, ["S1", "S3"])
        self.assertEqual(idle_ids, ["S2"])


class TestAmbiguityClarificationGate(unittest.TestCase):

    def test_placeholder_topics_detected(self):
        # Exact prompt from user test that caused hallucinated research directions
        ambiguous_prompt_1 = "What evidence exists regarding a controversial scientific claim?"
        is_amb, reason, questions = detect_topic_ambiguity(ambiguous_prompt_1)
        self.assertTrue(is_amb)
        self.assertIn("generic placeholder", reason)
        self.assertGreaterEqual(len(questions), 1)

        ambiguous_prompt_2 = "Tell me about research."
        is_amb2, _, _ = detect_topic_ambiguity(ambiguous_prompt_2)
        self.assertTrue(is_amb2)

    def test_concrete_scientific_topic_passes(self):
        concrete_topic = "Do multi-agent LLM debate architectures outperform single-agent baselines on GSM8K reasoning?"
        is_amb, reason, questions = detect_topic_ambiguity(concrete_topic)
        self.assertFalse(is_amb)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()

