import re
from .sources import is_primary_source_type, is_peer_reviewed_type
from .evidence_validator import EvidenceValidator


def _count_primary_sources(selected_sources):
    count = 0
    for item in selected_sources:
        src = item[0] if isinstance(item, (tuple, list)) else item
        if is_primary_source_type(src):
            count += 1
    return count


def _count_peer_reviewed(selected_sources):
    count = 0
    for item in selected_sources:
        src = item[0] if isinstance(item, (tuple, list)) else item
        if is_peer_reviewed_type(src):
            count += 1
    return count



def evaluate_evidence_sufficiency(
    question,
    extraction_findings,
    selection_bundle
):
    """
    Evaluate whether a single research question has sufficient evidence
    according to its requirements in the research plan.

    Returns a dict with:
      - question_id
      - sufficient: bool
      - selected_source_count
      - useful_source_count
      - idle_source_count
      - successful_retrieval_count
      - finding_count
      - support_count
      - counter_count
      - limitation_count
      - trade_off_count
      - quantitative_count
      - quantitative_source_count
      - counter_source_count
      - primary_source_count
      - peer_reviewed_count
      - missing_requirements: list[str]
      - evidence_gaps: list[str]
    """

    question_id = str(question.get("id", "")).strip().upper()
    source_reqs = question.get("source_requirements", {}) or {}
    requires_quant = bool(question.get("requires_quantitative_evidence", False))
    requires_counter = bool(question.get("requires_counter_evidence", False))

    q_sel_data = selection_bundle.get("per_question_selection", {}).get(question_id, {})
    selected_sources = q_sel_data.get("selected_sources", [])

    selected_source_count = len(selected_sources)
    useful_sources, idle_sources = EvidenceValidator.filter_useful_sources(selected_sources, extraction_findings)

    # Build comprehensive source lookup across question selection and global selection bundle
    source_lookup = {}
    for item in selected_sources:
        src = item[0] if isinstance(item, (tuple, list)) else item
        sid = str(src.get("source_id", "")).strip().upper()
        if sid:
            source_lookup[sid] = src
    for src in selection_bundle.get("unique_selected_sources", []) or []:
        sid = str(src.get("source_id", "")).strip().upper()
        if sid and sid not in source_lookup:
            source_lookup[sid] = src
    for src in selection_bundle.get("canonical_sources", []) or []:
        sid = str(src.get("source_id", "")).strip().upper()
        if sid and sid not in source_lookup:
            source_lookup[sid] = src

    # Resolve all sources that actually contributed findings for this question
    finding_sids = set()
    for f in extraction_findings:
        for sid in f.get("source_ids", []):
            finding_sids.add(str(sid).strip().upper())
        if f.get("source_id"):
            finding_sids.add(str(f["source_id"]).strip().upper())

    useful_sources_for_question = [
        source_lookup[sid] for sid in finding_sids if sid in source_lookup
    ]
    if not useful_sources_for_question and useful_sources:
        useful_sources_for_question = useful_sources

    useful_source_count = len(useful_sources_for_question) if useful_sources_for_question else len(useful_sources)
    idle_source_count = max(0, selected_source_count - len(useful_sources))

    successful_retrieval_count = sum(
        1 for src, _ in selected_sources
        if str(src.get("content_status", "") or "").lower() in ("full", "partial")
    )

    support_count = sum(1 for f in extraction_findings if f.get("stance") == "support")
    counter_count = sum(1 for f in extraction_findings if f.get("stance") == "counter")
    limitation_count = sum(1 for f in extraction_findings if f.get("stance") == "limitation")
    trade_off_count = sum(1 for f in extraction_findings if f.get("stance") in ("trade_off", "mixed"))
    quantitative_count = sum(
        1 for f in extraction_findings
        if len(f.get("quantitative_evidence", [])) > 0
    )
    finding_count = len(extraction_findings)

    # Distinct sources providing quantitative and counter evidence
    quantitative_sources = set()
    counter_sources = set()
    source_finding_counts = {}

    for f in extraction_findings:
        sids = f.get("source_ids", [])
        if not sids and f.get("source_id"):
            sids = [f["source_id"]]

        has_quant = len(f.get("quantitative_evidence", [])) > 0
        is_counter = f.get("stance") == "counter"

        if sids:
            for sid in sids:
                source_finding_counts[sid] = source_finding_counts.get(sid, 0) + 1
                if has_quant:
                    quantitative_sources.add(sid)
                if is_counter:
                    counter_sources.add(sid)
        else:
            if has_quant:
                quantitative_sources.add(f"synthetic_quant_{len(quantitative_sources) + 1}")
            if is_counter:
                counter_sources.add(f"synthetic_counter_{len(counter_sources) + 1}")

    quantitative_source_count = len(quantitative_sources)
    counter_source_count = len(counter_sources)

    useful_primary = _count_primary_sources(useful_sources_for_question)
    primary_source_count = useful_primary if useful_primary > 0 else _count_primary_sources(selected_sources)
    useful_peer = _count_peer_reviewed(useful_sources_for_question)
    peer_reviewed_count = useful_peer if useful_peer > 0 else _count_peer_reviewed(selected_sources)

    min_sources = source_reqs.get("minimum_sources", 0)
    min_primary = source_reqs.get("minimum_primary_sources", 0)
    min_quant = source_reqs.get("minimum_quantitative_sources", 0)
    min_counter = source_reqs.get("minimum_counter_evidence_sources", 0)
    min_peer_reviewed = source_reqs.get("minimum_peer_reviewed", 0)

    if requires_quant and min_quant == 0:
        min_quant = 1
    if requires_counter and min_counter == 0:
        min_counter = 1

    missing_requirements = []
    evidence_gaps = []

    contributing_sources = len(source_finding_counts) if source_finding_counts else (useful_source_count if useful_source_count > 0 else selected_source_count)
    effective_source_count = contributing_sources
    if effective_source_count < min_sources:
        missing_requirements.append("insufficient_sources")
        evidence_gaps.append(
            f"Only {effective_source_count} contributing sources, "
            f"but {min_sources} required (selected: {selected_source_count})."
        )

    if min_primary > 0 and primary_source_count < min_primary:
        missing_requirements.append("insufficient_primary_sources")
        evidence_gaps.append(
            f"Only {primary_source_count} primary sources, "
            f"but {min_primary} required."
        )

    if min_peer_reviewed > 0 and peer_reviewed_count < min_peer_reviewed:
        missing_requirements.append("insufficient_peer_reviewed")
        evidence_gaps.append(
            f"Only {peer_reviewed_count} peer-reviewed sources, "
            f"but {min_peer_reviewed} required."
        )

    if requires_quant and quantitative_source_count < min_quant:
        missing_requirements.append("quantitative_evidence")
        evidence_gaps.append(
            f"Only {quantitative_source_count} independent sources with quantitative evidence, "
            f"but {min_quant} required (total findings: {quantitative_count})."
        )

    if requires_counter and counter_source_count < min_counter:
        missing_requirements.append("counter_evidence")
        if counter_source_count == 0 and (trade_off_count > 0 or limitation_count > 0):
            evidence_gaps.append(
                f"Extracted {trade_off_count} trade-offs and {limitation_count} limitations, "
                f"but 0 direct counter refutations. {min_counter} independent counter sources required."
            )
        else:
            evidence_gaps.append(
                f"Only {counter_source_count} independent sources with counter-evidence, "
                f"but {min_counter} required (total findings: {counter_count})."
            )

    # Source concentration check: prevents single-source dominance from bypassing corroboration
    max_findings_from_single_source = max(source_finding_counts.values()) if source_finding_counts else 0
    high_concentration = (
        finding_count >= 4
        and len(source_finding_counts) > 0
        and (max_findings_from_single_source / finding_count) > 0.65
    )
    if high_concentration:
        if min_sources >= 2 and len(source_finding_counts) < min_sources:
            missing_requirements.append("excessive_source_concentration")
        evidence_gaps.append(
            f"High evidence concentration: {max_findings_from_single_source}/{finding_count} "
            f"findings originate from a single source. Independent replication needed."
        )



    if successful_retrieval_count == 0 and finding_count == 0:
        evidence_gaps.append(
            "No successful retrievals and no findings extracted."
        )

    sufficient = len(missing_requirements) == 0

    independent_source_count = len(source_finding_counts)

    return {
        "question_id": question_id,
        "sufficient": sufficient,
        "selected_source_count": selected_source_count,
        "useful_source_count": useful_source_count,
        "idle_source_count": idle_source_count,
        "source_count": useful_source_count,
        "independent_source_count": independent_source_count,
        "epistemic_triplet": {
            "finding_count": finding_count,
            "source_count": useful_source_count,
            "independent_source_count": independent_source_count,
        },
        "successful_retrieval_count": successful_retrieval_count,
        "finding_count": finding_count,
        "support_count": support_count,
        "counter_count": counter_count,
        "limitation_count": limitation_count,
        "trade_off_count": trade_off_count,
        "quantitative_count": quantitative_count,
        "quantitative_source_count": quantitative_source_count,
        "counter_source_count": counter_source_count,
        "primary_source_count": primary_source_count,
        "peer_reviewed_count": peer_reviewed_count,
        "high_concentration": high_concentration,
        "missing_requirements": missing_requirements,
        "evidence_gaps": evidence_gaps,
    }


def generate_targeted_queries(question, missing_requirements):
    """
    Generate deterministic targeted follow-up queries for a question
    based on its missing evidence requirements.

    Does NOT use LLM calls. Uses template-based generation from the
    question text and missing requirement types.
    """

    question_text = str(question.get("question", "") or "").strip()
    qtype = str(question.get("type", "") or "").strip().lower()
    qtext_lower = question_text.lower()

    queries = []

    clean_q = re.sub(r"\(.*?\)", "", question_text)
    clean_q = re.sub(r"[^\w\s-]", " ", clean_q)
    clean_q = " ".join(clean_q.split())

    for req in missing_requirements:
        req = str(req).strip().lower()

        if req == "quantitative_evidence":
            is_agent = any(k in qtext_lower for k in ("agent", "agents", "multi-agent", "multiagent"))
            if is_agent:
                queries.append({
                    "query_text": (
                        "multi-agent vs single-agent llm reasoning accuracy benchmark baseline GSM8K"
                    ),
                    "query_type": "normal",
                })
                queries.append({
                    "query_text": (
                        "multi-agent llm complex reasoning quantitative comparison empirical results"
                    ),
                    "query_type": "normal",
                })
            elif "rag" in qtext_lower and "hallucination" in qtext_lower:
                queries.append({
                    "query_text": (
                        "RAG hallucination rate quantitative comparison "
                        "benchmark baseline LLM"
                    ),
                    "query_type": "normal",
                })
                queries.append({
                    "query_text": (
                        "RAG vs non-RAG hallucination percentage "
                        "empirical results benchmark"
                    ),
                    "query_type": "normal",
                })
            elif "performance" in qtext_lower or "benchmark" in qtext_lower:
                queries.append({
                    "query_text": (
                        "quantitative performance comparison "
                        "benchmark results evaluation"
                    ),
                    "query_type": "normal",
                })
            else:
                queries.append({
                    "query_text": (
                        f"{clean_q} quantitative results empirical data"
                    ),
                    "query_type": "normal",
                })

        elif req == "counter_evidence":
            is_agent = any(k in qtext_lower for k in ("agent", "agents", "multi-agent", "multiagent"))
            if is_agent:
                queries.append({
                    "query_text": (
                        "single-agent outperforms multi-agent llm reasoning overhead latency cost degradation"
                    ),
                    "query_type": "counter",
                })
                queries.append({
                    "query_text": (
                        "multi-agent llm failure modes cascading error communication bottleneck limitations"
                    ),
                    "query_type": "counter",
                })
            elif "rag" in qtext_lower and "hallucination" in qtext_lower:
                queries.append({
                    "query_text": (
                        "RAG fails to reduce hallucinations failure cases "
                        "retrieval noise increases errors"
                    ),
                    "query_type": "counter",
                })
                queries.append({
                    "query_text": (
                        "retrieval augmented generation hallucination failure "
                        "limitations benchmark study"
                    ),
                    "query_type": "counter",
                })
            elif "performance" in qtext_lower or "comparison" in qtext_lower:
                queries.append({
                    "query_text": (
                        "counter evidence limitations failures "
                        "negative results comparison"
                    ),
                    "query_type": "counter",
                })
            else:
                queries.append({
                    "query_text": (
                        f"{clean_q} limitations failures counter evidence"
                    ),
                    "query_type": "counter",
                })

        elif req == "insufficient_sources":
            queries.append({
                "query_text": question_text,
                "query_type": "normal",
            })

        elif req == "insufficient_primary_sources":
            if "rag" in qtext_lower or "hallucination" in qtext_lower:
                queries.append({
                    "query_text": (
                        "peer-reviewed RAG hallucination "
                        "primary research study"
                    ),
                    "query_type": "normal",
                })
            else:
                queries.append({
                    "query_text": (
                        f"{question_text} peer-reviewed primary research"
                    ),
                    "query_type": "normal",
                })

        elif req == "insufficient_peer_reviewed":
            queries.append({
                "query_text": (
                    f"{question_text} peer-reviewed journal conference paper"
                ),
                "query_type": "normal",
            })

    seen = set()
    unique_queries = []
    for q in queries:
        key = (q["query_text"].strip().lower(), q["query_type"])
        if key not in seen:
            seen.add(key)
            unique_queries.append(q)

    return unique_queries


def check_all_sufficiency(questions, extraction_bundle, selection_bundle):
    """
    Evaluate evidence sufficiency for all questions.

    Returns:
      - results: list of sufficiency dicts, one per question
      - insufficient_questions: list of (question, sufficiency_result) tuples
    """

    results = []
    insufficient_questions = []

    questions_by_id = {
        str(q.get("id", "")).strip().upper(): q
        for q in questions
    }

    extracted_questions = extraction_bundle.get("questions", [])

    for eq in extracted_questions:
        qid = str(eq.get("question_id", "")).strip().upper()
        question = questions_by_id.get(qid)
        if question is None:
            continue

        findings = eq.get("findings", [])
        sufficiency = evaluate_evidence_sufficiency(
            question, findings, selection_bundle
        )
        results.append(sufficiency)

        if not sufficiency["sufficient"]:
            insufficient_questions.append((question, sufficiency))

    return results, insufficient_questions
