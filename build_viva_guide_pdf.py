import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return  # Suppress headers and footers on the cover page
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#555555"))
        
        # Running Header
        self.drawString(54, 842 - 36, "Autonomous Research Report Agent (ARA) — Viva Defense & Algorithmic Guide")
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(54, 842 - 42, 595 - 54, 842 - 42)
        
        # Running Footer
        self.line(54, 45, 595 - 54, 45)
        self.drawString(54, 32, "UPES School of Computer Science | Department of Informatics")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(595 - 54, 32, page_str)
        self.restoreState()

def build_viva_guide(output_pdf_path):
    print(f"Building Viva Guide PDF at: {output_pdf_path}...")
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#0B2545")
    c_secondary = colors.HexColor("#134074")
    c_accent = colors.HexColor("#1D4E89")
    c_text = colors.HexColor("#1F2937")
    c_muted = colors.HexColor("#4B5563")
    c_border = colors.HexColor("#D0D7DE")
    c_bg_light = colors.HexColor("#F8FAFC")
    c_code_bg = colors.HexColor("#F1F5F9")
    c_callout_bg = colors.HexColor("#EFF6FF")
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        alignment=1, # Center
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        alignment=1,
        spaceAfter=25
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )
    h3_style = ParagraphStyle(
        'Heading3_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=c_accent,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_text,
        spaceAfter=6
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.2,
        leading=13,
        textColor=c_text,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )
    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#0F172A")
    )
    tbl_header_style = ParagraphStyle(
        'TblHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1
    )
    tbl_cell_style = ParagraphStyle(
        'TblCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=c_text
    )
    tbl_cell_bold = ParagraphStyle(
        'TblCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=c_primary
    )
    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#1E3A8A")
    )
    
    def make_callout(text):
        p = Paragraph(f"<b>Key Defense Takeaway:</b> {text}", callout_style)
        t = Table([[p]], colWidths=[485])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_callout_bg),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#93C5FD")),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        return t

    def make_code_box(code_text):
        p = Paragraph(code_text.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style)
        t = Table([[p]], colWidths=[485])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
            ('BOX', (0,0), (-1,-1), 0.5, c_border),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    story = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 20))
    p_inst = Paragraph("UPES SCHOOL OF COMPUTER SCIENCE<br/>DEPARTMENT OF INFORMATICS", ParagraphStyle(
        'CoverInst', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, leading=17, alignment=1, textColor=c_primary
    ))
    story.append(p_inst)
    story.append(Spacer(1, 25))
    
    story.append(Paragraph("Autonomous Research Report Agent (ARA)", title_style))
    story.append(Paragraph("<b>Project Overview, Algorithmic Foundations & Viva Defense Manual</b><br/><i>Comprehensive Preparation Guide for Mid-Term Evaluation & Beyond</i>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=c_secondary, spaceBefore=5, spaceAfter=20))
    
    # Team Table on Cover
    team_data = [
        [Paragraph("<b>Student Name</b>", tbl_header_style), Paragraph("<b>Enrollment No.</b>", tbl_header_style), Paragraph("<b>SAP ID</b>", tbl_header_style), Paragraph("<b>Specialization & Batch</b>", tbl_header_style)],
        [Paragraph("<b>Devansh Saini</b>", tbl_cell_style), Paragraph("R2142230351", tbl_cell_style), Paragraph("500119031", tbl_cell_style), Paragraph("B.Tech CSE (AIML), Batch 8", tbl_cell_style)],
        [Paragraph("<b>Yash Thakur</b>", tbl_cell_style), Paragraph("R2142230632", tbl_cell_style), Paragraph("500119592", tbl_cell_style), Paragraph("B.Tech CSE (AIML), Batch 8", tbl_cell_style)],
        [Paragraph("<b>Kanishq Vikram Singh</b>", tbl_cell_style), Paragraph("R2142230345", tbl_cell_style), Paragraph("500121743", tbl_cell_style), Paragraph("B.Tech CSE (AIML), Batch 7", tbl_cell_style)],
        [Paragraph("<b>Sumit Kumar</b>", tbl_cell_style), Paragraph("R2142230187", tbl_cell_style), Paragraph("500119644", tbl_cell_style), Paragraph("B.Tech CSE (AIML), Batch 7", tbl_cell_style)],
    ]
    t_team = Table(team_data, colWidths=[130, 95, 95, 165])
    t_team.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_team)
    story.append(Spacer(1, 25))
    
    meta_p = Paragraph(
        "<b>Project Focus:</b> Multi-Agent Automated Scientific Inquiry & Information Retrieval<br/>"
        "<b>Repository Branch:</b> <code>main</code> (176 Passing Automated Tests with CI/CD)<br/>"
        "<b>Deliverables Included:</b> Mid-Term Report (.pdf), Slide Deck (.pptx), Interactive CLI, Live Demo Harness",
        ParagraphStyle('MetaInfo', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=14, alignment=1, textColor=c_muted)
    )
    story.append(meta_p)
    story.append(PageBreak())

    # =========================================================================
    # SECTION 1: EXECUTIVE PROJECT OVERVIEW
    # =========================================================================
    story.append(Paragraph("1. Executive Project Overview", h1_style))
    story.append(Paragraph(
        "The <b>Autonomous Research Report Agent (ARA)</b> is an evidence-grounded, multi-agent AI system designed to automate comprehensive academic literature reviews, technical due diligence, and scientific inquiry. Conventional language models suffer from severe operational failure modes when tasked with complex research: citation hallucination, confirmation bias (retrieving only confirmatory snippets), middle-context attention degradation (<i>'Lost in the Middle'</i>), and API rate-limiting bottlenecks.",
        body_style
    ))
    story.append(Paragraph(
        "ARA resolves these limitations through a disciplined four-phase pipeline where specialized autonomous agents collaborate under formal machine-readable JSON schema contracts:",
        body_style
    ))
    
    # 4 Phases High-Level Table
    phase_summary_data = [
        [Paragraph("<b>Phase</b>", tbl_header_style), Paragraph("<b>Agent Role</b>", tbl_header_style), Paragraph("<b>Key Responsibilities</b>", tbl_header_style), Paragraph("<b>Emitted Contract</b>", tbl_header_style)],
        [Paragraph("<b>Phase 1</b>", tbl_cell_bold), Paragraph("Research Planner", tbl_cell_style), Paragraph("Domain detection, sub-question formulation, hypothesis generation, and falsification criteria.", tbl_cell_style), Paragraph("<code>data/research_plan.json</code>", tbl_cell_style)],
        [Paragraph("<b>Phase 2</b>", tbl_cell_bold), Paragraph("Discovery & IR Engine", tbl_cell_style), Paragraph("Tri-provider retrieval (Tavily, OpenAlex, Semantic Scholar), multi-key deduplication, BM25 indexing, dense vector search, and sliding-window PDF passage chunking.", tbl_cell_style), Paragraph("<code>data/research_evidence.json</code>", tbl_cell_style)],
        [Paragraph("<b>Phase 3</b>", tbl_cell_bold), Paragraph("Evidence Validator & Critic", tbl_cell_style), Paragraph("Sentence-level NLI audits, character-level quote provenance against raw PDF text, contradiction mapping, and iterative sufficiency re-search triggers.", tbl_cell_style), Paragraph("<code>data/validated_evidence.json</code><br/><i>(Planned for Part 2)</i>", tbl_cell_style)],
        [Paragraph("<b>Phase 4</b>", tbl_cell_bold), Paragraph("Calibrated Synthesizer", tbl_cell_style), Paragraph("Epistemic confidence calibration (0.0 to 1.0), deterministic numerical citation links [1], [2], and multi-format report publishing (HTML, Markdown, PDF).", tbl_cell_style), Paragraph("<code>data/research_report.html</code><br/><i>(Planned for Part 2)</i>", tbl_cell_style)],
    ]
    t_phase = Table(phase_summary_data, colWidths=[60, 95, 205, 125])
    t_phase.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_secondary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_phase)
    story.append(Spacer(1, 10))
    story.append(make_callout(
        "For Mid-Term evaluation, <b>Phases 1 and 2 are fully engineered, tested, and demonstrated</b> with 176 unit tests. Phases 3 and 4 represent our planned development milestone for Major Project Part 2 (End-Term)."
    ))
    story.append(Spacer(1, 12))

    # =========================================================================
    # SECTION 2: WHAT IS IMPLEMENTED VS. WHAT IS PLANNED (ROADMAP)
    # =========================================================================
    story.append(Paragraph("2. Scope Delineation: Mid-Term vs. End-Term", h1_style))
    story.append(Paragraph(
        "Examiners frequently ask: <i>'Where does your completed work end and your future work begin?'</i> The table below defines the clear architectural boundary:",
        body_style
    ))

    scope_data = [
        [Paragraph("<b>Component / Dimension</b>", tbl_header_style), Paragraph("<b>Completed in Mid-Term (Part 1)</b>", tbl_header_style), Paragraph("<b>Planned for End-Term (Part 2)</b>", tbl_header_style)],
        [
            Paragraph("<b>Phase 1: Planning</b>", tbl_cell_bold),
            Paragraph("• Domain classification (Biomedical, Technical, Legal)<br/>• Sub-question decomposition (Mechanism, Debate)<br/>• Working & competing hypothesis generation<br/>• Automated schema validation in <code>planner/</code>", tbl_cell_style),
            Paragraph("• User-in-the-loop interactive plan editing via CLI<br/>• Dynamic ontology expansion for niche domains", tbl_cell_style)
        ],
        [
            Paragraph("<b>Phase 2: Discovery & IR</b>", tbl_cell_bold),
            Paragraph("• Tri-provider search (Tavily, OpenAlex, Semantic Scholar)<br/>• Hierarchical deduplication (DOI, arXiv ID, URL, Title)<br/>• 6-Step IR Engine (Porter stemmer + BM25 inverted index)<br/>• Two-Stage Cascade (500 -> 35 -> Top 10)<br/>• 350-word sliding-window PDF passage chunking", tbl_cell_style),
            Paragraph("• Local PDF vector caching on disk (FAISS/Chroma integration)<br/>• Cross-lingual academic discovery support", tbl_cell_style)
        ],
        [
            Paragraph("<b>Phase 3: Validation</b>", tbl_cell_bold),
            Paragraph("• Character-level quote verification baseline in <code>verifier/claim_verifier.py</code><br/>• Initial plan critique checks in <code>critique/plan_critic.py</code>", tbl_cell_style),
            Paragraph("• Sentence-level Natural Language Inference (NLI)<br/>• Cross-study contradiction detection matrix<br/>• Sufficiency scorecard & automated iterative re-search loops", tbl_cell_style)
        ],
        [
            Paragraph("<b>Phase 4: Synthesis & Output</b>", tbl_cell_bold),
            Paragraph("• Interactive CLI with live spinners & Rich tables<br/>• Standalone pipeline demo (<code>demo_semantic_pipeline.py</code>)<br/>• Initial HTML report template with citation anchors", tbl_cell_style),
            Paragraph("• Calibrated Epistemic Confidence scoring (0.0 to 1.0)<br/>• Headless PDF publication via WeasyPrint<br/>• Direct BibTeX and Zotero export integration", tbl_cell_style)
        ],
        [
            Paragraph("<b>Engineering & QA</b>", tbl_cell_bold),
            Paragraph("• 176 automated pytest suites passing in ~10.5s<br/>• Continuous Integration via <code>.github/workflows/tests.yml</code>", tbl_cell_style),
            Paragraph("• End-to-end benchmark against standard RAG baselines on public academic benchmarks (HotpotQA, BioASQ)", tbl_cell_style)
        ],
    ]
    t_scope = Table(scope_data, colWidths=[110, 185, 190])
    t_scope.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_secondary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_scope)
    story.append(PageBreak())

    # =========================================================================
    # SECTION 3: MATHEMATICAL & ALGORITHMIC DEEP-DIVE
    # =========================================================================
    story.append(Paragraph("3. Algorithmic Deep-Dive (Algorithms Implemented in Report)", h1_style))
    story.append(Paragraph(
        "This section details every algorithmic routine documented in Section 4 of the Mid-Term Evaluation Report. Expect exact questions on these mathematical formulations.",
        body_style
    ))
    
    # Algorithm 1: BM25
    story.append(Paragraph("3.1 Robertson–Spärck Jones BM25 Probabilistic Relevance Ranking", h2_style))
    story.append(Paragraph(
        "<b>Source Module:</b> <code>search_agent/semantic_indexer.py</code> | <b>Benchmark Execution:</b> 0.021s on local CPU for 500 candidates.<br/>"
        "BM25 is a non-linear term-matching ranking function that models the probability of relevance of candidate document <i>D</i> against user sub-question query <i>Q</i>. Unlike naive TF-IDF, BM25 prevents term frequency saturation and penalizes unnaturally long documents.",
        body_style
    ))
    story.append(make_code_box(
        "BM25 Formula:\n"
        "Score(D, Q) = SUM_{i=1..n} [ IDF(q_i) * ( f(q_i, D) * (k_1 + 1) ) / ( f(q_i, D) + k_1 * ( 1 - b + b * (|D| / avgdl) ) ) ]\n\n"
        "Inverse Document Frequency (IDF):\n"
        "IDF(q_i) = ln( ( N - n(q_i) + 0.5 ) / ( n(q_i) + 0.5 ) + 1 )"
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Core Parameters & System Values:</b><br/>"
        "• <b>k₁ = 1.5:</b> Term frequency saturation parameter. It controls how quickly the score asymptotes as term frequency <i>f(q_i, D)</i> increases. A higher <i>k₁</i> rewards repeated keywords; 1.5 prevents keyword stuffing from dominating.<br/>"
        "• <b>b = 0.75:</b> Document length normalization factor. If <i>b = 1</i>, full document length scaling is enforced; if <i>b = 0</i>, length is ignored. At 0.75, documents longer than <i>avgdl</i> are penalized unless they contain multiple distinct query terms.<br/>"
        "• <b>N:</b> Total number of candidate documents in the current retrieval pool (typically ~500).<br/>"
        "• <b>n(q_i):</b> Count of candidates containing stemmed token <i>q_i</i>.",
        bullet_style
    ))
    story.append(Spacer(1, 8))

    # Algorithm 2: Porter Stemmer
    story.append(Paragraph("3.2 Pure-Python Porter Stemming Algorithm (Porter, 1980)", h2_style))
    story.append(Paragraph(
        "<b>Source Module:</b> <code>search_agent/semantic_indexer.py</code> | <b>Standard:</b> Porter (1980) 5-Stage Suffix Stripping.<br/>"
        "To enable BM25 to match morphological variants across academic literature (e.g., <i>'retrieval'</i>, <i>'retrieved'</i>, <i>'retrieving'</i> → <b>'retriev'</b>), a pure-Python Porter stemmer was engineered from first principles. It sequentially executes:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Step 1a–1c:</b> Plural and past-participle stripping (<i>-sses → -ss, -ies → -i, -ing/-ed removal</i>).<br/>"
        "• <b>Step 2:</b> Double suffix reduction (<i>-ational → -ate, -ization → -ize, -fulness → -ful</i>).<br/>"
        "• <b>Step 3:</b> Complex suffix conversion (<i>-iciti → -ic, -ical → -ic, -ative → [null]</i>).<br/>"
        "• <b>Step 4:</b> Derivational suffix removal based on syllable measure <i>m > 1</i> (<i>-ance, -ence, -able, -ible, -ment</i>).<br/>"
        "• <b>Step 5a–5b:</b> Terminal <i>-e</i> and double-consonant cleanup (<i>-ll cleanup if m > 1</i>).",
        bullet_style
    ))
    story.append(make_callout(
        "<b>Crucial Viva Point:</b> Explain that writing this in pure Python guarantees <b>100% portability</b> across any operating system without requiring compiled C extensions, NLTK wheels, or spaCy runtime downloads."
    ))
    story.append(Spacer(1, 8))

    # Algorithm 3: Two-Stage Cascade
    story.append(Paragraph("3.3 Two-Stage Cascade Candidate Filtering (Coarse-to-Fine Search)", h2_style))
    story.append(Paragraph(
        "<b>Problem Solved:</b> Generating dense vector embeddings for 500+ candidates hits LLM embedding rate limits (HTTP 429) and induces 4-6 second latency spikes per query.<br/>"
        "<b>Mechanism:</b> ARA implements a two-stage cascade architecture:",
        body_style
    ))
    story.append(make_code_box(
        "Stage 1 (Coarse Filter - Local CPU, 21ms):\n"
        "  500 Gross Candidates ──[BM25 Scoring + Porter Stemming]──► Top 35 Candidates\n\n"
        "Stage 2 (Dense Re-Ranking - Gemini text-embedding-004 API):\n"
        "  Top 35 Candidates ──[Compute 768-dim Vector Embeddings]──► Cosine Similarity\n\n"
        "Hybrid Fusion Formula:\n"
        "  FinalScore(D) = alpha * Score_BM25_norm(D) + (1 - alpha) * CosineSim(v_Q, v_D)\n"
        "  where alpha = 0.35 (Lexical Weight), 1 - alpha = 0.65 (Semantic Dense Weight)"
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Empirical Result:</b> Reduces dense vector API requests by <b>93.0%</b> (from 500 API calls down to 35), completely eliminating rate limits while retaining 100% recall of relevant academic papers.",
        body_style
    ))
    story.append(PageBreak())

    # Algorithm 4: PDF Passage Chunking
    story.append(Paragraph("3.4 Sliding-Window PDF Passage Chunking", h2_style))
    story.append(Paragraph(
        "<b>Source Modules:</b> <code>search_agent/content_retriever.py</code> and <code>search_agent/semantic_indexer.py</code>.<br/>"
        "<b>Theoretical Justification:</b> <i>Liu et al. (2024)</i> demonstrated in their foundational paper <b>'Lost in the Middle: How Language Models Use Long Contexts'</b> that LLMs exhibit a U-shaped retrieval curve: information placed in the middle 40%–60% of an input prompt suffers high retrieval error rates.<br/>"
        "To prevent context dilution from 15-page arXiv PDFs, ARA applies sliding-window empirical chunking:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Window Size (W = 350 words):</b> Approximately 450 tokens, matching the typical length of a scientific methodology paragraph or experimental results section.<br/>"
        "• <b>Step Size (S = 300 words) & Overlap (O = 50 words):</b> A 50-word overlap guarantees that critical quantitative findings (e.g., benchmark tables, confidence intervals) spanning sentence boundaries are not truncated.<br/>"
        "• <b>Passage Selection Algorithm:</b> Each extracted passage is scored against the sub-question prompt using local BM25 density. Only the <b>top 5 high-density empirical paragraphs</b> are returned for evidence synthesis.",
        bullet_style
    ))
    story.append(Spacer(1, 8))

    # Algorithm 5: Multi-Key Deduplication
    story.append(Paragraph("3.5 Multi-Key Hierarchical Deduplication Algorithm", h2_style))
    story.append(Paragraph(
        "<b>Source Module:</b> <code>search_agent/sources.py</code> | <b>Benchmark:</b> 92.2% retention efficiency.<br/>"
        "Because academic literature appears concurrently across open-access repositories (arXiv), indexers (Semantic Scholar, OpenAlex), and commercial publishers under conflicting URLs, ARA executes a hierarchical resolution cascade:",
        body_style
    ))
    story.append(make_code_box(
        "Resolution Priority:\n"
        "  1. Canonical DOI: Match normalized DOI string (e.g., '10.1145/3586183.3606763')\n"
        "  2. Canonical arXiv ID: Strip version suffixes ('arXiv:2305.14283v2' -> '2305.14283')\n"
        "  3. Canonical URL: Normalize scheme (https), strip trailing slash & UTM tracking params\n"
        "  4. Fuzzy Title Matching: Levenshtein / Token-sort similarity >= 0.88 with author check"
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "During live benchmark execution on 539 harvested candidates, the deduplication engine successfully merged 42 duplicate records, retaining 497 unique academic sources without data loss.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Algorithm 6: Authority Dampening
    story.append(Paragraph("3.6 Logarithmic Citation Authority Dampening", h2_style))
    story.append(Paragraph(
        "<b>Formula:</b> <code>AuthorityScore(D) = log10(1 + citations_D) / log10(1 + citations_max)</code><br/>"
        "In naive ranking systems, seminal papers from 2017 with 40,000+ citations receive overwhelming authority scores, starving recent 2025/2026 preprints with 3-10 citations of visibility. Logarithmic scaling compresses the authority dynamic range, allowing high-relevance contemporary preprints to compete fairly against legacy foundations.",
        body_style
    ))
    story.append(Spacer(1, 12))

    # =========================================================================
    # SECTION 4: TEAM VIVA STRATEGY & DIVISION OF RESPONSIBILITY
    # =========================================================================
    story.append(Paragraph("4. Team Viva Strategy & Division of Responsibility", h1_style))
    story.append(Paragraph(
        "To deliver a cohesive, confident presentation, each team member should own a specific pillar of the pipeline during the viva defense:",
        body_style
    ))

    team_role_data = [
        [Paragraph("<b>Team Member</b>", tbl_header_style), Paragraph("<b>Assigned Viva Pillar</b>", tbl_header_style), Paragraph("<b>Key Concepts & Modules to Own</b>", tbl_header_style)],
        [
            Paragraph("<b>Devansh Saini</b>", tbl_cell_bold),
            Paragraph("Phase 1: Planning & Theoretical Problem Statement", tbl_cell_style),
            Paragraph("• Problem formulation & RAG vulnerabilities (Hallucination, Lost in the Middle)<br/>• Domain detection heuristic & question decomposition<br/>• Working & competing hypotheses + falsification criteria<br/>• Codebase: <code>planner/planner.py</code>, <code>planner/validation/</code>", tbl_cell_style)
        ],
        [
            Paragraph("<b>Yash Thakur</b>", tbl_cell_bold),
            Paragraph("Phase 2: 6-Step IR Engine & BM25 Mathematics", tbl_cell_style),
            Paragraph("• Robertson–Spärck Jones BM25 mathematical formulation (k1, b, IDF)<br/>• Pure-Python Porter stemmer (5 stages, zero external dependencies)<br/>• Inverted index construction & local CPU term scoring<br/>• Codebase: <code>search_agent/semantic_indexer.py</code>", tbl_cell_style)
        ],
        [
            Paragraph("<b>Kanishq Vikram Singh</b>", tbl_cell_bold),
            Paragraph("Two-Stage Filtering & PDF Passage Chunking", tbl_cell_style),
            Paragraph("• Two-stage cascade rationale (500 -> 35 -> Top 10, >90% API reduction)<br/>• Sliding-window chunking (350w window, 50w overlap, pypdf parser)<br/>• 'Lost in the Middle' mitigation benchmark (Liu et al., 2024)<br/>• Codebase: <code>search_agent/content_retriever.py</code>, <code>search_agent/source_ranker.py</code>", tbl_cell_style)
        ],
        [
            Paragraph("<b>Sumit Kumar</b>", tbl_cell_bold),
            Paragraph("Discovery, Multi-Key Deduplication & Test Suite", tbl_cell_style),
            Paragraph("• Tri-provider harvest (Tavily, OpenAlex, Semantic Scholar)<br/>• Multi-key deduplication cascade (DOI, arXiv ID, URL, Fuzzy Title)<br/>• 176 automated pytest tests & GitHub Actions CI/CD pipeline<br/>• Codebase: <code>search_agent/sources.py</code>, <code>search_agent/source_providers.py</code>, <code>.github/</code>", tbl_cell_style)
        ],
    ]
    t_team_roles = Table(team_role_data, colWidths=[105, 125, 255])
    t_team_roles.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_team_roles)
    story.append(PageBreak())

    # =========================================================================
    # SECTION 5: TOP 10 VIVA DEFENSE QUESTIONS & BULLETPROOF ANSWERS
    # =========================================================================
    story.append(Paragraph("5. Top 10 Viva Defense Questions & Master Answers", h1_style))
    story.append(Paragraph(
        "These ten questions represent the most likely lines of inquiry from the examination committee. Rehearse these answers verbatim with your teammates:",
        body_style
    ))

    qa_list = [
        (
            "Q1: Why did you build a custom BM25 and Porter stemmer instead of importing NLTK, Whoosh, or LangChain?",
            "Heavy NLP libraries like NLTK or LangChain introduce bloated dependency trees, opaque prompt wrappers, and platform-specific compiled C extensions. Implementing BM25 and the 5-stage Porter stemmer in pure Python guarantees that ARA runs in 21ms on any local CPU with zero native binary requirements. It gives us full transparency, allows dynamic term weighting adjustments, and is validated by our own automated unit tests."
        ),
        (
            "Q2: Modern LLMs (like Gemini 1.5 or Claude 3.5) support 1M+ token context windows. Why bother with 350-word passage chunking?",
            "While long context windows exist, empirical research by Liu et al. (2024, 'Lost in the Middle') proved that retrieval accuracy degrades severely when facts are positioned within the middle 40%–60% of an input prompt. Stuffing 15-page PDFs also causes context dilution, high financial cost, and severe latency. Sliding-window chunking isolates the top 5 high-density empirical paragraphs, giving higher factual precision at a fraction of the token cost."
        ),
        (
            "Q3: What specific empirical advantage does your Two-Stage Cascade give over standard dense vector retrieval?",
            "In naive vector RAG, embedding 500 candidate documents requires 500 individual API calls, inducing high latency and immediately triggering HTTP 429 rate limits on production endpoints. Our two-stage cascade executes Stage 1 BM25 coarse filtering on local CPU in 0.021s, narrowing 500 candidates down to 35. Vector embeddings are generated solely for those 35, reducing API consumption by 93.0%."
        ),
        (
            "Q4: How does your system prevent confirmation bias during retrieval?",
            "Conventional search agents query engines using leading user prompts, returning only confirmatory snippets. In Phase 1, ARA explicitly formulates both working hypotheses and competing hypotheses with defined falsification criteria. In Phase 2, the query formulation engine generates dedicated counter-evidence queries specifically searching for dissenting empirical results."
        ),
        (
            "Q5: How do you handle cases where two papers report completely contradictory findings?",
            "In Phase 1, competing hypotheses are established to accommodate contradictory viewpoints. In Phase 2, evidence cards are tagged with empirical methodology tiers (Randomized Trial vs. Observational vs. Synthetic). In Phase 3 (End-Term roadmap), our contradiction detection matrix cross-references opposing effect sizes and highlights epistemic uncertainty in the final report rather than artificially smoothing over disagreements."
        ),
        (
            "Q6: Why did you choose OpenAlex and Semantic Scholar alongside Tavily instead of just using Google/Bing search?",
            "Commercial web search APIs index blog posts, marketing landing pages, and secondary commentary, often lacking peer-reviewed authority. OpenAlex and Semantic Scholar provide direct access to structured scholarly metadata: DOIs, publication years, citation graphs, open-access PDF URLs, and formal abstracts. Interleaving web discovery with academic graphs ensures both timeliness and peer-reviewed rigor."
        ),
        (
            "Q7: How do you guarantee that citations in your final report are not hallucinated?",
            "In conventional RAG, citation assignment is left to the LLM's non-deterministic completion, frequently resulting in fabricated links. In ARA, every cited passage is extracted as a structured evidence card containing an audited character-level substring from raw source text. Numbered citations [1], [2] are assigned deterministically to canonical DOI/arXiv links."
        ),
        (
            "Q8: What is the purpose of the Logarithmic Citation Authority Dampening function?",
            "If raw citation count is used in ranking, foundational papers with 50,000 citations (e.g., Vaswani et al., 2017) completely dominate the retrieval pool, starving relevant, cutting-edge 2025/2026 preprints of visibility. Logarithmic scaling (log10(1 + citations)) compresses the dynamic range, allowing recent breakthroughs with 5 citations to compete fairly."
        ),
        (
            "Q9: How do you verify that your software works without relying on live API calls during viva?",
            "ARA includes a deterministic offline demonstration harness (python main.py --demo) and a standalone semantic pipeline visualizer (python demo_semantic_pipeline.py). Furthermore, our repository contains 176 automated pytest tests that pass in ~10.5 seconds, integrated with GitHub Actions CI/CD to provide verifiable proof of code health."
        ),
        (
            "Q10: What is your primary milestone for Major Project Part 2 (End-Term)?",
            "Our primary Part 2 milestone is the complete realization of Phase 3 (Sentence-Level Natural Language Inference for claim auditing, contradiction detection, and autonomous sufficiency re-search loops) and Phase 4 (Calibrated Epistemic Confidence scoring from 0.0 to 1.0 and headless publication-grade PDF compilation via WeasyPrint)."
        ),
    ]

    for q, a in qa_list:
        story.append(Paragraph(f"<b>{q}</b>", h3_style))
        story.append(Paragraph(f"<i>Answer:</i> {a}", body_style))
        story.append(Spacer(1, 4))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print("PDF build complete!")

if __name__ == "__main__":
    out_dir = os.path.join("Presentation_Documents")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "ARA_Team_Viva_and_Algorithms_Guide.pdf")
    build_viva_guide(out_path)
