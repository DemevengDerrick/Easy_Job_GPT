"""Subscriptions storage. SQLite locally, Supabase Postgres in production (DATABASE_URL)."""
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy import (JSON, Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table,
                        create_engine, delete, func, insert, select, update)

from . import config

MAX_ALERTS_PER_EMAIL = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

metadata = MetaData()

subscribers = Table(
    "subscribers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(320), nullable=False, index=True),
    Column("filters", JSON, nullable=False),
    Column("confirmed", Boolean, nullable=False, default=False),
    Column("token", String(64), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_sent_at", DateTime(timezone=True)),
)

sent_jobs = Table(
    "sent_jobs",
    metadata,
    Column("subscriber_id", Integer, ForeignKey("subscribers.id", ondelete="CASCADE"), primary_key=True),
    Column("job_id", String(32), primary_key=True),
    Column("sent_at", DateTime(timezone=True), nullable=False),
)


def _now():
    return datetime.now(timezone.utc)


def _normalize_url(url):
    # Supabase hands out postgres:// URLs; SQLAlchemy needs the psycopg (v3) driver name.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@lru_cache(maxsize=None)
def engine(url=None):
    eng = create_engine(_normalize_url(url or config.database_url()), pool_pre_ping=True)
    metadata.create_all(eng)
    return eng


def create_subscription(email, filters, eng=None):
    """Store an unconfirmed alert and return its token."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    if not filters.get("keywords"):
        raise ValueError("Please enter at least one keyword.")
    with (eng or engine()).begin() as conn:
        count = conn.execute(select(func.count()).select_from(subscribers).where(subscribers.c.email == email)).scalar()
        if count >= MAX_ALERTS_PER_EMAIL:
            raise ValueError(f"This email already has {MAX_ALERTS_PER_EMAIL} alerts. Unsubscribe from one first.")
        token = secrets.token_urlsafe(32)
        conn.execute(
            insert(subscribers).values(email=email, filters=filters, confirmed=False, token=token, created_at=_now())
        )
    return token


def get_subscription(token, eng=None):
    if not token:
        return None
    with (eng or engine()).connect() as conn:
        row = conn.execute(select(subscribers).where(subscribers.c.token == token)).mappings().first()
    return dict(row) if row else None


def confirm(token, eng=None):
    with (eng or engine()).begin() as conn:
        conn.execute(update(subscribers).where(subscribers.c.token == token).values(confirmed=True))
    return get_subscription(token, eng)


def update_filters(token, filters, eng=None):
    with (eng or engine()).begin() as conn:
        result = conn.execute(update(subscribers).where(subscribers.c.token == token).values(filters=filters))
    return result.rowcount > 0


def unsubscribe(token, eng=None):
    sub = get_subscription(token, eng)
    if not sub:
        return False
    with (eng or engine()).begin() as conn:
        conn.execute(delete(sent_jobs).where(sent_jobs.c.subscriber_id == sub["id"]))
        conn.execute(delete(subscribers).where(subscribers.c.id == sub["id"]))
    return True


def confirmed_subscriptions(eng=None):
    with (eng or engine()).connect() as conn:
        rows = conn.execute(select(subscribers).where(subscribers.c.confirmed.is_(True))).mappings().all()
    return [dict(r) for r in rows]


def sent_job_ids(subscriber_id, eng=None):
    with (eng or engine()).connect() as conn:
        rows = conn.execute(select(sent_jobs.c.job_id).where(sent_jobs.c.subscriber_id == subscriber_id))
        return {r[0] for r in rows}


def record_sent(subscriber_id, job_ids, eng=None):
    now = _now()
    with (eng or engine()).begin() as conn:
        if job_ids:
            conn.execute(
                insert(sent_jobs), [{"subscriber_id": subscriber_id, "job_id": j, "sent_at": now} for j in job_ids]
            )
        conn.execute(update(subscribers).where(subscribers.c.id == subscriber_id).values(last_sent_at=now))


def cleanup(eng=None, sent_days=180, unconfirmed_days=7):
    """Forget old sent-job markers and alerts that were never confirmed."""
    now = _now()
    with (eng or engine()).begin() as conn:
        conn.execute(delete(sent_jobs).where(sent_jobs.c.sent_at < now - timedelta(days=sent_days)))
        stale = select(subscribers.c.id).where(
            subscribers.c.confirmed.is_(False), subscribers.c.created_at < now - timedelta(days=unconfirmed_days)
        )
        conn.execute(delete(sent_jobs).where(sent_jobs.c.subscriber_id.in_(stale)))
        conn.execute(delete(subscribers).where(subscribers.c.id.in_(stale)))
