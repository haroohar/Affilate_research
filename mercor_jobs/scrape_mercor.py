"""Scrape all job listings from https://work.mercor.com/explore.

The explore page loads its listings from a public JSON endpoint, so no browser is needed.
Usage: python3 scrape_mercor.py   -> writes mercor_jobs.json / .csv / .xlsx next to this file
"""
import csv, json, os, urllib.request

API = "https://aws.api.mercor.com/work/listings-explore-page"
OUT = os.path.dirname(os.path.abspath(__file__))
FIRST = ['url', 'title', 'companyName', 'listingDomain', 'commitment', 'workArrangement', 'location',
         'payRateFrequency', 'rateMin', 'rateMax', 'hoursPerWeek', 'referralAmount', 'remainingSlots',
         'postedAt', 'createdAt', 'status', 'listingType', 'offersEquity', 'eligibleLocation',
         'eligibleResidenceLocation', 'ineligibleLocation', 'ineligibleResidenceLocation', 'description']


def cell(x):
    if isinstance(x, list):
        return '; '.join(map(str, x))
    return '' if x is None else x


def main():
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0",
                                               "Origin": "https://work.mercor.com"})
    jobs = json.load(urllib.request.urlopen(req, timeout=60))['listings']
    for j in jobs:
        j['url'] = f"https://work.mercor.com/jobs/{j['listingId']}"
    jobs.sort(key=lambda j: j.get('postedAt') or '', reverse=True)
    keys = FIRST + [k for k in jobs[0] if k not in FIRST]

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
