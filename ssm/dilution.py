from __future__ import annotations
import re
from typing import Dict, Tuple
from .models import Dilution

NUM = r"(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|m|k)?"\nUSD = r"\\$\\s*(\\d[\\d,]*(?:\\.\\d+)?)\\s*(million|thousand|m|k)?"

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
    t = re.sub(r"\s+", " ", text or "")
    d = Dilution(common_shares=common_shares, source="heuristic filing-text parser", confidence="low")
    warnings = []

    d.pre_funded_shares = _first([
        rf"pre[- ]funded warrants?.{{0,180}}?(?:purchase|acquire|representing|exercisable for|underlying).{{0,100}}?{NUM}\s+shares",
        rf"{NUM}\s+shares.{{0,140}}?pre[- ]funded warrants?",
    ], t)
    d.warrants_itm_shares = _first([
        rf"warrants?.{{0,180}}?(?:purchase|acquire|exercisable for).{{0,100}}?{NUM}\s+shares"
    ], t)
    if d.pre_funded_shares > 0 and d.warrants_itm_shares == d.pre_funded_shares:
        d.warrants_itm_shares = 0.0

    d.converts_shares = _first([
        rf"convertible (?:notes?|debentures?).{{0,220}}?convertible into.{{0,120}}?{NUM}\s+shares",
        rf"{NUM}\s+shares.{{0,160}}?convertible (?:notes?|debentures?)",
    ], t)
    d.preferred_shares_equiv = _first([
        rf"preferred (?:stock|shares).{{0,220}}?convertible into.{{0,120}}?{NUM}\s+shares"
    ], t)
    d.sbc_rsus_shares = _first([
        rf"(?:restricted stock units?|rsus).{{0,160}}?(?:representing|covering|for)?.{{0,80}}?{NUM}\s+shares"
    ], t)
    d.atm_remaining_usd = _first([
        rf"{USD}.{{0,100}}?(?:remaining|remain(?:ed|s)?|available).{{0,140}}?(?:at-the-market|sales agreement)",
        rf"(?:at-the-market|sales agreement).{{0,180}}?{USD}.{{0,100}}?(?:remaining|remain(?:ed|s)?|available)",
    ], t)

    material = bool(re.search(
        r"pre[- ]funded|warrant|convertible|preferred stock|preferred shares|\batm\b|at-the-market|equity line",
        t,
        re.I,
    ))
    extracted_any = any(x > 0 for x in [
        d.pre_funded_shares,
        d.warrants_itm_shares,
        d.converts_shares,
        d.preferred_shares_equiv,
        d.sbc_rsus_shares,
        d.atm_remaining_usd,
    ])

    if material and not extracted_any:
        warnings.append("Material dilution language found but no reliable share quantity extracted.")
    elif common_shares > 0:
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
