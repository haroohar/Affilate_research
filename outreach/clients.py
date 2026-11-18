"""Steps 2 and 3: AI Ark people search (Open to Work) and Apify LinkedIn profile fetch.

Keys come from AI_ARK_TOKEN and APIFY_TOKEN. In a Claude cloud session the network proxy can inject them,
so a placeholder is sent when the variable is unset and the proxy swaps in the saved key.
"""
import json, os, time, urllib.error, urllib.request

AI_ARK = 'https://api.ai-ark.com/api/developer-portal/v1'
APIFY = 'https://api.apify.com/v2/acts/harvestapi~linkedin-profile-scraper/run-sync-get-dataset-items'
APIFY_MODE = 'Profile details no email ($4 per 1k)'

# Country names AI Ark should leave out (Mercor cannot pay people there).
UNSUPPORTED_NAMES = ['Lebanon', 'Iraq', 'Iran', 'Syria', 'Palestine', 'Pakistan', 'Kazakhstan', 'Georgia', 'China',
                     'Hong Kong', 'Kenya', 'Russia', 'Ukraine', 'Cuba', 'North Korea', 'Belarus']


class ApiError(RuntimeError):
    pass


def _post(url, body, headers, timeout=120):
    data = json.dumps(body).encode()
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method='POST',
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json', **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'replace')[:500]
            if e.code == 429 and attempt < 3:
                time.sleep(int(e.headers.get('Retry-After') or 5))
                continue
            hint = {401: 'The API key is missing or wrong.',
                    403: 'Access refused. AI Ark only allows API use on its Builder or Scale plans.',
                    402: 'Out of credits or prepaid usage.',
                    408: 'The Apify run took over 300 seconds. Use a smaller batch.'}.get(e.code, '')
            raise ApiError(f'{url} returned HTTP {e.code}. {hint} {detail}'.strip()) from None


def ai_ark_body(profile, size):
    contact = {
        'profileBadge': {'any': {'include': ['OPEN_TO_WORK']}},
        # "latest" rather than "current": many open-to-work people have just left their last job.
        'experience': {'latest': {'title': {'any': {'include': {'mode': 'SMART', 'content': profile['titles']}}}}},
    }
    if profile.get('seniority'):
        contact['seniority'] = {'any': {'include': profile['seniority']}}
    loc = {'exclude': UNSUPPORTED_NAMES}
    if profile.get('countries'):
        loc['include'] = profile['countries']
    contact['location'] = {'any': loc}
    return {'contact': contact, 'page': 0, 'size': size}


def ai_ark_search(profile, size=25):
    """People with the Open to Work badge whose latest title fits the role. Costs 0.5 credits per result."""
    token = os.environ.get('AI_ARK_TOKEN', 'proxy-injected')
    res = _post(f'{AI_ARK}/people', ai_ark_body(profile, min(max(size, 1), 100)), {'X-TOKEN': token})
    people = []
    for p in res.get('content') or []:
        prof, link, loc = p.get('profile') or {}, p.get('link') or {}, p.get('location') or {}
        people.append({
            'ai_ark_id': p.get('id'),
            'name': prof.get('full_name') or ' '.join(filter(None, [prof.get('first_name'), prof.get('last_name')])),
            'first_name': prof.get('first_name'),
            'headline': prof.get('headline'),
            'title': prof.get('title'),
            'linkedin': link.get('linkedin'),
            'country': loc.get('country'),
            'ai_ark_open_to_work': (p.get('member_badges') or {}).get('open_to_work'),
        })
    return {'total': res.get('totalElements'), 'people': [p for p in people if p['linkedin']]}


def apify_profiles(urls, batch=20):
    """Full LinkedIn profiles via harvestapi/linkedin-profile-scraper (about $0.004 each)."""
    token = os.environ.get('APIFY_TOKEN', 'proxy-injected')
    out = []
    for i in range(0, len(urls), batch):
        chunk = urls[i:i + batch]
        items = _post(f'{APIFY}?timeout=290', {'profileScraperMode': APIFY_MODE, 'queries': chunk},
                      {'Authorization': f'Bearer {token}'}, timeout=310)
        out.extend(items if isinstance(items, list) else [])
    return out
