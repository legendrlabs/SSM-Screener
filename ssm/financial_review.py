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


def _cover_plain_text(text: str, max_chars: int = 60000) -> str:
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"&nbsp;|&#160;", " ", plain, flags=re.I)
    plain = re.sub(r"\s+", " ", plain).strip()
    head = plain[:max_chars]
    for marker in (
        r"\bPART\s+I\b",
        r"\bITEM\s+1[\.:]\s",
        r"\bPART\s+II\b",
    ):
        m = re.search(marker, head, re.I)
        if m and m.start() > 500:
            head = head[:m.start()]
            break
    return head

def cover_page_common_shares(text: str) -> float:
    """Resolve cover-page shares only; never scan notes/MD&A for this fallback."""
    plain = _cover_plain_text(text)

    class_values = {}
    # Common SEC cover-page wording: "N shares of Class A common stock ... outstanding".
    for outstanding in re.finditer(r"\boutstanding\b", plain, re.I):
        window = plain[max(0, outstanding.start() - 500):outstanding.end()]
        for m in re.finditer(
            r"(\d[\d,]*)\s+shares\s+of\s+(Class\s+[A-Z0-9-]+)\s+common stock",
            window,
            re.I,
        ):
            value = float(m.group(1).replace(",", ""))
            label = m.group(2).upper()
            class_values[label] = max(class_values.get(label, 0.0), value)
    if class_values:
        return sum(class_values.values())

    # Generic single-class cover wording.
    generic = []
    patterns = [
        r"(?:as of|on)\s+[^.]{0,120}?there (?:were|was)\s+(\d[\d,]*)\s+shares\s+of\s+(?:our\s+)?common stock[^.]{0,120}?outstanding",
        r"(\d[\d,]*)\s+shares\s+of\s+(?:our\s+)?common stock[^.]{0,180}?outstanding",
        r"common stock[^.]{0,180}?(\d[\d,]*)\s+shares[^.]{0,120}?outstanding",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, plain, re.I):
            generic.append(float(m.group(1).replace(",", "")))
    return max(generic) if generic else 0.0

def extract_atm_remaining_usd(text: str) -> float:
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"&nbsp;|&#160;", " ", plain, flags=re.I)
    plain = re.sub(r"\s+", " ", plain)
    amount = r"\$\s*(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|m|k)?"
    patterns = [
        rf"{amount}.{{0,100}}?(?:remaining|remain(?:ed|s)?|available).{{0,140}}?(?:at-the-market|sales agreement)",
        rf"(?:at-the-market|sales agreement).{{0,180}}?{amount}.{{0,100}}?(?:remaining|remain(?:ed|s)?|available)",
    ]
    values = []
    for pattern in patterns:
        for m in re.finditer(pattern, plain, re.I):
            raw = float(m.group(1).replace(",", ""))
            unit = (m.group(2) or "").lower()
            if unit in ("million", "m"):
                raw *= 1_000_000
            elif unit in ("thousand", "k"):
                raw *= 1_000
            values.append(raw)
    return max(values) if values else 0.0
