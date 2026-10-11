"""
Builds a comprehensive, publication-grade Question Bank PDF and Word document
for the Major Project Mid-Term Evaluation / Viva Defense of:
"Autonomous Research Report Agent: An Evidence-Driven Multi-Agent Framework for Automated Research"
School of Computer Science, UPES Dehradun.
"""

import os
import shutil
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# COLOR PALETTE
# ---------------------------------------------------------------------------
NAVY_PRIMARY = "#0B2545"      # Deep Navy
NAVY_SECONDARY = "#134074"    # Slate Navy
ACCENT_BLUE = "#1D4E89"       # Royal Blue
ACCENT_CYAN = "#0056B3"       # Highlight Blue
TEXT_DARK = "#222222"         # Charcoal Body
TEXT_MUTED = "#555555"        # Subtitle/Meta
BG_LIGHT = "#F4F7F9"          # Light Card Fill
BG_HIGHLIGHT = "#EBF3FB"      # Question Callout Fill
BORDER_COLOR = "#D0D7DE"      # Border Gray
QUESTION_BADGE = "#0B2545"

# ---------------------------------------------------------------------------
# 50 COMPREHENSIVE VIVA & PRESENTATION QUESTIONS AND MODEL ANSWERS
# ---------------------------------------------------------------------------
QUESTION_BANK = [
    # -------------------------------------------------------------
    # CATEGORY 1: PROJECT OVERVIEW, MOTIVATION & NOVELTY
    # -------------------------------------------------------------
    {
        "category": "Category 1: Project Overview, Motivation & Novelty",
        "questions": [
            {
                "q": "Q1. What is the core problem that your Autonomous Research Report Agent (ARA) is solving?",
                "a": "Conventional LLMs and standard RAG systems suffer from four major vulnerabilities when applied to academic research: (1) Superficial context stuffing where either short 100-word web snippets or entire 15-page PDFs are shoved into prompts, causing severe 'Lost-in-the-Middle' context decay; (2) Confirmation bias where naive search queries only retrieve confirmatory evidence; (3) Severe API bottlenecks and HTTP 429 rate limits caused by calculating dense vector embeddings across hundreds of uncurated candidate documents; and (4) Citation hallucination. ARA solves these through formal planning contracts, tri-source academic discovery, two-stage cascade indexing, and passage-level evidence grounding.",
                "tip": "Keep it crisp: mention 'Lost-in-the-Middle', 'Confirmation Bias', 'API Bottlenecks', and 'Citation Hallucination'."
            },
            {
                "q": "Q2. Why can't a researcher simply use ChatGPT, Perplexity, or standard Google Scholar search?",
                "a": "Standard ChatGPT has a static knowledge cutoff and hallucinates citations. Perplexity and web search agents rely almost exclusively on commercial web search APIs (Bing/Google), completely ignoring structured academic citation graphs (OpenAlex, Semantic Scholar) and peer-reviewed metadata. Furthermore, they do not formulate competing hypotheses or check falsification criteria, nor do they provide character-level auditability back to exact paragraphs within arXiv PDFs. Google Scholar provides records but cannot autonomously read, chunk, re-rank, and synthesize findings.",
                "tip": "Emphasize that Perplexity is a web search summarizer, whereas ARA is an evidence-grounded scientific research framework."
            },
            {
                "q": "Q3. In one minute, what is the core technical novelty of your project?",
                "a": "Our novelty consists of three architectural innovations: (1) A Two-Stage Cascade Hybrid Retrieval Engine combining pure-Python local BM25 scoring with Gemini dense vector re-ranking, cutting embedding API calls by 93% and running on the CPU in 21 milliseconds; (2) A Sliding-Window Scientific Passage Chunker (350 words, 50-word overlap) that extracts the top 5 high-density empirical paragraphs from 15-page PDFs to prevent transformer attention decay; and (3) A Hierarchical Academic Deduplication Engine resolving preprints and published papers across DOI, arXiv ID, URL, and fuzzy title matching with 92.2% efficiency.",
                "tip": "Memorize the numbers: '93% API reduction', '21 ms local CPU BM25', '350w/50w overlap', '92.2% deduplication efficiency'."
            },
            {
                "q": "Q4. Why did you choose an evidence-driven multi-agent framework rather than a single prompt-chained script?",
                "a": "Prompt chaining tightly couples reasoning, retrieval, and synthesis into a monolithic black box where failure in one stage corrupts the entire output. A multi-agent framework decouples responsibilities across distinct agents (Planner, Researcher, Validator, Synthesizer) governed by formal schema contracts (such as data/research_plan.json). This allows us to independently benchmark, unit-test, and optimize each stage—for example, evaluating the retrieval engine's precision without invoking LLM generation costs.",
                "tip": "Explain that agents enforce formal schema contracts rather than conversational back-and-forth."
            },
            {
                "q": "Q5. What are the primary application domains where ARA provides the highest value?",
                "a": "ARA is designed for: (1) Systematic scientific literature reviews across computer science, biomedicine, and engineering; (2) Evidence-based prior art discovery for algorithmic and patent research; (3) Technical due diligence comparing conflicting engineering benchmarks; and (4) Academic research assistance helping graduate and doctoral scholars formulate and test hypotheses with counter-evidence.",
                "tip": "Relate this directly to Section 1.4 of your report."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 2: SYSTEM ARCHITECTURE & MULTI-AGENT PLANNING
    # -------------------------------------------------------------
    {
        "category": "Category 2: System Architecture & Multi-Agent Planning (Phase 1)",
        "questions": [
            {
                "q": "Q6. Explain the end-to-end architecture of your system across its 4 phases.",
                "a": "Phase 1 (Completed): Research Planner decomposes user inquiries into domain categories, 3-5 sub-questions, working and competing hypotheses, and falsification criteria, outputting data/research_plan.json. Phase 2 (Completed): Tri-source discovery across Tavily, OpenAlex, and Semantic Scholar, hierarchical deduplication, 6-step semantic indexing, two-stage BM25/Vector filtering, and sliding-window PDF passage chunking, emitting data/research_evidence.json. Phase 3 (Planned for End-Term): Sentence-level Natural Language Inference (NLI) evidence validation and autonomous iterative re-search loops. Phase 4 (Planned for End-Term): Calibrated epistemic report synthesis and direct headless PDF compilation.",
                "tip": "Clearly delineate Mid-Term deliverables (Phases 1 & 2) from End-Term deliverables (Phases 3 & 4)."
            },
            {
                "q": "Q7. What is the role of the Research Planner and why is domain classification necessary?",
                "a": "The Planner (planner/planner.py) prevents undirected search. When given an open inquiry, it performs domain classification (Technical, Biomedical, Legal, General). This classification is necessary because retrieval parameters must adapt: technical papers require arXiv preprint queries and benchmark metrics, biomedical inquiries prioritize peer-reviewed DOI indexed works with clinical trial consensus, and legal inquiries prioritize statutory authorities.",
                "tip": "Highlight that different domains have fundamentally different evidence standards."
            },
            {
                "q": "Q8. How does your system address confirmation bias during the planning stage?",
                "a": "Standard search agents formulate queries that only look for confirmatory evidence. In ARA, the Planner is strictly prompted to generate both a primary Working Hypothesis and Competing Alternative Hypotheses, along with explicit empirical Falsification Criteria. These competing hypotheses generate targeted sub-queries that force the search agent to discover dissenting views, benchmark degradations, and counter-evidence.",
                "tip": "Mention Karl Popper's falsification criterion: science requires actively attempting to disprove the hypothesis."
            },
            {
                "q": "Q9. What is the exact data contract produced by Phase 1, and where is it stored?",
                "a": "Phase 1 serializes a machine-readable JSON artifact at data/research_plan.json. It contains: domain classification, query list, orthogonal sub-questions (addressing foundations, mechanisms, benchmarks, and trade-offs), working hypothesis, competing hypotheses, falsification criteria, and required evidence quotas (minimum peer-reviewed sources, quantitative tables, and counter-evidence count).",
                "tip": "Mention that this contract guarantees deterministic, testable boundaries for Phase 2."
            },
            {
                "q": "Q10. How does the system ensure that the LLM produces valid JSON schemas without formatting errors?",
                "a": "We enforce strict JSON output schemas via structured prompting, low-temperature sampling (0.1–0.2), and defensive validation parsing with fallbacks. If an LLM response contains markdown wrapping (e.g. ```json ... ```), regex sanitizers extract the inner JSON string before schema verification.",
                "tip": "Explain that robustness against non-deterministic completions is a core engineering requirement."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 3: ACADEMIC DISCOVERY & MULTI-KEY DEDUPLICATION
    # -------------------------------------------------------------
    {
        "category": "Category 3: Academic Discovery & Multi-Key Deduplication (Phase 2A & 2B)",
        "questions": [
            {
                "q": "Q11. Why did you integrate three search providers (Tavily, OpenAlex, Semantic Scholar) instead of just one?",
                "a": "Each provider has unique strengths: Tavily accesses the live web for contemporary whitepapers, engineering blogs, and newest preprints; OpenAlex accesses over 250 million scholarly records with rich metadata, open-access full-text PDF links, and institutional affiliations; Semantic Scholar provides academic citation graphs and influential citation metrics. Combining them provides a comprehensive, multi-angle scientific corpus.",
                "tip": "Call it 'Tri-Provider Scholarly Ingestion'."
            },
            {
                "q": "Q12. How does the system handle unauthenticated API rate limits on Semantic Scholar or OpenAlex?",
                "a": "Our unified asynchronous discovery layer (search_agent/search_engine.py) implements exponential backoff with jitter and graceful degradation. If Semantic Scholar returns HTTP 429 (Too Many Requests), the engine logs the event, automatically falls back to OpenAlex and Tavily academic search routes, and continues execution without terminating the pipeline.",
                "tip": "Evaluators love fault tolerance. Mention 'exponential backoff' and 'graceful fallback'."
            },
            {
                "q": "Q13. How does your Hierarchical Multi-Key Deduplication Engine work?",
                "a": "In search_agent/sources.py, deduplication operates in a 4-level hierarchy: (1) DOI Matching: If two records share a Digital Object Identifier, they are merged; (2) arXiv Identifier Matching: Canonical arXiv IDs (e.g., 2401.09136) are normalized and matched; (3) Normalized URL Matching: Query parameters, trailing slashes, and protocol variations are stripped; (4) Fuzzy Title Matching: Levenshtein distance similarity (>90%) with normalized punctuation consolidates preprints with their final journal titles.",
                "tip": "Mention the hierarchy: DOI -> arXiv ID -> URL -> Fuzzy Title."
            },
            {
                "q": "Q14. What were your empirical deduplication results in experimental benchmarks?",
                "a": "Across benchmark executions on complex scientific prompts, the discovery engine harvested 539 gross candidate sources. Our multi-key deduplication module merged 42 redundant records, retaining 497 unique academic sources, achieving a 92.2% deduplication retention efficiency while eliminating duplicate citations in the bibliography.",
                "tip": "Quote Section 6.1 of the report directly."
            },
            {
                "q": "Q15. What is Logarithmic Citation Authority Scaling and why did you implement it?",
                "a": "If raw citation counts are used directly for ranking, foundational papers from 2017 with 50,000 citations (like 'Attention Is All You Need') would completely dominate every search ranking, drowning out critical 2025 breakthroughs that have zero or few citations simply due to recency. We apply a logarithmic dampening function: Authority = log(1 + citations) / log(1 + max_citations). This normalizes credibility without penalizing recent preprints.",
                "tip": "Formula: Authority = log(1 + citations) / log(1 + max_citations). This shows strong mathematical maturity."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 4: THE 6-STEP IR ENGINE & MATHEMATICAL FOUNDATIONS
    # -------------------------------------------------------------
    {
        "category": "Category 4: The 6-Step IR Engine & Mathematical Foundations",
        "questions": [
            {
                "q": "Q16. Walk the panel through the 6 steps of your Information Retrieval engine.",
                "a": "Step 1: Stop-Word Removal using a tailored academic stop-word lexicon. Step 2: Pure-Python Porter Stemming implementing all 5 stages of morphological suffix stripping (conforming strictly to Porter, 1980). Step 3: Inverted Index & BM25 Scoring to compute probabilistic lexical relevance. Step 4: Two-Stage Coarse Filtering narrowing ~500 candidates down to 35. Step 5: Dense Vector Embedding via Google Gemini text-embedding-004 and Cosine Similarity calculation. Step 6: Prompt-Aligned Hybrid Re-ranking combining BM25 and vector scores.",
                "tip": "Walk through Step 1 to Step 6 sequentially as implemented in search_agent/semantic_indexer.py."
            },
            {
                "q": "Q17. Explain the mathematical formulation of Robertson–Spärck Jones BM25 term weighting.",
                "a": "BM25 scores a query Q against document D using: Score(D, Q) = sum_{q in Q} [ IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl))) ]. Here, f(q, D) is term frequency, |D| is document length, avgdl is average document length across the corpus, k1 = 1.5 governs term frequency saturation, and b = 0.75 controls the degree of document length penalization.",
                "tip": "Mention parameters k1 = 1.5 and b = 0.75. Explain that k1 prevents a term repeated 20 times from having 20x the weight."
            },
            {
                "q": "Q18. What is Inverse Document Frequency (IDF) in BM25 and why does it matter?",
                "a": "IDF penalizes common terms across the entire corpus and rewards rare, high-signal terms. In BM25, IDF(q) = ln((N - n(q) + 0.5) / (n(q) + 0.5) + 1), where N is the total number of documents and n(q) is the number of documents containing query term q. A term like 'retrieval' appearing in almost every document gets low IDF, whereas a specific term like 'falsification' gets high IDF.",
                "tip": "Explain that IDF ensures informative domain keywords dominate the score."
            },
            {
                "q": "Q19. Why did you write a custom Porter Stemmer in pure Python instead of importing NLTK or spaCy?",
                "a": "NLTK and spaCy are heavy external dependencies with compiled C-extensions, large data package downloads (nltk.download('punkt')), and platform-specific compilation overhead. By engineering a self-contained, 5-stage Porter stemmer in pure Python, our system runs with 100% portability across Windows, Linux, and minimal Docker containers with zero binary dependencies and instant startup time.",
                "tip": "Evaluators value dependency hygiene and lightweight pure-Python engineering."
            },
            {
                "q": "Q20. How is Cosine Similarity computed in Step 5?",
                "a": "Cosine similarity measures the cosine of the angle between two non-zero vectors in multi-dimensional semantic space: CosSim(u, v) = (u . v) / (||u|| * ||v||). In our pipeline, u is the 768-dimensional dense embedding of the research sub-question, and v is the candidate's embedding from Google Gemini text-embedding-004. Values range from -1.0 to +1.0 (typically 0.0 to 1.0 for normalized text embeddings).",
                "tip": "Explain that dot product over magnitude product captures semantic orientation regardless of length."
            },
            {
                "q": "Q21. How do you combine BM25 scores and Vector Cosine scores in Step 6?",
                "a": "Because BM25 yields unbounded positive scores while Cosine Similarity is bounded between 0 and 1, we first min-max normalize BM25 scores across the candidate set into the range [0.0, 1.0]. We then calculate the final hybrid score as: FinalScore = 0.35 * Normalized_BM25 + 0.65 * Dense_Cosine_Similarity. This balances exact keyword precision (35%) with semantic conceptual match (65%).",
                "tip": "Explain min-max normalization: (score - min) / (max - min), followed by the 35/65 weighted sum."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 5: TWO-STAGE HYBRID FILTERING & OPTIMIZATION
    # -------------------------------------------------------------
    {
        "category": "Category 5: Two-Stage Hybrid Filtering & Optimization",
        "questions": [
            {
                "q": "Q22. What is the two-stage candidate filtering mechanism and why is it essential?",
                "a": "In a naive RAG system, discovering 500 candidate papers across 3 APIs means making 500 remote embedding API requests. This creates 10+ seconds of network latency, costs money, and frequently crashes due to HTTP 429 rate limits. In our two-stage cascade: Stage 1 uses localized, in-memory BM25 to coarse-filter the 500 candidates down to 35 in 21 milliseconds on the CPU. Stage 2 generates dense embeddings solely for those 35 high-probability candidates.",
                "tip": "This is one of your strongest benchmark results: 500 -> 35 on CPU in 0.021s."
            },
            {
                "q": "Q23. What are the exact performance numbers for your two-stage optimization?",
                "a": "In our experimental benchmarks on 497 unique candidates: Stage 1 BM25 coarse filtering executed locally on the CPU in exactly 0.021 seconds (21 milliseconds), reducing candidates from 497 to 35. Stage 2 dense re-ranking required only 35 embedding calls instead of 497, achieving an exact 93.0% reduction in vector embedding API consumption.",
                "tip": "State clearly: '0.021 seconds latency' and '93.0% API reduction'."
            },
            {
                "q": "Q24. Does filtering 500 candidates down to 35 risk discarding semantically relevant papers (False Negatives)?",
                "a": "We conducted recall validation tests. Because scientific papers feature highly informative technical keywords in their titles and abstracts, the top 35 BM25 pool captures over 96% of semantically relevant works. By setting the cutoff at 35 (rather than 10 or 15), we maintain high candidate recall while keeping the downstream dense re-ranking batch well within API rate boundaries.",
                "tip": "Explain that technical literature is lexically rich, making BM25 an ideal coarse filter."
            },
            {
                "q": "Q25. How do you handle cases where a query has synonyms not present in the paper title?",
                "a": "That is precisely why Stage 2 dense vector embedding is paired with Stage 1. Even if a paper only matches 1 or 2 keywords in BM25, its inclusion in the top 35 allows Stage 2 dense embeddings to recognize semantic equivalence (e.g. 'hallucination reduction' vs 'factual grounding'). Furthermore, Phase 1 Planner generates multiple orthogonal sub-queries with diverse terminology.",
                "tip": "Explain that the Planner's multi-angle queries provide vocabulary diversification."
            },
            {
                "q": "Q26. What is the memory footprint and CPU overhead of running BM25 locally?",
                "a": "The memory footprint is negligible: an in-memory inverted index of 500 titles and abstracts occupies less than 2.5 megabytes of RAM. The scoring involves simple integer frequency lookups and floating-point arithmetic, which is why execution finishes in 21 milliseconds on a single standard CPU thread.",
                "tip": "Highlight that no external vector database daemon (Pinecone, Chroma, Milvus) is required for Phase 2 indexing."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 6: SCIENTIFIC PDF PROCESSING & "LOST-IN-THE-MIDDLE"
    # -------------------------------------------------------------
    {
        "category": "Category 6: Scientific PDF Processing & 'Lost-in-the-Middle' (Phase 2C)",
        "questions": [
            {
                "q": "Q27. What is the 'Lost-in-the-Middle' phenomenon and how does it affect scientific RAG?",
                "a": "Documented by Liu et al. (2024) in Transactions of the ACL, 'Lost in the Middle' proves that language models retrieve information accurately from the beginning and end of long input contexts, but their attention degrades precipitously (up to 40% performance drop) when relevant evidence is positioned within the middle 40%–60% of the prompt. Dumping entire 15-page PDFs into prompts causes the LLM to overlook critical quantitative metrics and ablation tables buried in the middle.",
                "tip": "Cite the paper: Liu et al. (2024), Transactions of the Association for Computational Linguistics."
            },
            {
                "q": "Q28. How does your Deep PDF Passage Chunking algorithm solve this?",
                "a": "When an arXiv scientific PDF is parsed via pypdf (averaging 10,000 to 15,000 words), documents >= 3,500 characters are segmented into 350-word sliding windows with a 50-word overlap. Each passage chunk is scored against the research sub-question using our hybrid indexing algorithm. Only the top 5 highest-signal empirical passages are extracted and passed to the LLM prompt.",
                "tip": "Parameters: 350-word window, 50-word overlap, top 5 passages extracted."
            },
            {
                "q": "Q29. Why did you choose a 350-word window with a 50-word overlap instead of standard 1000-token chunks?",
                "a": "A 350-word chunk corresponds roughly to 1 to 2 dense scientific paragraphs—the exact semantic unit where an author presents an experimental hypothesis, methodology, or quantitative result. The 50-word sliding overlap ensures that sentences crossing chunk boundaries are not truncated mid-premise. Larger 1000-token chunks re-introduce context dilution, while smaller 100-word chunks sever empirical context.",
                "tip": "Explain that 350 words is the natural semantic boundary of a scientific paragraph."
            },
            {
                "q": "Q30. How does ARA download and parse arXiv PDFs in real time?",
                "a": "In search_agent/content_retriever.py, when a discovered candidate contains an arXiv ID or open-access PDF link, the engine downloads the PDF stream with a strict timeout and user-agent header. It parses text page-by-page using pypdf, removes non-printable ligature artifacts and header/footer boilerplates, and passes the clean text stream to the passage chunker.",
                "tip": "Mention handling of timeouts and text sanitization."
            },
            {
                "q": "Q31. How much prompt token reduction does passage chunking achieve?",
                "a": "A standard 15-page scientific preprint averages 10,000 to 15,000 words (~13,000 to 20,000 tokens). Extracting the top 5 passages of 350 words totals approximately 1,750 words (~2,300 tokens). This achieves over a 70% to 85% reduction in token overhead per paper, eliminating prompt token bloat while ensuring high attention focus.",
                "tip": "Numbers: from 15,000 words down to 1,750 words = >70% token reduction."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 7: SOFTWARE ENGINEERING, TESTING & VERIFICATION
    # -------------------------------------------------------------
    {
        "category": "Category 7: Software Engineering, Testing & Verification",
        "questions": [
            {
                "q": "Q32. How many automated unit tests validate your repository, and what is your pass rate?",
                "a": "A total of 170 unit tests pass cleanly with 100% regression stability using pytest. These span: tests/test_semantic_indexer.py (7 tests covering stemmer invariance, BM25 weighting, cosine ranking, and chunking), tests/test_phase2_completion.py (18 tests covering connectors and fallback logic), tests/test_cli_ui.py (18 tests covering terminal progress rendering), and tests/test_end_to_end_research_eval.py (28 tests verifying complete contract schema compliance).",
                "tip": "State clearly: '170 unit tests, 100% passing cleanly under pytest'."
            },
            {
                "q": "Q33. What is the purpose of demo_semantic_pipeline.py?",
                "a": "demo_semantic_pipeline.py is a standalone, offline interactive verification script built with rich. It allows examiners to visualize all 7 stages of indexing in real time: raw text tokenization, stop-word removal, 5-stage Porter stemming roots, in-memory BM25 inverted index tables, dense vector generation, cosine ranking scores, and sliding-window PDF passage chunking on a sample scientific document without incurring live API costs.",
                "tip": "Offer to run demo_semantic_pipeline.py live on the terminal during the viva!"
            },
            {
                "q": "Q34. How is the codebase structured across modules and directories?",
                "a": "The repository adheres to modular separation: planner/ handles Phase 1 decomposition and hypothesis contracts; search_agent/ contains search_engine.py (connectors), sources.py (deduplication), semantic_indexer.py (BM25, embeddings, chunker), content_retriever.py (PDF parsing), and evidence_extractor.py (fact extraction); reports/ contains HTML and document generators; and tests/ contains the 170-test validation suite.",
                "tip": "Point to Section 5.1 Table in the Mid-Term Report."
            },
            {
                "q": "Q35. How do you prevent environment drift and ensure reproducible builds across machines?",
                "a": "All dependencies are pinned in requirements.txt and isolated within Python virtual environments. Because our IR engine (Porter stemmer, BM25, and deduplication) is engineered in pure Python with zero compiled C-extensions, the repository builds and passes all 170 tests identically across Windows, macOS, and Linux without native build-tool dependencies.",
                "tip": "Emphasize 'pure-Python portability' and 'pinned requirements.txt'."
            },
            {
                "q": "Q36. How do you monitor and display execution progress in the terminal CLI?",
                "a": "In main.py and the ui/ module, we utilize the rich library to display real-time terminal progress spinners, live provider status indicators (Tavily, OpenAlex, Semantic Scholar), harvested candidate counts, deduplication stats, and elapsed timestamps.",
                "tip": "Mention user experience: academic researchers need visibility into long-running multi-source harvesting."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 8: END-TERM ROADMAP, PHASE 3 & 4 DELIVERABLES
    # -------------------------------------------------------------
    {
        "category": "Category 8: End-Term Roadmap, Phase 3 & 4 Deliverables",
        "questions": [
            {
                "q": "Q37. What is planned for Phase 3 (Evidence Validation) in Major Project Part 2?",
                "a": "Phase 3 introduces an automated Evidence Validation Layer. It will implement sentence-level Natural Language Inference (NLI) to audit extracted claims against the raw PDF text, classifying claims as Entailment, Contradiction, or Neutral. It will also compute an Evidence Sufficiency Scorecard checking whether required quantitative data points and counter-evidence quotas have been satisfied.",
                "tip": "Mention sentence-level NLI: checking if the source text actually entails the extracted claim."
            },
            {
                "q": "Q38. How will the Autonomous Iterative Re-Search Loop work in Phase 3?",
                "a": "If the Evidence Sufficiency Scorecard flags gaps—such as an absence of quantitative benchmark comparisons or missing counter-evidence for a competing hypothesis—the agent will not proceed to synthesis. Instead, it will autonomously formulate targeted secondary queries, query the search connectors again, and index supplementary literature until evidence sufficiency criteria are fulfilled.",
                "tip": "This transforms ARA from a feed-forward pipeline into a true reflective agent."
            },
            {
                "q": "Q39. What is Epistemic Confidence Calibration in Phase 4?",
                "a": "Rather than presenting all LLM assertions with unearned certainty, the synthesizer will calculate a calibrated epistemic confidence score (ranging from 0.0 to 1.0) for every major section and conclusion. The score is calibrated against: the number of independent peer-reviewed sources supporting the finding, total citation authority, the absence of empirical contradictions, and the presence of verified quantitative data.",
                "tip": "Explain that scientific reports must distinguish between established consensus and speculative preprints."
            },
            {
                "q": "Q40. How will deterministic citation anchors work in the final report?",
                "a": "Every claim in the synthesized report will feature deterministic numerical citation anchors ([1], [2]) linking directly to the bibliography. Each bibliographic entry contains the canonical URL (prioritizing DOI, publisher URL, or arXiv landing page), publication year, author list, and the exact verbatim quote extracted from the paper.",
                "tip": "Point out that this eliminates citation fabrication entirely."
            },
            {
                "q": "Q41. How will the final report be compiled into a publication-ready PDF in Phase 4?",
                "a": "We are integrating WeasyPrint to directly compile publication-grade, paginated PDF documents from the final HTML report artifact. WeasyPrint supports CSS3 paged media specifications (@page rules, page-break controls, running headers, and footnote anchors), producing clean print deliverables headlessly.",
                "tip": "Mention WeasyPrint and CSS3 Paged Media."
            }
        ]
    },

    # -------------------------------------------------------------
    # CATEGORY 9: RAPID-FIRE / TOUGH DEFENSE QUESTIONS ("GRILL ME")
    # -------------------------------------------------------------
    {
        "category": "Category 9: Rapid-Fire & Tough Defense Questions ('Grill Me' Section)",
        "questions": [
            {
                "q": "Q42. 'Isn't your project just a wrapper around Google Gemini and Tavily?' (Tough Examiner Question)",
                "a": "No, absolutely not. The LLM (Gemini) is only invoked for reasoning tasks: decomposing the initial topic in Phase 1 and embedding the top 35 candidates in Phase 2. The entire retrieval backbone—tokenization, stop-word elimination, 5-stage Porter stemming, in-memory BM25 inverted indexing, two-stage cascading filters, multi-key deduplication across DOIs and arXiv IDs, and sliding-window PDF passage chunking—is engineered custom in pure Python. Even if we swapped Gemini for an open-source model like Llama 3, the entire retrieval architecture remains 100% operational.",
                "tip": "Be confident: explain that the core algorithmic engineering is in the retrieval and chunking pipeline, not the LLM."
            },
            {
                "q": "Q43. What happens if all three search APIs fail simultaneously due to a network outage?",
                "a": "The system includes an offline demo harness and cached local fixtures (tested in tests/test_phase2_completion.py). In production, if network requests timeout, the connector raises structured exception classes that trigger retry mechanisms; if unresolvable, the system logs the provider error and gracefully synthesizes a report based on whatever cached or partial evidence was successfully retrieved.",
                "tip": "Mention graceful degradation and structured exceptions."
            },
            {
                "q": "Q44. What is the computational complexity of your BM25 scoring algorithm?",
                "a": "Building the inverted index takes O(N * L) time, where N is the number of documents (~500) and L is average document length in tokens (~200). Query scoring takes O(|Q| * D_avg) time, where |Q| is the number of query tokens (typically 4–8) and D_avg is the average posting list length. In practice, this requires fewer than 10,000 simple floating-point operations, executing in ~21 milliseconds.",
                "tip": "State O(N * L) index time and O(|Q| * D_avg) query time."
            },
            {
                "q": "Q45. Why did you choose BM25 over TF-IDF?",
                "a": "TF-IDF has a linear term frequency term: if a word appears 20 times, it gets 20 times the score, making it vulnerable to keyword stuffing. BM25 solves this with term frequency saturation (controlled by parameter k1 = 1.5), meaning that after 3 or 4 occurrences, additional repetitions yield diminishing returns. Furthermore, BM25 incorporates document length normalization (parameter b = 0.75), penalizing long documents that match keywords purely due to verbosity.",
                "tip": "Explain term frequency saturation and document length normalization."
            },
            {
                "q": "Q46. Can you guarantee that ARA will never hallucinate a fact?",
                "a": "No LLM system can offer a 100% theoretical mathematical guarantee against hallucination. However, ARA mitigates hallucination through three architectural constraints: (1) Deterministic character-level quote extraction where findings must be grounded in raw PDF passage text; (2) Sentence-level NLI entailment audits in Phase 3; and (3) Explicit epistemic confidence scoring, which downgrades unverified claims to 'Inconclusive' rather than presenting them as factual.",
                "tip": "Never claim 100% zero hallucination; academic evaluators will reject that. Instead, explain your layered mitigation architecture."
            },
            {
                "q": "Q47. Why didn't you use an established vector database like ChromaDB or Pinecone?",
                "a": "ChromaDB and Pinecone are designed for persistent multi-gigabyte vector corpora across millions of documents. In ARA, each research inquiry dynamically harvests an ad-hoc, ephemeral candidate pool of ~500 papers. Spinning up a separate vector database daemon introduces unnecessary operational overhead, disk dependencies, and network roundtrips. In-memory numpy cosine similarity across 35 vectors takes 0.4 milliseconds with zero infrastructure overhead.",
                "tip": "This demonstrates senior architectural decision-making: choosing the right tool for the specific problem scale."
            },
            {
                "q": "Q48. How do you handle OCR noise and multi-column formatting in downloaded arXiv PDFs?",
                "a": "pypdf extracts text streams across PDF layout text objects. We apply a series of regex sanitization filters: joining hyphenated words broken across line breaks (e.g. 'retrie-val' -> 'retrieval'), stripping repeated academic header/footer strings, and removing non-printable binary font-encoding artifacts before text enters the sliding-window chunker.",
                "tip": "Mention de-hyphenation and header/footer stripping."
            },
            {
                "q": "Q49. How do you assess the quality of an academic paper beyond raw citation counts?",
                "a": "In addition to logarithmic citation authority scaling, ARA evaluates: (1) Publication venue credibility (distinguishing peer-reviewed conference/journal proceedings indexed in OpenAlex from unreviewed preprints); (2) Recency weighting to prioritize contemporary benchmarks; and (3) Empirical density, measuring whether the full-text paper contains quantitative benchmark tables and experimental sections.",
                "tip": "Explain that peer-review status, recency, and quantitative density are combined."
            },
            {
                "q": "Q50. If you had to summarize the entire project in one final sentence for the evaluation committee, what would it be?",
                "a": "'Autonomous Research Report Agent transitions automated scientific synthesis from naive, unverified prompt-chaining to an auditable, two-stage hybrid retrieval framework that plans competing hypotheses, queries heterogeneous scholarly graphs, eliminates attention decay through passage chunking, and guarantees source-grounded research integrity.'",
                "tip": "Deliver this closing sentence with confidence!"
            }
        ]
    }
]

# ---------------------------------------------------------------------------
# REPORTLAB NUMBERED CANVAS (Dynamic "Page X of Y" + Running Header/Footer)
# ---------------------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages):
        if self._pageNumber == 1:
            return  # Suppress running header/footer on title page

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#666666"))

        # Running Header
        header_y = 808
        self.drawString(50, header_y, "Autonomous Research Report Agent (ARA) — Viva & Presentation Question Bank")
        self.drawRightString(545, header_y, "UPES Dehradun | School of Computer Science")
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(50, header_y - 4, 545, header_y - 4)

        # Running Footer
        footer_y = 35
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(50, footer_y + 12, 545, footer_y + 12)
        self.drawString(50, footer_y, "Major Project Mid-Term Defense Question Bank (50 Questions & Model Answers)")
        self.drawRightString(545, footer_y, f"Page {self._pageNumber} of {total_pages}")

        self.restoreState()


# ---------------------------------------------------------------------------
# BUILD PDF QUESTION BANK
# ---------------------------------------------------------------------------
def build_pdf_question_bank(pdf_path):
    print(f"Generating Question Bank PDF: {pdf_path}...")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=52,
        bottomMargin=52
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_inst_style = ParagraphStyle(
        'CoverInst',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor(NAVY_PRIMARY),
        alignment=1
    )
    title_univ_style = ParagraphStyle(
        'CoverUniv',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor(TEXT_MUTED),
        alignment=1
    )
    title_main_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor(NAVY_PRIMARY),
        alignment=1
    )
    title_sub_style = ParagraphStyle(
        'CoverSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor(NAVY_SECONDARY),
        alignment=1
    )
    meta_style = ParagraphStyle(
        'CoverMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor(TEXT_DARK),
        alignment=1
    )

    category_heading_style = ParagraphStyle(
        'CategoryHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor(NAVY_PRIMARY),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    q_text_style = ParagraphStyle(
        'QuestionText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor(NAVY_PRIMARY),
        spaceBefore=1,
        spaceAfter=2
    )
    a_text_style = ParagraphStyle(
        'AnswerText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor(TEXT_DARK),
        alignment=4,  # Justified
        spaceAfter=3
    )
    tip_text_style = ParagraphStyle(
        'TipText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0056B3")
    )
    toc_style = ParagraphStyle(
        'TocText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor(TEXT_DARK)
    )

    story = []

    # -------------------------------------------------------------
    # COVER PAGE
    # -------------------------------------------------------------
    story.append(Spacer(1, 10))
    story.append(Paragraph("SCHOOL OF COMPUTER SCIENCE", title_inst_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("UNIVERSITY OF PETROLEUM & ENERGY STUDIES, DEHRADUN - 248007, UTTARAKHAND", title_univ_style))
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="92%", thickness=1.5, color=colors.HexColor(ACCENT_CYAN), spaceBefore=2, spaceAfter=14))

    story.append(Paragraph("MAJOR PROJECT MID-TERM DEFENSE QUESTION BANK", title_main_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Comprehensive Viva Preparation & Technical Defense Guide (50 Questions & Model Answers)", title_sub_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Project: <i>Autonomous Research Report Agent: An Evidence-Driven Multi-Agent Framework for Automated Research</i>", meta_style))

    story.append(HRFlowable(width="92%", thickness=1.5, color=colors.HexColor(ACCENT_CYAN), spaceBefore=14, spaceAfter=14))

    # Meta Table
    col_w = [115, 80, 115, 125]
    table_data = [
        [
            Paragraph("<b>Specialization / Batch</b>", ParagraphStyle('Hdr', parent=meta_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>SAP ID</b>", ParagraphStyle('Hdr', parent=meta_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Roll No / Reg ID</b>", ParagraphStyle('Hdr', parent=meta_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Name</b>", ParagraphStyle('Hdr', parent=meta_style, fontName='Helvetica-Bold', textColor=colors.white))
        ],
        [Paragraph("AIML, Batch 8", meta_style), Paragraph("500119031", meta_style), Paragraph("R2142230351", meta_style), Paragraph("Devansh Saini", meta_style)],
        [Paragraph("AIML, Batch 8", meta_style), Paragraph("500119592", meta_style), Paragraph("R2142230632", meta_style), Paragraph("Yash Thakur", meta_style)],
        [Paragraph("AIML, Batch 7", meta_style), Paragraph("500121743", meta_style), Paragraph("R2142230345", meta_style), Paragraph("Kanishq Vikram Singh", meta_style)],
        [Paragraph("AIML, Batch 7", meta_style), Paragraph("500119644", meta_style), Paragraph("R2142230187", meta_style), Paragraph("Sumit Kumar", meta_style)],
    ]
    t = Table(table_data, colWidths=col_w)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NAVY_PRIMARY)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F4F7F9"), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
    ]))
    story.append(t)

    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Project Mentor:</b> Dr. Anish Kumar Vishwakarma (Assistant Professor, School of Computer Science)", meta_style))
    story.append(Paragraph("<b>Department of Informatics | Academic Session: 2025–2026</b>", meta_style))

    story.append(Spacer(1, 14))

    # Overview Box
    overview_text = (
        "<b>How to Use This Question Bank:</b><br/>"
        "This question bank is engineered specifically for your Major Project Mid-Term Evaluation and Viva Defense. "
        "It contains <b>50 targeted questions</b> categorized into 9 technical dimensions—from algorithmic mathematical "
        "formulations (BM25, Porter stemmer, dense cosine ranking) to experimental benchmarks, multi-agent schema contracts, "
        "and aggressive examiner defense ('Grill Me' questions). Each entry provides an in-depth <b>Model Answer</b> alongside a "
        "<b>High-Yield Viva Tip</b> for quick 10-second recall under examination pressure."
    )
    overview_card = Table([[Paragraph(overview_text, ParagraphStyle('Ov', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor(NAVY_PRIMARY)))]], colWidths=[490])
    overview_card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(BG_HIGHLIGHT)),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(ACCENT_CYAN)),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(overview_card)

    story.append(PageBreak())

    # -------------------------------------------------------------
    # QUESTION BANK CONTENT (CATEGORIES 1 to 9)
    # -------------------------------------------------------------
    for cat_data in QUESTION_BANK:
        cat_title = cat_data["category"]
        story.append(Paragraph(cat_title, category_heading_style))
        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor(NAVY_PRIMARY), spaceBefore=1, spaceAfter=8))

        for item in cat_data["questions"]:
            q_num_and_title = item["q"]
            answer = item["a"]
            tip = item["tip"]

            card_content = [
                Paragraph(f"<b>{q_num_and_title}</b>", q_text_style),
                Spacer(1, 2),
                Paragraph(f"<b>Model Answer:</b> {answer}", a_text_style),
                Spacer(1, 2),
                Paragraph(f"💡 <b>Viva Tip / Key Recall:</b> {tip}", tip_text_style)
            ]

            card_table = Table([[card_content]], colWidths=[492])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
                ('LINEBEFORE', (0, 0), (0, -1), 2.5, colors.HexColor(NAVY_SECONDARY)),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 7),
                ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ]))

            story.append(KeepTogether([card_table, Spacer(1, 5)]))

    # Build PDF with dynamic NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Question Bank PDF saved successfully to {pdf_path}")


# ---------------------------------------------------------------------------
# BUILD WORD QUESTION BANK (.DOCX)
# ---------------------------------------------------------------------------
def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="{top}" w:type="dxa"/>'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'  <w:left w:w="{left}" w:type="dxa"/>'
        f'  <w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def build_word_question_bank(docx_path):
    print(f"Generating Question Bank Word document: {docx_path}...")
    doc = docx.Document()

    # 1-inch margins
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)
        s.different_first_page_header_footer = True

    # Header & Footer on subsequent pages
    header = doc.sections[0].header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hrun = header.add_run("Autonomous Research Report Agent — Mid-Term Defense Question Bank")
    hrun.font.name = 'Calibri'
    hrun.font.size = Pt(8.5)
    hrun.font.color.rgb = RGBColor(0x77, 0x77, 0x77)

    footer = doc.sections[0].footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    frun = footer.add_run("UPES School of Computer Science | Department of Informatics")
    frun.font.name = 'Calibri'
    frun.font.size = Pt(8.5)
    frun.font.color.rgb = RGBColor(0x77, 0x77, 0x77)

    # -------------------------------------------------------------
    # COVER / HEADER
    # -------------------------------------------------------------
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("SCHOOL OF COMPUTER SCIENCE\nUNIVERSITY OF PETROLEUM & ENERGY STUDIES, DEHRADUN - 248007\n")
    r_inst.font.name = 'Calibri'
    r_inst.font.bold = True
    r_inst.font.size = Pt(13)
    r_inst.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)

    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_line = p_div.add_run("―" * 48)
    r_line.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
    r_line.font.bold = True

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_t1 = p_title.add_run("MAJOR PROJECT MID-TERM DEFENSE QUESTION BANK\n")
    r_t1.font.bold = True
    r_t1.font.size = Pt(15)
    r_t1.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)
    r_t2 = p_title.add_run("Comprehensive Viva & Pipeline Defense Guide (50 Technical Questions & Model Answers)\n")
    r_t2.font.bold = True
    r_t2.font.size = Pt(12)
    r_t2.font.color.rgb = RGBColor(0x13, 0x40, 0x74)
    r_t3 = p_title.add_run("Autonomous Research Report Agent: An Evidence-Driven Multi-Agent Framework for Automated Research")
    r_t3.font.italic = True
    r_t3.font.size = Pt(10.5)
    r_t3.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    p_div2 = doc.add_paragraph()
    p_div2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_line2 = p_div2.add_run("―" * 48)
    r_line2.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
    r_line2.font.bold = True

    # Student Table
    tbl = doc.add_table(rows=5, cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Specialization / Batch", "SAP ID", "Roll No / Reg ID", "Name"]
    widths = [Inches(1.8), Inches(1.3), Inches(1.6), Inches(1.8)]

    for idx, h in enumerate(headers):
        cell = tbl.rows[0].cells[idx]
        cell.text = h
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9.5)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(cell, "0B2545")
        set_cell_margins(cell, 80, 80, 100, 100)

    students = [
        ("AIML, Batch 8", "500119031", "R2142230351", "Devansh Saini"),
        ("AIML, Batch 8", "500119592", "R2142230632", "Yash Thakur"),
        ("AIML, Batch 7", "500121743", "R2142230345", "Kanishq Vikram Singh"),
        ("AIML, Batch 7", "500119644", "R2142230187", "Sumit Kumar"),
    ]

    for r_idx, s in enumerate(students, start=1):
        bg = "F4F7F9" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(s):
            cell = tbl.rows[r_idx].cells[c_idx]
            cell.text = val
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell.paragraphs[0].runs[0].font.size = Pt(9)
            set_cell_background(cell, bg)
            set_cell_margins(cell, 80, 80, 100, 100)

    for row in tbl.rows:
        for idx, w in enumerate(widths):
            row.cells[idx].width = w

    p_mentor = doc.add_paragraph()
    p_mentor.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mentor.paragraph_format.space_before = Pt(14)
    r_m = p_mentor.add_run("Project Mentor: Dr. Anish Kumar Vishwakarma (Assistant Professor, School of Computer Science)\nDepartment of Informatics | Academic Session: 2025–2026")
    r_m.font.size = Pt(9.5)
    r_m.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    doc.add_page_break()

    # -------------------------------------------------------------
    # QUESTIONS & ANSWERS
    # -------------------------------------------------------------
    for cat_data in QUESTION_BANK:
        p_c = doc.add_paragraph()
        p_c.paragraph_format.space_before = Pt(14)
        p_c.paragraph_format.space_after = Pt(4)
        p_c.paragraph_format.keep_with_next = True
        r_c = p_c.add_run(cat_data["category"])
        r_c.font.bold = True
        r_c.font.size = Pt(13)
        r_c.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)

        for q_item in cat_data["questions"]:
            # Outer card as a 1x1 table with left border
            q_tbl = doc.add_table(rows=1, cols=1)
            q_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            q_cell = q_tbl.cell(0, 0)
            set_cell_background(q_cell, "FAFBFC")
            set_cell_margins(q_cell, 100, 100, 140, 140)

            # Left accent border
            tcPr = q_cell._tc.get_or_add_tcPr()
            borders = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>'
                f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>'
                f'  <w:left w:val="single" w:sz="18" w:space="0" w:color="134074"/>'
                f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>'
                f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>'
                f'</w:tcBorders>'
            )
            tcPr.append(borders)

            # Content inside cell
            p_q = q_cell.paragraphs[0]
            p_q.paragraph_format.space_after = Pt(3)
            r_q = p_q.add_run(q_item["q"])
            r_q.font.bold = True
            r_q.font.size = Pt(10)
            r_q.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)

            p_a = q_cell.add_paragraph()
            p_a.paragraph_format.space_after = Pt(3)
            p_a.paragraph_format.line_spacing = 1.15
            p_a.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            r_albl = p_a.add_run("Model Answer: ")
            r_albl.font.bold = True
            r_albl.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
            r_atxt = p_a.add_run(q_item["a"])
            r_atxt.font.size = Pt(9.5)
            r_atxt.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

            p_tip = q_cell.add_paragraph()
            p_tip.paragraph_format.space_after = Pt(0)
            r_tlbl = p_tip.add_run("💡 Viva Tip: ")
            r_tlbl.font.bold = True
            r_tlbl.font.size = Pt(9)
            r_tlbl.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
            r_ttxt = p_tip.add_run(q_item["tip"])
            r_ttxt.font.italic = True
            r_ttxt.font.size = Pt(9)
            r_ttxt.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)

            p_sp = doc.add_paragraph()
            p_sp.paragraph_format.space_after = Pt(4)

    doc.save(docx_path)
    print(f"Question Bank Word document saved successfully to {docx_path}")


# -------------------------------------------------------------
# MAIN DISPATCHER
# -------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)

    pdf_target = os.path.abspath("reports/question_bank_presentation_and_pipeline.pdf")
    docx_target = os.path.abspath("reports/question_bank_presentation_and_pipeline.docx")

    build_pdf_question_bank(pdf_target)
    build_word_question_bank(docx_target)

    # Copy to workspace root for direct access
    root_pdf = os.path.abspath("question_bank_presentation_and_pipeline.pdf")
    root_docx = os.path.abspath("question_bank_presentation_and_pipeline.docx")

    shutil.copyfile(pdf_target, root_pdf)
    shutil.copyfile(docx_target, root_docx)

    print("Question bank generation complete:")
    print(f"  PDF Target:  {pdf_target}")
    print(f"  Word Target: {docx_target}")
    print(f"  Root PDF:    {root_pdf}")
    print(f"  Root Word:   {root_docx}")
