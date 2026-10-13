"""Query every source concurrently, isolate failures, dedupe the results.

Run `python -m jobfinder.search GIS "data analyst"` for a live smoke test.
"""
import logging
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .filters import JobFilter, parse_terms
from .sources import load_sources

log = logging.getLogger(__name__)

_cache = {}
_cache_lock = threading.Lock()


@dataclass
class SourceStatus:
    name: str
    ok: bool
    count: int = 0
    error: str = ""
    seconds: float = 0.0


def _cached_fetch(source, keyword):
    key = (source.name, keyword if source.per_keyword else None)
    with _cache_lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < source.cache_ttl:
        return hit[1]
    jobs = source.fetch(keyword)
    with _cache_lock:
        _cache[key] = (time.time(), jobs)
    return jobs


def _run(source, keywords):
    started = time.time()
    try:
        jobs = []
        for kw in keywords if source.per_keyword else [None]:
            jobs += _cached_fetch(source, kw)
        return jobs, SourceStatus(source.name, True, len(jobs), seconds=time.time() - started)
    except Exception as exc:
        log.warning("%s failed: %s", source.name, exc)
        return [], SourceStatus(source.name, False, error=str(exc)[:300], seconds=time.time() - started)


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def dedupe(jobs):
    seen, out = set(), []
    for job in jobs:
        keys = {job.id, (_norm(job.title), _norm(job.organization), _norm(job.location))}
        if keys & seen:
            continue
        seen |= keys
        out.append(job)
    return out


def fetch_jobs(keywords, sources=None, max_workers=12):
    """Return (jobs matching any keyword, per-source statuses)."""
    keywords = parse_terms(keywords)
    sources = load_sources() if sources is None else sources
    jobs, statuses = [], []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_run, s, keywords) for s in sources]
        for f in as_completed(futures):
            found, status = f.result()
            jobs += found
            statuses.append(status)
    any_keyword = JobFilter(keywords=keywords, hide_expired=False)
    jobs = dedupe(j for j in jobs if any_keyword.matches_keywords(j))
    return jobs, sorted(statuses, key=lambda s: s.name.lower())


def main(argv):
    logging.basicConfig(level=logging.WARNING)
    keywords = argv or ["GIS"]
    jobs, statuses = fetch_jobs(keywords)
    for s in statuses:
        print(f"{'OK ' if s.ok else 'ERR'} {s.name:<22} {s.count:>5} fetched  {s.seconds:5.1f}s  {s.error}")
    print(f"\n{len(jobs)} jobs match {keywords}")
    for j in jobs[:15]:
        print(f"- [{j.source}] {j.title} | {j.organization} | {j.location} | {j.url}")


if __name__ == "__main__":
    main(sys.argv[1:])
