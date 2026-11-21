#!/usr/bin/env python3
"""Optional, read-only retrieval contract built on existing SpecMesh Map v0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

if __package__:
    from . import map_v0
    from .drive_evidence import drive_evidence
else:
    import map_v0
    from drive_evidence import drive_evidence

SCHEMA = "specmesh-retrieval-v0"
COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
PROJECT = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
MAX_FRAME = 1024 * 1024
RESULT_LIMIT = 5


def result(status, items=(), reason=None, **metadata):
    return {"status": status, "items": list(items), "reason": reason, **metadata}


def load_json(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_FRAME + 1)
    if len(raw) > MAX_FRAME:
        raise ValueError("input_too_large")
    return json.loads(raw)


def _spec_matches(spec, query):
    slug = spec.removeprefix("spec://")
    parts = re.findall(r"[a-zA-Z0-9]+", slug)
    if not parts:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\W_]*".join(map(re.escape, parts)) + r"(?![a-z0-9])"
    return re.search(pattern, query, re.I) is not None


def _terms(query):
    return set(re.findall(r"[A-Za-z0-9]{3,}", query.lower()))


def _local(root, query, requested_spec, requested_area):
    # Build in memory; never overwrite an existing cache or trust its currentness.
    try:
        graph = map_v0.build_graph(root)
    except (OSError, RuntimeError, ValueError):
        return result("failed", reason="map_build_failed"), None, None, None
    nodes = {n["id"]: n for n in graph["nodes"]}
    fingerprint = graph["source_fingerprint"]
    spec_ids = sorted(k for k in nodes if k.startswith("spec://"))
    choices = ([requested_spec] if requested_spec in spec_ids else []) if requested_spec else [
        k for k in spec_ids if _spec_matches(k, query)
    ]
    if len(choices) != 1:
        reason = "ambiguous_spec" if choices else "spec_not_found"
        return result("unbound" if choices else "no_match", reason=reason, candidates=choices), None, None, fingerprint
    spec = choices[0]
    relations = [
        e for e in graph["edges"]
        if e["from"] == spec and e["provenance"] == "asserted" and e["to"].startswith("code://")
    ]
    active = map_v0._injectable_areas(graph)
    candidate_areas = sorted({e["scope"] for e in relations if e.get("scope")})
    if requested_area and requested_area not in candidate_areas:
        return result("unbound", reason="area_not_bound_to_spec", candidates=candidate_areas), spec, None, fingerprint
    area = requested_area or (candidate_areas[0] if len(candidate_areas) == 1 else None)
    if (area and area not in active) or (candidate_areas and area is None):
        reason = "area_not_current" if area else "ambiguous_area"
        return result("unbound", reason=reason, candidates=candidate_areas), spec, area, fingerprint
    asserted = [e for e in relations if not e.get("scope") or e["scope"] == area]
    implementation, tests, related, unresolved = {}, {}, {}, []
    for edge in asserted:
        target, relation = edge["to"], edge["relation"]
        if nodes[target]["authority"] != "derived":
            unresolved.append(target)
            continue
        dest = implementation if relation == "implemented_by" else tests if relation == "verified_by" else related
        dest[target] = {"uri": target, "relation": relation, "provenance": "asserted"}
    impl_files = {uri.split("#")[0] for uri in implementation}
    terms = _terms(query)
    symbols = []
    for node in graph["nodes"]:
        uri = node["id"]
        if node["kind"] != "symbol" or uri.split("#")[0] not in impl_files:
            continue
        words = _terms(node["name"])
        hits = len(terms & words)
        if hits:
            symbols.append((hits, uri, {"uri": uri, "relation": "symbol_in_asserted_implementation", "provenance": "derived"}))
    symbols.sort(key=lambda entry: (-entry[0], entry[1]))
    for e in graph["edges"]:
        if e["relation"] == "tests" and e["to"] in impl_files and e["from"] not in tests:
            tests[e["from"]] = {"uri": e["from"], "relation": "tests", "provenance": "derived"}
    paths = []
    for n in graph["sources"]:
        name = n["path"]
        if re.fullmatch(r"plans/[^/]+/(?:task_plan|findings|progress|acceptance)\.md", name) and _spec_matches(spec, name.split("/")[1]):
            paths.append({"path": name, "provenance": "lexical_plan_path", "verification": "candidate_only"})
    missing = bool(unresolved or not implementation or not tests)
    data = result("partial" if missing else "matched", [*implementation.values(), *(e[2] for e in symbols)][:RESULT_LIMIT],
                  "missing_current_code_or_tests" if missing else None,
                  tests=list(tests.values())[:RESULT_LIMIT], related=list(related.values())[:RESULT_LIMIT], unresolved=sorted(set(unresolved)),
                  repository_documents=paths[:RESULT_LIMIT])
    return data, spec, area, fingerprint


def control_receipts(path, *, project, spec, area, revision):
    """Accept explicit out-of-band receipt exports, not a scan of a ControlMesh database."""
    if path is None:
        return result("not_checked", reason="control_receipt_export_not_supplied")
    if not (spec and area and revision):
        return result("unbound", reason="canonical_scope_requires_spec_area_revision")
    try:
        data = load_json(path)
        if (not isinstance(data, dict) or data.get("schema") != "controlmesh-receipts-v0"
                or not isinstance(data.get("items"), list) or any(not isinstance(row, dict) for row in data["items"])):
            return result("failed", reason="control_export_invalid")
    except (OSError, ValueError, RecursionError):
        return result("failed", reason="control_export_unreadable")
    rows, malformed = {}, False
    for row in data["items"]:
        if row.get("project") != project or row.get("spec_uri") != spec or row.get("area") != area or row.get("revision") != revision:
            continue
        def valid(v):
            return isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_:@./-]{1,180}", v) is not None
        if not all(valid(row.get(k)) for k in ("task_id", "run_id", "event_id")) or row.get("outcome") not in ("succeeded", "failed", "cancelled", "unknown"):
            malformed = True
            continue
        obj = {k: row[k] for k in ("task_id", "run_id", "event_id", "outcome")}
        key = tuple(obj[k] for k in ("task_id", "run_id", "event_id"))
        if key in rows and rows[key] != obj:
            return result("failed", reason="conflicting_control_outcome")
        rows[key] = obj
    return result("partial" if rows and malformed else "matched" if rows else "unbound" if malformed else "no_match",
                  [rows[k] for k in sorted(rows)[:RESULT_LIMIT]], "invalid_scoped_control_receipt" if malformed else None,
                  verification="caller_supplied_reference")


def history_evidence(materials_path, binding_path, *, project, spec, area, revision):
    """Only link indexed locators explicitly reviewed for this requirement; omit all bodies."""
    if materials_path is None and binding_path is None:
        return result("not_checked", reason="history_input_not_supplied")
    if binding_path is None or not all((spec, area, revision)):
        return result("unbound", reason="history_requires_reviewed_project_spec_area_revision_binding")
    try:
        binding = load_json(binding_path)
        if not isinstance(binding, dict) or binding.get("schema") != "specmesh-history-binding-v0":
            return result("failed", reason="history_binding_invalid")
        if tuple(binding.get(k) for k in ("project", "spec_uri", "area", "revision")) != (project, spec, area, revision):
            return result("unbound", reason="history_scope_mismatch")
        if materials_path is None:
            status = binding.get("search_status")
            if status not in ("not_indexed", "no_match", "failed"):
                return result("unbound", reason="history_materials_missing")
            return result(status, reason="caller_supplied_search_status", live_verified=False)
        data = load_json(materials_path)
        if (not isinstance(data, dict) or data.get("schema_version") != "history.indexed-materials.v1"
                or data.get("authorization") != "context_only" or data.get("binding") != "index_revision"
                or data.get("context_only") is not True or data.get("redacted") is not True):
            return result("failed", reason="history_materials_schema_invalid")
        fields = ("source", "store_id", "session_id", "index_revision")
        expected = tuple(binding.get(k) for k in fields)
        if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", v) for v in expected):
            return result("unbound", reason="history_locator_binding_incomplete")
        if expected != tuple(data.get(k) for k in fields):
            return result("unbound", reason="history_source_or_revision_mismatch")
        raw_rows = data.get("items")
        if not isinstance(raw_rows, list) or not 1 <= len(raw_rows) <= RESULT_LIMIT:
            return result("failed", reason="history_materials_items_invalid")
        items, seen = [], set()
        for row in raw_rows:
            if (not isinstance(row, dict) or expected != tuple(row.get(k) for k in fields)
                    or row.get("redacted") is not True or row.get("context_only") is not True):
                return result("failed", reason="history_materials_row_mismatch")
            locator = row.get("locator")
            pos, offset = row.get("message_index"), row.get("text_offset")
            if (not isinstance(locator, dict) or type(pos) is not int or pos < 0
                    or type(offset) is not int or offset < 0
                    or locator.get("message_index") != pos or locator.get("text_offset") != offset
                    or locator.get("index_revision") != expected[-1]
                    or (pos, offset) in seen):
                return result("failed", reason="history_locator_invalid")
            seen.add((pos, offset))
            item = dict(zip(fields, expected))
            item.update(message_index=pos, text_offset=offset, provenance="indexed_history_context")
            ref = locator.get("raw_ref")
            line = ref.get("line_no") if isinstance(ref, dict) else None
            if type(line) is int and line > 0:
                item["line_no"] = line
            items.append(item)
        return result("matched", items, reason="reviewed_binding_to_selected_cached_fragments",
                      coverage="selected_fragments_not_complete", live_verified=False)
    except (OSError, ValueError, RecursionError):
        return result("failed", reason="history_evidence_unreadable")


def retrieve(root, query, *, project, revision=None, spec=None, area=None, drive_manifest=None, control_export=None,
             history_materials=None, history_binding=None):
    project = project.lower()
    if not PROJECT.fullmatch(project):
        raise ValueError("project must be canonical owner/repository")
    if revision is not None and not COMMIT.fullmatch(revision):
        raise ValueError("revision must be a full lowercase Git object ID")
    if not query.strip() or len(query) > 512:
        raise ValueError("query must contain 1 to 512 characters")
    code, spec, area, fingerprint = _local(root, query.strip(), spec, area)
    bound = code["status"] in ("matched", "partial")
    out = {
        "schema": SCHEMA,
        "request": query,
        "identity": {"repository": project, "revision": revision,
                     "revision_basis": "caller_supplied" if revision else "unverified_worktree",
                     "source_fingerprint": fingerprint, "spec_uri": spec, "area": area},
        "sources": {
            "code": code,
            "control": control_receipts(control_export, project=project, spec=spec if bound else None, area=area, revision=revision),
            "history": history_evidence(history_materials, history_binding, project=project,
                                        spec=spec if bound else None, area=area, revision=revision),
            "drive": drive_evidence(drive_manifest, spec if bound else None, area, project, revision),
        },
    }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project", required=True, help="repository identity owner/name")
    parser.add_argument("--revision", help="caller-supplied full commit; graph fingerprint separately reflects workspace")
    parser.add_argument("--spec", help="exact spec:// identity")
    parser.add_argument("--area", help="exact area: identity; required for multiply-bound specs")
    parser.add_argument("--drive-manifest", type=Path, help="optional locally reviewed Drive bindings")
    parser.add_argument("--control-export", type=Path, help="optional explicit task/run/event receipt export")
    parser.add_argument("--history-materials", type=Path, help="selected native AgentTraceMesh materials JSON")
    parser.add_argument("--history-binding", type=Path, help="reviewed binding from requirement to native material identity")
    parser.add_argument("query")
    args = parser.parse_args(argv)
    try:
        response = retrieve(args.root.resolve(), args.query, project=args.project, revision=args.revision,
                            spec=args.spec, area=args.area, drive_manifest=args.drive_manifest,
                            control_export=args.control_export, history_materials=args.history_materials,
                            history_binding=args.history_binding)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if response["sources"]["code"]["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
