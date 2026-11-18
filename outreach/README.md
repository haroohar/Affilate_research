# Referral outreach pipeline

Finds people for low-commitment Mercor roles and writes a LinkedIn note for each one.

1. **Pick a role.** Low-commitment Mercor listings: up to 10 hrs/week, per task, or no hours stated, with a referral reward. Listing data comes from `mercor_jobs/mercor_jobs.json`; refresh it with `python3 mercor_jobs/scrape_mercor.py`.
2. **Find candidates.** AI Ark people search with the `OPEN_TO_WORK` badge, the role's job titles and seniority, leaving out countries Mercor can't pay. Costs 0.5 AI Ark credits per result, and API access needs AI Ark's Builder or Scale plan.
3. **Verify.** Apify's `harvestapi/linkedin-profile-scraper` fetches each LinkedIn profile (about $0.004 each; Apify's free tier allows 200 profiles in total). Only people whose profile shows `openToWork: true` go on, scored on job title, years of experience, role keywords, required credentials (PhD, MD, CPA, RN, bar) and country.
4. **Write the note.** For each strong or possible match: a connection note with no link (200 characters, or `--max-chars 300` on Premium), and a follow-up for after they accept. The follow-up has your referral link and says you get a referral bonus, which keeps the outreach consent-based, as Mercor's terms require.

## Setup (once)

```bash
cp outreach/.env.example outreach/.env    # then paste both keys into outreach/.env (git-ignored)
python3 outreach/run.py check             # free: confirms both keys work and shows AI Ark credits
```

## Use

```bash
python3 outreach/run.py roles                                 # pick a role (* = tuned search profile)
python3 outreach/run.py find "FP&A Expert" --limit 10 --referral-link "<your Mercor link for this role>"
python3 outreach/run.py batch --focus finance --tuned-only --limit 10        # shows the plan and cost only
python3 outreach/run.py batch --focus finance --tuned-only --limit 10 --yes  # runs it
```

Open `outreach/outputs/report.html`: every person with their match reasons, anything to confirm by hand, and Copy buttons for the note and the follow-up.

As you go, record each step:

```bash
python3 outreach/run.py mark https://www.linkedin.com/in/someone note_sent
```

The statuses are `to_send`, `note_sent`, `accepted`, `interested`, `link_sent`, `signed_up`, `placed`, `no_reply`, `declined` and `skip`. `python3 outreach/run.py tracker` shows the counts.

## Good to know

- **Without AI Ark's API plan:** filter for Open to Work in the AI Ark web app, save the LinkedIn URLs to a text file (one per line), and run `find "<role>" --urls file.txt`. Steps 3 and 4 work the same way.
- **One referral per person:** `outputs/tracker.csv` holds everyone across all roles. Anyone already there is skipped for other roles, so you don't pay to check them again or contact them twice. Mercor pays only one referral per person.
- **Costs:** `batch` refuses to run past `--max-credits` (default 100). Raw API results are cached under `outputs/<role>/`, so re-running costs nothing unless you pass `--refresh`.
- **Personal data:** `outputs/` is git-ignored because it holds personal data. Keep it that way.
- **Search profiles:** 24 roles have tuned search profiles in `role_profiles.json`, covering titles, seniority, minimum years, keywords, credentials and a manual checklist. Other roles get a rougher profile generated from the listing title.
- **Tests:** `python3 outreach/test_outreach.py` runs offline checks with made-up profiles and makes no API calls.
