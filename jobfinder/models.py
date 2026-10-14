import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from urllib.parse import urlsplit, urlunsplit

# Organisation categories shown in the filters.
UN = "UN system"
IFI = "Development bank / IFI"
AU = "African Union"
INTL = "NGO / International"
BOARD = "Job board"
COMPANY = "Company"
ORG_TYPES = [UN, IFI, AU, INTL, BOARD, COMPANY]

# Grade categories inferred from titles / grade fields.
GRADE_CATEGORIES = [
    "Professional (P/D)",
    "National Officer (NO)",
    "General Service (G)",
    "Consultant",
    "Internship",
    "Volunteer (UNV)",
    "Other",
]

_GRADE_RE = re.compile(
    r"\b(?:(P|D|FS|G|GS)\s?-?\s?([1-7])|(NO)\s?-?\s?([A-D])|(NO[A-D]))\b", re.IGNORECASE
)


@dataclass
class Job:
    title: str
    url: str
    organization: str
    source: str
    org_type: str
    location: str = ""
    remote: bool = False
    posted_at: date | None = None
    deadline: date | None = None
    grade: str = ""
    snippet: str = ""
    id: str = field(default="")

    def __post_init__(self):
        self.title = " ".join((self.title or "").split())
        self.location = " ".join((self.location or "").split())
        if not self.grade:
            self.grade = infer_grade(self.title)
        if not self.remote:
            self.remote = bool(re.search(r"\b(remote|home[- ]based|anywhere)\b", f"{self.title} {self.location}", re.I))
        if not self.id:
            self.id = hashlib.sha1(canonical_url(self.url).encode()).hexdigest()[:16]

    @property
    def grade_category(self):
        return grade_category(self.grade, self.title)

    def to_dict(self):
        d = asdict(self)
        d["grade_category"] = self.grade_category
        return d


def canonical_url(url):
    """Drop tracking query params and fragments so the same posting dedupes."""
    parts = urlsplit(url.strip())
    query = "&".join(
        p for p in parts.query.split("&") if p and not p.lower().startswith(("utm_", "feedid", "source=", "ref="))
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def infer_grade(text):
    m = _GRADE_RE.search(text or "")
    if not m:
        return ""
    if m.group(1):
        prefix = m.group(1).upper()
        return f"{'G' if prefix == 'GS' else prefix}-{m.group(2)}"
    if m.group(3):
        return f"NO-{m.group(4).upper()}"
    return f"NO-{m.group(5)[-1].upper()}"


def grade_category(grade, title=""):
    g = (grade or "").upper()
    t = (title or "").lower()
    if g.startswith(("P-", "D-")):
        return "Professional (P/D)"
    if g.startswith("NO-"):
        return "National Officer (NO)"
    if g.startswith(("G-", "FS-")):
        return "General Service (G)"
    if g in ("CON", "IC") or re.search(r"\b(consultan\w*|individual contractor|expert)\b", t):
        return "Consultant"
    if g.startswith("I-") or re.search(r"\bintern(ship)?\b|\bstagiaire\b", t):
        return "Internship"
    if re.search(r"\b(unv|volunteer)\b", t):
        return "Volunteer (UNV)"
    return "Other"
