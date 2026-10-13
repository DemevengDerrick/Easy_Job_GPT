"""Emails through Resend (https://resend.com). Needs RESEND_API_KEY and MAIL_FROM."""
from html import escape
from urllib.parse import urlencode

import requests

from . import config

RESEND_URL = "https://api.resend.com/emails"


def link(action, token):
    return f"{config.app_url()}/?{urlencode({'action': action, 'token': token})}"


def send_email(to, subject, html, text, headers=None):
    api_key, sender = config.get("RESEND_API_KEY"), config.get("MAIL_FROM")
    if not (api_key and sender):
        raise RuntimeError("RESEND_API_KEY and MAIL_FROM must be set to send email.")
    payload = {"from": sender, "to": [to], "subject": subject, "html": html, "text": text}
    if headers:
        payload["headers"] = headers
    r = requests.post(RESEND_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"Resend error {r.status_code}: {r.text[:300]}")
    return r.json()


def _layout(body):
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#1f2937">'
        f'<h2 style="margin-bottom:4px">Easy Job Finder</h2>{body}</div>'
    )


def describe(filters):
    parts = [("all of" if filters.get("match_all") else "any of") + ": " + ", ".join(filters.get("keywords", []))]
    for key, label in (("locations", "locations"), ("org_types", "organisations"), ("grade_categories", "grades")):
        if filters.get(key):
            parts.append(f"{label}: {', '.join(filters[key])}")
    if filters.get("remote_only"):
        parts.append("remote only")
    if filters.get("exclude"):
        parts.append(f"excluding: {', '.join(filters['exclude'])}")
    return "; ".join(parts)


def confirmation_email(email, token, filters):
    url = link("confirm", token)
    html = _layout(
        f"<p>Please confirm your daily job alert for <b>{escape(describe(filters))}</b>.</p>"
        f'<p><a href="{escape(url)}" style="background:#2563eb;color:#fff;padding:10px 18px;border-radius:6px;'
        'text-decoration:none">Confirm my alert</a></p>'
        "<p style='color:#6b7280;font-size:13px'>If you didn't ask for this, ignore this email; "
        "nothing will be sent.</p>"
    )
    text = f"Confirm your daily job alert ({describe(filters)}): {url}\n\nIf you didn't ask for this, ignore this email."
    return send_email(email, "Confirm your daily job alert", html, text)


def digest_html(jobs, sub, total):
    rows = []
    for j in jobs:
        meta = " · ".join(x for x in (j.organization, j.location, j.grade) if x)
        dates = []
        if j.posted_at:
            dates.append(f"posted {j.posted_at:%d %b}")
        if j.deadline:
            dates.append(f"closes {j.deadline:%d %b %Y}")
        rows.append(
            '<tr><td style="padding:10px 0;border-bottom:1px solid #e5e7eb">'
            f'<a href="{escape(j.url)}" style="font-weight:bold;color:#1d4ed8;text-decoration:none">{escape(j.title)}</a>'
            f'<br><span style="font-size:13px">{escape(meta)}</span>'
            f'<br><span style="font-size:12px;color:#6b7280">{escape(" · ".join(dates + [j.source]))}</span></td></tr>'
        )
    more = f"<p>…and {total - len(jobs)} more. Search the app to see them all.</p>" if total > len(jobs) else ""
    return _layout(
        f"<p>{total} new job{'s' if total != 1 else ''} for <b>{escape(describe(sub['filters']))}</b>:</p>"
        f'<table style="width:100%;border-collapse:collapse">{"".join(rows)}</table>{more}'
        f'<p style="font-size:12px;color:#6b7280;margin-top:24px">'
        f'<a href="{escape(link("manage", sub["token"]))}">Edit this alert</a> · '
        f'<a href="{escape(link("unsubscribe", sub["token"]))}">Unsubscribe</a></p>'
    )


def digest_text(jobs, sub, total):
    lines = [f"{total} new jobs for {describe(sub['filters'])}", ""]
    for j in jobs:
        lines += [j.title, f"  {j.organization} | {j.location} | {j.source}", f"  {j.url}", ""]
    lines += [f"Edit: {link('manage', sub['token'])}", f"Unsubscribe: {link('unsubscribe', sub['token'])}"]
    return "\n".join(lines)


def send_digest(sub, jobs, total):
    unsubscribe = link("unsubscribe", sub["token"])
    subject = f"{total} new job{'s' if total != 1 else ''}: {', '.join(sub['filters']['keywords'])[:60]}"
    return send_email(
        sub["email"],
        subject,
        digest_html(jobs, sub, total),
        digest_text(jobs, sub, total),
        headers={"List-Unsubscribe": f"<{unsubscribe}>"},
    )
