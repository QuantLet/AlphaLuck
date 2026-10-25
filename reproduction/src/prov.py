"""Fetch-with-provenance helper.

Every byte that lands in data/raw/ goes through here, so PROVENANCE.csv always
has: URL/endpoint, request payload, UTC timestamp, row count, SHA-256.
Cached: a file already on disk is never re-downloaded.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PROV = os.path.join(ROOT, "PROVENANCE.csv")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FIELDS = [
    "path",
    "method",
    "url",
    "payload",
    "fetched_utc",
    "http_status",
    "bytes",
    "rows",
    "sha256",
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rowcount(path: str) -> int:
    """Best-effort row count: length of the JSON list, or of its single list value."""
    try:
        with open(path) as fh:
            obj = json.load(fh)
    except Exception:
        return -1
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        lists = [v for v in obj.values() if isinstance(v, list)]
        if len(lists) == 1:
            return len(lists[0])
        return len(obj)
    return -1


def _record(path: str, method: str, url: str, payload, status: int) -> None:
    rel = os.path.relpath(path, ROOT)
    row = {
        "path": rel,
        "method": method,
        "url": url,
        "payload": "" if payload is None else json.dumps(payload, sort_keys=True),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": status,
        "bytes": os.path.getsize(path),
        "rows": _rowcount(path),
        "sha256": _sha256(path),
    }
    new = not os.path.exists(PROV)
    seen = set()
    if not new:
        with open(PROV) as fh:
            seen = {r["path"] for r in csv.DictReader(fh)}
    if rel in seen:
        return
    with open(PROV, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def fetch(
    name: str,
    url: str,
    payload: dict | None = None,
    *,
    method: str | None = None,
    sleep: float = 0.35,
    tries: int = 5,
    log_url: str | None = None,
) -> str:
    """Download to data/raw/<name>; return the path. No-op if already present.

    log_url, when given, is what gets written to PROVENANCE.csv in place of the
    real URL. It exists so that a request carrying an API key can be logged
    with the key redacted; the key is never written to disk.
    """
    rec_url = log_url or url
    path = os.path.join(RAW, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        _record(path, method or ("POST" if payload else "GET"), rec_url, payload, 200)
        return path

    method = method or ("POST" if payload else "GET")
    headers = {"User-Agent": UA, "Accept": "application/json"}
    delay = 1.0
    last = None
    for attempt in range(tries):
        try:
            if method == "POST":
                headers["Content-Type"] = "application/json"
                r = requests.post(url, json=payload, headers=headers, timeout=90)
            else:
                r = requests.get(url, headers=headers, timeout=90)
            if r.status_code == 200:
                tmp = path + ".part"
                with open(tmp, "wb") as fh:
                    fh.write(r.content)
                os.replace(tmp, path)
                _record(path, method, rec_url, payload, r.status_code)
                time.sleep(sleep)  # be polite
                return path
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2  # back off
                continue
            raise RuntimeError(last)
        except requests.RequestException as exc:  # network-level
            last = repr(exc)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"failed after {tries} tries: {url} {payload} -> {last}")


def load(name: str):
    with open(os.path.join(RAW, name)) as fh:
        return json.load(fh)
