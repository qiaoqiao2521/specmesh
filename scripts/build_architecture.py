#!/usr/bin/env python3
"""Build an offline, human-readable view of reviewed architecture and Map v0.

The reviewed JSON supplies labels and business relations; existing Map v0 supplies
file/symbol facts and area gates. Checks run only with --run-checks. Generated
files are disposable and never update project memory or architecture declarations.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

if __package__:
    from . import map_v0
else:
    import map_v0


MODEL_SCHEMA = "specmesh-architecture-v1"
VIEW_SCHEMA = "specmesh-architecture-view-v1"
STATUS_SCHEMA = "specmesh-architecture-status-v1"
PLACEHOLDER = "__SPECMESH_DATA__"
MARKER = ".specmesh-architecture-output"
IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}\Z")
PROJECT_ID = re.compile(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+\Z")
STATUSES = ("pass", "fail", "unknown", "stale", "blocked")
MAX_JSON = 2 * 1024 * 1024
ENGINE_ROOT = Path(__file__).resolve().parents[1]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("JSON input exceeds 2 MiB")
    return json.loads(raw)


def _text(value, label, maximum=2000, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not value.strip() and not allow_empty):
        raise ValueError(f"{label}: expected nonempty text, at most {maximum} characters")
    return value


def _id(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label}: invalid identifier")
    return value


def _relative(value):
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 for c in value):
        raise ValueError("path must be a repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("..", ".git") for p in path.parts) or str(path) != value or value == ".":
        raise ValueError(f"unsafe repository path: {value!r}")
    return value


def _under(root, relative):
    relative = _relative(relative)
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"path escapes repository through symlink: {relative}")
    return path


def _objects(value, label, maximum=200):
    if not isinstance(value, list) or len(value) > maximum or any(not isinstance(x, dict) for x in value):
        raise ValueError(f"{label}: expected an array of up to {maximum} objects")
    return value


def validate_model(value):
    """Fail loudly on malformed reviewed declarations; no normalization of IDs."""
    if not isinstance(value, dict) or value.get("schema") != MODEL_SCHEMA:
        raise ValueError(f"expected schema {MODEL_SCHEMA}")
    project = value.get("project")
    if not isinstance(project, dict) or not PROJECT_ID.fullmatch(str(project.get("id", ""))):
        raise ValueError("project.id must be owner/repository")
    _text(project.get("title"), "project.title", 160)
    _text(project.get("subtitle", ""), "project.subtitle", 1000, True)
    canonical_url = f"https://github.com/{project['id']}"
    if project.get("repository_url") != canonical_url:
        raise ValueError("project.repository_url must be the matching canonical HTTPS GitHub URL")
    layers, modules, checks, relations = (
        _objects(value.get(key, []), key) for key in ("layers", "modules", "checks", "relations")
    )
    if not layers or not modules:
        raise ValueError("at least one layer and module is required")
    indexes = {}
    for label, items in (("layer", layers), ("module", modules), ("check", checks)):
        ids = [_id(item.get("id"), f"{label}.id") for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate {label} ID")
        indexes[label] = set(ids)
    for layer in layers:
        _text(layer.get("label"), "layer.label", 160)
    for item in modules:
        _text(item.get("title"), "module.title", 160)
        _text(item.get("summary", ""), "module.summary", 2000, True)
        if item.get("layer") not in indexes["layer"]:
            raise ValueError("module references an unknown layer")
        if type(item.get("order", 0)) is not int:
            raise ValueError("module.order must be an integer")
        for key in ("paths", "checks", "anchors"):
            entries = item.get(key, [])
            if not isinstance(entries, list) or len(entries) > 100 or any(not isinstance(x, str) for x in entries):
                raise ValueError(f"module.{key} must be an array of strings")
            if len(set(entries)) != len(entries):
                raise ValueError(f"module.{key} has duplicate entries")
        if not item.get("paths"):
            raise ValueError("module.paths must identify at least one file or directory")
        for path in item["paths"]:
            _relative(path)
        for anchor in item.get("anchors", []):
            if not anchor.startswith("code://"):
                raise ValueError("module anchors must use code://")
            _relative(anchor[7:].split("#", 1)[0])
        if not set(item.get("checks", [])) <= indexes["check"]:
            raise ValueError("module references an unknown check")
        if "area" in item and not map_v0.AREA_ID_RE.fullmatch(str(item["area"])):
            raise ValueError("module.area must be a canonical area: identifier")
    for check in checks:
        _text(check.get("label"), "check.label", 200)
        argv = check.get("command")
        if not isinstance(argv, list) or not argv or len(argv) > 100 or any(
            not isinstance(a, str) or not a or len(a) > 4000 or "\0" in a for a in argv
        ):
            raise ValueError("check.command must be a nonempty argv array")
        timeout = check.get("timeout_seconds", 60)
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError("check timeout_seconds must be between 1 and 600")
    seen_relations = set()
    for edge in relations:
        if edge.get("from") not in indexes["module"] or edge.get("to") not in indexes["module"]:
            raise ValueError("relation endpoint is not a declared module")
        if edge["from"] == edge["to"]:
            raise ValueError("self relations are not supported")
        if edge.get("authority") != "asserted":
            raise ValueError("reviewed architecture relations must have authority=asserted")
        _text(edge.get("label"), "relation.label", 300)
        _id(edge.get("kind"), "relation.kind")
        key = (edge["from"], edge["to"], edge["kind"])
        if key in seen_relations:
            raise ValueError("duplicate architecture relation")
        seen_relations.add(key)
        evidence = edge.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > 30:
            raise ValueError("relation.evidence must be an array of paths")
        for path in evidence:
            _relative(path)
    return value


def _generated_path(relative):
    p = PurePosixPath(relative)
    return p.parts[0] == "dist" or p.parts[:2] == (".specmesh", "cache")


def _map_inputs(root):
    """Require every file Map reads outside its manifest loop to be bound too."""
    participating = {path.relative_to(root).as_posix() for path in map_v0.participating_files(root)}
    inputs = {}

    def read(relative):
        path = _under(root, relative)
        if _generated_path(relative):
            raise ValueError(f"Map input cannot be a generated output: {relative}")
        if not path.exists():
            inputs[relative] = None
            return None
        if not path.is_file() or relative not in participating:
            raise ValueError(f"Map input must participate in the source manifest: {relative}")
        content = path.read_bytes()
        inputs[relative] = _hash(content)
        return content

    # Check the context itself before asking Map's parser to read it. Its
    # configured memory/area files may be ignored or symlinked independently.
    read(".specmesh/context.md")
    config = map_v0.read_context(root)
    read(str(config["memory_root"]))
    area_path = str(config["areas_path"])
    area_content = read(area_path)
    areas = map_v0.parse_areas(area_content.decode("utf-8"), source=area_path) if area_content is not None else []
    return inputs, areas


def _graph(root):
    inputs, areas = _map_inputs(root)
    graph = map_v0.build_graph(root)
    current_inputs, _ = _map_inputs(root)
    manifest = {entry["path"]: entry["sha256"] for entry in graph["sources"]}
    if current_inputs != inputs or any(digest is not None and manifest.get(path) != digest
                                      for path, digest in inputs.items()):
        raise ValueError("Map configuration inputs changed while building the graph; rebuild the view")
    # Map already excludes its cache; exclude the Explorer's conventional dist
    # outputs too, including when reading an unpacked non-Git source directory.
    sources = [s for s in graph["sources"] if not _generated_path(s["path"])]
    removed = {n["id"] for n in graph["nodes"] if n["id"].startswith("code://")
               and _generated_path(n["id"][7:].split("#", 1)[0])}
    graph["sources"] = sources
    graph["source_fingerprint"] = map_v0.manifest_fingerprint(sources)
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in removed]
    graph["edges"] = [e for e in graph["edges"] if e["from"] not in removed and e["to"] not in removed]
    owners = {}
    for node in graph["nodes"]:
        if node["kind"] == "symbol" and node["authority"] == "derived":
            owners.setdefault(node["name"], []).append(node["id"])
    graph["source_state"]["area_resolution"] = map_v0.resolve_areas(
        areas, [s["path"] for s in sources], owners)
    return graph


def _git(root, args):
    return subprocess.run(["git", "--no-pager", *args], cwd=root, capture_output=True, text=True,
                          timeout=20, check=False)


def _source(root, graph, model, template):
    try:
        revision_result = _git(root, ["rev-parse", "--verify", "HEAD"])
        revision = revision_result.stdout.strip() if revision_result.returncode == 0 else None
        top_level = _git(root, ["rev-parse", "--show-toplevel"])
        if top_level.returncode or Path(top_level.stdout.strip()).resolve() != root:
            revision = None
        dirty_result = _git(root, ["diff", "--name-only", "--no-renames", "-z", "HEAD", "--"])
        untracked = _git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
        dirty = (any(p and not _generated_path(p) for p in (dirty_result.stdout + untracked.stdout).split("\0"))
                 if revision and dirty_result.returncode == untracked.returncode == 0 else None)
    except (OSError, subprocess.TimeoutExpired):
        revision, dirty = None, None
    if revision and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        revision = None
    template_fingerprint = _hash(template.encode("utf-8"))
    build_fingerprint = _hash(_json_bytes({
        "source": graph["source_fingerprint"], "model": _hash(_json_bytes(model)),
        "template": template_fingerprint, "builder": _hash(Path(__file__).read_bytes()),
        "map_engine": _hash(Path(map_v0.__file__).read_bytes()),
    }))
    return {"revision": revision, "dirty": dirty, "revision_basis": "git_head" if revision else "unversioned",
            "source_fingerprint": graph["source_fingerprint"], "build_fingerprint": build_fingerprint,
            "template_fingerprint": template_fingerprint,
            "generated_at": _now()}


def _binding(source):
    return {key: source[key] for key in ("revision", "dirty", "source_fingerprint", "build_fingerprint")}


def _check_record(check, status="unknown", reason="not_run"):
    return {"id": check["id"], "label": check["label"], "command": list(check["command"]),
            "status": status, "reason": reason, "exit_code": None, "duration_ms": None,
            "observed_at": None, "output_excerpt": ""}


def _run_check(check, root):
    result = _check_record(check)
    started = time.monotonic()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryFile() as log:
        try:
            process = subprocess.Popen(check["command"], cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, shell=False,
                                       start_new_session=os.name == "posix")
            try:
                code = process.wait(timeout=check.get("timeout_seconds", 60))
                result.update(status="pass" if code == 0 else "fail", reason="command_completed", exit_code=code)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                result.update(status="fail", reason="timeout", exit_code=process.returncode)
        except (FileNotFoundError, PermissionError, OSError):
            result.update(status="unknown", reason="command_unavailable")
        log.seek(0, os.SEEK_END)
        log.seek(max(0, log.tell() - 2000))
        result["output_excerpt"] = log.read().decode("utf-8", errors="replace").replace(str(root), "$REPO")
    result.update(duration_ms=round((time.monotonic() - started) * 1000), observed_at=_now())
    return result


def _prior_checks(path, checks, source):
    if path is None:
        return [_check_record(check) for check in checks]
    previous = _read_json(path)
    if not isinstance(previous, dict) or previous.get("schema") != STATUS_SCHEMA:
        raise ValueError("results must be a generated specmesh-architecture-status-v1 file")
    rows = _objects(previous.get("checks"), "previous checks")
    by_id = {}
    for row in rows:
        key = row.get("id")
        if not isinstance(key, str) or key in by_id:
            raise ValueError("previous checks have missing or duplicate IDs")
        if row.get("status") not in STATUSES:
            raise ValueError("previous check has an invalid status")
        by_id[key] = row
    same_binding = previous.get("binding") == _binding(source)
    output = []
    for check in checks:
        old = by_id.get(check["id"])
        if old is None:
            output.append(_check_record(check, reason="no_matching_result"))
            continue
        row = _check_record(check)
        for key in ("status", "reason", "exit_code", "duration_ms", "observed_at", "output_excerpt", "observed_status"):
            if key in old:
                row[key] = old[key]
        dated = False
        try:
            observed = datetime.fromisoformat(old.get("observed_at", ""))
            dated = observed.tzinfo is not None and observed <= datetime.now(timezone.utc)
        except (TypeError, ValueError):
            pass
        valid_outcome = (row["status"] != "pass" or type(row.get("exit_code")) is int and row["exit_code"] == 0)
        if not dated or not valid_outcome:
            row.update(status="unknown", reason="unverifiable_result_metadata")
        elif not same_binding or old.get("command") != check["command"]:
            row.update(observed_status=old.get("observed_status", old["status"]), status="stale",
                       reason="source_or_definition_changed")
        output.append(row)
    return output


def _head_paths(root, source):
    if not source["revision"]:
        return set()
    try:
        result = _git(root, ["ls-tree", "--full-tree", "-r", "--name-only", "-z", source["revision"]])
        return set(result.stdout.split("\0")) if result.returncode == 0 else set()
    except (OSError, subprocess.TimeoutExpired):
        return set()


def _url(project, source, path, head_paths):
    if not source["revision"] or path not in head_paths:
        return None
    return f"{project['repository_url']}/blob/{source['revision']}/{quote(path, safe='/')}"


def _modules(root, model, graph, source, checks, head_paths):
    source_paths = {s["path"] for s in graph["sources"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    active = map_v0._injectable_areas(graph)
    areas = graph["source_state"]["area_resolution"]
    check_index = {c["id"]: c for c in checks}
    result = []
    for declaration in model["modules"]:
        reasons, files = [], {}
        for path in declaration["paths"]:
            _under(root, path)
            matches = sorted(p for p in source_paths if p == path or p.startswith(path + "/"))
            if not matches or _generated_path(path):
                reasons.append(f"path_not_in_current_sources:{path}")
                files[path] = {"path": path, "exists": False, "url": None}
            for found in matches:
                url = _url(model["project"], source, found, head_paths)
                files[found] = {"path": found, "exists": True, "url": url,
                                "authority": "derived", "url_basis": "git_head" if url else None}
        for anchor in declaration.get("anchors", []):
            _under(root, anchor[7:].split("#", 1)[0])
            if anchor not in nodes or nodes[anchor]["authority"] != "derived":
                reasons.append(f"anchor_not_current:{anchor}")
        area = declaration.get("area")
        area_status = None
        if area:
            area_status = areas.get(area, {}).get("state", "unbound")
            if areas.get(area, {}).get("superseded_by"):
                area_status = "superseded"
            if area not in active:
                reasons.append(f"area_not_current:{area}")
        selected_checks = [check_index[c] for c in declaration.get("checks", [])]
        statuses = {c["status"] for c in selected_checks}
        status = "unknown"
        if reasons:
            status = "blocked"
        elif "fail" in statuses:
            status = "fail"
        elif "stale" in statuses:
            status = "stale"
        elif selected_checks and statuses == {"pass"}:
            status = "pass"
        elif "blocked" in statuses:
            status = "blocked"
        item = {**declaration, "order": declaration.get("order", 0), "files": list(files.values()),
                "check_ids": list(declaration.get("checks", [])), "checks": selected_checks,
                "status": status, "reasons": reasons, "structure_valid": not reasons,
                "area_status": area_status, "authority": "asserted"}
        result.append(item)
    layer_order = {layer["id"]: index for index, layer in enumerate(model["layers"])}
    return sorted(result, key=lambda m: (layer_order[m["layer"]], m["order"], m["id"]))


def _relations(root, model, modules, source, graph, head_paths):
    current = {m["id"]: m["structure_valid"] for m in modules}
    source_paths = {s["path"] for s in graph["sources"]}
    edges = []
    for declaration in model.get("relations", []):
        evidence = []
        for path in declaration.get("evidence", []):
            disk = _under(root, path)
            exists = disk.is_file() and path in source_paths
            evidence.append({"path": path, "exists": exists,
                             "url": _url(model["project"], source, path, head_paths) if exists else None})
        active = current[declaration["from"]] and current[declaration["to"]] and all(e["exists"] for e in evidence)
        edges.append({**declaration, "evidence": evidence, "active": active,
                      "reason": None if active else "endpoint_or_evidence_not_current"})
    return edges


def affected_modules(paths, modules, relations):
    """Return conservative declared downstream impact, not a behavior verdict."""
    direct, unmapped = set(), []
    for path in paths:
        owners = {m["id"] for m in modules if any(path == p or path.startswith(p + "/") for p in m["paths"])}
        direct.update(owners)
        if not owners:
            unmapped.append(path)
    adjacency = {m["id"]: set() for m in modules}
    for edge in relations:
        if edge.get("active", True):
            adjacency[edge["from"]].add(edge["to"])
    affected, queue = set(direct), deque(sorted(direct))
    while queue:
        for target in sorted(adjacency[queue.popleft()] - affected):
            affected.add(target)
            queue.append(target)
    return {"direct_modules": sorted(direct), "affected_modules": sorted(affected), "unmapped_files": sorted(unmapped)}


def _changes(root, base, modules, relations):
    empty = {"available": False, "base": base, "files": [], "reason": "base_ref_not_supplied"}
    if not base:
        return {**empty, **affected_modules([], modules, relations)}
    try:
        top_level = _git(root, ["rev-parse", "--show-toplevel"])
        if top_level.returncode or Path(top_level.stdout.strip()).resolve() != root:
            return {**empty, "reason": "git_root_unavailable", **affected_modules([], modules, relations)}
        verified = _git(root, ["rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"])
        if verified.returncode:
            empty["reason"] = "base_ref_unavailable"
            return {**empty, **affected_modules([], modules, relations)}
        base_sha = verified.stdout.strip()
        diff = _git(root, ["diff", "--name-only", "--no-renames", "-z", base_sha, "--"])
        untracked = _git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
        if diff.returncode or untracked.returncode:
            empty["reason"] = "git_diff_unavailable"
            return {**empty, **affected_modules([], modules, relations)}
        paths = sorted({p for p in (diff.stdout + untracked.stdout).split("\0") if p and not _generated_path(p)})
        return {"available": True, "base": base, "base_revision": base_sha, "files": paths, "reason": None,
                **affected_modules(paths, modules, relations)}
    except (OSError, subprocess.TimeoutExpired):
        return {**empty, "reason": "git_unavailable", **affected_modules([], modules, relations)}


def build_architecture(root, model_path=None, *, template_path=None, run_checks=False, results_path=None, base_ref=None):
    root = Path(root).resolve(strict=True)
    model_path = Path(model_path or "architecture/architecture.json")
    if not model_path.is_absolute():
        model_path = root / model_path
    model_path = model_path.resolve(strict=True)
    if not model_path.is_relative_to(root) or _generated_path(model_path.relative_to(root).as_posix()):
        raise ValueError("reviewed model must be inside repository source, outside generated directories")
    model = validate_model(_read_json(model_path))
    template_path = Path(template_path or ENGINE_ROOT / "architecture/explorer.html")
    template = template_path.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("viewer template must contain exactly one data placeholder")
    graph = _graph(root)
    source = _source(root, graph, model, template)
    head_paths = _head_paths(root, source)
    observed_binding = _binding(source)
    if run_checks and results_path is not None:
        raise ValueError("choose --run-checks or --results, not both")
    # Validate paths and area gates before executing any explicitly requested checks.
    pending = [_check_record(c) for c in model.get("checks", [])]
    preliminary = _modules(root, model, graph, source, pending, head_paths)
    _relations(root, model, preliminary, source, graph, head_paths)
    checks = ([_run_check(check, root) for check in model.get("checks", [])] if run_checks
              else _prior_checks(results_path, model.get("checks", []), source))
    if run_checks:
        fresh_graph = _graph(root)
        fresh_template = template_path.read_text(encoding="utf-8")
        fresh_source = _source(root, fresh_graph, model, fresh_template)
        if _binding(fresh_source) != observed_binding:
            for check in checks:
                check.update(observed_status=check["status"], status="stale", reason="sources_changed_during_checks")
            graph, source = fresh_graph, fresh_source
            head_paths = _head_paths(root, source)
    modules = _modules(root, model, graph, source, checks, head_paths)
    relations = _relations(root, model, modules, source, graph, head_paths)
    active_areas = map_v0._injectable_areas(graph)
    map_relations = [edge for edge in graph["edges"] if edge.get("scope") is None or edge["scope"] in active_areas]
    result = {"schema": VIEW_SCHEMA, "project": model["project"], "source": source, "layers": model["layers"],
              "modules": modules, "relations": relations, "checks": checks,
              "changes": _changes(root, base_ref, modules, relations),
              "map": {"schema": graph["schema"], "areas": graph["source_state"]["area_resolution"],
                      "relations": map_relations, "authority": "derived_structure_with_asserted_relations"},
              "summary": {"modules": len(modules), "relations": len(relations), "checks": len(checks),
                          "status_counts": dict(Counter(m["status"] for m in modules)),
                          "check_status_counts": dict(Counter(c["status"] for c in checks))},
              "verification": {"scope": "declared_checks_only", "architecture_relations": "reviewed_declarations",
                               "impact": "declared_downstream_candidates_not_proven_breakage"}}
    result["check_binding"] = observed_binding if run_checks else _binding(source)
    return result


def validate_output(root, output):
    root, given = Path(root).resolve(), Path(output).absolute()
    if any(p.is_symlink() for p in (given, *given.parents)):
        raise ValueError("output path cannot traverse a symlink")
    output = given.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError("output cannot overwrite or contain the source root")
    if output.is_relative_to(root):
        relative = output.relative_to(root)
        allowed = (relative.parts[0] == "dist" and len(relative.parts) > 1
                   or relative.parts[:2] == (".specmesh", "cache") and len(relative.parts) > 2)
        if not allowed:
            raise ValueError("in-repository output must be below dist/ or .specmesh/cache/")
    if output.exists():
        if not output.is_dir():
            raise ValueError("output is not a directory")
        entries = list(output.iterdir())
        for name in (MARKER, "index.html", "architecture.json", "status.json"):
            if (output / name).is_symlink():
                raise ValueError("output file cannot be a symlink")
        if entries and not (output / MARKER).is_file():
            raise ValueError("refusing to overwrite a nonempty directory without the generated-output marker")
        if (output / MARKER).exists() and (output / MARKER).read_text() != VIEW_SCHEMA + "\n":
            raise ValueError("generated-output marker is invalid")
    return output


def write_bundle(payload, output, *, root, template_path=None):
    output = validate_output(root, output)
    template = Path(template_path or ENGINE_ROOT / "architecture/explorer.html").read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("viewer template must contain exactly one data placeholder")
    if _hash(template.encode("utf-8")) != payload["source"]["template_fingerprint"]:
        raise ValueError("viewer template changed after source binding; rebuild the view")
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    embedded = embedded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    page = template.replace(PLACEHOLDER, embedded)
    status = {"schema": STATUS_SCHEMA, "generated_at": payload["source"]["generated_at"],
              "binding": payload["check_binding"], "checks": payload["checks"]}
    output.mkdir(parents=True, exist_ok=True)
    (output / MARKER).write_text(VIEW_SCHEMA + "\n", encoding="utf-8")
    (output / "index.html").write_text(page, encoding="utf-8")
    for name, data in (("architecture.json", payload), ("status.json", status)):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model", type=Path, default=Path("architecture/architecture.json"))
    parser.add_argument("--output", type=Path, help="generated directory; default: ROOT/dist/architecture")
    parser.add_argument("--run-checks", action="store_true", help="explicitly execute reviewed argv checks")
    parser.add_argument("--results", type=Path, help="read previous generated status.json; does not execute checks")
    parser.add_argument("--base-ref", help="Git commit/ref used for observed file changes")
    parser.add_argument("--check", action="store_true", help="validate model and current bindings; no output writes or checks")
    args = parser.parse_args(argv)
    if args.check and (args.run_checks or args.results):
        parser.error("--check cannot be combined with --run-checks or --results")
    root = args.root.resolve()
    output = args.output or root / "dist/architecture"
    try:
        if not args.check:
            validate_output(root, output)
        payload = build_architecture(root, args.model, run_checks=args.run_checks, results_path=args.results, base_ref=args.base_ref)
        blocked = any(not module["structure_valid"] for module in payload["modules"]) or any(not e["active"] for e in payload["relations"])
        if not args.check:
            write_bundle(payload, output, root=root)
        evidence_requested = args.run_checks or args.results is not None
        failed_checks = evidence_requested and any(c["status"] != "pass" for c in payload["checks"])
        print(json.dumps({"schema": VIEW_SCHEMA, "output": str(output.resolve()) if not args.check else None,
                          "source": payload["source"], "summary": payload["summary"],
                          "structural_validation": "blocked" if blocked else "valid"}, ensure_ascii=False))
        return 1 if blocked or failed_checks else 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
