"""Read-only adapter for an explicit Drive evidence binding manifest.

A match links previously observed metadata, not live Drive verification. Neither
the path nor a record can trigger an API call, a download, or credential access.
"""
from datetime import datetime
import json
from pathlib import Path
import re

_MAX_BYTES = 1024 * 1024
_FILE_ID = re.compile(r"[A-Za-z0-9_-]{10,200}\Z")
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z\Z")


def _utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean(value, max_length):
    return (
        isinstance(value, str) and 0 < len(value) <= max_length
        and value == value.strip() and value.isprintable()
    )


def drive_evidence(manifest_path, spec_uri, area, project, revision):
    """Return strictly scope-bound items without reading file contents from Drive.

    A malformed candidate for *this* scope is unbound; valid records for other
    commits/projects are no match, never fallback evidence. A matched manifest
    does not assert ongoing accessibility, authenticity, or freshness.
    """
    def result(status, reason, items=None):
        return {
            "status": status,
            "reason": reason,
            "items": [] if items is None else items,
            "source": "drive_binding_manifest",
            "live_verified": False,
        }

    if manifest_path is None:
        return result("not_checked", "manifest_not_supplied")
    if not all(_clean(value, limit) for value, limit in ((spec_uri, 500), (area, 200), (project, 300))):
        return result("unbound", "request_scope_not_explicit")
    if not isinstance(revision, str) or not _COMMIT.fullmatch(revision):
        return result("unbound", "request_requires_full_commit")
    try:
        with Path(manifest_path).open("rb") as handle:
            payload = handle.read(_MAX_BYTES + 1)
        if len(payload) > _MAX_BYTES:
            return result("failed", "manifest_too_large")
        envelope = json.loads(payload)
    except FileNotFoundError:
        return result("failed", "manifest_not_found")
    except (OSError, TypeError, ValueError, RecursionError):
        return result("failed", "manifest_unreadable")
    if (
        not isinstance(envelope, dict)
        or type(envelope.get("schema_version")) is not int
        or envelope["schema_version"] != 1
        or not isinstance(envelope.get("items"), list)
        or any(not isinstance(row, dict) for row in envelope["items"])
    ):
        return result("failed", "manifest_schema_invalid")
    accepted = {}
    unbound = 0
    conflicts = set()
    for row in envelope["items"]:
        if row.get("spec_uri") != spec_uri or row.get("area") != area or row.get("project") != project:
            continue
        bound_revision = row.get("revision")
        if not isinstance(bound_revision, str) or not _COMMIT.fullmatch(bound_revision):
            unbound += 1
            continue
        if bound_revision != revision:
            continue
        file_id = row.get("file_id")
        title = row.get("title")
        timestamp = row.get("observed_at")
        observed = _utc(timestamp)
        if not isinstance(file_id, str) or not _FILE_ID.fullmatch(file_id) or not _clean(title, 300) or observed is None:
            unbound += 1
            continue
        if file_id in accepted and accepted[file_id]["title"] != title:
            conflicts.add(file_id)
            continue
        if file_id in accepted and _utc(accepted[file_id]["observed_at"]) >= observed:
            continue
        accepted[file_id] = {
            "file_id": file_id,
            "url": f"https://drive.google.com/file/d/{file_id}/view",
            "spec_uri": spec_uri,
            "area": area,
            "project": project,
            "revision": revision,
            "title": title,
            "observed_at": timestamp,
        }
    for file_id in conflicts:
        accepted.pop(file_id, None)
    if accepted:
        return result(
            "matched", "explicit_manifest_binding",
            sorted(accepted.values(), key=lambda item: (_utc(item["observed_at"]), item["file_id"]), reverse=True),
        )
    if unbound or conflicts:
        return result("unbound", "scope_records_missing_valid_binding")
    return result("no_match", "no_exact_scope_and_revision_match")
