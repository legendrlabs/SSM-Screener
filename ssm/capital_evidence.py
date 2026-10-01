"""Narrow evidence readers; security units are never assumed to be shares."""
from datetime import datetime
from html.parser import HTMLParser
import re

from .financial_review import visible_filing_text


def preferred_signal_text(text: str) -> str:
    """Mask only explicitly unissued capacity and nonoperative boilerplate.

    Each occurrence is evaluated separately. A zero balance cannot clear another
    class, a subsequent issuance, or historical conversion terms elsewhere.
    """
    pattern = r'preferred (?:stock|shares)'
    sentences = re.split(r'(?<=\.)\s+', text)
    result = []
    for sentence in sentences:
        accounting = bool(re.search(r'\b(?:ASU\s+\d{4}-\d+|FASB)\b', sentence, re.I))
        shelf = bool(re.search(r'\bmay\b[^.]{0,100}\bsell\b', sentence, re.I)
                     and re.search(r'shelf registration', sentence, re.I))
        charter = bool(re.search(r'blank check', sentence, re.I)
                       and re.search(r'\bcould\b', sentence, re.I))
        # Actual issuer-specific holdings or issuances must survive boilerplate.
        positive = (r'\b[1-9][\d,]*\s+(?:preferred\s+)?shares\s+(?:(?:were|are)\s+)?(?:issued|outstanding)\b'
                    r'|\bissued\s+[1-9][\d,]*\s+(?:preferred\s+)?shares\b')
        live = bool(re.search(r'\b(?:our|its)\s+(?:Series\s+[A-Z0-9-]+\s+)?preferred|\bCompany\b[^.]{0,50}\bissued\b|\bremain\w*\s+outstanding', sentence, re.I)
                    or re.search(positive, sentence, re.I))
        if (accounting or shelf or charter) and not live:
            result.append(re.sub(pattern, '_PREFERRED_CAPACITY_', sentence, flags=re.I))
            continue

        def mask_zero(match):
            tail = sentence[match.end():match.end() + 350]
            # Do not borrow a zero balance from the next security/class.
            tail = re.split(r'preferred (?:stock|shares)|common stock|Series\s+[A-Z0-9-]+', tail, maxsplit=1, flags=re.I)[0]
            zero = re.search(r'\bnone\s+(?:issued|outstanding)\b', tail, re.I)
            period_only = zero and re.match(r'\s+(?:during|in|since|this|for|over)\b', tail[zero.end():], re.I)
            if zero and not period_only and not re.search(positive, tail, re.I):
                return '_PREFERRED_CAPACITY_'
            return match.group(0)

        result.append(re.sub(pattern, mask_zero, sentence, flags=re.I))
    return ' '.join(result)


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.tables = []
        self.context = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.stack.append({'rows': [], 'row': None, 'cell': None, 'context': self.context[-1200:]})
        elif self.stack and tag == 'tr':
            self.stack[-1]['row'] = []
        elif self.stack and tag in {'td', 'th'}:
            self.stack[-1]['cell'] = []

    def handle_endtag(self, tag):
        if not self.stack:
            return
        table = self.stack[-1]
        if tag in {'td', 'th'} and table['cell'] is not None:
            if table['row'] is not None:
                table['row'].append(re.sub(r'\s+', ' ', ''.join(table['cell'])).strip())
            table['cell'] = None
        elif tag == 'tr' and table['row'] is not None:
            table['rows'].append(table['row'])
            table['row'] = None
        elif tag == 'table':
            self.tables.append(self.stack.pop())

    def handle_data(self, data):
        self.context = (self.context + data + ' ')[-1200:]
        if self.stack and self.stack[-1]['cell'] is not None:
            self.stack[-1]['cell'].append(data)


def outstanding_warrant_units(text: str):
    """Accept a single-period tranche table only when every row reconciles.

    This is an outstanding *unit* count, not a common-share equivalent. Tables
    with multiple numeric columns, incomplete rows or conflicting dates/counts
    are left unresolved.
    """
    parser = _Tables()
    parser.feed(re.sub(r'<(ix:header|ix:hidden|script|style)\b[^>]*>.*?</\1\s*>', ' ', text or '', flags=re.I | re.S))
    evidence = []
    for table in parser.tables:
        context = visible_filing_text(table['context'])
        narrative = re.search(r'(\d[\d,]*)(?:\s+and\s+\d[\d,]*)?\s+warrants\s+outstanding\s+and\s+exercisable\s+as of\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})', context, re.I)
        if not narrative:
            continue
        rows = table['rows']
        header = ' '.join(' '.join(row) for row in rows[:4])
        table_date = re.search(r'As of\s+([A-Za-z]+\s+\d{1,2},)', header, re.I)
        if not table_date:
            continue
        try:
            as_of = datetime.strptime(narrative.group(2), '%B %d, %Y').date().isoformat()
        except ValueError:
            continue
        years = re.findall(r'(?<!\d)(20\d{2})(?!\d)', ' '.join(' '.join(row) for row in rows if not re.search(r'exercise price', ' '.join(row), re.I)))
        if years != [as_of[:4]]:
            continue
        try:
            if datetime.strptime(table_date.group(1) + ' ' + years[0], '%B %d, %Y').date().isoformat() != as_of:
                continue
        except ValueError:
            continue
        prefunded = ordinary = total = 0
        valid = True
        for row in rows:
            cells = [cell for cell in row if cell]
            if not cells or re.search(r'As of|Issue Date', ' '.join(cells), re.I) or cells == [as_of[:4]]:
                continue
            if len(cells) == 1 and re.fullmatch(r'\d[\d,]*', cells[0]):
                if total:
                    valid = False
                    break
                total = int(cells[0].replace(',', ''))
                continue
            if len(cells) != 2 or not re.search(r'exercise price', cells[0], re.I) or not re.fullmatch(r'\d[\d,]*', cells[1]):
                valid = False
                break
            value = int(cells[1].replace(',', ''))
            if re.search(r'pre[- ]funded', cells[0], re.I):
                prefunded += value
            else:
                ordinary += value
        if valid and prefunded > 0 and total == prefunded + ordinary == int(narrative.group(1).replace(',', '')):
            evidence.append((as_of, prefunded, ordinary))
    if not evidence:
        return None
    latest = max(item[0] for item in evidence)
    matches = {item for item in evidence if item[0] == latest}
    return matches.pop() if len(matches) == 1 else None
