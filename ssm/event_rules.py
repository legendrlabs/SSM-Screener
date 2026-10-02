from __future__ import annotations
import re
from typing import Tuple
from .financial_review import visible_filing_text


def operative_text(text: str) -> str:
    """Read the transaction narrative, excluding cover and cautionary boilerplate."""
    t = visible_filing_text(text)
    item = re.search(r'\bItem\s+(?:1\.01|2\.01|7\.01|8\.01)\b', t, re.I)
    if item:
        t = t[item.start():]
    t = re.split(r'\bItem\s+9\.01\b|\bSIGNATURES?\b|Forward[- ]Looking Statements|Certain statements contained in', t, maxsplit=1, flags=re.I)[0]
    return t[:30000]

EVENT_KEYWORDS = {
    "MERGER_REVERSE_MERGER": [r"\bmerger agreement\b", r"\breverse merger\b", r"\bbusiness combination\b", r"\bmerger consideration\b"],
    "ASSET_SALE_ACQUISITION": [r"\bacquisition\b", r"\bacquire[sd]?\b", r"\basset sale\b", r"\bdisposition\b", r"\bpurchase agreement\b"],
    "STRATEGIC_INVESTMENT_PIPE": [r"\bstrategic investment\b", r"\bprivate placement\b", r"\bpipe\b", r"\bsecurities purchase agreement\b"],
    "DEBT_RESTRUCTURING": [r"\bredemption\b", r"\brefinanc", r"\bdebt repayment\b", r"\bdebt extinguish", r"\bnotes? repaid\b"],
    "LARGE_CONTRACT": [r"\bmaster services agreement\b", r"\bpurchase order\b", r"\bcontract value\b", r"\bgovernment contract\b", r"\btake-or-pay\b"],
    "BUSINESS_PIVOT": [r"\bstrategic pivot\b", r"\btransition(?:ing)? to\b", r"\brebrand", r"\bname change\b", r"\bai infrastructure\b", r"\bdata center\b", r"\bgpu\b", r"\bbitcoin treasury\b", r"\brobotics\b"],
    "LISTING_CAPITAL_STRUCTURE": [r"\breverse stock split\b", r"\bminimum bid price\b", r"\bnasdaq deficiency\b", r"\bwarrant inducement\b"]
}

def classify_event(text: str) -> Tuple[str, int, str]:
    t = operative_text(text).lower()
    terminal = bool(re.search(r'(?:separate existence.{0,60}ceased|ceased to exist as a separate entity)', t)
                    and re.search(r'converted into.{0,140}(?:cash|\$)|no longer.{0,50}(?:listed|traded)', t))
    anchor = None
    if terminal:
        anchor = 'TERMINAL_MERGER'
    elif re.search(r'(?:has |have |company |parties )terminated.{0,40}(?:merger|business combination) agreement|(?:merger|business combination) agreement (?:was|has been) terminated', t[:2500]):
        anchor = 'MERGER_TERMINATED'
    elif re.search(r'liquidating distribution|liquidation activities|plan of sale and liquidation', t):
        anchor = 'LIQUIDATION_DISTRIBUTION'
    elif re.search(r'merger agreement|agreement and plan of merger|to be acquired', t) and re.search(r'contingent value right|\bcvr\b', t):
        anchor = 'MERGER_CASH_CVR'
    elif re.search(r'(?:entered into|amends and restates|executed).{0,300}(?:credit agreement|loan agreement)', t):
        anchor = 'DEBT_RESTRUCTURING'
    elif re.search(r'exchange agreement', t) and re.search(r'senior notes|principal amount|debt', t):
        anchor = 'DEBT_RESTRUCTURING'
    elif re.search(r'(?:entered into|signed|executed).{0,180}asset purchase agreement|completed.{0,80}(?:sale|acquisition)', t):
        anchor = 'ASSET_SALE_ACQUISITION'
    elif re.search(r'(?:forward|reverse) (?:stock|share) split', t):
        anchor = 'LISTING_CAPITAL_STRUCTURE'
    elif re.search(r'manufacturing.{0,70}agreement|supply agreement|contract extension', t):
        anchor = 'LARGE_CONTRACT'
    scores = {}
    for label, pats in EVENT_KEYWORDS.items():
        hits = sum(bool(re.search(p, t)) for p in pats)
        if hits:
            scores[label] = hits
    label = anchor or (max(scores, key=scores.get) if scores else "OTHER")
    proof = 0
    nonbinding = bool(re.search(r"\bnon[- ]binding\b|\bletter of intent\b|\bpreliminary\b|\bexplor(?:e|ing)\b|\bconsidering\b", t))
    if nonbinding:
        proof = 1
    else:
        if re.search(r"\bdefinitive agreement\b|\bbinding agreement\b|\bentered into\b|\bexecuted\b|\bsigned\b", t): proof = max(proof, 2)
        for sentence in re.split(r'(?<=[.;])\s+', t):
            if re.search(r'\bclosed\b|\bconsummated\b|\bcompleted\b|\bfunded\b|\beffected\b', sentence) and not re.search(r'\bif\b|\bnot\b|\bwill\b|\bwould\b|\bmay\b|\bexpected\b|\banticipat\w*\b|\bsubject to\b|\bupon\b', sentence):
                proof = max(proof, 3)
        if re.search(r"\bgo-live\b|\bcommenced operations\b|\brevenue recognized\b|\bcommercial operations\b|\bplaced into service\b", t): proof = max(proof, 4)
    if terminal:
        proof = 3
    return label, proof, label.replace("_", " ").title() if label != "OTHER" else ""
