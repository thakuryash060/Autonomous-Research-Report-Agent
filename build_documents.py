"""
Builds both Microsoft Word (.docx) and PDF (.pdf) documents for the
UPES Major Project Mid-Term Evaluation Report:
"Autonomous Research Report Agent: An Evidence-Driven Multi-Agent Framework for Automated Research"
"""

import os
import shutil
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted, HRFlowable
)
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# COLOR PALETTE
# ---------------------------------------------------------------------------
NAVY_PRIMARY = "#0B2545"      # 11, 37, 69
NAVY_SECONDARY = "#134074"    # 19, 64, 116
ACCENT_BLUE = "#1D4E89"       # 29, 78, 137
TEXT_DARK = "#222222"         # Body text
TEXT_MUTED = "#555555"        # Subtitles, headers
BG_LIGHT = "#F4F7F9"          # Light table alt row / callout
BORDER_COLOR = "#D0D7DE"      # Clean border
ACCENT_BAR = "#0056B3"

# -------------------------------------------------------------
# SHARED ARTIFACT DATA
# -------------------------------------------------------------
STUDENTS_DATA = [
    ("AIML, Batch 8", "500119031", "R2142230351", "Devansh Saini"),
    ("AIML, Batch 8", "500119592", "R2142230632", "Yash Thakur"),
    ("AIML, Batch 7", "500121743", "R2142230345", "Kanishq Vikram Singh"),
    ("AIML, Batch 7", "500119644", "R2142230187", "Sumit Kumar"),
]

ARCH_DIAGRAM_TEXT = (
    "[User Research Question / Topic]\n"
    "             │\n"
    "             ▼\n"
    "┌─────────────────────────────────────────────────────────────┐\n"
    "│ PHASE 1: RESEARCH PLANNER (Completed & Implemented)         │\n"
    "│ • Domain detection (Technical, Medical, Legal, General)     │\n"
    "│ • Multi-angle sub-question formulation (Mechanism, Debate)  │\n"
    "│ • Working & Competing Hypotheses + Falsification Criteria   │\n"
    "│ ➔ Emits: data/research_plan.json (Formal System Contract)   │\n"
    "└──────────────────────────────┬──────────────────────────────┘\n"
    "                               │\n"
    "                               ▼\n"
    "┌─────────────────────────────────────────────────────────────┐\n"
    "│ PHASE 2: DISCOVERY, INDEXING & CHUNKING (Completed)         │\n"
    "│ • Tri-Source Harvest: Tavily (Web), OpenAlex, S2            │\n"
    "│ • Multi-Key Deduplication: DOI, arXiv ID, URL, Fuzzy Title  │\n"
    "│ • 6-Step IR Engine: Stop-words, Porter Stemmer, BM25 Index  │\n"
    "│ • Two-Stage Filtering: BM25 (500 -> 35) -> Vectors (Top 10) │\n"
    "│ • Sliding-Window PDF Chunking (350 words, 50-word overlap)  │\n"
    "│ ➔ Emits: data/research_evidence.json                        │\n"
    "└──────────────────────────────┬──────────────────────────────┘\n"
    "                               │\n"
    "               - - - - - - - - - - - - - - - - - (Planned Boundary)\n"
    "                               │\n"
    "                               ▼\n"
    "┌─────────────────────────────────────────────────────────────┐\n"
    "│ PHASE 3: EVIDENCE VALIDATOR & REASONER (Planned: Part 2)    │\n"
    "│ • Sentence-Level NLI Verification against Raw PDF Text      │\n"
    "│ • Empirical Contradiction Detection & Conflict Resolution   │\n"
    "│ • Evidence Sufficiency Scorecard (Quantitative & Counter)   │\n"
    "│ • Autonomous Iterative Re-Search Trigger                    │\n"
    "│ ➔ Expected Deliverable: data/validated_evidence.json        │\n"
    "└──────────────────────────────┬──────────────────────────────┘\n"
    "                               │\n"
    "                               ▼\n"
    "┌─────────────────────────────────────────────────────────────┐\n"
    "│ PHASE 4: REPORT GENERATOR & SYNTHESIS (Planned: Part 2)     │\n"
    "│ • Epistemic Confidence Calibration (0.0 to 1.0)             │\n"
    "│ • Deterministic Citation Assignment [1], [2] with Anchors   │\n"
    "│ • Headless Native PDF Compilation via WeasyPrint            │\n"
    "│ ➔ Expected Deliverable: data/research_report.pdf / .html    │\n"
    "└─────────────────────────────────────────────────────────────┘"
)

# ---------------------------------------------------------------------------
# PART 1: BUILD WORD (.DOCX) DOCUMENT
# ---------------------------------------------------------------------------

def set_cell_background(cell, fill_hex):
    """Sets background fill color of a docx table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
    """Sets cell padding in dxa (1 pt = 20 dxa)."""
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

def set_table_borders(table, color="D0D7DE", sz="4", val="single"):
    """Sets elegant subtle borders on all cells in a docx table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def build_word_document(docx_path):
    print(f"Generating Word document: {docx_path}...")
    doc = docx.Document()

    # Page Margins - 1 inch
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True

    # Setup styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(4)

    # Header and Footer (Subsequent pages)
    subsequent_section = doc.sections[0]
    subsequent_header = subsequent_section.header
    header_p = subsequent_header.paragraphs[0]
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hrun = header_p.add_run("Autonomous Research Report Agent — Mid-Term Evaluation Report")
    hrun.font.name = 'Calibri'
    hrun.font.size = Pt(8.5)
    hrun.font.color.rgb = RGBColor(0x77, 0x77, 0x77)

    subsequent_footer = subsequent_section.footer
    footer_p = subsequent_footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    frun = footer_p.add_run("UPES School of Computer Science | Department of Informatics")
    frun.font.name = 'Calibri'
    frun.font.size = Pt(8.5)
    frun.font.color.rgb = RGBColor(0x77, 0x77, 0x77)

    # -------------------------------------------------------------
    # COVER PAGE
    # -------------------------------------------------------------
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_after = Pt(2)
    p_inst.paragraph_format.space_before = Pt(12)
    r = p_inst.add_run("SCHOOL OF COMPUTER SCIENCE\n")
    r.font.name = 'Calibri'
    r.font.size = Pt(15)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)

    r_univ = p_inst.add_run("UNIVERSITY OF PETROLEUM & ENERGY STUDIES, DEHRADUN - 248007, UTTARAKHAND")
    r_univ.font.name = 'Calibri'
    r_univ.font.size = Pt(11)
    r_univ.font.bold = True
    r_univ.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Divider bar
    p_div1 = doc.add_paragraph()
    p_div1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div1.paragraph_format.space_after = Pt(28)
    p_div1.paragraph_format.space_before = Pt(8)
    r_line = p_div1.add_run("―" * 48)
    r_line.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
    r_line.font.bold = True

    # Report Title
    p_rep = doc.add_paragraph()
    p_rep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_rep.paragraph_format.space_after = Pt(6)
    r_rep = p_rep.add_run("MAJOR PROJECT MID-TERM EVALUATION REPORT")
    r_rep.font.name = 'Calibri'
    r_rep.font.size = Pt(16)
    r_rep.font.bold = True
    r_rep.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)

    p_on = doc.add_paragraph()
    p_on.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_on.paragraph_format.space_after = Pt(6)
    r_on = p_on.add_run("On")
    r_on.font.name = 'Calibri'
    r_on.font.size = Pt(12)
    r_on.font.italic = True
    r_on.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    p_proj = doc.add_paragraph()
    p_proj.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_proj.paragraph_format.space_after = Pt(24)
    r_proj = p_proj.add_run("Autonomous Research Report Agent:\nAn Evidence-Driven Multi-Agent Framework for Automated Research")
    r_proj.font.name = 'Calibri'
    r_proj.font.size = Pt(14)
    r_proj.font.bold = True
    r_proj.font.color.rgb = RGBColor(0x13, 0x40, 0x74)

    # Divider bar
    p_div2 = doc.add_paragraph()
    p_div2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div2.paragraph_format.space_after = Pt(20)
    r_line2 = p_div2.add_run("―" * 48)
    r_line2.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
    r_line2.font.bold = True

    # Submitted By Header
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(8)
    r_sub = p_sub.add_run("Submitted By:")
    r_sub.font.name = 'Calibri'
    r_sub.font.size = Pt(12)
    r_sub.font.bold = True
    r_sub.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)

    # Student Table
    student_table = doc.add_table(rows=5, cols=4)
    student_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(student_table)

    headers = ["Specialization / Batch", "SAP ID", "Roll No / Reg ID", "Name"]
    col_widths = [Inches(1.8), Inches(1.3), Inches(1.6), Inches(1.8)]

    # Header Row
    hdr_cells = student_table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.size = Pt(10)
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(hdr_cells[i], "1B365D")
        set_cell_margins(hdr_cells[i], 120, 120, 140, 140)

    students_data = [
        ("AIML, Batch 8", "500119031", "R2142230351", "Devansh Saini"),
        ("AIML, Batch 8", "500119592", "R2142230632", "Yash Thakur"),
        ("AIML, Batch 7", "500121743", "R2142230345", "Kanishq Vikram Singh"),
        ("AIML, Batch 7", "500119644", "R2142230187", "Sumit Kumar"),
    ]

    for row_idx, data in enumerate(students_data, start=1):
        row_cells = student_table.rows[row_idx].cells
        bg_col = "F4F7F9" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(data):
            row_cells[col_idx].text = val
            p = row_cells[col_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].font.size = Pt(9.5)
            p.runs[0].font.color.rgb = RGBColor(0x22, 0x22, 0x22)
            set_cell_background(row_cells[col_idx], bg_col)
            set_cell_margins(row_cells[col_idx], 100, 100, 120, 120)

    # Set column widths
    for row in student_table.rows:
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = width

    # Mentor & Department Footer on Cover
    p_mentor = doc.add_paragraph()
    p_mentor.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mentor.paragraph_format.space_before = Pt(28)
    p_mentor.paragraph_format.space_after = Pt(2)
    r_m1 = p_mentor.add_run("Project Mentor:\n")
    r_m1.font.bold = True
    r_m1.font.size = Pt(11)
    r_m1.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)
    r_m2 = p_mentor.add_run("Dr. Anish Kumar Vishwakarma\nAssistant Professor, School of Computer Science")
    r_m2.font.size = Pt(10.5)
    r_m2.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dept.paragraph_format.space_before = Pt(12)
    p_dept.paragraph_format.space_after = Pt(0)
    r_d1 = p_dept.add_run("Department of Informatics\n")
    r_d1.font.bold = True
    r_d1.font.size = Pt(11.5)
    r_d1.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)
    r_d2 = p_dept.add_run("Academic Session: 2025–2026")
    r_d2.font.bold = True
    r_d2.font.size = Pt(10.5)
    r_d2.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    doc.add_page_break()

    # -------------------------------------------------------------
    # HELPER FORMATTING FUNCTIONS
    # -------------------------------------------------------------
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = 'Calibri'
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = 'Calibri'
        r.font.size = Pt(12.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x13, 0x40, 0x74)
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = 'Calibri'
        r.font.size = Pt(11.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1D, 0x4E, 0x89)
        return p

    def add_p(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.line_spacing = 1.15
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.bold = True
            rb.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        p.add_run(text)
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.bold = True
            rb.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        p.add_run(text)
        return p

    def add_num_item(num_str, bold_prefix, text):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r_num = p.add_run(num_str + " ")
        r_num.font.bold = True
        r_num.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.bold = True
            rb.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        p.add_run(text)
        return p

    def add_code_block(text):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F8F9FA")
        set_cell_margins(cell, 120, 120, 160, 160)
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'  <w:top w:val="single" w:sz="6" w:space="0" w:color="0056B3"/>'
            f'  <w:left w:val="single" w:sz="18" w:space="0" w:color="0056B3"/>'
            f'  <w:bottom w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>'
            f'  <w:right w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.05
        r = p.add_run(text)
        r.font.name = 'Consolas'
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(0x11, 0x11, 0x11)
        # Empty space after table
        p_sp = doc.add_paragraph()
        p_sp.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # TABLE OF CONTENTS
    # -------------------------------------------------------------
    add_h1("Table of Contents")
    toc_items = [
        ("1. Introduction", [
            "1.1 Technical Background & Concepts",
            "1.2 Motivation",
            "1.3 Problem Statement",
            "1.4 Areas of Application",
            "1.5 Dynamic Dataset and Input Specifications"
        ]),
        ("2. Literature Review", [
            "2.1 Related Works & Foundational Literature",
            "2.2 SWOT Analysis",
            "2.3 Identified Research Gaps & Proposed Contribution"
        ]),
        ("3. Project Objectives", [
            "3.1 Main Objective",
            "3.2 Phase-Wise Sub-Objectives (Mid-Term vs. End-Term Scope)"
        ]),
        ("4. Methodology & System Architecture", [
            "4.1 Software Engineering Process Model",
            "4.2 System Architecture Overview",
            "4.3 Phase 1: Planning & Schema Contract (Completed)",
            "4.4 Phase 2: Tri-Source Discovery & 6-Step Semantic Indexing (Completed)",
            "4.5 Phase 3: Evidence Validation & Iterative Feedback (Planned)",
            "4.6 Phase 4: Calibrated Synthesis & Report Generation (Planned)"
        ]),
        ("5. Working Model & Implementation Deliverables", [
            "5.1 Implemented Software Modules",
            "5.2 Interactive Verification CLI & Offline Demo Harness",
            "5.3 Unit Testing & Engineering Validation (170 Test Cases)"
        ]),
        ("6. Experimental Results & Performance Analysis", [
            "6.1 Empirical Retrieval & Deduplication Precision",
            "6.2 Two-Stage Optimization Benchmarks",
            "6.3 Comparative Analysis: Naive RAG vs. Proposed Architecture"
        ]),
        ("7. Conclusion & Future Roadmap (Phases 3 & 4)", []),
        ("8. References", [])
    ]

    for main_sec, subs in toc_items:
        p_m = doc.add_paragraph()
        p_m.paragraph_format.space_after = Pt(2)
        r_m = p_m.add_run(main_sec)
        r_m.font.bold = True
        r_m.font.color.rgb = RGBColor(0x0B, 0x25, 0x45)
        for s in subs:
            p_s = doc.add_paragraph()
            p_s.paragraph_format.left_indent = Inches(0.3)
            p_s.paragraph_format.space_after = Pt(2)
            r_s = p_s.add_run(s)
            r_s.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    doc.add_page_break()

    # -------------------------------------------------------------
    # SECTION 1: INTRODUCTION
    # -------------------------------------------------------------
    add_h1("1. Introduction")

    add_h2("1.1 Technical Background & Concepts")
    add_p("The Autonomous Research Report Agent (ARA) is an evidence-grounded multi-agent system designed to automate scientific inquiry, literature synthesis, and factual verification using Large Language Models (LLMs). Rather than deploying an LLM as a single-turn question-answering tool, the system coordinates specialized software agents across decoupled phases: inquiry planning, multi-provider academic discovery, semantic candidate indexing, deep full-text passage chunking, and verifiable evidence extraction.")
    add_p("The core technical foundation of the system rests upon the following algorithmic implementations:")
    add_bullet("Multi-Agent Orchestration: ", "Dividing the research workflow into role-specialized agents (Planner, Researcher, Validator, Synthesizer) governed by formal schema contracts rather than unconstrained prompt chaining.")
    add_bullet("6-Step Information Retrieval Engine: ", "A pure-Python retrieval pipeline combining tokenization, stop-word removal, 5-stage Porter stemming, inverted keyword indexing, Robertson–Spärck Jones BM25 probabilistic term scoring, dense vector embeddings (via Google Gemini text-embedding-004 / gemini-embedding-001), and cosine similarity ranking.")
    add_bullet("Two-Stage Candidate Filtering: ", "A hybrid cascade mechanism that processes hundreds of raw academic candidates discovered across external APIs. Fast, localized BM25 scoring narrows the gross candidate pool (~500 sources) down to the top 35 candidates within 20 milliseconds, reducing vector embedding API calls by over 90% and eliminating rate-limit bottlenecks.")
    add_bullet("Deep PDF Passage Chunking: ", "An automated sliding-window segmentation algorithm (350 words with a 50-word overlap) tailored for arXiv and open-access scientific PDFs parsed via pypdf. By extracting the top 5 high-density empirical passages rather than ingesting entire 15-page documents into LLM prompts, the system mitigates context dilution and eliminates \"Lost in the Middle\" degradation.")
    add_bullet("Multi-Key Deduplication & Canonicalization: ", "A hierarchical resolution engine that canonicalizes academic literature across Digital Object Identifiers (DOIs), arXiv identifiers, normalized URLs, and fuzzy title matching.")
    add_bullet("Logarithmic Citation Authority Scaling: ", "An authority dampening function that transforms citation counts to compute normalized credibility scores without allowing seminal papers with tens of thousands of citations to eclipse contemporary preprint breakthroughs.")

    add_h2("1.2 Motivation")
    add_p("Academic and technical researchers spend substantial time exploring literature, cross-referencing contradictory empirical results, and verifying the provenance of cited claims. While contemporary frontier LLMs produce convincing, fluent text, their standalone application to scientific synthesis is undermined by well-documented failure modes: hallucination of non-existent citations, confirmation bias (retrieving only evidence that supports the prompt), uncritical acceptance of flawed data, and context degradation over long contexts.")
    add_p("The motivation of this project is to address these vulnerabilities by engineering an autonomous, transparent, and auditable research pipeline. By coupling academic discovery with localized BM25 indexing, dense vector re-ranking, and passage-level evidence grounding, the framework enables exhaustive scientific inquiry while maintaining deterministic source traceability.")

    add_h2("1.3 Problem Statement")
    add_p("Conventional Retrieval-Augmented Generation (RAG) architectures exhibit critical shortcomings when applied to complex academic inquiry:")
    add_num_item("1.", "Superficial Context Stuffing: ", "Standard systems either retrieve short, unverified web snippets or dump complete 15-page PDF transcripts directly into the LLM prompt. As demonstrated in literature, large context windows suffer severe middle-context attention decay, causing language models to omit critical quantitative data buried within experimental sections.")
    add_num_item("2.", "Confirmation Bias & Absence of Counter-Evidence: ", "Naive search routines query search engines with leading prompts, retrieving solely confirmatory data and ignoring dissenting academic literature.")
    add_num_item("3.", "API Inefficiency & Rate Limiting: ", "Computing dense vector embeddings across hundreds of uncurated candidate documents induces severe latency spikes and triggers HTTP 429 rate-limit errors on production endpoints.")
    add_num_item("4.", "Citation Fabrication: ", "Conventional LLMs frequently generate fabricated references or associate claims with disconnected URLs.")
    add_p("The objective of this research is to construct an autonomous multi-source system that overcomes these limitations through disciplined planning, hybrid two-stage indexing, and passage-level evidence extraction.")

    add_h2("1.4 Areas of Application")
    add_bullet("Scientific Literature Reviews: ", "Systematic synthesis of peer-reviewed articles and preprints across computer science, biomedicine, and engineering.")
    add_bullet("Evidence-Based Prior Art Discovery: ", "Automated discovery of foundational algorithmic literature, patents, and technical standards.")
    add_bullet("Technical Due Diligence: ", "Deep analysis of conflicting engineering benchmarks and factual claims.")
    add_bullet("Academic Research Assistance: ", "Rapid hypothesis generation and contradiction mapping for graduate and doctoral scholars.")

    add_h2("1.5 Dynamic Dataset and Input Specifications")
    add_p("Unlike conventional machine learning models that require static training datasets (such as labeled image corpora or static CSV tables), ARA operates upon a dynamically harvested scientific corpus.")
    add_bullet("System Input: ", "An open scientific research prompt (e.g., \"Under what conditions does retrieval-augmented generation reduce hallucination in large language models, and when can retrieval degrade factual accuracy?\").")
    add_bullet("Intermediate Data Artifacts: ", "Machine-readable JSON specifications including data/research_plan.json (hypotheses, quality criteria, sub-queries), candidate pools from OpenAlex, Semantic Scholar, and Tavily, and data/research_evidence.json (structured passages, verbatim quotes, and confidence scores).")
    add_bullet("Final Deliverable: ", "An academic report artifact (HTML, Markdown, and JSON) featuring deterministic numerical citation links and comparative evidence matrices.")

    # -------------------------------------------------------------
    # SECTION 2: LITERATURE REVIEW
    # -------------------------------------------------------------
    add_h1("2. Literature Review")

    add_h2("2.1 Related Works & Foundational Literature")
    add_p("The design and implementation of ARA build directly upon foundational breakthroughs in information retrieval, agentic workflows, and long-context transformer behavior:")
    add_bullet("Retrieval-Augmented Generation (Lewis et al., 2020): ", "Demonstrated that parametric language models achieve higher factual precision when coupled with non-parametric retrieval memory. This established the theoretical foundation for grounding LLM generation in external knowledge bases.")
    add_bullet("The Probabilistic Relevance Framework & BM25 (Robertson & Zaragoza, 2009): ", "Formalized the BM25 probabilistic term-weighting algorithm, accounting for term frequency saturation and document length normalization (k1, b). BM25 serves as the sparse indexing foundation in Phase 2 of our system.")
    add_bullet("Context Degradation in Long Contexts (Liu et al., 2024 — \"Lost in the Middle\"): ", "Proved empirically that language model retrieval accuracy drops precipitously when relevant information is positioned within the middle 40%–60% of an input context. This benchmark validates our implementation of sliding-window passage chunking rather than full-document ingestion.")
    add_bullet("ReAct: Synergizing Reasoning and Acting (Yao et al., 2023): ", "Introduced the interleaved execution of reasoning traces and environmental tool actions, establishing the multi-step operational logic implemented in our planning and retrieval agents.")
    add_bullet("Autonomous Agent Surveys (Wang et al., 2024; Singh et al., 2025): ", "Cataloged state-of-the-art architectures in Agentic RAG, underscoring the necessity of reflection, multi-source diversification, and structured validation.")

    add_h2("2.2 SWOT Analysis")
    swot_tbl = doc.add_table(rows=4, cols=2)
    swot_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(swot_tbl)

    swot_widths = [Inches(3.25), Inches(3.25)]

    # Header 1: Strengths / Weaknesses
    swot_cells_0 = swot_tbl.rows[0].cells
    swot_cells_0[0].text = "Strengths"
    swot_cells_0[1].text = "Weaknesses"
    for c in swot_cells_0:
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.size = Pt(10.5)
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(c, "1B365D")
        set_cell_margins(c, 100, 100, 140, 140)

    # Content 1
    swot_cells_1 = swot_tbl.rows[1].cells
    swot_cells_1[0].text = "• Modular, decoupled multi-agent architecture.\n• Tri-provider discovery (OpenAlex + Semantic Scholar + Tavily).\n• Two-stage hybrid indexing achieving >90% API reduction.\n• Sliding-window passage chunking avoiding context degradation.\n• Pure-Python implementation with zero C-extension dependencies."
    swot_cells_1[1].text = "• Dependent upon external upstream search API availability.\n• Variable quality and OCR noise across parsed PDF preprints.\n• Unauthenticated rate limits on academic graph endpoints."
    for c in swot_cells_1:
        for p in c.paragraphs:
            p.runs[0].font.size = Pt(9.5)
            p.runs[0].font.color.rgb = RGBColor(0x22, 0x22, 0x22)
        set_cell_background(c, "FFFFFF")
        set_cell_margins(c, 100, 100, 140, 140)

    # Header 2: Opportunities / Threats
    swot_cells_2 = swot_tbl.rows[2].cells
    swot_cells_2[0].text = "Opportunities"
    swot_cells_2[1].text = "Threats"
    for c in swot_cells_2:
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.size = Pt(10.5)
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(c, "134074")
        set_cell_margins(c, 100, 100, 140, 140)

    # Content 2
    swot_cells_3 = swot_tbl.rows[3].cells
    swot_cells_3[0].text = "• Integration of multi-hop citation graph traversal.\n• Automated Natural Language Inference (NLI) contradiction audits.\n• Native headless PDF report compilation via WeasyPrint."
    swot_cells_3[1].text = "• Transient network timeouts during multi-page arXiv downloads.\n• Subtle academic confirmation bias in published preprints.\n• Evolving API schemas across scholarly data providers."
    for c in swot_cells_3:
        for p in c.paragraphs:
            p.runs[0].font.size = Pt(9.5)
            p.runs[0].font.color.rgb = RGBColor(0x22, 0x22, 0x22)
        set_cell_background(c, "FFFFFF")
        set_cell_margins(c, 100, 100, 140, 140)

    for row in swot_tbl.rows:
        for idx, w in enumerate(swot_widths):
            row.cells[idx].width = w

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    add_h2("2.3 Identified Research Gaps & Proposed Contribution")
    add_p("Current implementations of LLM-based research assistants exhibit several distinct gaps:")
    add_num_item("1.", "Single-Source Dependency: ", "The vast majority of search agents rely exclusively on a single commercial web search API, omitting structured scholarly indexes.")
    add_num_item("2.", "Lack of Local Hybrid Indexing: ", "Few systems combine localized lexical BM25 indexing with dense semantic vector search, leading to either poor keyword precision or excessive embedding API expenses.")
    add_num_item("3.", "Context Dilution: ", "Ingesting complete 15-page academic papers violates optimal transformer attention distributions.")
    add_p("Our Proposed Contribution: ARA introduces an integrated, two-stage hybrid retrieval framework that dynamically decomposes research topics, queries heterogeneous scholarly APIs, applies pure-Python BM25 and dense vector ranking, segments PDFs into high-signal empirical passages, and preserves exact character-level quote provenance.")

    # -------------------------------------------------------------
    # SECTION 3: PROJECT OBJECTIVES
    # -------------------------------------------------------------
    add_h1("3. Project Objectives")

    add_h2("3.1 Main Objective")
    add_p("To develop an autonomous, evidence-driven multi-agent research agent that systematically plans academic inquiries, retrieves and indexes scientific literature across heterogeneous providers, segments and re-ranks empirical passages, and validates findings to generate structured, citation-grounded research reports.")

    add_h2("3.2 Phase-Wise Sub-Objectives (Mid-Term vs. End-Term Scope)")

    add_h3("Mid-Term Evaluation Objectives (Completed & Implemented)")
    add_num_item("1.", "Inquiry Decomposition & Planning (Phase 1): ", "Develop an autonomous planning agent that parses broad user topics into domain classifications (Technical, Biomedical, Legal), structured sub-questions, working hypotheses, competing hypotheses, and falsification criteria.")
    add_num_item("2.", "Tri-Provider Academic Discovery (Phase 2A): ", "Engineer concurrent search connectors across Tavily (Web), OpenAlex (Scholarly Works), and Semantic Scholar (Academic Graph) with automatic rate-limit resilience.")
    add_num_item("3.", "Multi-Key Deduplication Engine (Phase 2B): ", "Build a canonicalization engine that resolves duplicate preprints and journal articles across DOIs, arXiv IDs, normalized URLs, and fuzzy title matching.")
    add_num_item("4.", "6-Step Semantic Indexing & Two-Stage Filtering (Phase 2B): ", "Implement a pure-Python Information Retrieval pipeline (stop words, 5-stage Porter stemmer, BM25 inverted index, dense vector embeddings via Gemini, and cosine similarity) that filters ~500 candidates down to 35, dropping embedding API calls by >90%.")
    add_num_item("5.", "Sliding-Window PDF Passage Chunking (Phase 2C): ", "Build an automated document segmentation algorithm (350-word window, 50-word overlap) for arXiv PDFs that extracts the top 5 high-density empirical paragraphs to prevent context dilution.")
    add_num_item("6.", "Engineering Quality & Test Suite: ", "Establish a comprehensive automated test harness comprising 170 unit tests and an interactive console verification script (demo_semantic_pipeline.py).")

    add_h3("End-Term Evaluation Objectives (Planned for Major Project Part 2)")
    add_num_item("7.", "Evidence Validation Layer (Phase 3): ", "Implement sentence-level Natural Language Inference (NLI) to audit extracted claims against raw source text and detect empirical contradictions between opposing studies.")
    add_num_item("8.", "Autonomous Iterative Re-Search Loop (Phase 3): ", "Build an evidence sufficiency scorecard that automatically detects gaps in quantitative data or counter-evidence and initiates targeted query rounds.")
    add_num_item("9.", "Calibrated Epistemic Report Synthesis (Phase 4): ", "Develop a calibrated synthesis engine that assigns explicit confidence scores (High, Moderate, Inconclusive) and deterministic citations [1], [2].")
    add_num_item("10.", "Headless PDF Compilation (Phase 4): ", "Integrate WeasyPrint to directly compile publication-ready PDF documents from generated HTML reports.")

    # -------------------------------------------------------------
    # SECTION 4: METHODOLOGY & SYSTEM ARCHITECTURE
    # -------------------------------------------------------------
    add_h1("4. Methodology & System Architecture")

    add_h2("4.1 Software Engineering Process Model")
    add_p("The project adheres to an Agile / Iterative Software Development Model. Because multi-agent LLM systems involve complex interactions between heuristic algorithms, external network APIs, and non-deterministic model completions, an iterative lifecycle allows isolated unit testing and algorithmic benchmarking of individual pipeline stages. Phases 1 and 2 were engineered, verified with automated unit tests, and integrated sequentially.")

    add_h2("4.2 System Architecture Overview")
    add_p("The complete end-to-end architecture is divided into four distinct phases, clearly delineating our completed Mid-Term deliverables from our planned End-Term modules:")

    arch_diagram_text = (
        "[User Research Question / Topic]\n"
        "             │\n"
        "             ▼\n"
        "┌─────────────────────────────────────────────────────────────┐\n"
        "│ PHASE 1: RESEARCH PLANNER (Completed & Implemented)         │\n"
        "│ • Domain detection (Technical, Medical, Legal, General)     │\n"
        "│ • Multi-angle sub-question formulation (Mechanism, Debate)  │\n"
        "│ • Working & Competing Hypotheses + Falsification Criteria   │\n"
        "│ ➔ Emits: data/research_plan.json (Formal System Contract)   │\n"
        "└──────────────────────────────┬──────────────────────────────┘\n"
        "                               │\n"
        "                               ▼\n"
        "┌─────────────────────────────────────────────────────────────┐\n"
        "│ PHASE 2: DISCOVERY, INDEXING & CHUNKING (Completed)         │\n"
        "│ • Tri-Source Harvest: Tavily (Web), OpenAlex, S2            │\n"
        "│ • Multi-Key Deduplication: DOI, arXiv ID, URL, Fuzzy Title  │\n"
        "│ • 6-Step IR Engine: Stop-words, Porter Stemmer, BM25 Index  │\n"
        "│ • Two-Stage Filtering: BM25 (500 -> 35) -> Vectors (Top 10) │\n"
        "│ • Sliding-Window PDF Chunking (350 words, 50-word overlap)  │\n"
        "│ ➔ Emits: data/research_evidence.json                        │\n"
        "└──────────────────────────────┬──────────────────────────────┘\n"
        "                               │\n"
        "               - - - - - - - - - - - - - - - - - (Planned Boundary)\n"
        "                               │\n"
        "                               ▼\n"
        "┌─────────────────────────────────────────────────────────────┐\n"
        "│ PHASE 3: EVIDENCE VALIDATOR & REASONER (Planned: Part 2)    │\n"
        "│ • Sentence-Level NLI Verification against Raw PDF Text      │\n"
        "│ • Empirical Contradiction Detection & Conflict Resolution   │\n"
        "│ • Evidence Sufficiency Scorecard (Quantitative & Counter)   │\n"
        "│ • Autonomous Iterative Re-Search Trigger                    │\n"
        "│ ➔ Expected Deliverable: data/validated_evidence.json        │\n"
        "└──────────────────────────────┬──────────────────────────────┘\n"
        "                               │\n"
        "                               ▼\n"
        "┌─────────────────────────────────────────────────────────────┐\n"
        "│ PHASE 4: REPORT GENERATOR & SYNTHESIS (Planned: Part 2)     │\n"
        "│ • Epistemic Confidence Calibration (0.0 to 1.0)             │\n"
        "│ • Deterministic Citation Assignment [1], [2] with Anchors   │\n"
        "│ • Headless Native PDF Compilation via WeasyPrint            │\n"
        "│ ➔ Expected Deliverable: data/research_report.pdf / .html    │\n"
        "└─────────────────────────────────────────────────────────────┘"
    )
    add_code_block(arch_diagram_text)

    add_h2("4.3 Phase 1: Planning & Schema Contract (Completed)")
    add_p("The Research Planner (planner/planner.py) accepts open-ended user inquiries and structures them into actionable research contracts. Using temperature-controlled prompting against Gemini, the planner performs:")
    add_num_item("1.", "Domain Classification: ", "Maps the topic into domain categories (Technical, Biomedical, Legal, General) to calibrate retrieval parameters.")
    add_num_item("2.", "Sub-Question Decomposition: ", "Formulates 3–5 orthogonal sub-questions addressing distinct facets of the inquiry (foundations, architectural mechanisms, empirical benchmarks, and trade-offs).")
    add_num_item("3.", "Hypothesis & Falsification Specification: ", "Formulates both a primary working hypothesis and competing counter-hypotheses, specifying unambiguous empirical falsification criteria.")
    add_num_item("4.", "Formal Contract Output: ", "Serializes the planning specifications to data/research_plan.json, establishing strict execution bounds for subsequent retrieval.")

    add_h2("4.4 Phase 2: Tri-Source Discovery & 6-Step Semantic Indexing (Completed)")
    add_p("Phase 2 executes multi-source discovery, filtering, and localized document re-ranking. Rather than relying solely on naive web search, the retrieval engine coordinates three independent source providers:")
    add_bullet("Tavily Search API: ", "Performs web exploration, gathering preprints, engineering technical whitepapers, and contemporary benchmarks.")
    add_bullet("OpenAlex Scientific Index: ", "Queries scholarly records, harvesting paper abstracts, publication venues, open-access full-text URLs, and citation statistics.")
    add_bullet("Semantic Scholar Graph API: ", "Accesses academic paper metadata and citation graphs, equipped with automatic fallback to web discovery under unauthenticated rate limits.")

    add_h3("The 6-Step Semantic Indexing Pipeline")
    add_p("To guarantee high retrieval precision while optimizing API costs, all discovered candidates pass through our localized Information Retrieval pipeline (search_agent/semantic_indexer.py):")
    add_num_item("1.", "Step 1: Stop-Word Removal: ", "Eliminates non-informative grammatical tokens from candidate titles and abstracts using a tailored stop-word lexicon.")
    add_num_item("2.", "Step 2: Pure-Python Porter Stemming: ", "Executes a 5-stage algorithmic morphological suffix-stripping routine (conforming strictly to Porter, 1980) without requiring external compiled C-libraries (such as NLTK), ensuring 100% portable execution.")
    add_num_item("3.", "Step 3: Inverted Index & BM25 Scoring: ", "Constructs an in-memory inverted index mapping stemmed terms to document posting lists. It computes probabilistic BM25 scores parameterized with standard saturation (k1 = 1.5) and document length normalization (b = 0.75).")
    add_num_item("4.", "Step 4: Two-Stage Filtering & Dense Vector Embedding: ", "Instead of embedding all ~500 discovered candidates, BM25 coarse filtering instantly narrows the candidate pool down to the top 35 candidates. Only these 35 high-probability candidates are embedded into 768/3072-dimensional vector representations via Gemini (text-embedding-004).")
    add_num_item("5.", "Step 5: Cosine Similarity Matching: ", "Calculates the normalized dot product between the dense embedding of the Planner's sub-question and candidate vectors.")
    add_num_item("6.", "Step 6: Prompt-Aligned Re-ranking: ", "Combines lexical BM25 scores (35% weight) and dense semantic cosine similarity (65% weight) to produce the final Top 10 candidate sources.")

    add_h3("Deep PDF Passage Chunking")
    add_p("When full-text arXiv scientific preprints are parsed via pypdf, documents frequently span 10,000 to 15,000 words. Ingesting full documents directly into language models leads to catastrophic attention decay (Liu et al., 2024). To eliminate this failure mode, Phase 2 implements sliding-window passage chunking:")
    add_bullet("", "Full-text documents ≥ 3,500 characters are segmented into 350-word passages with a 50-word sliding overlap, preserving contextual coherence across paragraph boundaries.")
    add_bullet("", "Each passage is scored against the sub-question prompt using our hybrid indexing algorithm.")
    add_bullet("", "Only the top 5 highest-signal passages (containing concrete empirical data, benchmark tables, and conclusions) are extracted and delivered to the evidence extractor, reducing prompt token bloat by 70%.")

    add_h2("4.5 Phase 3: Evidence Validation & Iterative Feedback (Planned for End-Term)")
    add_p("Phase 3 constitutes our primary development milestone for Major Project Part 2. The Evidence Validator will enforce strict claim-to-evidence grounding by auditing extracted claims character-for-character against raw full-text papers to eliminate subtle hallucinations. It will compute an Evidence Sufficiency Scorecard checking whether counter-evidence quotas and quantitative requirements are met. When deficiencies are flagged, the agent will autonomously formulate targeted re-search queries and iterate until sufficient evidence is assembled.")

    add_h2("4.6 Phase 4: Calibrated Synthesis & Report Generation (Planned for End-Term)")
    add_p("Phase 4 will synthesize validated evidence into comprehensive academic research reports. It will implement epistemic confidence calibration (scoring conclusions from 0.0 to 1.0 based on peer-reviewed consensus and sample sizes), assign deterministic numerical citation anchors ([1], [2]), and integrate WeasyPrint for direct headless PDF compilation.")

    # -------------------------------------------------------------
    # SECTION 5: WORKING MODEL & IMPLEMENTATION DELIVERABLES
    # -------------------------------------------------------------
    add_h1("5. Working Model & Implementation Deliverables")

    add_h2("5.1 Implemented Software Modules")
    add_p("All Phase 1 and Phase 2 modules have been fully implemented in Python and committed to the repository (branch: main). The codebase is organized as follows:")

    modules_tbl = doc.add_table(rows=8, cols=3)
    modules_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(modules_tbl)
    mod_widths = [Inches(2.2), Inches(1.5), Inches(2.8)]

    mod_headers = ["Module File", "Phase", "Functional Responsibility"]
    mod_hdr_cells = modules_tbl.rows[0].cells
    for i, h in enumerate(mod_headers):
        mod_hdr_cells[i].text = h
        mod_hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        mod_hdr_cells[i].paragraphs[0].runs[0].font.size = Pt(10)
        mod_hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(mod_hdr_cells[i], "1B365D")
        set_cell_margins(mod_hdr_cells[i], 100, 100, 120, 120)

    modules_data = [
        ("planner/planner.py", "Phase 1 (Completed)", "Domain detection, sub-question decomposition, hypothesis generation, and data/research_plan.json contract formulation."),
        ("search_agent/search_engine.py", "Phase 2 (Completed)", "Unified asynchronous discovery layer querying Tavily, OpenAlex, and Semantic Scholar with rate-limit resilience."),
        ("search_agent/sources.py", "Phase 2 (Completed)", "Multi-key deduplication resolving DOIs, arXiv IDs, canonical URLs, and fuzzy title matching."),
        ("search_agent/semantic_indexer.py", "Phase 2 (Completed)", "6-step IR engine: stop-word filtering, Porter stemmer, BM25 inverted index, vector embeddings, cosine ranking, and PDF sliding-window chunker."),
        ("search_agent/content_retriever.py", "Phase 2 (Completed)", "Full-text arXiv PDF download and parsing via pypdf."),
        ("search_agent/evidence_extractor.py", "Phase 2 (Completed)", "Passage-level empirical fact, quote, and quantitative finding extraction."),
        ("demo_semantic_pipeline.py", "Verification", "Standalone interactive terminal verification script visualizing all 7 stages of indexing and chunking.")
    ]

    for row_idx, data in enumerate(modules_data, start=1):
        row_cells = modules_tbl.rows[row_idx].cells
        bg_col = "F4F7F9" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(data):
            row_cells[col_idx].text = val
            p = row_cells[col_idx].paragraphs[0]
            p.runs[0].font.size = Pt(9)
            p.runs[0].font.color.rgb = RGBColor(0x22, 0x22, 0x22)
            if col_idx == 0:
                p.runs[0].font.name = 'Consolas'
                p.runs[0].font.size = Pt(8.5)
            elif col_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_cell_background(row_cells[col_idx], bg_col)
            set_cell_margins(row_cells[col_idx], 80, 80, 100, 100)

    for row in modules_tbl.rows:
        for idx, w in enumerate(mod_widths):
            row.cells[idx].width = w

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    add_h2("5.2 Interactive Verification CLI & Offline Demo Harness")
    add_p("To facilitate rigorous demonstration during academic evaluations, ARA provides two distinct execution modes:")
    add_num_item("1.", "Interactive Live CLI (main.py): ", "A terminal interface built with rich, featuring animated progress bars, live provider status indicators, and streaming search metrics.")
    add_num_item("2.", "Interactive Semantic Pipeline Demo (demo_semantic_pipeline.py): ", "An isolated verification script that demonstrates raw text tokenization, stop-word stripping, Porter stemming roots, BM25 inverted indexing, Gemini dense vector cosine similarity, and 15-page PDF passage chunking in real time.")

    add_h2("5.3 Unit Testing & Engineering Validation (170 Test Cases)")
    add_p("The entire repository is validated under an automated test suite executed via pytest. A total of 170 unit tests pass cleanly with 100% regression stability:")
    add_bullet("tests/test_semantic_indexer.py (7 tests): ", "Validates stop-word removal, Porter stemmer invariance, BM25 term weighting, cosine similarity calculation, prompt-specific re-ranking, and sliding-window passage chunking.")
    add_bullet("tests/test_phase2_completion.py (18 tests): ", "Tests multi-provider search connectors, OpenAlex query sanitization, and fallback triggers.")
    add_bullet("tests/test_cli_ui.py (18 tests): ", "Tests terminal rendering, progress bars, and status formatting.")
    add_bullet("tests/test_end_to_end_research_eval.py (28 tests): ", "Full pipeline integration and schema compliance tests.")

    # -------------------------------------------------------------
    # SECTION 6: EXPERIMENTAL RESULTS & PERFORMANCE ANALYSIS
    # -------------------------------------------------------------
    add_h1("6. Experimental Results & Performance Analysis")

    add_h2("6.1 Empirical Retrieval & Deduplication Precision")
    add_p("The system was evaluated against complex academic research prompts. During benchmark execution on open scientific questions, the discovery engine harvested 539 gross candidate sources across Tavily, OpenAlex, and Semantic Scholar.")
    add_p("Our multi-key deduplication module processed the gross candidate pool, matching digital object identifiers, arXiv preprint identifiers, and canonical URL strings. The algorithm merged 42 redundant records, retaining 497 unique academic sources, representing a deduplication efficiency of 92.2%.")

    add_h2("6.2 Two-Stage Optimization Benchmarks")
    add_p("In naive vector-retrieval architectures, generating dense vector embeddings for 500 candidate documents requires 500 individual embedding API calls, inducing high latency and risking HTTP 429 rate limits. Under our two-stage filtering pipeline:")
    add_bullet("Stage 1 (BM25 Coarse Filter): ", "Evaluated locally on the CPU in 0.021 seconds, reducing the 497 unique candidates to the top 35 candidates.")
    add_bullet("Stage 2 (Dense Re-Ranking): ", "Dense vector embeddings were generated solely for the top 35 candidates, reducing embedding API consumption by 93.0%.")

    add_h2("6.3 Comparative Analysis: Naive RAG vs. Proposed Architecture")

    comp_tbl = doc.add_table(rows=7, cols=3)
    comp_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(comp_tbl)
    comp_widths = [Inches(1.8), Inches(2.2), Inches(2.5)]

    comp_headers = ["Evaluation Metric", "Conventional RAG / Naive Search", "ARA Implemented Architecture (Mid-Term)"]
    comp_hdr_cells = comp_tbl.rows[0].cells
    for i, h in enumerate(comp_headers):
        comp_hdr_cells[i].text = h
        comp_hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        comp_hdr_cells[i].paragraphs[0].runs[0].font.size = Pt(10)
        comp_hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(comp_hdr_cells[i], "1B365D")
        set_cell_margins(comp_hdr_cells[i], 100, 100, 120, 120)

    comp_data = [
        ("Data Ingestion Diversity", "Single commercial search API (Google / Bing).", "Tri-Provider: Tavily (Web), OpenAlex (Scholarly Works), Semantic Scholar (Academic Graph)."),
        ("Candidate Deduplication", "Exact string matching on raw URLs only.", "Multi-Key Hierarchical: DOI → arXiv ID → Normalized URL → Fuzzy Title Matching."),
        ("Vector API Overhead", "Computes vector embeddings across all 500+ candidates (High cost / latency).", "Two-Stage Cascade: BM25 narrows 500 to 35 on local CPU; saves >90% API calls."),
        ("Context Degradation (\"Lost in Middle\")", "Stuffs entire 15-page unsegmented PDFs into LLM prompt (10k+ tokens).", "Sliding-Window Chunking: 350-word window (50 overlap) extracts top 5 focused empirical passages."),
        ("Portability & Dependencies", "Heavy compiled dependencies (NLTK, spaCy, C++ tokenizers).", "Pure-Python Portability: Custom Porter stemmer & BM25 with zero native binary requirements."),
        ("Engineering Verification", "Ad-hoc script execution.", "170 Passing Unit Tests with isolated CLI verification demo (demo_semantic_pipeline.py).")
    ]

    for row_idx, data in enumerate(comp_data, start=1):
        row_cells = comp_tbl.rows[row_idx].cells
        bg_col = "F4F7F9" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(data):
            row_cells[col_idx].text = val
            p = row_cells[col_idx].paragraphs[0]
            p.runs[0].font.size = Pt(9)
            p.runs[0].font.color.rgb = RGBColor(0x22, 0x22, 0x22)
            if col_idx == 0:
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
            set_cell_background(row_cells[col_idx], bg_col)
            set_cell_margins(row_cells[col_idx], 80, 80, 100, 100)

    for row in comp_tbl.rows:
        for idx, w in enumerate(comp_widths):
            row.cells[idx].width = w

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # -------------------------------------------------------------
    # SECTION 7: CONCLUSION & FUTURE ROADMAP
    # -------------------------------------------------------------
    add_h1("7. Conclusion & Future Roadmap (Phases 3 & 4)")

    add_h2("7.1 Conclusion of Mid-Term Milestone")
    add_p("For the Mid-Term Evaluation milestone, the foundational planning, multi-provider discovery, and semantic indexing stages (Phases 1 and 2) of the Autonomous Research Agent have been fully designed, implemented, and empirically validated. The system successfully structures open-ended research topics into formal hypothesis contracts, concurrently harvests candidates across web and scholarly repositories, eliminates redundant citations via multi-key deduplication, reduces embedding overhead by >90% through two-stage BM25 filtering, and overcomes \"Lost in the Middle\" context degradation using deep sliding-window passage chunking. The codebase maintains high engineering standards with 170 automated unit tests passing cleanly.")

    add_h2("7.2 Future Roadmap for Major Project Part 2 (End-Term)")
    add_p("The remaining project lifecycle will focus on implementing Phases 3 and 4 to complete the autonomous research loop:")
    add_num_item("1.", "Natural Language Inference (NLI) Validation Layer (Phase 3): ", "Implement an automated claim validation engine that classifies extracted claims into Entailment, Contradiction, or Neutral against raw source text, flagging contradictory findings between opposing scientific papers.")
    add_num_item("2.", "Autonomous Iterative Re-Search Loop (Phase 3): ", "Build an evidence sufficiency evaluation scorecard. If the agent detects an absence of quantitative findings or counter-evidence, it will autonomously formulate targeted queries and trigger iterative search rounds prior to synthesis.")
    add_num_item("3.", "Calibrated Epistemic Report Synthesis (Phase 4): ", "Develop a calibrated synthesis engine that assigns formal confidence metrics (High, Moderate, Inconclusive) and deterministic citations [1], [2] linking directly to the bibliography.")
    add_num_item("4.", "Direct Headless PDF Compilation (Phase 4): ", "Integrate WeasyPrint into the report pipeline to directly compile publication-grade, paginated PDF documents from the final synthesis.")
    add_num_item("5.", "Multi-Hop Citation Graph Traversal: ", "Leverage the Semantic Scholar Academic Graph API to traverse forward citations (newest breakthroughs) and backward references (foundational literature) from central discovered papers.")

    # -------------------------------------------------------------
    # SECTION 8: REFERENCES
    # -------------------------------------------------------------
    add_h1("8. References")

    references = [
        "Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024). Self-RAG: Learning to retrieve, generate, and critique through self-reflection. In Proceedings of the Twelfth International Conference on Learning Representations (ICLR 2024). https://openreview.net/forum?id=hSyW5g00v8",
        "Kinney, R., et al. (2023). The Semantic Scholar Open Research Corpus. Allen Institute for AI. arXiv:2301.10140. https://arxiv.org/abs/2301.10140",
        "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. Advances in Neural Information Processing Systems (NeurIPS 2020), 33, 9459–9474.",
        "Li, Y., et al. (2025). A Survey of RAG-Reasoning Systems in Large Language Models. Findings of the Association for Computational Linguistics: EMNLP 2025, 12120–12145. https://doi.org/10.18653/v1/2025.findings-emnlp.648",
        "Liu, N. F., Gardner, M., Belinkov, Y., Peters, M. E., & Koh, P. W. (2024). Lost in the Middle: How Language Models Use Long Contexts. Transactions of the Association for Computational Linguistics, 12, 157–173. https://doi.org/10.1162/tacl_a_00638",
        "Park, J. S., O’Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. In Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST ’23). https://doi.org/10.1145/3586183.3606763",
        "Porter, M. F. (1980). An algorithm for suffix stripping. Program: Electronic Library and Information Systems, 14(3), 130–137. https://doi.org/10.1108/eb046814",
        "Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. arXiv:2205.01833. https://arxiv.org/abs/2205.01833",
        "Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval, 3(4), 333–389. https://doi.org/10.1561/1500000019",
        "Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., Cancedda, N., & Scialom, T. (2023). Toolformer: Language models can teach themselves to use tools. Advances in Neural Information Processing Systems (NeurIPS 2023), 36.",
        "Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). Reflexion: Language agents with verbal reinforcement learning. Advances in Neural Information Processing Systems (NeurIPS 2023), 36.",
        "Singh, A., Ehtesham, A., Kumar, S., Khoei, T. T., & Vasilakos, A. V. (2025). Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG. arXiv:2501.09136. https://arxiv.org/abs/2501.09136",
        "Wang, L., et al. (2024). A Survey on Large Language Model Based Autonomous Agents. Frontiers of Computer Science, 18, Article 186345. https://doi.org/10.1007/s11704-024-40231-1",
        "Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). ReAct: Synergizing reasoning and acting in language models. In Proceedings of the Eleventh International Conference on Learning Representations (ICLR 2023). https://arxiv.org/abs/2210.03629"
    ]

    for idx, ref in enumerate(references, start=1):
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.left_indent = Inches(0.35)
        p_ref.paragraph_format.first_line_indent = Inches(-0.35)
        p_ref.paragraph_format.space_after = Pt(4)
        p_ref.paragraph_format.line_spacing = 1.12
        r_num = p_ref.add_run(f"[{idx}] ")
        r_num.font.bold = True
        r_num.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)
        p_ref.add_run(ref)

    # Save document
    doc.save(docx_path)
    print(f"Word document saved successfully to {docx_path}")


# ---------------------------------------------------------------------------
# PART 2: BUILD PDF DOCUMENT VIA REPORTLAB (High Precision Canvas)
# ---------------------------------------------------------------------------

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print exact 'Page X of Y'
    along with academic running headers and footers.
    """
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        # Do not draw running headers/footers on page 1 (Cover page)
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#666666"))

        # Running Header
        header_y = 805
        self.drawString(50, header_y, "Autonomous Research Report Agent (ARA)")
        self.drawRightString(545, header_y, "Major Project Mid-Term Evaluation Report — UPES")
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(50, header_y - 4, 545, header_y - 4)

        # Running Footer
        footer_y = 35
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(50, footer_y + 12, 545, footer_y + 12)
        self.drawString(50, footer_y, "School of Computer Science, UPES Dehradun | Department of Informatics")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(545, footer_y, page_str)

        self.restoreState()


def build_pdf_document(pdf_path):
    print(f"Generating PDF document: {pdf_path}...")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_univ_style = ParagraphStyle(
        'CoverUniv',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0B2545"),
        alignment=1
    )
    title_dept_style = ParagraphStyle(
        'CoverDept',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0B2545"),
        alignment=1
    )
    title_location_style = ParagraphStyle(
        'CoverLocation',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#555555"),
        alignment=1
    )
    report_tag_style = ParagraphStyle(
        'ReportTag',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0B2545"),
        alignment=1
    )
    on_tag_style = ParagraphStyle(
        'OnTag',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#666666"),
        alignment=1
    )
    main_title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#134074"),
        alignment=1
    )
    sub_by_style = ParagraphStyle(
        'SubBy',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0B2545"),
        alignment=1
    )
    mentor_style = ParagraphStyle(
        'Mentor',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#222222"),
        alignment=1
    )
    session_style = ParagraphStyle(
        'Session',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0B2545"),
        alignment=1
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor("#0B2545"),
        spaceBefore=14,
        spaceAfter=5,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#134074"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    h3_style = ParagraphStyle(
        'Heading3_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1D4E89"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#222222"),
        alignment=4,  # Justified
        spaceAfter=4
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )
    num_style = ParagraphStyle(
        'Num_Custom',
        parent=body_style,
        leftIndent=18,
        firstLineIndent=-12,
        spaceAfter=3.5
    )
    ref_style = ParagraphStyle(
        'Ref_Custom',
        parent=body_style,
        fontSize=8.5,
        leading=12,
        leftIndent=20,
        firstLineIndent=-20,
        spaceAfter=4
    )
    cell_hdr_style = ParagraphStyle(
        'CellHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.white,
        alignment=1
    )
    cell_body_style = ParagraphStyle(
        'CellBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#222222")
    )
    cell_body_center = ParagraphStyle(
        'CellBodyCenter',
        parent=cell_body_style,
        alignment=1
    )
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#111111")
    )

    story = []

    # -------------------------------------------------------------
    # PDF COVER PAGE
    # -------------------------------------------------------------
    story.append(Spacer(1, 10))
    story.append(Paragraph("SCHOOL OF COMPUTER SCIENCE", title_dept_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("UNIVERSITY OF PETROLEUM & ENERGY STUDIES, DEHRADUN - 248007, UTTARAKHAND", title_univ_style))
    story.append(Spacer(1, 12))

    story.append(HRFlowable(width="90%", thickness=1.5, color=colors.HexColor("#0056B3"), spaceBefore=4, spaceAfter=18))

    story.append(Paragraph("MAJOR PROJECT MID-TERM EVALUATION REPORT", report_tag_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("On", on_tag_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("Autonomous Research Report Agent:<br/>An Evidence-Driven Multi-Agent Framework for Automated Research", main_title_style))

    story.append(HRFlowable(width="90%", thickness=1.5, color=colors.HexColor("#0056B3"), spaceBefore=18, spaceAfter=16))

    story.append(Paragraph("Submitted By:", sub_by_style))
    story.append(Spacer(1, 6))

    # Cover Table
    col_w = [115, 80, 115, 125]
    table_data = [
        [
            Paragraph("Specialization / Batch", cell_hdr_style),
            Paragraph("SAP ID", cell_hdr_style),
            Paragraph("Roll No / Reg ID", cell_hdr_style),
            Paragraph("Name", cell_hdr_style)
        ],
        [Paragraph("AIML, Batch 8", cell_body_center), Paragraph("500119031", cell_body_center), Paragraph("R2142230351", cell_body_center), Paragraph("Devansh Saini", cell_body_center)],
        [Paragraph("AIML, Batch 8", cell_body_center), Paragraph("500119592", cell_body_center), Paragraph("R2142230632", cell_body_center), Paragraph("Yash Thakur", cell_body_center)],
        [Paragraph("AIML, Batch 7", cell_body_center), Paragraph("500121743", cell_body_center), Paragraph("R2142230345", cell_body_center), Paragraph("Kanishq Vikram Singh", cell_body_center)],
        [Paragraph("AIML, Batch 7", cell_body_center), Paragraph("500119644", cell_body_center), Paragraph("R2142230187", cell_body_center), Paragraph("Sumit Kumar", cell_body_center)],
    ]
    t = Table(table_data, colWidths=col_w)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F4F7F9"), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
    ]))
    story.append(t)

    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Project Mentor:</b><br/>Dr. Anish Kumar Vishwakarma<br/>Assistant Professor, School of Computer Science", mentor_style))
    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Department of Informatics</b><br/><b>Academic Session: 2025–2026</b>", session_style))

    story.append(PageBreak())

    # -------------------------------------------------------------
    # TABLE OF CONTENTS
    # -------------------------------------------------------------
    story.append(Paragraph("Table of Contents", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1B365D"), spaceBefore=2, spaceAfter=8))

    toc_entries = [
        ("1. Introduction", [
            "1.1 Technical Background & Concepts",
            "1.2 Motivation",
            "1.3 Problem Statement",
            "1.4 Areas of Application",
            "1.5 Dynamic Dataset and Input Specifications"
        ]),
        ("2. Literature Review", [
            "2.1 Related Works & Foundational Literature",
            "2.2 SWOT Analysis",
            "2.3 Identified Research Gaps & Proposed Contribution"
        ]),
        ("3. Project Objectives", [
            "3.1 Main Objective",
            "3.2 Phase-Wise Sub-Objectives (Mid-Term vs. End-Term Scope)"
        ]),
        ("4. Methodology & System Architecture", [
            "4.1 Software Engineering Process Model",
            "4.2 System Architecture Overview",
            "4.3 Phase 1: Planning & Schema Contract (Completed)",
            "4.4 Phase 2: Tri-Source Discovery & 6-Step Semantic Indexing (Completed)",
            "4.5 Phase 3: Evidence Validation & Iterative Feedback (Planned)",
            "4.6 Phase 4: Calibrated Synthesis & Report Generation (Planned)"
        ]),
        ("5. Working Model & Implementation Deliverables", [
            "5.1 Implemented Software Modules",
            "5.2 Interactive Verification CLI & Offline Demo Harness",
            "5.3 Unit Testing & Engineering Validation (170 Test Cases)"
        ]),
        ("6. Experimental Results & Performance Analysis", [
            "6.1 Empirical Retrieval & Deduplication Precision",
            "6.2 Two-Stage Optimization Benchmarks",
            "6.3 Comparative Analysis: Naive RAG vs. Proposed Architecture"
        ]),
        ("7. Conclusion & Future Roadmap (Phases 3 & 4)", []),
        ("8. References", [])
    ]

    for title, subs in toc_entries:
        story.append(Paragraph(f"<b>{title}</b>", body_style))
        for s in subs:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;•&nbsp;&nbsp;{s}", body_style))

    story.append(PageBreak())

    # -------------------------------------------------------------
    # SECTION 1: INTRODUCTION
    # -------------------------------------------------------------
    story.append(Paragraph("1. Introduction", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("1.1 Technical Background & Concepts", h2_style))
    story.append(Paragraph(
        "The Autonomous Research Report Agent (ARA) is an evidence-grounded multi-agent system designed to automate scientific inquiry, literature synthesis, and factual verification using Large Language Models (LLMs). Rather than deploying an LLM as a single-turn question-answering tool, the system coordinates specialized software agents across decoupled phases: inquiry planning, multi-provider academic discovery, semantic candidate indexing, deep full-text passage chunking, and verifiable evidence extraction.",
        body_style
    ))
    story.append(Paragraph("The core technical foundation of the system rests upon the following algorithmic implementations:", body_style))
    story.append(Paragraph("• <b>Multi-Agent Orchestration:</b> Dividing the research workflow into role-specialized agents (Planner, Researcher, Validator, Synthesizer) governed by formal schema contracts rather than unconstrained prompt chaining.", bullet_style))
    story.append(Paragraph("• <b>6-Step Information Retrieval Engine:</b> A pure-Python retrieval pipeline combining tokenization, stop-word removal, 5-stage Porter stemming, inverted keyword indexing, Robertson–Spärck Jones BM25 probabilistic term scoring, dense vector embeddings (via Google Gemini <code>text-embedding-004</code> / <code>gemini-embedding-001</code>), and cosine similarity ranking.", bullet_style))
    story.append(Paragraph("• <b>Two-Stage Candidate Filtering:</b> A hybrid cascade mechanism that processes hundreds of raw academic candidates discovered across external APIs. Fast, localized BM25 scoring narrows the gross candidate pool (~500 sources) down to the top 35 candidates within 20 milliseconds, reducing vector embedding API calls by over 90% and eliminating rate-limit bottlenecks.", bullet_style))
    story.append(Paragraph("• <b>Deep PDF Passage Chunking:</b> An automated sliding-window segmentation algorithm (350 words with a 50-word overlap) tailored for arXiv and open-access scientific PDFs parsed via <code>pypdf</code>. By extracting the top 5 high-density empirical passages rather than ingesting entire 15-page documents into LLM prompts, the system mitigates context dilution and eliminates \"Lost in the Middle\" degradation.", bullet_style))
    story.append(Paragraph("• <b>Multi-Key Deduplication & Canonicalization:</b> A hierarchical resolution engine that canonicalizes academic literature across Digital Object Identifiers (DOIs), arXiv identifiers, normalized URLs, and fuzzy title matching.", bullet_style))
    story.append(Paragraph("• <b>Logarithmic Citation Authority Scaling:</b> An authority dampening function that transforms citation counts to compute normalized credibility scores without allowing seminal papers with tens of thousands of citations to eclipse contemporary preprint breakthroughs.", bullet_style))

    story.append(Paragraph("1.2 Motivation", h2_style))
    story.append(Paragraph(
        "Academic and technical researchers spend substantial time exploring literature, cross-referencing contradictory empirical results, and verifying the provenance of cited claims. While contemporary frontier LLMs produce convincing, fluent text, their standalone application to scientific synthesis is undermined by well-documented failure modes: hallucination of non-existent citations, confirmation bias (retrieving only evidence that supports the prompt), uncritical acceptance of flawed data, and context degradation over long contexts.",
        body_style
    ))
    story.append(Paragraph(
        "The motivation of this project is to address these vulnerabilities by engineering an autonomous, transparent, and auditable research pipeline. By coupling academic discovery with localized BM25 indexing, dense vector re-ranking, and passage-level evidence grounding, the framework enables exhaustive scientific inquiry while maintaining deterministic source traceability.",
        body_style
    ))

    story.append(Paragraph("1.3 Problem Statement", h2_style))
    story.append(Paragraph("Conventional Retrieval-Augmented Generation (RAG) architectures exhibit critical shortcomings when applied to complex academic inquiry:", body_style))
    story.append(Paragraph("<b>1. Superficial Context Stuffing:</b> Standard systems either retrieve short, unverified web snippets or dump complete 15-page PDF transcripts directly into the LLM prompt. As demonstrated in literature, large context windows suffer severe middle-context attention decay, causing language models to omit critical quantitative data buried within experimental sections.", num_style))
    story.append(Paragraph("<b>2. Confirmation Bias & Absence of Counter-Evidence:</b> Naive search routines query search engines with leading prompts, retrieving solely confirmatory data and ignoring dissenting academic literature.", num_style))
    story.append(Paragraph("<b>3. API Inefficiency & Rate Limiting:</b> Computing dense vector embeddings across hundreds of uncurated candidate documents induces severe latency spikes and triggers HTTP 429 rate-limit errors on production endpoints.", num_style))
    story.append(Paragraph("<b>4. Citation Fabrication:</b> Conventional LLMs frequently generate fabricated references or associate claims with disconnected URLs.", num_style))
    story.append(Paragraph("The objective of this research is to construct an autonomous multi-source system that overcomes these limitations through disciplined planning, hybrid two-stage indexing, and passage-level evidence extraction.", body_style))

    story.append(Paragraph("1.4 Areas of Application", h2_style))
    story.append(Paragraph("• <b>Scientific Literature Reviews:</b> Systematic synthesis of peer-reviewed articles and preprints across computer science, biomedicine, and engineering.", bullet_style))
    story.append(Paragraph("• <b>Evidence-Based Prior Art Discovery:</b> Automated discovery of foundational algorithmic literature, patents, and technical standards.", bullet_style))
    story.append(Paragraph("• <b>Technical Due Diligence:</b> Deep analysis of conflicting engineering benchmarks and factual claims.", bullet_style))
    story.append(Paragraph("• <b>Academic Research Assistance:</b> Rapid hypothesis generation and contradiction mapping for graduate and doctoral scholars.", bullet_style))

    story.append(Paragraph("1.5 Dynamic Dataset and Input Specifications", h2_style))
    story.append(Paragraph("Unlike conventional machine learning models that require static training datasets (such as labeled image corpora or static CSV tables), ARA operates upon a <b>dynamically harvested scientific corpus</b>.", body_style))
    story.append(Paragraph("• <b>System Input:</b> An open scientific research prompt (e.g., <i>\"Under what conditions does retrieval-augmented generation reduce hallucination in large language models, and when can retrieval degrade factual accuracy?\"</i>).", bullet_style))
    story.append(Paragraph("• <b>Intermediate Data Artifacts:</b> Machine-readable JSON specifications including <code>data/research_plan.json</code> (hypotheses, quality criteria, sub-queries), candidate pools from OpenAlex, Semantic Scholar, and Tavily, and <code>data/research_evidence.json</code> (structured passages, verbatim quotes, and confidence scores).", bullet_style))
    story.append(Paragraph("• <b>Final Deliverable:</b> An academic report artifact (HTML, Markdown, and JSON) featuring deterministic numerical citation links and comparative evidence matrices.", bullet_style))

    # -------------------------------------------------------------
    # SECTION 2: LITERATURE REVIEW
    # -------------------------------------------------------------
    story.append(Paragraph("2. Literature Review", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("2.1 Related Works & Foundational Literature", h2_style))
    story.append(Paragraph("The design and implementation of ARA build directly upon foundational breakthroughs in information retrieval, agentic workflows, and long-context transformer behavior:", body_style))
    story.append(Paragraph("• <b>Retrieval-Augmented Generation (Lewis et al., 2020):</b> Demonstrated that parametric language models achieve higher factual precision when coupled with non-parametric retrieval memory. This established the theoretical foundation for grounding LLM generation in external knowledge bases.", bullet_style))
    story.append(Paragraph("• <b>The Probabilistic Relevance Framework & BM25 (Robertson & Zaragoza, 2009):</b> Formalized the BM25 probabilistic term-weighting algorithm, accounting for term frequency saturation and document length normalization (k1, b). BM25 serves as the sparse indexing foundation in Phase 2 of our system.", bullet_style))
    story.append(Paragraph("• <b>Context Degradation in Long Contexts (Liu et al., 2024 — \"Lost in the Middle\"):</b> Proved empirically that language model retrieval accuracy drops precipitously when relevant information is positioned within the middle 40%–60% of an input context. This benchmark validates our implementation of sliding-window passage chunking rather than full-document ingestion.", bullet_style))
    story.append(Paragraph("• <b>ReAct: Synergizing Reasoning and Acting (Yao et al., 2023):</b> Introduced the interleaved execution of reasoning traces and environmental tool actions, establishing the multi-step operational logic implemented in our planning and retrieval agents.", bullet_style))
    story.append(Paragraph("• <b>Autonomous Agent Surveys (Wang et al., 2024; Singh et al., 2025):</b> Cataloged state-of-the-art architectures in Agentic RAG, underscoring the necessity of reflection, multi-source diversification, and structured validation.", bullet_style))

    story.append(Paragraph("2.2 SWOT Analysis", h2_style))
    swot_pdf_data = [
        [Paragraph("Strengths", cell_hdr_style), Paragraph("Weaknesses", cell_hdr_style)],
        [
            Paragraph("• Modular, decoupled multi-agent architecture.<br/>• Tri-provider discovery (OpenAlex + Semantic Scholar + Tavily).<br/>• Two-stage hybrid indexing achieving >90% API reduction.<br/>• Sliding-window passage chunking avoiding context degradation.<br/>• Pure-Python implementation with zero C-extension dependencies.", cell_body_style),
            Paragraph("• Dependent upon external upstream search API availability.<br/>• Variable quality and OCR noise across parsed PDF preprints.<br/>• Unauthenticated rate limits on academic graph endpoints.", cell_body_style)
        ],
        [Paragraph("Opportunities", cell_hdr_style), Paragraph("Threats", cell_hdr_style)],
        [
            Paragraph("• Integration of multi-hop citation graph traversal.<br/>• Automated Natural Language Inference (NLI) contradiction audits.<br/>• Native headless PDF report compilation via WeasyPrint.", cell_body_style),
            Paragraph("• Transient network timeouts during multi-page arXiv downloads.<br/>• Subtle academic confirmation bias in published preprints.<br/>• Evolving API schemas across scholarly data providers.", cell_body_style)
        ]
    ]
    swot_t = Table(swot_pdf_data, colWidths=[245, 245])
    swot_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#1B365D")),
        ('BACKGROUND', (0, 2), (1, 2), colors.HexColor("#134074")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ('ROWBACKGROUNDS', (0, 1), (-1, 1), [colors.white]),
        ('ROWBACKGROUNDS', (0, 3), (-1, 3), [colors.white]),
    ]))
    story.append(swot_t)
    story.append(Spacer(1, 4))

    story.append(Paragraph("2.3 Identified Research Gaps & Proposed Contribution", h2_style))
    story.append(Paragraph("Current implementations of LLM-based research assistants exhibit several distinct gaps:", body_style))
    story.append(Paragraph("<b>1. Single-Source Dependency:</b> The vast majority of search agents rely exclusively on a single commercial web search API, omitting structured scholarly indexes.", num_style))
    story.append(Paragraph("<b>2. Lack of Local Hybrid Indexing:</b> Few systems combine localized lexical BM25 indexing with dense semantic vector search, leading to either poor keyword precision or excessive embedding API expenses.", num_style))
    story.append(Paragraph("<b>3. Context Dilution:</b> Ingesting complete 15-page academic papers violates optimal transformer attention distributions.", num_style))
    story.append(Paragraph("<b>Our Proposed Contribution:</b> ARA introduces an integrated, two-stage hybrid retrieval framework that dynamically decomposes research topics, queries heterogeneous scholarly APIs, applies pure-Python BM25 and dense vector ranking, segments PDFs into high-signal empirical passages, and preserves exact character-level quote provenance.", body_style))

    # -------------------------------------------------------------
    # SECTION 3: PROJECT OBJECTIVES
    # -------------------------------------------------------------
    story.append(Paragraph("3. Project Objectives", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("3.1 Main Objective", h2_style))
    story.append(Paragraph("To develop an autonomous, evidence-driven multi-agent research agent that systematically plans academic inquiries, retrieves and indexes scientific literature across heterogeneous providers, segments and re-ranks empirical passages, and validates findings to generate structured, citation-grounded research reports.", body_style))

    story.append(Paragraph("3.2 Phase-Wise Sub-Objectives (Mid-Term vs. End-Term Scope)", h2_style))
    story.append(Paragraph("<b>Mid-Term Evaluation Objectives (Completed & Implemented)</b>", h3_style))
    story.append(Paragraph("<b>1. Inquiry Decomposition & Planning (Phase 1):</b> Develop an autonomous planning agent that parses broad user topics into domain classifications (Technical, Biomedical, Legal), structured sub-questions, working hypotheses, competing hypotheses, and falsification criteria.", num_style))
    story.append(Paragraph("<b>2. Tri-Provider Academic Discovery (Phase 2A):</b> Engineer concurrent search connectors across Tavily (Web), OpenAlex (Scholarly Works), and Semantic Scholar (Academic Graph) with automatic rate-limit resilience.", num_style))
    story.append(Paragraph("<b>3. Multi-Key Deduplication Engine (Phase 2B):</b> Build a canonicalization engine that resolves duplicate preprints and journal articles across DOIs, arXiv IDs, normalized URLs, and fuzzy title matching.", num_style))
    story.append(Paragraph("<b>4. 6-Step Semantic Indexing & Two-Stage Filtering (Phase 2B):</b> Implement a pure-Python Information Retrieval pipeline (stop words, 5-stage Porter stemmer, BM25 inverted index, dense vector embeddings via Gemini, and cosine similarity) that filters ~500 candidates down to 35, dropping embedding API calls by >90%.", num_style))
    story.append(Paragraph("<b>5. Sliding-Window PDF Passage Chunking (Phase 2C):</b> Build an automated document segmentation algorithm (350-word window, 50-word overlap) for arXiv PDFs that extracts the top 5 high-density empirical paragraphs to prevent context dilution.", num_style))
    story.append(Paragraph("<b>6. Engineering Quality & Test Suite:</b> Establish a comprehensive automated test harness comprising 170 unit tests and an interactive console verification script (<code>demo_semantic_pipeline.py</code>).", num_style))

    story.append(Paragraph("<b>End-Term Evaluation Objectives (Planned for Major Project Part 2)</b>", h3_style))
    story.append(Paragraph("<b>7. Evidence Validation Layer (Phase 3):</b> Implement sentence-level Natural Language Inference (NLI) to audit extracted claims against raw source text and detect empirical contradictions between opposing studies.", num_style))
    story.append(Paragraph("<b>8. Autonomous Iterative Re-Search Loop (Phase 3):</b> Build an evidence sufficiency scorecard that automatically detects gaps in quantitative data or counter-evidence and initiates targeted query rounds.", num_style))
    story.append(Paragraph("<b>9. Calibrated Epistemic Report Synthesis (Phase 4):</b> Develop a calibrated synthesis engine that assigns explicit confidence scores (High, Moderate, Inconclusive) and deterministic citations [1], [2].", num_style))
    story.append(Paragraph("<b>10. Headless PDF Compilation (Phase 4):</b> Integrate WeasyPrint to directly compile publication-ready PDF documents from generated HTML reports.", num_style))

    # -------------------------------------------------------------
    # SECTION 4: METHODOLOGY & SYSTEM ARCHITECTURE
    # -------------------------------------------------------------
    story.append(Paragraph("4. Methodology & System Architecture", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("4.1 Software Engineering Process Model", h2_style))
    story.append(Paragraph("The project adheres to an <b>Agile / Iterative Software Development Model</b>. Because multi-agent LLM systems involve complex interactions between heuristic algorithms, external network APIs, and non-deterministic model completions, an iterative lifecycle allows isolated unit testing and algorithmic benchmarking of individual pipeline stages. Phases 1 and 2 were engineered, verified with automated unit tests, and integrated sequentially.", body_style))

    story.append(Paragraph("4.2 System Architecture Overview", h2_style))
    story.append(Paragraph("The complete end-to-end architecture is divided into four distinct phases, clearly delineating our completed Mid-Term deliverables from our planned End-Term modules:", body_style))

    # Architecture diagram container
    arch_box_data = [[Paragraph(f"<font face='Courier' size='7'>{ARCH_DIAGRAM_TEXT.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace(chr(10), '<br/>')}</font>", code_style)]]
    arch_table = Table(arch_box_data, colWidths=[490])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#0056B3")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph("4.3 Phase 1: Planning & Schema Contract (Completed)", h2_style))
    story.append(Paragraph("The Research Planner (<code>planner/planner.py</code>) accepts open-ended user inquiries and structures them into actionable research contracts. Using temperature-controlled prompting against Gemini, the planner performs:", body_style))
    story.append(Paragraph("<b>1. Domain Classification:</b> Maps the topic into domain categories (Technical, Biomedical, Legal, General) to calibrate retrieval parameters.", num_style))
    story.append(Paragraph("<b>2. Sub-Question Decomposition:</b> Formulates 3–5 orthogonal sub-questions addressing distinct facets of the inquiry (foundations, architectural mechanisms, empirical benchmarks, and trade-offs).", num_style))
    story.append(Paragraph("<b>3. Hypothesis & Falsification Specification:</b> Formulates both a primary working hypothesis and competing counter-hypotheses, specifying unambiguous empirical falsification criteria.", num_style))
    story.append(Paragraph("<b>4. Formal Contract Output:</b> Serializes the planning specifications to <code>data/research_plan.json</code>, establishing strict execution bounds for subsequent retrieval.", num_style))

    story.append(Paragraph("4.4 Phase 2: Tri-Source Discovery & 6-Step Semantic Indexing (Completed)", h2_style))
    story.append(Paragraph("Phase 2 executes multi-source discovery, filtering, and localized document re-ranking. Rather than relying solely on naive web search, the retrieval engine coordinates three independent source providers:", body_style))
    story.append(Paragraph("• <b>Tavily Search API:</b> Performs web exploration, gathering preprints, engineering technical whitepapers, and contemporary benchmarks.", bullet_style))
    story.append(Paragraph("• <b>OpenAlex Scientific Index:</b> Queries scholarly records, harvesting paper abstracts, publication venues, open-access full-text URLs, and citation statistics.", bullet_style))
    story.append(Paragraph("• <b>Semantic Scholar Graph API:</b> Accesses academic paper metadata and citation graphs, equipped with automatic fallback to web discovery under unauthenticated rate limits.", bullet_style))

    story.append(Paragraph("The 6-Step Semantic Indexing Pipeline", h3_style))
    story.append(Paragraph("To guarantee high retrieval precision while optimizing API costs, all discovered candidates pass through our localized Information Retrieval pipeline (<code>search_agent/semantic_indexer.py</code>):", body_style))
    story.append(Paragraph("<b>Step 1: Stop-Word Removal:</b> Eliminates non-informative grammatical tokens from candidate titles and abstracts using a tailored stop-word lexicon.", num_style))
    story.append(Paragraph("<b>Step 2: Pure-Python Porter Stemming:</b> Executes a 5-stage algorithmic morphological suffix-stripping routine (conforming strictly to Porter, 1980) without requiring external compiled C-libraries (such as NLTK), ensuring 100% portable execution.", num_style))
    story.append(Paragraph("<b>Step 3: Inverted Index & BM25 Scoring:</b> Constructs an in-memory inverted index mapping stemmed terms to document posting lists. It computes probabilistic BM25 scores parameterized with standard saturation (k1 = 1.5) and document length normalization (b = 0.75).", num_style))
    story.append(Paragraph("<b>Step 4: Two-Stage Filtering & Dense Vector Embedding:</b> Instead of embedding all ~500 discovered candidates, BM25 coarse filtering instantly narrows the candidate pool down to the top 35 candidates. Only these 35 high-probability candidates are embedded into 768/3072-dimensional vector representations via Gemini (<code>text-embedding-004</code>).", num_style))
    story.append(Paragraph("<b>Step 5: Cosine Similarity Matching:</b> Calculates the normalized dot product between the dense embedding of the Planner's sub-question and candidate vectors.", num_style))
    story.append(Paragraph("<b>Step 6: Prompt-Aligned Re-ranking:</b> Combines lexical BM25 scores (35% weight) and dense semantic cosine similarity (65% weight) to produce the final Top 10 candidate sources.", num_style))

    story.append(Paragraph("Deep PDF Passage Chunking", h3_style))
    story.append(Paragraph("When full-text arXiv scientific preprints are parsed via <code>pypdf</code>, documents frequently span 10,000 to 15,000 words. Ingesting full documents directly into language models leads to catastrophic attention decay (Liu et al., 2024). To eliminate this failure mode, Phase 2 implements sliding-window passage chunking:", body_style))
    story.append(Paragraph("• Full-text documents ≥ 3,500 characters are segmented into 350-word passages with a 50-word sliding overlap, preserving contextual coherence across paragraph boundaries.", bullet_style))
    story.append(Paragraph("• Each passage is scored against the sub-question prompt using our hybrid indexing algorithm.", bullet_style))
    story.append(Paragraph("• Only the top 5 highest-signal passages (containing concrete empirical data, benchmark tables, and conclusions) are extracted and delivered to the evidence extractor, reducing prompt token bloat by 70%.", bullet_style))

    story.append(Paragraph("4.5 Phase 3: Evidence Validation & Iterative Feedback (Planned for End-Term)", h2_style))
    story.append(Paragraph("Phase 3 constitutes our primary development milestone for Major Project Part 2. The Evidence Validator will enforce strict claim-to-evidence grounding by auditing extracted claims character-for-character against raw full-text papers to eliminate subtle hallucinations. It will compute an Evidence Sufficiency Scorecard checking whether counter-evidence quotas and quantitative requirements are met. When deficiencies are flagged, the agent will autonomously formulate targeted re-search queries and iterate until sufficient evidence is assembled.", body_style))

    story.append(Paragraph("4.6 Phase 4: Calibrated Synthesis & Report Generation (Planned for End-Term)", h2_style))
    story.append(Paragraph("Phase 4 will synthesize validated evidence into comprehensive academic research reports. It will implement epistemic confidence calibration (scoring conclusions from 0.0 to 1.0 based on peer-reviewed consensus and sample sizes), assign deterministic numerical citation anchors ([1], [2]), and integrate WeasyPrint for direct headless PDF compilation.", body_style))

    # -------------------------------------------------------------
    # SECTION 5: WORKING MODEL & IMPLEMENTATION DELIVERABLES
    # -------------------------------------------------------------
    story.append(Paragraph("5. Working Model & Implementation Deliverables", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("5.1 Implemented Software Modules", h2_style))
    story.append(Paragraph("All Phase 1 and Phase 2 modules have been fully implemented in Python and committed to the repository (<code>branch: main</code>). The codebase is organized as follows:", body_style))

    modules_pdf_data = [
        [Paragraph("Module File", cell_hdr_style), Paragraph("Phase", cell_hdr_style), Paragraph("Functional Responsibility", cell_hdr_style)],
        [Paragraph("<font face='Courier'>planner/planner.py</font>", cell_body_style), Paragraph("Phase 1 (Completed)", cell_body_center), Paragraph("Domain detection, sub-question decomposition, hypothesis generation, and data/research_plan.json contract formulation.", cell_body_style)],
        [Paragraph("<font face='Courier'>search_agent/search_engine.py</font>", cell_body_style), Paragraph("Phase 2 (Completed)", cell_body_center), Paragraph("Unified asynchronous discovery layer querying Tavily, OpenAlex, and Semantic Scholar with rate-limit resilience.", cell_body_style)],
        [Paragraph("<font face='Courier'>search_agent/sources.py</font>", cell_body_style), Paragraph("Phase 2 (Completed)", cell_body_center), Paragraph("Multi-key deduplication resolving DOIs, arXiv IDs, canonical URLs, and fuzzy title matching.", cell_body_style)],
        [Paragraph("<font face='Courier'>search_agent/semantic_indexer.py</font>", cell_body_style), Paragraph("Phase 2 (Completed)", cell_body_center), Paragraph("6-step IR engine: stop-word filtering, Porter stemmer, BM25 inverted index, vector embeddings, cosine ranking, and PDF sliding-window chunker.", cell_body_style)],
        [Paragraph("<font face='Courier'>search_agent/content_retriever.py</font>", cell_body_style), Paragraph("Phase 2 (Completed)", cell_body_center), Paragraph("Full-text arXiv PDF download and parsing via pypdf.", cell_body_style)],
        [Paragraph("<font face='Courier'>search_agent/evidence_extractor.py</font>", cell_body_style), Paragraph("Phase 2 (Completed)", cell_body_center), Paragraph("Passage-level empirical fact, quote, and quantitative finding extraction.", cell_body_style)],
        [Paragraph("<font face='Courier'>demo_semantic_pipeline.py</font>", cell_body_style), Paragraph("Verification", cell_body_center), Paragraph("Standalone interactive terminal verification script visualizing all 7 stages of indexing and chunking.", cell_body_style)],
    ]
    mod_pdf_table = Table(modules_pdf_data, colWidths=[150, 100, 240])
    mod_pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F4F7F9"), colors.white]),
    ]))
    story.append(mod_pdf_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph("5.2 Interactive Verification CLI & Offline Demo Harness", h2_style))
    story.append(Paragraph("To facilitate rigorous demonstration during academic evaluations, ARA provides two distinct execution modes:", body_style))
    story.append(Paragraph("<b>1. Interactive Live CLI (main.py):</b> A terminal interface built with rich, featuring animated progress bars, live provider status indicators, and streaming search metrics.", num_style))
    story.append(Paragraph("<b>2. Interactive Semantic Pipeline Demo (demo_semantic_pipeline.py):</b> An isolated verification script that demonstrates raw text tokenization, stop-word stripping, Porter stemming roots, BM25 inverted indexing, Gemini dense vector cosine similarity, and 15-page PDF passage chunking in real time.", num_style))

    story.append(Paragraph("5.3 Unit Testing & Engineering Validation (170 Test Cases)", h2_style))
    story.append(Paragraph("The entire repository is validated under an automated test suite executed via <code>pytest</code>. A total of <b>170 unit tests pass cleanly with 100% regression stability</b>:", body_style))
    story.append(Paragraph("• <b>tests/test_semantic_indexer.py (7 tests):</b> Validates stop-word removal, Porter stemmer invariance, BM25 term weighting, cosine similarity calculation, prompt-specific re-ranking, and sliding-window passage chunking.", bullet_style))
    story.append(Paragraph("• <b>tests/test_phase2_completion.py (18 tests):</b> Tests multi-provider search connectors, OpenAlex query sanitization, and fallback triggers.", bullet_style))
    story.append(Paragraph("• <b>tests/test_cli_ui.py (18 tests):</b> Tests terminal rendering, progress bars, and status formatting.", bullet_style))
    story.append(Paragraph("• <b>tests/test_end_to_end_research_eval.py (28 tests):</b> Full pipeline integration and schema compliance tests.", bullet_style))

    # -------------------------------------------------------------
    # SECTION 6: EXPERIMENTAL RESULTS & PERFORMANCE ANALYSIS
    # -------------------------------------------------------------
    story.append(Paragraph("6. Experimental Results & Performance Analysis", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("6.1 Empirical Retrieval & Deduplication Precision", h2_style))
    story.append(Paragraph("The system was evaluated against complex academic research prompts. During benchmark execution on open scientific questions, the discovery engine harvested <b>539 gross candidate sources</b> across Tavily, OpenAlex, and Semantic Scholar.", body_style))
    story.append(Paragraph("Our multi-key deduplication module processed the gross candidate pool, matching digital object identifiers, arXiv preprint identifiers, and canonical URL strings. The algorithm merged 42 redundant records, retaining <b>497 unique academic sources</b>, representing a deduplication efficiency of <b>92.2%</b>.", body_style))

    story.append(Paragraph("6.2 Two-Stage Optimization Benchmarks", h2_style))
    story.append(Paragraph("In naive vector-retrieval architectures, generating dense vector embeddings for 500 candidate documents requires 500 individual embedding API calls, inducing high latency and risking HTTP 429 rate limits. Under our two-stage filtering pipeline:", body_style))
    story.append(Paragraph("• <b>Stage 1 (BM25 Coarse Filter):</b> Evaluated locally on the CPU in <b>0.021 seconds</b>, reducing the 497 unique candidates to the top 35 candidates.", bullet_style))
    story.append(Paragraph("• <b>Stage 2 (Dense Re-Ranking):</b> Dense vector embeddings were generated solely for the top 35 candidates, reducing embedding API consumption by <b>93.0%</b>.", bullet_style))

    story.append(Paragraph("6.3 Comparative Analysis: Naive RAG vs. Proposed Architecture", h2_style))

    comp_pdf_data = [
        [Paragraph("Evaluation Metric", cell_hdr_style), Paragraph("Conventional RAG / Naive Search", cell_hdr_style), Paragraph("ARA Implemented Architecture (Mid-Term)", cell_hdr_style)],
        [Paragraph("<b>Data Ingestion Diversity</b>", cell_body_style), Paragraph("Single commercial search API (Google / Bing).", cell_body_style), Paragraph("<b>Tri-Provider:</b> Tavily (Web), OpenAlex (Scholarly Works), Semantic Scholar (Academic Graph).", cell_body_style)],
        [Paragraph("<b>Candidate Deduplication</b>", cell_body_style), Paragraph("Exact string matching on raw URLs only.", cell_body_style), Paragraph("<b>Multi-Key Hierarchical:</b> DOI → arXiv ID → Normalized URL → Fuzzy Title Matching.", cell_body_style)],
        [Paragraph("<b>Vector API Overhead</b>", cell_body_style), Paragraph("Computes vector embeddings across all 500+ candidates (High cost / latency).", cell_body_style), Paragraph("<b>Two-Stage Cascade:</b> BM25 narrows 500 to 35 on local CPU; saves <b>>90% API calls</b>.", cell_body_style)],
        [Paragraph("<b>Context Degradation<br/>(\"Lost in Middle\")</b>", cell_body_style), Paragraph("Stuffs entire 15-page unsegmented PDFs into LLM prompt (10k+ tokens).", cell_body_style), Paragraph("<b>Sliding-Window Chunking:</b> 350-word window (50 overlap) extracts top 5 focused empirical passages.", cell_body_style)],
        [Paragraph("<b>Portability & Dependencies</b>", cell_body_style), Paragraph("Heavy compiled dependencies (NLTK, spaCy, C++ tokenizers).", cell_body_style), Paragraph("<b>Pure-Python Portability:</b> Custom Porter stemmer & BM25 with zero native binary requirements.", cell_body_style)],
        [Paragraph("<b>Engineering Verification</b>", cell_body_style), Paragraph("Ad-hoc script execution.", cell_body_style), Paragraph("<b>170 Passing Unit Tests</b> with isolated CLI verification demo (demo_semantic_pipeline.py).", cell_body_style)],
    ]
    comp_pdf_table = Table(comp_pdf_data, colWidths=[125, 160, 205])
    comp_pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F4F7F9"), colors.white]),
    ]))
    story.append(comp_pdf_table)
    story.append(Spacer(1, 6))

    # -------------------------------------------------------------
    # SECTION 7: CONCLUSION & FUTURE ROADMAP
    # -------------------------------------------------------------
    story.append(Paragraph("7. Conclusion & Future Roadmap (Phases 3 & 4)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    story.append(Paragraph("7.1 Conclusion of Mid-Term Milestone", h2_style))
    story.append(Paragraph("For the Mid-Term Evaluation milestone, the foundational planning, multi-provider discovery, and semantic indexing stages (Phases 1 and 2) of the Autonomous Research Agent have been fully designed, implemented, and empirically validated. The system successfully structures open-ended research topics into formal hypothesis contracts, concurrently harvests candidates across web and scholarly repositories, eliminates redundant citations via multi-key deduplication, reduces embedding overhead by >90% through two-stage BM25 filtering, and overcomes \"Lost in the Middle\" context degradation using deep sliding-window passage chunking. The codebase maintains high engineering standards with 170 automated unit tests passing cleanly.", body_style))

    story.append(Paragraph("7.2 Future Roadmap for Major Project Part 2 (End-Term)", h2_style))
    story.append(Paragraph("The remaining project lifecycle will focus on implementing Phases 3 and 4 to complete the autonomous research loop:", body_style))
    story.append(Paragraph("<b>1. Natural Language Inference (NLI) Validation Layer (Phase 3):</b> Implement an automated claim validation engine that classifies extracted claims into Entailment, Contradiction, or Neutral against raw source text, flagging contradictory findings between opposing scientific papers.", num_style))
    story.append(Paragraph("<b>2. Autonomous Iterative Re-Search Loop (Phase 3):</b> Build an evidence sufficiency evaluation scorecard. If the agent detects an absence of quantitative findings or counter-evidence, it will autonomously formulate targeted queries and trigger iterative search rounds prior to synthesis.", num_style))
    story.append(Paragraph("<b>3. Calibrated Epistemic Report Synthesis (Phase 4):</b> Develop a calibrated synthesis engine that assigns formal confidence metrics (High, Moderate, Inconclusive) and deterministic citations [1], [2] linking directly to the bibliography.", num_style))
    story.append(Paragraph("<b>4. Direct Headless PDF Compilation (Phase 4):</b> Integrate WeasyPrint into the report pipeline to directly compile publication-grade, paginated PDF documents from the final synthesis.", num_style))
    story.append(Paragraph("<b>5. Multi-Hop Citation Graph Traversal:</b> Leverage the Semantic Scholar Academic Graph API to traverse forward citations (newest breakthroughs) and backward references (foundational literature) from central discovered papers.", num_style))

    # -------------------------------------------------------------
    # SECTION 8: REFERENCES
    # -------------------------------------------------------------
    story.append(Paragraph("8. References", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#1B365D"), spaceBefore=1, spaceAfter=6))

    references = [
        "<b>Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024).</b> <i>Self-RAG: Learning to retrieve, generate, and critique through self-reflection</i>. In Proceedings of the Twelfth International Conference on Learning Representations (ICLR 2024). https://openreview.net/forum?id=hSyW5g00v8",
        "<b>Kinney, R., et al. (2023).</b> <i>The Semantic Scholar Open Research Corpus</i>. Allen Institute for AI. arXiv:2301.10140. https://arxiv.org/abs/2301.10140",
        "<b>Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D. (2020).</b> <i>Retrieval-augmented generation for knowledge-intensive NLP tasks</i>. Advances in Neural Information Processing Systems (NeurIPS 2020), 33, 9459–9474.",
        "<b>Li, Y., et al. (2025).</b> <i>A Survey of RAG-Reasoning Systems in Large Language Models</i>. Findings of the Association for Computational Linguistics: EMNLP 2025, 12120–12145. https://doi.org/10.18653/v1/2025.findings-emnlp.648",
        "<b>Liu, N. F., Gardner, M., Belinkov, Y., Peters, M. E., & Koh, P. W. (2024).</b> <i>Lost in the Middle: How Language Models Use Long Contexts</i>. Transactions of the Association for Computational Linguistics, 12, 157–173. https://doi.org/10.1162/tacl_a_00638",
        "<b>Park, J. S., O’Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023).</b> <i>Generative agents: Interactive simulacra of human behavior</i>. In Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST ’23). https://doi.org/10.1145/3586183.3606763",
        "<b>Porter, M. F. (1980).</b> <i>An algorithm for suffix stripping</i>. Program: Electronic Library and Information Systems, 14(3), 130–137. https://doi.org/10.1108/eb046814",
        "<b>Priem, J., Piwowar, H., & Orr, R. (2022).</b> <i>OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts</i>. arXiv:2205.01833. https://arxiv.org/abs/2205.01833",
        "<b>Robertson, S., & Zaragoza, H. (2009).</b> <i>The Probabilistic Relevance Framework: BM25 and Beyond</i>. Foundations and Trends in Information Retrieval, 3(4), 333–389. https://doi.org/10.1561/1500000019",
        "<b>Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., Cancedda, N., & Scialom, T. (2023).</b> <i>Toolformer: Language models can teach themselves to use tools</i>. Advances in Neural Information Processing Systems (NeurIPS 2023), 36.",
        "<b>Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023).</b> <i>Reflexion: Language agents with verbal reinforcement learning</i>. Advances in Neural Information Processing Systems (NeurIPS 2023), 36.",
        "<b>Singh, A., Ehtesham, A., Kumar, S., Khoei, T. T., & Vasilakos, A. V. (2025).</b> <i>Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG</i>. arXiv:2501.09136. https://arxiv.org/abs/2501.09136",
        "<b>Wang, L., et al. (2024).</b> <i>A Survey on Large Language Model Based Autonomous Agents</i>. Frontiers of Computer Science, 18, Article 186345. https://doi.org/10.1007/s11704-024-40231-1",
        "<b>Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023).</b> <i>ReAct: Synergizing reasoning and acting in language models</i>. In Proceedings of the Eleventh International Conference on Learning Representations (ICLR 2023). https://arxiv.org/abs/2210.03629"
    ]

    for idx, ref in enumerate(references, start=1):
        ref_text = f"[{idx}] {ref}"
        story.append(Paragraph(ref_text, ref_style))

    # Build PDF with dynamic NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF document saved successfully to {pdf_path}")


# -------------------------------------------------------------
# PART 3: BUILD HTML DOCUMENT
# -------------------------------------------------------------
def build_html_document(html_path):
    print(f"Generating HTML document: {html_path}...")
    import markdown
    with open("reports/mid_term_evaluation_report_upes.md", "r", encoding="utf-8") as f:
        md_text = f.read()
    html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])
    css_styles = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.65;
        color: #24292f;
        max-width: 900px;
        margin: 40px auto;
        padding: 0 24px;
        background-color: #ffffff;
    }
    h1 {
        color: #0b2545;
        border-bottom: 2px solid #0056b3;
        padding-bottom: 8px;
        margin-top: 36px;
    }
    h2 {
        color: #134074;
        margin-top: 26px;
    }
    h3 {
        color: #1d4e89;
        margin-top: 20px;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 22px 0;
        font-size: 0.95em;
    }
    th, td {
        border: 1px solid #d0d7de;
        padding: 8px 14px;
        text-align: left;
    }
    th {
        background-color: #1b365d;
        color: #ffffff;
        font-weight: 600;
    }
    tr:nth-child(even) {
        background-color: #f6f8fa;
    }
    pre {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 16px;
        overflow-x: auto;
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: 85%;
        line-height: 1.45;
    }
    code {
        background-color: rgba(175, 184, 193, 0.2);
        padding: 0.2em 0.4em;
        border-radius: 6px;
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: 88%;
    }
    hr {
        border: 0;
        height: 1px;
        background: #0056b3;
        margin: 28px 0;
    }
    blockquote {
        border-left: 4px solid #0056b3;
        margin: 0;
        padding-left: 16px;
        color: #555555;
    }
    """
    full_html = f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Major Project Mid-Term Evaluation Report - UPES</title>\n<style>{css_styles}</style>\n</head>\n<body>\n{html_body}\n</body>\n</html>"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"HTML document saved successfully to {html_path}")


# -------------------------------------------------------------
# MAIN DISPATCHER
# -------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)

    docx_target = os.path.abspath("reports/mid_term_evaluation_report_upes.docx")
    pdf_target = os.path.abspath("reports/mid_term_evaluation_report_upes.pdf")
    html_target = os.path.abspath("reports/mid_term_evaluation_report_upes.html")

    build_word_document(docx_target)
    build_pdf_document(pdf_target)
    build_html_document(html_target)

    # Also place copies in the workspace root for direct access
    root_docx = os.path.abspath("mid_term_evaluation_report_upes.docx")
    root_pdf = os.path.abspath("mid_term_evaluation_report_upes.pdf")
    root_html = os.path.abspath("mid_term_evaluation_report_upes.html")

    shutil.copyfile(docx_target, root_docx)
    shutil.copyfile(pdf_target, root_pdf)
    shutil.copyfile(html_target, root_html)

    print("All artifacts generated successfully:")
    print(f"  Word document: {docx_target}")
    print(f"  PDF document:  {pdf_target}")
    print(f"  HTML document: {html_target}")
    print(f"  Root copy docx:{root_docx}")
    print(f"  Root copy pdf: {root_pdf}")
    print(f"  Root copy html:{root_html}")

