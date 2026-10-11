import json
import re
from typing import Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field

from .claim_normalizer import NormalizedClaim


class NLIDirectionScore(BaseModel):
    premise_id: str
    hypothesis_id: str
    p_entailment: float = 0.0
    p_neutral: float = 0.0
    p_contradiction: float = 0.0
    primary_label: Literal["entailment", "neutral", "contradiction"] = "neutral"
    rationale: str = ""


class BidirectionalNLIResult(BaseModel):
    claim_a_id: str
    claim_b_id: str
    forward_ab: NLIDirectionScore
    backward_ba: NLIDirectionScore
    c_sym: float = 0.0  # Symmetric contradiction score
    d_sym: float = 0.0  # Directional asymmetry |P_AB^C - P_BA^C|
    is_asymmetric: bool = False
    verdict: Literal["CONTRADICTION", "ENTAILMENT", "NEUTRAL", "ASYMMETRIC_CONFLICT"] = "NEUTRAL"
    requires_divergence_analysis: bool = False


def _heuristic_nli(premise_text: str, hypothesis_text: str) -> NLIDirectionScore:
    """Fast deterministic heuristic NLI evaluator for offline testing and baseline verification."""
    p_lower = premise_text.lower()
    h_lower = hypothesis_text.lower()

    # Look for explicit opposing directional statements
    p_pos = bool(re.search(r"\b(improves?|increases?|outperforms?|superior|gains?|faster|higher)\b", p_lower))
    p_neg = bool(re.search(r"\b(degrades?|decreases?|fails?|inferior|slower|lower|bottleneck|drops?)\b", p_lower))
    h_pos = bool(re.search(r"\b(improves?|increases?|outperforms?|superior|gains?|faster|higher)\b", h_lower))
    h_neg = bool(re.search(r"\b(degrades?|decreases?|fails?|inferior|slower|lower|bottleneck|drops?)\b", h_lower))

    if (p_pos and h_neg) or (p_neg and h_pos):
        return NLIDirectionScore(
            premise_id="P",
            hypothesis_id="H",
            p_entailment=0.05,
            p_neutral=0.15,
            p_contradiction=0.80,
            primary_label="contradiction",
            rationale="Opposing semantic polarity detected between premise and hypothesis assertions."
        )
    elif (p_pos and h_pos) or (p_neg and h_neg):
        return NLIDirectionScore(
            premise_id="P",
            hypothesis_id="H",
            p_entailment=0.75,
            p_neutral=0.20,
            p_contradiction=0.05,
            primary_label="entailment",
            rationale="Congruent semantic polarity detected."
        )

    return NLIDirectionScore(
        premise_id="P",
        hypothesis_id="H",
        p_entailment=0.20,
        p_neutral=0.70,
        p_contradiction=0.10,
        primary_label="neutral",
        rationale="Insufficient shared polarity to assert entailment or contradiction."
    )


def evaluate_bidirectional_nli(
    claim_a: NormalizedClaim,
    claim_b: NormalizedClaim,
    gemini_client=None,
    model: str = "gemini-2.5-flash"
) -> BidirectionalNLIResult:
    """
    Run symmetric bidirectional Natural Language Inference:
    Evaluates:
      1. Premise A -> Hypothesis B
      2. Premise B -> Hypothesis A
    Calculates symmetric contradiction score C_sym and directional asymmetry D_sym.
    """
    text_a = f"{claim_a.outcome_variable}: {claim_a.verbatim_quote}"
    text_b = f"{claim_b.outcome_variable}: {claim_b.verbatim_quote}"

    if gemini_client is not None:
        try:
            prompt = f"""You are a precise Natural Language Inference (NLI) evaluator for scientific claims.
Evaluate the logical relationship between these two scientific assertions in BOTH directions.

ASSERTION A: "{text_a}"
ASSERTION B: "{text_b}"

Return ONLY valid JSON matching this exact structure:
{{
  "forward_ab": {{
    "p_entailment": 0.05,
    "p_neutral": 0.15,
    "p_contradiction": 0.80,
    "primary_label": "contradiction",
    "rationale": "Brief scientific justification."
  }},
  "backward_ba": {{
    "p_entailment": 0.05,
    "p_neutral": 0.15,
    "p_contradiction": 0.80,
    "primary_label": "contradiction",
    "rationale": "Brief scientific justification."
  }}
}}"""
            res = gemini_client.models.generate_content(model=model, contents=prompt)
            data = json.loads(res.text.strip())
            fwd = NLIDirectionScore(premise_id=claim_a.claim_id, hypothesis_id=claim_b.claim_id, **data["forward_ab"])
            bwd = NLIDirectionScore(premise_id=claim_b.claim_id, hypothesis_id=claim_a.claim_id, **data["backward_ba"])
        except Exception:
            fwd = _heuristic_nli(text_a, text_b)
            fwd.premise_id = claim_a.claim_id
            fwd.hypothesis_id = claim_b.claim_id
            bwd = _heuristic_nli(text_b, text_a)
            bwd.premise_id = claim_b.claim_id
            bwd.hypothesis_id = claim_a.claim_id
    else:
        fwd = _heuristic_nli(text_a, text_b)
        fwd.premise_id = claim_a.claim_id
        fwd.hypothesis_id = claim_b.claim_id
        bwd = _heuristic_nli(text_b, text_a)
        bwd.premise_id = claim_b.claim_id
        bwd.hypothesis_id = claim_a.claim_id

    # Compute symmetric metrics
    c_sym = round((fwd.p_contradiction + bwd.p_contradiction) / 2.0, 4)
    d_sym = round(abs(fwd.p_contradiction - bwd.p_contradiction), 4)
    is_asym = d_sym > 0.40

    # Categorize verdict
    if is_asym:
        verdict = "ASYMMETRIC_CONFLICT"
        req_div = True
    elif c_sym >= 0.65:
        verdict = "CONTRADICTION"
        req_div = True
    elif fwd.primary_label == "entailment" and bwd.primary_label == "entailment":
        verdict = "ENTAILMENT"
        req_div = False
    else:
        verdict = "NEUTRAL"
        req_div = False

    return BidirectionalNLIResult(
        claim_a_id=claim_a.claim_id,
        claim_b_id=claim_b.claim_id,
        forward_ab=fwd,
        backward_ba=bwd,
        c_sym=c_sym,
        d_sym=d_sym,
        is_asymmetric=is_asym,
        verdict=verdict,
        requires_divergence_analysis=req_div
    )

