"""Scrape all job listings from https://work.mercor.com/explore.

The explore page loads its listings from a public JSON endpoint, so no browser is needed.
Usage: python3 scrape_mercor.py   -> writes mercor_jobs.json / .csv / .xlsx next to this file
"""
import csv, html, json, os, re, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://aws.api.mercor.com/work/listings-explore-page"
OUT = os.path.dirname(os.path.abspath(__file__))
FIRST = ['url', 'title', 'companyName', 'listingDomain', 'commitment', 'workArrangement', 'location',
         'payRateFrequency', 'rateMin', 'rateMax', 'hoursPerWeek', 'referralAmount', 'remainingSlots',
         'postedAt', 'createdAt', 'status', 'listingType', 'offersEquity', 'eligibleLocation',
         'eligibleResidenceLocation', 'ineligibleLocation', 'ineligibleResidenceLocation', 'employmentType', 'validThrough',
         'companyWebsite', 'companyDescription', 'fullPostingText', 'pageFooterText', 'referralText', 'description']


def cell(x):
    if isinstance(x, list):
        return '; '.join(map(str, x))
    return '' if x is None else x


REFERRAL_POLICY = 'https://talent.docs.mercor.com/policies/referrals'
UA = {"User-Agent": "Mozilla/5.0"}
PAGE_EXTRA = ['companyWebsite', 'companyDescription', 'availableSpots', 'activeContractorsCount',
              'latestHeadcountGoalDeadline', 'sumMinHeadcountGoals', 'isConsumerData']


def page_details(job):
    """Fetch the job page: it adds site text (EEO line, Contract and Payment Terms, About Mercor)
    and a few fields that the explore feed leaves out."""
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(job['url'], headers=UA), timeout=60)
            raw = raw.read().decode('utf-8', 'replace')
            break
        except Exception as e:
            err = e
    else:
        return {'pageFetchError': str(err)}
    out = {}
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw, re.S)
    if m:
        props = json.loads(m.group(1))['props']['pageProps']
        role = props.get('role') or {}
        out.update({k: role.get(k) for k in PAGE_EXTRA})
        jp = (props.get('structuredData') or {}).get('jobPosting') or {}
        out['employmentType'] = jp.get('employmentType')
        out['validThrough'] = jp.get('validThrough')
    body = re.sub(r'<(script|style)\b.*?</\1>', '', raw, flags=re.S)
    body = re.sub(r'<(br|/p|/li|/h\d|/div)[^>]*>', '\n', body)
    text = html.unescape(re.sub(r'<[^>]+>', '', body))
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    # Site text sits between the end of the description and the referral box / testimonial block.
    last_line = [l.strip() for l in job['description'].strip().splitlines() if l.strip()][-1]
    last_line = re.sub(r'[*_#`\\]|^[-\d.]+\s*', '', last_line).strip()[-60:]
    start = text.find(last_line)
    if start != -1:
        start += len(last_line)
    else:  # description text rendered differently; anchor on the first site-added line instead
        hits = [i for i in (text.find(m) for m in ('We consider all qualified applicants',
                'Contract and Payment Terms', 'About Mercor')) if i != -1]
        start = min(hits) if hits else -1
    ends = [i for i in (text.find(m, max(start, 0)) for m in ('Share the referral link',
            'Activate my referral link', 'One interview, real results')) if i != -1]
    end = min(ends) if ends else -1
    # Referral box: "Earn up to $X by referring" + its explanation, ending before the activate button.
    ref = None
    rm = re.compile(r'Earn (up to \$|rewards by referring)').search(text, max(start, 0))
    r0 = rm.start() if rm else -1
    r1 = text.find('Activate my referral link', max(r0, 0))
    if r0 != -1 and r1 > r0:
        lines = []
        for l in text[r0:r1].splitlines():
            l = l.strip()
            if l and l not in lines:  # the page repeats the "Referral limits apply" sentence
                lines.append(l)
        lines = [l for l in lines if not any(l != o and l in o for o in lines)]
        ref = '\n'.join(lines).replace('See the Referral Policy',
                                       'See the Referral Policy (' + REFERRAL_POLICY + ')')
    out['referralText'] = ref
    if start != -1 and end > start:
        tail = text[start:end]
        tail = re.sub(r'\s*Earn (up to \$[\d,]+|rewards) by referring\s*$', '', tail).strip()
        out['pageFooterText'] = tail
        full = job['description'].strip() + '\n\n' + tail
    else:
        out['pageFooterText'] = None
        full = job['description'].strip()
    out['fullPostingText'] = full + ('\n\n' + ref if ref else '')
    return out


def main():
    req = urllib.request.Request(API, headers={**UA, "Origin": "https://work.mercor.com"})
    jobs = json.load(urllib.request.urlopen(req, timeout=60))['listings']
    for j in jobs:
        j['url'] = f"https://work.mercor.com/jobs/{j['listingId']}"
    with ThreadPoolExecutor(8) as ex:
        for j, extra in zip(jobs, ex.map(page_details, jobs)):
            j.update(extra)
    jobs.sort(key=lambda j: j.get('postedAt') or '', reverse=True)
    keys = FIRST + sorted({k for j in jobs for k in j} - set(FIRST))

    with open(os.path.join(OUT, 'mercor_jobs.json'), 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT, 'mercor_jobs.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(keys)
        for j in jobs:
            w.writerow([cell(j.get(k)) for k in keys])
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Jobs'
        ws.append(keys)
        for j in jobs:
            ws.append([(c[:32000] if isinstance(c, str) else c) for c in (cell(j.get(k)) for k in keys)])
        ws.freeze_panes = 'B2'
        ws.auto_filter.ref = ws.dimensions
        wb.save(os.path.join(OUT, 'mercor_jobs.xlsx'))
    except ImportError:
        pass
    print(f"Saved {len(jobs)} jobs to {OUT}")


if __name__ == '__main__':
    main()
