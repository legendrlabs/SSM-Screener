from __future__ import annotations
import csv, json, os
from pathlib import Path
from .models import Candidate, Dilution
from .event_rules import classify_event
from .dilution import heuristic_extract_dilution, apply_override
from .gates import evaluate_gates
from .scoring import score_candidate, bucket_candidate
from .providers.sec import SecClient, latest_fact_value, filing_risk_flags
from .providers.market import market_snapshot, market_snapshots
from .financial_review import financial_note_hits, conservative_merge_dilution, cover_page_common_shares

OFFERING_FORMS = {"S-1", "S-3", "424B3", "424B5"}
OWNERSHIP_FORMS = {"SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"}
PROXY_FORMS = {"DEF 14A", "PRE 14A"}

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_watchlist(path):
    p = Path(path)
    if not p.exists():
        return set()
    with p.open(encoding="utf-8") as f:
        return {(r.get("ticker") or "").strip().upper() for r in csv.DictReader(f) if (r.get("ticker") or "").strip()}

def _ticker_map(sec):
    by_cik, by_ticker = {}, {}
    for x in sec.exchange_tickers():
        cik = str(int(x.get("cik")))
        t = str(x.get("ticker", "")).upper()
        rec = {"ticker": t, "name": x.get("name", ""), "exchange": x.get("exchange", ""), "cik": cik}
        by_cik[cik] = rec
        by_ticker[t] = rec
    return by_cik, by_ticker

def _common_shares(facts):
    v = latest_fact_value(facts, "EntityCommonStockSharesOutstanding")
    try:
        return float(v) if v else 0.0
    except Exception:
        return 0.0

def _items(filing):
    return {x.strip() for x in (filing.get("items") or "").replace(";", ",").split(",") if x.strip()}

def _metadata_event(filing):
    form, items = filing.get("form", ""), _items(filing)
    if form == "8-K":
        rules = [
            ("2.01", "ASSET_SALE_ACQUISITION", 3),
            ("5.01", "CONTROL_CHANGE", 3),
            ("3.02", "STRATEGIC_INVESTMENT_PIPE", 2),
            ("2.03", "FINANCING_DEBT", 2),
            ("1.01", "MATERIAL_DEFINITIVE_AGREEMENT", 2),
            ("5.03", "LISTING_CAPITAL_STRUCTURE", 1),
            ("5.07", "CORPORATE_ACTION", 1),
            ("8.01", "OTHER", 1),
        ]
        for item, label, proof in rules:
            if item in items:
                return label, proof, f"8-K Item {item} metadata"
        return "OTHER", 0, "8-K metadata"
    if form in OFFERING_FORMS:
        return "SECURITIES_OFFERING", 2, f"{form} financing filing"
    if form in OWNERSHIP_FORMS:
        return "OWNERSHIP_CHANGE", 1, f"{form} ownership filing"
    if form in PROXY_FORMS:
        return "CORPORATE_ACTION", 1, f"{form} proxy filing"
    return "OTHER", 0, form

def _material(filing, cfg):
    if filing.get("form") != "8-K":
        return filing.get("form") in set(cfg["event_forms"])
    return bool(_items(filing) & set(cfg["material_8k_items"]))

def _watch_filing(sec, cik, event_forms):
    r = sec.submissions(cik).get("filings", {}).get("recent", {})
    n = len(r.get("form", []))
    for i in range(n):
        form = r.get("form", [""] * n)[i]
        if form not in event_forms:
            continue
        filed = r.get("filingDate", [""] * n)[i]
        acc = r.get("accessionNumber", [""] * n)[i]
        doc = r.get("primaryDocument", [""] * n)[i]
        items = r.get("items", [""] * n)[i] if i < len(r.get("items", [])) else ""
        return {
            "cik": cik, "form": form, "filed": filed, "accession": acc,
            "items": items or "", "primary_document": doc,
            "filename": f"edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}",
            "source": "submissions-watchlist",
        }
    return None

def build_candidate(sec, meta, filing, overrides, cfg, snapshot=None):
    c = Candidate(ticker=meta["ticker"], name=meta["name"], exchange=meta["exchange"], cik=meta["cik"])
    c.latest_event_date = filing.get("filed")
    c.latest_event_form = filing.get("form")
    c.latest_event_accession = filing.get("accession") or filing.get("filename")
    c.event_type, c.event_proof, c.event_summary = _metadata_event(filing)

    if snapshot:
        for k, v in snapshot.items():
            setattr(c, k, v)
    else:
        try:
            for k, v in market_snapshot(c.ticker).items():
                setattr(c, k, v)
        except Exception as e:
            c.data_warnings.append(f"Market data error: {e}")

    financial_record = None
    try:
        financial_record = sec.latest_financial_record(meta["cik"])
        if financial_record:
            c.latest_financial_filing_date = financial_record.get("filed")
            c.latest_financial_form = financial_record.get("form")
            c.latest_financial_accession = financial_record.get("accession")
        common = _common_shares(sec.companyfacts(meta["cik"]))
    except Exception as e:
        common = 0.0
        c.data_warnings.append(f"SEC facts error: {e}")

    c.dilution = apply_override(
        Dilution(common_shares=common, source="SEC companyfacts metadata precheck", confidence="low"),
        overrides.get(c.ticker, {}),
    )

    mc = c.basic_market_cap()
    if mc is not None and mc > cfg["market_cap_expand_max"]:
        c.gate_status = c.bucket = "REJECT"
        c.data_warnings.append("Market cap above expanded universe ceiling; filing body skipped.")
        c.priority_score = score_candidate(c)
        return c

    txt = ""
    try:
        if filing.get("filename"):
            txt = sec.submission_text(filing["filename"])
    except Exception as e:
        c.data_warnings.append(f"Filing-text retrieval error: {e}")

    if txt:
        label, proof, summary = classify_event(txt)
        if label != "OTHER":
            c.event_type = label
        c.event_proof = max(c.event_proof, proof)
        if summary:
            c.event_summary = summary
        for k, v in filing_risk_flags(txt).items():
            setattr(c, k, v)
        d, warnings = heuristic_extract_dilution(txt, common)
        c.dilution = apply_override(d, overrides.get(c.ticker, {}))
        c.data_warnings.extend(warnings)
    elif c.dilution.confidence != "high":
        c.data_warnings.append("Event filing body unavailable; dilution verification incomplete.")

    # Mandatory second pass: read the latest 10-Q/10-K body for notes that often
    # contain warrants, converts, preferreds, SBC, related-party items, liquidity
    # language and subsequent events. Event discovery and financial validation are
    # deliberately separate stages.
    financial_text = ""
    if financial_record and financial_record.get("filename"):
        try:
            financial_text = sec.submission_text(financial_record["filename"])
            c.financial_review_complete = True
            c.financial_note_hits = financial_note_hits(financial_text)
            cover_common = cover_page_common_shares(financial_text)
            if common <= 0 and cover_common > 0:
                common = cover_common
                c.dilution.common_shares = cover_common
                c.data_warnings.append("Common shares resolved from latest 10-Q/10-K cover page.")
            elif common > 0 and cover_common > 0:
                ratio = cover_common / common
                if ratio < 0.8 or ratio > 1.25:
                    c.data_warnings.append(
                        f"Companyfacts vs cover-page shares differ materially ({common:.0f} vs {cover_common:.0f})."
                    )
            for k, v in filing_risk_flags(financial_text).items():
                setattr(c, k, bool(getattr(c, k)) or bool(v))
            fin_dilution, fin_warnings = heuristic_extract_dilution(financial_text, common)
            fin_dilution.source = f"{financial_record.get('form')} second-pass filing parser"
            c.dilution = conservative_merge_dilution(c.dilution, fin_dilution)
            c.dilution = apply_override(c.dilution, overrides.get(c.ticker, {}))
            c.data_warnings.extend(fin_warnings)
        except Exception as e:
            c.data_warnings.append(f"Financial filing second-pass error: {e}")
    else:
        c.data_warnings.append("Latest 10-Q/10-K primary document unavailable.")

    c.gate_status, reasons = evaluate_gates(c, cfg)
    c.data_warnings.extend(reasons)
    c.priority_score = score_candidate(c)
    c.bucket = bucket_candidate(c)
    return c

def scan(days=7, config_path="config/default.json", watchlist_path="config/watchlist.csv", overrides_path="config/overrides.json"):
    cfg = load_json(config_path)
    overrides = load_json(overrides_path) if Path(overrides_path).exists() else {}
    sec = SecClient()
    by_cik, by_ticker = _ticker_map(sec)
    latest = {}

    for raw in sec.recent_filings(days, cfg["event_forms"]):
        meta = by_cik.get(str(int(raw["cik"])))
        if not meta or meta["exchange"] not in cfg["exchanges"]:
            continue
        try:
            filing = sec.enrich_filing(meta["cik"], raw)
        except Exception:
            filing = raw
        if not _material(filing, cfg):
            continue
        t = meta["ticker"]
        if t not in latest or (filing.get("filed") or "") > (latest[t].get("filed") or ""):
            latest[t] = filing

    event_forms = set(cfg["event_forms"])
    for t in load_watchlist(watchlist_path):
        if t in latest or t not in by_ticker:
            continue
        try:
            f = _watch_filing(sec, by_ticker[t]["cik"], event_forms)
            if f:
                latest[t] = f
        except Exception:
            pass

    snapshots = market_snapshots(list(latest)) if latest else {}
    out = []
    for t, filing in latest.items():
        try:
            out.append(build_candidate(sec, by_ticker[t], filing, overrides, cfg, snapshots.get(t)))
        except Exception as e:
            c = Candidate(ticker=t, name=by_ticker[t]["name"], exchange=by_ticker[t]["exchange"], cik=by_ticker[t]["cik"])
            c.data_warnings.append(f"Pipeline error: {e}")
            out.append(c)

    cfg["_sec_discovery_mode"] = sec.last_discovery_mode or os.getenv("SSM_SEC_DISCOVERY_MODE", "auto")
    out.sort(key=lambda c: (c.bucket == "A_RESEARCH_NOW", c.priority_score or -1), reverse=True)
    return out, cfg
