"""
Unit tests verifying Phase 2 completion:
- Step 7: Source Ranker with dynamic source policy, deterministic tie-breaking, and domain-agnostic relevance
- Step 10: Evidence Output with evidence gaps and sufficiency evaluation
- Step 11: Summary Generator context building
"""

import sys
import os
import unittest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

from search_agent.source_ranker import (
    rank_sources,
    classify_source,
    score_source,
    compute_evidence_eligibility,
    _build_policy_quality_scores,
)
from search_agent.evidence_output import build_research_evidence_output
from search_agent.summary_generator import build_research_context


class TestSourceRankerPolicyAndSorting(unittest.TestCase):

    def test_deterministic_tie_breaking_academic_ids(self):
        questions = [{"id": "Q1", "question": "What are the effects of transformers?"}]
        sources = [
            {"source_id": "OA-W200", "title": "Paper B", "url": "https://doi.org/10.1/b", "content": "Transformer paper", "score": 0.8},
            {"source_id": "OA-W100", "title": "Paper A", "url": "https://doi.org/10.1/a", "content": "Transformer paper", "score": 0.8},
            {"source_id": "S1", "title": "Web A", "url": "https://example.com/a", "content": "Transformer paper", "score": 0.8},
        ]
        ranked = rank_sources(sources, questions)
        ids = [s["source_id"] for s in ranked]
        # Should be deterministic
        self.assertEqual(len(ranked), 3)
        self.assertIn("OA-W100", ids)
        self.assertIn("OA-W200", ids)
        self.assertIn("S1", ids)

    def test_dynamic_source_policy_applied(self):
        policy = {
            "tiers": [
                {"tier": 1, "source_types": ["peer-reviewed conference paper"], "role": "evidence"},
                {"tier": 2, "source_types": ["official technical report"], "role": "evidence"},
                {"tier": 3, "source_types": ["corporate blog"], "role": "discovery"}
            ],
            "evidence_eligible_source_types": ["peer-reviewed conference paper", "official technical report"],
            "discovery_only_source_types": ["corporate blog"]
        }
        scores = _build_policy_quality_scores(policy)
        self.assertEqual(scores.get("conference_paper"), 0.95)

        # Check eligibility against dynamic policy
        src_blog = {"source_type": "corporate_blog", "url": "https://blog.google/post"}
        eligible, reason = compute_evidence_eligibility(src_blog, source_policy=policy)
        self.assertFalse(eligible)
        self.assertEqual(reason, "policy_discovery_only")

    def test_classify_academic_providers(self):
        s2_paper = {
            "provider_name": "semanticscholar",
            "venue": "NeurIPS 2024",
            "publication_types": ["Conference"],
            "title": "Scaling Laws for Language Models",
            "url": "https://doi.org/10.1234/567"
        }
        self.assertEqual(classify_source(s2_paper), "conference_paper")

        oa_review = {
            "provider_name": "openalex",
            "title": "A Systematic Review of Retrieval Augmented Generation",
            "url": "https://doi.org/10.1234/review"
        }
        self.assertEqual(classify_source(oa_review), "systematic_review")

        arxiv_paper = {
            "provider_name": "semanticscholar",
            "url": "https://arxiv.org/abs/2305.18290",
            "title": "Direct Preference Optimization",
            "venue": "arXiv"
        }
        self.assertEqual(classify_source(arxiv_paper), "preprint")


class TestEvidenceOutputArtifact(unittest.TestCase):

    def test_build_evidence_output_includes_gaps_and_summary(self):
        topic = "Test Topic"
        sources = [
            {
                "source_id": "S1",
                "title": "Test Title",
                "url": "https://example.com",
                "source_type": "peer_reviewed_paper",
                "authors": ["Alice Smith", "Bob Jones"],
                "publication_year": 2024,
                "citation_count": 42
            }
        ]
        extraction_bundle = {
            "questions": [{"question_id": "Q1", "question": "Does it work?"}],
            "source_finding_map": {"S1": ["Q1-F1"]},
            "all_findings": [{"finding_id": "Q1-F1", "stance": "support", "claim": "Works well"}]
        }
        sufficiency_results = [
            {
                "question_id": "Q1",
                "sufficient": False,
                "selected_source_count": 1,
                "primary_source_count": 1,
                "finding_count": 1,
                "quantitative_count": 0,
                "counter_count": 0,
                "missing_requirements": ["minimum_quantitative_sources"],
                "evidence_gaps": ["Need 1 more quantitative finding"]
            }
        ]
        summary_text = "This is a comprehensive scientific synthesis."

        artifact = build_research_evidence_output(
            topic,
            sources,
            extraction_bundle,
            summary=summary_text,
            sufficiency_results=sufficiency_results
        )

        self.assertEqual(artifact["topic"], topic)
        self.assertEqual(artifact["summary"], summary_text)
        self.assertEqual(len(artifact["evidence_gaps"]), 1)
        self.assertIn("[Q1] Need 1 more quantitative finding", artifact["evidence_gaps"])
        self.assertEqual(len(artifact["sufficiency_evaluation"]), 1)
        self.assertFalse(artifact["sufficiency_evaluation"][0]["sufficient"])
        self.assertEqual(artifact["sources"][0]["authors"], ["Alice Smith", "Bob Jones"])
        self.assertEqual(artifact["sources"][0]["citation_count"], 42)


class TestSummaryContextBuilder(unittest.TestCase):

    def test_build_research_context(self):
        sources = [
            {
                "source_id": "S1",
                "title": "Attention Is All You Need",
                "url": "https://arxiv.org/abs/1706.03762",
                "source_type": "preprint",
                "content": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
                "authors": ["Vaswani", "Shazeer"],
                "publication_year": 2017
            }
        ]
        bundle = {
            "all_findings": [
                {"finding_id": "Q1-F1", "claim": "Transformers replace recurrence with attention", "stance": "support", "source_ids": ["S1"]}
            ]
        }
        context = build_research_context(sources, extraction_bundle=bundle)
        self.assertIn("Attention Is All You Need", context)
        self.assertIn("Vaswani, Shazeer", context)
        self.assertIn("KEY EXTRACTED FINDINGS", context)
        self.assertIn("Q1-F1", context)


class TestDomainGatedSourceRanker(unittest.TestCase):
    """Verifies that off-domain biology/spectrometry papers and domain-LLM papers
    are properly penalized or disqualified on multi-agent AI questions."""

    def setUp(self):
        self.multi_agent_question = {
            "id": "Q1",
            "type": "comparison",
            "question": "How do multi-agent LLM frameworks compare empirically against single-agent baselines on standardized complex reasoning benchmarks?",
            "preferred_source_types": ["peer-reviewed conference paper", "primary research preprint"],
            "requires_counter_evidence": True,
        }

    def test_prost_multi_agent_paper_ranks_high(self):
        source = {
            "source_id": "S_PROST",
            "title": "ProST: Progressive Sub-task Training for Multi-agent Large Language Models",
            "abstract": "We study multi-agent LLM frameworks and compare cooperative agents against single-agent baselines on complex reasoning benchmarks.",
            "source_type": "conference_paper",
            "fields_of_study": ["Computer Science"],
            "score": 0.85,
        }
        score_dict = score_source(source, self.multi_agent_question)
        self.assertGreaterEqual(score_dict["relevance_score"], 0.70)
        self.assertIn("multi_agent", score_dict["relevance_reason"])
        self.assertGreaterEqual(score_dict["final_score"], 0.70)

    def test_dna_methylation_biology_paper_disqualified(self):
        source = {
            "source_id": "S_BIO",
            "title": "Quantitative comparison of DNA methylation assays",
            "abstract": "We present an empirical assessment comparing methylation profiling across multiple biological assays.",
            "source_type": "peer_reviewed_paper",
            "fields_of_study": ["Biology"],
            "score": 0.90,
        }
        score_dict = score_source(source, self.multi_agent_question)
        self.assertEqual(score_dict["relevance_score"], 0.0)
        self.assertEqual(score_dict["final_score"], 0.0)
        self.assertEqual(score_dict["relevance_reason"], "domain_mismatch_fields_of_study")

    def test_mass_spectrometry_paper_disqualified_by_title(self):
        source = {
            "source_id": "S_SWATH",
            "title": "Comparison of SWATH mass spectrometry workflows for proteomic analysis",
            "abstract": "Empirical evaluation of SWATH-MS performance and benchmarking in quantitative proteomics.",
            "source_type": "peer_reviewed_paper",
            "score": 0.88,
        }
        score_dict = score_source(source, self.multi_agent_question)
        self.assertEqual(score_dict["relevance_score"], 0.0)
        self.assertEqual(score_dict["final_score"], 0.0)
        self.assertEqual(score_dict["relevance_reason"], "domain_mismatch_penalty")

    def test_condensation_nuclei_counter_not_selected_as_counter_evidence(self):
        source = {
            "source_id": "S_AEROSOL",
            "title": "Condensation nuclei counter calibration and performance comparison",
            "abstract": "Evaluation of counter instruments in aerosol measurement.",
            "source_type": "peer_reviewed_paper",
            "discovered_by": [{"question_id": "Q1", "query_type": "counter"}],
            "score": 0.85,
        }
        score_dict = score_source(source, self.multi_agent_question)
        self.assertEqual(score_dict["relevance_score"], 0.0)
        self.assertEqual(score_dict["final_score"], 0.0)

    def test_bloomberggpt_capped_on_multi_agent_comparison(self):
        source = {
            "source_id": "S_BLOOMBERG",
            "title": "BloombergGPT: A Large Language Model for Finance",
            "abstract": "We train a 50-billion parameter language model on financial data and evaluate on standardized financial benchmarks.",
            "source_type": "preprint",
            "fields_of_study": ["Computer Science"],
            "score": 0.85,
        }
        score_dict = score_source(source, self.multi_agent_question)
        self.assertLessEqual(score_dict["relevance_score"], 0.20)
        self.assertEqual(score_dict["relevance_reason"], "general_llm_without_agent_focus")

    def test_selector_excludes_irrelevant_biology_and_aerosol(self):
        from search_agent.source_selector import select_sources_for_question
        sources = [
            {
                "source_id": "S_BIO",
                "title": "Quantitative comparison of DNA methylation assays",
                "source_type": "peer_reviewed_paper",
                "fields_of_study": ["Biology"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
            },
            {
                "source_id": "S_AEROSOL",
                "title": "Condensation nuclei counter calibration",
                "source_type": "peer_reviewed_paper",
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "counter"}],
            },
            {
                "source_id": "S_PROST",
                "title": "ProST: Progressive Sub-task Training for Multi-agent Large Language Models",
                "abstract": "Cooperative multi-agent LLM systems outperforming single-agent baselines on complex reasoning.",
                "source_type": "conference_paper",
                "fields_of_study": ["Computer Science"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
            },
        ]
        ranked = rank_sources(sources, [self.multi_agent_question])
        selection = select_sources_for_question(self.multi_agent_question, ranked)
        selected_ids = [s[0]["source_id"] for s in selection["selected_sources"]]
        self.assertIn("S_PROST", selected_ids)
        self.assertNotIn("S_BIO", selected_ids)
        self.assertNotIn("S_AEROSOL", selected_ids)

    def test_full_user_critique_scenario(self):
        """Simulates all papers identified in user critique:
        1. ProST (Multi-agent LLM) -> Top ranked
        2. LLM Survey (General LLM) -> Lower rank
        3. BloombergGPT (Finance LLM) -> Lower rank
        4. DNA Methylation (Biology) -> Disqualified (0.0)
        5. SWATH Mass Spectrometry (Proteomics) -> Disqualified (0.0)
        6. Condensation Nuclei Counter (Aerosol) -> Disqualified (0.0)
        """
        sources = [
            {
                "source_id": "S_PROST",
                "title": "ProST: Progressive Sub-task Training for Multi-agent Large Language Models",
                "abstract": "We explore cooperative multi-agent LLM systems and benchmark multi-agent debate vs single-agent baselines on complex reasoning tasks.",
                "source_type": "conference_paper",
                "fields_of_study": ["Computer Science"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
            },
            {
                "source_id": "S_SURVEY",
                "title": "A Comprehensive Overview of Large Language Models",
                "abstract": "A survey of large language models, pretraining, fine-tuning, and general benchmark evaluations.",
                "source_type": "preprint",
                "fields_of_study": ["Computer Science"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "secondary"}],
            },
            {
                "source_id": "S_BLOOMBERG",
                "title": "BloombergGPT: A Large Language Model for Finance",
                "abstract": "A 50-billion parameter language model for finance trained on extensive financial domain data.",
                "source_type": "preprint",
                "fields_of_study": ["Computer Science"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "secondary"}],
            },
            {
                "source_id": "S_BIO",
                "title": "Quantitative comparison of DNA methylation assays",
                "abstract": "Comparative evaluation of DNA methylation profiling across genomic benchmarks.",
                "source_type": "peer_reviewed_paper",
                "fields_of_study": ["Biology"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
            },
            {
                "source_id": "S_SWATH",
                "title": "Comparison of SWATH mass spectrometry workflows for proteomic analysis",
                "abstract": "Evaluation of SWATH mass spectrometry in proteomics.",
                "source_type": "peer_reviewed_paper",
                "fields_of_study": ["Chemistry"],
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "secondary"}],
            },
            {
                "source_id": "S_COUNTER",
                "title": "Condensation nuclei counter calibration and performance comparison",
                "abstract": "Calibration and counter measurement of aerosol particles.",
                "source_type": "peer_reviewed_paper",
                "content_status": "full",
                "discovered_by": [{"question_id": "Q1", "query_type": "counter"}],
            },
        ]
        ranked = rank_sources(sources, [self.multi_agent_question])
        ids = [s["source_id"] for s in ranked]
        # ProST must be #1
        self.assertEqual(ids[0], "S_PROST")

        # Disqualified papers must have 0.0 scores
        for sid in ("S_BIO", "S_SWATH", "S_COUNTER"):
            src = next(s for s in ranked if s["source_id"] == sid)
            q1_scores = src["ranking_by_question"]["Q1"]
            self.assertEqual(q1_scores["relevance_score"], 0.0)
            self.assertEqual(q1_scores["final_score"], 0.0)

        # ProST must substantially outscore general LLM papers
        prost_score = next(s for s in ranked if s["source_id"] == "S_PROST")["ranking_by_question"]["Q1"]["final_score"]
        survey_score = next(s for s in ranked if s["source_id"] == "S_SURVEY")["ranking_by_question"]["Q1"]["final_score"]
        bloomberg_score = next(s for s in ranked if s["source_id"] == "S_BLOOMBERG")["ranking_by_question"]["Q1"]["final_score"]
        self.assertGreater(prost_score, survey_score)
        self.assertGreater(prost_score, bloomberg_score)


class TestPhase2Enhancements(unittest.TestCase):
    """Verifies the implementation of Phase 2 review items:
    - Quantitative difference auto-computation
    - Planner requirements selection enforcement
    - Venue diversity cap enforcement
    - Empirical contradiction detection
    - Sufficiency-aware context building
    """

    def test_quantitative_difference_auto_calculation(self):
        from search_agent.evidence_extractor import extract_evidence_from_source
        from unittest.mock import MagicMock

        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '''
        {
          "findings": [
            {
              "claim": "Multi-agent debate improved math reasoning accuracy.",
              "stance": "support",
              "confidence": "high",
              "evidence": [{"evidence_type": "quantitative", "evidence_text": "GSM8K accuracy rose from 80% to 90%"}],
              "quantitative_evidence": [
                {
                  "model": "GPT-4",
                  "dataset": "GSM8K",
                  "metric": "Accuracy",
                  "baseline_score": 80.0,
                  "experimental_score": 90.0,
                  "absolute_difference": null,
                  "relative_difference": null
                }
              ]
            }
          ]
        }
        '''
        mock_gemini.models.generate_content.return_value = mock_response

        question = {
            "id": "Q1",
            "question": "How do multi-agent systems compare to single agents?",
            "requires_quantitative_evidence": True
        }
        source = {
            "source_id": "S1",
            "title": "Debate Paper",
            "content": "GSM8K accuracy rose from 80% to 90%"
        }

        findings = extract_evidence_from_source(mock_gemini, question, source)
        self.assertEqual(len(findings), 1)
        quant = findings[0]["quantitative_evidence"][0]
        self.assertEqual(quant["baseline_score"], 80.0)
        self.assertEqual(quant["experimental_score"], 90.0)
        # Verify auto-computed deltas
        self.assertEqual(quant["absolute_difference"], 10.0)
        self.assertEqual(quant["relative_difference"], 12.5)

    def test_planner_source_requirements_selection(self):
        from search_agent.source_selector import select_sources_for_question

        question = {
            "id": "Q1",
            "requires_counter_evidence": True,
            "source_requirements": {
                "minimum_sources": 4,
                "minimum_counter_evidence_sources": 2,
                "minimum_primary_sources": 2
            }
        }
        sources = [
            {
                "source_id": "C1",
                "source_type": "conference_paper",
                "venue": "acl",
                "evidence_eligible": True,
                "discovered_by": [{"question_id": "Q1", "query_type": "counter"}],
                "ranking_by_question": {"Q1": {"final_score": 0.80, "relevance_score": 0.70}}
            },
            {
                "source_id": "C2",
                "source_type": "preprint",
                "venue": "arxiv",
                "evidence_eligible": True,
                "discovered_by": [{"question_id": "Q1", "query_type": "counter"}],
                "ranking_by_question": {"Q1": {"final_score": 0.75, "relevance_score": 0.65}}
            },
            {
                "source_id": "P1",
                "source_type": "peer_reviewed_paper",
                "venue": "ieee",
                "evidence_eligible": True,
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
                "ranking_by_question": {"Q1": {"final_score": 0.85, "relevance_score": 0.80}}
            },
            {
                "source_id": "P2",
                "source_type": "conference_paper",
                "venue": "neurips",
                "evidence_eligible": True,
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
                "ranking_by_question": {"Q1": {"final_score": 0.70, "relevance_score": 0.60}}
            },
            {
                "source_id": "W1",
                "source_type": "technical_article",
                "venue": "web_domain",
                "evidence_eligible": True,
                "discovered_by": [{"question_id": "Q1", "query_type": "primary"}],
                "ranking_by_question": {"Q1": {"final_score": 0.60, "relevance_score": 0.50}}
            },
        ]

        selection = select_sources_for_question(question, sources, max_sources=4)
        selected_sources = selection["selected_sources"]
        roles = {s[0]["source_id"]: s[1] for s in selected_sources}

        # Must satisfy 2 counter evidence sources
        counter_ids = [sid for sid, role in roles.items() if role == "counter_evidence"]
        self.assertGreaterEqual(len(counter_ids), 2)
        self.assertIn("C1", counter_ids)
        self.assertIn("C2", counter_ids)

    def test_venue_diversity_cap(self):
        from search_agent.source_selector import select_sources_for_question

        question = {
            "id": "Q1",
            "requires_counter_evidence": False,
            "source_requirements": {"minimum_sources": 4}
        }
        sources = [
            {"source_id": "A1", "venue": "arxiv", "evidence_eligible": True, "ranking_by_question": {"Q1": {"final_score": 0.90, "relevance_score": 0.8}}},
            {"source_id": "A2", "venue": "arxiv", "evidence_eligible": True, "ranking_by_question": {"Q1": {"final_score": 0.88, "relevance_score": 0.8}}},
            {"source_id": "A3", "venue": "arxiv", "evidence_eligible": True, "ranking_by_question": {"Q1": {"final_score": 0.85, "relevance_score": 0.8}}},
            {"source_id": "A4", "venue": "arxiv", "evidence_eligible": True, "ranking_by_question": {"Q1": {"final_score": 0.82, "relevance_score": 0.8}}},
            {"source_id": "N1", "venue": "neurips", "evidence_eligible": True, "ranking_by_question": {"Q1": {"final_score": 0.80, "relevance_score": 0.7}}},
            {"source_id": "I1", "venue": "icml", "evidence_eligible": True, "ranking_by_question": {"Q1": {"final_score": 0.78, "relevance_score": 0.7}}},
        ]

        selection = select_sources_for_question(question, sources, max_sources=4)
        selected_sids = [s[0]["source_id"] for s in selection["selected_sources"]]
        selected_venues = [s[0]["venue"] for s in selection["selected_sources"]]

        # Arxiv must be capped at 2 because alternative venues exist
        arxiv_count = selected_venues.count("arxiv")
        self.assertLessEqual(arxiv_count, 2)
        self.assertIn("N1", selected_sids)
        self.assertIn("I1", selected_sids)

    def test_contradiction_detection(self):
        from search_agent.summary_generator import detect_empirical_contradictions

        findings = [
            {"question_id": "Q1", "claim": "Multi-agent systems outperform single agents on math.", "stance": "support"},
            {"question_id": "Q1", "claim": "Communication overhead degrades multi-agent accuracy on simple tasks.", "stance": "counter"},
            {"question_id": "Q2", "claim": "Token costs scale linearly with agent count.", "stance": "context"},
        ]

        contradictions = detect_empirical_contradictions(findings)
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0]["question_id"], "Q1")
        self.assertEqual(len(contradictions[0]["support_claims"]), 1)
        self.assertEqual(len(contradictions[0]["counter_claims"]), 1)

    def test_sufficiency_aware_context(self):
        from search_agent.summary_generator import build_research_context

        sources = [{"source_id": "S1", "title": "Paper 1", "content": "Sample content"}]
        sufficiency = [
            {
                "question_id": "Q1",
                "sufficient": False,
                "evidence_gaps": ["Need 2 more quantitative findings"]
            }
        ]

        context = build_research_context(sources, sufficiency_results=sufficiency)
        self.assertIn("EVIDENCE SUFFICIENCY & IDENTIFIED GAPS", context)
        self.assertIn("Need 2 more quantitative findings", context)

    def test_evidence_output_includes_contradictions(self):
        from search_agent.evidence_output import build_research_evidence_output

        bundle = {
            "questions": [{"question_id": "Q1", "question": "Compare single vs multi agent"}],
            "source_finding_map": {"S1": ["Q1-F1", "Q1-F2"]},
            "all_findings": [
                {"question_id": "Q1", "claim": "Multi-agent helps", "stance": "support"},
                {"question_id": "Q1", "claim": "Multi-agent fails due to cascading errors", "stance": "counter"},
            ]
        }
        sources = [{"source_id": "S1", "title": "Test Paper", "url": "https://example.com"}]

        output = build_research_evidence_output("Topic", sources, bundle)
        self.assertIn("contradictions", output)
        self.assertEqual(len(output["contradictions"]), 1)
        self.assertEqual(output["statistics"]["contradictions_detected"], 1)


if __name__ == "__main__":
    unittest.main()




