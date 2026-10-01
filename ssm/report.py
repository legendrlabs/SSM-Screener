from __future__ import annotations
import csv,json
from pathlib import Path

def _m(x):
    if x is None:return ""
    if abs(x)>=1e9:return f"${x/1e9:.2f}B"
    if abs(x)>=1e6:return f"${x/1e6:.1f}M"
    if abs(x)>=1e3:return f"${x/1e3:.1f}K"
    return f"${x:.2f}"

def write_outputs(candidates,cfg,out_dir):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    flat=[]
    for c in candidates:
        d=c.to_dict(); dil=d.pop("dilution"); d.update({f"dilution_{k}":v for k,v in dil.items()}); d["data_warnings"]=" | ".join(d.get("data_warnings") or []); flat.append(d)
    if flat:
        with (out/"candidates.csv").open("w",newline="",encoding="utf-8-sig") as f: w=csv.DictWriter(f,fieldnames=list(flat[0].keys()));w.writeheader();w.writerows(flat)
    else:(out/"candidates.csv").write_text("",encoding="utf-8")
    with (out/"dilution_check.csv").open("w",newline="",encoding="utf-8-sig") as f:
        fields=["ticker","common_shares","near_fd_shares","strict_fd_shares","fd_ratio","atm_remaining_usd","atm_ratio","confidence","source"];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in candidates:w.writerow({"ticker":c.ticker,"common_shares":c.dilution.common_shares,"near_fd_shares":c.dilution.near_fd_shares,"strict_fd_shares":c.dilution.strict_fd_shares,"fd_ratio":c.dilution.fd_ratio,"atm_remaining_usd":c.dilution.atm_remaining_usd,"atm_ratio":c.atm_ratio(),"confidence":c.dilution.confidence,"source":c.dilution.source})
    with (out/"event_ledger.csv").open("w",newline="",encoding="utf-8-sig") as f:
        fields=["ticker","event_date","form","event_type","event_proof","accession","summary","gate_status","bucket"];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in candidates:w.writerow({"ticker":c.ticker,"event_date":c.latest_event_date,"form":c.latest_event_form,"event_type":c.event_type,"event_proof":c.event_proof,"accession":c.latest_event_accession,"summary":c.event_summary,"gate_status":c.gate_status,"bucket":c.bucket})
    safe=all(c.gate_status!="DATA_HOLD" for c in candidates if c.bucket=="A_RESEARCH_NOW")
    q={"SAFE_TO_ACT":safe,"sec_discovery_mode":cfg.get("_sec_discovery_mode","unknown"),"candidate_count":len(candidates),"financial_review_incomplete_count":sum(not c.financial_review_complete for c in candidates),"data_hold_count":sum(c.gate_status=="DATA_HOLD" for c in candidates),"pass_count":sum(c.gate_status=="PASS" for c in candidates),"watch_count":sum(c.gate_status=="WATCH" for c in candidates),"reject_count":sum(c.gate_status=="REJECT" for c in candidates)}
    (out/"quality.json").write_text(json.dumps(q,indent=2),encoding="utf-8")
    top=[c for c in candidates if c.bucket=="A_RESEARCH_NOW"][:cfg["max_candidates"]]; watch=[c for c in candidates if c.bucket in ("B_WATCH","C_SPECULATIVE")][:10]; reject=[c for c in candidates if c.bucket=="REJECT"][:10]; hold=[c for c in candidates if c.bucket=="DATA_HOLD"][:10]
    md=["# Special Situation Microcap — latest","",f"**SAFE_TO_ACT: {'TRUE' if safe else 'FALSE'}**",""]
    if not top:md += ["## NO CANDIDATE",""]
    else:
        md += ["## A — RESEARCH NOW","","|Ticker|Price|Basic MC|Near-FD MC|Strict FD MC|Event|Proof|10-Q/K|Score|","|---|---:|---:|---:|---:|---|---:|---|---:|"]
        for c in top:md.append(f"|{c.ticker}|{_m(c.price)}|{_m(c.basic_market_cap())}|{_m(c.near_fd_market_cap())}|{_m(c.strict_fd_market_cap())}|{c.event_type}|{c.event_proof}|{c.latest_financial_form or ''} {c.latest_financial_filing_date or ''}|{c.priority_score}|")
    for title,arr in [("B/C — WATCH",watch),("DATA HOLD",hold),("REJECT",reject)]:
        md += ["",f"## {title}",""]
        if not arr:md.append("- None")
        for c in arr:md.append(f"- **{c.ticker}** — {c.bucket}, score {c.priority_score}. {'; '.join(c.data_warnings[:3])}")
    (out/"latest.md").write_text("\n".join(md),encoding="utf-8")
