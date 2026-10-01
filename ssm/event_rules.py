from __future__ import annotations
import re
from typing import Tuple

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
    t = re.sub(r"\s+", " ", text or "").lower()
    scores = {}
    for label, pats in EVENT_KEYWORDS.items():
        hits = sum(bool(re.search(p, t)) for p in pats)
        if hits:
            scores[label] = hits
    label = max(scores, key=scores.get) if scores else "OTHER"
    proof = 0
    nonbinding = bool(re.search(r"\bnon[- ]binding\b|\bletter of intent\b|\bpreliminary\b|\bexplor(?:e|ing)\b|\bconsider(?:ing|ation)\b", t))
    if nonbinding:
        proof = 1
    else:
        if re.search(r"\bdefinitive agreement\b|\bbinding agreement\b|\bentered into\b|\bexecuted\b|\bsigned\b", t): proof = max(proof, 2)
        if re.search(r"\bclosed\b|\bclosing completed\b|\bconsummated\b|\bfunded\b|\breceived\b|\bacquisition was completed\b", t): proof = max(proof, 3)
        if re.search(r"\bgo-live\b|\bcommenced operations\b|\brevenue recognized\b|\bcommercial operations\b|\bplaced into service\b", t): proof = max(proof, 4)
    return label, proof, label.replace("_", " ").title() if label != "OTHER" else ""
