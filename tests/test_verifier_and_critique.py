"""
tests/test_verifier_and_critique.py

Unit tests for ClaimVerifier (strict quote auditing) and PlanCritic (hypothesis falsification).
"""

import unittest
from verifier.claim_verifier import ClaimVerifier, normalize_text_for_audit
from critique.plan_critic import PlanCritic


class TestClaimVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = ClaimVerifier(strict_mode=True)
        self.raw_source = (
            "We conducted a randomized controlled trial with 95 developers. "
            "The group using GitHub Copilot completed the task 55.8% faster than the control group. "
            "However, code review times increased by 15%."
        )

    def test_verbatim_quote_passes(self):
        quote = "completed the task 55.8% faster than the control group"
        is_valid, ratio, msg = self.verifier.verify_quote_exact_substring(quote, self.raw_source)
        self.assertTrue(is_valid)
        self.assertEqual(ratio, 1.0)

    def test_fabricated_quote_fails_closed(self):
        quote = "developers achieved a 99.9% productivity boost with zero errors"
        is_valid, ratio, msg = self.verifier.verify_quote_exact_substring(quote, self.raw_source)
        self.assertFalse(is_valid)
        self.assertEqual(ratio, 0.0)

    def test_missing_source_text_fails_closed(self):
        quote = "completed the task 55.8% faster"
        is_valid, ratio, msg = self.verifier.verify_quote_exact_substring(quote, "")
        self.assertFalse(is_valid)
        self.assertIn("fail-closed", msg)

    def test_finding_audit_workflow(self):
        finding = {
            "claim": "Copilot speeds up development by over 50%.",
            "evidence": [
                {"evidence_text": "completed the task 55.8% faster than the control group"}
            ]
        }
        audited = self.verifier.verify_finding(finding, self.raw_source)
        self.assertTrue(audited["is_grounded"])
        self.assertEqual(audited["verification_status"], "fully_verified")


class TestPlanCritic(unittest.TestCase):

    def setUp(self):
        self.plan_data = {
            "hypothesis": "Generative AI increases developer productivity across all coding tasks.",
            "competing_hypotheses": [
                "Generative AI productivity gains are limited to novice developers and degrade for experienced engineers.",
                "AI generated code increases code churn and maintainability debt."
            ],
            "falsification_criteria": [
                "Controlled empirical trials showing experienced developers were slower with AI.",
                "Evidence showing code churn or defect rates increase significantly."
            ]
        }
        self.critic = PlanCritic(self.plan_data)

    def test_hypothesis_falsification_detection(self):
        counter_findings = [
            {
                "claim": "METR 2025 trial showed experienced developers were slower with AI on complex tasks.",
                "stance": "counter",
                "evidence": [{"evidence_text": "Experienced developers were slower due to debugging subtle errors."}]
            }
        ]
        result = self.critic.evaluate_falsification(counter_findings)
        self.assertTrue(result["hypothesis_falsified"])
        self.assertGreaterEqual(result["triggered_count"], 1)

    def test_critique_report_verdict(self):
        findings = [
            {
                "claim": "Novice developers completed tasks 55% faster.",
                "stance": "support",
                "evidence": [{"evidence_text": "Novice developers completed tasks faster."}]
            },
            {
                "claim": "Experienced developers were slower and defect rates increased.",
                "stance": "counter",
                "evidence": [{"evidence_text": "Defect rates increase significantly in production."}]
            }
        ]
        report = self.critic.review_evidence_package(findings)
        self.assertEqual(report["hypothesis_verdict"], "FALSIFIED_OR_STRONGLY_QUALIFIED")
        self.assertTrue(report["metrics"]["has_counter_evidence"])
        self.assertGreater(len(report["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
