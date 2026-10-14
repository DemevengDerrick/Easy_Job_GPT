# Easy Job Finder

Search open positions across the UN system, development banks, the African Union, humanitarian
organisations and reputable job boards in one place. Filter the results, and subscribe to a daily
email with **new** jobs that match your keywords.

http://easy-job-gpt.streamlit.app/

## Features

- **One search, many official sources.** Results come from official career-site APIs and feeds, not
  from scraping LinkedIn or Indeed.
- **Keyword matching**: whole words only (so `GIS` doesn't match "logistics"). Choose any or all
  keywords, add exclusion words, or match on titles only.
- **Filters**: location, remote/home-based, organisation type (UN, IFI, AU, NGO, job board,
  company), contract/grade (P/D, NO, G, consultant, internship, UNV), source, posting date, and
  hiding expired postings. You can sort by newest or closing soon and download results as CSV.
- **Daily email alerts** with double opt-in. Each alert is emailed at most once per job and
  includes links to edit or unsubscribe. A GitHub Actions cron job sends them.

## Sources

| Source | Covers | How |
|---|---|---|
| UN Careers | UN Secretariat, UNEP, OCHA, regional commissions… | public JSON API |
| UNDP, IOM | | Oracle Recruiting Cloud API |
| WHO, FAO, IAEA | | Taleo job-board API |
| WFP, UNHCR, IMF, Global Fund | | Workday API |
| World Bank Group (IBRD, IFC, MIGA…) | | Cornerstone career-site API |
| UNESCO, ILO, African Union | | SuccessFactors RSS |
| UNICEF | | career-site listing page (best effort, sometimes blocked by bot protection) |
| ReliefWeb | UNICEF, UNHCR, OCHA, NGOs and many more | API v2, needs `RELIEFWEB_APPNAME` |
| Adzuna, Jooble | general aggregators | APIs, need free keys |
| Remotive, Arbeitnow, Remote OK, We Work Remotely | remote jobs | public APIs / RSS |
| Greenhouse, Lever | companies listed in `jobfinder/sources.yaml` | public board APIs |

To add an organisation that uses Oracle, Taleo, Workday, Cornerstone or SuccessFactors, add one line to
[`jobfinder/sources.yaml`](jobfinder/sources.yaml). Each existing entry shows which IDs to copy from the
organisation's careers URL.

**Not supported yet:** the African Development Bank. afdb.org blocks automated access, and its
SuccessFactors page has no public feed. Some AfDB vacancies do reach ReliefWeb.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py                       # the web app
python -m jobfinder.search GIS "data analyst"   # live check of every source
python -m pytest                           # tests (offline, use saved fixtures)
```

Without any configuration, alerts are stored in a local `jobfinder.db` SQLite file. To send real
email, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill it in.

## Deploy

1. **Database:** create a free [Supabase](https://supabase.com) project. Copy the **Session pooler**
   connection string from Project Settings → Database. (GitHub runners only speak IPv4, so the direct
   connection won't work.) The tables are created automatically on first use.
2. **Email:** create a [Resend](https://resend.com) account, verify your sending domain, and create an
   API key.
3. **Streamlit Cloud:** set the app's main file to `app.py`, then paste your secrets in App settings →
   Secrets (see `.streamlit/secrets.toml.example`). Set `APP_URL` to the app's public URL.
4. **Daily emails:** in GitHub → Settings → Secrets and variables → Actions, add `DATABASE_URL`,
   `RESEND_API_KEY`, `MAIL_FROM` and `APP_URL`, plus any of `RELIEFWEB_APPNAME`, `ADZUNA_APP_ID`,
   `ADZUNA_APP_KEY`, `JOOBLE_KEY`. The workflow in `.github/workflows/daily-digest.yml` runs every day
   at 06:00 UTC. You can also run it by hand from the Actions tab, with a dry-run option.

## How the daily digest works

`scripts/daily_digest.py` loads every confirmed alert and fetches each source **once** for the
combined keywords of all alerts. It then applies each alert's filters and emails only jobs that alert
hasn't received before (at most 50 per email). It records what was sent, so a job never arrives twice.
Unconfirmed alerts are deleted after 7 days.

---
Derrick Demeveng | LinkedIn: www.linkedin.com/in/demeveng-derrick
