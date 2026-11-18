"""Offline checks for the matcher, the notes and the AI Ark request. Profiles below are made up.

  python3 outreach/test_outreach.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roles, clients, match, notes  # noqa: E402

PROF = roles.profile_for(roles.find_role('list_AAABoddaxN8U-VxGZ5BD-Y_n'))  # FP&A Expert
PERSON = {'linkedin': 'https://www.linkedin.com/in/example-fpa', 'first_name': 'Dana', 'name': 'Dana Example'}


def fake_profile(open_to_work=True, position='Senior Manager, FP&A', start=2014, country='IL'):
    return {'firstName': 'Dana', 'lastName': 'Example', 'linkedinUrl': PERSON['linkedin'], 'openToWork': open_to_work,
            'headline': 'FP&A leader | Forecasting & budgeting', 'about': 'Built the financial model and variance reporting.',
            'location': {'countryCode': country},
            'skills': [{'name': 'Financial Planning'}, {'name': 'Budgeting'}],
            'experience': [{'position': position, 'companyName': 'Acme Widgets', 'startDate': {'year': 2021}},
                           {'position': 'Financial Analyst', 'companyName': 'Old Co', 'startDate': {'year': start}}]}


def test_strong_match():
    ev = match.evaluate(fake_profile(), PROF)
    assert ev['verdict'] == 'Strong match', ev
    assert ev['company'] == 'Acme Widgets'


def test_not_open_to_work():
    assert match.evaluate(fake_profile(open_to_work=False), PROF)['verdict'] == 'Not open to work'


def test_unsupported_country():
    assert match.evaluate(fake_profile(country='PK'), PROF)['verdict'] == 'Wrong country'


def test_wrong_field_is_weak():
    p = fake_profile(position='Barista', start=2023)
    p.update(headline='Coffee lover', about='', skills=[])
    p['experience'] = p['experience'][:1]
    assert match.evaluate(p, PROF)['verdict'] == 'Weak match'


def test_note_fits_limits():
    lp = fake_profile()
    ev = match.evaluate(lp, PROF)
    for limit in (200, 300):
        n = notes.connection_note(PERSON, lp, PROF, ev, limit)
        assert len(n) <= limit and n.startswith('Hi Dana') and 'http' not in n, n
    assert 'referral bonus' in notes.follow_up(PERSON, lp, PROF, 'https://work.mercor.com/x?referralCode=abc')


def test_ai_ark_body():
    b = clients.ai_ark_body(PROF, 25)
    assert b['contact']['profileBadge'] == {'any': {'include': ['OPEN_TO_WORK']}}
    assert 'Pakistan' in b['contact']['location']['any']['exclude'] and b['size'] == 25


def test_full_run_offline():
    """Steps 2-4, tracker, report and mark, with both APIs replaced by made-up data."""
    import tempfile, types, run
    tmp = tempfile.mkdtemp()
    run.OUT, run.TRACKER = tmp, os.path.join(tmp, 'tracker.csv')
    good = fake_profile()
    off = fake_profile(open_to_work=False)
    off['linkedinUrl'] = 'https://www.linkedin.com/in/example-closed'
    clients.ai_ark_search = lambda prof, size: {'total': 2, 'people': [
        PERSON, {'linkedin': off['linkedinUrl'], 'first_name': 'Sam', 'name': 'Sam Example'}]}
    clients.apify_profiles = lambda urls: [good, off]
    args = types.SimpleNamespace(urls=None, limit=10, refresh=True, max_chars=200, referral_link=None)
    tracker = {}
    run.run_role(roles.find_role('FP&A Expert'), args, tracker)
    run.save_tracker(tracker)
    t = run.load_tracker()
    assert t['example-fpa']['status'] == 'to_send' and t['example-fpa']['note'], t['example-fpa']
    assert t['example-closed']['status'] == 'skip' and not t['example-closed']['note']
    assert 'Copy note' in open(run.write_report(t)).read()
    # the same person turned up for another role is not checked or contacted again
    new, skipped = run.run_role(roles.find_role('Accounting Expert'), args, t)
    assert skipped == 2 and new == 0
    run.cmd_mark(types.SimpleNamespace(who=PERSON['linkedin'], status='note_sent'))
    assert run.load_tracker()['example-fpa']['status'] == 'note_sent'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
        print('ok  ', t.__name__)
    lp = fake_profile()
    ev = match.evaluate(lp, PROF)
    print('\nExample (made-up profile):', ev['verdict'], ev['score'], ev['reasons'])
    for limit in (200, 300):
        n = notes.connection_note(PERSON, lp, PROF, ev, limit)
        print(f'\n{limit}-char note ({len(n)}): {n}')
    print('\nFollow-up:\n' + notes.follow_up(PERSON, lp, PROF))
