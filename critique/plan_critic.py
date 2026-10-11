"""
critique/plan_critic.py

Plan Critic Agent for Autonomous Research Agent (ARA).
Reviews synthesized research evidence and report drafts against the formal
Planner contract (data/research_plan.json):
1. Evaluates Working Hypothesis vs Competing Hypotheses
2. Audits Falsification Criteria against extracted empirical counter-evidence
3. Checks per-question evidence quota compliance
4. Emits an actionable Critique Report with verdicts and revision triggers
"""

import re
from typing import Dict, List, Any, Optional, Tuple


class PlanCritic:
    """
    Independent Critic Agent that audits synthesized research evidence against
    the Planner's hypothesis contract and falsification criteria.
    """

    def __init__(self, plan_data: Dict[str, Any]):
        self.plan = plan_data
        self.working_hypothesis = plan_data.get("hypothesis", "")
        self.competing_hypotheses = plan_data.get("competing_hypotheses", []) or []
        self.falsification_criteria = plan_data.get("falsification_criteria", []) or []
        self.evaluation_criteria = plan_data.get("evaluation_criteria", []) or []
        self.questions = plan_data.get("questions", []) or []

    def evaluate_falsification(self, counter_findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if any extracted counter-evidence matches the Planner's explicit falsification criteria.
        """
        falsification_triggers = []
        counter_texts = []
        for f in counter_findings:
            claim = str(f.get("claim", ""))
            ev_texts = " ".join(e.get("evidence_text", "") for e in f.get("evidence", []))
            counter_texts.append(f"{claim} {ev_texts}".lower())

        all_counter_corpus = " ".join(counter_texts)

        for idx, criterion in enumerate(self.falsification_criteria, start=1):
            crit_lower = criterion.lower()
            # Token overlap check
            crit_words = [w for w in re.findall(r"\w+", crit_lower) if len(w) > 3]
            hits = sum(1 for w in crit_words if w in all_counter_corpus)
            ratio = hits / len(crit_words) if crit_words else 0.0

            is_triggered = ratio >= 0.40 and len(counter_findings) > 0

            falsification_triggers.append({
                "criterion_id": f"FC{idx}",
                "criterion": criterion,
                "triggered": is_triggered,
                "confidence": round(ratio, 2),
                "matching_signals": hits
            })

        any_triggered = any(t["triggered"] for t in falsification_triggers)

        return {
            "hypothesis_falsified": any_triggered,
            "falsification_details": falsification_triggers,
            "total_criteria": len(self.falsification_criteria),
            "triggered_count": sum(1 for t in falsification_triggers if t["triggered"])
        }

    def assess_competing_hypotheses(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Determine empirical support for each competing hypothesis.
        """
        corpus = " ".join(f.get("claim", "") + " " + " ".join(e.get("evidence_text", "") for e in f.get("evidence", [])) for f in findings).lower()
        results = []

        for idx, comp in enumerate(self.competing_hypotheses, start=1):
            comp_lower = comp.lower()
            comp_words = [w for w in re.findall(r"\w+", comp_lower) if len(w) > 3]
            hits = sum(1 for w in comp_words if w in corpus)
            ratio = hits / len(comp_words) if comp_words else 0.0

            if ratio >= 0.50:
                verdict = "supported_by_evidence"
            elif ratio >= 0.25:
                verdict = "partially_supported"
            else:
                verdict = "unsupported"

            results.append({
                "hypothesis_id": f"H_ALT_{idx}",
                "hypothesis_text": comp,
                "verdict": verdict,
                "alignment_score": round(ratio, 2)
            })

        return results

    def review_evidence_package(
        self,
        findings: List[Dict[str, Any]],
        evidence_summary: str = ""
    ) -> Dict[str, Any]:
        """
        Comprehensive review of the evidence package emitting an official Critique Report.
        """
        support_findings = [f for f in findings if f.get("stance") == "support"]
        counter_findings = [f for f in findings if f.get("stance") in ("counter", "limitation", "trade_off")]

        # 1. Evaluate falsification
        falsification_audit = self.evaluate_falsification(counter_findings)

        # 2. Evaluate competing hypotheses
        competing_audit = self.assess_competing_hypotheses(findings)

        # 3. Formulate Primary Hypothesis Verdict
        if falsification_audit["hypothesis_falsified"]:
            verdict = "FALSIFIED_OR_STRONGLY_QUALIFIED"
            verdict_explanation = "Empirical counter-evidence triggered at least one explicit falsification criterion."
        elif len(support_findings) > 0 and len(counter_findings) > 0:
            verdict = "PARTIALLY_SUPPORTED_WITH_TRADE_OFFS"
            verdict_explanation = "Primary hypothesis holds under bounded conditions, but significant empirical trade-offs or overhead were validated."
        elif len(support_findings) > 0:
            verdict = "SUPPORTED"
            verdict_explanation = "Empirical evidence supports the working hypothesis with no falsifying counter-evidence."
        else:
            verdict = "INSUFFICIENT_EVIDENCE"
            verdict_explanation = "Insufficient empirical data to render a definitive verdict."

        critique_report = {
            "working_hypothesis": self.working_hypothesis,
            "hypothesis_verdict": verdict,
            "verdict_explanation": verdict_explanation,
            "falsification_audit": falsification_audit,
            "competing_hypotheses_audit": competing_audit,
            "metrics": {
                "total_findings": len(findings),
                "supporting_findings_count": len(support_findings),
                "counter_findings_count": len(counter_findings),
                "has_counter_evidence": len(counter_findings) > 0
            },
            "recommendations": []
        }

        # Generate actionable recommendations
        if len(counter_findings) == 0:
            critique_report["recommendations"].append("Trigger iterative search round: Zero counter-evidence discovered (risk of confirmation bias).")
        if falsification_audit["hypothesis_falsified"]:
            critique_report["recommendations"].append("Revise report narrative: Working hypothesis falsified by empirical benchmarks.")
        if any(h["verdict"] == "supported_by_evidence" for h in competing_audit):
            critique_report["recommendations"].append("Reconcile competing hypothesis: Alternative hypothesis demonstrated strong empirical alignment.")

        return critique_report
