import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Literal
from pydantic import BaseModel, Field

from .evidence_lineage import GLOBAL_LINEAGE_REGISTRY, EvidenceLineageRecord


SEMANTIC_NEGATORS = {
    "however", "although", "except", "contrary", "whereas",
    "synthetic", "clean synthetic", "noiseless", "controlled setting",
    "limited to", "restricted to", "only when", "provided that",
    "preliminary", "hypothetical", "caution", "overfitting"
}

MODAL_HEDGING_WEIGHTS = {
    "proves": 0.95,
    "demonstrates": 0.85,
    "shows": 0.80,
    "indicates": 0.70,
    "suggests": 0.55,
    "hints": 0.45,
    "speculates": 0.30,
    "hypothesizes": 0.35,
}


class ClaimScope(str, Enum):
    PAPER_LEVEL = "paper_level"
    EXPERIMENT_LEVEL = "experiment_level"
    DATASET_LEVEL = "dataset_level"
    SUBGROUP_LEVEL = "subgroup_level"


class NormalizedConditions(BaseModel):
    dataset: str = "general"
    dataset_version: Optional[str] = None
    split: str = "test"
    model_architecture: Optional[str] = None
    model_size: Optional[str] = None
    metric_name: str = "accuracy"
    metric_family: str = "accuracy"
    hardware: Optional[str] = None
    evaluation_year: Optional[int] = None


class ClaimUncertainty(BaseModel):
    confidence_interval: Optional[Tuple[float, float]] = None
    confidence_level: Optional[float] = 0.95
    p_value: Optional[float] = None
    std_dev: Optional[float] = None
    sample_size: Optional[int] = None
    modal_hedging_score: float = 0.80


class NormalizedClaim(BaseModel):
    """
    Schema v2.0: Canonical Epistemic Claim Model.
    Carries full experimental context, statistical uncertainty,
    provenance lineage, and decontextualization indicators.
    """
    claim_id: str
    paper_id: str
    paper_title: str
    doi: Optional[str] = None
    publication_year: Optional[int] = None
    claim_scope: ClaimScope = ClaimScope.EXPERIMENT_LEVEL

    # Outcome & Impact
    outcome_variable: str
    direction: Literal["increase", "decrease", "no_effect"]
    normalized_direction: int = 1  # +1 for improvement, -1 for degradation, 0 neutral
    magnitude: Optional[float] = None
    magnitude_type: Literal["absolute_points", "relative_percent", "multiplier", "qualitative"] = "qualitative"

    # Comparison Context
    baseline: Optional[str] = None
    intervention: Optional[str] = None

    # Experimental Conditions
    conditions: NormalizedConditions

    # Statistical Rigor
    uncertainty: ClaimUncertainty

    # Provenance & Lineage
    verbatim_quote: str
    page_number: Optional[int] = None
    section_or_table: Optional[str] = None
    lineage_id: str = ""
    negators_detected: List[str] = Field(default_factory=list)
    is_contextually_qualified: bool = False


def scan_parent_context_for_negators(quote: str, parent_text: str, radius_words: int = 200) -> List[str]:
    """
    Close the 'Decontextualization Loophole':
    Inspects a ±radius_words window around the verbatim quote for semantic caveats
    (e.g., 'assuming clean synthetic inputs', 'however', 'limited to').
    """
    if not quote or not parent_text:
        return []

    q_lower = quote.strip().lower()
    p_lower = parent_text.lower()
    idx = p_lower.find(q_lower)
    if idx == -1:
        # Quote not found exactly; search full parent text for prominent caveats
        window_text = p_lower
    else:
        # Extract ±radius_words surrounding text
        words_before = p_lower[:idx].split()[-radius_words:]
        words_after = p_lower[idx + len(q_lower):].split()[:radius_words]
        window_text = " ".join(words_before + [q_lower] + words_after)

    found = []
    for neg in SEMANTIC_NEGATORS:
        if re.search(r"\b" + re.escape(neg) + r"\b", window_text):
            found.append(neg)
    return sorted(list(set(found)))


def infer_modal_hedging_score(text: str) -> float:
    """Calculate an epistemic confidence discount based on linguistic modal verbs."""
    text_lower = text.lower()
    scores = []
    for verb, score in MODAL_HEDGING_WEIGHTS.items():
        if re.search(r"\b" + verb + r"\b", text_lower):
            scores.append(score)
    return min(scores) if scores else 0.80


def normalize_raw_finding(
    raw_finding: Dict[str, Any],
    source: Dict[str, Any],
    claim_id: str,
    parent_context: str = ""
) -> NormalizedClaim:
    """
    Transform an atomic finding from Phase 2 into a Schema v2.0 NormalizedClaim
    with cryptographic evidence lineage.
    """
    claim_text = str(raw_finding.get("claim", "")).strip()
    source_id = str(source.get("source_id", "UNKNOWN")).strip().upper()
    title = str(source.get("title", "")).strip()
    doi = source.get("doi")
    pub_year = source.get("publication_year")

    # Extract primary evidence quote and location
    ev_list = raw_finding.get("evidence", [])
    primary_quote = claim_text
    location = None
    if ev_list and isinstance(ev_list, list):
        primary_quote = str(ev_list[0].get("evidence_text", claim_text)).strip()
        location = ev_list[0].get("location_in_source")

    # Extract quantitative records if available
    quant_list = raw_finding.get("quantitative_evidence", [])
    quant = quant_list[0] if quant_list and isinstance(quant_list, list) else {}

    metric = str(quant.get("metric", "performance")).strip().lower() or "performance"
    dataset = str(quant.get("dataset", "standard benchmark")).strip() or "standard benchmark"
    model_name = quant.get("model")

    # Magnitude and direction extraction
    claim_l = f"{claim_text} {primary_quote}".lower()
    if any(w in claim_l for w in ("drop", "drops", "reduced", "reduces", "decreased", "decreases", "lower", "fall", "falls")):
        raw_dir = "decrease"
    elif any(w in claim_l for w in ("increase", "increases", "rose", "rises", "gained", "gains", "higher")):
        raw_dir = "increase"
    else:
        stance = str(raw_finding.get("stance", "support")).lower()
        raw_dir = "increase" if stance == "support" else ("decrease" if stance == "counter" else "no_effect")


    magnitude = None
    magnitude_type = "qualitative"
    if quant.get("absolute_difference") is not None:
        try:
            magnitude = float(quant["absolute_difference"])
            magnitude_type = "absolute_points"
        except (ValueError, TypeError):
            pass
    elif quant.get("relative_difference") is not None:
        try:
            magnitude = float(quant["relative_difference"])
            magnitude_type = "relative_percent"
        except (ValueError, TypeError):
            pass
    elif quant.get("multiplier") is not None:
        try:
            m_str = str(quant["multiplier"]).lower().rstrip("x").strip()
            magnitude = float(m_str)
            magnitude_type = "multiplier"
        except (ValueError, TypeError):
            pass

    # Normalized direction: +1 improvement, -1 degradation, 0 neutral
    lower_is_better_metrics = {"error_rate", "latency", "latency_ms", "perplexity", "loss", "overhead"}
    is_lower_better = any(m in metric for m in lower_is_better_metrics)
    if raw_dir == "increase":
        norm_dir = -1 if is_lower_better else +1
    elif raw_dir == "decrease":
        norm_dir = +1 if is_lower_better else -1
    else:
        norm_dir = 0

    # Decontextualization check
    full_parent = parent_context or str(source.get("retrieved_content", "") or source.get("content", ""))
    negators = scan_parent_context_for_negators(primary_quote, full_parent)
    modal_hedging = infer_modal_hedging_score(primary_quote)

    # Register into Evidence Lineage Registry
    lineage_record = GLOBAL_LINEAGE_REGISTRY.register(
        claim_id=claim_id,
        source=source,
        verbatim_quote=primary_quote,
        parent_context=full_parent[:2000],
        section_or_table=location,
        transformations=["extracted_from_phase2", "schema_v2_normalization"],
        negators=negators
    )

    # Metric Family categorization
    if any(k in metric for k in ("acc", "top-1", "accuracy", "rate")):
        m_family = "accuracy"
    elif any(k in metric for k in ("latency", "time", "speed", "throughput")):
        m_family = "latency"
    elif "f1" in metric:
        m_family = "f1"
    else:
        m_family = metric

    conditions = NormalizedConditions(
        dataset=dataset,
        model_architecture=model_name,
        metric_name=metric,
        metric_family=m_family,
        evaluation_year=pub_year
    )

    uncertainty = ClaimUncertainty(
        modal_hedging_score=modal_hedging
    )

    return NormalizedClaim(
        claim_id=claim_id,
        paper_id=source_id,
        paper_title=title,
        doi=doi,
        publication_year=pub_year,
        claim_scope=ClaimScope.EXPERIMENT_LEVEL,
        outcome_variable=metric,
        direction=raw_dir,
        normalized_direction=norm_dir,
        magnitude=magnitude,
        magnitude_type=magnitude_type,
        conditions=conditions,
        uncertainty=uncertainty,
        verbatim_quote=primary_quote,
        section_or_table=location,
        lineage_id=lineage_record.lineage_id,
        negators_detected=negators,
        is_contextually_qualified=len(negators) > 0
    )


def normalize_evidence_bundle(evidence_bundle: Dict[str, Any], sources_list: List[Dict[str, Any]]) -> List[NormalizedClaim]:
    """
    Normalize all findings from a Phase 2 research_evidence.json package.
    Assigns stable claim IDs (C1, C2...) and builds complete lineage.
    """
    sources_by_id = {str(s.get("source_id", "")).strip().upper(): s for s in sources_list}
    normalized_claims = []
    claim_counter = 1

    for q_entry in evidence_bundle.get("questions", []):
        for finding in q_entry.get("findings", []):
            s_ids = finding.get("source_ids", [])
            primary_sid = str(s_ids[0]).strip().upper() if s_ids else "UNKNOWN"
            source = sources_by_id.get(primary_sid, {"source_id": primary_sid, "title": "Unknown Source"})

            claim_id = f"C{claim_counter}"
            norm_claim = normalize_raw_finding(
                raw_finding=finding,
                source=source,
                claim_id=claim_id,
                parent_context=source.get("retrieved_content", "")
            )
            normalized_claims.append(norm_claim)
            claim_counter += 1

    return normalized_claims
