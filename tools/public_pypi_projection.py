#!/usr/bin/env python3
"""Fail-closed public projection of an authorized private PyPI manifest.

Only previously published, publicly resolvable package identities leave this
boundary. Held, internal, never, third-party and queued rows are never copied.
This is a dated governance snapshot, not a live or cryptographic re-verification.
"""
import datetime as dt
import hashlib
import json
import re

NAME = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
PUBLISHED_KEYS = ("name", "repo", "status", "pypi_version", "pypi_url", "source")

class ProjectionHold(ValueError):
    """Source data cannot be transformed into a safe public catalog."""

def _unique_pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ProjectionHold("DUPLICATE_JSON_KEY")
        out[key] = value
    return out

def public_projection(raw: bytes, revision: str) -> bytes:
    if not isinstance(raw, bytes) or len(raw) > 2_000_000:
        raise ProjectionHold("SOURCE_SIZE_UNAVAILABLE")
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ProjectionHold("IMMUTABLE_SOURCE_REVISION_UNAVAILABLE")
    try:
        source = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError) as exc:
        raise ProjectionHold("INVALID_SOURCE_JSON") from exc
    if not isinstance(source, dict) or source.get("schema") != "szl.pypi-packages.v1":
        raise ProjectionHold("INVALID_SOURCE_SCHEMA")
    generated_at = source.get("generated_at")
    if not isinstance(generated_at, str):
        raise ProjectionHold("SOURCE_TIMESTAMP_UNAVAILABLE")
    try:
        timestamp = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionHold("INVALID_SOURCE_TIMESTAMP") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != dt.timedelta(0):
        raise ProjectionHold("UNTRUSTED_SOURCE_TIMEZONE")
    rows = source.get("packages")
    if not isinstance(rows, list) or not rows:
        raise ProjectionHold("SOURCE_PACKAGE_COVERAGE_UNAVAILABLE")
    public, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("status"), str):
            raise ProjectionHold("INVALID_SOURCE_PACKAGE_ROW")
        if row["status"] != "published":
            continue
        if not all(isinstance(row.get(k), str) for k in PUBLISHED_KEYS):
            raise ProjectionHold("PUBLISHED_FIELDS_UNAVAILABLE")
        name, repo = row["name"], row["repo"]
        if not NAME.fullmatch(name) or not NAME.fullmatch(repo):
            raise ProjectionHold("INVALID_PUBLISHED_IDENTITY")
        if name in seen:
            raise ProjectionHold("DUPLICATE_PUBLISHED_NAME")
        seen.add(name)
        if not VERSION.fullmatch(row["pypi_version"]):
            raise ProjectionHold("INVALID_PUBLISHED_VERSION")
        if row["pypi_url"] != f"https://pypi.org/project/{name}/":
            raise ProjectionHold("UNEXPECTED_PYPI_LINK")
        if row["source"].rstrip("/") != f"https://github.com/szl-holdings/{repo}":
            raise ProjectionHold("UNEXPECTED_GITHUB_SOURCE")
        public.append({key: row[key] for key in PUBLISHED_KEYS})
    if not public:
        raise ProjectionHold("NO_PUBLISHED_PROJECTS")
    public.sort(key=lambda x: x["name"])
    result = {
        "schema": "szl.pypi-packages.v1",
        "generated_at": generated_at,
        "public_projection": {
            "schema": "szl.public-pypi-projection/v1",
            "source_repository": "szl-holdings/szl-org-health",
            "source_commit": revision,
            "source_manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "omitted_statuses": ["queued", "hold", "internal", "never", "third-party"],
            "limitations": "Dated source audit; no new live PyPI or attestation readback",
        },
        "counts": {"published": len(public), "queued": 0},
        "packages": public,
    }
    return (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
