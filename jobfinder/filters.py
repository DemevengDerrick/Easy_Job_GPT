import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from functools import lru_cache


def parse_terms(text):
    """'GIS, data analyst; remote sensing' -> ['GIS', 'data analyst', 'remote sensing']"""
    if isinstance(text, (list, tuple)):
        text = ",".join(text)
    terms = (t.strip() for t in re.split(r"[,;\n]", text or ""))
    return list(dict.fromkeys(t for t in terms if t))


@lru_cache(maxsize=512)
def _pattern(term):
    # Whole words only, so "GIS" doesn't match "logistics"; allow a plural ending.
    words = [re.escape(w) for w in term.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?:s|es)?(?!\w)", re.IGNORECASE)


def mentions(text, term):
    return bool(_pattern(term).search(text or ""))


@dataclass
class JobFilter:
    keywords: list = field(default_factory=list)
    match_all: bool = False          # every keyword must appear (default: any)
    exclude: list = field(default_factory=list)
    title_only: bool = False
    locations: list = field(default_factory=list)
    remote_only: bool = False
    org_types: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    grade_categories: list = field(default_factory=list)
    posted_within_days: int | None = None
    hide_expired: bool = True

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in names})

    def matches_keywords(self, job):
        if not self.keywords:
            return True
        text = job.title if self.title_only else f"{job.title} {job.organization} {job.snippet}"
        hits = (mentions(text, k) for k in self.keywords)
        return all(hits) if self.match_all else any(hits)

    def matches(self, job, today=None):
        today = today or date.today()
        if not self.matches_keywords(job):
            return False
        full_text = f"{job.title} {job.snippet}"
        if any(mentions(full_text, x) for x in self.exclude):
            return False
        if self.remote_only and not job.remote:
            return False
        if self.locations:
            loc = job.location.lower()
            wants_remote = any(l.lower() == "remote" for l in self.locations)
            if not (any(l.lower() in loc for l in self.locations) or (wants_remote and job.remote)):
                return False
        if self.org_types and job.org_type not in self.org_types:
            return False
        if self.sources and job.source not in self.sources:
            return False
        if self.grade_categories and job.grade_category not in self.grade_categories:
            return False
        # Postings without a date are kept: many career sites don't publish one.
        if self.posted_within_days and job.posted_at and job.posted_at < today - timedelta(days=self.posted_within_days):
            return False
        if self.hide_expired and job.deadline and job.deadline < today:
            return False
        return True

    def apply(self, jobs, today=None):
        return [j for j in jobs if self.matches(j, today)]


def sort_jobs(jobs, by="newest"):
    if by == "deadline":
        return sorted(jobs, key=lambda j: (j.deadline is None, j.deadline or date.max))
    return sorted(jobs, key=lambda j: (j.posted_at is None, -(j.posted_at or date.min).toordinal()))
