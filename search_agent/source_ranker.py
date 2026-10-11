import re
from urllib.parse import urlsplit


SOURCE_TYPES = {
    "systematic_review",
    "peer_reviewed_paper",
    "conference_paper",
    "preprint",
    "government",
    "official",
    "academic",
    "standards",
    "documentation",
    "news",
    "technical_article",
    "corporate_blog",
    "personal_blog",
    "forum",
    "social_media",
    "video",
    "other"
}

SOURCE_QUALITY_SCORES = {
    "systematic_review": 1.00,
    "peer_reviewed_paper": 0.95,
    "conference_paper": 0.90,
    "government": 0.90,
    "official": 0.88,
    "standards": 0.88,
    "academic": 0.82,
    "preprint": 0.80,
    "documentation": 0.78,
    "technical_article": 0.65,
    "news": 0.55,
    "corporate_blog": 0.50,
    "personal_blog": 0.35,
    "forum": 0.25,
    "social_media": 0.20,
    "video": 0.20,
    "other": 0.40
}

RANKING_WEIGHTS = {
    "relevance": 0.40,
    "source_quality": 0.25,
    "planner_preference": 0.20,
    "tavily": 0.15
}


def configure_ranking_weights(
    relevance: float = 0.40,
    source_quality: float = 0.25,
    planner_preference: float = 0.20,
    tavily: float = 0.15
) -> dict:
    """
    Dynamically configure Phase 2 ranking weights.
    Normalizes weights to ensure their sum equals 1.0.
    """
    total = relevance + source_quality + planner_preference + tavily
    if total <= 0:
        raise ValueError("Sum of ranking weights must be strictly positive.")
    RANKING_WEIGHTS["relevance"] = round(relevance / total, 4)
    RANKING_WEIGHTS["source_quality"] = round(source_quality / total, 4)
    RANKING_WEIGHTS["planner_preference"] = round(planner_preference / total, 4)
    RANKING_WEIGHTS["tavily"] = round(tavily / total, 4)
    return dict(RANKING_WEIGHTS)


def compute_reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    weights: list[float] = None,
    k: int = 60
) -> dict[str, float]:
    """
    Reciprocal Rank Fusion (RRF) for combining distinct retrieval and ranking signals
    (e.g., Sparse BM25 + Dense Vector Cosine Similarity + Quality Heuristics).
    RRF(d) = sum_{r in R} (w_r / (k + rank_r(d)))
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)

    scores: dict[str, float] = {}
    for r_idx, ranked_items in enumerate(ranked_lists):
        w = weights[r_idx] if r_idx < len(weights) else 1.0
        for rank, item_id in enumerate(ranked_items, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + (w / (k + rank))

    return scores


EVIDENCE_ELIGIBLE_SOURCE_TYPES = {
    "systematic_review",
    "peer_reviewed_paper",
    "conference_paper",
    "government",
    "official",
    "standards",
    "academic",
    "preprint",
    "documentation",
    "technical_article",
}

EVIDENCE_EXCLUSION_REASONS = {
    "video": "video",
    "social_media": "social_media",
    "forum": "forum",
    "personal_blog": "blog",
    "corporate_blog": "blog",
    "news": "news",
    "other": "unsupported_source_type",
}

PREFERENCE_TO_SOURCE_TYPES = {
    "systematic review": {"systematic_review"},
    "systematic survey": {"systematic_review"},
    "meta-analysis": {"systematic_review"},
    "peer-reviewed paper": {"peer_reviewed_paper", "conference_paper"},
    "peer-reviewed journal article": {"peer_reviewed_paper"},
    "clinical study": {"peer_reviewed_paper"},
    "conference paper": {"conference_paper", "peer_reviewed_paper"},
    "peer-reviewed conference paper": {"conference_paper", "peer_reviewed_paper"},
    "benchmark paper": {"peer_reviewed_paper", "conference_paper"},
    "primary research preprint": {"preprint"},
    "archived primary research preprint": {"preprint"},
    "preprint": {"preprint"},
    "official technical report": {"official", "government"},
    "technical report": {"official", "government", "academic"},
    "official documentation": {"documentation", "official"},
    "technical documentation": {"documentation", "official"},
    "repository documentation": {"documentation"},
    "technical standard": {"standards"},
    "security advisory": {"official", "government"},
    "government dataset": {"government"},
    "government report": {"government"},
    "academic research paper": {"peer_reviewed_paper", "academic"},
    "research paper": {"peer_reviewed_paper", "academic"},
    "industry research publication": {"technical_article", "official"},
    "technical blog": {"corporate_blog", "personal_blog"},
    "workshop notes": {"conference_paper", "academic"},
}

STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "of", "on", "or", "that", "the", "this", "to",
    "under", "what", "when", "where", "which", "with"
}

_METHODOLOGY_BOILERPLATE_WEIGHTS = {
    "quantitative": 0.15, "quantitatively": 0.15,
    "comparison": 0.15, "comparative": 0.15, "comparisons": 0.15, "compare": 0.15, "compared": 0.15,
    "assessment": 0.15, "evaluating": 0.15, "evaluation": 0.15, "evaluations": 0.15, "evaluate": 0.15, "evaluated": 0.15,
    "analysis": 0.15, "analyses": 0.15, "analyzing": 0.15,
    "study": 0.15, "studies": 0.15,
    "empirical": 0.15, "empirically": 0.15,
    "counter": 0.15, "evidence": 0.15,
    "approach": 0.15, "approaches": 0.15,
    "method": 0.15, "methods": 0.15, "methodology": 0.15, "methodologies": 0.15,
    "using": 0.15, "based": 0.15, "new": 0.15, "novel": 0.15, "paper": 0.15,
    "result": 0.15, "results": 0.15,
    "investigation": 0.15, "investigating": 0.15,
    "systematic": 0.15, "overview": 0.15, "survey": 0.15,
    "effective": 0.15, "effectiveness": 0.15,
    "impact": 0.15, "role": 0.15,
    "framework": 0.25, "frameworks": 0.25,
    "technique": 0.20, "techniques": 0.20,
    "application": 0.20, "applications": 0.20,
}

_DOMAIN_SUBJECT_WEIGHTS = {
    "agent": 1.3, "agents": 1.3, "multiagent": 1.4,
    "llm": 1.3, "llms": 1.3, "reasoning": 1.3,
    "debate": 1.3, "collaborative": 1.3, "cooperative": 1.3, "collaboration": 1.3,
    "consensus": 1.3, "overhead": 1.2, "propagation": 1.2, "cascading": 1.2,
    "decomposition": 1.3, "subtask": 1.3, "subtasks": 1.3,
    "hallucination": 1.3, "hallucinations": 1.3, "factuality": 1.3, "faithfulness": 1.3,
    "rag": 1.3, "retrieval": 1.2,
}

_MODERATE_ML_WEIGHTS = {
    "model": 0.8, "models": 0.8, "system": 0.8, "systems": 0.8,
    "benchmark": 0.9, "benchmarks": 0.9, "transformer": 0.9, "transformers": 0.9,
    "training": 0.7, "dataset": 0.8, "datasets": 0.8,
    "accuracy": 0.8, "performance": 0.7,
}

_TERM_WEIGHTS = {
    **_METHODOLOGY_BOILERPLATE_WEIGHTS,
    **_DOMAIN_SUBJECT_WEIGHTS,
    **_MODERATE_ML_WEIGHTS,
}


_NLP_QUERY_INDICATORS = {
    "nlp",
    "natural language",
    "language",
    "text",
    "translation",
    "linguistic",
    "sentiment",
    "parsing",
    "question",
    "bert",
    "gpt",
    "attention",
}

_NLP_DOMAIN_CONCEPTS = {
    "attention mechanism",
    "self-attention",
    "multi-head attention",
    "language model",
    "pretraining",
    "pre-training",
    "fine-tuning",
    "pretrained",
    "machine translation",
    "sequence-to-sequence",
    "seq2seq",
    "named entity",
    "question answering",
    "text generation",
    "language understanding",
    "natural language",
    "positional encoding",
    "wordpiece",
    "subword",
    "encoder-decoder",
    "recurrent",
    "convolutional",
    "sequence transduction",
    "bidirectional",
    "masked language",
    "language representation",
}

_NON_NLP_DOMAIN_INDICATORS = {
    "medical imaging",
    "medical image",
    "image segmentation",
    "computer vision",
    "pedestrian detection",
    "time series",
    "trajectory forecasting",
    "trajectory prediction",
    "asset prediction",
    "weather forecasting",
    "molecular biology",
    "remote sensing",
    "satellite imagery",
    "video understanding",
    "depth estimation",
    "point cloud",
    "graph neural",
    "electric vehicle",
    "ev charging",
    "load forecasting",
    "energy management",
    "autonomous driving",
    "robotics",
    "drug discovery",
    "smart grid",
    "power system",
}

_NON_NLP_SECONDARY_INDICATORS = {
    "speech",
    "audio",
    "music",
    "recommendation",
    "forecasting",
    "prediction",
}

_QUERY_INTENT_CONCEPTS = {
    "performance": {
        "benchmark", "evaluation", "performance", "accuracy", "f1",
        "bleu", "rouge", "glue", "superglue", "mmlu",
        "comparison", "baseline", "fine-tuning", "zero-shot", "few-shot",
        "language understanding", "natural language processing",
    },
    "computational_cost": {
        "inference", "training compute", "computational cost", "flops",
        "latency", "throughput", "memory", "gpu", "energy", "power",
        "efficiency", "carbon", "deployment", "serving", "quantization",
        "pruning", "distillation", "hardware", "inference cost",
    },
    "robustness": {
        "adversarial", "robustness", "attack", "vulnerability",
        "hallucination", "factuality", "out-of-distribution", "ood",
        "distribution shift", "generalization", "perturbation", "safety",
        "reliability",
    },
    "scaling": {
        "scaling law", "parameter scaling", "parameter count", "model size",
        "data scaling", "dataset size", "compute-optimal", "data availability",
        "architectural bottleneck", "parameter-efficient", "peft", "lora",
        "memory", "fine-tuning cost",
    },
    "hallucination_definition": {
        "hallucination", "factuality", "faithfulness", "factual consistency",
        "taxonomy", "classification", "detection", "evaluation",
        "hallucination types", "factual error", "unsupported claim",
        "contradiction", "grounding", "factuality error",
    },
    "rag_vs_nonrag_comparison": {
        "retrieval augmented generation", "rag", "baseline", "non-rag",
        "without retrieval", "with retrieval", "comparison", "ablation",
        "benchmark", "hallucination rate", "factuality score",
        "faithfulness score", "evaluation dataset", "empirical evaluation",
        "experimental results", "no retrieval", "vanilla",
        "retrieval-augmented", "non-retrieval",
    },
    "rag_failure_modes": {
        "retrieval failure", "irrelevant context", "noisy context",
        "outdated knowledge", "missing information", "incomplete context",
        "conflicting evidence", "context fragmentation", "chunking",
        "retrieval quality", "hallucination propagation",
        "retrieval-induced hallucination", "unsupported generation",
        "knowledge base limitation", "robustness", "failure mode",
        "boundary condition", "retrieval error", "context window",
    },
    "retrieval_configuration": {
        "dense retrieval", "sparse retrieval", "hybrid retrieval",
        "bm25", "vector search", "embedding retrieval", "top-k",
        "chunk size", "chunking strategy", "overlap", "reranking",
        "re-ranking", "cross-encoder", "retriever", "retrieval precision",
        "retrieval recall", "retrieval f1", "similarity threshold",
        "retrieval configuration", "dense", "sparse", "hybrid",
    },
    "multi_agent_comparison": {
        "multi-agent", "multi agent", "multiagent", "single-agent", "single agent",
        "agent debate", "collaborative reasoning", "agent society", "role-playing",
        "cooperative agents", "multi-agent debate", "consensus", "mcts", "sub-task",
        "subtask", "sub-task training", "multi-agent system", "multi-agent systems",
        "single-agent baseline", "agent communication", "multi-agent collaboration",
        "task decomposition", "distributed reasoning", "multi-agent framework",
        "multi-agent frameworks", "prost", "autogen", "metagpt", "chatdev",
    },
    "multi_agent_limitations": {
        "error propagation", "cascading errors", "cascading error", "communication overhead",
        "token overhead", "coordination cost", "hallucination amplification",
        "groupthink", "agent failure", "communication bottleneck", "consensus breakdown",
        "infinite loop", "message overhead", "redundancy", "latency overhead",
        "syllogistic failure", "miscommunication", "cost overhead",
    },
    "multi_agent_boundary_conditions": {
        "task decomposition", "task complexity", "modular", "structural decomposition",
        "sub-goal", "subtask", "subtasks", "role specialization", "boundary condition",
        "boundary conditions", "task-dependent", "agent coordination",
        "collaboration topology", "heterogeneous agents", "homogeneous agents",
        "problem structure", "verification overhead",
    },
}

_DISALLOWED_FIELDS_OF_STUDY = {
    "biology",
    "medicine",
    "chemistry",
    "materials science",
    "geology",
    "environmental science",
    "agricultural and food sciences",
    "immunology and microbiology",
    "pharmacology, toxicology and pharmaceutics",
    "nursing",
    "dentistry",
    "veterinary",
}

_ALLOWED_CS_FIELDS = {
    "computer science",
    "artificial intelligence",
    "computation and language",
    "machine learning",
    "engineering",
    "mathematics",
    "linguistics",
    "cognitive science",
}

_DOMAIN_MISMATCH_INDICATORS = {
    # Biology / Proteomics / Genetics
    "dna methylation",
    "methylation",
    "epigenetic",
    "mass spectrometry",
    "swath",
    "proteomics",
    "metabolomics",
    "genomics",
    "genome",
    "protein language models",
    "protein folding",
    "cellular",
    "cardiac",
    "cardiovascular",
    "cardiology",
    "endocardial",
    "myocardial",
    "arrhythmia",
    "atrial fibrillation",
    "electrocardiogram",
    "electrophysiology",
    "ecg",
    "coronary",
    "oncology",
    "cancer",
    "clinical trial",
    "pharmacokinetics",
    "in vitro",
    "in vivo",
    "pathogen",
    "pathology",
    "biochemical",
    "enzyme",
    "antibody",
    "antibodies",
    # Chemistry / Physics / Aerosol
    "condensation nuclei",
    "nuclei counter",
    "aerosol",
    "nanoparticle",
    "crystallography",
    "polymer",
    "spectrophotometry",
    "chromatography",
    "geochemical",
    # Vehicles / Driving / Traffic
    "driving simulator",
    "vehicle dynamics",
    "traffic flow",
    "electric vehicle charging",
    "smart grid",
    "wind turbine",
    # Medical imaging / Clinical psychology
    "medical imaging",
    "medical image",
    "image segmentation",
    "schizophrenia",
    "psychiatric",
    "depression",
    "anxiety",
    "sensory precision",
    "hallucination-prone",
    "perceptual",
    "drug discovery",
}


def _term_weight(term):
    return _TERM_WEIGHTS.get(term, 1.0)


def _is_nlp_question(question_text):
    qtext = str(question_text or "").lower()
    return any(indicator in qtext for indicator in _NLP_QUERY_INDICATORS)


def _is_llm_rag_question(question_text):
    qtext = str(question_text or "").lower()
    return any(
        indicator in qtext
        for indicator in (
            "llm", "large language model", "language model",
            "rag", "retrieval augmented", "retrieval",
            "hallucination", "factuality", "faithfulness",
        )
    )


def _is_ai_query(query_text, question_text=""):
    combined = f"{query_text} {question_text}".lower()
    return any(
        kw in combined
        for kw in (
            "llm", "large language", "language model", "agent", "multi-agent",
            "single-agent", "reasoning", "rag", "retrieval augmented",
            "hallucination", "neural", "deep learning", "nlp", "transformer",
            "artificial intelligence", "machine learning",
            "decoding", "activation steering", "knowledge conflict", "parametric",
            "pre-trained", "weights", "prompt", "prompting", "logits", "logit",
            "fine-tuning", "cot", "chain-of-thought", "contextual knowledge",
            "inference", "generation", "generative"
        )
    )


def _detect_query_intent(question_text, question_type=None):
    qtype = str(question_type or "").lower().strip()
    qtext = str(question_text or "").lower()

    # Multi-agent intent detection takes precedence if agent context is present
    is_agent_context = any(
        kw in qtext for kw in ("agent", "agents", "multi-agent", "single-agent", "multiagent")
    )
    if is_agent_context:
        if any(kw in qtext for kw in ("failure mode", "error propagation", "overhead", "bottleneck", "latency", "cost", "propagation")):
            return "multi_agent_limitations"
        if any(kw in qtext for kw in ("boundary condition", "boundary", "when do", "structural", "task-dependent", "under what", "decomposition")):
            return "multi_agent_boundary_conditions"
        if any(kw in qtext for kw in ("compare", "vs", "outperform", "baseline", "standardized", "benchmark", "empirically", "accuracy")):
            return "multi_agent_comparison"
        if qtype == "comparison":
            return "multi_agent_comparison"
        if qtype == "limitations":
            return "multi_agent_limitations"
        if qtype == "boundary_conditions":
            return "multi_agent_boundary_conditions"

    # RAG/hallucination-specific intent detection takes precedence over generic type
    if any(kw in qtext for kw in ("failure mode", "boundary condition", "fail to prevent", "retrieval configuration")):
        if "retrieval configuration" in qtext or "dense" in qtext or "sparse" in qtext or "chunking" in qtext:
            return "retrieval_configuration"
        return "rag_failure_modes"

    if any(kw in qtext for kw in ("rag vs", "non-rag", "without retrieval", "with retrieval", "compared to", "compared with")):
        return "rag_vs_nonrag_comparison"

    if any(kw in qtext for kw in ("how much", "to what extent", "how effectively", "how significantly")):
        if "rag" in qtext or "retrieval" in qtext:
            return "rag_vs_nonrag_comparison"

    if any(kw in qtext for kw in ("how do", "what retrieval", "what configuration", "dense vs", "sparse vs", "chunking", "reranking")):
        return "retrieval_configuration"

    if any(kw in qtext for kw in ("what are hallucinations", "how are hallucinations", "define", "definition of", "taxonomy")):
        return "hallucination_definition"

    if any(kw in qtext for kw in ("hallucination", "rag", "retrieval")):
        if "retrieval" in qtext and ("configuration" in qtext or "dense" in qtext or "sparse" in qtext or "chunk" in qtext):
            return "retrieval_configuration"
        if "failure" in qtext or "fail" in qtext or "boundary" in qtext:
            return "rag_failure_modes"
        if "compare" in qtext or "versus" in qtext or "vs" in qtext or "compared" in qtext:
            return "rag_vs_nonrag_comparison"
        if "what are" in qtext or "definition" in qtext or "taxonomy" in qtext or "how are" in qtext:
            return "hallucination_definition"
        return "robustness"

    if qtype == "performance":
        return "performance"
    elif qtype == "effects":
        if any(kw in qtext for kw in ("computational", "cost", "memory", "energy", "flops", "latency", "inference", "environmental")):
            return "computational_cost"
        return "performance"
    elif qtype == "limitations":
        return "robustness"
    elif qtype == "scaling":
        return "scaling"

    cost_keywords = ("computational", "cost", "memory", "energy", "flops", "latency", "inference", "environmental")
    perf_keywords = ("benchmark", "performance", "comparison", "accuracy", "evaluation")
    robust_keywords = ("robustness", "failure", "vulnerability", "hallucination", "generalization")
    scaling_keywords = ("scaling", "parameter", "model size", "compute-optimal")

    scores = {
        "computational_cost": sum(1 for kw in cost_keywords if kw in qtext),
        "performance": sum(1 for kw in perf_keywords if kw in qtext),
        "robustness": sum(1 for kw in robust_keywords if kw in qtext),
        "scaling": sum(1 for kw in scaling_keywords if kw in qtext),
    }

    best_intent = max(scores, key=scores.get)
    if scores[best_intent] > 0:
        return best_intent

    return None


def _domain_and_text(source):
    url = str(source.get("url", "") or "").strip()
    parsed = urlsplit(url)
    domain = (parsed.hostname or "").lower()
    text = " ".join(
        str(source.get(field, "") or "")
        for field in ("title", "content")
    ).lower()
    return domain, text


def classify_source(source):
    """Classify a source using conservative URL and metadata signals."""

    provider_name = str(source.get("provider_name", "") or "").lower()
    venue = str(source.get("venue", "") or "").lower()
    doi = str(source.get("doi", "") or "").lower()
    url = str(source.get("url", "") or "").lower()
    title = str(source.get("title", "") or "").lower()
    pub_types = [str(pt).lower() for pt in source.get("publication_types", []) or []]

    if provider_name in ("openalex", "semanticscholar"):
        if (
            "systematic review" in title
            or "meta-analysis" in title
            or ("review" in pub_types and any(w in title for w in ("systematic", "survey", "overview", "meta-analysis")))
        ):
            return "systematic_review"

        if (
            "arxiv.org" in url
            or "arxiv" in venue
            or "biorxiv" in venue
            or "medrxiv" in venue
            or "preprint" in pub_types
            or "/10.48550/" in doi
        ):
            return "preprint"

        conference_indicators = (
            "conference", "proceedings", "symposium", "workshop",
            "acl", "emnlp", "naacl", "aaai", "ijcai",
            "neurips", "nips", "icml", "iclr",
            "cvpr", "iccv", "eccv", "icassp",
            "colt", "kdd", "sigir", "www", "chi",
        )
        journal_indicators = (
            "journal", "transactions", "letters",
            "review", "annals", "bulletin", "nature",
            "science", "ieee", "acm", "springer", "elsevier"
        )

        if "conference" in pub_types or any(ind in venue for ind in conference_indicators):
            return "conference_paper"
        elif "journalarticle" in pub_types or any(ind in venue for ind in journal_indicators):
            return "peer_reviewed_paper"
        elif doi and "/10.48550/" not in doi:
            return "peer_reviewed_paper"
        elif venue:
            return "peer_reviewed_paper"

        return "academic"

    domain, text = _domain_and_text(source)
    title = str(source.get("title", "") or "").lower()
    combined = f"{title} {text}"

    if domain in {"arxiv.org", "export.arxiv.org"} and "/abs/" in str(source.get("url", "")):
        return "preprint"

    if "aclanthology.org" in domain or "proceedings" in domain or "openreview.net" in domain:
        return "conference_paper"

    if domain.endswith(".gov") or ".gov." in domain:
        return "government"

    if domain in {"reddit.com", "www.reddit.com", "old.reddit.com"} or domain.endswith(".reddit.com"):
        return "forum"

    if domain in {"linkedin.com", "www.linkedin.com"} or domain.endswith(".linkedin.com"):
        return "social_media"

    if domain in {"youtube.com", "www.youtube.com", "youtu.be", "vimeo.com"}:
        return "video"

    if domain in {"medium.com", "www.medium.com"} or domain.endswith(".medium.com"):
        return "personal_blog"

    if domain in {
        "springer.com", "link.springer.com", "nature.com", "sciencedirect.com",
        "www.sciencedirect.com", "pmc.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
        "jamanetwork.com", "tandfonline.com",
        "ieee.org", "ieeexplore.ieee.org", "acm.org", "dl.acm.org",
        "aaai.org", "jmlr.org", "pnas.org"
    }:
        return "peer_reviewed_paper"

    if domain.endswith(".edu") or ".edu." in domain:
        return "academic"

    if domain in {"w3.org", "www.w3.org", "iso.org", "www.iso.org", "ietf.org", "www.ietf.org"}:
        return "standards"

    documentation_markers = (
        domain.startswith("docs."),
        domain.startswith("developer."),
        domain.startswith("developers."),
        domain.startswith("support."),
        "readthedocs" in domain,
        "documentation" in domain,
        "docs" in title
    )

    if any(documentation_markers):
        return "documentation"

    news_domains = {
        "bbc.com", "bbc.co.uk", "reuters.com", "apnews.com", "nytimes.com",
        "cnn.com", "theguardian.com", "washingtonpost.com"
    }

    if domain in news_domains or any(
        marker in domain
        for marker in ("news.", "newsroom.")
    ):
        return "news"

    if domain.startswith("blog.") or "/blog/" in str(source.get("url", "")):
        return "corporate_blog"

    if domain.endswith(".org") and any(
        marker in combined
        for marker in ("technical report", "research report", "white paper")
    ):
        return "official"

    if any(
        marker in combined
        for marker in ("technical article", "engineering blog", "developer blog")
    ):
        return "technical_article"

    return "other"


def _tokens(value):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _relevance_score(source, query_text, intent=None, content_status=None, question_text=""):
    is_ai = _is_ai_query(query_text, question_text)

    # 1. Academic fields_of_study filter
    fields_of_study = [str(f).lower().strip() for f in (source.get("fields_of_study") or [])]
    if is_ai and fields_of_study:
        has_allowed = any(
            any(allowed in f for allowed in _ALLOWED_CS_FIELDS)
            for f in fields_of_study
        )
        has_disallowed = any(
            any(disallowed in f for disallowed in _DISALLOWED_FIELDS_OF_STUDY)
            for f in fields_of_study
        )
        if has_disallowed and not has_allowed:
            return 0.0

    title_lower = str(source.get("title", "") or "").lower()
    source_text = (
        f"{title_lower} "
        f"{str(source.get('abstract') or source.get('content', '') or '').lower()}"
    )

    # 2. Severe non-domain indicator filter in title
    if is_ai:
        title_mismatch = any(ind in title_lower for ind in _DOMAIN_MISMATCH_INDICATORS)
        has_ai_anchors = any(
            kw in source_text
            for kw in (
                "llm", "large language", "language model", "agent", "multi-agent",
                "single-agent", "prompting", "reasoning", "transformer",
                "artificial intelligence", "machine learning", "neural network"
            )
        )
        if title_mismatch and not has_ai_anchors:
            return 0.0

    # 3. Subject Anchor Gating
    combined_query = f"{query_text} {question_text}".lower()
    is_agent_query = any(
        kw in combined_query
        for kw in ("agent", "agents", "multi-agent", "single-agent", "multiagent")
    )
    is_rag_query = _is_llm_rag_question(combined_query)

    agent_anchors = (
        "agent", "agents", "multi-agent", "multiagent", "single-agent",
        "agent debate", "collaborative", "cooperative", "autogen", "metagpt",
        "chatdev", "camel", "prost", "subtask", "sub-task"
    )
    has_agent_anchor = any(anc in source_text for anc in agent_anchors)

    if is_agent_query:
        if not has_agent_anchor:
            has_broad_ai = any(
                kw in source_text
                for kw in ("language model", "llm", "large language", "reasoning", "transformer")
            )
            if not has_broad_ai:
                return 0.0
    elif is_rag_query:
        rag_anchors = (
            "rag", "retrieval", "retrieval-augmented", "retrieval augmented",
            "hallucination", "hallucinations", "factuality", "faithfulness",
            "llm", "language model", "large language"
        )
        has_rag_anchor = any(anc in source_text for anc in rag_anchors)
        if not has_rag_anchor:
            return 0.0

    # 4. Query token scoring
    query_tokens = _tokens(query_text)
    if not query_tokens:
        return 0.0

    title_tokens = _tokens(source.get("title", ""))
    abstract = source.get("abstract") or source.get("content", "")
    abstract_tokens = _tokens(abstract)

    title_intersection = query_tokens & title_tokens
    abstract_intersection = query_tokens & abstract_tokens

    query_weight = sum(_term_weight(t) for t in query_tokens)
    if query_weight == 0:
        return 0.0

    title_weight = sum(_term_weight(t) for t in title_intersection)
    abstract_weight = sum(_term_weight(t) for t in abstract_intersection)

    raw_score = ((title_weight / query_weight) * 0.70) + ((abstract_weight / query_weight) * 0.30)
    relevance_score = min(1.0, raw_score)

    # 5. Cap if agent query but lacks agent focus
    if is_agent_query and not has_agent_anchor:
        relevance_score = min(0.20, relevance_score)
    else:
        # Question-specific substantive keyword alignment
        if question_text:
            generic_ai_words = {
                "model", "models", "llm", "llms", "ai", "system", "systems", "language",
                "task", "tasks", "large", "study", "approach", "paper", "using", "based",
                "what", "how", "when", "which", "are", "the", "and", "for", "with"
            }
            q_words = {w for w in re.findall(r"[a-z0-9]+", question_text.lower()) if len(w) > 2 and w not in STOPWORDS and w not in generic_ai_words}
            if q_words:
                q_specific_hits = sum(1 for w in q_words if w in source_text)
                if q_specific_hits == 0:
                    relevance_score = min(0.10, relevance_score)
                elif q_specific_hits >= 2:
                    relevance_score = min(1.0, relevance_score + min(0.20, q_specific_hits * 0.05))

        # Intent concepts boost
        if intent and intent in _QUERY_INTENT_CONCEPTS:
            intent_concepts = _QUERY_INTENT_CONCEPTS[intent]
            generic_intent_terms = {
                "hallucination", "llm", "model", "ai", "learning", "system",
                "method", "approach", "study", "data", "benchmark", "retrieval",
                "generation", "agent", "agents"
            }
            specific_hits = sum(
                1 for concept in intent_concepts
                if concept in source_text and concept not in generic_intent_terms
            )
            intent_hits = sum(1 for concept in intent_concepts if concept in source_text)

            if specific_hits >= 3:
                boost = min(0.50, specific_hits * 0.12)
                relevance_score = min(1.0, relevance_score + boost)
            elif specific_hits >= 2:
                boost = min(0.35, specific_hits * 0.10)
                relevance_score = min(1.0, relevance_score + boost)
            elif specific_hits >= 1 or intent_hits >= 2:
                boost = 0.20
                relevance_score = min(1.0, relevance_score + boost)

    # 6. Legacy NLP domain boost and penalty
    if is_rag_query:
        concept_hits = sum(1 for concept in _NLP_DOMAIN_CONCEPTS if concept in source_text)
        if concept_hits >= 2:
            boost = min(0.50, concept_hits * 0.15)
            relevance_score = min(1.0, relevance_score + boost)

        non_nlp_hits = sum(1 for indicator in _NON_NLP_DOMAIN_INDICATORS if indicator in source_text)
        non_nlp_secondary = sum(1 for indicator in _NON_NLP_SECONDARY_INDICATORS if indicator in source_text)
        if non_nlp_hits >= 1 and non_nlp_hits > concept_hits:
            penalty = min(0.60, non_nlp_hits * 0.20 + non_nlp_secondary * 0.05)
            relevance_score = max(0.0, relevance_score - penalty)

    # 7. Domain-agnostic keyphrase matching boost
    query_lower = query_text.lower()
    words = [w for w in re.findall(r"[a-z0-9]+", query_lower) if w not in STOPWORDS and len(w) > 2]
    query_phrases = set()
    for i in range(len(words) - 1):
        query_phrases.add(f"{words[i]} {words[i+1]}")
    for i in range(len(words) - 2):
        query_phrases.add(f"{words[i]} {words[i+1]} {words[i+2]}")

    if query_phrases:
        phrase_hits = sum(1 for phrase in query_phrases if phrase in source_text)
        if phrase_hits >= 2:
            relevance_score = min(1.0, relevance_score + min(0.30, phrase_hits * 0.10))
        elif phrase_hits == 1:
            relevance_score = min(1.0, relevance_score + 0.10)

    return relevance_score


def _relevance_reason(source, query_text, score, intent=None, question_text=""):
    is_ai = _is_ai_query(query_text, question_text)
    fields_of_study = [str(f).lower().strip() for f in (source.get("fields_of_study") or [])]
    if is_ai and fields_of_study:
        has_allowed = any(any(allowed in f for allowed in _ALLOWED_CS_FIELDS) for f in fields_of_study)
        has_disallowed = any(any(disallowed in f for disallowed in _DISALLOWED_FIELDS_OF_STUDY) for f in fields_of_study)
        if has_disallowed and not has_allowed:
            return "domain_mismatch_fields_of_study"

    title_lower = str(source.get("title", "") or "").lower()
    source_text = f"{title_lower} {str(source.get('abstract') or source.get('content', '') or '').lower()}"

    if is_ai:
        title_mismatch = any(ind in title_lower for ind in _DOMAIN_MISMATCH_INDICATORS)
        has_ai_anchors = any(
            kw in source_text
            for kw in (
                "llm", "large language", "language model", "agent", "multi-agent",
                "single-agent", "prompting", "reasoning", "transformer",
                "artificial intelligence", "machine learning", "neural network"
            )
        )
        if title_mismatch and not has_ai_anchors:
            return "domain_mismatch_penalty"

    combined_query = f"{query_text} {question_text}".lower()
    is_agent_query = any(kw in combined_query for kw in ("agent", "agents", "multi-agent", "single-agent", "multiagent"))
    if is_agent_query:
        agent_anchors = (
            "agent", "agents", "multi-agent", "multiagent", "single-agent",
            "agent debate", "collaborative", "cooperative", "autogen", "metagpt",
            "chatdev", "camel", "prost", "subtask", "sub-task"
        )
        has_agent_anchor = any(anc in source_text for anc in agent_anchors)
        if not has_agent_anchor:
            has_broad_ai = any(kw in source_text for kw in ("language model", "llm", "large language", "reasoning", "transformer"))
            if has_broad_ai:
                return "general_llm_without_agent_focus"
            return "no_subject_anchor_match"

    query_tokens = _tokens(query_text)
    title_tokens = _tokens(source.get("title", ""))
    abstract = source.get("abstract") or source.get("content", "")
    abstract_tokens = _tokens(abstract)

    title_matches = query_tokens & title_tokens
    abstract_matches = query_tokens & abstract_tokens

    if intent and intent in _QUERY_INTENT_CONCEPTS:
        intent_concepts = _QUERY_INTENT_CONCEPTS[intent]
        specific_hits = sum(
            1 for c in intent_concepts
            if c in source_text and c not in {"agent", "agents", "llm", "model", "system"}
        )
        if intent == "multi_agent_comparison" and specific_hits >= 2:
            return "multi_agent_comparative_match"
        elif intent == "multi_agent_limitations" and specific_hits >= 2:
            return "multi_agent_failure_mode_match"
        elif intent == "multi_agent_boundary_conditions" and specific_hits >= 2:
            return "multi_agent_boundary_match"
        elif intent == "rag_vs_nonrag_comparison" and specific_hits >= 2:
            return "direct_comparison_match"
        elif intent == "rag_failure_modes" and specific_hits >= 2:
            return "failure_mode_match"
        elif intent == "hallucination_definition" and specific_hits >= 2:
            return "hallucination_definition_match"

    subject_anchors_set = {
        "agent", "agents", "multiagent", "multi", "single",
        "llm", "llms", "language", "model", "models", "gpt", "transformer", "transformers",
        "reasoning", "reason", "cot", "prompt", "prompting",
        "rag", "retrieval", "hallucination", "hallucinations", "factuality",
    }
    has_anchor_in_title = any(t in subject_anchors_set for t in title_matches)

    if score >= 0.5 and len(title_matches) >= 2 and has_anchor_in_title:
        return "strong_title_match"
    elif score >= 0.35 and len(title_matches) >= 1 and has_anchor_in_title:
        return "moderate_title_match"
    elif score >= 0.15 and len(abstract_matches) >= 2:
        return "abstract_match"
    elif score > 0.0:
        return "generic_overlap_only"
    else:
        return "no_significant_overlap"


def _planner_preference_score(source_type, preferred_source_types):
    if not preferred_source_types:
        return 0.5

    preferred_types = set()

    for preference in preferred_source_types:
        preference_key = str(preference).strip().lower()
        preferred_types.update(
            PREFERENCE_TO_SOURCE_TYPES.get(
                preference_key,
                set()
            )
        )

    if not preferred_types:
        return 0.5

    return 1.0 if source_type in preferred_types else 0.0


def _tavily_score(source):
    score = source.get("score")

    if score is None:
        return 0.5

    try:
        return max(0.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        return 0.5


def _normalize_policy_type_to_source_types(pref_str):
    clean = str(pref_str).strip().lower()
    if clean in PREFERENCE_TO_SOURCE_TYPES:
        return set(PREFERENCE_TO_SOURCE_TYPES[clean])
    underscore = clean.replace(" ", "_").replace("-", "_")
    if underscore in SOURCE_TYPES:
        return {underscore}
    if "blog" in clean:
        return {"corporate_blog", "personal_blog"}
    return {clean, underscore}


def _build_policy_quality_scores(source_policy):
    if not source_policy or not isinstance(source_policy, dict):
        return SOURCE_QUALITY_SCORES

    custom_scores = dict(SOURCE_QUALITY_SCORES)
    tiers = source_policy.get("tiers", [])
    for tier_info in tiers:
        tier_num = tier_info.get("tier", 3)
        role = str(tier_info.get("role", "evidence")).lower()
        types = tier_info.get("source_types", [])

        if tier_num == 1:
            base_score = 0.95
        elif tier_num == 2:
            base_score = 0.85
        else:
            base_score = 0.65 if role == "evidence" else 0.50

        for t in types:
            mapped_types = _normalize_policy_type_to_source_types(t)
            for mt in mapped_types:
                if mt in SOURCE_TYPES:
                    custom_scores[mt] = base_score

    return custom_scores


def score_source(source, research_question, custom_quality_scores=None):
    """Score one source relative to one Planner question."""

    source_type = source.get(
        "source_type",
        "other"
    )

    query_texts = [
        research_question.get("question", "")
    ]

    question_id = str(
        research_question.get("id", "")
    ).strip().upper()

    for discovery in source.get("discovered_by", []):
        if discovery.get("question_id", "").upper() == question_id:
            query_texts.append(discovery.get("query_text", ""))

    best_relevance = 0.0
    best_relevance_reason = "no_query"
    intent = _detect_query_intent(
        research_question.get("question", ""),
        research_question.get("type")
    )
    content_status = str(source.get("content_status", "") or "").lower()
    question_text = research_question.get("question", "")
    for query in query_texts:
        q_score = _relevance_score(
            source,
            query,
            intent=intent,
            content_status=content_status,
            question_text=question_text
        )
        if q_score > best_relevance:
            best_relevance = q_score
            best_relevance_reason = _relevance_reason(
                source,
                query,
                q_score,
                intent=intent,
                question_text=question_text
            )

    if best_relevance == 0.0 and query_texts:
        best_relevance_reason = _relevance_reason(
            source,
            query_texts[0],
            0.0,
            intent=intent,
            question_text=question_text
        )

    relevance_score = best_relevance
    scores_dict = custom_quality_scores if custom_quality_scores is not None else SOURCE_QUALITY_SCORES
    source_quality_score = scores_dict.get(source_type, scores_dict.get("other", 0.40))
    planner_preference_score = _planner_preference_score(
        source_type,
        research_question.get("preferred_source_types", [])
    )
    tavily_score = _tavily_score(source)

    content_status_bonus = 0.0
    if content_status == "full":
        content_status_bonus = 0.15
    elif content_status == "partial":
        content_status_bonus = 0.10
    elif content_status == "snippet_only":
        content_status_bonus = 0.05
    elif content_status == "failed":
        content_status_bonus = -0.10

    requires_quantitative = bool(research_question.get("requires_quantitative_evidence", False))
    quantitative_bonus = 0.0
    if requires_quantitative:
        source_text_all = f"{source.get('title', '')} {source.get('abstract', '')} {source.get('content', '')}".lower()
        has_numbers = bool(re.search(r"\b\d+(?:\.\d+)?%|\b\d+\.\d+\b|\baccuracy\b|\bf1\b|\bpass@1\b|\bbaseline\b|\bscore\b", source_text_all))
        if has_numbers:
            quantitative_bonus = 0.08

    requires_counter = bool(research_question.get("requires_counter_evidence", False))
    counter_bonus = 0.0
    if requires_counter:
        is_counter_disc = any(
            str(d.get("query_type", "")).lower() == "counter"
            for d in source.get("discovered_by", [])
            if str(d.get("question_id", "")).upper() == question_id
        )
        source_text_all = f"{source.get('title', '')} {source.get('abstract', '')} {source.get('content', '')}".lower()
        has_counter_signals = any(
            kw in source_text_all
            for kw in ("limitation", "failure", "degradation", "overhead", "bottleneck", "trade-off", "underperform", "error propagation")
        )
        if is_counter_disc or has_counter_signals:
            counter_bonus = 0.08

    if relevance_score <= 0.05:
        # Crucial gate: Irrelevant papers cannot ride on prestige/quality scores alone
        final_score = relevance_score * RANKING_WEIGHTS["relevance"]
    elif relevance_score < 0.15:
        # Low-relevance papers capped so they cannot beat domain-relevant sources
        final_score = min(
            0.20,
            relevance_score * RANKING_WEIGHTS["relevance"]
            + source_quality_score * 0.05
        )
    else:
        authority_score = (
            source_quality_score * RANKING_WEIGHTS["source_quality"]
            + planner_preference_score * RANKING_WEIGHTS["planner_preference"]
            + tavily_score * RANKING_WEIGHTS["tavily"]
        )
        bonuses = content_status_bonus + quantitative_bonus + counter_bonus
        # Multiplicative relevance weighting: Authority and bonuses cannot overpower actual question relevance
        final_score = (
            relevance_score * RANKING_WEIGHTS["relevance"]
            + (authority_score + bonuses) * relevance_score
        )

    return {
        "relevance_score": round(relevance_score, 4),
        "relevance_reason": best_relevance_reason,
        "source_quality_score": round(source_quality_score, 4),
        "planner_preference_score": round(planner_preference_score, 4),
        "tavily_score": round(tavily_score, 4),
        "content_status_bonus": round(content_status_bonus, 4),
        "quantitative_bonus": round(quantitative_bonus, 4),
        "counter_bonus": round(counter_bonus, 4),
        "final_score": round(final_score, 4)
    }


def compute_evidence_eligibility(source, source_policy=None):
    """Determine whether a source is eligible as evidence, with an explainable reason."""
    if source.get("content_status") == "failed" and not source.get("abstract") and not source.get("content"):
        return False, "content_extraction_failed"

    source_type = source.get("source_type", "other")

    if source_policy and isinstance(source_policy, dict):
        discovery_types = {str(t).lower().strip() for t in source_policy.get("discovery_only_source_types", [])}
        for disc in discovery_types:
            mapped = _normalize_policy_type_to_source_types(disc)
            if source_type in mapped:
                return False, "policy_discovery_only"

        eligible_types = {str(t).lower().strip() for t in source_policy.get("evidence_eligible_source_types", [])}
        for elig in eligible_types:
            mapped = _normalize_policy_type_to_source_types(elig)
            if source_type in mapped:
                return True, "eligible"

    if source_type in EVIDENCE_ELIGIBLE_SOURCE_TYPES:
        return True, "eligible"
    reason = EVIDENCE_EXCLUSION_REASONS.get(source_type, "unsupported_source_type")
    return False, reason


def rank_sources(sources, research_questions, source_policy=None):
    """Classify and rank all canonical sources without filtering them."""

    questions_by_id = {
        str(question.get("id", "")).strip().upper(): question
        for question in research_questions
    }

    policy_scores = _build_policy_quality_scores(source_policy)

    for source in sources:
        source_type = classify_source(source)
        if source_type == "other" and source.get("source_type") in SOURCE_TYPES:
            source_type = source["source_type"]
        source["source_type"] = source_type if source_type in SOURCE_TYPES else "other"

        evidence_eligible, eligibility_reason = compute_evidence_eligibility(source, source_policy=source_policy)
        source["evidence_eligible"] = evidence_eligible
        source["eligibility_reason"] = eligibility_reason

        ranking_by_question = {}

        for question_id, question in questions_by_id.items():
            ranking_by_question[question_id] = score_source(
                source,
                question,
                custom_quality_scores=policy_scores
            )

        if ranking_by_question:
            best_question_id, best_score = max(
                ranking_by_question.items(),
                key=lambda item: (
                    item[1]["final_score"],
                    item[0]
                )
            )
            source["ranking_score"] = best_score["final_score"]
            source["ranking_question_id"] = best_question_id
        else:
            source["ranking_score"] = 0.0
            source["ranking_question_id"] = ""

        source["ranking_by_question"] = ranking_by_question

    def _sort_key(s):
        score = float(s.get("ranking_score", 0.0) or 0.0)
        sid = str(s.get("source_id", "") or "")
        is_tavily = sid.startswith("S") and sid[1:].isdigit()
        num = int(sid[1:]) if is_tavily else 999999
        return (-score, num, sid)

    return sorted(sources, key=_sort_key)


def print_ranking_diagnostics(
    sources,
    research_questions,
    top_n=5
):
    """Print concise per-question ranking diagnostics."""

    for question in research_questions:

        question_id = str(
            question.get(
                "id",
                ""
            )
        ).strip().upper()

        ranked_sources = [
            source
            for source in sources
            if question_id in source.get(
                "ranking_by_question",
                {}
            )
        ]

        ranked_sources.sort(
            key=lambda source: source[
                "ranking_by_question"
            ][question_id][
                "final_score"
            ],
            reverse=True
        )

        print(
            f"\n{question_id}"
        )

        print(
            "\nQuestion:"
        )

        print(
            question.get(
                "question",
                ""
            )
        )

        print(
            "\nPlanner Preferred Types:"
        )

        for preferred_type in question.get(
            "preferred_source_types",
            []
        ):

            print(
                f"- {preferred_type}"
            )

        print(
            "\nTOP RANKED SOURCES"
        )

        for position, source in enumerate(
            ranked_sources[:top_n],
            start=1
        ):

            scores = source[
                "ranking_by_question"
            ][question_id]

            provenance_types = sorted({
                discovery.get(
                    "query_type",
                    ""
                )
                for discovery in source.get(
                    "discovered_by",
                    []
                )
                if discovery.get(
                    "question_id",
                    ""
                ).strip().upper() == question_id
            })

            print(
                f"\n{position}. {source.get('source_id', '')}"
            )

            print(
                f"   title: {source.get('title', '')}"
            )

            print(
                f"   type: {source.get('source_type', 'other')}"
            )

            print(
                "   query provenance: "
                f"{', '.join(provenance_types) or 'unknown'}"
            )

            print(
                "   relevance: "
                f"{scores['relevance_score']:.4f}"
            )

            print(
                "   quality: "
                f"{scores['source_quality_score']:.4f}"
            )

            print(
                "   preference: "
                f"{scores['planner_preference_score']:.4f}"
            )

            print(
                "   tavily: "
                f"{scores['tavily_score']:.4f}"
            )

            print(
                "   final: "
                f"{scores['final_score']:.4f}"
            )

        counter_sources = [
            source
            for source in ranked_sources
            if any(
                discovery.get(
                    "query_type",
                    ""
                ).strip().lower() == "counter"
                and discovery.get(
                    "question_id",
                    ""
                ).strip().upper() == question_id
                for discovery in source.get(
                    "discovered_by",
                    []
                )
            )
        ]

        print(
            "\nCOUNTER-EVIDENCE CANDIDATES"
        )

        for source in counter_sources[:top_n]:

            score = source[
                "ranking_by_question"
            ][question_id][
                "final_score"
            ]

            print(
                f"{source.get('source_id', '')} | "
                f"type: {source.get('source_type', 'other')} | "
                f"final: {score:.4f}"
            )
