import json
import re
from typing import List, Dict, Any, Optional, Tuple

from .evidence_validator import EvidenceValidator

MODEL = "gemini-3.5-flash-lite"

ALLOWED_STANCES = {"support", "counter", "limitation", "trade_off", "mixed", "context"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_EVIDENCE_TYPES = {
    "quantitative",
    "qualitative",
    "methodological",
    "boundary_condition",
    "comparison"
}

SUPPORT_EVIDENCE_PATTERNS = [
    # Multi-agent advantage
    r"multi-agent\b[^\.\;\n]*\b(?:outperform|superior|better|higher|improves?|surpasses?|exceeds?|enhances?|boosts?)",
    r"(?:outperform|superior|better|higher|improves?|surpasses?|exceeds?)[^\.\;\n]*\b(?:single-agent|single llm|baseline)",
    r"single-agent\b[^\.\;\n]*\b(?:fail|failures?|underperform|suffer|error|bottleneck|limitation)",
    r"(?:advantage|superiority|benefit|gain)\s+of\s+multi-agent",
    r"multi-agent\b[^\.\;\n]*\b(?:achieves?|scores?)\s+(?:higher|better|state-of-the-art|\d+(?:\.\d+)?%)",
    r"multi-agent\b[^\.\;\n]*\bresolve\b[^\.\;\n]*\berror",
    r"collaborative\b[^\.\;\n]*\b(?:improves?|outperforms?|superior|reduces? error)",
    # Topic-invariant / directional advantage & mitigation (e.g., RAG, prompting, architectures)
    r"(?:reduces?|mitigates?|suppresses?|eliminates?)\s+(?:hallucination|error|failure|toxicity|bias)",
    r"(?:reduction|drop|decrease)\s+in\s+(?:hallucination|error|failure|toxicity|bias)\s+(?:by|of)\s+\d+",
    r"(?:outperforms?|surpasses?|exceeds?|beats?)\s+(?:standard|baseline|direct|prior\s+work)",
    r"(?:state-of-the-art|sota)\s+(?:accuracy|performance|results?|reasoning)",
    r"(?:significant|substantial)\s+(?:gain|improvement|boost)\s+in\s+(?:accuracy|reasoning|f1|pass@1)",
]

COUNTER_EVIDENCE_PATTERNS = [
    # Multi-agent disadvantage & overhead
    r"(?:baseline|single-agent|single\s+model|single\s+llm|self-consistency|sc\b|cot\b|chain-of-thought|standard\s+(?:prompting|model|approach)|sampling|majority\s+voting)\b[^\.\;\n]*\b(?:matches|outperforms|superior|better|exceeds?)",
    r"(?:underperform|fails?|failures?|degrades?|degradation|worse|lower|inferior)\s+(?:than|compared to|relative to)\s+(?:baseline|single-agent|single\s+model|single\s+llm|self-consistency|sc\b|cot\b|chain-of-thought|standard\s+prompting|sampling|majority\s+voting)",
    r"(?:comparable|equivalent|similar)\s+(?:or|to)\s+(?:slightly\s+)?(?:lower|worse|inferior)\s+(?:performance|accuracy|results?|scores?)",
    r"(?:comparable|equivalent|similar)\s+(?:or|to)\s+(?:slightly\s+)?(?:lower|worse|inferior)\s+than\s+(?:baseline|single-agent|single\s+model|self-consistency|sc\b|cot\b|chain-of-thought)",
    r"(?:fails?|failed|unable)\s+to\s+(?:improve|outperform|beat|surpass|exceed)\b",
    r"(?:does not|doesn't|cannot)\s+(?:consistently\s+)?(?:improve|outperform|surpass|beat|show advantage)\b",
    r"(?:barely|marginally|hardly)\s+(?:improves?|improved|gains?)\b",
    r"(?:no|little|negligible|marginal|diminishing)\s+(?:improvement|gain|advantage|lift|returns?|accuracy boost)\b",
    r"(?:performance|accuracy)\s+(?:gains?|improvements?)\s+(?:diminish|disappear|vanish|evaporate|fail to materialize)\b",
    r"\b(?:degrades?|degradation|impairs?|hurts?)\s+(?:reasoning|accuracy|performance|code|math)\b",
    r"\b(?:not|never)\s+(?:a\s+)?(?:silver bullet|panacea|universally effective)\b",
    r"single-agent\b[^\.\;\n]*\b(?:outperform|matches|superior|better|exceeds?)[^\.\;\n]*\bmulti-agent",
    r"multi-agent\b[^\.\;\n]*\b(?:underperform|fails?|failures?|degrades?|degradation|worse|lower)",
    r"multi-agent\b[^\.\;\n]*\b(?:suffer|suffers|prone to)\b[^\.\;\n]*\b(?:error propagation|cascading|hallucination|bottleneck)",
    r"(?:overhead|cost|latency|bottleneck|breakdown)\b[^\.\;\n]*\bmulti-agent",
    r"multi-agent\b[^\.\;\n]*\b(?:quadratic token|massive overhead|high latency|prohibitive cost|communication overhead)",
    r"(?:equal|equivalent|normalized)\s+(?:compute|tokens?)[^\.\;\n]*\bsingle-agent\b[^\.\;\n]*\b(?:matches|outperforms)",
    r"debate hacking|cheap-talk|groupthink|infinite loop|consensus breakdown",
    # Topic-invariant / baseline parity or failure / overhead
    r"(?:baseline|standard\s+(?:prompting|model|approach))\b[^\.\;\n]*\b(?:matches|outperforms|superior|better)",
    r"(?:equal|equivalent|normalized)\s+(?:compute|budget|tokens?)[^\.\;\n]*\b(?:eliminates?|matches|no significant difference)",
    r"(?:not consistently|fails to consistently|no significant difference|statistically equivalent|fails to outperform)",
    r"(?:increases?|escalates?|worsens?)\s+(?:hallucination|error|latency|cost|overhead|failure)",
    r"(?:retrieval noise|distractor|irrelevant\s+context)\b[^\.\;\n]*\b(?:degrades?|impairs?|lowers?|increases? error)",
    r"(?:overhead|latency|token cost|computational expense)\b[^\.\;\n]*\b(?:prohibitive|drastically increases|outweighs)",
    # Inference acceleration / speedup / latency regression / threshold failure patterns
    r"(?:fails?|failed|unable)\s+to\s+(?:provide|deliver|yield|achieve|produce)?\s*(?:a\s+)?(?:net\s+)?(?:speedup|acceleration|latency reduction|gain|benefit|advantage)\b",
    r"\b(?:slower\s+than|degrades?\s+below|worse\s+than)\s+(?:target[- ]only|target\s+model|target\s+decoding|standard\s+decoding|non-speculative|baseline|autoregressive|direct\s+decoding)\b",
    r"\b(?:no|zero|negative|diminishing)\s+(?:speedup|net speedup|acceleration|latency reduction|gain|benefit)\b",
    r"(?:negates?|offsets?|eliminates?)\s+(?:its\s+)?(?:benefits?|gains?|speedup)\b",
    r"(?:overhead|cost)\s+(?:can\s+)?(?:make|renders?)\s+[a-z\s_-]*(?:slower|inefficient)\s+than\b",
    r"(?:performance|throughput)\s+(?:degradation|degrades?)\b",
    r"(?:rejected\s+tokens?|verification\s+effort|verification\s+overhead|draft\s+computation\s+cost)\s+(?:offset|negate|exceed|outweigh)",
    r"\b(?:more expensive than decoding directly|slower than target decoding)\b",
    # Performance deterioration / degradation / drops on non-conflicting or general data
    r"\b(?:deteriorates?|deterioration|degrades?|degradation|impairs?|erodes?|compromises?)\s+(?:on|in|under|performance|accuracy|generation)\b",
    r"\b(?:performance|accuracy|score)\s+(?:drops?|falls?|degrades?|deteriorates?|losses?|penalt(?:y|ies))\b",
    r"\b(?:drops?|losses?|degradation|deterioration)\s+in\s+(?:performance|accuracy|score|sensitivity)\b",
    r"\b(?:inadvertently\s+deteriorate|deteriorate\s+performance|performance\s+drops?)\b",
]

MIXED_TRADE_OFF_PATTERNS = [
    r"(?:higher accuracy|improves?|outperforms?|superior|better|gains?|boosts?|advances?)[^\.\;\n]*(?:but|however|at the cost of|accompanied by|offset by|at the expense of)[^\.\;\n]*(?:overhead|latency|cost|error|penalty|tokens?|trade-?off)",
    r"(?:trade-off|tradeoff|task-dependent|mixed results|mixed performance)",
    r"(?:outperform|superior)[^\.\;\n]*(?:on|in)[^\.\;\n]*(?:math|gsm8k|complex)[^\.\;\n]*(?:but|while)[^\.\;\n]*(?:underperform|worse|degrades?|fails?)",
    r"(?:gains?|improvements?)\s+(?:diminish|disappear|vanish)\s+(?:on|under|when)",
]


def _verify_and_calibrate_stance(stance: str, claim: str, evidence_texts: list) -> str:
    """
    Classify finding stance with semantic directionality relative to the hypothesis/claim.
    Supports multi-agent and generalized directional patterns (e.g. error mitigation vs overhead/parity).
    """
    claim_lower = str(claim or "").lower()
    combined = (f"{claim_lower} " + " ".join(evidence_texts)).lower()

    # Prioritize claim-level counter assertions:
    claim_is_counter = any(re.search(p, claim_lower) for p in COUNTER_EVIDENCE_PATTERNS)
    claim_is_support = any(re.search(p, claim_lower) for p in SUPPORT_EVIDENCE_PATTERNS)
    claim_is_tradeoff = any(re.search(p, claim_lower) for p in MIXED_TRADE_OFF_PATTERNS)

    if claim_is_counter and not claim_is_support and not claim_is_tradeoff:
        return "counter"

    is_mixed = any(re.search(p, combined) for p in MIXED_TRADE_OFF_PATTERNS)
    is_support = any(re.search(p, combined) for p in SUPPORT_EVIDENCE_PATTERNS)
    is_counter = any(re.search(p, combined) for p in COUNTER_EVIDENCE_PATTERNS)

    if is_mixed or (is_support and is_counter):
        return "mixed"
    elif is_support and not is_counter:
        return "support"
    elif is_counter and not is_support:
        return "counter"

    # Fallback to model's label if valid, defaulting to context
    stance_clean = str(stance or "context").strip().lower()
    return stance_clean if stance_clean in ALLOWED_STANCES else "context"


def _infer_location_in_source(evidence_text: str, source_text: str) -> str:
    """Infer section, table, or paper region if location_in_source was omitted."""
    if not evidence_text or not source_text:
        return "Main Text"
    search_sub = evidence_text[:40].strip()
    idx = source_text.lower().find(search_sub.lower()) if search_sub else -1
    if idx != -1:
        preceding = source_text[max(0, idx - 500):idx]
        sec_match = re.findall(r"(?:Section|Sec\.|Table|Tab\.|Figure|Fig\.|Appendix)\s+[0-9A-Za-z\.]+", preceding, re.I)
        if sec_match:
            return sec_match[-1].strip()
        if "abstract" in preceding.lower():
            return "Abstract"
        if "introduction" in preceding.lower():
            return "Introduction"
        if "conclusion" in preceding.lower():
            return "Conclusion"
    return "Main Text"


def _decompose_complex_finding(finding: dict) -> list[dict]:
    """
    Decomposes a compound finding into atomic findings when it bundles both
    positive performance gains and negative trade-offs / bottlenecks / overhead.
    """
    claim = str(finding.get("claim", "")).strip()
    quant_list = finding.get("quantitative_evidence", [])
    ev_list = finding.get("evidence", [])
    ev_texts = [e.get("evidence_text", "") for e in ev_list]

    contrast_match = re.search(
        r"^(.*?)\s*(?:,\s*(?:but|however|while|yet|whereas)\s*|\s+(?:at the cost of|accompanied by|offset by)\s+)(.*)$",
        claim,
        re.I
    )

    if not contrast_match and len(quant_list) <= 1:
        return [finding]

    if contrast_match:
        part1 = contrast_match.group(1).strip()
        part2 = contrast_match.group(2).strip()

        if len(part1) > 15 and len(part2) > 15:
            quant1 = []
            quant2 = []
            for qrec in quant_list:
                metric_name = str(qrec.get("metric", "")).lower()
                if any(m in metric_name for m in ("cost", "latency", "token", "overhead", "time", "error")):
                    quant2.append(qrec)
                else:
                    quant1.append(qrec)

            stance1 = _verify_and_calibrate_stance("support", part1, [])
            stance2 = _verify_and_calibrate_stance("counter", part2, [])

            f1 = dict(finding)
            f1["claim"] = part1
            f1["stance"] = stance1
            f1["quantitative_evidence"] = quant1 if quant1 else quant_list
            f1["atomic_type"] = "performance"

            f2 = dict(finding)
            f2["claim"] = part2.capitalize()
            f2["stance"] = stance2
            f2["quantitative_evidence"] = quant2 if quant2 else []
            f2["atomic_type"] = "overhead_or_limitation"

            return [f1, f2]

    return [finding]


STOP_WORDS = {
    "what", "which", "where", "when", "whom", "how", "does", "with", "from", "that",
    "this", "each", "were", "been", "have", "more", "over", "into", "their", "such",
    "than", "also", "then", "under", "most", "about", "both", "these", "those", "using",
    "based", "study", "paper", "show", "shows", "shown", "within", "between",
    "among", "across", "will", "would", "could", "should", "some", "other"
}


def _validate_finding_for_question(claim: str, evidence_texts: list, question: dict) -> bool:
    """
    Validate that an extracted finding specifically answers its assigned research question.
    Applies strict variable-gated alignment based on question topic and requirements.
    """
    if not claim:
        return False
    claim_lower = claim.lower()
    bio_chem_markers = (
        "dna methylation", "mass spectrometry", "proteomics", "cardiovascular",
        "condensation nuclei", "in vitro", "in vivo", "pharmacokinetics",
        "schizophrenia", "clinical psychology"
    )
    if any(m in claim_lower for m in bio_chem_markers):
        return False

    qtext = str(question.get("question", "")).lower()
    qtype = str(question.get("type", "")).lower()
    combined = f"{claim_lower} " + " ".join(evidence_texts).lower()

    # Question 3 / Overhead / Latency / Cost / Token requirements:
    # Pure accuracy claims without cost/latency/token dimensions MUST be rejected.
    if any(k in qtext for k in ("overhead", "latency", "cost", "token", "compute", "resource", "api cost")):
        cost_indicators = (
            "latency", "cost", "overhead", "token", "compute", "time", "gpu",
            "flops", "api", "inference", "consumption", "throughput", "efficiency",
            "resource", "delay", "expensive", "cheaper", "multiplier", "budget"
        )
        if not any(ind in combined for ind in cost_indicators):
            return False

    # Question 2 / Limitations / Failure modes / Error propagation:
    if "failure" in qtext or "bottleneck" in qtext or "error propagation" in qtext or "limitations" in qtype:
        limitation_indicators = (
            "fail", "failure", "bottleneck", "error", "propagation", "overhead",
            "latency", "cost", "token", "degrad", "limitation", "breakdown",
            "hallucination", "vulnerability", "groupthink", "loop", "collapse",
            "decay", "cascading", "inefficiency", "conflict"
        )
        if not any(ind in combined for ind in limitation_indicators):
            return False

    # Question 4 / Boundary conditions / Modularity / Coordination topology:
    if "boundary condition" in qtext or "under what" in qtext or "when" in qtext or "topology" in qtext or "modular" in qtext:
        boundary_indicators = (
            "boundary", "condition", "complexity", "trade-off", "tradeoff",
            "task-dependent", "when", "structure", "topology", "modular",
            "decomposition", "role", "coordination", "heterogeneous",
            "threshold", "scale", "dense", "hierarchy", "centralized"
        )
        if not any(ind in combined for ind in boundary_indicators):
            return False

    # Comparative / Benchmark reasoning accuracy questions:
    if "compare" in qtext or "comparison" in qtype or "quantitatively" in qtext:
        comparative_indicators = (
            "compare", "comparison", "vs", "versus", "outperform", "baseline",
            "single-agent", "multi-agent", "accuracy", "score", "benchmark",
            "higher", "lower", "better", "worse", "gain", "difference",
            "reduction", "mitigate", "improvement", "superior"
        )
        if not any(ind in combined for ind in comparative_indicators):
            return False

    if "security" in qtext or "vulnerability" in qtext or "privacy" in qtext:
        security_indicators = (
            "security", "leakage", "vulnerability", "privacy", "attack",
            "injection", "safety", "trust", "exposure", "jailbreak"
        )
        if not any(ind in combined for ind in security_indicators):
            return False

    return True


def _verify_passage_relevance(claim: str, evidence_texts: list, question_text: str) -> bool:
    """
    Validate that a claim or passage shares substantive vocabulary with the target question.
    Eliminates broad core anchor traps, ensuring strict topic alignment.
    """
    if not claim:
        return False
    claim_lower = claim.lower()
    bio_chem_markers = (
        "dna methylation", "mass spectrometry", "proteomics", "cardiovascular",
        "condensation nuclei", "in vitro", "in vivo", "pharmacokinetics",
        "schizophrenia", "clinical psychology"
    )
    if any(m in claim_lower for m in bio_chem_markers):
        return False

    q_tokens = {w for w in re.findall(r"[a-z0-9]+", question_text.lower()) if len(w) > 2 and w not in STOP_WORDS}
    text_tokens = {w for w in re.findall(r"[a-z0-9]+", (f"{claim} " + " ".join(evidence_texts)).lower()) if len(w) > 2 and w not in STOP_WORDS}

    overlap = q_tokens & text_tokens
    if len(overlap) < 1:
        return False
    return True


def _is_number_grounded(num_val, source_text: str) -> bool:
    if num_val is None:
        return True
    try:
        val_float = float(num_val)
    except (ValueError, TypeError):
        return True
    str_val = str(num_val).strip()
    if str_val in source_text:
        return True
    if str_val.endswith(".0") and str_val[:-2] in source_text:
        return True
    round_str = f"{val_float:.1f}"
    if round_str in source_text:
        return True
    return False


def _verify_quantitative_grounding(qrecord: dict, source_text: str) -> dict:
    """
    Validate that:
    1. A reported percentage difference (e.g. 'improved by 4.8%') is NOT mistakenly
       assigned as baseline_score = 0.0 and experimental_score = 4.8.
    2. baseline_score and experimental_score are only kept if they actually exist in the source text.
    3. If baseline was not explicitly reported, baseline_score MUST be None.
    4. Auto-compute absolute and relative differences only when both baseline and experimental exist.
    5. Validate multipliers (e.g. '3.5x', '65-fold') and ranges without synthesizing fake baseline scores.
    """
    b_score = qrecord.get("baseline_score")
    e_score = qrecord.get("experimental_score")
    diff = qrecord.get("absolute_difference")

    # Detect synthetic 0.0 baseline when text actually reported a difference (e.g. "improved by 4.8%")
    if b_score == 0.0 and (e_score is not None or diff is not None):
        has_explicit_zero = bool(re.search(r"\b0(?:\.0)?%|\bzero(?:\s+percent)?\b", source_text.lower()))
        if not has_explicit_zero:
            if diff is None and e_score is not None:
                qrecord["absolute_difference"] = e_score
                qrecord["experimental_score"] = None
            qrecord["baseline_score"] = None
            b_score = None
            e_score = qrecord.get("experimental_score")

    if b_score is not None and not _is_number_grounded(b_score, source_text):
        qrecord["baseline_score"] = None
        b_score = None

    if e_score is not None and not _is_number_grounded(e_score, source_text):
        qrecord["experimental_score"] = None
        e_score = None

    if isinstance(b_score, (int, float)) and isinstance(e_score, (int, float)):
        qrecord["absolute_difference"] = round(float(e_score) - float(b_score), 4)
        if float(b_score) != 0:
            qrecord["relative_difference"] = round(
                ((float(e_score) - float(b_score)) / float(b_score)) * 100.0, 2
            )
        else:
            qrecord["relative_difference"] = None
    elif qrecord.get("absolute_difference") is not None:
        if not _is_number_grounded(qrecord["absolute_difference"], source_text):
            qrecord["absolute_difference"] = None
        qrecord["relative_difference"] = None

    # Multiplier grounding check
    multiplier = qrecord.get("multiplier")
    if multiplier is not None:
        m_str = str(multiplier).strip()
        num_m = re.search(r"(\d+(?:\.\d+)?)", m_str)
        if num_m:
            if not _is_number_grounded(num_m.group(1), source_text):
                qrecord["multiplier"] = None
        else:
            qrecord["multiplier"] = None

    # Range grounding check
    rmin = qrecord.get("range_min")
    rmax = qrecord.get("range_max")
    if rmin is not None and not _is_number_grounded(rmin, source_text):
        qrecord["range_min"] = None
    if rmax is not None and not _is_number_grounded(rmax, source_text):
        qrecord["range_max"] = None

    return qrecord


def _clean_and_parse_json(raw_output: str) -> dict:
    """
    Robustly clean and parse JSON response from LLM, handling markdown code fences,
    extraneous text, extra trailing data after JSON object, control characters, and unescaped quotes/newlines.
    """
    text = raw_output.strip()

    # Strip markdown code blocks
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Find the start of the JSON object
    first_brace = text.find("{")
    if first_brace != -1:
        text = text[first_brace:]

    decoder = json.JSONDecoder(strict=False)

    # 1. Try raw_decode directly (parses top-level JSON object and ignores trailing extra data)
    try:
        obj, _ = decoder.raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2. Try raw_decode on text cleaned of invalid control characters
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    try:
        obj, _ = decoder.raw_decode(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 3. Try raw_decode after sanitizing unescaped backslashes
    sanitized = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', cleaned)
    try:
        obj, _ = decoder.raw_decode(sanitized)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 4. Fallback: isolate between first '{' and last '}'
    last_brace = text.rfind("}")
    if last_brace != -1:
        try:
            return json.loads(text[:last_brace + 1], strict=False)
        except Exception:
            pass
    return {}


def extract_heuristic_quantitative_records(text: str, source_id: str, content_to_use: str = "") -> List[dict]:
    """
    Extract factual quantitative metrics (accuracy contrasts, latency overheads, execution time,
    size footprints, multipliers, ranges) from evidence text.
    """
    records = []

    # 1. Percentage contrast (e.g. 71.4% to 11.3%, 12% vs 88%, from 45% to 12%, reduced from 30% to 10%)
    vs_matches = re.finditer(
        r"(?:from\s+)?(\d+(?:\.\d+)?)\s*%\s*(?:vs\.?|compared to|against|to|-)\s*(\d+(?:\.\d+)?)\s*%",
        text,
        re.I
    )
    text_lower = text.lower()
    if any(k in text_lower for k in ("hallucinat", "factual error", "faithfulness")):
        m_name = "Hallucination / Error Rate %"
    elif any(k in text_lower for k in ("accuracy", "exact match", "f1", "qa score")):
        m_name = "Accuracy / Performance Score %"
    elif any(k in text_lower for k in ("asr", "attack success")):
        m_name = "Attack Success Rate %"
    elif any(k in text_lower for k in ("error rate", "failure rate", "drop", "degrad")):
        m_name = "Error / Degradation Rate %"
    else:
        m_name = "Empirical Score / Proportion %"

    for vm in vs_matches:
        try:
            b_val = float(vm.group(1))
            e_val = float(vm.group(2))
            diff = round(e_val - b_val, 4)
            rel = round((diff / b_val) * 100.0, 2) if b_val != 0 else None
            records.append({
                "source_id": source_id,
                "metric": m_name,
                "baseline_score": b_val,
                "experimental_score": e_val,
                "absolute_difference": diff,
                "relative_difference": rel,
                "multiplier": None,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 2. Timing / Latency / Resource transition (from X to Y microseconds/ms/KiB)
    for tm in re.finditer(r"(?:from\s+)?(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(microsecond|microseconds|μs|us|ms|millisecond|milliseconds|second|seconds|s|KiB|KB|MB|MiB)\b", text, re.I):
        try:
            b_val = float(tm.group(1))
            e_val = float(tm.group(2))
            unit = tm.group(3)
            metric_type = "Serialized Size" if unit.lower() in ("kib", "kb", "mb", "mib") else "Latency / Execution Time"
            diff = round(e_val - b_val, 4)
            rel = round((diff / b_val) * 100.0, 2) if b_val != 0 else None
            records.append({
                "source_id": source_id,
                "metric": f"{metric_type} ({unit})",
                "baseline_score": b_val,
                "experimental_score": e_val,
                "absolute_difference": diff,
                "relative_difference": rel,
                "multiplier": None,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 3. Explicit Latency Overhead measurement (e.g. median latency overhead of 61.2 ms)
    for lm in re.finditer(r"(?:latency\s+overhead\s+(?:of\s+)?|overhead\s+(?:of\s+)?|latency\s+(?:of\s+)?|delay\s+(?:of\s+)?)(\d+(?:\.\d+)?)\s*(ms|milliseconds?|microseconds?|μs|us|seconds?|s)\b", text, re.I):
        try:
            l_val = float(lm.group(1))
            l_unit = lm.group(2)
            records.append({
                "source_id": source_id,
                "metric": f"Latency Overhead ({l_unit})",
                "baseline_score": None,
                "experimental_score": l_val,
                "absolute_difference": l_val,
                "relative_difference": None,
                "multiplier": None,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 4. Multiplier / overhead factor (e.g. 3.5x overhead)
    mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|[- ]fold)\s*(?:overhead|speedup|token|cost|latency|increase|gain)?", text, re.I)
    if mm:
        try:
            m_val = mm.group(1)
            mult_str = f"{m_val}x" if "fold" not in mm.group(0).lower() else f"{m_val}-fold"
            records.append({
                "source_id": source_id,
                "metric": "Multiplier / Overhead Factor",
                "baseline_score": None,
                "experimental_score": None,
                "absolute_difference": None,
                "relative_difference": None,
                "multiplier": mult_str,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 5. Reported percentage difference (e.g. reduced by 28.1%)
    for dm in re.finditer(r"(?:improved?|increased?|decreased?|dropped?|reduced?|by)\s+([\+\-]?\d+(?:\.\d+)?)\s*%", text, re.I):
        try:
            diff_val = float(dm.group(1))
            records.append({
                "source_id": source_id,
                "metric": "Reported Difference %",
                "baseline_score": None,
                "experimental_score": None,
                "absolute_difference": diff_val,
                "relative_difference": None,
                "multiplier": None,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 6. Performance / bound range (e.g. 0.00-0.95%)
    rm = re.search(r"(?:between|from)?\s*(\d+(?:\.\d+)?)\s*(?:%|ms|s)?\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*%", text, re.I)
    if rm and not records:
        try:
            rmin = float(rm.group(1))
            rmax = float(rm.group(2))
            records.append({
                "source_id": source_id,
                "metric": "Performance Range %",
                "baseline_score": None,
                "experimental_score": None,
                "absolute_difference": round(rmax - rmin, 4),
                "relative_difference": None,
                "multiplier": None,
                "range_min": rmin,
                "range_max": rmax,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 7. Reported rate / percentage proportion (e.g. 48% of SD steps were more expensive, over 40% of verification effort)
    for pm in re.finditer(r"(?:over|more than|approximately|~|exceeding)?\s*(\d+(?:\.\d+)?)\s*%\s*of\s+([a-zA-Z0-9\s_-]+?)(?:\s+(?:were|are|was|spent|failed|rejected|expensive|overhead)|[,\.]|$)", text, re.I):
        try:
            p_val = float(pm.group(1))
            category = pm.group(2).strip()
            if len(category) > 40:
                category = category[:40].strip()
            records.append({
                "source_id": source_id,
                "metric": f"Proportion of {category.title()} %",
                "baseline_score": None,
                "experimental_score": p_val,
                "absolute_difference": p_val,
                "relative_difference": None,
                "multiplier": None,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    # 8. Acceptance / rejection rate threshold (e.g. acceptance rate threshold of 0.6 / 60%)
    for am in re.finditer(r"(?:acceptance\s+rate|rejection\s+rate|threshold)\s*(?:of|below|<|<=|>|>=)?\s*(\d+(?:\.\d+)?)\s*(%|percent)?\b", text, re.I):
        try:
            rate_val = float(am.group(1))
            unit = "%" if am.group(2) or rate_val > 1.0 else "ratio"
            records.append({
                "source_id": source_id,
                "metric": f"Acceptance / Failure Threshold ({unit})",
                "baseline_score": None,
                "experimental_score": rate_val,
                "absolute_difference": rate_val,
                "relative_difference": None,
                "multiplier": None,
                "range_min": None,
                "range_max": None,
                "location_in_source": "Parsed from finding text"
            })
        except Exception:
            pass

    if content_to_use:
        records = [_verify_quantitative_grounding(r, content_to_use) for r in records]
    return records


def extract_evidence_from_source(
    gemini_client,
    question,
    source,
    model=MODEL
):
    """
    Extract source-grounded structured evidence records for one (question, source) pair.
    Uses retrieved_content (falling back to content snippet if deep content unavailable).
    """

    question_id = str(question.get("id", "")).strip().upper()
    question_text = str(question.get("question", "")).strip()
    evidence_needed = question.get("evidence_needed", [])
    requires_quant = bool(question.get("requires_quantitative_evidence", False))
    quant_fields = question.get("quantitative_fields", [])
    exp_fields = question.get("experimental_context_fields", [])
    boundary_conds = question.get("boundary_conditions", [])

    source_id = str(source.get("source_id", "")).strip().upper()

    # Content selection: use retrieved_content first, fallback to search snippet content
    retrieved = source.get("retrieved_content", "").strip()
    snippet = source.get("content", "").strip()
    content_to_use = retrieved if retrieved else snippet

    if not content_to_use:
        return []

    try:
        # Deep PDF Passage Chunking: focus long scientific documents on highest-signal 350-word passages
        if len(content_to_use) >= 3500 and gemini_client is not None:
            try:
                from .semantic_indexer import extract_relevant_passages
                query_focus = f"{question_text} {' '.join(evidence_needed)}"
                focused_content, _ = extract_relevant_passages(
                    gemini_client,
                    content_to_use,
                    query_prompt=query_focus,
                    top_k=5,
                    min_chars_to_chunk=3500
                )
                if focused_content and len(focused_content) >= 800:
                    content_to_use = focused_content
            except Exception:
                pass

        # Bounded text snippet limit to prevent prompt overflows while giving maximum context
        max_chars = 30000
        if len(content_to_use) > max_chars:
            content_to_use = content_to_use[:max_chars]


        prompt = f"""
You are a precise evidence extraction agent in an autonomous research system.
Extract factual findings grounded ONLY in the provided source text for the target research question.

TARGET RESEARCH QUESTION:
ID: {question_id}
Question: {question_text}
Evidence Needed: {evidence_needed}
Requires Quantitative Evidence: {requires_quant}
Quantitative Fields: {quant_fields}
Experimental Context Fields: {exp_fields}
Boundary Conditions to Look For: {boundary_conds}

SOURCE DOCUMENT:
Source ID: {source_id}
Title: {source.get("title", "")}
URL: {source.get("url", "")}
Source Type: {source.get("source_type", "other")}

CONTENT:
{content_to_use}

CRITICAL EXTRACTION RULES:
1. Extract ONLY facts explicitly supported by the text.
2. Do NOT invent claims, numbers, statistics, benchmarks, URLs, or source IDs.
3. Use ONLY source_id "{source_id}". Do NOT generate or reference any other source ID.
4. MULTI-STANCE & COUNTER-EVIDENCE EXTRACTION:
   - Actively extract DISTINCT findings for positive gains/vulnerabilities, defenses, negative trade-offs, and counter-evidence.
   - For Defense & Mitigation Questions:
     * Actively extract defense mechanisms (sanitization, filtering, guardrails, certified aggregation like PRA-RAG, perplexity detectors).
     * For "support" stance: extract evidence showing how defenses effectively mitigate attacks, drop attack success rates, or protect systems.
     * For "counter" stance: extract evidence demonstrating defense bypasses, evasion techniques, high false positive rates, or cases where defenses fail.
     * For "trade_off" stance: extract latency overhead, compute cost, or degradation of benign query generation.
   - For Comparative / Empirical Questions:
     * Extract a "support" finding for confirmed hypotheses or positive comparative gains.
     * Extract a "counter" finding for baseline superiority, attack failures, high resilience, or falsifications.
     * Extract a "mixed" finding if benchmark results show conflicting gains across different tasks.
     * Do NOT collapse all findings into a single "support" record!
   - Stance definitions:
     - "support": Evidence confirms the proposition, shows positive gains, or confirms vulnerability/effectiveness.
     - "counter": True refutation, baseline superiority, high resilience against attack, defense bypass, or hypothesis failure.
     - "limitation": Scope constraints, narrow benchmarks, or implementation bounds that do NOT refute the core hypothesis.
     - "trade_off": Explicit compromise where gains are offset by latency/token/false-positive overhead.
     - "context": Relevant background or methodology without direct comparative stance.
5. QUANTITATIVE EVIDENCE EXTRACTION:
   - When numbers, percentages, or benchmark scores appear in the text, extract numerical values:
     * Provide numerical floats or ints for "baseline_score" and "experimental_score" (e.g. 78.5, 84.2).
     * Provide "absolute_difference" (e.g. 5.7) and "relative_difference" (e.g. 7.26).
     * Provide "multiplier" (e.g. "3.5x", "65-fold") if relative factor or overhead multiplier is reported.
     * Provide "range_min" and "range_max" (e.g. 64.3 and 71.4) if performance range is reported.
     * Do NOT leave these fields null if numbers are present in the text!
6. Confidence must be EXACTLY one of: "high", "medium", "low".
7. Evidence type must be EXACTLY one of: "quantitative", "qualitative", "methodological", "boundary_condition", "comparison".
8. If no relevant evidence exists in the text for this research question, return an empty array [].

Return ONLY valid JSON matching this exact structure:
{{
  "findings": [
    {{
      "claim": "Concise factual summary statement grounded in the source text.",
      "stance": "support|counter|limitation|trade_off|mixed|context",
      "confidence": "high|medium|low",
      "evidence": [
        {{
          "evidence_type": "quantitative|qualitative|methodological|boundary_condition|comparison",
          "evidence_text": "Short supporting quote or tightly grounded excerpt from text.",
          "location_in_source": "Section 4.1 or Table 2 if discernible, else null"
        }}
      ],
      "quantitative_evidence": [
        {{
          "model": "Model name (e.g. GPT-4, LLaMA-3) or null",
          "dataset": "Dataset/Benchmark name (e.g. GSM8K, MATH) or null",
          "task": "Task name or null",
          "metric": "Metric name (e.g. Accuracy %, Latency ms, Token Multiplier) or null",
          "baseline_score": 78.5,
          "experimental_score": 84.2,
          "absolute_difference": 5.7,
          "relative_difference": 7.26,
          "multiplier": "3.5x or null",
          "range_min": 64.3,
          "range_max": 71.4,
          "location_in_source": "Table 2 or Section 4 if discernible, else null"
        }}
      ]
    }}
  ]
}}
"""

        import time

        response = None
        for attempt in range(4):
            try:
                response = gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                break
            except Exception as err:
                err_str = str(err)
                if any(c in err_str for c in ("429", "RESOURCE_EXHAUSTED")):
                    time.sleep(12)
                elif any(c in err_str for c in ("503", "UNAVAILABLE", "500", "INTERNAL", "DEADLINE_EXCEEDED", "overloaded", "ServiceUnavailable")):
                    time.sleep(2 ** attempt + 2)
                else:
                    raise err

        if response is None or not response.text:
            return []

        raw_output = response.text.strip()
        parsed = _clean_and_parse_json(raw_output)
        raw_findings = parsed.get("findings", [])
        if not isinstance(raw_findings, list):
            return []

        validated_findings = []

        for item in raw_findings:
            if not isinstance(item, dict):
                continue

            claim = str(item.get("claim", "")).strip()
            if not claim:
                continue

            stance = str(item.get("stance", "context")).strip().lower()
            if stance not in ALLOWED_STANCES:
                stance = "context"

            confidence = str(item.get("confidence", "medium")).strip().lower()
            if confidence not in ALLOWED_CONFIDENCE:
                confidence = "medium"

            # Clean evidence items
            raw_ev = item.get("evidence", [])
            clean_ev = []
            if isinstance(raw_ev, list):
                for ev in raw_ev:
                    if isinstance(ev, dict):
                        ev_text = str(ev.get("evidence_text", "")).strip()
                        if not ev_text:
                            continue
                        ev_type = str(ev.get("evidence_type", "qualitative")).strip().lower()
                        if ev_type not in ALLOWED_EVIDENCE_TYPES:
                            ev_type = "qualitative"
                        loc = ev.get("location_in_source")
                        loc_str = str(loc).strip() if loc is not None else None
                        if not loc_str or loc_str.lower() in ("null", "none"):
                            loc_str = _infer_location_in_source(ev_text, content_to_use)

                        clean_ev.append({
                            "source_id": source_id,
                            "evidence_type": ev_type,
                            "evidence_text": ev_text,
                            "location_in_source": loc_str
                        })

            ev_texts = [e["evidence_text"] for e in clean_ev]

            # 1. Passage Relevance Verification
            if not _verify_passage_relevance(claim, ev_texts, question_text):
                continue

            # 1b. Question-Specific Evidence Validation
            if not _validate_finding_for_question(claim, ev_texts, question):
                continue

            # 2. Stance Calibration & Verification
            stance = _verify_and_calibrate_stance(stance, claim, ev_texts)

            # Clean quantitative evidence items
            raw_quant = item.get("quantitative_evidence", [])
            clean_quant = []
            if requires_quant and isinstance(raw_quant, list):
                for qitem in raw_quant:
                    if isinstance(qitem, dict):
                        clean_qrecord = {"source_id": source_id}
                        for field in [
                            "model", "dataset", "task", "metric",
                            "baseline_score", "experimental_score",
                            "absolute_difference", "relative_difference",
                            "multiplier", "range_min", "range_max",
                            "location_in_source"
                        ]:
                            val = qitem.get(field)
                            if field == "multiplier":
                                clean_qrecord[field] = str(val).strip() if val is not None and str(val).strip() and str(val).lower() != "null" else None
                            elif field in ("range_min", "range_max"):
                                if isinstance(val, (int, float)):
                                    clean_qrecord[field] = float(val)
                                elif isinstance(val, str) and val.strip() and val.lower() != "null":
                                    try:
                                        clean_qrecord[field] = float(val.strip().rstrip("%"))
                                    except ValueError:
                                        clean_qrecord[field] = None
                                else:
                                    clean_qrecord[field] = None
                            elif isinstance(val, (int, float)):
                                clean_qrecord[field] = val
                            elif isinstance(val, str) and val.strip() and val.lower() != "null":
                                try:
                                    clean_qrecord[field] = float(val.strip().rstrip("%"))
                                except ValueError:
                                    clean_qrecord[field] = val.strip()
                            else:
                                clean_qrecord[field] = None

                        # Ensure provenance location is populated
                        qloc = clean_qrecord.get("location_in_source")
                        if not qloc or str(qloc).lower() in ("null", "none"):
                            clean_qrecord["location_in_source"] = (
                                (clean_ev[0]["location_in_source"] if clean_ev else None)
                                or _infer_location_in_source(str(clean_qrecord.get("metric", "")), content_to_use)
                            )

                        # 3. Grounding Verification: check against source text
                        clean_qrecord = _verify_quantitative_grounding(clean_qrecord, content_to_use)

                        clean_quant.append(clean_qrecord)

            # Heuristic fallback: if quantitative is required and empty, parse from text
            if requires_quant and not clean_quant:
                try:
                    combined_text = f"{claim} " + " ".join(e.get("evidence_text", "") for e in clean_ev)
                    parsed_records = extract_heuristic_quantitative_records(combined_text, source_id, content_to_use)
                    clean_quant.extend(parsed_records)
                except Exception:
                    pass

            candidate_finding = {
                "question_id": question_id,
                "source_ids": [source_id],
                "claim": claim,
                "stance": stance,
                "confidence": confidence,
                "evidence": clean_ev,
                "quantitative_evidence": clean_quant
            }

            # Run through Evidence Validation Layer (EVL)
            is_valid, validated_f, reasons = EvidenceValidator.validate_finding(
                candidate_finding,
                question,
                source_text=content_to_use
            )

            if is_valid:
                validated_findings.append(validated_f)

        return validated_findings

    except Exception as error:
        print(f"Evidence extraction failed for {source_id} on {question_id}: {error}")
        return []


def extract_research_evidence(
    gemini_client,
    research_plan,
    selection_bundle,
    model=MODEL,
    existing_extraction_bundle: Optional[dict] = None
):
    """
    Run evidence extraction across all research questions and selected sources.
    Applies atomic finding decomposition and global multi-question evidence routing.
    Assigns stable finding IDs (Q1-F1, Q1-F2...) and constructs question-level findings and gaps.
    Preserves and merges findings across research rounds when existing_extraction_bundle is provided.
    """

    questions = research_plan.get("questions", [])
    per_question_sel = selection_bundle.get("per_question_selection", {})

    source_finding_map = {}
    all_findings_list = []
    question_raw_findings = {}

    existing_q_findings = {}
    already_extracted_sources_by_qid = {}
    if existing_extraction_bundle:
        # Carry forward existing source-finding mappings
        for sid, fids in existing_extraction_bundle.get("source_finding_map", {}).items():
            source_finding_map[sid] = list(fids)

        for q_entry in existing_extraction_bundle.get("questions", []):
            qid = str(q_entry.get("question_id", "")).strip().upper()
            findings = list(q_entry.get("findings", []))
            existing_q_findings[qid] = findings
            already_extracted_sources_by_qid[qid] = set()
            for f in findings:
                for sid in f.get("source_ids", []):
                    already_extracted_sources_by_qid[qid].add(sid)

    # Stage 1: Direct extraction and atomic decomposition per question
    for question in questions:
        question_id = str(question.get("id", "")).strip().upper()
        q_sel_data = per_question_sel.get(question_id, {})
        sel_tuples = q_sel_data.get("selected_sources", [])

        direct_findings = []
        for source, reason in sel_tuples:
            source_id = source["source_id"]
            # Check if this source or any of its known aliases has already been extracted for this question
            source_aliases = set(source.get("all_source_ids", [source_id])) | {source_id}
            if already_extracted_sources_by_qid.get(question_id) and (source_aliases & already_extracted_sources_by_qid[question_id]):
                continue

            raw_findings = extract_evidence_from_source(
                gemini_client,
                question,
                source,
                model=model
            )
            for f in raw_findings:
                atomic_findings = _decompose_complex_finding(f)
                for af in atomic_findings:
                    direct_findings.append((af, source_id))

        question_raw_findings[question_id] = direct_findings

    # Stage 2: Global multi-question evidence routing
    global_findings_pool = []
    for qid, q_findings in question_raw_findings.items():
        for f, sid in q_findings:
            global_findings_pool.append((f, sid, qid))

    # Also include existing findings for cross-question routing opportunities
    for qid, f_list in existing_q_findings.items():
        for f in f_list:
            sids = f.get("source_ids", [""])
            sid = sids[0] if sids else ""
            global_findings_pool.append((f, sid, qid))

    extracted_questions = []

    for question in questions:
        question_id = str(question.get("id", "")).strip().upper()
        q_findings = []
        q_counter_findings = []

        def _is_cross_routing_allowed(orig_q, target_q, finding_item) -> bool:
            t_text = str(target_q.get("question", "")).lower()
            t_type = str(target_q.get("type", "")).lower()
            claim_lower = str(finding_item.get("claim", "")).lower()

            is_defense_target = any(k in t_text for k in ("defense", "mitigat", "guardrail", "sanitiz", "filter", "protect", "robustness", "safeguard")) or "defense" in t_type
            is_mechanics_target = any(k in t_text for k in ("vector", "mechanic", "how do", "threat model", "taxonomy")) or "mechanisms" in t_type

            finding_evaluates_defense = any(k in claim_lower for k in ("defense", "mitigat", "guardrail", "sanitiz", "filter", "pra-rag", "detector", "detection", "perplexity", "refusal", "certified", "resilience", "countermeasure", "false positive"))

            # If target is defense evaluation: finding MUST explicitly evaluate defenses or mitigations
            if is_defense_target and not finding_evaluates_defense:
                return False

            # If target is attack mechanics: pure defense finding without mechanics is disallowed
            if is_mechanics_target and finding_evaluates_defense and not any(k in claim_lower for k in ("vector", "mechanic", "payload", "poison", "injection", "exploit")):
                return False

            # Generalized Topic Gating:
            is_speedup_comp = any(k in t_text for k in ("speedup", "speedup factor", "latency reduction", "across different draft", "draft model size"))
            is_hardware_bottleneck = any(k in t_text for k in ("hardware bottleneck", "architectural bottleneck", "memory bandwidth", "hardware setup", "cpu/gpu", "accelerator"))
            is_threshold_target = any(k in t_text for k in ("threshold", "acceptance rate", "under what", "fail to provide")) or "boundary_conditions" in t_type
            is_tradeoff_failure_target = any(k in t_text for k in ("trade-off", "tradeoff", "failure mode", "side effect", "drawback", "risk")) or "limitations" in t_type

            # If target is hardware bottleneck question: finding must discuss hardware/architecture/bottlenecks
            if is_hardware_bottleneck and not any(k in claim_lower for k in ("bottleneck", "hardware", "cpu", "gpu", "bandwidth", "memory", "cache", "interconnect", "kernel", "communication", "parallelism", "architecture")):
                return False

            # If target is trade-offs / failure modes / limitations question: finding must discuss trade-offs, degradation, overhead, failure, or limitations
            if is_tradeoff_failure_target and not is_hardware_bottleneck and not any(k in claim_lower for k in ("trade-off", "tradeoff", "fail", "degrad", "deteriorat", "overhead", "cost", "drop", "inconsistent", "limitation", "drawback", "penalty", "side effect", "ineffective")):
                return False

            # If target is speedup/latency comparative question: hardware background without speedup or draft model comparison cannot route
            if is_speedup_comp and not any(k in claim_lower for k in ("speedup", "speed-up", "latency reduction", "draft", "x speedup", "accelerat", "throughput")):
                return False

            # If target is threshold / failure question: finding must discuss failure, degradation, threshold, or acceptance rate
            if is_threshold_target and not any(k in claim_lower for k in ("threshold", "acceptance", "fail", "negat", "drop", "slower", "degrad", "overhead", "rejection", "accuracy")):
                return False

            return True

        def _is_semantically_equivalent_claim(c1: str, c2: str, threshold: float = 0.65) -> bool:
            s1 = c1.strip().lower()
            s2 = c2.strip().lower()
            if s1 == s2:
                return True
            for acr, exp in [("asr", "attack success rate"), ("em", "exact match"), ("llm", "large language model"), ("rag", "retrieval augmented generation")]:
                s1 = re.sub(rf"\b{acr}\b", exp, s1)
                s2 = re.sub(rf"\b{acr}\b", exp, s2)
            stop = {
                "the", "a", "an", "is", "are", "was", "were", "of", "in", "to",
                "and", "or", "for", "with", "on", "at", "by", "that", "this", "it"
            }
            tokens1 = {w for w in re.findall(r"\w+", s1) if w not in stop and len(w) > 2}
            tokens2 = {w for w in re.findall(r"\w+", s2) if w not in stop and len(w) > 2}
            if not tokens1 or not tokens2:
                return False
            inter = len(tokens1 & tokens2)
            union = len(tokens1 | tokens2)
            jaccard = inter / union if union > 0 else 0.0
            containment = inter / min(len(tokens1), len(tokens2))
            return max(jaccard, containment) >= threshold

        def _try_merge_or_add_finding(candidate, sid, orig_qid=None, is_pre_existing=False):
            c_claim = candidate.get("claim", "").strip()
            if not c_claim:
                return

            # Check for semantic equivalence with existing findings
            for existing in q_findings:
                if _is_semantically_equivalent_claim(c_claim, existing.get("claim", "")):
                    # Merge source IDs into existing finding
                    if sid and sid not in existing.setdefault("source_ids", []):
                        existing["source_ids"].append(sid)
                    for s in candidate.get("source_ids", []):
                        if s and s not in existing["source_ids"]:
                            existing["source_ids"].append(s)

                    # Merge quotes without duplicates
                    existing_quotes = {e.get("evidence_text", "").strip() for e in existing.get("evidence", [])}
                    for ev in candidate.get("evidence", []):
                        ev_t = ev.get("evidence_text", "").strip()
                        if ev_t and ev_t not in existing_quotes:
                            existing.setdefault("evidence", []).append(ev)
                            existing_quotes.add(ev_t)

                    # Merge quantitative metrics without duplicates
                    existing_metrics = {str(q.get("metric", "")) for q in existing.get("quantitative_evidence", [])}
                    for q in candidate.get("quantitative_evidence", []):
                        m = str(q.get("metric", ""))
                        if m not in existing_metrics:
                            existing.setdefault("quantitative_evidence", []).append(q)
                            existing_metrics.add(m)

                    fid = existing.get("finding_id")
                    if sid:
                        source_finding_map.setdefault(sid, [])
                        if fid and fid not in source_finding_map[sid]:
                            source_finding_map[sid].append(fid)
                    return

            # Enforce Source Concentration Cap for NEW findings only: max 2 findings per unique paper per question
            if not is_pre_existing and sid:
                existing_count_for_sid = sum(1 for existing in q_findings if sid in existing.get("source_ids", []))
                if existing_count_for_sid >= 2:
                    return

            # Assign finding ID: preserve existing finding_id if available and not conflicting
            existing_fids = {f.get("finding_id") for f in q_findings}
            cand_fid = candidate.get("finding_id")
            if is_pre_existing and cand_fid and cand_fid not in existing_fids:
                fid = cand_fid
            else:
                fid = f"{question_id}-F{len(q_findings) + 1}"

            new_f = dict(candidate)
            new_f["finding_id"] = fid
            new_f["question_id"] = question_id
            if orig_qid:
                new_f["routed_from_question"] = orig_qid
            new_f.setdefault("source_ids", [])
            if sid and sid not in new_f["source_ids"]:
                new_f["source_ids"].append(sid)
            for s in candidate.get("source_ids", []):
                if s and s not in new_f["source_ids"]:
                    new_f["source_ids"].append(s)

            for s in new_f.get("source_ids", []):
                source_finding_map.setdefault(s, [])
                if fid not in source_finding_map[s]:
                    source_finding_map[s].append(fid)

            q_findings.append(new_f)
            if new_f not in all_findings_list:
                all_findings_list.append(new_f)
            if new_f.get("stance") == "counter":
                q_counter_findings.append(new_f)

        # 0. Seed existing findings for this question from previous rounds
        for existing_f in existing_q_findings.get(question_id, []):
            first_sid = existing_f.get("source_ids", [None])[0] if existing_f.get("source_ids") else None
            _try_merge_or_add_finding(existing_f, first_sid, is_pre_existing=True)

        # 1. Add direct findings for this question
        for f, sid in question_raw_findings.get(question_id, []):
            _try_merge_or_add_finding(f, sid)

        # 2. Cross-route relevant findings from other questions (Global Evidence Routing)
        for other_f, sid, orig_qid in global_findings_pool:
            if orig_qid == question_id:
                continue

            # Archetype gating: prevent incompatible cross-routing (e.g. pure attack into defense question)
            if not _is_cross_routing_allowed(orig_qid, question, other_f):
                continue

            # Strict EVL gate on candidate finding for this target question
            is_valid, validated_routed, reasons = EvidenceValidator.validate_finding(
                other_f,
                question,
                source_text=""
            )
            if is_valid:
                # If target question requires quantitative evidence and routed finding has no valid quantitative records for it,
                # re-extract heuristic quantitative records tailored to this target question from the finding's text
                if question.get("requires_quantitative_evidence") and not validated_routed.get("quantitative_evidence"):
                    comb_text = f"{validated_routed.get('claim', '')} " + " ".join(e.get("evidence_text", "") for e in validated_routed.get("evidence", []))
                    parsed_quants = extract_heuristic_quantitative_records(comb_text, sid)
                    if parsed_quants:
                        q_ok, clean_parsed, _ = EvidenceValidator.validate_quantitative_validity(
                            {"quantitative_evidence": parsed_quants},
                            question,
                            ""
                        )
                if question.get("requires_quantitative_evidence") and not validated_routed.get("quantitative_evidence") and validated_routed.get("stance") != "counter":
                    # Do not route non-quantitative non-counter findings into a question requiring quantitative evidence
                    continue

                _try_merge_or_add_finding(validated_routed, sid, orig_qid=orig_qid)

        # Determine evidence readiness status
        req_quant = bool(question.get("requires_quantitative_evidence", False))
        req_counter = bool(question.get("requires_counter_evidence", False))

        has_quant = any(len(f.get("quantitative_evidence", [])) > 0 for f in q_findings)
        has_counter = len(q_counter_findings) > 0

        gaps = []
        if not q_findings:
            gaps.append("No findings extracted from selected sources for this question.")
        if req_quant and not has_quant:
            gaps.append("Quantitative evidence required by Planner, but no quantitative records extracted.")
        if req_counter and not has_counter:
            gaps.append("Counter evidence required by Planner, but no actual counter stance findings extracted.")

        if not q_findings:
            status = "insufficient"
        elif (req_quant and not has_quant) or (req_counter and not has_counter):
            status = "partial"
        else:
            status = "complete_candidate"

        extracted_questions.append({
            "question_id": question_id,
            "question": question.get("question", ""),
            "status": status,
            "findings": q_findings,
            "counter_evidence": q_counter_findings,
            "evidence_gaps": gaps
        })

    return {
        "questions": extracted_questions,
        "source_finding_map": source_finding_map,
        "all_findings": all_findings_list
    }
