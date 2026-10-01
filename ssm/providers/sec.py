from __future__ import annotations
import os,re,time,datetime as dt
import requests
SEC_BASE="https://www.sec.gov"

class SecClient:
    def __init__(self,user_agent=None,pause=.15):
        self.user_agent=user_agent or os.getenv("SEC_USER_AGENT","")
        if not self.user_agent: raise RuntimeError("Set SEC_USER_AGENT='Name email@example.com' before live SEC requests.")
        self.pause=pause; self.s=requests.Session(); self.s.headers.update({"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate"})
    def _get(self,url):
        time.sleep(self.pause); r=self.s.get(url,timeout=30); r.raise_for_status(); return r
    def exchange_tickers(self):
        r=self._get(f"{SEC_BASE}/files/company_tickers_exchange.json").json(); fields=r["fields"]; return [dict(zip(fields,row)) for row in r["data"]]
    def daily_master_index(self,day):
        q=(day.month-1)//3+1; url=f"{SEC_BASE}/Archives/edgar/daily-index/{day.year}/QTR{q}/master.{day:%Y%m%d}.idx"
        try: txt=self._get(url).text
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code==404: return []
            raise
        lines=txt.splitlines(); start=0
        for i,line in enumerate(lines):
            if line.startswith("CIK|Company Name|Form Type|Date Filed|Filename"): start=i+1; break
        out=[]
        for line in lines[start:]:
            if "|" not in line: continue
            p=line.split("|")
            if len(p)==5: out.append({"cik":p[0],"company":p[1],"form":p[2],"filed":p[3],"filename":p[4]})
        return out
    def recent_filings(self,days,forms):
        forms=set(forms); today=dt.date.today(); rows=[]
        for i in range(days+1):
            for row in self.daily_master_index(today-dt.timedelta(days=i)):
                if row["form"] in forms: rows.append(row)
        return rows
    def submission_text(self,filename): return self._get(f"{SEC_BASE}/Archives/{filename}").text
    def submissions(self,cik): return self._get(f"{SEC_BASE}/submissions/CIK{int(cik):010d}.json").json()
    def latest_financial_filing(self,cik):
        r=self.submissions(cik).get("filings",{}).get("recent",{})
        for form,filed in zip(r.get("form",[]),r.get("filingDate",[])):
            if form in ("10-Q","10-K"): return filed
        return None
    def companyfacts(self,cik): return self._get(f"{SEC_BASE}/api/xbrl/companyfacts/CIK{int(cik):010d}.json").json()

def latest_fact_value(companyfacts,tag):
    node=companyfacts.get("facts",{}).get("dei",{}).get(tag) or companyfacts.get("facts",{}).get("us-gaap",{}).get(tag)
    if not node: return None
    rows=[]
    for u in node.get("units",{}).values(): rows.extend(u)
    rows=[x for x in rows if x.get("val") is not None and x.get("filed")]; rows.sort(key=lambda x:x.get("filed",""),reverse=True)
    return rows[0]["val"] if rows else None

def filing_risk_flags(text):
    t=re.sub(r"\s+"," ",text or "").lower()
    return {
        "going_concern":"substantial doubt about our ability to continue as a going concern" in t,
        "nasdaq_deficiency":bool(re.search(r"minimum bid price|nasdaq deficiency|listing qualifications",t)),
        "reverse_split":bool(re.search(r"reverse stock split|reverse split",t)),
        "vie_or_offshore":bool(re.search(r"variable interest entity|\bvie\b|cayman islands|british virgin islands|\bbvi\b|\bprc\b",t)),
        "related_party":"related party" in t or "related-party" in t,
        "auditor_flag":bool(re.search(r"auditor resignation|dismissed.*independent registered public accounting firm|pcaob.*unable",t)),
    }
