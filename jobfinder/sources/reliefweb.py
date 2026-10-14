"""ReliefWeb API v2: humanitarian and development jobs from UN agencies and NGOs.

v1 was switched off (HTTP 410) and v2 only accepts an approved appname:
request one at https://apidoc.reliefweb.int/parameters#appname and set RELIEFWEB_APPNAME.
"""
from .. import config, net
from ..models import INTL, UN, Job
from .base import Source, SourceError

API = "https://api.reliefweb.int/v2/jobs"
UN_HINTS = ("UN", "United Nations", "UNICEF", "UNHCR", "WFP", "OCHA", "UNDP", "UNFPA", "IOM", "WHO", "FAO", "UNOPS")


class ReliefWeb(Source):
    name = "ReliefWeb"
    org_type = INTL
    per_keyword = True

    def fetch(self, keyword=None):
        appname = config.get("RELIEFWEB_APPNAME")
        if not appname:
            raise SourceError("RELIEFWEB_APPNAME is not set (ReliefWeb requires an approved appname)")
        body = {
            "limit": 200,
            "sort": ["date.created:desc"],
            "fields": {
                "include": ["title", "url_alias", "url", "date.created", "date.closing", "source.name",
                            "source.shortname", "country.name", "city.name", "body", "type.name"]
            },
        }
        if keyword:
            body["query"] = {"value": keyword, "fields": ["title", "body"], "operator": "AND"}
        return self.parse(net.post(API, params={"appname": appname}, json=body).json())

    def parse(self, data):
        jobs = []
        for item in data.get("data", []):
            f = item.get("fields", {})
            sources = f.get("source") or [{}]
            org = sources[0].get("name", "")
            short = sources[0].get("shortname", "")
            places = [c.get("name") for c in (f.get("city") or []) + (f.get("country") or []) if c.get("name")]
            is_un = any(short == h or short.startswith(h + " ") or h in org.split() for h in UN_HINTS)
            jobs.append(
                Job(
                    title=f.get("title", ""),
                    url=f.get("url_alias") or f.get("url") or f"https://reliefweb.int/job/{item.get('id')}",
                    organization=org,
                    source=self.name,
                    org_type=UN if is_un else INTL,
                    location=", ".join(dict.fromkeys(places)),
                    posted_at=net.to_date((f.get("date") or {}).get("created")),
                    deadline=net.to_date((f.get("date") or {}).get("closing")),
                    snippet=net.strip_html(f.get("body")),
                )
            )
        return jobs
