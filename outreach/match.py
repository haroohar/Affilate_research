"""Step 3b: check a fetched LinkedIn profile against the role. Returns a score, a verdict and the reasons."""
import datetime, re
from roles import UNSUPPORTED

STRONG, POSSIBLE = 70, 45


def norm_url(u):
    m = re.search(r'linkedin\.com/in/([^/?#]+)', u or '', re.I)
    return m.group(1).lower().rstrip('/') if m else (u or '').lower()


def latest_job(profile):
    exp = profile.get('experience') or []
    return exp[0] if exp else {}


def career_years(profile):
    years = [((e.get('startDate') or {}).get('year')) for e in profile.get('experience') or []]
    years = [y for y in years if isinstance(y, int) and y > 1950]
    return datetime.date.today().year - min(years) if years else None


def evaluate(profile, role_profile):
    reasons, score = [], 0
    job = latest_job(profile)
    position = job.get('position') or ''
    headline = profile.get('headline') or ''
    title_text = f'{position} {headline}'.lower()
    blob = ' '.join([title_text, (profile.get('about') or '').lower(),
                     ' '.join((s.get('name') or '').lower() for s in profile.get('skills') or []),
                     ' '.join((e.get('description') or '').lower() for e in (profile.get('experience') or [])[:3])])

    otw = profile.get('openToWork')
    if otw is not True:
        return {'score': 0, 'verdict': 'Not open to work', 'reasons': ['LinkedIn profile does not show Open to Work'],
                'years': career_years(profile), 'position': position, 'company': job.get('companyName')}

    titles = [t.lower() for t in role_profile['titles']] + [role_profile['field'].lower()]
    hit = next((t for t in titles if t in title_text), None)
    if not hit:  # fall back to word overlap, e.g. "Senior Manager, FP&A" vs "FP&A Manager"
        words = {w for t in titles for w in re.findall(r'[a-z&+]{3,}', t)} - {'senior', 'manager', 'head', 'director'}
        hit = next((w for w in words if re.search(rf'(?<![a-z]){re.escape(w)}(?![a-z])', title_text)), None)
    if hit:
        score += 35; reasons.append(f'Title fits ("{hit}" in "{position or headline}")')
    else:
        reasons.append(f'Title does not obviously fit: "{position or headline}"')

    yrs, need = career_years(profile), role_profile.get('min_years') or 0
    if yrs is None:
        score += 10; reasons.append('Career length unknown')
    elif yrs >= need:
        score += 25; reasons.append(f'About {yrs} years of experience (role asks {need}+)')
    else:
        reasons.append(f'Only about {yrs} years of experience (role asks {need}+)')

    kws = [k for k in role_profile.get('keywords', []) if re.search(rf'(?<![a-z]){re.escape(k.lower())}(?![a-z])', blob)]
    score += min(len(kws), 3) * 10
    reasons.append('Relevant terms: ' + ', '.join(kws) if kws else 'No role keywords found in profile')

    cc = ((profile.get('location') or {}).get('countryCode') or '').upper()
    allowed = role_profile.get('countries_iso2') or []
    if cc in UNSUPPORTED or (allowed and cc and cc not in allowed):
        return {'score': score, 'verdict': 'Wrong country', 'years': yrs, 'position': position, 'company': job.get('companyName'),
                'reasons': reasons + [f'Located in {cc}, which this role or Mercor does not accept']}
    if cc:
        score += 10; reasons.append(f'Located in {cc}')
    else:
        reasons.append('Country not shown; check before sending')

    verdict = 'Strong match' if score >= STRONG else 'Possible match' if score >= POSSIBLE else 'Weak match'
    return {'score': score, 'verdict': verdict, 'reasons': reasons, 'years': yrs,
            'position': position, 'company': job.get('companyName')}
