import math
from typing import Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel

from .claim_normalizer import NormalizedClaim


class MetricOntologyEntry(BaseModel):
    name: str
    family: str
    higher_is_better: bool = True
    complement_metric: Optional[str] = None   # e.g., error_rate = 1.0 - accuracy (for probabilities)
    reciprocal_metric: Optional[str] = None   # e.g., throughput = 1.0 / latency_s


# Formal scientific metric dictionary
METRIC_ONTOLOGY: Dict[str, MetricOntologyEntry] = {
    "accuracy": MetricOntologyEntry(name="accuracy", family="accuracy", higher_is_better=True, complement_metric="error_rate"),
    "error_rate": MetricOntologyEntry(name="error_rate", family="accuracy", higher_is_better=False, complement_metric="accuracy"),
    "f1": MetricOntologyEntry(name="f1", family="f1", higher_is_better=True),
    "macro_f1": MetricOntologyEntry(name="macro_f1", family="f1", higher_is_better=True),
    "micro_f1": MetricOntologyEntry(name="micro_f1", family="f1", higher_is_better=True),
    "latency": MetricOntologyEntry(name="latency", family="latency", higher_is_better=False, reciprocal_metric="throughput"),
    "latency_ms": MetricOntologyEntry(name="latency_ms", family="latency", higher_is_better=False, reciprocal_metric="throughput"),
    "throughput": MetricOntologyEntry(name="throughput", family="latency", higher_is_better=True, reciprocal_metric="latency"),
    "tokens_per_second": MetricOntologyEntry(name="tokens_per_second", family="latency", higher_is_better=True, reciprocal_metric="latency"),
    "bleu": MetricOntologyEntry(name="bleu", family="generation", higher_is_better=True),
    "rouge": MetricOntologyEntry(name="rouge", family="generation", higher_is_better=True),
    "perplexity": MetricOntologyEntry(name="perplexity", family="language", higher_is_better=False),
    "loss": MetricOntologyEntry(name="loss", family="loss", higher_is_better=False),
}


class StatisticalComparisonResult(BaseModel):
    verdict: Literal[
        "DIRECTIONAL_CONFLICT",
        "STATISTICALLY_EQUIVALENT",
        "CONSISTENT_EFFECT",
        "STATISTICAL_INDETERMINATE",
        "INCOMPARABLE_METRIC"
    ]
    effect_difference: Optional[float] = None
    confidence_interval_overlaps: Optional[bool] = None
    is_statistically_significant: bool = False
    details: str = ""


def harmonize_metric_values(
    val: float,
    metric_from: str,
    metric_target: str
) -> Optional[float]:
    """
    Carefully harmonize metric values using formal mathematical relationships:
    - Complements: Accuracy 0.98 <-> Error Rate 0.02
    - Percent to Probability: 98% -> 0.98
    """
    m_from = metric_from.lower().strip()
    m_to = metric_target.lower().strip()
    if m_from == m_to:
        return val

    entry_from = METRIC_ONTOLOGY.get(m_from)
    if entry_from and entry_from.complement_metric == m_to:
        # Check if values are in [0, 100] or [0, 1]
        if val > 1.0:
            return 100.0 - val
        return 1.0 - val

    return None


def compare_statistical_claims(
    claim_a: NormalizedClaim,
    claim_b: NormalizedClaim,
    epsilon: float = 0.02
) -> StatisticalComparisonResult:
    """
    Empirically compare two quantitative claims using statistical rigor:
    - Tests for directional disagreement.
    - Evaluates equivalence margins (|Δ| <= epsilon).
    - Checks confidence interval overlap when intervals are available.
    - Returns STATISTICAL_INDETERMINATE if crucial variance is unknown.
    """
    # 1. Metric Family Check
    fam_a = claim_a.conditions.metric_family.lower()
    fam_b = claim_b.conditions.metric_family.lower()
    if fam_a != fam_b and "performance" not in (fam_a, fam_b):
        return StatisticalComparisonResult(
            verdict="INCOMPARABLE_METRIC",
            details=f"Metrics belong to different scientific families ({fam_a} vs {fam_b})"
        )

    # 2. Check if numerical magnitudes exist
    mag_a = claim_a.magnitude
    mag_b = claim_b.magnitude
    if mag_a is None or mag_b is None:
        return StatisticalComparisonResult(
            verdict="STATISTICAL_INDETERMINATE",
            details="One or both claims lack numerical magnitude; defer to linguistic NLI."
        )

    # Harmonize metrics if necessary
    m_a = claim_a.conditions.metric_name
    m_b = claim_b.conditions.metric_name
    if m_a != m_b:
        harmonized_b = harmonize_metric_values(mag_b, m_b, m_a)
        if harmonized_b is not None:
            mag_b = harmonized_b
        else:
            return StatisticalComparisonResult(
                verdict="INCOMPARABLE_METRIC",
                details=f"Incompatible metric types without known transformation ({m_a} vs {m_b})"
            )

    # 3. Normalized Directions Check
    dir_a = claim_a.normalized_direction  # +1 gain, -1 degradation, 0 neutral
    dir_b = claim_b.normalized_direction

    diff = abs(mag_a - mag_b)

    # 4. Confidence Interval Overlap Analysis
    ci_a = claim_a.uncertainty.confidence_interval
    ci_b = claim_b.uncertainty.confidence_interval
    ci_overlap = None

    if ci_a and ci_b:
        ci_overlap = not (ci_a[1] < ci_b[0] or ci_b[1] < ci_a[0])

    # 5. Directional Conflict Evaluation
    if dir_a != 0 and dir_b != 0 and dir_a != dir_b:
        # Opposing normalized directions (e.g. Paper A reports +10% gain, Paper B reports -5% loss)
        if diff > epsilon:
            if ci_overlap is False:
                # Strong statistical conflict: opposing directions and non-overlapping CIs
                return StatisticalComparisonResult(
                    verdict="DIRECTIONAL_CONFLICT",
                    effect_difference=diff,
                    confidence_interval_overlaps=False,
                    is_statistically_significant=True,
                    details=f"Opposing normalized directions with non-overlapping CIs (|Δ|={diff:.3f} > {epsilon})"
                )
            elif ci_overlap is True:
                # Overlapping CIs means true difference is uncertain
                return StatisticalComparisonResult(
                    verdict="STATISTICAL_INDETERMINATE",
                    effect_difference=diff,
                    confidence_interval_overlaps=True,
                    is_statistically_significant=False,
                    details="Opposing point estimates, but confidence intervals overlap."
                )
            else:
                # No CI provided -> directional conflict with unverified variance
                return StatisticalComparisonResult(
                    verdict="DIRECTIONAL_CONFLICT",
                    effect_difference=diff,
                    confidence_interval_overlaps=None,
                    is_statistically_significant=False,
                    details=f"Opposing normalized directions (|Δ|={diff:.3f} > {epsilon}); CIs unstated in text."
                )

    # 6. Same Direction: Check Equivalence Margin
    if diff <= epsilon:
        return StatisticalComparisonResult(
            verdict="STATISTICALLY_EQUIVALENT",
            effect_difference=diff,
            confidence_interval_overlaps=ci_overlap,
            details=f"Effect sizes fall within equivalence margin (|Δ|={diff:.3f} <= {epsilon})"
        )

    return StatisticalComparisonResult(
        verdict="CONSISTENT_EFFECT",
        effect_difference=diff,
        confidence_interval_overlaps=ci_overlap,
        details=f"Both papers report consistent direction of effect (|Δ|={diff:.3f})"
    )

