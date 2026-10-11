import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .divergence_analyzer import ContradictionMatrixEntry, ConflictTaxonomy
from .claim_normalizer import NormalizedClaim


class EvidenceGap(BaseModel):
    gap_id: str
    target_pair_id: str
    gap_type: str  # "STATISTICAL_UNCERTAINTY", "METHODOLOGICAL_DISPARITY", "MISSING_FULL_TEXT", "REPLICATION_DEFICIT"
    missing_variables: List[str] = Field(default_factory=list)
    recommended_search_query: str
    expected_info_gain: float = 0.8  # I(q)
    gap_relevance: float = 0.9       # R(q)
    estimated_cost: float = 1.0      # Cost(q)
    utility_score: float = 0.0       # U(q)
    action: str = "SEARCH"           # "SEARCH" or "ABSTAIN"


def compute_gap_utility(info_gain: float, relevance: float, cost: float = 1.0, lam: float = 0.1) -> float:
    """
    Formal expected utility function:
    U(q) = (P(gap resolved | q) * I(q) * R(q)) / (Cost(q) + lambda)
    """
    p_resolved = 0.75  # Empirical prior
    numerator = p_resolved * info_gain * relevance
    denominator = cost + lam
    return round(numerator / denominator, 4)


class EvidenceGapPlanner:
    """
    Plans targeted literature queries to resolve specific empirical gaps
    identified in the Contradiction Matrix.
    """
    def __init__(self, utility_threshold: float = 0.40, max_re_search_rounds: int = 3):
        self.utility_threshold = utility_threshold
        self.max_re_search_rounds = max_re_search_rounds

    def plan_gaps(
        self,
        unresolved_entries: List[ContradictionMatrixEntry],
        claims_by_id: Dict[str, NormalizedClaim],
        current_round: int = 1
    ) -> List[EvidenceGap]:
        if current_round > self.max_re_search_rounds:
            return []

        gaps = []
        gap_counter = 1

        for entry in unresolved_entries:
            if entry.classification not in (ConflictTaxonomy.GENUINE_EMPIRICAL_CONFLICT, ConflictTaxonomy.INSUFFICIENT_EVIDENCE):
                continue

            c_a = claims_by_id.get(entry.claim_a_id)
            c_b = claims_by_id.get(entry.claim_b_id)
            if not c_a or not c_b:
                continue

            # Identify missing information
            var = c_a.outcome_variable
            dataset = c_a.conditions.dataset
            model_a = c_a.conditions.model_architecture or "model"
            model_b = c_b.conditions.model_architecture or "baseline"

            if entry.statistical_result and entry.statistical_result.confidence_interval_overlaps is None:
                gap_type = "STATISTICAL_UNCERTAINTY"
                query = f'"{dataset}" "{var}" standard deviation confidence interval variance'
                info_gain = 0.85
                relevance = 0.90
            elif entry.classification == ConflictTaxonomy.GENUINE_EMPIRICAL_CONFLICT:
                gap_type = "REPLICATION_DEFICIT"
                query = f'"{model_a}" vs "{model_b}" on {dataset} {var} comparison benchmark'
                info_gain = 0.80
                relevance = 0.95
            else:
                gap_type = "METHODOLOGICAL_DISPARITY"
                query = f'{dataset} {var} evaluation setup hyperparameters'
                info_gain = 0.60
                relevance = 0.70

            utility = compute_gap_utility(info_gain, relevance, cost=1.0)
            action = "SEARCH" if utility >= self.utility_threshold else "ABSTAIN"

            gaps.append(EvidenceGap(
                gap_id=f"GAP-{gap_counter:02d}",
                target_pair_id=entry.pair_id,
                gap_type=gap_type,
                missing_variables=[var, dataset],
                recommended_search_query=query,
                expected_info_gain=info_gain,
                gap_relevance=relevance,
                utility_score=utility,
                action=action
            ))
            gap_counter += 1

        return gaps

