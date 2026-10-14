from datetime import date, timedelta

from jobfinder.filters import JobFilter, mentions, parse_terms, sort_jobs
from jobfinder.models import IFI, UN, Job, canonical_url, infer_grade
from jobfinder.search import dedupe

TODAY = date(2026, 10, 13)


def job(title, **kw):
    kw.setdefault("url", f"https://example.org/{title.replace(' ', '-')}")
    kw.setdefault("organization", "UNDP")
    kw.setdefault("source", "UNDP")
    kw.setdefault("org_type", UN)
    return Job(title=title, **kw)


def test_parse_terms():
    assert parse_terms("GIS, data analyst; GIS\nM&E ") == ["GIS", "data analyst", "M&E"]


def test_whole_word_matching():
    assert mentions("Senior GIS Officer", "gis")
    assert not mentions("Logistics Officer", "GIS")
    assert mentions("Data Analysts wanted", "data analyst")
    assert mentions("data   analyst", "Data Analyst")
    assert mentions("M&E Specialist", "M&E")


def test_keywords_any_all_and_title_only():
    j = job("GIS Officer", snippet="remote sensing and data analysis")
    assert JobFilter(keywords=["GIS", "python"]).matches(j, TODAY)
    assert not JobFilter(keywords=["GIS", "python"], match_all=True).matches(j, TODAY)
    assert JobFilter(keywords=["remote sensing"]).matches(j, TODAY)
    assert not JobFilter(keywords=["remote sensing"], title_only=True).matches(j, TODAY)


def test_exclude_location_remote_org_grade():
    j = job("GIS Officer, P-3", location="Nairobi, Kenya")
    assert not JobFilter(keywords=["GIS"], exclude=["officer"]).matches(j, TODAY)
    assert JobFilter(keywords=["GIS"], locations=["kenya"]).matches(j, TODAY)
    assert not JobFilter(keywords=["GIS"], locations=["Geneva"]).matches(j, TODAY)
    assert not JobFilter(keywords=["GIS"], remote_only=True).matches(j, TODAY)
    assert JobFilter(keywords=["GIS"], org_types=[UN]).matches(j, TODAY)
    assert not JobFilter(keywords=["GIS"], org_types=[IFI]).matches(j, TODAY)
    assert JobFilter(keywords=["GIS"], grade_categories=["Professional (P/D)"]).matches(j, TODAY)
    home = job("GIS Consultant", location="Home-based")
    assert home.remote and JobFilter(keywords=["GIS"], locations=["remote"]).matches(home, TODAY)
    assert home.grade_category == "Consultant"


def test_dates():
    old = job("GIS Officer", posted_at=TODAY - timedelta(days=10))
    undated = job("GIS Analyst")
    expired = job("GIS Lead", deadline=TODAY - timedelta(days=1))
    f = JobFilter(keywords=["GIS"], posted_within_days=7)
    assert not f.matches(old, TODAY) and f.matches(undated, TODAY)
    assert not f.matches(expired, TODAY)
    assert JobFilter(keywords=["GIS"], hide_expired=False).matches(expired, TODAY)


def test_filter_roundtrip_ignores_unknown_keys():
    f = JobFilter(keywords=["GIS"], locations=["Kenya"], posted_within_days=3)
    assert JobFilter.from_dict({**f.to_dict(), "legacy": 1}) == f


def test_grades():
    assert infer_grade("Programme Officer, P3") == "P-3"
    assert infer_grade("Partnerships Officer, NOC") == "NO-C"
    assert infer_grade("Driver, G-3") == "G-3"
    assert infer_grade("Chief, D 1") == "D-1"
    assert infer_grade("Data Analyst") == ""


def test_canonical_url_and_dedupe():
    a = job("GIS Officer", url="https://Jobs.example.org/job/1/?utm_source=rss&feedId=null")
    b = job("GIS Officer", url="https://jobs.example.org/job/1")
    c = job("GIS  officer", url="https://reliefweb.int/job/9")  # same title/org/location, other site
    assert canonical_url(a.url) == canonical_url(b.url) and a.id == b.id
    assert dedupe([a, b, c]) == [a]


def test_sort():
    a = job("A", posted_at=TODAY, deadline=TODAY + timedelta(days=30))
    b = job("B", posted_at=TODAY - timedelta(days=2), deadline=TODAY + timedelta(days=2))
    c = job("C")
    assert sort_jobs([c, b, a]) == [a, b, c]
    assert sort_jobs([c, a, b], "deadline") == [b, a, c]
