import json
from typing import Dict, Any, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from .claim_normalizer import NormalizedClaim
from .divergence_analyzer import ContradictionMatrixEntry, ConflictTaxonomy
from .study_independence import cluster_independent_evidence_units, IndependentEvidenceUnit


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relation: str  # "SUPPORTS", "CONTRADICTS", "CONDITIONED_ON", "MEMBER_OF"
    classification: Optional[str] = None
    weight: float = 1.0


class ClaimGraph(BaseModel):
    nodes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    edges: List[GraphEdge] = Field(default_factory=list)
    independent_units: Dict[str, IndependentEvidenceUnit] = Field(default_factory=dict)
    unresolved_conflicts: List[str] = Field(default_factory=list)


def build_claim_graph(
    claims: List[NormalizedClaim],
    matrix_entries: List[ContradictionMatrixEntry],
    sources_list: List[Dict[str, Any]]
) -> ClaimGraph:
    """
    Construct the formal Epistemic Claim Graph.
    Connects: Claims <-> Papers <-> Conditions <-> Independent Evidence Units.
    """
    nodes = {}
    edges = []

    # 1. Add Claim Nodes
    for c in claims:
        nodes[c.claim_id] = {
            "type": "claim",
            "paper_id": c.paper_id,
            "variable": c.outcome_variable,
            "direction": c.normalized_direction,
            "magnitude": c.magnitude,
            "quote": c.verbatim_quote,
            "lineage_id": c.lineage_id
        }

    # 2. Add Paper Nodes
    source_map = {str(s.get("source_id", "")).strip().upper(): s for s in sources_list}
    for sid, s in source_map.items():
        nodes[sid] = {
            "type": "paper",
            "title": s.get("title", ""),
            "doi": s.get("doi"),
            "year": s.get("publication_year"),
            "access_state": s.get("access_state", "unknown")
        }

    # 3. Add Edges from Contradiction Matrix
    unresolved = []
    for entry in matrix_entries:
        if entry.classification == ConflictTaxonomy.GENUINE_EMPIRICAL_CONFLICT:
            edges.append(GraphEdge(
                source_id=entry.claim_a_id,
                target_id=entry.claim_b_id,
                relation="CONTRADICTS",
                classification=entry.classification.value,
                weight=1.0
            ))
            edges.append(GraphEdge(
                source_id=entry.claim_b_id,
                target_id=entry.claim_a_id,
                relation="CONTRADICTS",
                classification=entry.classification.value,
                weight=1.0
            ))
            unresolved.append(entry.pair_id)
        elif entry.classification == ConflictTaxonomy.EXPLAINED_CONTRADICTION:
            edges.append(GraphEdge(
                source_id=entry.claim_a_id,
                target_id=entry.claim_b_id,
                relation="CONDITIONALLY_DIVERGES",
                classification=entry.classification.value,
                weight=0.5
            ))
        elif entry.classification == ConflictTaxonomy.NO_CONFLICT:
            edges.append(GraphEdge(
                source_id=entry.claim_a_id,
                target_id=entry.claim_b_id,
                relation="SUPPORTS",
                classification=entry.classification.value,
                weight=0.8
            ))

    # 4. Cluster Independent Evidence Units
    units = cluster_independent_evidence_units(claims, sources_list)
    for uid, unit in units.items():
        nodes[uid] = {
            "type": "independent_unit",
            "canonical_paper": unit.canonical_paper_id,
            "member_papers": unit.member_paper_ids,
            "claims_count": unit.claims_count
        }
        for mem in unit.member_paper_ids:
            edges.append(GraphEdge(source_id=mem, target_id=uid, relation="MEMBER_OF"))

    return ClaimGraph(
        nodes=nodes,
        edges=edges,
        independent_units=units,
        unresolved_conflicts=unresolved
    )


def verify_graph_topology(graph: ClaimGraph) -> Tuple[bool, List[str]]:
    """
    Enforce topological consistency checks on the Claim Graph:
    Detects paradox loops (e.g. Node A has CONTRADICTS edge to Node B,
    while simultaneously having a SUPPORTS edge to Node B).
    """
    violations = []
    pair_relations: Dict[Tuple[str, str], Set[str]] = {}

    for e in graph.edges:
        key = (e.source_id, e.target_id)
        pair_relations.setdefault(key, set()).add(e.relation)

    for (src, tgt), rels in pair_relations.items():
        if "CONTRADICTS" in rels and "SUPPORTS" in rels:
            violations.append(f"Topological paradox between {src} and {tgt}: both CONTRADICTS and SUPPORTS edges exist.")

        # Check reverse consistency
        rev_key = (tgt, src)
        rev_rels = pair_relations.get(rev_key, set())
        if "CONTRADICTS" in rels and "SUPPORTS" in rev_rels:
            violations.append(f"Asymmetric paradox: {src}->{tgt} CONTRADICTS, but {tgt}->{src} SUPPORTS.")

    is_valid = len(violations) == 0
    return is_valid, violations


def synthesize_against_hypotheses(
    graph: ClaimGraph,
    claims: List[NormalizedClaim],
    research_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Hypothesis-Conditioned Synthesis:
    Maps gathered claims and evidence clusters directly against Phase 1 hypotheses:
    - Primary Hypothesis
    - Competing Hypotheses
    - Falsification Criteria
    Calculates weighted NetEvidence over independent units.
    """
    primary_hyp = research_plan.get("hypothesis", "")
    competing = research_plan.get("competing_hypotheses", [])
    fals_criteria = research_plan.get("falsification_criteria", [])

    # Map paper to independent unit weight
    paper_weights = {}
    for uid, unit in graph.independent_units.items():
        w = 1.0 / max(len(unit.member_paper_ids), 1)
        for p in unit.member_paper_ids:
            paper_weights[p] = w

    support_score = 0.0
    counter_score = 0.0
    supporting_claims = []
    counter_claims = []

    for c in claims:
        p_weight = paper_weights.get(c.paper_id, 1.0)
        # Apply modal hedging discount
        hedging = c.uncertainty.modal_hedging_score
        effective_w = p_weight * hedging

        if c.normalized_direction > 0:
            support_score += effective_w
            supporting_claims.append(c.claim_id)
        elif c.normalized_direction < 0:
            counter_score += effective_w
            counter_claims.append(c.claim_id)

    net_evidence = round(support_score - counter_score, 4)

    # Determine resolution leaning
    if net_evidence >= 1.5:
        verdict = "STRONGLY_SUPPORTS_PRIMARY_HYPOTHESIS"
    elif net_evidence >= 0.5:
        verdict = "LEANS_TOWARD_PRIMARY_HYPOTHESIS"
    elif net_evidence <= -1.5:
        verdict = "STRONGLY_FAVORS_COMPETING_HYPOTHESIS"
    elif net_evidence <= -0.5:
        verdict = "LEANS_TOWARD_COMPETING_HYPOTHESIS"
    else:
        verdict = "EMPIRICALLY_INCONCLUSIVE"

    return {
        "primary_hypothesis": primary_hyp,
        "competing_hypotheses": competing,
        "falsification_criteria": fals_criteria,
        "synthesis_verdict": verdict,
        "net_evidence_score": net_evidence,
        "support_weight": round(support_score, 4),
        "counter_weight": round(counter_score, 4),
        "independent_units_evaluated": len(graph.independent_units),
        "supporting_claim_ids": supporting_claims,
        "counter_claim_ids": counter_claims,
        "unresolved_conflicts_count": len(graph.unresolved_conflicts)
    }
