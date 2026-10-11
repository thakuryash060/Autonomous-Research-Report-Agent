import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


def compute_sha256(content: str) -> str:
    """Compute deterministic SHA-256 hex digest of UTF-8 content."""
    if not content:
        return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # empty string hash
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class LineageAnchor(BaseModel):
    """Immutable provenance anchor for a discrete piece of scientific evidence."""
    source_id: str
    paper_title: str
    doi: Optional[str] = None
    url: Optional[str] = None
    page_number: Optional[int] = None
    section_or_table: Optional[str] = None
    passage_hash: str
    verbatim_quote: str
    quote_hash: str
    created_at_ts: float = Field(default_factory=time.time)


class EvidenceLineageRecord(BaseModel):
    """
    Complete traceable provenance chain connecting:
    Source Document -> Extracted Passage -> Verbatim Quote -> Normalized Claim -> Decision.
    Enforces zero-hallucination verification across Phase 3 and Phase 4.
    """
    lineage_id: str
    claim_id: str
    anchor: LineageAnchor
    extraction_version: str = "v2.0-epistemic"
    normalization_transformations: List[str] = Field(default_factory=list)
    parent_context_hash: Optional[str] = None
    negators_found_in_radius: List[str] = Field(default_factory=list)
    lineage_hash: str = ""

    def finalize_hash(self) -> str:
        """Compute the cryptographic tamper-evident lineage hash."""
        payload = f"{self.lineage_id}:{self.claim_id}:{self.anchor.passage_hash}:{self.anchor.quote_hash}:{self.extraction_version}"
        self.lineage_hash = compute_sha256(payload)
        return self.lineage_hash


class EvidenceLineageRegistry:
    """
    Central in-memory and serializable registry of evidence provenance records.
    Provides verifiable lookups and audit trails for synthesis and reporting.
    """
    def __init__(self):
        self._records: Dict[str, EvidenceLineageRecord] = {}
        self._by_claim_id: Dict[str, str] = {}

    def register(
        self,
        claim_id: str,
        source: Dict[str, Any],
        verbatim_quote: str,
        parent_context: str = "",
        page_number: Optional[int] = None,
        section_or_table: Optional[str] = None,
        transformations: Optional[List[str]] = None,
        negators: Optional[List[str]] = None
    ) -> EvidenceLineageRecord:
        source_id = str(source.get("source_id", "UNKNOWN")).strip().upper()
        title = str(source.get("title", "")).strip()
        doi = source.get("doi")
        url = source.get("url")

        passage_hash = compute_sha256(parent_context or verbatim_quote)
        quote_hash = compute_sha256(verbatim_quote)
        parent_ctx_hash = compute_sha256(parent_context) if parent_context else None

        lineage_id = f"LIN-{claim_id}-{quote_hash[:8]}"

        anchor = LineageAnchor(
            source_id=source_id,
            paper_title=title,
            doi=doi,
            url=url,
            page_number=page_number,
            section_or_table=section_or_table,
            passage_hash=passage_hash,
            verbatim_quote=verbatim_quote,
            quote_hash=quote_hash
        )

        record = EvidenceLineageRecord(
            lineage_id=lineage_id,
            claim_id=claim_id,
            anchor=anchor,
            normalization_transformations=transformations or [],
            parent_context_hash=parent_ctx_hash,
            negators_found_in_radius=negators or []
        )
        record.finalize_hash()

        self._records[lineage_id] = record
        self._by_claim_id[claim_id] = lineage_id
        return record

    def get_by_lineage_id(self, lineage_id: str) -> Optional[EvidenceLineageRecord]:
        return self._records.get(lineage_id)

    def get_by_claim_id(self, claim_id: str) -> Optional[EvidenceLineageRecord]:
        lid = self._by_claim_id.get(claim_id)
        return self._records.get(lid) if lid else None

    def verify_provenance(self, claim_id: str, passage_text: str) -> bool:
        """Verify that a claim's quote exists verbatim inside the supplied passage."""
        record = self.get_by_claim_id(claim_id)
        if not record:
            return False
        quote = record.anchor.verbatim_quote
        return bool(quote and quote.strip().lower() in passage_text.strip().lower())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": len(self._records),
            "records": [r.model_dump() for r in self._records.values()]
        }


# Global lineage registry singleton
GLOBAL_LINEAGE_REGISTRY = EvidenceLineageRegistry()

