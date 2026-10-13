"""careers.un.org: UN Secretariat, its departments, regional commissions, UNEP, OCHA..."""
from .. import net
from ..models import UN, Job
from .base import Source

API = "https://careers.un.org/api/public/opening/jo/list/filteredV2/en"
PAGE_SIZE = 200


class UNCareers(Source):
    name = "UN Careers"
    org_type = UN

    def fetch(self, keyword=None):
        jobs, page = [], 0
        while True:
            body = {
                "filterConfig": {},
                "pagination": {"page": page, "itemPerPage": PAGE_SIZE, "sortBy": "startDate", "sortDirection": -1},
            }
            data = net.post(API, json=body, timeout=60).json()["data"]
            jobs += self.parse(data)
            page += 1
            if not data["list"] or page * PAGE_SIZE >= data.get("count", 0):
                return jobs

    def parse(self, data):
        jobs = []
        for it in data.get("list", []):
            stations = ", ".join(s.get("description", "").title() for s in it.get("dutyStation") or [])
            jobs.append(
                Job(
                    title=it.get("postingTitle") or it.get("jobTitle", ""),
                    url=f"https://careers.un.org/jobSearchDescription/{it['jobId']}?language=en",
                    organization=(it.get("dept") or {}).get("name") or "United Nations",
                    source=self.name,
                    org_type=self.org_type,
                    location=stations,
                    posted_at=net.to_date(it.get("startDate")),
                    deadline=net.to_date(it.get("endDate")),
                    grade=it.get("jobLevel", ""),
                    snippet=net.strip_html(it.get("jobDescription")),
                )
            )
        return jobs
