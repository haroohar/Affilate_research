"""Build mercor_database.html: every Mercor listing in one filterable page, focused on referral value.

Usage: python3 scrape_mercor.py && python3 views/build_database.py
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_PATH = os.path.join(HERE, '..', 'mercor_jobs.json')

# Mercor leaves listingDomain empty on ~90 listings; fill those from the title.
INFER = [
    (r'linguistic', 'Language and Audio'),
    (r'voice actor|audio', 'Language and Audio'),
    (r'drug discovery|medical affairs|cmc|pharmacovigilance|clinical|regulatory affairs|neurolog|urolog|oncolog|physician|nurse|\brn\b|md/do',
     'Medicine'),
    (r'patent attorney|lawyer|legal|attorney', 'Law'),
    (r'fp&a|accounting|investment banking|finance|tax|cpa|loan|financial', 'Finance'),
    (r'sales|account executive|\bhr\b|recruit|operations', 'Business Operations'),
    (r'software|engineer, backend|open source|developer|agent engineer|devops|kernel|ml |machine learning|llm',
     'Software Engineering'),
    (r'electrical|mechanical|network engineering|simulation', 'Other Engineering'),
    (r'mathematics|biology|chemistry|physics|life sciences', 'Life, Physical, and Social Science'),
    (r'design|art director|video|motion|3d|visualization|music|editorial', 'Arts & Design'),
]

FOCUS = {
    'finance': re.compile(r'financ|fp&a|accounting|audit|tax|cpa|cfa|banking|private equity|venture|wealth|asset management|'
                          r'insurance|underwrit|loan|trader|controller|treasury|actuar|excel expert', re.I),
    'tech': re.compile(r'software|engineer|developer|machine learning|\bml\b|mlops|\bllm\b|\bai\b agent|agent engineer|'
                       r'data scien|gpu|kernel|devops|security|cyber|cve|swe-bench|kubernetes|aws|code|python', re.I),
}

UNIT = {'hourly': '/hr', 'per-task': '/task', 'one-time': ' one-time', 'yearly': '/yr'}


def category(j):
    if j.get('listingDomain'):
        return j['listingDomain']
    t = (j.get('title') or '').lower()
    for pat, cat in INFER:
        if re.search(pat, t):
            return cat
    return 'Miscellaneous'


def pay(j):
    a, b = j.get('rateMin'), j.get('rateMax')
    if not a and not b:
        return 'Not listed'
    s = f"${a:,.0f}" if (a == b or not b) else f"${a:,.0f}–${b:,.0f}"
    return s + UNIT.get(j.get('payRateFrequency'), '')


def geo(j):
    el = j.get('eligibleLocation') or []
    if el == ['USA']:
        return 'US only', 'USA'
    if el:
        return f'{len(el)} countries' if len(el) > 3 else ', '.join(el), ', '.join(el)
    loc = (j.get('location') or '')
    if re.search(r'^(united states|us\b|remote \(us\)|remote \(united states\)|remote — united states)|bay area|, ca$', loc, re.I):
        return 'US only', 'USA (from location text)'
    return 'Open (supported countries)', 'Any country Mercor supports'


HRS = re.compile(r'(?:minimum of|at least|min\.?|up to|about|around|approximately|~)?\s*(\d{1,2})\s*(?:[-–]|to)?\s*(\d{1,2})?\+?\s*'
                 r'(?:hours?|hrs?)\s*(?:per|a|/|each)\s*week', re.I)
LIGHT_TEXT = re.compile(r'no (weekly )?minimum|as (few|little) as|minutes?,? paid|\d+[- ]minute', re.I)


def load(j):
    """Time commitment level, from Mercor's hoursPerWeek or, when that is empty, the posting text."""
    h, note = j.get('hoursPerWeek'), ''
    text = j.get('fullPostingText') or ''
    if h is None:
        m = HRS.search(text)
        if m:
            lo = int(m.group(1)); h = lo
            note = m.group(0).strip()
    if (j.get('commitment') == 'task-based' or j.get('payRateFrequency') in ('per-task', 'one-time')) and (h is None or h <= 10):
        return 'Light', h, note or 'Paid per task or survey'
    if h is not None:
        if h <= 10: return 'Light', h, note
        if h <= 25: return 'Part-time', h, note
        return 'Full-time', h, note
    if LIGHT_TEXT.search(text):
        return 'Light', None, LIGHT_TEXT.search(text).group(0)
    return 'Flexible', None, 'No weekly hours stated'


def referral(j):
    t = j.get('referralText') or ''
    amt = j.get('referralAmount') or 0
    if 'rewards by referring' in t or '20% of your referral' in t:
        return 'Earnings share', amt
    if amt:
        return 'Fixed', amt
    return 'None', 0


def summarize(j):
    """One listing as the page (and the outreach pipeline) uses it."""
    g_short, g_full = geo(j)
    r_model, r_amt = referral(j)
    blob = ' '.join([j.get('title') or '', category(j)])
    focus = [k for k, rx in FOCUS.items() if rx.search(blob)]
    lvl, hrs, hnote = load(j)
    return {
        'id': j['listingId'],
        'title': j.get('title') or '',
        'url': j['url'],
        'cat': category(j),
        'type': 'Talent pool' if j.get('opportunityType', '').startswith('talent') else 'Current project',
        'commit': j.get('commitment') or '',
        'pay': pay(j),
        'rmin': j.get('rateMin') or 0,
        'rmax': j.get('rateMax') or 0,
        'freq': j.get('payRateFrequency') or '',
        'hours': hrs,
        'load': lvl,
        'hnote': hnote,
        'loc': j.get('location') or '',
        'geo': g_short,
        'geoFull': g_full,
        'eligible': j.get('eligibleLocation') or [],
        'refModel': r_model,
        'ref': r_amt,
        'slots': j.get('remainingSlots'),
        'posted': (j.get('postedAt') or '')[:10],
        'focus': focus,
        'text': j.get('fullPostingText') or j.get('description') or '',
    }


def load_listings():
    return [summarize(j) for j in json.load(open(JOBS_PATH, encoding='utf-8'))]


def main():
    out = load_listings()
    data = json.dumps(out, ensure_ascii=False).replace('</', '<\\/')
    tpl = open(os.path.join(HERE, 'database_template.html'), encoding='utf-8').read()
    scraped = max(o['posted'] for o in out)
    html = tpl.replace('__DATA__', data).replace('__SCRAPED__', scraped)
    open(os.path.join(HERE, 'mercor_database.html'), 'w', encoding='utf-8').write(html)
    cats = {}
    for o in out:
        cats[o['cat']] = cats.get(o['cat'], 0) + 1
    print(len(out), 'listings;', sorted(cats.items(), key=lambda x: -x[1]))
    print('load', {k: sum(o['load'] == k for o in out) for k in ('Light', 'Flexible', 'Part-time', 'Full-time')})
    print('focus finance', sum('finance' in o['focus'] for o in out), 'tech', sum('tech' in o['focus'] for o in out))


if __name__ == '__main__':
    main()
