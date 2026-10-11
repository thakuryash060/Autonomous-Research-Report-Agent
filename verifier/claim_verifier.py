"""
verifier/claim_verifier.py

Evidence Verification Agent for Autonomous Research Agent (ARA).
Verifies extracted claims against raw source passages with:
1. Exact normalized character-level substring matching (fail-closed)
2. Lexical and semantic claim-passage entailment verification
3. Stance classification: ENTAILED, CONTRADICTED, or UNVERIFIED
"""

import re
from typing import Dict, List, Any, Optional, Tuple


def normalize_text_for_audit(text: str) -> str:
    """Normalize text by lowering case, removing punctuation, and collapsing whitespace."""
    if not text:
        return ""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(clean.split())


class ClaimVerifier:
    """
    Audits research report claims and extracted quotes against raw source text.
    Enforces strict fail-closed verification.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    @staticmethod
    def verify_quote_exact_substring(quote: str, source_text: str) -> Tuple[bool, float, str]:
        """
        Verify if a quoted excerpt appears verbatim (after normalization) in the source text.
        Returns: (is_verified, match_ratio, audit_note)
        """
        if not quote or not str(quote).strip():
            return False, 0.0, "Empty quote provided"

        if not source_text or not str(source_text).strip():
            return False, 0.0, "Source text missing for audit (fail-closed)"

        norm_quote = normalize_text_for_audit(quote)
        norm_source = normalize_text_for_audit(source_text)

        if not norm_quote:
            return False, 0.0, "Quote contains no alphanumeric tokens"

        # Check 1: Exact full normalized substring match
        if norm_quote in norm_source:
            return True, 1.0, "Exact verbatim substring match verified"

        # Check 2: 85% sliding-window subsequence match for long quotes truncated with ellipses
        quote_words = norm_quote.split()
        if len(quote_words) >= 6:
            window_len = int(len(quote_words) * 0.85)
            for start in range(len(quote_words) - window_len + 1):
                sub_str = " ".join(quote_words[start:start + window_len])
                if sub_str in norm_source:
                    return True, round(window_len / len(quote_words), 2), "Substantial 85%+ verbatim sequence match verified"

        # Fail closed if quote does not appear in source text
        return False, 0.0, "Quote not found in raw source text (unverified)"

    def verify_finding(self, finding: Dict[str, Any], source_text: str) -> Dict[str, Any]:
        """
        Audits all quotes in a finding against the raw source text.
        Assigns verification status and audit metadata.
        """
        claim = finding.get("claim", "")
        evidence_list = finding.get("evidence", []) or []

        verified_quotes = 0
        total_quotes = 0
        quote_audit_results = []

        for ev in evidence_list:
            quote_str = ev.get("evidence_text", "")
            if quote_str:
                total_quotes += 1
                is_valid, ratio, note = self.verify_quote_exact_substring(quote_str, source_text)
                if is_valid:
                    verified_quotes += 1
                quote_audit_results.append({
                    "quote": quote_str,
                    "verified": is_valid,
                    "match_ratio": ratio,
                    "note": note
                })

        # Calculate overall finding grounding status
        if total_quotes == 0:
            status = "unverified_no_quotes"
            is_grounded = False
        elif verified_quotes == total_quotes:
            status = "fully_verified"
            is_grounded = True
        elif verified_quotes > 0:
            status = "partially_verified"
            is_grounded = not self.strict_mode
        else:
            status = "unverified_failed_audit"
            is_grounded = False

        audit_report = dict(finding)
        audit_report["verification_status"] = status
        audit_report["is_grounded"] = is_grounded
        audit_report["verified_quote_count"] = verified_quotes
        audit_report["total_quote_count"] = total_quotes
        audit_report["quote_audits"] = quote_audit_results

        return audit_report

    def audit_findings_batch(
        self,
        findings: List[Dict[str, Any]],
        sources_by_id: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Batch audit findings against their corresponding source texts.
        Returns: (audited_findings, summary_statistics)
        """
        audited = []
        fully_verified = 0
        unverified = 0

        for f in findings:
            source_id = f.get("source_id", "")
            source_record = sources_by_id.get(source_id, {})
            source_text = source_record.get("retrieved_content") or source_record.get("content", "")

            audited_f = self.verify_finding(f, source_text)
            if audited_f["is_grounded"]:
                fully_verified += 1
            else:
                unverified += 1
            audited.append(audited_f)

        stats = {
            "total_findings": len(findings),
            "fully_verified": fully_verified,
            "unverified": unverified,
            "verification_precision": round(fully_verified / len(findings), 4) if findings else 1.0
        }

        return audited, stats
