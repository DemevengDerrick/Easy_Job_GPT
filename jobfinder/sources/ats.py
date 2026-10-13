"""Generic adapters for the applicant-tracking systems used by UN agencies and IFIs.

Each class is configured per organisation in sources.yaml.
"""
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Job
from .base import Source, SourceError


class OracleRecruiting(Source):
    """Oracle Recruiting Cloud candidate-experience sites (UNDP, IOM...)."""

    def fetch(self, keyword=None):
        host, site = self.cfg["host"], self.cfg["site"]
        jobs, offset, limit = [], 0, 200
        while True:
            url = (
                f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true"
                f"&expand=requisitionList&finder=findReqs;siteNumber={site},limit={limit},offset={offset},"
                "sortBy=POSTING_DATES_DESC"
            )
            item = net.get(url, timeout=60).json()["items"][0]
            batch = self.parse(item)
            jobs += batch
            offset += limit
            if not batch or offset >= item.get("TotalJobsCount", 0):
                return jobs

    def parse(self, item):
        host, site = self.cfg["host"], self.cfg["site"]
        return [
            Job(
                title=r["Title"],
                url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{r['Id']}",
                organization=self.name,
                source=self.name,
                org_type=self.org_type,
                location=r.get("PrimaryLocation") or "",
                remote=(r.get("WorkplaceType") or "").lower() == "remote",
                posted_at=net.to_date(r.get("PostedDate")),
                deadline=net.to_date(r.get("PostingEndDate")),
                snippet=net.strip_html(r.get("ShortDescriptionStr")),
            )
            for r in item.get("requisitionList", [])
        ]


class Taleo(Source):
    """Oracle Taleo career sections (WHO, FAO, IAEA...).

    The third column is the posting date on some sites and the closing date on
    others, so `date_column` in the config says which.
    """

    def fetch(self, keyword=None):
        jobs, page = [], 1
        while True:
            body = {
                "multilineEnabled": False,
                "sortingSelection": {"sortBySelectionParam": "3", "ascendingSortingOrder": "false"},
                "fieldData": {"fields": {"KEYWORD": "", "LOCATION": "", "JOB_FIELD": ""}, "valid": True},
                "filterSelectionParam": {"searchFilterSelections": []},
                "advancedSearchFiltersSelectionParam": {"searchFilterSelections": []},
                "pageNo": page,
            }
            url = f"https://{self.cfg['host']}/careersection/rest/jobboard/searchjobs?lang=en&portal={self.cfg['portal']}"
            data = net.post(url, json=body, headers={"tz": "GMT+00:00"}).json()
            batch = self.parse(data)
            jobs += batch
            paging = data.get("pagingData", {})
            if not batch or page * paging.get("pageSize", 25) >= paging.get("totalCount", 0):
                return jobs
            page += 1

    def parse(self, data):
        host, section = self.cfg["host"], self.cfg["section"]
        date_field = "deadline" if self.cfg.get("date_column") == "deadline" else "posted_at"
        jobs = []
        for r in data.get("requisitionList", []):
            cols = r.get("column", [])
            location = cols[1] if len(cols) > 1 else ""
            location = "; ".join(_taleo_location(l) for l in re.findall(r'"([^"]+)"', location) or [location])
            when = net.to_date(cols[2]) if len(cols) > 2 else None
            jobs.append(
                Job(
                    title=cols[0] if cols else "",
                    url=f"https://{host}/careersection/{section}/jobdetail.ftl?job={r['contestNo']}&lang=en",
                    organization=self.name,
                    source=self.name,
                    org_type=self.org_type,
                    location=location,
                    **{date_field: when},
                )
            )
        return jobs


def _taleo_location(text):
    """'Austria-Vienna-Vienna-IAEA Headquarters' -> 'Austria, Vienna, IAEA Headquarters'"""
    if text.lower().startswith("home-based"):
        return "Home-based"
    parts = [p.strip() for p in text.split("-") if p.strip()]
    return ", ".join(dict.fromkeys(parts))


class Workday(Source):
    """Workday 'cxs' job boards (WFP, UNHCR, IMF, Global Fund...)."""

    def fetch(self, keyword=None):
        tenant, wd, site = self.cfg["tenant"], self.cfg["wd"], self.cfg["site"]
        url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        jobs, offset = [], 0
        while True:
            body = {"limit": 20, "offset": offset, "searchText": "", "appliedFacets": {}}
            data = net.post(url, json=body, headers={"Accept": "application/json"}).json()
            if offset == 0:
                total = data.get("total", 0)  # Workday only reports the total on the first page
            batch = self.parse(data)
            jobs += batch
            offset += 20
            if not batch or offset >= total:
                return jobs

    def parse(self, data):
        tenant, wd, site = self.cfg["tenant"], self.cfg["wd"], self.cfg["site"]
        return [
            Job(
                title=p["title"],
                url=f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{p['externalPath']}",
                organization=self.name,
                source=self.name,
                org_type=self.org_type,
                location=p.get("locationsText", ""),
                posted_at=net.relative_date(p.get("postedOn")),
            )
            for p in data.get("jobPostings", [])
            if p.get("externalPath")
        ]


class Cornerstone(Source):
    """Cornerstone OnDemand career sites (World Bank Group).

    The career page embeds a short-lived public token for its own search API.
    """

    def fetch(self, keyword=None):
        corp, site_id = self.cfg["corp"], self.cfg.get("site_id", 1)
        page = net.get(f"https://{corp}.csod.com/ux/ats/careersite/{site_id}/home?c={corp}").text
        token = re.search(r'"token":"([^"]+)"', page)
        cloud = re.search(r'"cloud":"([^"]+)"', page)
        if not (token and cloud):
            raise SourceError("could not find the career-site search token")
        jobs, number = [], 1
        while True:
            body = {
                "careerSiteId": site_id, "careerSitePageId": site_id, "pageNumber": number, "pageSize": 100,
                "cultureId": 1, "searchText": "", "cultureName": "en-US", "states": [], "countryCodes": [],
                "cities": [], "placeID": "", "radius": None, "postingsWithinDays": None,
                "customFieldCheckboxKeys": [], "customFieldDropdowns": [], "customFieldRadios": [],
            }
            data = net.post(
                cloud.group(1) + "rec-job-search/external/jobs",
                json=body,
                headers={"Authorization": "Bearer " + token.group(1)},
            ).json()["data"]
            batch = self.parse(data)
            jobs += batch
            if not batch or number * 100 >= data.get("totalCount", 0):
                return jobs
            number += 1

    def parse(self, data):
        corp, site_id = self.cfg["corp"], self.cfg.get("site_id", 1)
        jobs = []
        for r in data.get("requisitions", []):
            locs = r.get("locations") or []
            location = "; ".join(", ".join(x for x in (l.get("city"), l.get("country")) if x) for l in locs)
            jobs.append(
                Job(
                    title=r["displayJobTitle"],
                    url=f"https://{corp}.csod.com/ux/ats/careersite/{site_id}/home/requisition/{r['requisitionId']}?c={corp}",
                    organization=self.name,
                    source=self.name,
                    org_type=self.org_type,
                    location=location,
                    posted_at=net.to_date(r.get("postingEffectiveDate")),
                    deadline=net.to_date(r.get("postingExpirationDate")),
                    snippet=net.strip_html(r.get("externalDescription")),
                )
            )
        return jobs


class SuccessFactorsRSS(Source):
    """SAP SuccessFactors career sites (UNESCO, ILO, African Union...).

    The RSS feed is capped at about 20 items, so it is queried once per keyword.
    """

    per_keyword = True

    def fetch(self, keyword=None):
        r = net.get(f"https://{self.cfg['host']}/services/rss/job/", params={"locale": "en_US", "keywords": keyword or ""})
        return self.parse(r.content)

    def parse(self, content):
        import feedparser

        jobs = []
        for e in feedparser.parse(content).entries:
            title = e.get("title", "")
            m = re.match(r"^(.*)\(([^()]*)\)\s*$", title)
            jobs.append(
                Job(
                    title=m.group(1).strip() if m else title,
                    url=e.get("link", ""),
                    organization=self.name,
                    source=self.name,
                    org_type=self.org_type,
                    location=m.group(2) if m else "",
                    posted_at=net.to_date(e.get("published")),
                    snippet=net.strip_html(e.get("summary")),
                )
            )
        return jobs


class PageUp(Source):
    """PageUp career sites (UNICEF). HTML listing, so this is the most fragile adapter."""

    def fetch(self, keyword=None):
        r = net.get(f"https://{self.cfg['host']}/en-us/listing/", params={"page": 1, "page-items": 1000}, timeout=60)
        if r.status_code == 202 or not r.text.strip():
            raise SourceError("site answered with a bot-protection challenge; try again later")
        return self.parse(r.text)

    def parse(self, page):
        base = f"https://{self.cfg['host']}"
        jobs = []
        for item in BeautifulSoup(page, "html.parser").select(".list-view--item"):
            link = item.select_one("a.job-link")
            if not link:
                continue
            location = item.select_one(".location")
            closing = item.select_one(".close-date time")
            teaser = item.select_one(".row--teaser")
            jobs.append(
                Job(
                    title=link.get_text(" ", strip=True),
                    url=base + link["href"] if link["href"].startswith("/") else link["href"],
                    organization=self.name,
                    source=self.name,
                    org_type=self.org_type,
                    location=location.get_text(strip=True) if location else "",
                    deadline=net.to_date(closing.get("datetime")) if closing else None,
                    snippet=teaser.get_text(" ", strip=True)[:3000] if teaser else "",
                )
            )
        return jobs
