"""Shared HTTP session plus small parsing helpers used by the source adapters."""
import html
import re
import threading
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "Mozilla/5.0 (compatible; EasyJobFinder/1.0; +https://github.com/DemevengDerrick/Data_job_search)"
TIMEOUT = 20

_local = threading.local()


def session():
    """One retrying session per thread (requests.Session is not thread-safe)."""
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        retry = Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=None)
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
        _local.session = s
    return s


def get(url, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    r = session().get(url, **kwargs)
    r.raise_for_status()
    return r


def post(url, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    r = session().post(url, **kwargs)
    r.raise_for_status()
    return r


def strip_html(text, limit=3000):
    if not text:
        return ""
    if "<" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = " ".join(html.unescape(text).split())
    return text[:limit]


def to_date(value):
    """Parse ISO strings, epoch seconds/milliseconds and the usual human formats."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date()
    try:
        return dateparser.parse(str(value), fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def relative_date(text, today=None):
    """Workday style 'Posted Today' / 'Posted 3 Days Ago' / 'Posted 30+ Days Ago'."""
    today = today or date.today()
    t = (text or "").lower()
    if "today" in t:
        return today
    if "yesterday" in t:
        return today - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*day", t)
    if m:
        return today - timedelta(days=int(m.group(1)))
    return None
