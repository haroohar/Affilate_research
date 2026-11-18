"""Step 1: pick low-commitment Mercor listings and turn each into a search + match profile."""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'mercor_jobs', 'views'))
from build_database import load_listings  # noqa: E402

PROFILES = json.load(open(os.path.join(HERE, 'role_profiles.json'), encoding='utf-8'))
LOW = ('Light', 'Flexible')

# Countries Mercor says it cannot onboard or pay (talent.docs.mercor.com/policies/supported-countries, read 2026-11-18).
# Mercor also excludes any country missing from its supported list, so treat this as a minimum.
UNSUPPORTED = {'LB', 'IQ', 'IR', 'SY', 'PS', 'PK', 'KZ', 'GE', 'CN', 'HK', 'KE', 'RU', 'UA', 'CU', 'KP', 'BY'}

# Mercor stores eligible countries as ISO-3 codes; AI Ark filters on country names and LinkedIn returns ISO-2.
ISO3 = {'USA': ('US', 'United States'), 'GBR': ('GB', 'United Kingdom'), 'CAN': ('CA', 'Canada'), 'IRL': ('IE', 'Ireland'),
        'DEU': ('DE', 'Germany'), 'FRA': ('FR', 'France'), 'NLD': ('NL', 'Netherlands'), 'ESP': ('ES', 'Spain'),
        'PRT': ('PT', 'Portugal'), 'ITA': ('IT', 'Italy'), 'POL': ('PL', 'Poland'), 'IND': ('IN', 'India'),
        'AUS': ('AU', 'Australia'), 'NZL': ('NZ', 'New Zealand'), 'BRA': ('BR', 'Brazil'), 'MEX': ('MX', 'Mexico'),
        'SGP': ('SG', 'Singapore'), 'JPN': ('JP', 'Japan'), 'KOR': ('KR', 'South Korea'), 'ZAF': ('ZA', 'South Africa'),
        'CHE': ('CH', 'Switzerland'), 'PER': ('PE', 'Peru'), 'ISR': ('IL', 'Israel'), 'ARE': ('AE', 'United Arab Emirates')}


def low_commitment_roles():
    return [r for r in load_listings() if r['load'] in LOW and r['ref']]


def min_years(text):
    m = re.search(r'(\d{1,2})\+?\s*(?:or more\s+)?years', text or '', re.I)
    return int(m.group(1)) if m else 0


def profile_for(role):
    """Search/match profile for a listing: the curated one if present, else derived from the listing."""
    base = PROFILES.get(role['id'])
    if base is None:
        core = re.sub(r'\s*[\(–—-].*$', '', role['title']).replace(' Expert', '').strip()
        base = {'label': role['title'], 'field': core, 'titles': [core], 'seniority': [],
                'min_years': min_years(role['text']), 'keywords': [w.lower() for w in re.findall(r'[A-Za-z&+]{3,}', core)],
                'pitch': f'flexible {core} work evaluating AI models', 'generated': True}
    p = dict(base)
    p['role'] = role
    codes = [ISO3[c] for c in role['eligible'] if c in ISO3]
    p['countries_iso2'] = [c[0] for c in codes]
    p['countries'] = [c[1] for c in codes]
    return p


def find_role(key):
    roles = load_listings()
    hit = [r for r in roles if r['id'] == key] or [r for r in roles if key.lower() in r['title'].lower()]
    if not hit:
        raise SystemExit(f'No Mercor listing matches "{key}". Run: python3 outreach/run.py roles')
    return hit[0]


if __name__ == '__main__':
    for r in sorted(low_commitment_roles(), key=lambda r: -r['ref']):
        print(f"{r['id']}  ${r['ref']:>6,.0f}  {r['load']:<8} {r['pay']:<18} {r['geo']:<26} {r['title']}")
