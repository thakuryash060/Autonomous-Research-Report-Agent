"""
End-to-end evaluation and regression test suite for Autonomous Research Agent.
Verifies all 13 research improvements:
1. Planner quality and feasibility validation
2. Multi-key cross-provider deduplication cascade (DOI, arXiv ID, URL, Title)
3. Stronger relevance filtering & requirement-aware ranking
4. Hard relevance threshold in source selection
5. Strict source policy and extraction-failure eligibility enforcement
6. Evidence-level passage relevance filtering
7. Stance calibration and sanity verification
8. Grounded quantitative number verification & auto-computation
9. Dimensional contradiction analysis (dataset, model, task)
10. Evidence diversity scoring across venues, models, benchmarks, and years
11. Gap-driven targeted re-search query generation
12. Calibrated epistemic evidence synthesis output
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from planner.validation.quality_validator import validate_plan_quality
from search_agent.sources import (
    deduplicate_sources,
    _extract_canonical_keys,
    _extract_arxiv_id,
    is_primary_source_type,
    is_peer_reviewed_type
)
from search_agent.source_ranker import (
    rank_sources,
    score_source,
    compute_evidence_eligibility,
    classify_source
)
from search_agent.source_selector import select_sources_for_question
from search_agent.evidence_extractor import (
    _verify_passage_relevance,
    _validate_finding_for_question,
    _verify_and_calibrate_stance,
    _is_number_grounded,
    _verify_quantitative_grounding,
    _decompose_complex_finding,
    extract_research_evidence
)
from search_agent.summary_generator import (
    detect_empirical_contradictions,
    calculate_evidence_diversity,
    build_research_context
)
from search_agent.evidence_sufficiency import (
    evaluate_evidence_sufficiency,
    generate_targeted_queries
)
from search_agent.evidence_output import build_research_evidence_output


class TestPlanQualityValidation(unittest.TestCase):

    def setUp(self):
        with open("data/research_plan.json", "r", encoding="utf-8") as f:
            self.valid_plan = json.load(f)

    def test_valid_plan_passes(self):
        validated = validate_plan_quality(self.valid_plan)
        self.assertIsNotNone(validated)
        self.assertEqual(len(validated["questions"]), len(self.valid_plan["questions"]))

    def test_duplicate_questions_rejected(self):
        plan = json.loads(json.dumps(self.valid_plan))
        # Make question 2 identical / near-duplicate to question 1
        plan["questions"][1]["question"] = plan["questions"][0]["question"]
        with self.assertRaises(RuntimeError) as ctx:
            validate_plan_quality(plan)
        self.assertIn("Duplicate or near-duplicate", str(ctx.exception))

    def test_unrealistic_quota_rejected(self):
        plan = json.loads(json.dumps(self.valid_plan))
        plan["questions"][0]["source_requirements"]["minimum_sources"] = 45
        with self.assertRaises(RuntimeError) as ctx:
            validate_plan_quality(plan)
        self.assertIn("unrealistic minimum_sources quota", str(ctx.exception))

    def test_inconsistent_counter_evidence_requirement_rejected(self):
        plan = json.loads(json.dumps(self.valid_plan))
        # Requires counter evidence but provides no counter queries
        plan["questions"][0]["requires_counter_evidence"] = True
        plan["questions"][0]["search_strategy"]["counter_evidence_queries"] = []
        plan["questions"][0]["search_strategy"]["counter_evidence"] = []
        with self.assertRaises(RuntimeError) as ctx:
            validate_plan_quality(plan)
        self.assertIn("requires counter-evidence but no counter-evidence search queries", str(ctx.exception))


class TestMultiKeyDeduplication(unittest.TestCase):

    def test_arxiv_id_extraction(self):
        self.assertEqual(_extract_arxiv_id("https://arxiv.org/abs/2406.12345v2"), "2406.12345")
        self.assertEqual(_extract_arxiv_id("https://arxiv.org/pdf/2305.01234.pdf"), "2305.01234")
        self.assertEqual(_extract_arxiv_id("arxiv:2401.99999"), "2401.99999")

    def test_doi_and_title_cascade(self):
        # Three records from different providers representing the same paper
        s1 = {
            "source_id": "OA-W1",
            "title": "ProST: Progressive Sub-task Training for Collaborative Reasoning",
            "url": "https://openalex.org/W12345",
            "doi": "https://doi.org/10.48550/arXiv.2406.01234",
            "score": 0.85,
            "provider_name": "openalex",
            "venue": "NeurIPS"
        }
        s2 = {
            "source_id": "S2-1",
            "title": "ProST: Progressive Sub-task Training for Collaborative Reasoning",
            "url": "https://api.semanticscholar.org/CorpusID:99999",
            "doi": "10.48550/arxiv.2406.01234",
            "score": 0.92,
            "provider_name": "semanticscholar",
            "citation_count": 45
        }
        s3 = {
            "source_id": "S1",
            "title": "ProST: Progressive Sub-Task Training for Collaborative Reasoning",
            "url": "https://arxiv.org/abs/2406.01234v1",
            "score": 0.70,
            "content": "Full experimental results on GSM8K and HumanEval benchmarks."
        }

        merged = deduplicate_sources([s1, s2, s3])
        self.assertEqual(len(merged), 1)
        canonical = merged[0]
        self.assertEqual(canonical["duplicate_count"], 2)
        self.assertEqual(canonical["score"], 0.92)  # Max score preserved
        self.assertEqual(canonical["citation_count"], 45)  # Enriched
        self.assertIn("Full experimental results", canonical["content"])  # Richer content preserved
        self.assertEqual(canonical["venue"], "NeurIPS")  # Metadata enriched


class TestSourceRankingAndGating(unittest.TestCase):

    def test_low_relevance_paper_is_strictly_gated(self):
        # A Nature paper with prestige, but completely off-topic for multi-agent reasoning
        question = {
            "id": "Q1",
            "question": "How do multi-agent LLM systems compare quantitatively to single-agent systems on complex reasoning benchmarks?",
            "requires_quantitative_evidence": True,
            "requires_counter_evidence": True
        }
        spectrometry_paper = {
            "source_id": "S1",
            "title": "High-Throughput Mass Spectrometry and Proteomics Analysis",
            "url": "https://nature.com/articles/s41586-024-1234",
            "content": "We evaluate high-throughput protein sequencing benchmarks.",
            "source_type": "peer_reviewed_paper",
            "fields_of_study": ["biology", "medicine"]
        }
        scores = score_source(spectrometry_paper, question)
        # Should be disqualified or strictly gated
        self.assertEqual(scores["relevance_score"], 0.0)
        self.assertEqual(scores["final_score"], 0.0)

    def test_requirement_aware_bonuses(self):
        question = {
            "id": "Q1",
            "question": "How do multi-agent LLM systems compare quantitatively to single-agent systems?",
            "requires_quantitative_evidence": True,
            "requires_counter_evidence": True
        }
        paper_with_numbers = {
            "source_id": "S1",
            "title": "Multi-agent LLM systems achieve 84.2% accuracy on GSM8K benchmark compared to 78.5% baseline",
            "url": "https://arxiv.org/abs/2401.00001",
            "content": "Quantitative comparison shows 84.2% vs 78.5% baseline, but token cost increased by 3.5x overhead.",
            "discovered_by": [{"question_id": "Q1", "query_text": "multi-agent reasoning", "query_type": "counter"}]
        }
        scores = score_source(paper_with_numbers, question)
        self.assertGreaterEqual(scores["quantitative_bonus"], 0.08)
        self.assertGreaterEqual(scores["counter_bonus"], 0.08)
        self.assertGreater(scores["relevance_score"], 0.50)

    def test_failed_content_extraction_ineligible_for_evidence(self):
        failed_src = {
            "source_id": "S1",
            "title": "Paper",
            "url": "https://example.com/p",
            "source_type": "peer_reviewed_paper",
            "content_status": "failed",
            "content": "",
            "abstract": ""
        }
        eligible, reason = compute_evidence_eligibility(failed_src)
        self.assertFalse(eligible)
        self.assertEqual(reason, "content_extraction_failed")

    def test_discovery_only_sources_excluded_from_selection(self):
        question = {"id": "Q1", "question": "Multi-agent LLM reasoning evaluation"}
        blog_src = {
            "source_id": "S1",
            "source_type": "corporate_blog",
            "ranking_by_question": {"Q1": {"relevance_score": 0.8, "final_score": 0.8}},
            "evidence_eligible": False,
            "eligibility_reason": "policy_discovery_only"
        }
        res = select_sources_for_question(question, [blog_src])
        self.assertEqual(len(res["selected_sources"]), 0)

    def test_author_diversity_cap_enforced(self):
        question = {"id": "Q1", "question": "Multi-agent LLM reasoning evaluation"}
        # 3 papers by the exact same author
        sources = [
            {
                "source_id": f"S{i}",
                "title": f"Paper {i}",
                "authors": ["John Doe", "Jane Smith"],
                "source_type": "peer_reviewed_paper",
                "ranking_by_question": {"Q1": {"relevance_score": 0.8, "final_score": 0.9 - (i * 0.05)}},
                "evidence_eligible": True
            }
            for i in range(1, 4)
        ]
        res = select_sources_for_question(question, sources, max_sources=5)
        # Max 2 allowed from same primary author
        self.assertEqual(len(res["selected_sources"]), 2)

    def test_dynamic_effective_max_quota_allocation(self):
        # Question requires 6 sources, but default max_sources is 5
        question = {
            "id": "Q1",
            "question": "Multi-agent LLM reasoning evaluation",
            "source_requirements": {
                "minimum_sources": 6,
                "minimum_primary_sources": 2
            }
        }
        sources = [
            {
                "source_id": f"S{i}",
                "title": f"Independent Paper {i}",
                "venue": f"Venue {i}",
                "authors": [f"Author {i}"],
                "source_type": "peer-reviewed conference paper",
                "ranking_by_question": {"Q1": {"relevance_score": 0.8, "final_score": 0.9 - (i * 0.02)}},
                "evidence_eligible": True
            }
            for i in range(1, 8)
        ]
        # Should dynamically expand to satisfy minimum_sources=6
        res = select_sources_for_question(question, sources, max_sources=5)
        self.assertEqual(len(res["selected_sources"]), 6)

    def test_quantitative_candidate_prioritization(self):
        question = {
            "id": "Q1",
            "question": "Quantitative evaluation of multi-agent LLMs",
            "requires_quantitative_evidence": True,
            "source_requirements": {
                "minimum_sources": 3,
                "minimum_quantitative_sources": 2
            }
        }
        # S1 and S2 are conceptual/survey (no numbers, higher base score)
        # S3 and S4 have quantitative data (percentages/benchmarks, slightly lower base score)
        sources = [
            {
                "source_id": "S1",
                "title": "A Conceptual Overview of Language Models",
                "abstract": "We explore qualitative concepts and emergent agent phenomena.",
                "venue": "Venue 1",
                "authors": ["Author 1"],
                "source_type": "peer-reviewed journal article",
                "ranking_by_question": {"Q1": {"relevance_score": 0.8, "final_score": 0.95, "quantitative_bonus": 0.0}},
                "evidence_eligible": True
            },
            {
                "source_id": "S2",
                "title": "Philosophical Perspectives on Agent Interactions",
                "abstract": "A survey of agent architectures without numerical evaluations.",
                "venue": "Venue 2",
                "authors": ["Author 2"],
                "source_type": "peer-reviewed journal article",
                "ranking_by_question": {"Q1": {"relevance_score": 0.8, "final_score": 0.94, "quantitative_bonus": 0.0}},
                "evidence_eligible": True
            },
            {
                "source_id": "S3",
                "title": "Empirical GSM8K Benchmarking of Multi-Agent Debate",
                "abstract": "Results show accuracy improved by 14.2% over single-agent baseline.",
                "venue": "Venue 3",
                "authors": ["Author 3"],
                "source_type": "peer-reviewed conference paper",
                "ranking_by_question": {"Q1": {"relevance_score": 0.75, "final_score": 0.85, "quantitative_bonus": 0.08}},
                "evidence_eligible": True
            },
            {
                "source_id": "S4",
                "title": "Quantitative Evaluation of Token Latency and Cost",
                "abstract": "Pass@1 scores reach 78.5% with 3.2x computational overhead.",
                "venue": "Venue 4",
                "authors": ["Author 4"],
                "source_type": "archival preprint from reputable institution",
                "ranking_by_question": {"Q1": {"relevance_score": 0.75, "final_score": 0.84, "quantitative_bonus": 0.08}},
                "evidence_eligible": True
            }
        ]
        res = select_sources_for_question(question, sources, max_sources=3)
        selected_ids = [s[0]["source_id"] for s in res["selected_sources"]]
        # Both quantitative candidates (S3 and S4) must be selected
        self.assertIn("S3", selected_ids)
        self.assertIn("S4", selected_ids)
        self.assertEqual(len(selected_ids), 3)


class TestEvidenceValidationAndGrounding(unittest.TestCase):

    def test_passage_relevance_rejects_off_domain(self):
        qtext = "How do multi-agent LLM systems compare quantitatively on complex reasoning?"
        bio_claim = "DNA methylation patterns indicate epigenetic changes in cellular pathways."
        self.assertFalse(_verify_passage_relevance(bio_claim, [], qtext))

        agent_claim = "Multi-agent debate increases accuracy on GSM8K by 5.7% over single-agent baseline."
        self.assertTrue(_verify_passage_relevance(agent_claim, [], qtext))

    def test_stance_calibration(self):
        # A finding that reports catastrophic failure but was mistakenly labeled 'support'
        claim = "Multi-agent communication suffered from error propagation, increasing token costs by 400% with lower accuracy."
        calibrated = _verify_and_calibrate_stance("support", claim, [])
        self.assertEqual(calibrated, "counter")

        # A finding that reports pure accuracy gains but was mistakenly labeled 'counter'
        gain_claim = "Multi-agent systems achieved state-of-the-art results, superior to single-agent baselines."
        calibrated_support = _verify_and_calibrate_stance("counter", gain_claim, [])
        self.assertEqual(calibrated_support, "support")

        # Mixed evidence: contains BOTH support indicators and counter/trade-off indicators
        mixed_claim = "Multi-agent systems achieve 84% accuracy outperforming single-agent, but incur high latency overhead and token cost."
        calibrated_mixed = _verify_and_calibrate_stance("support", mixed_claim, [])
        self.assertEqual(calibrated_mixed, "mixed")

    def test_location_in_source_inference(self):
        from search_agent.evidence_extractor import _infer_location_in_source
        source_text = "Section 3.2 Evaluation Results: On the GSM8K benchmark, the multi-agent system achieved 84.2% accuracy."
        loc = _infer_location_in_source("multi-agent system achieved 84.2%", source_text)
        self.assertIn("Section 3.2", loc)

    def test_quantitative_grounding_and_autocomputation(self):
        source_text = "The multi-agent system achieved 84.2% accuracy on GSM8K compared to the single-agent baseline of 78.5%."
        # Valid grounded record
        valid_q = {
            "baseline_score": 78.5,
            "experimental_score": 84.2,
            "absolute_difference": None,
            "relative_difference": None
        }
        grounded = _verify_quantitative_grounding(valid_q, source_text)
        self.assertEqual(grounded["baseline_score"], 78.5)
        self.assertEqual(grounded["experimental_score"], 84.2)
        self.assertEqual(grounded["absolute_difference"], 5.7)
        self.assertEqual(grounded["relative_difference"], 7.26)

        # Hallucinated record with numbers absent in source text
        hallucinated_q = {
            "baseline_score": 99.9,  # Absent in source text
            "experimental_score": 84.2,
            "absolute_difference": 15.7
        }
        sanitized = _verify_quantitative_grounding(hallucinated_q, source_text)
        self.assertIsNone(sanitized["baseline_score"])

    def test_source_type_normalization_and_sufficiency(self):
        # Planner policy types
        self.assertTrue(is_primary_source_type("peer-reviewed conference paper"))
        self.assertTrue(is_primary_source_type("peer-reviewed journal article"))
        self.assertTrue(is_primary_source_type("archival preprint from reputable institution"))
        self.assertTrue(is_primary_source_type("official technical report"))
        self.assertTrue(is_primary_source_type("systematic literature review"))
        self.assertTrue(is_primary_source_type("academic"))
        self.assertTrue(is_primary_source_type("journal_article"))
        self.assertTrue(is_primary_source_type("proceedings_article"))
        self.assertFalse(is_primary_source_type("corporate_blog"))

        self.assertTrue(is_peer_reviewed_type("peer-reviewed conference paper"))
        self.assertTrue(is_peer_reviewed_type("peer-reviewed journal article"))
        self.assertTrue(is_peer_reviewed_type("journal_article"))
        self.assertTrue(is_peer_reviewed_type("proceedings_article"))
        self.assertFalse(is_peer_reviewed_type("archival preprint from reputable institution"))
        self.assertFalse(is_peer_reviewed_type("official technical report"))

        # Sufficiency evaluation with Planner source types
        question = {
            "id": "Q1",
            "source_requirements": {
                "minimum_sources": 2,
                "minimum_primary_sources": 2,
                "minimum_peer_reviewed": 1
            }
        }
        selection_bundle = {
            "per_question_selection": {
                "Q1": {
                    "selected_sources": [
                        ({"source_type": "peer-reviewed conference paper", "content_status": "full"}, "top_ranked"),
                        ({"source_type": "journal_article", "content_status": "full"}, "top_ranked")
                    ]
                }
            }
        }
        findings = [{"stance": "support", "quantitative_evidence": []}]
        res = evaluate_evidence_sufficiency(question, findings, selection_bundle)
        self.assertEqual(res["primary_source_count"], 2)
        self.assertEqual(res["peer_reviewed_count"], 2)
        self.assertTrue(res["sufficient"])

    def test_difference_number_not_hallucinated_as_zero_baseline(self):
        source_text = "The study found that accuracy improved by 4.8 percentage points on the MATH dataset."
        # If extraction mistakenly set baseline_score to 0.0 because it saw a difference of 4.8
        bogus_diff_q = {
            "baseline_score": 0.0,
            "experimental_score": 4.8,
            "absolute_difference": 4.8
        }
        sanitized = _verify_quantitative_grounding(bogus_diff_q, source_text)
        # Baseline 0.0 was never in source text; should be sanitized to None!
        self.assertIsNone(sanitized["baseline_score"])
        self.assertEqual(sanitized["absolute_difference"], 4.8)


class TestDimensionalContradictionsAndDiversity(unittest.TestCase):

    def test_dimensional_contradiction_detection(self):
        findings = [
            {
                "question_id": "Q1",
                "claim": "Multi-agent debate improves math accuracy on GSM8K benchmark.",
                "stance": "support",
                "quantitative_evidence": [{"model": "GPT-4", "dataset": "GSM8K", "task": "Math Reasoning"}]
            },
            {
                "question_id": "Q1",
                "claim": "Single-agent systems outperform multi-agent systems on HumanEval due to communication overhead.",
                "stance": "counter",
                "quantitative_evidence": [{"model": "LLaMA-3", "dataset": "HumanEval", "task": "Code Generation"}]
            }
        ]
        contradictions = detect_empirical_contradictions(findings)
        self.assertEqual(len(contradictions), 1)
        c = contradictions[0]
        self.assertIn("GSM8K", c["dimensions"]["support_datasets"])
        self.assertIn("HumanEval", c["dimensions"]["counter_datasets"])
        self.assertIn("GPT-4", c["dimensions"]["support_models"])
        self.assertIn("benchmarks", c["description"])

    def test_evidence_diversity_calculation(self):
        sources = [
            {"venue": "ICLR 2024", "publication_year": 2024},
            {"venue": "NeurIPS 2023", "publication_year": 2023},
            {"venue": "ACL 2024", "publication_year": 2024}
        ]
        findings = [
            {"quantitative_evidence": [{"model": "GPT-4", "dataset": "GSM8K"}]},
            {"quantitative_evidence": [{"model": "Claude 3", "dataset": "MATH"}]}
        ]
        diversity = calculate_evidence_diversity(sources, findings)
        self.assertGreater(diversity["diversity_score"], 0.70)
        self.assertEqual(len(diversity["unique_venues"]), 3)
        self.assertEqual(len(diversity["unique_models"]), 2)
        self.assertEqual(len(diversity["unique_benchmarks"]), 2)


class TestTargetedReSearchQueries(unittest.TestCase):

    def test_agent_targeted_queries_generated(self):
        question = {
            "id": "Q1",
            "question": "How do multi-agent LLM systems compare to single-agent systems?",
            "type": "comparison"
        }
        queries = generate_targeted_queries(question, ["quantitative_evidence", "counter_evidence"])
        self.assertGreaterEqual(len(queries), 2)
        query_texts = " ".join(q["query_text"] for q in queries)
        self.assertIn("multi-agent", query_texts.lower())
        self.assertIn("counter", [q["query_type"] for q in queries])


class TestAtomicDecompositionAndGlobalRouting(unittest.TestCase):

    def test_atomic_finding_decomposition(self):
        compound_finding = {
            "claim": "Multi-agent systems achieve 84% accuracy outperforming single-agent, but incur high latency overhead and token cost.",
            "evidence": [{"evidence_text": "Accuracy reached 84% on GSM8K, but token cost grew by 400% with high latency."}],
            "quantitative_evidence": [
                {"metric": "Accuracy", "experimental_score": 84.0, "baseline_score": 78.0},
                {"metric": "Token Cost Overhead", "absolute_difference": 400.0}
            ],
            "stance": "mixed"
        }
        decomposed = _decompose_complex_finding(compound_finding)
        self.assertEqual(len(decomposed), 2)
        f1, f2 = decomposed[0], decomposed[1]

        # First atomic finding is performance gain
        self.assertEqual(f1["stance"], "support")
        self.assertEqual(f1["atomic_type"], "performance")
        self.assertIn("accuracy", f1["claim"].lower())

        # Second atomic finding is latency/cost trade-off
        self.assertEqual(f2["stance"], "counter")
        self.assertEqual(f2["atomic_type"], "overhead_or_limitation")
        self.assertIn("latency", f2["claim"].lower())

    def test_global_multi_question_evidence_routing(self):
        # Mock research plan with Q1 (accuracy) and Q3 (latency/overhead)
        plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "What benchmarks demonstrate accuracy of multi-agent LLM systems?",
                    "type": "performance"
                },
                {
                    "id": "Q3",
                    "question": "How do computational overhead, latency, and API costs compare between multi-agent and single-agent systems?",
                    "type": "comparison"
                }
            ]
        }
        # S1 was selected ONLY for Q1, not Q3
        selection_bundle = {
            "per_question_selection": {
                "Q1": {
                    "selected_sources": [
                        (
                            {
                                "source_id": "S1",
                                "title": "Empirical Multi-Agent Benchmarks",
                                "content": "Section 4. Latency Analysis: Multi-agent execution increases token consumption by 350% and latency overhead."
                            },
                            "top_ranked"
                        )
                    ]
                },
                "Q3": {
                    "selected_sources": []
                }
            },
            "unique_selected_sources": []
        }

        class MockResponse:
            text = json.dumps({
                "findings": [
                    {
                        "claim": "Multi-agent execution increases token consumption by 350% and latency overhead compared to single-agent runs.",
                        "stance": "counter",
                        "confidence": "high",
                        "evidence": [
                            {"evidence_text": "Multi-agent execution increases token consumption by 350% and latency overhead.", "location_in_source": "Section 4"}
                        ],
                        "quantitative_evidence": [
                            {"metric": "token overhead", "absolute_difference": 350.0, "location_in_source": "Section 4"}
                        ]
                    }
                ]
            })

        class MockGeminiClient:
            class models:
                @staticmethod
                def generate_content(*args, **kwargs):
                    return MockResponse()

        result = extract_research_evidence(MockGeminiClient(), plan, selection_bundle)
        q3_result = next(q for q in result["questions"] if q["question_id"] == "Q3")
        # Q3 should have received the routed finding even though S1 was only selected for Q1!
        self.assertGreaterEqual(len(q3_result["findings"]), 1)
        routed_f = q3_result["findings"][0]
        self.assertEqual(routed_f["question_id"], "Q3")
        self.assertEqual(routed_f.get("routed_from_question"), "Q1")



class TestPhase2RedIssuesHardening(unittest.TestCase):

    def test_sufficiency_requires_distinct_sources(self):
        """
        Verify that evidence sufficiency cannot be faked by multiple findings
        from a single paper when minimum_quantitative_sources requires multiple independent sources.
        """
        question = {
            "id": "Q1",
            "question": "How do multi-agent LLM systems compare quantitatively?",
            "requires_quantitative_evidence": True,
            "source_requirements": {
                "minimum_sources": 2,
                "minimum_quantitative_sources": 2
            }
        }
        selection_bundle = {
            "per_question_selection": {
                "Q1": {
                    "selected_sources": [
                        ({"source_id": "S1", "content_status": "full", "source_type": "academic"}, "top"),
                        ({"source_id": "S2", "content_status": "full", "source_type": "academic"}, "top")
                    ]
                }
            }
        }

        # 4 quantitative findings, but ALL from source S1
        single_source_findings = [
            {
                "finding_id": f"Q1-F{i}",
                "source_ids": ["S1"],
                "claim": f"Multi-agent benchmark result {i}",
                "stance": "support",
                "quantitative_evidence": [{"metric": "Accuracy", "experimental_score": 80.0 + i}]
            }
            for i in range(1, 5)
        ]

        result = evaluate_evidence_sufficiency(question, single_source_findings, selection_bundle)
        self.assertFalse(result["sufficient"])
        self.assertEqual(result["quantitative_count"], 4)
        self.assertEqual(result["quantitative_source_count"], 1)
        self.assertIn("quantitative_evidence", result["missing_requirements"])

        # Now add finding from an independent source S2
        two_source_findings = list(single_source_findings) + [
            {
                "finding_id": "Q1-F5",
                "source_ids": ["S2"],
                "claim": "Independent replication benchmark result",
                "stance": "support",
                "quantitative_evidence": [{"metric": "Accuracy", "experimental_score": 85.0}]
            }
        ]

        result_satisfied = evaluate_evidence_sufficiency(question, two_source_findings, selection_bundle)
        self.assertTrue(result_satisfied["sufficient"])
        self.assertEqual(result_satisfied["quantitative_source_count"], 2)
        self.assertNotIn("quantitative_evidence", result_satisfied["missing_requirements"])

    def test_strict_variable_gated_relevance(self):
        """
        Verify strict question-specific validation:
        - Pure accuracy claims rejected for latency/cost questions.
        - Failure/bottleneck claims accepted for limitation questions.
        - Boundary/modularity claims accepted for boundary condition questions.
        """
        q_latency = {
            "id": "Q3",
            "question": "What are the computational overheads, token costs, and latency penalties in multi-agent architectures?",
            "type": "comparison"
        }
        q_failure = {
            "id": "Q2",
            "question": "What are the primary failure modes, error propagation bottlenecks, and cascading hallucinations in multi-agent systems?",
            "type": "limitations"
        }
        q_boundary = {
            "id": "Q4",
            "question": "Under what boundary conditions, task complexity thresholds, and coordination topologies do multi-agent systems fail to provide benefits?",
            "type": "boundary_conditions"
        }

        # Pure accuracy claim without cost/overhead indicators
        accuracy_claim = "Multi-agent debate improves GSM8K accuracy from 78% to 85% on mathematical reasoning."
        self.assertFalse(_validate_finding_for_question(accuracy_claim, [], q_latency))

        # Overhead claim with latency and token indicators
        overhead_claim = "Multi-agent coordination incurs 3.5x token cost overhead and 450ms additional inference latency."
        self.assertTrue(_validate_finding_for_question(overhead_claim, [], q_latency))

        # Failure mode claim
        failure_claim = "Cascading error propagation occurs when early agent hallucination misleads downstream debate consensus."
        self.assertTrue(_validate_finding_for_question(failure_claim, [], q_failure))

        # Boundary condition claim
        boundary_claim = "For simple sequential tasks, centralized hierarchical topology degrades performance relative to modular single-agent prompting."
        self.assertTrue(_validate_finding_for_question(boundary_claim, [], q_boundary))

    def test_directional_stance_resolution_across_topics(self):
        """
        Verify topic-invariant directional stance classification across diverse research topics.
        """
        # Topic: RAG hallucination reduction -> support
        rag_support = "The hybrid retrieval-augmented generation framework reduces hallucination by 42% on biomedical QA."
        self.assertEqual(_verify_and_calibrate_stance("context", rag_support, []), "support")

        # Topic: Retrieval noise failure -> counter
        noise_counter = "Retrieval noise and distractor passages degrade reasoning accuracy and increase error rates compared to standard prompting."
        self.assertEqual(_verify_and_calibrate_stance("context", noise_counter, []), "counter")

        # Topic: Normalized compute parity -> counter
        parity_counter = "Under equivalent compute budgets, standard prompting matches multi-agent accuracy across all tested benchmarks."
        self.assertEqual(_verify_and_calibrate_stance("context", parity_counter, []), "counter")

        # Topic: Mixed trade-off (accuracy vs latency/overhead) -> mixed
        tradeoff_mixed = "Collaborative multi-agent debate achieves superior accuracy on complex tasks, but at the expense of 4x token overhead and latency penalties."
        self.assertEqual(_verify_and_calibrate_stance("support", tradeoff_mixed, []), "mixed")

    def test_multiplier_and_range_parsing(self):
        """
        Verify native extraction and grounding of multipliers ('3.5x', '65-fold')
        and performance ranges ('[64.3, 71.4]%') without synthesizing zero baselines.
        """
        source_text = "The multi-agent system incurred 3.5x token overhead and 65-fold communication complexity. Gains ranged from 64.3% to 71.4%."

        # Grounded multiplier record
        mult_record = {
            "multiplier": "3.5x",
            "baseline_score": None,
            "experimental_score": None,
            "absolute_difference": None
        }
        verified_mult = _verify_quantitative_grounding(mult_record, source_text)
        self.assertEqual(verified_mult["multiplier"], "3.5x")
        self.assertIsNone(verified_mult["baseline_score"])

        # Grounded range record
        range_record = {
            "range_min": 64.3,
            "range_max": 71.4,
            "baseline_score": None,
            "experimental_score": None
        }
        verified_range = _verify_quantitative_grounding(range_record, source_text)
        self.assertEqual(verified_range["range_min"], 64.3)
        self.assertEqual(verified_range["range_max"], 71.4)
        self.assertIsNone(verified_range["baseline_score"])

        # Hallucinated multiplier absent in source
        hallucinated_mult = {
            "multiplier": "99.9x"
        }
        verified_hallucinated = _verify_quantitative_grounding(hallucinated_mult, source_text)
        self.assertIsNone(verified_hallucinated["multiplier"])


if __name__ == "__main__":
    unittest.main()


