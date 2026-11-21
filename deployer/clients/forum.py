"""Issue a publishing capability scoped to a single tournament booking."""

import base64
import hashlib
import hmac
import json
import os
from urllib.parse import urlsplit

import requests


def origin():
    return os.environ.get("APDA_FORUM_URL", "").rstrip("/")


def configured():
    try:
        base = urlsplit(origin())
        return (
            base.scheme == "https" and bool(base.hostname)
            and base.username is None and not (base.path or base.query or base.fragment)
            and bool(os.environ.get("APDA_MITTAB_FORUM_SIGNING_KEY"))
        )
    except ValueError:
        return False


def is_forum_url(value):
    try:
        target = urlsplit(value)
        base = urlsplit(origin())
        return (
            target.scheme == base.scheme == "https"
            and target.netloc == base.netloc
            and bool(target.hostname)
            and target.username is None
            and bool(target.path.strip("/") or target.query)
        )
    except ValueError:
        return False


def publication_settings(app):
    if app.is_test or app.forum_mode not in ("new", "existing") or not configured():
        return {}
    claims = {"id": app.checkout_key, "mode": app.forum_mode, "tab_url": app.url}
    if app.forum_mode == "new":
        claims["title"] = app.forum_selection
    else:
        claims["topic_url"] = app.forum_selection
    encoded = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).rstrip(b"=")
    secret = os.environ["APDA_MITTAB_FORUM_SIGNING_KEY"].encode()
    signature = hmac.new(secret, encoded, hashlib.sha256).hexdigest()
    return {
        "APDA_FORUM_URL": origin(),
        "APDA_FORUM_PUBLICATION_ID": app.checkout_key,
        "APDA_FORUM_TOURNAMENT_TOKEN": f"{encoded.decode()}.{signature}",
    }


def announce(app):
    config = publication_settings(app)
    if not config:
        raise ValueError("Forum publishing is not configured")
    response = requests.post(
        f"{origin()}/wp-json/apda-forum/v1/tournaments/{app.checkout_key}/announcement",
        headers={"X-APDA-Tournament-Token": config["APDA_FORUM_TOURNAMENT_TOKEN"]},
        timeout=(3, 10),
        allow_redirects=False,
    )
    if response.status_code not in (200, 201):
        raise ValueError(f"Forum announcement returned HTTP {response.status_code}")
    payload = response.json()
    url = payload.get("url")
    if payload.get("status") == "pending_approval":
        return ""
    if url and is_forum_url(url):
        return url
    raise ValueError("Forum announcement returned an invalid topic URL")
