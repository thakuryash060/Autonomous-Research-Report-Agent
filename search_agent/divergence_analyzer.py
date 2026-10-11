from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .claim_normalizer import NormalizedClaim
from .pair_generator import ClaimPairCandidate
from .statistical_comparator import StatisticalComparisonResult, compare_statistical_claims
from .bidirectional_nli import BidirectionalNLIResult, evaluate_bidirectional_nli


class ConflictTaxonomy(str, Enum):
    GENUINE_EMPIRICAL_CONFLICT = "GENUINE_EMPIRICAL_CONFLICT"
    EXPLAINED_CONTRADICTION = "EXPLAINED_CONTRADICTION"
    INCOMPARABLE = "INCOMPARABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_CONFLICT = "NO_CONFLICT"


class ExplanationVerificationStatus(str, Enum):
    VERIFIED_EXPLANATION = "VERIFIED_EXPLANATION"
    PLAUSIBLE_EXPLANATION = "PLAUSIBLE_EXPLANATION"
    UNEXPLAINED = "UNEXPLAINED"


class ContradictionMatrixEntry(BaseModel):
    pair_id: str
    claim_a_id: str
    claim_b_id: str
    paper_a_id: str
    paper_b_id: str
    classification: ConflictTaxonomy
    explanation_status: ExplanationVerificationStatus
    divergent_conditions: List[str] = Field(default_factory=list)
    explanation_rationale: str = ""
    statistical_result: Optional[StatisticalComparisonResult] = None
    nli_result: Optional[BidirectionalNLIResult] = None
    epistemic_confidence: float = 0.80


def analyze_divergence(
    pair: ClaimPairCandidate,
    gemini_client=None
) -> ContradictionMatrixEntry:
    """
    Perform deep causal divergence analysis on a candidate pair:
    1. Checks statistical comparability.
    2. Runs bidirectional NLI if ambiguous or qualitative.
    3. Analyzes experimental conditions to separate Explained from Genuine conflicts.
    4. Evaluates explanation verification status (VERIFIED vs PLAUSIBLE vs UNEXPLAINED).
    """
    c1 = pair.claim_a
    c2 = pair.claim_b

    # Step 1: Incomparability Check
    if not pair.is_compatible:
        return ContradictionMatrixEntry(
            pair_id=pair.pair_id,
            claim_a_id=c1.claim_id,
            claim_b_id=c2.claim_id,
            paper_a_id=c1.paper_id,
            paper_b_id=c2.paper_id,
            classification=ConflictTaxonomy.INCOMPARABLE,
            explanation_status=ExplanationVerificationStatus.PLAUSIBLE_EXPLANATION,
            explanation_rationale=pair.incompatibility_reason or "Incompatible experimental tasks or metrics.",
            epistemic_confidence=0.90
        )

    # Step 2: Statistical Test
    stat_res = compare_statistical_claims(c1, c2)
    nli_res = None

    # Step 3: Bidirectional NLI if qualitative or indeterminate
    has_conflict = False
    if stat_res.verdict == "DIRECTIONAL_CONFLICT":
        has_conflict = True
    elif stat_res.verdict in ("STATISTICAL_INDETERMINATE", "CONSISTENT_EFFECT"):
        nli_res = evaluate_bidirectional_nli(c1, c2, gemini_client=gemini_client)
        if nli_res.verdict in ("CONTRADICTION", "ASYMMETRIC_CONFLICT"):
            has_conflict = True
    elif stat_res.verdict == "STATISTICALLY_EQUIVALENT":
        return ContradictionMatrixEntry(
            pair_id=pair.pair_id,
            claim_a_id=c1.claim_id,
            claim_b_id=c2.claim_id,
            paper_a_id=c1.paper_id,
            paper_b_id=c2.paper_id,
            classification=ConflictTaxonomy.NO_CONFLICT,
            explanation_status=ExplanationVerificationStatus.VERIFIED_EXPLANATION,
            statistical_result=stat_res,
            explanation_rationale="Findings are statistically equivalent within tolerance bounds.",
            epistemic_confidence=0.88
        )

    if not has_conflict:
        return ContradictionMatrixEntry(
            pair_id=pair.pair_id,
            claim_a_id=c1.claim_id,
            claim_b_id=c2.claim_id,
            paper_a_id=c1.paper_id,
            paper_b_id=c2.paper_id,
            classification=ConflictTaxonomy.NO_CONFLICT,
            explanation_status=ExplanationVerificationStatus.VERIFIED_EXPLANATION,
            statistical_result=stat_res,
            nli_result=nli_res,
            explanation_rationale="No empirical or linguistic conflict detected between claims.",
            epistemic_confidence=0.85
        )

    # Step 4: Causal Condition Divergence Checking
    divergences = []
    # Dataset divergence
    if c1.conditions.dataset.lower() != c2.conditions.dataset.lower():
        divergences.append(f"dataset ({c1.conditions.dataset} vs {c2.conditions.dataset})")

    # Model architecture / size divergence
    m1 = c1.conditions.model_architecture or "unspecified"
    m2 = c2.conditions.model_architecture or "unspecified"
    if m1.lower() != m2.lower():
        divergences.append(f"model architecture ({m1} vs {m2})")

    # Hardware environment divergence
    if c1.conditions.hardware and c2.conditions.hardware and c1.conditions.hardware != c2.conditions.hardware:
        divergences.append(f"hardware ({c1.conditions.hardware} vs {c2.conditions.hardware})")

    # Temporal shift
    if pair.temporal_shift_detected:
        divergences.append(f"evaluation timeline ({pair.temporal_delta_years} years difference)")

    # Decontextualization caveats
    if c1.is_contextually_qualified or c2.is_contextually_qualified:
        all_negs = c1.negators_detected + c2.negators_detected
        divergences.append(f"boundary qualifiers ({', '.join(all_negs)})")

    # Step 5: Classify into Explained vs Genuine Conflict
    if divergences:
        # Methodological difference exists -> EXPLAINED_CONTRADICTION
        explanation_status = ExplanationVerificationStatus.PLAUSIBLE_EXPLANATION
        # If controlled benchmarks or boundary qualifiers exist, elevate to VERIFIED
        if c1.is_contextually_qualified or c2.is_contextually_qualified or "dataset" in divergences[0]:
            explanation_status = ExplanationVerificationStatus.VERIFIED_EXPLANATION

        return ContradictionMatrixEntry(
            pair_id=pair.pair_id,
            claim_a_id=c1.claim_id,
            claim_b_id=c2.claim_id,
            paper_a_id=c1.paper_id,
            paper_b_id=c2.paper_id,
            classification=ConflictTaxonomy.EXPLAINED_CONTRADICTION,
            explanation_status=explanation_status,
            divergent_conditions=divergences,
            statistical_result=stat_res,
            nli_result=nli_res,
            explanation_rationale=f"Divergence explained by methodological variation in {'; '.join(divergences)}.",
            epistemic_confidence=0.82
        )
    else:
        # Conditions are identical, yet results conflict -> GENUINE_EMPIRICAL_CONFLICT
        return ContradictionMatrixEntry(
            pair_id=pair.pair_id,
            claim_a_id=c1.claim_id,
            claim_b_id=c2.claim_id,
            paper_a_id=c1.paper_id,
            paper_b_id=c2.paper_id,
            classification=ConflictTaxonomy.GENUINE_EMPIRICAL_CONFLICT,
            explanation_status=ExplanationVerificationStatus.UNEXPLAINED,
            statistical_result=stat_res,
            nli_result=nli_res,
            explanation_rationale="Identical experimental conditions produce statistically significant opposing outcomes.",
            epistemic_confidence=0.86
        )

