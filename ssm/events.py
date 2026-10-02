"""Review source-backed transactions and retain the active economic catalyst."""
from datetime import date, datetime, timedelta
import re

from .event_rules import classify_event, operative_text, liquidation_evidence, adopted_rights_plan, resale_registration, closed_debt_equity_exchange

PRIORITY = {'TERMINAL_MERGER': 110, 'MERGER_TERMINATED': 105,
            'LIQUIDATION_DISTRIBUTION': 100, 'MERGER_CASH_CVR': 90, 'REVERSE_MERGER_CVR': 90, 'MERGER_CVR_UNVERIFIED': 85,
            'MERGER_REVERSE_MERGER': 85, 'ASSET_SALE_ACQUISITION': 70,
            'STRATEGIC_INVESTMENT_PIPE': 65, 'DEBT_RESTRUCTURING': 60,
            'LARGE_CONTRACT': 50, 'BUSINESS_PIVOT': 45,
            'LISTING_CAPITAL_STRUCTURE': 25}
MONTH_DATE = r'([A-Z][a-z]+\s+\d{1,2},\s*20\d{2})'


def select_event(reviewed):
    if not reviewed:
        return None
    latest_merger = max((x.get('filed', '') for x in reviewed if x['event_type'] in {'MERGER_CASH_CVR', 'REVERSE_MERGER_CVR', 'MERGER_CVR_UNVERIFIED', 'MERGER_REVERSE_MERGER'}), default='')
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


def event_terms(text, kind, *, cleaned=False):
    t = text if cleaned else operative_text(text)
    terms = {}
    if kind in {'MERGER_CASH_CVR', 'REVERSE_MERGER_CVR', 'MERGER_CVR_UNVERIFIED', 'MERGER_REVERSE_MERGER', 'TERMINAL_MERGER'}:
        cash = re.search(r'\$\s*(\d+(?:\.\d+)?)\s+per share.{0,45}?in cash', t, re.I)
        if not cash:
            cash = re.search(r'converted into.{0,100}?\$\s*(\d+(?:\.\d+)?)\s+(?:cash|per share)', t, re.I)
        if cash and kind != 'REVERSE_MERGER_CVR':
            terms['cash_per_share_usd'] = float(cash.group(1))
        if kind in {'MERGER_CASH_CVR', 'REVERSE_MERGER_CVR', 'MERGER_CVR_UNVERIFIED'}:
            terms['cvr_conditional'] = True
            if re.search(r'non[- ]tradable|non[- ]transferable', t, re.I):
                terms['cvr_transferable'] = False
            illustrative = re.search(r'aggregate potential merger consideration (?:of|is)\s*\$\s*(\d+(?:\.\d+)?)\s+per share', t, re.I)
            if kind == 'MERGER_CASH_CVR' and illustrative and re.search(r'assuming full|illustration', t, re.I):
                terms['illustrative_total_per_share_usd'] = float(illustrative.group(1))
        if kind == 'REVERSE_MERGER_CVR':
            terms['consideration_type'] = 'STOCK'
            for key, pattern in [('legacy_holder_ownership_pct', r'pre[- ]merger (?:company|parent) stockholders.{0,180}?approximately\s*([\d.]+)%'),
                                 ('target_and_financing_ownership_pct', r'stockholders\s*\(inclusive of investors in the private placement\).{0,180}?approximately\s*([\d.]+)%')]:
                ownership = re.search(pattern, t, re.I)
                if ownership:
                    terms[key] = float(ownership.group(1))
            terms['ownership_illustrative'] = True
            terms['ownership_subject_to_closing_adjustments'] = True
            if re.search(r'net proceeds|monetization', t, re.I):
                terms['cvr_basis'] = 'Legacy asset monetization net proceeds'
            if re.search(r'may declare', t, re.I):
                terms['cvr_distribution_status'] = 'CONTEMPLATED'
    if kind == 'LIQUIDATION_DISTRIBUTION':
        distribution = None
        for clause in liquidation_evidence(t):
            declaration = re.search(r'\b(?:approved|approves|declared|declares)\b(?P<gap>.{0,100}?)liquidating (?:cash )?distribution', clause, re.I)
            if (not declaration or re.search(r'\bplan\b|contemplat|propos|consider', declaration.group('gap'), re.I)
                    or re.search(r'subject to|contingent upon', clause, re.I)):
                continue
            # A preferred-holder amount is not a common-share distribution.
            entitlement = clause[declaration.start():]
            if re.search(r'preferred', clause, re.I):
                distribution = re.search(r'\$\s*(\d+(?:\.\d+)?)\s+per common share(?!\s+par value)', entitlement, re.I)
            else:
                distribution = re.search(r'liquidating (?:cash )?distribution.{0,90}?\$\s*(\d+(?:\.\d+)?)\s*(?:\([^)]*\)\s*)?per (?:common )?share(?!\s+par value)', entitlement, re.I)
                if not distribution:
                    distribution = re.search(r'\$\s*(\d+(?:\.\d+)?)\s+per (?:common )?share(?!\s+par value).{0,50}liquidating (?:cash )?distribution', entitlement, re.I)
            if distribution:
                break
        if distribution:
            terms['distribution_per_share_usd'] = float(distribution.group(1))
            terms['distribution_status'] = 'DECLARED'
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
        if 'dissolution_date' in terms or re.search(r'(?:company|registrant|issuer).{0,80}(?:intends? to|plans? to|will).{0,80}(?:voluntary dissolution|dissolve|terminate its existence)', t, re.I):
            terms['dissolution_status'] = 'PLANNED'
        if 'payment_date' not in terms:
            value = _date_after(t, r'(?:special dividend|distribution) will be paid on', 40)
            if value:
                terms['payment_date'] = value
        if 'record_date' not in terms:
            value = _date_after(t, r'shareholders of record', 80)
            if value:
                terms['record_date'] = value
    if kind == 'LISTING_CAPITAL_STRUCTURE' and adopted_rights_plan(t):
        terms['capital_structure_action'] = 'RIGHTS_PLAN'
    if kind == 'LISTING_CAPITAL_STRUCTURE' and resale_registration(t):
        terms['capital_structure_action'] = 'RESALE_REGISTRATION'
    if kind == 'DEBT_RESTRUCTURING':
        warrant = re.search(r'warrants.{0,100}purchase.{0,60}?(\d[\d,]*)\s+shares.{0,140}exercise price of\s*\$\s*(\d+(?:\.\d+)?)', t, re.I)
        if warrant:
            terms['new_warrant_shares'] = int(warrant.group(1).replace(',', ''))
            terms['new_warrant_exercise_price_usd'] = float(warrant.group(2))
            terms['warrant_reconciliation_required'] = True
        structural = bool(warrant or closed_debt_equity_exchange(t))
        if closed_debt_equity_exchange(t):
            terms['capital_structure_action'] = 'DEBT_EQUITY_EXCHANGE'
        for sentence in re.split(r'(?<=[.;])\s+', t):
            if re.search(r'\bif\b|\bunless\b|\bmay\b|\bwould\b|\bnot\b', sentence, re.I):
                continue
            if re.search(r'(?:debt|notes).{0,80}(?:were|was|has been|have been) converted into.{0,50}(?:equity|common stock)|(?:exchanged|converted).{0,100}(?:debt|notes).{0,100}(?:equity|common stock)|(?:creditors|lenders).{0,60}(?:forgave|forgiven).{0,60}(?:debt|notes)|(?:cured|resolved).{0,40}(?:payment default|actual default)', sentence, re.I):
                structural = True
        routine = bool(re.search(r'amend|amends and restates', t, re.I) and re.search(r'credit(?: and security)? agreement|loan agreement', t, re.I))
        terms['materiality'] = 'STRUCTURAL' if structural else 'ROUTINE' if routine else 'UNVERIFIED'
        commitments = re.search(r'(?:revolving commitments|commitments).{0,60}from\s*\$\s*([\d.]+)\s*million\s+to\s*\$\s*([\d.]+)\s*million', t, re.I)
        if commitments:
            terms['revolving_commitment_before_usd'] = float(commitments.group(1)) * 1e6
            terms['revolving_commitment_after_usd'] = float(commitments.group(2)) * 1e6
            terms['commitment_change_is_debt_reduction'] = False
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
    if kind == 'LISTING_CAPITAL_STRUCTURE' and adopted_rights_plan(operative_text(text)): return 'ADOPTED'
    if kind == 'LISTING_CAPITAL_STRUCTURE' and resale_registration(operative_text(text)): return 'REGISTERED'
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
            narratives = [operative_text(primary)]
            if filing.get('form') == '8-K' and re.search(r'Exhibit\s+99\.|99\.\d', primary, re.I):
                # Incorporated press releases own economic terms. Select them
                # by type; a pile of EX-10 documents cannot crowd them out.
                for doc in sec.filing_documents(cik, filing.get('accession'), filing.get('index_url')):
                    if doc['type'].startswith('EX-99'):
                        exhibit = sec.submission_text(doc['url'])
                        text += '\n' + exhibit
                        narratives.append(operative_text(exhibit))
                        sources.append(doc['url'])
            # Clean each document before joining; one document's Item 9 or
            # cautionary section must not hide another's consideration terms.
            narrative = '\n'.join(narratives)
            label, proof, summary = classify_event(narrative, cleaned=True)
            terms = event_terms(narrative, label, cleaned=True)
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
