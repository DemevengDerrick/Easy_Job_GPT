from datetime import date, timedelta

import pytest

from jobfinder import db, digest, notify
from jobfinder.models import UN, Job

TODAY = date.today()


def job(title, days_ago=0, **kw):
    return Job(
        title=title,
        url=f"https://example.org/{title.replace(' ', '-')}",
        organization="WHO",
        source="WHO",
        org_type=UN,
        posted_at=TODAY - timedelta(days=days_ago),
        **kw,
    )


@pytest.fixture
def eng(tmp_path):
    db.engine.cache_clear()
    return db.engine(f"sqlite:///{tmp_path / 'test.db'}")


def test_subscription_lifecycle(eng):
    token = db.create_subscription(" Me@Example.org ", {"keywords": ["GIS"]}, eng)
    sub = db.get_subscription(token, eng)
    assert sub["email"] == "me@example.org" and not sub["confirmed"]
    assert db.confirmed_subscriptions(eng) == []
    db.confirm(token, eng)
    assert [s["token"] for s in db.confirmed_subscriptions(eng)] == [token]
    assert db.update_filters(token, {"keywords": ["data"]}, eng)
    assert db.get_subscription(token, eng)["filters"] == {"keywords": ["data"]}
    assert db.unsubscribe(token, eng) and db.get_subscription(token, eng) is None
    assert not db.unsubscribe(token, eng)


def test_subscription_validation(eng):
    with pytest.raises(ValueError):
        db.create_subscription("not-an-email", {"keywords": ["GIS"]}, eng)
    with pytest.raises(ValueError):
        db.create_subscription("a@b.org", {"keywords": []}, eng)
    for _ in range(db.MAX_ALERTS_PER_EMAIL):
        db.create_subscription("a@b.org", {"keywords": ["GIS"]}, eng)
    with pytest.raises(ValueError):
        db.create_subscription("a@b.org", {"keywords": ["GIS"]}, eng)


def test_select_new_respects_filters_and_sent():
    jobs = [job("GIS Officer"), job("GIS Analyst", 1), job("Driver"), job("GIS Lead", deadline=TODAY - timedelta(days=1))]
    sub = {"filters": {"keywords": ["GIS"]}}
    shown, ids, total = digest.select_new(jobs, sub, sent_ids={jobs[1].id})
    assert [j.title for j in shown] == ["GIS Officer"] and total == 1 and ids == [jobs[0].id]


def test_select_new_caps_email_but_marks_everything(monkeypatch):
    monkeypatch.setattr(digest, "MAX_JOBS_PER_EMAIL", 2)
    jobs = [job(f"GIS Officer {i}", i) for i in range(5)]
    shown, ids, total = digest.select_new(jobs, {"filters": {"keywords": ["GIS"]}}, set())
    assert len(shown) == 2 and total == 5 and len(ids) == 5
    assert shown[0].title == "GIS Officer 0"  # newest first


def test_run_sends_once_then_nothing_new(eng, monkeypatch):
    token = db.create_subscription("me@example.org", {"keywords": ["GIS"]}, eng)
    db.confirm(token, eng)
    jobs = [job("GIS Officer"), job("Driver")]
    fetched_keywords, sent = [], []
    monkeypatch.setattr(digest, "fetch_jobs", lambda kws: (fetched_keywords.append(kws) or jobs, []))
    monkeypatch.setattr(notify, "send_digest", lambda sub, shown, total: sent.append((sub["email"], total)))

    assert digest.run(eng=eng) == {"subscriptions": 1, "emails": 1}
    assert sent == [("me@example.org", 1)] and fetched_keywords == [["GIS"]]
    assert db.get_subscription(token, eng)["last_sent_at"] is not None

    assert digest.run(eng=eng) == {"subscriptions": 1, "emails": 0}  # nothing new the second day
    jobs.append(job("GIS Specialist"))
    digest.run(eng=eng)
    assert sent[-1] == ("me@example.org", 1)


def test_failed_send_is_not_recorded(eng, monkeypatch):
    token = db.create_subscription("me@example.org", {"keywords": ["GIS"]}, eng)
    db.confirm(token, eng)
    monkeypatch.setattr(digest, "fetch_jobs", lambda kws: ([job("GIS Officer")], []))

    def boom(*a):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(notify, "send_digest", boom)
    assert digest.run(eng=eng)["emails"] == 0
    assert db.sent_job_ids(db.get_subscription(token, eng)["id"], eng) == set()


def test_dry_run_records_nothing(eng, monkeypatch, capsys):
    token = db.create_subscription("me@example.org", {"keywords": ["GIS"]}, eng)
    db.confirm(token, eng)
    monkeypatch.setattr(digest, "fetch_jobs", lambda kws: ([job("GIS Officer")], []))
    digest.run(dry_run=True, eng=eng)
    assert "GIS Officer" in capsys.readouterr().out
    assert db.sent_job_ids(db.get_subscription(token, eng)["id"], eng) == set()


def test_digest_email_escapes_and_links(monkeypatch):
    monkeypatch.setenv("APP_URL", "https://jobs.example.app/")
    sub = {"token": "tok", "email": "me@example.org", "filters": {"keywords": ["GIS"]}}
    html = notify.digest_html([job("GIS <script>")], sub, 3)
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "https://jobs.example.app/?action=unsubscribe&amp;token=tok" in html
    assert "and 2 more" in html
