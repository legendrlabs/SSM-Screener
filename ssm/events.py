"""Review source-backed transactions and retain the active economic catalyst."""
from datetime import date, datetime, timedelta
import re

from .event_rules import classify_event, operative_text

PRIORITY = {'TERMINAL_MERGER': 110, 'MERGER_TERMINATED': 105,
            'LIQUIDATION_DISTRIBUTION': 100, 'MERGER_CASH_CVR': 90,
            'MERGER_REVERSE_MERGER': 85, 'ASSET_SALE_ACQUISITION': 70,
            'STRATEGIC_INVESTMENT_PIPE': 65, 'DEBT_RESTRUCTURING': 60,
            'LARGE_CONTRACT': 50, 'BUSINESS_PIVOT': 45,
            'LISTING_CAPITAL_STRUCTURE': 25}
MONTH_DATE = r'([A-Z][a-z]+\s+\d{1,2},\s*20\d{2})'


def select_event(reviewed):
    if not reviewed:
        return None
    latest_merger = max((x.get('filed', '') for x in reviewed if x['event_type'] in {'MERGER_CASH_CVR', 'MERGER_REVERSE_MERGER'}), default='')
    eligible = [x for x in reviewed if not (x['event_type'] == 'MERGER_TERMINATED' and x.get('filed', '') < latest_merger)]
    # Retain active merger/liquidation lifecycles through routine filings.
    # Other transactions use recency; an old asset deal cannot hide refinancing.
    return max(eligible, key=lambda x: (PRIORITY.get(x['event_type'], 10) if PRIORITY.get(x['event_type'], 10) >= 85 else 0,
                                       x.get('filed', ''), x.get('accession', '')))


def _date_after(text, anchor, distance=180):
    match = re.search('(?:' + anchor + ')' + r'.{0,' + str(distance) + r'}?' + MONTH_DATE, text, re.I)
    if not match:
        return None
    try:
        return datetime.strptime(re.sub(r'\s+', ' ', match.group(1)), '%B %d, %Y').date().isoformat()
    except ValueError:
        return None


def event_terms(text, kind):
    t = operative_text(text)
    terms = {}
    if kind in {'MERGER_CASH_CVR', 'MERGER_REVERSE_MERGER', 'TERMINAL_MERGER'}:
        cash = re.search(r'\$\s*(\d+(?:\.\d+)?)\s+per share.{0,45}?in cash', t, re.I)
        if not cash:
            cash = re.search(r'converted into.{0,100}?\$\s*(\d+(?:\.\d+)?)\s+(?:cash|per share)', t, re.I)
        if cash:
            terms['cash_per_share_usd'] = float(cash.group(1))
        if kind == 'MERGER_CASH_CVR':
            terms['cvr_conditional'] = True
            if re.search(r'non[- ]tradable|non[- ]transferable', t, re.I):
                terms['cvr_transferable'] = False
            illustrative = re.search(r'aggregate potential merger consideration (?:of|is)\s*\$\s*(\d+(?:\.\d+)?)\s+per share', t, re.I)
            if illustrative and re.search(r'assuming full|illustration', t, re.I):
                terms['illustrative_total_per_share_usd'] = float(illustrative.group(1))
    if kind == 'LIQUIDATION_DISTRIBUTION':
        distribution = re.search(r'\$\s*(\d+(?:\.\d+)?)\s+per (?:common )?share.{0,70}(?:liquidating|liquidation|distribution)', t, re.I)
        if not distribution:
            distribution = re.search(r'(?:liquidating distribution|liquidating cash distribution|special.{0,20}distribution).{0,90}?\$\s*(\d+(?:\.\d+)?)\s+per (?:common )?share', t, re.I)
        if distribution:
            terms['distribution_per_share_usd'] = float(distribution.group(1))
            terms['distribution_status'] = 'DECLARED' if re.search(r'declar|approved', t, re.I) else 'UNKNOWN'
        for key, anchor in [('payment_date', r'(?:special dividend|distribution).{0,30}(?:will be paid|is payable|payable) on|payment date (?:is|of)'),
                            ('record_date', r'record (?:on|date)'),
                            ('ex_dividend_date', r'ex[- ]dividend date (?:is|of|will be)'),
                            ('last_trading_date', r'last (?:day of trading|trading day)(?: on the NYSE)? (?:is|to be|is expected to be)'),
                            ('dissolution_date', r'dissolution[, ]+(?:effective|is planned for)|articles of dissolution.{0,40}(?:on|effective)')]:
            value = _date_after(t, anchor, 60)
            if value:
                terms[key] = value
        before_ex = re.search(MONTH_DATE + r'\s+ex[- ]dividend date', t, re.I)
        if before_ex:
            terms['ex_dividend_date'] = datetime.strptime(before_ex.group(1), '%B %d, %Y').date().isoformat()
        if re.search(r'due bills?|due[- ]bill', t, re.I):
            terms['due_bills'] = True
        if re.search(r'dissolution|dissolve', t, re.I):
            terms['dissolution_status'] = 'PLANNED'
        if 'payment_date' not in terms:
            value = _date_after(t, r'(?:special dividend|distribution) will be paid on', 40)
            if value:
                terms['payment_date'] = value
        if 'record_date' not in terms:
            value = _date_after(t, r'shareholders of record', 80)
            if value:
                terms['record_date'] = value
    if kind == 'DEBT_RESTRUCTURING':
        warrant = re.search(r'warrants.{0,100}purchase.{0,60}?(\d[\d,]*)\s+shares.{0,140}exercise price of\s*\$\s*(\d+(?:\.\d+)?)', t, re.I)
        if warrant:
            terms['new_warrant_shares'] = int(warrant.group(1).replace(',', ''))
            terms['new_warrant_exercise_price_usd'] = float(warrant.group(2))
            terms['warrant_reconciliation_required'] = True
    if kind == 'ASSET_SALE_ACQUISITION':
        amount = re.search(r'aggregate purchase price.{0,70}?\$\s*([\d.]+)\s*million', t, re.I)
        if amount:
            terms['sale_price_estimate_usd'] = float(amount.group(1)) * 1e6
        repurchase = re.search(r'increase.{0,80}repurchase authorization from\s*\$\s*([\d.]+)\s*million to\s*\$\s*([\d.]+)\s*million', t, re.I)
        if repurchase:
            terms['repurchase_total_usd'] = float(repurchase.group(2)) * 1e6
            terms['repurchase_increment_usd'] = (float(repurchase.group(2)) - float(repurchase.group(1))) * 1e6
            terms['repurchase_conditional'] = bool(re.search(r'conditioned upon|only upon.{0,50}closing', t, re.I))
    actual_date = re.search(r'\bOn\s+' + MONTH_DATE, t)
    if actual_date:
        try:
            terms['transaction_date'] = datetime.strptime(actual_date.group(1), '%B %d, %Y').date().isoformat()
        except ValueError:
            pass
    return terms


def event_status(text, kind, proof):
    if kind == 'TERMINAL_MERGER': return 'TERMINAL'
    if kind == 'MERGER_TERMINATED': return 'CANCELLED'
    if kind == 'LIQUIDATION_DISTRIBUTION': return 'LIQUIDATING'
    if proof <= 1: return 'PRELIMINARY' if proof else 'UNKNOWN'
    return 'COMPLETED' if proof >= 3 else 'SIGNED'


def review_material_events(sec, cik, discovered, cfg):
    recent = sec.submissions(cik).get('filings', {}).get('recent', {})
    cutoff = (date.today() - timedelta(days=cfg['event_max_age_days'])).isoformat()
    filings = {discovered.get('accession') or discovered.get('filename'): dict(discovered)}
    for i, form in enumerate(recent.get('form', [])):
        if form != '8-K' or recent['filingDate'][i] < cutoff:
            continue
        items = recent.get('items', [''] * len(recent['form']))[i] or ''
        if not set(re.split(r'[,;]', items)).intersection(cfg['material_8k_items']):
            continue
        accession = recent['accessionNumber'][i]
        filings[accession] = {'cik': cik, 'form': form, 'filed': recent['filingDate'][i], 'items': items,
                              'accession': accession, 'filename': f"edgar/data/{int(cik)}/{accession.replace('-', '')}/{recent['primaryDocument'][i]}"}
    reviewed, warnings = [], []
    for filing in filings.values():
        try:
            primary = sec.submission_text(filing['filename'])
            sources = ['https://www.sec.gov/Archives/' + filing['filename']]
            text = primary
            if filing.get('form') == '8-K' and re.search(r'Exhibit\s+99\.|99\.\d', primary, re.I):
                # Incorporated press releases own economic terms. Select them
                # by type; a pile of EX-10 documents cannot crowd them out.
                for doc in sec.filing_documents(cik, filing.get('accession'), filing.get('index_url')):
                    if doc['type'].startswith('EX-99'):
                        text += '\n' + sec.submission_text(doc['url'])
                        sources.append(doc['url'])
            label, proof, summary = classify_event(text)
            # Classify the operative primary first, but use the press release
            # for stronger transaction facts/terms when the primary is generic.
            press = text[len(primary):]
            if press:
                ex_label, ex_proof, ex_summary = classify_event(press)
                if PRIORITY.get(ex_label, 10) > PRIORITY.get(label, 10):
                    label, proof, summary = ex_label, max(proof, ex_proof), ex_summary
            terms = event_terms(primary, label)
            if press:
                terms.update(event_terms(press, label))
            reviewed.append({**filing, 'event_type': label, 'event_proof': proof,
                             'event_status': event_status(text, label, proof), 'summary': summary,
                             'terms': terms,
                             'sources': sources, 'text': primary, 'combined_text': text})
        except Exception as exc:
            warnings.append(f"Event review failed for {filing.get('accession')}: {exc}")
    selected = select_event(reviewed)
    if selected:
        selected = dict(selected)
        selected['selection_reason'] = 'Retain an active merger/liquidation lifecycle; otherwise select the most recent material economic event.'
    return selected, reviewed, warnings
