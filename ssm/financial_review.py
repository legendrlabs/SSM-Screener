from __future__ import annotations
import re
from .models import Dilution

NOTE_PATTERNS = {
    "WARRANTS": r"\bwarrants?\b",
    "PRE_FUNDED": r"pre[- ]funded",
    "CONVERTIBLES": r"convertible (?:notes?|debentures?|preferred)",
    "PREFERRED": r"preferred stock|preferred shares",
    "ATM_EQUITY_LINE": r"at-the-market|\bATM\b|equity line|SEPA|ELOC",
    "STOCK_COMP": r"stock-based compensation|share-based compensation|restricted stock units?|\bRSUs\b",
    "GOING_CONCERN": r"going concern|substantial doubt",
    "RELATED_PARTY": r"related party|related-party",
    "SUBSEQUENT_EVENTS": r"subsequent events?",
    "COMMITMENTS_CONTINGENCIES": r"commitments? and contingencies|contingencies",
    "DEBT": r"notes? payable|credit facility|term loan|debt",
    "STOCKHOLDERS_EQUITY": r"stockholders['’]? equity|shareholders['’]? equity",
}

DILUTION_FIELDS = [
    "pre_funded_shares",
    "options_itm_shares",
    "warrants_itm_shares",
    "warrants_otm_shares",
    "converts_shares",
    "preferred_shares_equiv",
    "merger_consideration_shares",
    "sbc_rsus_shares",
    "atm_remaining_usd",
    "warrant_exercise_cash_usd",
]

def financial_note_hits(text: str) -> list[str]:
    t = re.sub(r"\s+", " ", text or "")
    return [label for label, pattern in NOTE_PATTERNS.items() if re.search(pattern, t, re.I)]

def conservative_merge_dilution(current: Dilution, financial: Dilution) -> Dilution:
    """
    Merge event-filing and 10-Q/10-K cap-table evidence conservatively.

    Share-equivalent categories use max(), not addition, because the same
    instrument is often disclosed in both filings. This may overstate stale
    instruments, but avoids double counting while preserving a conservative
    screening bias.
    """
    out = Dilution(
        common_shares=max(current.common_shares, financial.common_shares),
        source=" + ".join(x for x in [current.source, financial.source] if x),
        confidence="medium" if "medium" in {current.confidence, financial.confidence} else "low",
    )
    if "high" in {current.confidence, financial.confidence}:
        out.confidence = "high"
    for field in DILUTION_FIELDS:
        setattr(out, field, max(float(getattr(current, field, 0) or 0), float(getattr(financial, field, 0) or 0)))
    return out
