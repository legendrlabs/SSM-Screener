from __future__ import annotations
import re
from typing import Dict, Tuple
from .models import Dilution
from .financial_review import visible_filing_text

NUM = r"(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|m|k)?"

def _to_num(raw, unit):
    try:
        n = float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0
    u = (unit or "").lower()
    if u in ("million", "m"):
        n *= 1_000_000
    elif u in ("thousand", "k"):
        n *= 1_000
    return n

def _first(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.I | re.S)
        if not m:
            continue
        value = _to_num(m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None)
        if value > 0:
            return value
    return 0.0

def heuristic_extract_dilution(text: str, common_shares: float = 0.0) -> Tuple[Dilution, list[str]]:
    t = visible_filing_text(text)
    clauses = re.split(r'(?<=[.;])\s+', t)
    def scope(pattern):
        return ' ; '.join(clause for clause in clauses if re.search(pattern, clause, re.I))
    d = Dilution(common_shares=common_shares, source="heuristic filing-text parser", confidence="low")
    warnings = []
    d.pre_funded_shares = _first([
        rf"pre[- ]funded warrants?\s+outstanding\s+(?:was|were|is|are|of|:)\s*{NUM}",
        rf"{NUM}\s+pre[- ]funded warrants?\s+(?:were|are)\s+outstanding",
        rf"pre[- ]funded warrants?.{{0,220}}?(?:purchase|acquire|representing|exercisable for|underlying).{{0,120}}?(?:up to\s+|an aggregate of\s+)?{NUM}\s+shares",
        rf"{NUM}\s+shares.{{0,160}}?pre[- ]funded warrants?",
        rf"{NUM}\s+pre[- ]funded warrants?.{{0,220}}?each.{{0,80}}?(?:one|1)\s+share",
    ], scope(r'pre[- ]funded'))
    # Mask the pre-funded label rather than removing the sentence: the same
    # sentence may also describe a distinct ordinary-warrant tranche.
    ordinary = re.sub(r'pre[- ]funded\s+warrants?', '_PRE_FUNDED_', t, flags=re.I)
    gap = r'(?:(?!_PRE_FUNDED_|;|\.\s).)'
    d.warrants_itm_shares = _first([
        rf"warrants?{gap}{{0,220}}?(?:purchase|acquire|exercisable for|underlying){gap}{{0,120}}?(?:up to\s+|an aggregate of\s+)?{NUM}\s+shares",
        rf"{NUM}\s+shares\s+(?:of common stock\s+)?(?:underlying|issuable upon exercise of)\s+(?:the\s+)?(?:new |common |series [a-z0-9-]+ )?warrants?",
    ], ordinary)
    d.converts_shares = _first([
        rf"convertible (?:notes?|debentures?).{{0,220}}?convertible into.{{0,120}}?{NUM}\s+shares",
        rf"{NUM}\s+shares.{{0,160}}?convertible (?:notes?|debentures?)",
    ], scope(r'convertible (?:notes?|debentures?)'))
    d.preferred_shares_equiv = _first([
        rf"preferred (?:stock|shares).{{0,220}}?convertible into.{{0,120}}?{NUM}\s+shares"
    ], scope(r'preferred (?:stock|shares)'))
    d.sbc_rsus_shares = _first([
        rf"(?:restricted stock units?|rsus).{{0,160}}?(?:representing|covering|for)?.{{0,80}}?{NUM}\s+shares"
    ], scope(r'restricted stock units?|\brsus\b'))
    material = bool(re.search(
        r"pre[- ]funded|warrant|convertible|preferred stock|preferred shares|\batm\b|at-the-market|equity line",
        t,
        re.I,
    ))
    extracted = sum([
        d.pre_funded_shares,
        d.warrants_itm_shares,
        d.converts_shares,
        d.preferred_shares_equiv,
        d.sbc_rsus_shares,
    ])
    if material and extracted == 0:
        warnings.append("Material dilution language found but no reliable share quantity extracted.")
    checks = [
        (r'pre[- ]funded', d.pre_funded_shares, 'pre-funded warrants'),
        (r'\bwarrants?\b', d.warrants_itm_shares, 'ordinary warrants'),
        (r'convertible (?:notes?|debentures?)', d.converts_shares, 'convertible debt'),
        (r'preferred (?:stock|shares)', d.preferred_shares_equiv, 'preferred shares'),
    ]
    for pattern, quantity, label in checks:
        scope = ordinary if label == 'ordinary warrants' else t
        if re.search(pattern, scope, re.I) and quantity <= 0:
            warnings.append(f'Unresolved share quantity for {label}.')
    if not warnings and common_shares > 0:
        d.confidence = "medium"
    return d, warnings

def apply_override(d: Dilution, override: Dict) -> Dilution:
    if not override:
        return d
    fields = set(Dilution.__dataclass_fields__)
    for k, v in override.items():
        if k in fields and k not in {"source", "confidence"}:
            setattr(d, k, float(v) if isinstance(v, (int, float)) else v)
    if override.get("source"):
        d.source = override["source"]
    if override.get("confidence"):
        d.confidence = override["confidence"]
    return d
