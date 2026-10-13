"""Daily digest: fetch once for all subscribers, email each one only jobs they haven't seen."""
import logging

from . import db, notify
from .filters import JobFilter, sort_jobs
from .search import fetch_jobs

log = logging.getLogger(__name__)

MAX_JOBS_PER_EMAIL = 50


def select_new(jobs, sub, sent_ids, today=None):
    """Return (jobs to show, ids to mark as sent, number of new jobs).

    Every new match is marked as sent, even past the email cap, so a big
    backlog (e.g. on the first digest) doesn't trickle out over weeks.
    """
    matches = JobFilter.from_dict(sub["filters"]).apply(jobs, today)
    new = sort_jobs([j for j in matches if j.id not in sent_ids])
    return new[:MAX_JOBS_PER_EMAIL], list(dict.fromkeys(j.id for j in new)), len(new)


def run(dry_run=False, eng=None):
    eng = eng or db.engine()
    db.cleanup(eng)
    subs = db.confirmed_subscriptions(eng)
    if not subs:
        log.info("No confirmed subscriptions.")
        return {"subscriptions": 0, "emails": 0}

    keywords = list(dict.fromkeys(k for s in subs for k in s["filters"].get("keywords", [])))
    jobs, statuses = fetch_jobs(keywords)
    for s in statuses:
        log.info("%-22s %s %5d %s", s.name, "OK " if s.ok else "ERR", s.count, s.error)

    sent = 0
    for sub in subs:
        shown, ids, total = select_new(jobs, sub, db.sent_job_ids(sub["id"], eng))
        if not total:
            log.info("%s: nothing new", sub["email"])
            continue
        if dry_run:
            print(f"\n=== {sub['email']} — {total} new ===\n{notify.digest_text(shown, sub, total)}")
            continue
        try:
            notify.send_digest(sub, shown, total)
        except Exception as exc:  # keep going for the other subscribers
            log.error("%s: sending failed: %s", sub["email"], exc)
            continue
        db.record_sent(sub["id"], ids, eng)
        sent += 1
        log.info("%s: sent %d jobs", sub["email"], total)
    return {"subscriptions": len(subs), "emails": sent}
