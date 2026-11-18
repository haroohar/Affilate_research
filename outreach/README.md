# Referral outreach pipeline

Finds people for low-commitment Mercor roles and drafts a LinkedIn note for each one.

1. **Pick a role.** `python3 outreach/run.py roles` lists low-commitment Mercor listings (up to 10 hrs/week, per-task, or no hours stated) that pay a referral reward. Data comes from `mercor_jobs/mercor_jobs.json`; refresh it with `python3 mercor_jobs/scrape_mercor.py`.
2. **Find candidates.** AI Ark people search with the `OPEN_TO_WORK` badge, the role's job titles and seniority, leaving out countries Mercor can't pay. Costs 0.5 AI Ark credits per result. API access needs AI Ark's Builder or Scale plan.
3. **Verify.** Apify's `harvestapi/linkedin-profile-scraper` fetches each LinkedIn profile (about $0.004 each; Apify's free tier allows 200 profiles in total). `match.py` keeps people whose profile shows `openToWork: true` and scores the fit: job title, years of experience, role keywords, and country.
4. **Write the note.** For each strong or possible match: a connection note (200 characters by default, `--max-chars 300` for Premium) with no link, plus a follow-up to send after they accept. The follow-up carries your referral link and says you get a referral bonus. That keeps the outreach consent-based, as Mercor's referral terms require.

```bash
export AI_ARK_TOKEN=...   # app.ai-ark.com, API Management
export APIFY_TOKEN=...    # console.apify.com, Settings, API & Integrations
python3 outreach/run.py find "FP&A Expert" --limit 25 --referral-link "https://work.mercor.com/jobs/...?referralCode=..."
```

No AI Ark API plan? Export or copy LinkedIn URLs from the AI Ark web app (Open to Work filter) into a text file, one per line, and run `--urls file.txt`. Steps 3 and 4 run the same way.

Results go to `outreach/outputs/<role>/candidates.md` and `candidates.csv`. That folder is git-ignored because it holds personal data. Raw API responses are cached there too, so re-running doesn't spend credits again; pass `--refresh` to re-query.

Search titles, keywords and minimum years for each role live in `role_profiles.json`. Roles without an entry get a profile generated from the listing title, which is rougher; add an entry to tune it.

Run the offline checks with `python3 outreach/test_outreach.py` (made-up profiles, no API calls).
