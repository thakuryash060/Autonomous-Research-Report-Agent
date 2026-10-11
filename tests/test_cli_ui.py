"""
tests/test_cli_ui.py

Unit tests for the ARA CLI UI components, theme, console controller, and event hooks.
Verifies deterministic rendering of startup screens, live step trees, gap alerts,
epistemic confidence bars, and final screens without triggering external research.
"""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.text import Text

from cli.theme import (
    format_confidence_bar,
    format_status_indicator,
    SYM_CHECK,
    SYM_HALF,
    SYM_DIAMOND,
    SYM_REFRESH,
)
from cli.components import (
    render_banner,
    render_startup_status,
    render_evidence_gap_alert,
    render_re_search_launch,
    render_provider_warning,
    render_evidence_table,
    render_final_screen,
)
from cli.progress import ResearchProgressManager
from cli.console import ARAConsole
from search_agent.source_providers import set_provider_event_hook, _emit_provider_event
from search_agent.tee_logger import TeeLogger


class TestCLIThemeAndFormatting(unittest.TestCase):
    """Test theme formatting helpers."""

    def test_confidence_bar_formatting(self):
        bar_text = format_confidence_bar(0.73, "MODERATE", width=20)
        self.assertIn("MODERATE", bar_text)
        self.assertIn("0.73", bar_text)
        self.assertIn("█", bar_text)
        self.assertIn("░", bar_text)

    def test_confidence_bar_clamping(self):
        bar_low = format_confidence_bar(-0.5, "LOW", width=10)
        self.assertIn("0.00", bar_low)
        bar_high = format_confidence_bar(1.5, "VERY_HIGH", width=10)
        self.assertIn("1.00", bar_high)

    def test_status_indicator(self):
        suff = format_status_indicator(True)
        self.assertIn("sufficient", suff)
        self.assertIn(SYM_CHECK, suff)

        insuff = format_status_indicator(False)
        self.assertIn("insufficient", insuff)
        self.assertIn(SYM_HALF, insuff)


class TestCLIComponents(unittest.TestCase):
    """Test visual card and screen rendering."""

    def test_render_banner(self):
        banner = render_banner()
        self.assertIsInstance(banner, Text)
        plain = banner.plain
        self.assertIn("AUTONOMOUS RESEARCH AGENT", plain)
        self.assertIn("Evidence-driven research", plain)

    def test_render_startup_status(self):
        status_box = render_startup_status(
            openalex_active=True,
            semantic_scholar_active=True,
            tavily_active=True
        )
        plain = status_box.plain
        self.assertIn("Academic Search", plain)
        self.assertIn("OpenAlex", plain)
        self.assertIn("Semantic Scholar", plain)
        self.assertIn("Web Research", plain)
        self.assertIn("Tavily", plain)
        self.assertIn("Autonomous", plain)

    def test_render_evidence_gap_alert(self):
        gaps = [
            {"question_id": "Q2", "missing_requirements": ["counter_evidence"]},
            {"question_id": "Q3", "missing_requirements": ["quantitative_evidence"]},
        ]
        alert = render_evidence_gap_alert(gaps)
        plain = alert.plain
        self.assertIn(SYM_DIAMOND, plain)
        self.assertIn("Evidence gap detected", plain)
        self.assertIn("Q2 needs additional counter evidence", plain)
        self.assertIn("Q3 needs additional quantitative evidence", plain)

    def test_render_re_search_launch(self):
        actions = ["searching quantitative evidence", "searching counter-evidence"]
        launch_card = render_re_search_launch(actions, extra_source_count=8)
        plain = launch_card.plain
        self.assertIn(SYM_REFRESH, plain)
        self.assertIn("Launching targeted research...", plain)
        self.assertIn("searching quantitative evidence", plain)
        self.assertIn("retrieving 8 additional sources", plain)

    def test_render_provider_warning(self):
        card = render_provider_warning("OpenAlex", "rate limited", "Continuing with Semantic Scholar")
        plain = card.plain
        self.assertIn("OpenAlex rate limited", plain)
        self.assertIn("Continuing with Semantic Scholar", plain)

    def test_render_final_screen(self):
        sufficiency_results = [
            {"question_id": "Q1", "sufficient": True, "finding_count": 12},
            {"question_id": "Q2", "sufficient": True, "finding_count": 9},
            {"question_id": "Q3", "sufficient": False, "finding_count": 4},
        ]
        screen = render_final_screen(
            sufficiency_results=sufficiency_results,
            confidence_score=0.73,
            confidence_tier="MODERATE",
            total_sources=18,
            total_quant=14,
            total_counter=4,
            research_rounds=2,
            plan_path="data/research_plan.json",
            evidence_path="data/research_evidence.json",
            report_path="data/research_report.md",
            log_path="evaluation_logs/test.txt"
        )
        self.assertIsNotNone(screen)


class TestResearchProgressManager(unittest.TestCase):
    """Test progress manager rendering steps."""

    def setUp(self):
        self.buf = io.StringIO()
        self.console = Console(file=self.buf, force_terminal=False, color_system=None)
        self.progress = ResearchProgressManager(self.console)

    def test_planning_step_output(self):
        self.progress.complete_planning(question_count=3, has_counter=True)
        output = self.buf.getvalue()
        self.assertIn("Planning research", output)
        self.assertIn("Generated 3 research questions", output)
        self.assertIn("Defined evidence requirements", output)
        self.assertIn("Created counter-evidence strategy", output)

    def test_search_step_output(self):
        self.progress.complete_search(
            providers=["Tavily", "OpenAlex", "Semantic Scholar"],
            candidate_count=544,
            unique_count=392
        )
        output = self.buf.getvalue()
        self.assertIn("Searching", output)
        self.assertIn("Tavily", output)
        self.assertIn("OpenAlex", output)
        self.assertIn("Semantic Scholar", output)
        self.assertIn("544 candidates", output)
        self.assertIn("392 unique sources", output)

    def test_ranking_and_retrieval_output(self):
        self.progress.complete_ranking(selected_count=13)
        self.progress.complete_retrieval(retrieved=12, total=13)
        output = self.buf.getvalue()
        self.assertIn("Ranking sources", output)
        self.assertIn("13 sources selected for deep retrieval", output)
        self.assertIn("Retrieving evidence", output)
        self.assertIn("12 / 13", output)


class TestARAConsoleController(unittest.TestCase):
    """Test the central ARAConsole controller."""

    def test_console_initialization(self):
        ui = ARAConsole(verbose=False)
        self.assertIsNotNone(ui.console)
        self.assertIsNotNone(ui.progress)

    def test_provider_event_hook_integration(self):
        mock_hook = MagicMock()
        set_provider_event_hook(mock_hook)
        _emit_provider_event("OpenAlex", "rate limited", "Continuing with Semantic Scholar")
        mock_hook.assert_called_once_with("OpenAlex", "rate limited", "Continuing with Semantic Scholar")

    def test_provider_warning_debouncing(self):
        ui = ARAConsole(verbose=False)
        ui.console = Console(file=io.StringIO())
        # First warning should register and print
        ui.show_provider_warning("OpenAlex", "rate limited", "Continuing with Semantic Scholar")
        self.assertIn("OpenAlex:rate limited", ui._warned_providers)

        # Second identical warning should be suppressed
        ui.show_provider_warning("OpenAlex", "rate limited", "Continuing with Semantic Scholar")
        # Should not crash and set size remains 1
        self.assertEqual(len(ui._warned_providers), 1)

    def test_spinner_does_not_redirect_stdout(self):
        ui = ARAConsole(verbose=False)
        ui.spinner("Test Spinner")
        self.assertFalse(ui.progress._active_status._live._redirect_stdout)
        self.assertFalse(ui.progress._active_status._live._redirect_stderr)
        ui.stop_spinner()

    def test_show_final_screen_extracts_correct_metrics(self):
        ui = ARAConsole(verbose=False)
        buf = io.StringIO()
        ui.console = Console(file=buf)

        report_artifact = {
            "epistemic_calibration": {
                "confidence_score": 0.85,
                "confidence_tier": "HIGH_CONFIDENCE"
            }
        }
        evidence_artifact = {
            "statistics": {
                "selected_sources": 12,
                "quantitative_findings": 8,
                "counter_findings": 2
            },
            "sources": [{"source_id": f"S{i}"} for i in range(12)]
        }
        sufficiency_results = [
            {"question_id": "Q1", "sufficient": True, "finding_count": 6, "quantitative_count": 4, "counter_count": 1},
            {"question_id": "Q2", "sufficient": True, "finding_count": 6, "quantitative_count": 4, "counter_count": 1}
        ]

        ui.show_final_screen(
            report_artifact=report_artifact,
            evidence_artifact=evidence_artifact,
            sufficiency_results=sufficiency_results,
            log_path="evaluation_logs/test.txt"
        )
        rendered = buf.getvalue()
        self.assertIn("Research complete", rendered)
        self.assertIn("Quantitative findings", rendered)
        self.assertIn("8", rendered)
        self.assertIn("Counter-evidence", rendered)
        self.assertIn("2", rendered)


class TestTeeLoggerVerboseAndQuiet(unittest.TestCase):
    """Test TeeLogger with verbose=True vs verbose=False."""

    def test_quiet_mode_writes_to_file_without_terminal_spam(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            terminal_buf = io.StringIO()
            # Test TeeLogger in quiet/normal mode
            logger = TeeLogger(log_dir=tmp_dir, verbose=False)
            # Replace terminal stream in logger for testing
            logger.stdout_tee.terminal = terminal_buf

            print("This is a detailed internal debug line.")
            logger.close()

            # Terminal buffer should NOT contain the message in quiet mode
            self.assertNotIn("This is a detailed internal debug line.", terminal_buf.getvalue())

            # Log file MUST contain the message
            with open(logger.get_log_path(), "r", encoding="utf-8") as f:
                log_content = f.read()
            self.assertIn("This is a detailed internal debug line.", log_content)


if __name__ == "__main__":
    unittest.main()
