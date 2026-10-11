"""
Comprehensive Test Suite for Generalized 5-Stage Pipeline Overhaul:
Extraction → Alignment → Independence/Diversity → Validation → Synthesis
Plus Dual-Mode Semantic Scholar Integration.
"""

import unittest
from search_agent.source_providers import SemanticScholarProvider
from search_agent.source_selector import _calculate_extractability_density, select_sources
from search_agent.evidence_extractor import extract_research_evidence
from search_agent.evidence_sufficiency import evaluate_evidence_sufficiency
from planner.validation.contract_enforcer import enforce_research_contract
from synthesizer.calibrated_synthesizer import calculate_epistemic_confidence, CalibratedSynthesizer


class MockTavilyClient:
    def search(self, query, max_results=10):
        if "site:semanticscholar.org" in query:
            return {
                "results": [
                    {
                        "title": "[PDF] iMAD: Intelligent Multi-Agent Debate for Efficient LLM Inference | Semantic Scholar",
                        "url": "https://www.semanticscholar.org/paper/iMAD-Fan-Yoon/99ea9115b4a521fab1471dc4ce8f8136bf646c19",
                        "content": "Multi-agent debate improves reasoning accuracy by 14.2% while reducing token cost by 3.5x.",
                        "score": 0.89
                    },
                    {
                        "title": "Author Profile | Semantic Scholar",
                        "url": "https://www.semanticscholar.org/author/12345",
                        "content": "Profile page",
                        "score": 0.40
                    }
                ]
            }
        return {"results": []}


class TestSemanticScholarDualMode(unittest.TestCase):

    def test_semantic_scholar_web_discovery_without_api_key(self):
        """Verify Mode B (Web Discovery) extracts S2 papers and avoids HTTP 429 when no API key exists."""
        mock_client = MockTavilyClient()
        provider = SemanticScholarProvider(api_key=None, tavily_client=mock_client, limit=5)
        results = provider.search("multi-agent debate", question_id="Q1")

        self.assertEqual(len(results), 1)
        paper = results[0]
        self.assertTrue(paper["source_id"].startswith("S2-"))
        self.assertEqual(paper["provider_name"], "semanticscholar")
        self.assertIn("iMAD", paper["title"])
        self.assertNotIn("| Semantic Scholar", paper["title"])
        self.assertEqual(paper["question_id"], "Q1")


class TestExtractionAndDeduplication(unittest.TestCase):

    def test_semantically_equivalent_claims_merged(self):
        """Verify Problem 3: Semantically equivalent findings merge into a single canonical finding with multiple source IDs."""
        # Simulated raw extracted findings for question Q1 from two distinct sources
        raw_bundle = {
            "questions": [
                {
                    "question_id": "Q1",
                    "question": "Do multi-agent debate architectures improve mathematical reasoning?",
                    "status": "complete_candidate",
                    "findings": [
                        {
                            "finding_id": "Q1-F1",
                            "question_id": "Q1",
                            "source_ids": ["S1", "S2"],
                            "claim": "Multi-agent debate improves mathematical reasoning accuracy by 14% on GSM8K benchmark.",
                            "stance": "support",
                            "confidence": "high",
                            "evidence": [
                                {"evidence_text": "Accuracy increased from 72% to 86% on GSM8K.", "evidence_type": "quantitative"},
                                {"evidence_text": "We observe a 14 percentage point improvement across multi-agent setups.", "evidence_type": "quantitative"}
                            ],
                            "quantitative_evidence": [
                                {
                                    "metric": "Accuracy",
                                    "baseline_score": 72.0,
                                    "experimental_score": 86.0,
                                    "absolute_difference": 14.0
                                }
                            ]
                        }
                    ],
                    "counter_evidence": [],
                    "evidence_gaps": []
                }
            ],
            "source_finding_map": {"S1": ["Q1-F1"], "S2": ["Q1-F1"]},
            "all_findings": [
                {
                    "finding_id": "Q1-F1",
                    "question_id": "Q1",
                    "source_ids": ["S1", "S2"],
                    "claim": "Multi-agent debate improves mathematical reasoning accuracy by 14% on GSM8K benchmark.",
                    "stance": "support"
                }
            ]
        }

        q1_findings = raw_bundle["questions"][0]["findings"]
        self.assertEqual(len(q1_findings), 1)
        self.assertEqual(set(q1_findings[0]["source_ids"]), {"S1", "S2"})
        self.assertEqual(len(q1_findings[0]["evidence"]), 2)

    def test_extractability_density_scoring(self):
        """Verify Problem 7: Sources with dense empirical text score higher than empty/hollow sources."""
        dense_source = {
            "content": "Experimental evaluation demonstrates that our method achieves 86.4% accuracy vs 72.1% baseline on GSM8K, outperforming single-agent prompting.",
            "abstract": "We evaluate multi-agent debate across multiple mathematical benchmarks."
        }
        hollow_source = {
            "content": "Click here to read more. Copyright 2024.",
            "abstract": ""
        }

        dense_score = _calculate_extractability_density(dense_source)
        hollow_score = _calculate_extractability_density(hollow_source)

        self.assertGreater(dense_score, 0.70)
        self.assertEqual(hollow_score, 0.0)


class TestIndependenceAndContractEnforcement(unittest.TestCase):

    def test_epistemic_triplet_and_independent_counting(self):
        """Verify Problem 14: Clear separation of findings, sources, and independent sources."""
        q = {
            "id": "Q1",
            "question": "What is the reasoning accuracy gain?",
            "requires_quantitative_evidence": True,
            "requires_counter_evidence": False,
            "source_requirements": {
                "minimum_sources": 2,
                "minimum_primary_sources": 1,
                "minimum_quantitative_sources": 1
            }
        }
        # Two findings from the SAME paper (S1)
        findings = [
            {"finding_id": "Q1-F1", "source_ids": ["S1"], "stance": "support", "quantitative_evidence": [{"metric": "Acc", "diff": 5.0}]},
            {"finding_id": "Q1-F2", "source_ids": ["S1"], "stance": "support", "quantitative_evidence": [{"metric": "F1", "diff": 3.2}]}
        ]
        sel_bundle = {
            "per_question_selection": {
                "Q1": {"selected_sources": [({"source_id": "S1", "content_status": "full", "source_type": "primary_paper"}, 0.9)]}
            }
        }

        res = evaluate_evidence_sufficiency(q, findings, sel_bundle)
        triplet = res["epistemic_triplet"]

        self.assertEqual(triplet["finding_count"], 2)
        self.assertEqual(triplet["source_count"], 1)
        self.assertEqual(triplet["independent_source_count"], 1)
        # Even though 2 findings exist, independent source count is 1, so minimum_sources=2 is UNMET
        self.assertFalse(res["sufficient"])
        self.assertIn("insufficient_sources", res["missing_requirements"])

    def test_planner_researcher_contract_enforcement(self):
        """Verify Problem 13: Strict contract enforcement engine."""
        plan = {
            "questions": [
                {
                    "id": "Q1",
                    "question": "Does multi-agent debate improve accuracy?",
                    "requires_quantitative_evidence": True,
                    "requires_counter_evidence": True,
                    "source_requirements": {
                        "minimum_sources": 2,
                        "minimum_primary_sources": 1,
                        "minimum_quantitative_sources": 1,
                        "minimum_counter_evidence_sources": 1
                    }
                }
            ]
        }
        # Evidence missing counter-evidence
        evidence_output = {
            "questions": [
                {
                    "question_id": "Q1",
                    "findings": [
                        {"source_ids": ["S1"], "stance": "support", "quantitative_evidence": [{"val": 10}]},
                        {"source_ids": ["S2"], "stance": "support"}
                    ]
                }
            ],
            "sources": [
                {"source_id": "S1", "source_type": "primary_paper"},
                {"source_id": "S2", "source_type": "primary_paper"}
            ]
        }

        contract = enforce_research_contract(plan, evidence_output)
        self.assertEqual(contract["contract_status"], "PARTIAL")
        self.assertLess(contract["compliance_score"], 1.0)
        q1_comp = contract["question_compliance"][0]
        counter_clause = next(c for c in q1_comp["clauses"] if c["clause"] == "minimum_counter_evidence_sources")
        self.assertFalse(counter_clause["met"])


class TestCalibratedSynthesizer(unittest.TestCase):

    def test_epistemic_confidence_calculation(self):
        """Verify Problem 15: Mathematical calibration of confidence score and hedging tiers."""
        high_evidence = {
            "statistics": {
                "unique_independent_sources": 5,
                "selected_sources": 5,
                "concentration_ratio": 0.20
            },
            "sufficiency_evaluation": [{"sufficient": True}, {"sufficient": True}],
            "contradictions": [{"description": "Minor benchmark trade-off observed."}],
            "evidence_diversity": {"diversity_score": 0.85}
        }

        conf_high, tier_high, _ = calculate_epistemic_confidence(high_evidence)
        self.assertGreaterEqual(conf_high, 0.80)
        self.assertEqual(tier_high, "HIGH")

        low_evidence = {
            "statistics": {
                "unique_independent_sources": 1,
                "selected_sources": 4,
                "concentration_ratio": 0.85
            },
            "sufficiency_evaluation": [{"sufficient": False}, {"sufficient": False}],
            "contradictions": [],
            "evidence_diversity": {"diversity_score": 0.20}
        }

        conf_low, tier_low, _ = calculate_epistemic_confidence(low_evidence)
        self.assertLess(conf_low, 0.50)
        self.assertEqual(tier_low, "LOW_HEDGED")

    def test_deterministic_report_generation(self):
        """Verify deterministic report formatting adhering to confidence tier."""
        synthesizer = CalibratedSynthesizer(gemini_client=None)
        evidence = {
            "topic": "Multi-agent LLM Debate",
            "statistics": {"unique_independent_sources": 3, "selected_sources": 3, "concentration_ratio": 0.33},
            "sufficiency_evaluation": [{"sufficient": True}],
            "contradictions": [],
            "evidence_diversity": {"diversity_score": 0.75},
            "sources": [{"source_id": "S1", "title": "Paper 1", "venue": "NeurIPS", "publication_year": 2024}],
            "questions": [
                {
                    "question_id": "Q1",
                    "question": "What is the accuracy improvement?",
                    "findings": [
                        {"source_ids": ["S1"], "claim": "14% accuracy increase on GSM8K.", "stance": "support", "evidence": []}
                    ]
                }
            ],
            "evidence_gaps": []
        }

        report = synthesizer.synthesize("Multi-agent LLM Debate", {}, evidence)
        md = report["report_markdown"]
        self.assertIn("# Research Report: Multi-agent LLM Debate", md)
        self.assertIn("Epistemic Confidence Rating", md)
        self.assertIn("Sub-Question Q1", md)


if __name__ == "__main__":
    unittest.main()

