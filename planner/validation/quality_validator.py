import re


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "me", "more", "most", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves",
    "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}


QUESTION_BOILERPLATE = {
    "what", "how", "does", "impact", "effect", "affect", "influence", "role",
    "quantitative", "quantitatively", "qualitative", "qualitatively", "empirical",
    "investigate", "evaluate", "compare", "compared", "comparison", "relative",
    "versus", "vs", "benchmark", "performance", "measure", "measured", "rate"
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
    return {t for t in tokens if t not in STOPWORDS}


def _similarity(set1: set[str], set2: set[str]) -> float:
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    jaccard = intersection / union if union > 0 else 0.0
    containment = intersection / min(len(set1), len(set2)) if min(len(set1), len(set2)) > 0 else 0.0
    return max(jaccard, containment)


def _extract_query_tokens(q: dict) -> set[str]:
    strat = q.get("search_strategy", {})
    all_queries = []
    for k in ("primary_queries", "secondary_queries", "counter_evidence_queries"):
        val = strat.get(k, [])
        if isinstance(val, list):
            all_queries.extend(val)
        elif isinstance(val, str):
            all_queries.append(val)
    return _tokenize(" ".join(all_queries))


def validate_plan_quality(plan: dict) -> dict:
    """
    Validate plan quality, question distinctness, quota feasibility,
    and evidence consistency.
    """
    questions = plan.get("questions", [])

    # 1. Question Duplication Check
    for i in range(len(questions)):
        q1 = questions[i]
        q1_text = q1.get("question", "").strip()
        tokens1 = _tokenize(q1_text)
        for j in range(i + 1, len(questions)):
            q2 = questions[j]
            q2_text = q2.get("question", "").strip()
            tokens2 = _tokenize(q2_text)

            # Exact duplicate check
            if q1_text.lower() == q2_text.lower() or (tokens1 and tokens1 == tokens2):
                raise RuntimeError(
                    f"Duplicate or near-duplicate research questions detected between "
                    f"'{q1.get('id', f'#{i+1}')}' and '{q2.get('id', f'#{j+1}')}' "
                    f"(content similarity: 1.00). Questions must be distinct."
                )

            sim = _similarity(tokens1, tokens2)
            if sim > 0.70:
                # Check whether questions are investigating distinct variables/tasks
                # or have distinct search strategies
                diff1 = {w for w in (tokens1 - tokens2) if w not in QUESTION_BOILERPLATE and len(w) >= 3}
                diff2 = {w for w in (tokens2 - tokens1) if w not in QUESTION_BOILERPLATE and len(w) >= 3}

                query_tokens1 = _extract_query_tokens(q1)
                query_tokens2 = _extract_query_tokens(q2)
                query_sim = _similarity(query_tokens1, query_tokens2) if (query_tokens1 and query_tokens2) else 0.0

                # If both questions possess substantive distinguishing keywords and distinct search targets,
                # they are valid parallel investigations across distinct domains/tasks (e.g. math vs code).
                if diff1 and diff2 and query_sim < 0.60:
                    continue

                raise RuntimeError(
                    f"Duplicate or near-duplicate research questions detected between "
                    f"'{q1.get('id', f'#{i+1}')}' and '{q2.get('id', f'#{j+1}')}' "
                    f"(content similarity: {sim:.2f}). Questions must be distinct."
                )

    # 2. Quota Feasibility Check
    for q in questions:
        qid = q.get("id", "Unknown")
        sr = q.get("source_requirements", {})
        min_sources = sr.get("minimum_sources", 0)
        min_counter = sr.get("minimum_counter_evidence_sources", 0)
        min_primary = sr.get("minimum_primary_sources", 0)
        min_quant = sr.get("minimum_quantitative_sources", 0)

        if min_sources > 30:
            raise RuntimeError(
                f"Question {qid} specifies an unrealistic minimum_sources quota ({min_sources} > 30). "
                "Per-question source quotas must be feasible within retrieval constraints."
            )
        if min_counter > min_sources:
            raise RuntimeError(
                f"Question {qid} requires minimum_counter_evidence_sources ({min_counter}) "
                f"exceeding total minimum_sources ({min_sources})."
            )
        if min_primary > min_sources:
            raise RuntimeError(
                f"Question {qid} requires minimum_primary_sources ({min_primary}) "
                f"exceeding total minimum_sources ({min_sources})."
            )
        if min_quant > min_sources:
            raise RuntimeError(
                f"Question {qid} requires minimum_quantitative_sources ({min_quant}) "
                f"exceeding total minimum_sources ({min_sources})."
            )

    # 3. Evidence Requirement Consistency Check
    for q in questions:
        qid = q.get("id", "Unknown")
        if q.get("requires_quantitative_evidence"):
            q_fields = q.get("quantitative_fields", [])
            if not q_fields or len(q_fields) == 0:
                raise RuntimeError(
                    f"Question {qid} requires quantitative evidence but quantitative_fields is empty."
                )
        if q.get("requires_counter_evidence"):
            strategy = q.get("search_strategy", {})
            counter_queries = strategy.get("counter_evidence_queries", []) or strategy.get("counter_evidence", [])
            if not counter_queries:
                raise RuntimeError(
                    f"Question {qid} requires counter-evidence but no counter-evidence search queries "
                    "were provided in search_strategy."
                )

    # 4. Falsification Criteria Check
    hypothesis = plan.get("hypothesis")
    falsification_criteria = plan.get("falsification_criteria", [])
    if hypothesis and not falsification_criteria:
        raise RuntimeError(
            "Plan contains a hypothesis but no falsification_criteria were provided."
        )

    # 5. Scientific Feasibility & Calibrated Benchmark Evaluation
    from .plan_quality_benchmark import evaluate_plan_quality
    benchmark_report = evaluate_plan_quality(plan)
    plan["plan_quality_benchmark"] = benchmark_report

    return plan


