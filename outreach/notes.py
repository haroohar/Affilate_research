"""Step 4: the connection-request note, and the follow-up message to send once they accept.

The note carries no link: Mercor's referral terms require consent-based outreach, so the referral link goes
only in the follow-up, after the person has accepted and shown interest.
"""
import re

# LinkedIn allows 300 characters on Premium and 200 on free accounts.
DEFAULT_MAX = 200


def rate_text(role):
    if role['freq'] == 'hourly' and role['rmax']:
        lo, hi = role['rmin'] or role['rmax'], role['rmax']
        return f'${lo:,.0f}/hr' if lo == hi else f'${lo:,.0f}-{hi:,.0f}/hr'
    return 'paid per task'


def hours_text(role):
    if role['hours'] and role['hours'] <= 10:
        return f"~{role['hours']} hrs/wk"
    return 'flexible hours' if role['load'] == 'Flexible' else 'low hours'


def first_name(person, profile):
    n = (profile or {}).get('firstName') or person.get('first_name') or (person.get('name') or '').split(' ')[0]
    return n.strip().split(' ')[0].title() if n else 'there'


def clean_position(pos):
    return re.sub(r'\s+', ' ', re.split(r'\s[|@•]\s', pos or '')[0]).strip()[:45]


def connection_note(person, profile, role_profile, ev, max_chars=DEFAULT_MAX):
    role = role_profile['role']
    name, pos, co = first_name(person, profile), clean_position(ev.get('position')), (ev.get('company') or '').strip()
    field, rate, hrs = role_profile['field'], rate_text(role), hours_text(role)
    variants = [
        f"Hi {name}, your {field} background stood out. I refer experienced pros to paid, remote AI-training projects ({rate}, {hrs}). Open to hearing more?",
        f"Hi {name}, I refer {field} pros to paid, remote AI-training work ({rate}, {hrs}). Your background fits. Interested in details?",
        f"Hi {name}, I refer {field} pros to paid remote AI-training work ({rate}). Interested?",
    ]
    if pos and co:  # most personal version first, used only when we know their job and company
        variants.insert(0, f"Hi {name}, your {pos} work at {co} stood out. I refer experienced {field} pros to paid, "
                           f"remote AI-training projects ({rate}, {hrs}). Open to hearing more?")
    return next((v for v in variants if len(v) <= max_chars), variants[-1][:max_chars])


def follow_up(person, profile, role_profile, referral_link=None):
    role = role_profile['role']
    link = referral_link or '[paste your Mercor referral link for this role]'
    return (f"Thanks for connecting, {first_name(person, profile)}! The role is \"{role['title']}\" on Mercor, which runs paid "
            f"AI-training projects. It pays {rate_text(role)} and is remote with {hours_text(role)}. You'd use your "
            f"{role_profile['field']} judgement to review and improve AI answers.\n\n"
            f"If you'd like to apply, sign up through this link and confirm me as your referrer when asked: {link}\n\n"
            f"To be upfront: I'm an independent referrer, not Mercor staff, and Mercor pays me a referral bonus if you're "
            f"placed. No pressure at all, and happy to answer questions.")
