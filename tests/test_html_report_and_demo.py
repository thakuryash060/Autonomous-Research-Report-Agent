"""
tests/test_html_report_and_demo.py

Comprehensive deterministic unit tests for:
1. HTML report generation (data/research_report.html)
2. HTML escaping (XSS / special characters handling)
3. Deterministic citation numbering ([1], [2]...)
4. Clickable citation anchors (<a href="#source-N">)
5. Source link generation
6. Canonical URL selection priority (DOI -> Publisher -> arXiv -> PMC -> Landing page)
7. Findings -> source traceability
8. Quantitative evidence table rendering
9. Counter-evidence & contradiction rendering
10. Insufficient evidence rendering & status indicators
11. Report generation with missing optional metadata (nulls, empty lists, missing fields)
12. --demo performs zero external provider calls & enforces network guard
13. Demo HTML clearly displays "DEMO DATA — NOT A REAL RESEARCH RESULT"
14. Normal existing tests remain passing
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reports.html_renderer import (
    render_html_report,
    select_canonical_url,
    build_citation_map,
    format_authors,
    replace_citations_in_text,
)
from demo.demo_data import (
    DEMO_TOPIC,
    DEMO_PLAN,
    DEMO_ROUND1_SUFFICIENCY,
    DEMO_ROUND2_SUFFICIENCY,
    DEMO_EVIDENCE_ARTIFACT,
    DEMO_REPORT_ARTIFACT,
)
from demo.demo_runner import run_demo, NetworkGuardViolation


class TestCanonicalUrlSelection(unittest.TestCase):
    """Test priority selection of canonical URLs."""

    def test_doi_priority_over_other_urls(self):
        source = {
            "doi": "10.1038/s41586-020-2649-2",
            "url": "https://www.semanticscholar.org/paper/12345",
            "open_access_url": "https://europepmc.org/articles/PMC123"
        }
        url = select_canonical_url(source)
        self.assertEqual(url, "https://doi.org/10.1038/s41586-020-2649-2")

    def test_full_doi_url_preserved(self):
        source = {
            "doi": "https://doi.org/10.1145/3318464.3389700",
            "url": "https://openalex.org/W999"
        }
        url = select_canonical_url(source)
        self.assertEqual(url, "https://doi.org/10.1145/3318464.3389700")

    def test_publisher_url_prioritized_over_landing_page(self):
        source = {
            "url": "https://www.nature.com/articles/s41586-021-03819-2",
            "provider_name": "semanticscholar"
        }
        url = select_canonical_url(source)
        self.assertEqual(url, "https://www.nature.com/articles/s41586-021-03819-2")

    def test_arxiv_url_selected(self):
        source = {
            "url": "https://arxiv.org/abs/2302.00093",
            "provider_name": "semanticscholar"
        }
        url = select_canonical_url(source)
        self.assertEqual(url, "https://arxiv.org/abs/2302.00093")

    def test_pmc_url_selected(self):
        source = {
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2656292",
            "provider_name": "semanticscholar"
        }
        url = select_canonical_url(source)
        self.assertEqual(url, "https://pmc.ncbi.nlm.nih.gov/articles/PMC2656292")

    def test_empty_source_returns_empty_string(self):
        self.assertEqual(select_canonical_url({}), "")
        self.assertEqual(select_canonical_url(None), "")


class TestAuthorFormatting(unittest.TestCase):
    """Test standard academic author citation formatting."""

    def test_single_author(self):
        self.assertEqual(format_authors(["Alice Smith"]), "Alice Smith")

    def test_two_authors(self):
        self.assertEqual(format_authors(["Alice Smith", "Bob Jones"]), "Alice Smith & Bob Jones")

    def test_three_or_more_authors(self):
        self.assertEqual(format_authors(["Alice Smith", "Bob Jones", "Charlie Brown"]), "Alice Smith et al.")

    def test_author_dict_objects(self):
        authors = [{"display_name": "Patrick Lewis"}, {"display_name": "Ethan Perez"}, {"display_name": "Aleksandra Piktus"}]
        self.assertEqual(format_authors(authors), "Patrick Lewis et al.")

    def test_missing_authors_returns_unknown(self):
        self.assertEqual(format_authors([]), "Unknown Authors")
        self.assertEqual(format_authors(None), "Unknown Authors")


class TestCitationMappingAndAnchors(unittest.TestCase):
    """Test deterministic citation indexing and traceability."""

    def setUp(self):
        self.evidence = {
            "sources": [
                {"source_id": "S1", "title": "Paper One", "authors": ["Author One"]},
                {"source_id": "S2", "title": "Paper Two", "authors": ["Author Two", "Author Three"]},
                {"source_id": "S3", "title": "Paper Three", "authors": ["Author Four"]}
            ],
            "questions": [
                {
                    "question_id": "Q1",
                    "findings": [
                        {"claim": "Finding A [S2].", "source_ids": ["S2"]}
                    ]
                }
            ]
        }
        self.report = {
            "report_markdown": "Introductory evidence [S1] and comparative findings [S2, S1]."
        }

    def test_citation_order_matches_appearance(self):
        cite_map, cited, uncited = build_citation_map(self.evidence, self.report)
        # S1 appeared first in report markdown -> [1]
        self.assertEqual(cite_map["S1"], 1)
        # S2 appeared second -> [2]
        self.assertEqual(cite_map["S2"], 2)
        # S3 was not cited in text -> in uncited list
        self.assertNotIn("S3", cite_map)
        self.assertEqual(len(uncited), 1)
        self.assertEqual(uncited[0]["source_id"], "S3")

    def test_citation_anchor_replacement(self):
        cite_map = {"S1": 1, "S2": 2}
        text = "Sleep deprivation impairs performance [S1] and memory [S1, S2]."
        replaced = replace_citations_in_text(text, cite_map)
        self.assertIn('<a href="#source-1" class="cite-ref" title="Jump to source [1]">1</a>', replaced)
        self.assertIn('<a href="#source-2" class="cite-ref" title="Jump to source [2]">2</a>', replaced)


class TestHtmlReportRendering(unittest.TestCase):
    """Test comprehensive HTML report generation and structure."""

    def test_render_html_report_file_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "research_report.html")
            html_output = render_html_report(
                report_artifact=DEMO_REPORT_ARTIFACT,
                evidence_artifact=DEMO_EVIDENCE_ARTIFACT,
                research_plan=DEMO_PLAN,
                output_path=out_file,
                is_demo=False
            )
            self.assertTrue(os.path.exists(out_file))
            self.assertIn("<!DOCTYPE html>", html_output)
            self.assertIn("ARA · Autonomous Research Agent", html_output)
            self.assertIn(DEMO_TOPIC, html_output)

    def test_html_escaping_prevents_xss(self):
        malicious_plan = {
            "topic": "Testing <script>alert('xss')</script> Injection & Escaping",
            "domain": "AI/ML <img src=x onerror=alert(1)>",
            "research_mode": "CAUSAL",
            "temporal_sensitivity": "HIGH"
        }
        malicious_evidence = {
            "sources": [
                {
                    "source_id": "S1",
                    "title": "<script>alert('title')</script>",
                    "authors": ["<script>bad</script>"],
                    "url": "https://example.com/<tag>"
                }
            ],
            "questions": [],
            "statistics": {}
        }
        malicious_report = {
            "topic": malicious_plan["topic"],
            "epistemic_calibration": {"confidence_score": 0.5, "confidence_tier": "MODERATE"},
            "report_markdown": "Test claim with <script>evil()</script>"
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "xss_test.html")
            html_output = render_html_report(
                report_artifact=malicious_report,
                evidence_artifact=malicious_evidence,
                research_plan=malicious_plan,
                output_path=out_file,
                is_demo=False
            )
            # Must NOT contain raw unescaped script tag
            self.assertNotIn("<script>alert('xss')</script>", html_output)
            self.assertNotIn("<script>evil()</script>", html_output)
            self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", html_output)

    def test_quantitative_evidence_table_rendered(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "quant_test.html")
            html_output = render_html_report(
                report_artifact=DEMO_REPORT_ARTIFACT,
                evidence_artifact=DEMO_EVIDENCE_ARTIFACT,
                research_plan=DEMO_PLAN,
                output_path=out_file,
                is_demo=False
            )
            # Check for quantitative table elements
            self.assertIn("data-table", html_output)
            self.assertIn("QA Exact Match Accuracy", html_output)
            self.assertIn("51.8%", html_output)
            self.assertIn("-22.4% Degradation", html_output)

    def test_counter_evidence_and_contradictions_rendered(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "counter_test.html")
            html_output = render_html_report(
                report_artifact=DEMO_REPORT_ARTIFACT,
                evidence_artifact=DEMO_EVIDENCE_ARTIFACT,
                research_plan=DEMO_PLAN,
                output_path=out_file,
                is_demo=False
            )
            self.assertIn("counter-box", html_output)
            self.assertIn("Empirical Tension", html_output)
            self.assertIn("Frontier scale reasoning models remain robust", html_output)

    def test_insufficient_evidence_rendering(self):
        evidence_with_insufficient = dict(DEMO_EVIDENCE_ARTIFACT)
        evidence_with_insufficient["sufficiency_evaluation"] = DEMO_ROUND1_SUFFICIENCY

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "insuff_test.html")
            html_output = render_html_report(
                report_artifact=DEMO_REPORT_ARTIFACT,
                evidence_artifact=evidence_with_insufficient,
                research_plan=DEMO_PLAN,
                output_path=out_file,
                is_demo=False
            )
            self.assertIn("status-insufficient", html_output)
            self.assertIn("◐ Insufficient", html_output)
            self.assertIn("Completed with Gaps", html_output)

    def test_missing_optional_metadata_handled_gracefully(self):
        minimal_plan = {"topic": "Minimal Test"}
        minimal_evidence = {
            "sources": [{"source_id": "S1"}],  # No title, authors, doi, venue, year
            "questions": [],
            "statistics": {}
        }
        minimal_report = {
            "topic": "Minimal Test",
            "epistemic_calibration": {},
            "report_markdown": "Minimal markdown."
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "minimal_test.html")
            html_output = render_html_report(
                report_artifact=minimal_report,
                evidence_artifact=minimal_evidence,
                research_plan=minimal_plan,
                output_path=out_file,
                is_demo=False
            )
            self.assertTrue(os.path.exists(out_file))
            self.assertIn("Untitled Document", html_output)
            self.assertIn("Unknown Authors", html_output)

    def test_demo_banner_displayed_in_demo_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "demo_banner_test.html")
            html_output = render_html_report(
                report_artifact=DEMO_REPORT_ARTIFACT,
                evidence_artifact=DEMO_EVIDENCE_ARTIFACT,
                research_plan=DEMO_PLAN,
                output_path=out_file,
                is_demo=True
            )
            self.assertIn("DEMO DATA — NOT A REAL RESEARCH RESULT", html_output)


class TestOfflineDemoRunner(unittest.TestCase):
    """Test --demo mode execution and strict network isolation."""

    def test_demo_mode_executes_offline_without_network(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                os.makedirs("data", exist_ok=True)
                os.makedirs("evaluation_logs", exist_ok=True)

                # Run offline demo with buffered console to prevent cp1252 charmap errors in pytest
                from cli.console import ARAConsole
                from rich.console import Console
                buf_ui = ARAConsole(verbose=False)
                buf_ui.console = Console(file=io.StringIO(), markup=True)
                buf_ui.progress.console = buf_ui.console

                run_demo(verbose=False, auto_open=False, ui=buf_ui)

                # Verify all artifacts were produced
                self.assertTrue(os.path.exists("data/research_report.html"))
                self.assertTrue(os.path.exists("data/research_report.md"))
                self.assertTrue(os.path.exists("data/research_report.json"))
                self.assertTrue(os.path.exists("data/research_evidence.json"))
                self.assertTrue(os.path.exists("data/research_plan.json"))

                # Verify HTML report contains DEMO banner
                with open("data/research_report.html", "r", encoding="utf-8") as f:
                    html_content = f.read()
                self.assertIn("DEMO DATA — NOT A REAL RESEARCH RESULT", html_content)
                self.assertIn("Patrick Lewis", html_content)
                self.assertIn("#source-1", html_content)

            finally:
                os.chdir(orig_cwd)

    def test_network_guard_blocks_external_calls(self):
        from demo.demo_runner import install_network_guard
        import urllib.request

        install_network_guard()
        with self.assertRaises(NetworkGuardViolation):
            urllib.request.urlopen("https://api.openalex.org/works")


if __name__ == "__main__":
    unittest.main()
