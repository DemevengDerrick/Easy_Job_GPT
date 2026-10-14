"""Parser tests against trimmed real responses saved in tests/fixtures."""
import json
from datetime import date
from pathlib import Path

import pytest

from jobfinder.models import AU, IFI, INTL, UN
from jobfinder.sources import load_sources
from jobfinder.sources.ats import Cornerstone, OracleRecruiting, PageUp, SuccessFactorsRSS, Taleo, Workday
from jobfinder.sources.boards import (Adzuna, Arbeitnow, Greenhouse, Jooble, Lever, RemoteOK, Remotive,
                                      WeWorkRemotely)
from jobfinder.sources.reliefweb import ReliefWeb
from jobfinder.sources.un_careers import UNCareers

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def raw(name):
    return (FIXTURES / name).read_bytes()


def check(jobs, source, n=None):
    assert jobs, "parser returned nothing"
    if n is not None:
        assert len(jobs) == n
    for j in jobs:
        assert j.title and j.url.startswith("http") and j.source == source and j.id
    return jobs


def test_un_careers():
    jobs = check(UNCareers().parse(load("un_careers.json")), "UN Careers", 3)
    assert all(j.org_type == UN and j.url.startswith("https://careers.un.org/jobSearchDescription/") for j in jobs)
    assert all(isinstance(j.posted_at, date) and isinstance(j.deadline, date) for j in jobs)
    assert all("<" not in j.snippet for j in jobs)


def test_oracle():
    src = OracleRecruiting({"name": "IOM", "host": "h.example", "site": "CX_1001", "org_type": UN})
    jobs = check(src.parse(load("oracle.json")), "IOM", 2)
    assert jobs[0].url.startswith("https://h.example/hcmUI/CandidateExperience/en/sites/CX_1001/job/")
    assert jobs[0].posted_at


def test_taleo_deadline_column_and_location():
    cfg = {"name": "FAO", "host": "jobs.fao.org", "section": "fao_external", "portal": "1", "date_column": "deadline"}
    jobs = check(Taleo(cfg).parse(load("taleo_fao.json")), "FAO", 3)
    assert all(j.deadline and j.posted_at is None for j in jobs)
    assert all('"' not in j.location and "[" not in j.location for j in jobs)
    assert "jobdetail.ftl?job=" in jobs[0].url


def test_taleo_location_helper():
    from jobfinder.sources.ats import _taleo_location

    assert _taleo_location("Austria-Vienna-Vienna-IAEA Headquarters") == "Austria, Vienna, IAEA Headquarters"
    assert _taleo_location("Home-Based") == "Home-based"


def test_workday():
    src = Workday({"name": "WFP", "tenant": "wfp", "wd": "wd3", "site": "job_openings"})
    jobs = check(src.parse(load("workday.json")), "WFP", 3)
    assert jobs[0].url.startswith("https://wfp.wd3.myworkdayjobs.com/job_openings/job/")


def test_cornerstone():
    src = Cornerstone({"name": "World Bank Group", "corp": "worldbankgroup", "org_type": IFI})
    jobs = check(src.parse(load("cornerstone.json")), "World Bank Group", 2)
    assert "/requisition/" in jobs[0].url and jobs[0].deadline


def test_successfactors_rss_splits_location_from_title():
    src = SuccessFactorsRSS({"name": "African Union", "host": "jobs.au.int", "org_type": AU})
    jobs = check(src.parse(raw("successfactors.rss")), "African Union", 2)
    assert all("(" not in j.title[-1:] for j in jobs)
    assert any(j.location for j in jobs)
    assert src.per_keyword


def test_pageup():
    jobs = check(PageUp({"name": "UNICEF", "host": "jobs.unicef.org"}).parse(raw("pageup.html").decode()), "UNICEF", 2)
    assert jobs[0].url.startswith("https://jobs.unicef.org/en-us/job/")
    assert jobs[0].deadline and jobs[0].location and jobs[0].grade == "P-3"


def test_reliefweb_flags_un_agencies():
    jobs = check(ReliefWeb().parse(load("reliefweb.json")), "ReliefWeb", 2)
    assert jobs[0].org_type == UN and jobs[0].location == "Nairobi, Kenya" and jobs[0].snippet.startswith("Manage GIS")
    assert jobs[1].org_type == INTL and jobs[1].deadline is None


def test_reliefweb_requires_appname(monkeypatch):
    from jobfinder.sources import SourceError

    monkeypatch.delenv("RELIEFWEB_APPNAME", raising=False)
    with pytest.raises(SourceError):
        ReliefWeb().fetch("GIS")


@pytest.mark.parametrize(
    "cls,fixture,name",
    [(Adzuna, "adzuna.json", "Adzuna"), (Jooble, "jooble.json", "Jooble"), (Remotive, "remotive.json", "Remotive"),
     (Arbeitnow, "arbeitnow.json", "Arbeitnow"), (RemoteOK, "remoteok.json", "Remote OK")],
)
def test_json_boards(cls, fixture, name):
    jobs = check(cls().parse(load(fixture)), name)
    assert all("<" not in j.title for j in jobs)


def test_remoteok_skips_legal_notice():
    assert len(RemoteOK().parse(load("remoteok.json"))) == 2


def test_weworkremotely_splits_company():
    jobs = check(WeWorkRemotely().parse(raw("weworkremotely.rss")), "We Work Remotely", 2)
    assert all(j.organization and j.remote for j in jobs)


def test_greenhouse_and_lever():
    check(Greenhouse().parse(load("greenhouse.json"), "developmentseed"), "Greenhouse")
    check(Lever().parse(load("lever.json"), "palantir"), "Lever", 2)


def test_sources_yaml_loads():
    names = {s.name for s in load_sources()}
    for expected in ("UN Careers", "UNDP", "WHO", "World Bank Group", "African Union", "IMF", "UNESCO"):
        assert expected in names
