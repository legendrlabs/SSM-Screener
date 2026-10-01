from __future__ import annotations
import re
from typing import Dict, Tuple
from .models import Dilution

NUM = r"([\d,.]+)\s*(million|thousand|m|k)?"

def _to_num(raw, unit):
    n = float(raw.replace(",", "")); u=(unit or "").lower()
    if u in ("million","m"): n *= 1_000_000
    elif u in ("thousand","k"): n *= 1_000
    return n

def _first(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.I | re.S)
        if m: return _to_num(m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None)
    return 0.0

def heuristic_extract_dilution(text: str, common_shares: float = 0.0) -> Tuple[Dilution, list[str]]:
    t = re.sub(r"\s+", " ", text or "")
    d = Dilution(common_shares=common_shares, source="heuristic filing-text parser", confidence="low")
    warnings=[]
    d.pre_funded_shares = _first([rf"pre[- ]funded warrants?.{{0,160}}?(?:purchase|acquire|representing).{{0,80}}?{NUM}\s+shares", rf"{NUM}\s+shares.{{0,120}}?pre[- ]funded warrants?"], t)
    d.warrants_itm_shares = _first([rf"warrants?.{{0,120}}?(?:purchase|acquire).{{0,80}}?{NUM}\s+shares"], t)
    d.converts_shares = _first([rf"convertible (?:notes?|debentures?).{{0,180}}?convertible into.{{0,80}}?{NUM}\s+shares"], t)
    d.preferred_shares_equiv = _first([rf"preferred stock.{{0,180}}?convertible into.{{0,80}}?{NUM}\s+shares"], t)
    d.sbc_rsus_shares = _first([rf"(?:restricted stock units?|rsus).{{0,120}}?{NUM}\s+shares"], t)
    material = bool(re.search(r"pre[- ]funded|warrant|convertible|preferred stock|\batm\b|at-the-market|equity line|\bsepa\b|\beloc\b", t, re.I))
    extracted = sum([d.pre_funded_shares,d.warrants_itm_shares,d.converts_shares,d.preferred_shares_equiv,d.sbc_rsus_shares])
    if material and extracted == 0:
        warnings.append("Material dilution language found but no reliable share quantity extracted.")
    elif extracted > 0 and common_shares > 0:
        d.confidence="medium"
    elif common_shares > 0:
        d.confidence="medium"
    return d, warnings

def apply_override(d: Dilution, override: Dict) -> Dilution:
    if not override: return d
    fields=set(Dilution.__dataclass_fields__)
    for k,v in override.items():
        if k in fields and k not in {"source","confidence"}: setattr(d,k,float(v) if isinstance(v,(int,float)) else v)
    if override.get("source"): d.source=override["source"]
    if override.get("confidence"): d.confidence=override["confidence"]
    return d
