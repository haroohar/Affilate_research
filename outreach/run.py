"""Referral outreach pipeline for low-commitment Mercor roles.

  python3 outreach/run.py roles                         # step 1: list low-commitment roles with a referral reward
  python3 outreach/run.py find "FP&A Expert" --limit 25 # steps 2-4 for one role
  python3 outreach/run.py find "FP&A Expert" --urls my_list.txt   # skip AI Ark: use LinkedIn URLs you collected

Each step's raw result is cached in outreach/outputs/<role>/, so re-running does not spend credits again
(pass --refresh to re-query). Output: candidates.csv and candidates.md with a note per person.
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roles, clients, match, notes  # noqa: E402


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


def cached(path, refresh, fn):
    if os.path.exists(path) and not refresh:
        return json.load(open(path, encoding='utf-8'))
    data = fn()
    json.dump(data, open(path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    return data


def cmd_roles(_):
    rs = sorted(roles.low_commitment_roles(), key=lambda r: -r['ref'])
    print(f'{len(rs)} low-commitment Mercor listings with a referral reward (highest reward first)\n')
    for r in rs:
        tag = '*' if r['id'] in roles.PROFILES else ' '
        print(f"{tag} ${r['ref']:>6,.0f}  {r['load']:<8} {r['pay']:<18} {r['geo']:<26} {r['title']}  [{r['id']}]")
    print('\n* = has a hand-tuned search profile in role_profiles.json; others get one generated from the listing.')


def cmd_find(a):
    role = roles.find_role(a.role)
    if role['load'] not in roles.LOW:
        print(f"Note: \"{role['title']}\" is {role['load']} ({role['hours'] or '?'} hrs/wk), not low commitment.")
    prof = roles.profile_for(role)
    out = os.path.join(HERE, 'outputs', slug(role['title']) + '-' + role['id'][-6:])
    os.makedirs(out, exist_ok=True)
    print(f"Role: {role['title']} | {role['pay']} | {role['load']} | referral up to ${role['ref']:,.0f}")
    if prof.get('generated'):
        print('  Using a search profile generated from the listing. Add one to role_profiles.json to tune it.')

    # Step 2: candidates with the Open to Work badge
    if a.urls:
        urls = [l.strip() for l in open(a.urls, encoding='utf-8') if 'linkedin.com/in/' in l]
        people = [{'linkedin': u, 'name': '', 'first_name': ''} for u in urls]
        print(f'Step 2: using {len(people)} LinkedIn URLs from {a.urls} (AI Ark skipped)')
    else:
        print(f"Step 2: AI Ark search, Open to Work + titles {prof['titles'][:4]}... (up to {a.limit} results, 0.5 credits each)")
        res = cached(os.path.join(out, '1_ai_ark.json'), a.refresh, lambda: clients.ai_ark_search(prof, a.limit))
        people = res['people']
        print(f"  {res.get('total')} matches in AI Ark, {len(people)} pulled")
    if not people:
        print('No candidates found. Loosen the titles or seniority in role_profiles.json.')
        return

    # Step 3: full LinkedIn profiles, then verify Open to Work + fit
    urls = [p['linkedin'] for p in people]
    print(f'Step 3: Apify LinkedIn profiles for {len(urls)} people (about ${len(urls) * 0.004:.2f})')
    items = cached(os.path.join(out, '2_linkedin_profiles.json'), a.refresh, lambda: clients.apify_profiles(urls))
    by_url = {match.norm_url(i.get('linkedinUrl') or i.get('publicIdentifier')): i for i in items}

    rows = []
    for p in people:
        lp = by_url.get(match.norm_url(p['linkedin']))
        if not lp:
            rows.append({**p, 'verdict': 'Profile not returned', 'score': 0, 'reasons': ['Apify returned no profile'], 'note': ''})
            continue
        ev = match.evaluate(lp, prof)
        ok = ev['verdict'] in ('Strong match', 'Possible match')
        rows.append({
            **p, 'name': p.get('name') or f"{lp.get('firstName', '')} {lp.get('lastName', '')}".strip(),
            'linkedin': lp.get('linkedinUrl') or p['linkedin'], **ev,
            # Step 4: only for people worth contacting
            'note': notes.connection_note(p, lp, prof, ev, a.max_chars) if ok else '',
            'follow_up': notes.follow_up(p, lp, prof, a.referral_link) if ok else '',
        })
    rows.sort(key=lambda r: -r['score'])
    write(out, role, rows, a.max_chars)


def write(out, role, rows, max_chars):
    keys = ['verdict', 'score', 'name', 'linkedin', 'position', 'company', 'years', 'reasons', 'note', 'follow_up']
    with open(os.path.join(out, 'candidates.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(keys)
        for r in rows:
            w.writerow([' | '.join(r[k]) if isinstance(r.get(k), list) else r.get(k, '') for k in keys])
    good = [r for r in rows if r.get('note')]
    lines = [f"# {role['title']}: outreach list", '',
             f"{role['pay']} · {role['load']} · referral up to ${role['ref']:,.0f} · [listing]({role['url']})", '',
             f"{len(good)} of {len(rows)} candidates verified as open to work and a fit. "
             f"Notes are at most {max_chars} characters. Send each with a connection request, then send the follow-up "
             f"(with your referral link) only after they accept and say they're interested.", '']
    for r in good:
        lines += [f"## {r['name']} · {r['verdict']} ({r['score']})", f"{r['linkedin']}", '',
                  f"{r.get('position') or ''} at {r.get('company') or ''} · ~{r.get('years') or '?'} yrs", '',
                  *[f'- {x}' for x in r['reasons']], '',
                  f"**Connection note ({len(r['note'])} chars):**", '', f"> {r['note']}", '',
                  '**Follow-up after they accept:**', '', '> ' + r['follow_up'].replace('\n\n', '\n>\n> '), '']
    skipped = [r for r in rows if not r.get('note')]
    if skipped:
        lines += ['## Skipped', ''] + [f"- {r.get('name') or r['linkedin']}: {r['verdict']}" for r in skipped]
    open(os.path.join(out, 'candidates.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'Step 4: {len(good)} notes written ({len(skipped)} skipped)\n  {out}/candidates.md\n  {out}/candidates.csv')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('roles', help='list low-commitment roles')
    f = sub.add_parser('find', help='search, verify and write notes for one role')
    f.add_argument('role', help='Mercor listing ID or part of its title')
    f.add_argument('--limit', type=int, default=25, help='AI Ark results to pull (max 100, 0.5 credits each)')
    f.add_argument('--urls', help='text file of LinkedIn profile URLs to use instead of AI Ark')
    f.add_argument('--max-chars', type=int, default=notes.DEFAULT_MAX, help='note length: 200 free LinkedIn, 300 Premium')
    f.add_argument('--referral-link', help='your Mercor referral link for this role (goes in the follow-up)')
    f.add_argument('--refresh', action='store_true', help='re-query AI Ark and Apify instead of using cached results')
    a = ap.parse_args()
    try:
        (cmd_roles if a.cmd == 'roles' else cmd_find)(a)
    except clients.ApiError as e:
        sys.exit(f'Stopped: {e}')


if __name__ == '__main__':
    main()
