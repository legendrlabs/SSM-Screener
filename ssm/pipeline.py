from __future__ import annotations
import csv,json
from pathlib import Path
from .models import Candidate
from .event_rules import classify_event
from .dilution import heuristic_extract_dilution,apply_override
from .gates import evaluate_gates
from .scoring import score_candidate,bucket_candidate
from .providers.sec import SecClient,latest_fact_value,filing_risk_flags
from .providers.market import market_snapshot

def load_json(path):
    with open(path,encoding="utf-8") as f: return json.load(f)

def load_watchlist(path):
    p=Path(path); out=set()
    if not p.exists(): return out
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t=(r.get("ticker") or "").strip().upper()
            if t: out.add(t)
    return out

def _ticker_map(sec):
    by_cik={}; by_ticker={}
    for x in sec.exchange_tickers():
        cik=str(x.get("cik")); t=str(x.get("ticker","")).upper(); rec={"ticker":t,"name":x.get("name",""),"exchange":x.get("exchange",""),"cik":cik}; by_cik[str(int(cik))]=rec; by_ticker[t]=rec
    return by_cik,by_ticker

def _common_shares(facts):
    v=latest_fact_value(facts,"EntityCommonStockSharesOutstanding")
    try: return float(v) if v else 0.0
    except Exception: return 0.0

def build_candidate(sec,meta,filing,overrides,cfg):
    c=Candidate(ticker=meta["ticker"],name=meta["name"],exchange=meta["exchange"],cik=meta["cik"])
    c.latest_event_date=filing["filed"]; c.latest_event_form=filing["form"]; c.latest_event_accession=filing["filename"]
    txt=sec.submission_text(filing["filename"]); c.event_type,c.event_proof,c.event_summary=classify_event(txt)
    for k,v in filing_risk_flags(txt).items(): setattr(c,k,v)
    c.latest_financial_filing_date=sec.latest_financial_filing(meta["cik"]); facts=sec.companyfacts(meta["cik"])
    d,warnings=heuristic_extract_dilution(txt,_common_shares(facts)); d=apply_override(d,overrides.get(c.ticker,{})); c.dilution=d; c.data_warnings.extend(warnings)
    try:
        for k,v in market_snapshot(c.ticker).items(): setattr(c,k,v)
    except Exception as e: c.data_warnings.append(f"Market data error: {e}")
    c.gate_status,reasons=evaluate_gates(c,cfg); c.data_warnings.extend(reasons); c.priority_score=score_candidate(c); c.bucket=bucket_candidate(c); return c

def scan(days=7,config_path="config/default.json",watchlist_path="config/watchlist.csv",overrides_path="config/overrides.json"):
    cfg=load_json(config_path); overrides=load_json(overrides_path) if Path(overrides_path).exists() else {}; sec=SecClient(); by_cik,by_ticker=_ticker_map(sec)
    latest={}
    for f in sec.recent_filings(days,cfg["event_forms"]):
        meta=by_cik.get(str(int(f["cik"])))
        if not meta or meta["exchange"] not in cfg["exchanges"]: continue
        t=meta["ticker"]
        if t not in latest or f["filed"]>latest[t]["filed"]: latest[t]=f
    for t in load_watchlist(watchlist_path):
        if t in latest or t not in by_ticker: continue
        cik=by_ticker[t]["cik"]; r=sec.submissions(cik).get("filings",{}).get("recent",{})
        for form,filed,acc,doc in zip(r.get("form",[]),r.get("filingDate",[]),r.get("accessionNumber",[]),r.get("primaryDocument",[])):
            if form in cfg["event_forms"]:
                latest[t]={"cik":cik,"company":by_ticker[t]["name"],"form":form,"filed":filed,"filename":f"edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}"}; break
    out=[]
    for t,filing in latest.items():
        try: out.append(build_candidate(sec,by_ticker[t],filing,overrides,cfg))
        except Exception as e:
            c=Candidate(ticker=t,name=by_ticker[t]["name"],exchange=by_ticker[t]["exchange"],cik=by_ticker[t]["cik"]); c.data_warnings.append(f"Pipeline error: {e}"); out.append(c)
    out.sort(key=lambda c:((c.bucket=="A_RESEARCH_NOW"),(c.priority_score or -1)),reverse=True)
    return out,cfg
