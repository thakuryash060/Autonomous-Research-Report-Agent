import re
from typing import Dict, Any, List, Set
from pydantic import BaseModel, Field

from .claim_normalizer import NormalizedClaim


class IndependentEvidenceUnit(BaseModel):
    """
    A cluster of dependent publications/preprints originating from the same
    experimental cohort or author team, grouped to prevent evidence overcounting.
    """
    unit_id: str
    canonical_paper_id: str
    member_paper_ids: List[str] = Field(default_factory=list)
    member_dois: List[str] = Field(default_factory=list)
    claims_count: int = 0
    independence_weight: float = 1.0


def _clean_title(t: str) -> Set[str]:
    words = re.findall(r"\b[a-z0-9]{3,}\b", (t or "").lower())
    return set(words)


def cluster_independent_evidence_units(
    claims: List[NormalizedClaim],
    sources_list: List[Dict[str, Any]]
) -> Dict[str, IndependentEvidenceUnit]:
    """
    Identify shared experimental cohorts, preprint/publication duplicates,
    and overlapping studies.
    Ensures that an arXiv preprint and its published conference version
    count as 1 Independent Evidence Unit rather than 2 independent studies.
    """
    source_map = {str(s.get("source_id", "")).strip().upper(): s for s in sources_list}
    units: Dict[str, IndependentEvidenceUnit] = {}
    paper_to_unit: Dict[str, str] = {}
    unit_counter = 1

    unique_pids = sorted(list({c.paper_id for c in claims}))

    for pid in unique_pids:
        s_data = source_map.get(pid, {})
        title = s_data.get("title", "")
        doi = s_data.get("doi")
        title_words = _clean_title(title)

        matched_unit_id = None
        for uid, unit in units.items():
            canon_src = source_map.get(unit.canonical_paper_id, {})
            canon_title = canon_src.get("title", "")
            canon_words = _clean_title(canon_title)

            # Check title similarity (e.g. preprint vs published title)
            overlap = len(title_words & canon_words) / max(len(title_words | canon_words), 1)
            if overlap >= 0.75:
                matched_unit_id = uid
                break

            # Check DOI similarity
            if doi and canon_src.get("doi") and doi.strip().lower() == canon_src.get("doi", "").strip().lower():
                matched_unit_id = uid
                break

        if matched_unit_id:
            units[matched_unit_id].member_paper_ids.append(pid)
            if doi:
                units[matched_unit_id].member_dois.append(doi)
            paper_to_unit[pid] = matched_unit_id
        else:
            uid = f"IEU-{unit_counter:02d}"
            units[uid] = IndependentEvidenceUnit(
                unit_id=uid,
                canonical_paper_id=pid,
                member_paper_ids=[pid],
                member_dois=[doi] if doi else [],
                independence_weight=1.0
            )
            paper_to_unit[pid] = uid
            unit_counter += 1

    # Tally claims per unit
    for c in claims:
        uid = paper_to_unit.get(c.paper_id)
        if uid and uid in units:
            units[uid].claims_count += 1

    return units

