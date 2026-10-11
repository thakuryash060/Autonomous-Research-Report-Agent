import re
from typing import Dict, Any, List, Set, Tuple


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "me", "more", "most", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves",
    "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}

TESTABLE_CUES = {
    "increase", "decrease", "reduce", "higher", "lower", "exceed", "fall",
    "outperform", "degrade", "trade-off", "tradeoff", "overhead", "latency",
    "accuracy", "f1", "error", "rate", "threshold", "significant", "percent",
    "gain", "loss", "diverge", "converge", "baseline", "relative"
}


def _tokenize(text: str) -> Set[str]:
    tokens = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", str(text).lower())
    return {t for t in tokens if t not in STOPWORDS}


def _jaccard_similarity(s1: Set[str], s2: Set[str]) -> float:
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def evaluate_plan_quality(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Empirically evaluate the scientific quality, feasibility, and calibration
    of a Phase 1 Research Plan across 4 core axes:

    1. Specificity (0.30): Variable, metric, and boundary condition clarity.
    2. Falsifiability (0.25): Non-trivial hypotheses, competing explanations, and refutation criteria.
    3. Facet Coverage (0.25): Inquiry diversity across priority tiers and question scopes.
    4. Query Orthogonality (0.20): Search query independence (minimizing token/retrieval overlap).
    """
    questions = plan.get("questions", [])
    if not questions:
        return {
            "overall_score": 0.0,
            "grade": "F",
            "is_sound": False,
            "breakdown": {},
            "issues": ["Plan contains no research questions."]
        }

    issues: List[str] = []

    # -------------------------------------------------------------
    # 1. SPECIFICITY SCORE (0.30)
    # -------------------------------------------------------------
    spec_points = 0.0
    total_q = len(questions)

    for q in questions:
        q_score = 0.0
        # Measurable quantitative requirements
        if q.get("requires_quantitative_evidence"):
            q_fields = q.get("quantitative_fields", [])
            if q_fields:
                q_score += 0.4
        else:
            q_score += 0.2  # Qualitative questions have valid place

        # Explicit evidence needed
        ev_needed = q.get("evidence_needed", [])
        if len(ev_needed) >= 2:
            q_score += 0.3
        elif len(ev_needed) == 1:
            q_score += 0.15

        # Boundary conditions
        b_conds = q.get("boundary_conditions", [])
        if b_conds:
            q_score += 0.3

        spec_points += min(1.0, q_score)

    specificity_score = round(spec_points / total_q, 4) if total_q > 0 else 0.0

    # -------------------------------------------------------------
    # 2. FALSIFIABILITY & COMPETING EXPLANATIONS SCORE (0.25)
    # -------------------------------------------------------------
    fals_score = 0.0
    hyp = str(plan.get("hypothesis", "")).strip()
    competing = plan.get("competing_hypotheses", [])
    fals_criteria = plan.get("falsification_criteria", [])

    if hyp and len(hyp) >= 15:
        fals_score += 0.25
        # Check if hypothesis contains testable direction/relation
        hyp_tokens = _tokenize(hyp)
        if hyp_tokens & TESTABLE_CUES:
            fals_score += 0.15
        else:
            issues.append("Primary hypothesis lacks explicit comparative or directional test criteria.")

    if competing and isinstance(competing, list) and len(competing) >= 1:
        fals_score += 0.30
        # Check orthogonality between primary and competing hypotheses
        hyp_tok = _tokenize(hyp)
        for idx, comp in enumerate(competing):
            comp_tok = _tokenize(str(comp))
            sim = _jaccard_similarity(hyp_tok, comp_tok)
            if sim > 0.85:
                issues.append(f"Competing hypothesis #{idx+1} is nearly identical to primary hypothesis (sim: {sim:.2f}).")
    else:
        issues.append("No competing hypotheses defined to counter-balance confirmation bias.")

    if fals_criteria and isinstance(fals_criteria, list) and len(fals_criteria) >= 1:
        fals_score += 0.30
    else:
        issues.append("No falsification criteria defined.")

    falsifiability_score = round(min(1.0, fals_score), 4)

    # -------------------------------------------------------------
    # 3. FACET & PRIORITY COVERAGE (0.25)
    # -------------------------------------------------------------
    priorities = {str(q.get("priority", "")).lower() for q in questions}
    has_high = "high" in priorities
    has_med_or_low = bool(priorities & {"medium", "low"})

    facet_score = 0.0
    if has_high:
        facet_score += 0.4
    if has_med_or_low:
        facet_score += 0.2

    # Check question types / scopes
    q_types = {str(q.get("type", "")).lower() for q in questions}
    if len(q_types) >= 2:
        facet_score += 0.4
    else:
        facet_score += 0.2

    facet_coverage_score = round(min(1.0, facet_score), 4)

    # -------------------------------------------------------------
    # 4. QUERY ORTHOGONALITY (0.20)
    # -------------------------------------------------------------
    all_queries: List[str] = []
    for q in questions:
        strat = q.get("search_strategy", {})
        for qkey in ("primary_queries", "secondary_queries", "counter_evidence_queries"):
            qlist = strat.get(qkey, [])
            if isinstance(qlist, list):
                all_queries.extend([str(x) for x in qlist if x])

    if len(all_queries) >= 2:
        query_token_sets = [_tokenize(q) for q in all_queries if q.strip()]
        pairwise_sims = []
        for i in range(len(query_token_sets)):
            for j in range(i + 1, len(query_token_sets)):
                s = _jaccard_similarity(query_token_sets[i], query_token_sets[j])
                pairwise_sims.append(s)

        avg_overlap = sum(pairwise_sims) / len(pairwise_sims) if pairwise_sims else 0.0
        # High orthogonality = low overlap
        orthogonality_score = round(max(0.0, 1.0 - avg_overlap), 4)
        if avg_overlap > 0.60:
            issues.append(f"Search queries exhibit high pairwise redundancy (average overlap {avg_overlap:.2f}).")
    else:
        orthogonality_score = 0.5

    # -------------------------------------------------------------
    # AGGREGATE CALIBRATED BENCHMARK SCORE
    # -------------------------------------------------------------
    overall_score = round(
        0.30 * specificity_score +
        0.25 * falsifiability_score +
        0.25 * facet_coverage_score +
        0.20 * orthogonality_score,
        4
    )

    if overall_score >= 0.85:
        grade = "A (Exemplary)"
    elif overall_score >= 0.70:
        grade = "B (Scientifically Sound)"
    elif overall_score >= 0.55:
        grade = "C (Marginal / Needs Refinement)"
    else:
        grade = "D (Poor / Ill-Calibrated)"

    is_sound = overall_score >= 0.60 and len(issues) <= 2

    return {
        "overall_score": overall_score,
        "grade": grade,
        "is_sound": is_sound,
        "breakdown": {
            "specificity": specificity_score,
            "falsifiability": falsifiability_score,
            "facet_coverage": facet_coverage_score,
            "query_orthogonality": orthogonality_score,
        },
        "issues": issues
    }

