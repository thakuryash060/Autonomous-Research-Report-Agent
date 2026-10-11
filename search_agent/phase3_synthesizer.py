import json
import os
from typing import Dict, Any, List, Optional

from .claim_normalizer import normalize_evidence_bundle, NormalizedClaim
from .pair_generator import generate_candidate_pairs
from .divergence_analyzer import analyze_divergence, ContradictionMatrixEntry
from .claim_graph import build_claim_graph, verify_graph_topology, synthesize_against_hypotheses, ClaimGraph
from .evidence_gap_planner import EvidenceGapPlanner, EvidenceGap
from .evidence_lineage import GLOBAL_LINEAGE_REGISTRY


def run_phase3_synthesis(
    evidence_bundle: Dict[str, Any],
    sources_list: List[Dict[str, Any]],
    research_plan: Dict[str, Any],
    gemini_client=None,
    output_dir: str = "data"
) -> Dict[str, Any]:
    """
    Execute Phase 3: Epistemically-Grounded Cross-Source Synthesis & Contradiction Resolution.

    Steps:
      3.1 Rich Claim Normalization & Cryptographic Lineage Tracking
      3.2 Candidate Pair Generation with Hard Compatibility Gates
      3.3 Metric Ontology & Statistical Comparability Testing
      3.4 Symmetric Bidirectional NLI
      3.5 Causal Divergence Analysis & Explanation Verification
      3.6 Epistemic Claim Graph & Study Independence Clustering
      3.7 Hypothesis-Conditioned NetEvidence Synthesis
      3.8 Evidence Gap Planning with Utility Scoring U(q)
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Claim Normalization (Schema v2.0)
    normalized_claims = normalize_evidence_bundle(evidence_bundle, sources_list)

    # 2. Candidate Pair Generation
    pairs = generate_candidate_pairs(normalized_claims)

    # 3-5. Divergence Analysis & Contradiction Matrix
    matrix_entries: List[ContradictionMatrixEntry] = []
    for p in pairs:
        entry = analyze_divergence(p, gemini_client=gemini_client)
        matrix_entries.append(entry)

    # 6. Build Claim Graph & Study Independence
    claim_graph = build_claim_graph(normalized_claims, matrix_entries, sources_list)
    is_topo_valid, topo_issues = verify_graph_topology(claim_graph)

    # 7. Hypothesis-Conditioned Synthesis
    hypothesis_synthesis = synthesize_against_hypotheses(claim_graph, normalized_claims, research_plan)

    # 8. Evidence Gap Planning
    claims_by_id = {c.claim_id: c for c in normalized_claims}
    unresolved_entries = [e for e in matrix_entries if e.classification.value in ("GENUINE_EMPIRICAL_CONFLICT", "INSUFFICIENT_EVIDENCE")]
    gap_planner = EvidenceGapPlanner()
    gaps = gap_planner.plan_gaps(unresolved_entries, claims_by_id)

    # -----------------------------------------------------------------
    # Save Canonical Phase 3 Output Artifacts to data/
    # -----------------------------------------------------------------
    # A. Contradiction Matrix
    matrix_path = os.path.join(output_dir, "contradiction_matrix.json")
    with open(matrix_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_pairs_evaluated": len(matrix_entries),
            "conflicts_detected": sum(1 for e in matrix_entries if e.classification.value == "GENUINE_EMPIRICAL_CONFLICT"),
            "explained_divergences": sum(1 for e in matrix_entries if e.classification.value == "EXPLAINED_CONTRADICTION"),
            "incomparable_pairs": sum(1 for e in matrix_entries if e.classification.value == "INCOMPARABLE"),
            "matrix": [e.model_dump() for e in matrix_entries]
        }, f, indent=2)

    # B. Claim Graph
    graph_path = os.path.join(output_dir, "claim_graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(claim_graph.model_dump(), f, indent=2)

    # C. Hypothesis Synthesis
    synthesis_path = os.path.join(output_dir, "hypothesis_synthesis.json")
    with open(synthesis_path, "w", encoding="utf-8") as f:
        json.dump(hypothesis_synthesis, f, indent=2)

    # D. Unresolved Evidence Gaps
    gaps_path = os.path.join(output_dir, "unresolved_evidence_gaps.json")
    with open(gaps_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_gaps": len(gaps),
            "actionable_search_queries": [g.recommended_search_query for g in gaps if g.action == "SEARCH"],
            "gaps": [g.model_dump() for g in gaps]
        }, f, indent=2)

    return {
        "status": "success",
        "claims_normalized": len(normalized_claims),
        "pairs_evaluated": len(pairs),
        "matrix_entries": len(matrix_entries),
        "is_topologically_sound": is_topo_valid,
        "topology_issues": topo_issues,
        "independent_evidence_units": len(claim_graph.independent_units),
        "hypothesis_verdict": hypothesis_synthesis.get("synthesis_verdict"),
        "net_evidence_score": hypothesis_synthesis.get("net_evidence_score"),
        "gaps_planned": len(gaps),
        "artifacts_emitted": [matrix_path, graph_path, synthesis_path, gaps_path]
    }

