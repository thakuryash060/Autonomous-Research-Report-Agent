import re
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

from .claim_normalizer import NormalizedClaim, ClaimScope


class ClaimPairCandidate(BaseModel):
    """A pair of claims originating from distinct papers ready for comparative synthesis."""
    pair_id: str
    claim_a: NormalizedClaim
    claim_b: NormalizedClaim
    is_compatible: bool = True
    incompatibility_reason: Optional[str] = None
    compatibility_score: float = 1.0
    temporal_delta_years: Optional[int] = None
    temporal_shift_detected: bool = False
    requires_statistical_test: bool = True
    requires_nli: bool = False


def _token_jaccard(t1: str, t2: str) -> float:
    s1 = set(re.findall(r"\b\w{2,}\b", (t1 or "").lower()))
    s2 = set(re.findall(r"\b\w{2,}\b", (t2 or "").lower()))
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def evaluate_claim_compatibility(c1: NormalizedClaim, c2: NormalizedClaim) -> Tuple[bool, float, Optional[str]]:
    """
    Apply hard constraints and soft compatibility functions C(A, B).
    Returns: (is_compatible, score, incompatibility_reason)
    """
    # Hard Constraint 1: Distinct Papers
    if c1.paper_id == c2.paper_id:
        return False, 0.0, "Same source paper (intra-study comparison)"

    # Hard Constraint 2: Metric Family Compatibility
    f1 = c1.conditions.metric_family.lower()
    f2 = c2.conditions.metric_family.lower()
    if f1 != f2 and f1 != "performance" and f2 != "performance":
        return False, 0.0, f"Incompatible metric families ({f1} vs {f2})"

    # Hard Constraint 3: Disjoint Claim Scopes
    if c1.claim_scope == ClaimScope.SUBGROUP_LEVEL and c2.claim_scope == ClaimScope.PAPER_LEVEL:
        # Don't directly contradict an aggregate paper claim with a narrow subgroup claim
        return False, 0.2, "Scope mismatch (paper-level aggregate vs narrow subgroup)"

    # Soft Compatibility Scoring C(A, B)
    # Metric score
    metric_sim = 1.0 if c1.conditions.metric_name == c2.conditions.metric_name else 0.7
    # Dataset score
    d1 = c1.conditions.dataset.lower()
    d2 = c2.conditions.dataset.lower()
    if d1 == d2 or "general" in (d1, d2) or "standard" in (d1, d2):
        dataset_sim = 1.0
    else:
        # Different evaluation benchmarks within same metric family are comparable and route to Explained Contradiction
        dataset_sim = max(_token_jaccard(d1, d2), 0.50)


    # Outcome variable score
    outcome_sim = _token_jaccard(c1.outcome_variable, c2.outcome_variable)

    # Model setting score
    m1 = str(c1.conditions.model_architecture or "").lower()
    m2 = str(c2.conditions.model_architecture or "").lower()
    model_sim = 1.0 if (m1 == m2 or not m1 or not m2) else _token_jaccard(m1, m2)

    comp_score = round(
        0.35 * metric_sim +
        0.35 * dataset_sim +
        0.15 * outcome_sim +
        0.15 * model_sim,
        4
    )

    is_compat = comp_score >= 0.45
    reason = None if is_compat else f"Low overall experimental comparability (score: {comp_score})"
    return is_compat, comp_score, reason


def generate_candidate_pairs(claims: List[NormalizedClaim]) -> List[ClaimPairCandidate]:
    """
    Generate bounded candidate pairs across normalized claims.
    Enforces hard compatibility gates and records temporal version shifts.
    """
    candidates = []
    pair_counter = 1

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            c1 = claims[i]
            c2 = claims[j]

            # Evaluate hard & soft compatibility
            is_compat, comp_score, incomp_reason = evaluate_claim_compatibility(c1, c2)

            # Temporal awareness
            year1 = c1.publication_year
            year2 = c2.publication_year
            t_delta = abs(year1 - year2) if (year1 and year2) else None
            temporal_shift = t_delta is not None and t_delta >= 3

            # Determine whether rule/statistical check vs NLI is needed
            has_numbers = (c1.magnitude is not None) and (c2.magnitude is not None)
            requires_stat = has_numbers and is_compat
            requires_nli = (not has_numbers) and is_compat

            pair = ClaimPairCandidate(
                pair_id=f"PAIR-{pair_counter:03d}",
                claim_a=c1,
                claim_b=c2,
                is_compatible=is_compat,
                incompatibility_reason=incomp_reason,
                compatibility_score=comp_score,
                temporal_delta_years=t_delta,
                temporal_shift_detected=temporal_shift,
                requires_statistical_test=requires_stat,
                requires_nli=requires_nli
            )
            candidates.append(pair)
            pair_counter += 1

    return candidates
