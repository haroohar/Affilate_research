"""Referral outreach pipeline for low-commitment Mercor roles.

  python3 outreach/run.py check                          # confirm the AI Ark and Apify keys work (free)
  python3 outreach/run.py roles                          # step 1: low-commitment roles with a referral reward
  python3 outreach/run.py find "FP&A Expert" --limit 25  # steps 2-4 for one role
  python3 outreach/run.py find "FP&A Expert" --urls my_list.txt   # skip AI Ark: LinkedIn URLs you collected
  python3 outreach/run.py batch --focus finance --limit 10        # several roles; shows the cost, add --yes to run
  python3 outreach/run.py mark linkedin.com/in/someone accepted   # record where each person is
  python3 outreach/run.py tracker                        # counts by status and role
  python3 outreach/run.py report                         # rebuild outputs/report.html

Everything lands in outreach/outputs/ (git-ignored: it holds personal data). Raw API results are cached per
role, so re-running does not spend credits again; pass --refresh to re-query.
"""
import argparse, csv, datetime, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roles, clients, match, notes  # noqa: E402

OUT = os.path.join(HERE, 'outputs')
TRACKER = os.path.join(OUT, 'tracker.csv')
STATUSES = ['to_send', 'note_sent', 'accepted', 'interested', 'link_sent', 'signed_up', 'placed',
            'no_reply', 'declined', 'skip']
FIELDS = ['key', 'status', 'updated', 'role_id', 'role_title', 'verdict', 'score', 'name', 'linkedin',
          'position', 'company', 'years', 'reasons', 'check', 'note', 'follow_up']
AI_ARK_COST, APIFY_COST = 0.5, 0.004


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


def today():
    return datetime.date.today().isoformat()


def cached(path, refresh, fn):
    if os.path.exists(path) and not refresh:
        return json.load(open(path, encoding='utf-8'))
    data = fn()
    json.dump(data, open(path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    return data


# ---------- tracker: one row per person across all roles ----------

def load_tracker():
    if not os.path.exists(TRACKER):
        return {}
    return {r['key']: r for r in csv.DictReader(open(TRACKER, encoding='utf-8'))}


def save_tracker(rows):
    os.makedirs(OUT, exist_ok=True)
    with open(TRACKER, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: (r['role_title'], -int(r['score'] or 0))):
            w.writerow({k: r.get(k, '') for k in FIELDS})


def as_text(v):
    return ' | '.join(v) if isinstance(v, list) else ('' if v is None else str(v))


# ---------- commands ----------

def cmd_check(_):
    for name, msg in clients.check_keys().items():
        print(f'{name:7} {msg}')


def cmd_roles(_):
    rs = sorted(roles.low_commitment_roles(), key=lambda r: -r['ref'])
    print(f'{len(rs)} low-commitment Mercor listings with a referral reward (highest reward first)\n')
    for r in rs:
        tag = '*' if r['id'] in roles.PROFILES else ' '
        print(f"{tag} ${r['ref']:>6,.0f}  {r['load']:<8} {r['pay']:<18} {r['geo']:<26} {r['title']}  [{r['id']}]")
    print('\n* = hand-tuned search profile in role_profiles.json; others get one generated from the listing.')


def run_role(role, a, tracker):
    """Steps 2-4 for one role. Updates tracker in place and returns (new, skipped) counts."""
    if role['load'] not in roles.LOW:
        print(f"  Note: this role is {role['load']} ({role['hours'] or '?'} hrs/wk), not low commitment.")
    prof = roles.profile_for(role)
    out = os.path.join(OUT, slug(role['title']) + '-' + role['id'][-6:])
    os.makedirs(out, exist_ok=True)
    print(f"\n== {role['title']} | {role['pay']} | {role['load']} | referral up to ${role['ref']:,.0f}")
    if prof.get('generated'):
        print('  Search profile generated from the listing; add one to role_profiles.json to tune it.')

    # Step 2: Open to Work candidates
    if getattr(a, 'urls', None):
        people = [{'linkedin': l.strip(), 'name': '', 'first_name': ''}
                  for l in open(a.urls, encoding='utf-8') if 'linkedin.com/in/' in l]
        print(f'  Step 2: {len(people)} LinkedIn URLs from {a.urls} (AI Ark skipped)')
    else:
        res = cached(os.path.join(out, '1_ai_ark.json'), a.refresh, lambda: clients.ai_ark_search(prof, a.limit))
        people = res['people']
        print(f"  Step 2: AI Ark found {res.get('total')} open-to-work matches, pulled {len(people)}")

    # Don't pay to re-check, or re-contact, anyone already in the tracker (Mercor pays one referral per person).
    fresh, already = [], []
    for p in people:
        t = tracker.get(match.norm_url(p['linkedin']))
        (already if t and t['role_id'] != role['id'] else fresh).append(p)
    for p in already:
        print(f"  - skip {p.get('name') or p['linkedin']}: already in tracker for {tracker[match.norm_url(p['linkedin'])]['role_title']}")
    if not fresh:
        print('  No new candidates.')
        return 0, len(already)

    # Step 3: LinkedIn profiles, then verify Open to Work and fit
    urls = [p['linkedin'] for p in fresh]
    print(f'  Step 3: Apify LinkedIn profiles for {len(urls)} people (about ${len(urls) * APIFY_COST:.2f})')
    items = cached(os.path.join(out, '2_linkedin_profiles.json'), a.refresh, lambda: clients.apify_profiles(urls))
    by_url = {match.norm_url(i.get('linkedinUrl') or i.get('publicIdentifier')): i for i in items}

    new = 0
    for p in fresh:
        key = match.norm_url(p['linkedin'])
        lp = by_url.get(key)
        ev = match.evaluate(lp, prof) if lp else {'verdict': 'Profile not returned', 'score': 0,
                                                    'reasons': ['Apify returned no profile'], 'check': []}
        ok = ev['verdict'] in ('Strong match', 'Possible match')
        prev = tracker.get(key, {})
        tracker[key] = {
            'key': key, 'role_id': role['id'], 'role_title': role['title'],
            'status': prev.get('status') or ('to_send' if ok else 'skip'), 'updated': today(),
            'verdict': ev['verdict'], 'score': ev['score'],
            'name': p.get('name') or (f"{lp.get('firstName', '')} {lp.get('lastName', '')}".strip() if lp else ''),
            'linkedin': (lp or {}).get('linkedinUrl') or p['linkedin'],
            'position': ev.get('position') or '', 'company': ev.get('company') or '', 'years': ev.get('years') or '',
            'reasons': as_text(ev['reasons']), 'check': as_text(ev.get('check')),
            # Step 4: notes only for people worth contacting
            'note': notes.connection_note(p, lp, prof, ev, a.max_chars) if ok else '',
            'follow_up': notes.follow_up(p, lp, prof, a.referral_link) if ok else '',
        }
        new += ok and not prev
    good = sum(1 for r in tracker.values() if r['role_id'] == role['id'] and r['note'])
    print(f'  Step 4: {good} people with notes for this role ({new} new)')
    return new, len(already)


def cmd_find(a):
    tracker = load_tracker()
    run_role(roles.find_role(a.role), a, tracker)
    save_tracker(tracker)
    print(f'\nReport: {write_report(tracker)}\nTracker: {TRACKER}')


def cmd_batch(a):
    pool = roles.low_commitment_roles()
    if a.focus != 'all':
        pool = [r for r in pool if a.focus in r['focus']]
    if a.tuned_only:
        pool = [r for r in pool if r['id'] in roles.PROFILES]
    if a.open_only:
        pool = [r for r in pool if r['geo'] != 'US only']
    pool = sorted(pool, key=lambda r: -r['ref'])[:a.max_roles]
    credits = len(pool) * a.limit * AI_ARK_COST
    print(f'{len(pool)} roles, up to {a.limit} AI Ark results each.')
    print(f'Worst case: {credits:g} AI Ark credits and about ${len(pool) * a.limit * APIFY_COST:.2f} on Apify '
          f'(cached roles cost nothing).')
    for r in pool:
        print(f"  ${r['ref']:>6,.0f}  {r['pay']:<16} {r['geo']:<26} {r['title']}")
    if credits > a.max_credits:
        sys.exit(f'Stopped: that could use {credits:g} credits, over --max-credits {a.max_credits:g}. '
                 f'Lower --limit or --max-roles, or raise --max-credits.')
    if not a.yes:
        print('\nNothing was run. Add --yes to run these roles.')
        return
    tracker, new = load_tracker(), 0
    for r in pool:
        try:
            n, _ = run_role(r, a, tracker)
            new += n
        except clients.ApiError as e:
            print(f'  Stopped on this role: {e}')
            if 'HTTP 40' in str(e) and 'HTTP 404' not in str(e):
                break  # bad key, no plan access or no credits: the next roles would fail the same way
        save_tracker(tracker)
    print(f'\n{new} new people to contact.\nReport: {write_report(tracker)}\nTracker: {TRACKER}')


def cmd_mark(a):
    if a.status not in STATUSES:
        sys.exit(f'Unknown status "{a.status}". Use one of: {", ".join(STATUSES)}')
    tracker = load_tracker()
    key = match.norm_url(a.who)
    hits = [k for k in tracker if k == key] or [k for k, r in tracker.items() if a.who.lower() in r['name'].lower()]
    if len(hits) != 1:
        sys.exit(f'{"No" if not hits else len(hits)} tracker rows match "{a.who}". Use their LinkedIn URL.')
    tracker[hits[0]].update(status=a.status, updated=today())
    save_tracker(tracker)
    write_report(tracker)
    print(f"{tracker[hits[0]]['name']}: {a.status}")


def cmd_tracker(_):
    tracker = load_tracker()
    if not tracker:
        print('Tracker is empty. Run find or batch first.')
        return
    from collections import Counter
    print('By status:', dict(Counter(r['status'] for r in tracker.values())))
    for role, n in Counter(r['role_title'] for r in tracker.values()).most_common():
        st = Counter(r['status'] for r in tracker.values() if r['role_title'] == role)
        print(f'  {n:>3}  {role}: ' + ', '.join(f'{k} {v}' for k, v in st.items()))


def cmd_report(_):
    print(write_report(load_tracker()))


# ---------- report: one local page with every note ready to copy ----------

def write_report(tracker):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'report.html')
    rows = [r for r in tracker.values() if r['note']]
    groups = {}
    for r in sorted(rows, key=lambda r: -int(r['score'] or 0)):
        groups.setdefault(r['role_title'], []).append(r)
    e = html.escape
    cards = []
    for role, rs in groups.items():
        cards.append(f'<h2>{e(role)} <span>{len(rs)}</span></h2>')
        for r in rs:
            reasons = ''.join(f'<li>{e(x)}</li>' for x in r['reasons'].split(' | ') if x)
            check = ''.join(f'<li>{e(x)}</li>' for x in r['check'].split(' | ') if x)
            cards.append(f'''<article data-status="{e(r['status'])}">
  <header><div><b>{e(r['name'] or r['linkedin'])}</b> <i class="v">{e(r['verdict'])} · {e(str(r['score']))}</i>
  <div class="m">{e(r['position'])}{' at ' + e(r['company']) if r['company'] else ''}{' · ~' + e(str(r['years'])) + ' yrs' if r['years'] else ''}</div></div>
  <div class="r"><span class="st">{e(r['status'])}</span><a href="{e(r['linkedin'])}" target="_blank" rel="noopener">Open LinkedIn</a></div></header>
  <ul class="why">{reasons}</ul>{f'<p class="ck">Confirm before sending:</p><ul class="why">{check}</ul>' if check else ''}
  <label>Connection note <small>{len(r['note'])} chars</small></label><div class="txt">{e(r['note'])}</div><button type="button">Copy note</button>
  <label>Follow-up after they accept</label><div class="txt">{e(r['follow_up'])}</div><button type="button">Copy follow-up</button>
</article>''')
    body = ''.join(cards) or '<p>No candidates yet. Run <code>python3 outreach/run.py find "FP&amp;A Expert"</code>.</p>'
    counts = {s: sum(1 for r in tracker.values() if r['status'] == s) for s in STATUSES}
    summary = ' · '.join(f'{k.replace("_", " ")} {v}' for k, v in counts.items() if v)
    page = f'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Outreach notes</title>
<style>
:root{{--bg:#f5f6f3;--card:#fff;--ink:#18211d;--mut:#5c6862;--line:#dde2dc;--acc:#0d6b4f;color-scheme:light dark}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111613;--card:#182019;--ink:#e6ece8;--mut:#9aa8a0;--line:#2a352e;--acc:#5fcf9f}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,sans-serif}}
main{{max-width:860px;margin:0 auto;padding:24px max(16px,env(safe-area-inset-left))}}
h1{{margin:0}} h2{{margin:28px 0 8px;font-size:18px}} h2 span{{color:var(--mut);font-weight:400}}
.sum{{color:var(--mut)}} .bar{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}
.bar button,article button{{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:4px 10px;cursor:pointer}}
.bar button[aria-pressed=true]{{background:var(--acc);color:var(--card);border-color:var(--acc)}}
article{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:10px 0}}
header{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}} .v{{color:var(--acc);font-style:normal;font-size:12px}}
.m{{color:var(--mut);font-size:13px}} .r{{display:flex;gap:10px;align-items:center}} .r a{{color:var(--acc)}}
.st{{font-size:12px;border:1px solid var(--line);border-radius:4px;padding:1px 6px}}
.why{{margin:8px 0;padding-left:18px;color:var(--mut);font-size:13px}} .ck{{margin:6px 0 0;font-size:13px;font-weight:600}}
label{{display:block;margin-top:10px;font-weight:600;font-size:13px}} label small{{color:var(--mut);font-weight:400}}
.txt{{white-space:pre-wrap;border:1px solid var(--line);border-radius:6px;padding:8px;margin:4px 0;user-select:all}}
</style><main>
<h1>Outreach notes</h1><p class="sum">{len(rows)} people with notes · {e(summary)} · updated {today()}.
Send the note with a connection request. Send the follow-up, which has your referral link, only after they accept and show interest.
Record progress with <code>python3 outreach/run.py mark &lt;linkedin-url&gt; note_sent</code>.</p>
<div class="bar"><button type="button" data-f="" aria-pressed="true">All</button><button type="button" data-f="to_send" aria-pressed="false">To send</button>
<button type="button" data-f="note_sent" aria-pressed="false">Note sent</button><button type="button" data-f="accepted" aria-pressed="false">Accepted</button></div>
{body}</main>
<script>
document.addEventListener('click', ev => {{
  const b = ev.target.closest('article button');
  if (b) {{ const t = b.previousElementSibling.textContent;
    navigator.clipboard.writeText(t).then(() => {{ b.textContent = 'Copied'; setTimeout(() => b.textContent = b.textContent.replace('Copied', 'Copy again'), 1500); }}, () => {{}}); return; }}
  const f = ev.target.closest('[data-f]');
  if (f) {{ document.querySelectorAll('[data-f]').forEach(x => x.setAttribute('aria-pressed', x === f));
    document.querySelectorAll('article').forEach(a => a.hidden = !!f.dataset.f && a.dataset.status !== f.dataset.f); }}
}});
</script>'''
    open(path, 'w', encoding='utf-8').write(page)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check', help='confirm the API keys work (no credits used)')
    sub.add_parser('roles', help='list low-commitment roles')

    def role_opts(p):
        p.add_argument('--limit', type=int, default=25, help='AI Ark results per role (max 100, 0.5 credits each)')
        p.add_argument('--max-chars', type=int, default=notes.DEFAULT_MAX, help='note length: 200 free LinkedIn, 300 Premium')
        p.add_argument('--referral-link', help='your Mercor referral link (goes in the follow-up)')
        p.add_argument('--refresh', action='store_true', help='re-query AI Ark and Apify instead of using cached results')

    f = sub.add_parser('find', help='search, verify and write notes for one role')
    f.add_argument('role', help='Mercor listing ID or part of its title')
    f.add_argument('--urls', help='text file of LinkedIn profile URLs to use instead of AI Ark')
    role_opts(f)
    b = sub.add_parser('batch', help='run several low-commitment roles')
    b.add_argument('--focus', choices=['all', 'finance', 'tech'], default='all')
    b.add_argument('--tuned-only', action='store_true', help='only roles with a profile in role_profiles.json')
    b.add_argument('--open-only', action='store_true', help='skip US-only roles')
    b.add_argument('--max-roles', type=int, default=5)
    b.add_argument('--max-credits', type=float, default=100, help='refuse to run if the worst case is above this')
    b.add_argument('--yes', action='store_true', help='actually run (otherwise just show the plan and cost)')
    role_opts(b)
    m = sub.add_parser('mark', help='record outreach status for a person')
    m.add_argument('who', help='LinkedIn URL (or part of their name)')
    m.add_argument('status', help=' / '.join(STATUSES))
    sub.add_parser('tracker', help='show outreach counts')
    sub.add_parser('report', help='rebuild outputs/report.html')
    a = ap.parse_args()
    cmds = {'check': cmd_check, 'roles': cmd_roles, 'find': cmd_find, 'batch': cmd_batch, 'mark': cmd_mark,
            'tracker': cmd_tracker, 'report': cmd_report}
    try:
        cmds[a.cmd](a)
    except clients.ApiError as e:
        sys.exit(f'Stopped: {e}')


if __name__ == '__main__':
    main()
