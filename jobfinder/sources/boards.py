"""Aggregator APIs, remote job boards and company ATS boards."""
from .. import config, net
from ..models import BOARD, COMPANY, Job
from .base import Source, SourceError


class Adzuna(Source):
    """https://developer.adzuna.com: needs ADZUNA_APP_ID and ADZUNA_APP_KEY."""

    name = "Adzuna"
    org_type = BOARD
    per_keyword = True

    def fetch(self, keyword=None):
        app_id, app_key = config.get("ADZUNA_APP_ID"), config.get("ADZUNA_APP_KEY")
        if not (app_id and app_key):
            raise SourceError("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set")
        jobs = []
        for country in self.cfg.get("countries", ["gb"]):
            params = {"app_id": app_id, "app_key": app_key, "results_per_page": 50, "max_days_old": 30}
            if keyword:
                params["what"] = keyword
            data = net.get(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1", params=params).json()
            jobs += self.parse(data)
        return jobs

    def parse(self, data):
        return [
            Job(
                title=net.strip_html(r.get("title")),
                url=r["redirect_url"],
                organization=(r.get("company") or {}).get("display_name", ""),
                source=self.name,
                org_type=self.org_type,
                location=(r.get("location") or {}).get("display_name", ""),
                posted_at=net.to_date(r.get("created")),
                snippet=net.strip_html(r.get("description")),
            )
            for r in data.get("results", [])
        ]


class Jooble(Source):
    """https://jooble.org/api/about: needs JOOBLE_KEY."""

    name = "Jooble"
    org_type = BOARD
    per_keyword = True

    def fetch(self, keyword=None):
        key = config.get("JOOBLE_KEY")
        if not key:
            raise SourceError("JOOBLE_KEY is not set")
        body = {"keywords": keyword or "", "location": self.cfg.get("location", "")}
        return self.parse(net.post(f"https://jooble.org/api/{key}", json=body).json())

    def parse(self, data):
        return [
            Job(
                title=net.strip_html(r.get("title")),
                url=r["link"],
                organization=r.get("company", ""),
                source=self.name,
                org_type=self.org_type,
                location=r.get("location", ""),
                posted_at=net.to_date(r.get("updated")),
                snippet=net.strip_html(r.get("snippet")),
            )
            for r in data.get("jobs", [])
        ]


class Remotive(Source):
    """https://remotive.com/api: asks clients to call it only a few times a day."""

    name = "Remotive"
    org_type = BOARD
    cache_ttl = 6 * 3600

    def fetch(self, keyword=None):
        return self.parse(net.get("https://remotive.com/api/remote-jobs", timeout=60).json())

    def parse(self, data):
        return [
            Job(
                title=r["title"],
                url=r["url"],
                organization=r.get("company_name", ""),
                source=self.name,
                org_type=self.org_type,
                location=r.get("candidate_required_location") or "Remote",
                remote=True,
                posted_at=net.to_date(r.get("publication_date")),
                snippet=net.strip_html(r.get("description")),
            )
            for r in data.get("jobs", [])
        ]


class Arbeitnow(Source):
    name = "Arbeitnow"
    org_type = BOARD

    def fetch(self, keyword=None):
        jobs = []
        for page in range(1, self.cfg.get("pages", 3) + 1):
            data = net.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page}).json()
            jobs += self.parse(data)
            if not (data.get("links") or {}).get("next"):
                break
        return jobs

    def parse(self, data):
        return [
            Job(
                title=r["title"],
                url=r["url"],
                organization=r.get("company_name", ""),
                source=self.name,
                org_type=self.org_type,
                location=r.get("location", ""),
                remote=bool(r.get("remote")),
                posted_at=net.to_date(r.get("created_at")),
                snippet=net.strip_html(r.get("description")),
            )
            for r in data.get("data", [])
        ]


class RemoteOK(Source):
    """https://remoteok.com/api: terms ask that jobs link back to Remote OK (we do)."""

    name = "Remote OK"
    org_type = BOARD

    def fetch(self, keyword=None):
        return self.parse(net.get("https://remoteok.com/api").json())

    def parse(self, data):
        return [
            Job(
                title=r["position"],
                url=r.get("url") or f"https://remoteok.com/remote-jobs/{r['id']}",
                organization=r.get("company", ""),
                source=self.name,
                org_type=self.org_type,
                location=r.get("location") or "Remote",
                remote=True,
                posted_at=net.to_date(r.get("date") or r.get("epoch")),
                snippet=net.strip_html(r.get("description")),
            )
            for r in data
            if isinstance(r, dict) and r.get("position")  # first element is the legal notice
        ]


class WeWorkRemotely(Source):
    name = "We Work Remotely"
    org_type = BOARD

    def fetch(self, keyword=None):
        return self.parse(net.get("https://weworkremotely.com/remote-jobs.rss").content)

    def parse(self, content):
        import feedparser

        jobs = []
        for e in feedparser.parse(content).entries:
            company, _, title = e.get("title", "").partition(":")
            if not title:
                company, title = "", company
            jobs.append(
                Job(
                    title=title.strip(),
                    url=e.get("link", ""),
                    organization=company.strip(),
                    source=self.name,
                    org_type=self.org_type,
                    location=e.get("region") or "Remote",
                    remote=True,
                    posted_at=net.to_date(e.get("published")),
                    snippet=net.strip_html(e.get("summary")),
                )
            )
        return jobs


class Greenhouse(Source):
    """Public Greenhouse job boards for the companies listed in sources.yaml."""

    name = "Greenhouse"
    org_type = COMPANY

    def fetch(self, keyword=None):
        jobs, errors = [], []
        for board in self.cfg.get("boards", []):
            try:
                data = net.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs").json()
                jobs += self.parse(data, board)
            except Exception as exc:  # one dead board shouldn't hide the others
                errors.append(f"{board}: {exc}")
        if errors and not jobs:
            raise SourceError("; ".join(errors))
        return jobs

    def parse(self, data, board):
        company = data.get("meta", {}).get("name") or board.title()
        return [
            Job(
                title=r["title"],
                url=r["absolute_url"],
                organization=r.get("company_name") or company,
                source=self.name,
                org_type=self.org_type,
                location=(r.get("location") or {}).get("name", ""),
                posted_at=net.to_date(r.get("first_published") or r.get("updated_at")),
            )
            for r in data.get("jobs", [])
        ]


class Lever(Source):
    """Public Lever job boards for the companies listed in sources.yaml."""

    name = "Lever"
    org_type = COMPANY

    def fetch(self, keyword=None):
        jobs, errors = [], []
        for board in self.cfg.get("boards", []):
            try:
                data = net.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"}).json()
                jobs += self.parse(data, board)
            except Exception as exc:
                errors.append(f"{board}: {exc}")
        if errors and not jobs:
            raise SourceError("; ".join(errors))
        return jobs

    def parse(self, data, board):
        return [
            Job(
                title=r["text"],
                url=r["hostedUrl"],
                organization=board.title(),
                source=self.name,
                org_type=self.org_type,
                location=(r.get("categories") or {}).get("location", ""),
                remote=r.get("workplaceType") == "remote",
                posted_at=net.to_date(r.get("createdAt")),
                snippet=(r.get("descriptionPlain") or "")[:3000],
            )
            for r in data
        ]
