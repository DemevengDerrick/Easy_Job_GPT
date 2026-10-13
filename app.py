import os
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Easy Job Finder", page_icon="🔭", layout="wide")

# Copy Streamlit secrets into the environment so worker threads can read them. Only touch
# st.secrets when a file exists: otherwise Streamlit renders a "No secrets found" error.
_SECRET_FILES = [Path.cwd() / ".streamlit" / "secrets.toml", Path.home() / ".streamlit" / "secrets.toml"]
if any(p.exists() for p in _SECRET_FILES):
    for _key, _value in st.secrets.items():
        if isinstance(_value, (str, int, float)) and _value != "":
            os.environ.setdefault(_key, str(_value))

from jobfinder import db, notify  # noqa: E402
from jobfinder.filters import JobFilter, parse_terms, sort_jobs  # noqa: E402
from jobfinder.models import GRADE_CATEGORIES, ORG_TYPES  # noqa: E402
from jobfinder.search import fetch_jobs  # noqa: E402
from jobfinder.sources import load_sources  # noqa: E402

LOGO = Path(__file__).parent / "img" / "image.png"
POSTED_WITHIN = {"Any time": None, "Last 24 hours": 1, "Last 3 days": 3, "Last week": 7, "Last 2 weeks": 14, "Last month": 30}


@st.cache_data(ttl=3600, show_spinner=False)
def search(keywords):
    return fetch_jobs(list(keywords))


@st.cache_data(show_spinner=False)
def source_names():
    return sorted({s.name for s in load_sources()}, key=str.lower)


def filter_controls(key, f):
    """Widgets for every filter except keywords; returns a JobFilter."""
    match_all = st.toggle("Require all keywords", f.match_all, key=f"{key}_all")
    title_only = st.toggle("Match job titles only", f.title_only, key=f"{key}_title")
    exclude = st.text_input("Exclude words", ", ".join(f.exclude), key=f"{key}_excl", placeholder="e.g. intern, driver")
    locations = st.text_input(
        "Locations", ", ".join(f.locations), key=f"{key}_loc", placeholder="e.g. Kenya, Geneva, remote"
    )
    remote_only = st.checkbox("Remote / home-based only", f.remote_only, key=f"{key}_remote")
    org_types = st.multiselect("Organisation type", ORG_TYPES, f.org_types, key=f"{key}_org")
    grades = st.multiselect("Contract / grade", GRADE_CATEGORIES, f.grade_categories, key=f"{key}_grade")
    sources = st.multiselect("Sources", source_names(), [s for s in f.sources if s in source_names()], key=f"{key}_src")
    labels = list(POSTED_WITHIN)
    current = next((l for l, d in POSTED_WITHIN.items() if d == f.posted_within_days), "Any time")
    posted = st.selectbox("Posted", labels, labels.index(current), key=f"{key}_posted")
    hide_expired = st.checkbox("Hide expired postings", f.hide_expired, key=f"{key}_expired")
    return JobFilter(
        keywords=f.keywords, match_all=match_all, exclude=parse_terms(exclude), title_only=title_only,
        locations=parse_terms(locations), remote_only=remote_only, org_types=org_types, sources=sources,
        grade_categories=grades, posted_within_days=POSTED_WITHIN[posted], hide_expired=hide_expired,
    )


def handle_link_actions():
    """Confirm / unsubscribe / manage links from the emails. Returns True if a page was shown."""
    action, token = st.query_params.get("action"), st.query_params.get("token")
    if not (action and token):
        return False
    try:
        sub = db.get_subscription(token)
    except Exception as exc:
        st.error(f"Subscriptions are unavailable right now: {exc}")
        return True
    if not sub:
        st.warning("This link is no longer valid. The alert may already have been removed.")
    elif action == "confirm":
        db.confirm(token)
        st.success(f"Your daily alert is active: **{notify.describe(sub['filters'])}**. "
                   "The first digest arrives with the next daily run.")
    elif action == "unsubscribe":
        db.unsubscribe(token)
        st.success("You're unsubscribed. You won't get any more emails for this alert.")
    elif action == "manage":
        st.subheader(f"Edit alert for {sub['email']}")
        current = JobFilter.from_dict(sub["filters"])
        with st.form("manage"):
            keywords = st.text_input("Keywords (comma-separated)", ", ".join(current.keywords))
            updated = filter_controls("manage", current)
            if st.form_submit_button("Save changes", type="primary"):
                updated.keywords = parse_terms(keywords)
                if not updated.keywords:
                    st.error("Please enter at least one keyword.")
                else:
                    db.update_filters(token, updated.to_dict())
                    st.success("Saved.")
        if st.button("Unsubscribe from this alert"):
            db.unsubscribe(token)
            st.success("You're unsubscribed.")
    else:
        return False
    if st.button("Go to job search"):
        st.query_params.clear()
        st.rerun()
    return True


def results_table(jobs):
    df = pd.DataFrame(
        {
            "Title": [j.title for j in jobs],
            "Organisation": [j.organization for j in jobs],
            "Location": [j.location for j in jobs],
            "Grade": [j.grade or j.grade_category for j in jobs],
            "Posted": [j.posted_at for j in jobs],
            "Deadline": [j.deadline for j in jobs],
            "Source": [j.source for j in jobs],
            "Link": [j.url for j in jobs],
        }
    )
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Link": st.column_config.LinkColumn("Link", display_text="Open ↗"),
            "Posted": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Deadline": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Title": st.column_config.TextColumn(width="large"),
        },
    )
    return df


# ---------------------------------------------------------------- page
col1, col2 = st.columns([1, 12])
with col1:
    if LOGO.exists():
        st.image(str(LOGO), width=73)
with col2:
    st.title("Easy Job Finder")

if not handle_link_actions():
    st.write(
        "Search open positions across the UN system, the World Bank, IMF, the African Union, "
        "humanitarian organisations and reputable job boards, then get new matches by email every day."
    )

    with st.sidebar:
        st.header("Filters")
        current_filter = filter_controls("search", JobFilter())

    with st.form("search"):
        keywords_text = st.text_input(
            "Keywords (comma-separated)", st.session_state.get("keywords", "GIS"),
            placeholder="e.g. GIS, data analyst, monitoring and evaluation",
        )
        st.form_submit_button("🔭 Search", type="primary")
    st.session_state["keywords"] = keywords_text
    current_filter.keywords = parse_terms(keywords_text)

    search_tab, alert_tab = st.tabs(["🔎 Results", "🔔 Daily email alert"])

    with search_tab:
        if not current_filter.keywords:
            st.info("Enter at least one keyword.")
        else:
            with st.spinner("Searching all sources… (about 30 seconds the first time)"):
                jobs, statuses = search(tuple(current_filter.keywords))
            sort_by = st.radio("Sort by", ["Newest", "Closing soon"], horizontal=True)
            shown = sort_jobs(current_filter.apply(jobs), "deadline" if sort_by == "Closing soon" else "newest")
            st.caption(f"{len(shown)} jobs match ({len(jobs)} found before filters).")
            df = results_table(shown)
            st.download_button("Download CSV", df.to_csv(index=False), "jobs.csv", "text/csv")
            failed = [s for s in statuses if not s.ok]
            with st.expander(f"Sources: {len(statuses) - len(failed)} answered, {len(failed)} unavailable"):
                st.dataframe(
                    pd.DataFrame([{"Source": s.name, "Status": "OK" if s.ok else "Unavailable",
                                   "Jobs fetched": s.count, "Details": s.error} for s in statuses]),
                    hide_index=True, use_container_width=True,
                )

    with alert_tab:
        st.write("Get one email a day with **new** jobs matching your current keywords and sidebar filters:")
        st.info(notify.describe(current_filter.to_dict()) if current_filter.keywords else "Enter keywords first.")
        with st.form("subscribe", clear_on_submit=True):
            email = st.text_input("Email address")
            if st.form_submit_button("Subscribe", type="primary"):
                token = None
                try:
                    token = db.create_subscription(email, current_filter.to_dict())
                    notify.confirmation_email(email.strip(), token, current_filter.to_dict())
                    st.success("Check your inbox and click the confirmation link to start your alert.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    if token:
                        db.unsubscribe(token)  # don't keep an alert nobody can confirm
                    st.error(f"Couldn't create the alert right now: {exc}")
        st.caption("You can edit or cancel the alert from the link at the bottom of every email.")

st.caption("Derrick Demeveng | LinkedIn: www.linkedin.com/in/demeveng-derrick")
