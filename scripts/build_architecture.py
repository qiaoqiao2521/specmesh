#!/usr/bin/env python3
"""Build an offline, human-readable view of Map v0 and its Git evolution.

Map provides the primary nodes, edges, areas, and global/focus selection. Optional
reviewed JSON adds business modules and checks. Checks run only with --run-checks.
Generated files never update project memory or architecture declarations.
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
from urllib.parse import quote, urlsplit

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


def _project(root):
    project = {"id": root.name, "title": root.name, "subtitle": "SpecMesh Map", "repository_url": None}
    try:
        top = _git(root, ["rev-parse", "--show-toplevel"])
        if top.returncode or Path(top.stdout.strip()).resolve() != root:
            return project
        remote = _git(root, ["config", "--get", "remote.origin.url"])
        origin = remote.stdout.strip() if remote.returncode == 0 else ""
        if origin.startswith("git@github.com:"):
            name = origin[len("git@github.com:"):]
        else:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("https", "ssh") or parsed.hostname != "github.com":
                return project
            name = parsed.path.lstrip("/")
        name = name.removesuffix(".git").rstrip("/")
        if PROJECT_ID.fullmatch(name):
            project.update(id=name, title=name.rsplit("/", 1)[-1], repository_url="https://github.com/" + name)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return project


def _model(root, model_path, no_model):
    if no_model and model_path is not None:
        raise ValueError("choose --model or --no-model, not both")
    path = Path(model_path) if model_path is not None else root / "architecture/architecture.json"
    if not path.is_absolute():
        path = root / path
    if no_model or model_path is None and not path.exists():
        return {"schema": MODEL_SCHEMA, "project": _project(root), "layers": [], "modules": [],
                "relations": [], "checks": []}, None
    path = path.resolve(strict=True)
    if not path.is_relative_to(root) or _generated_path(path.relative_to(root).as_posix()):
        raise ValueError("reviewed model must be inside repository source, outside generated directories")
    return validate_model(_read_json(path)), path.relative_to(root).as_posix()


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
    if not project.get("repository_url") or not source["revision"] or path not in head_paths:
        return None
    return f"{project['repository_url']}/blob/{source['revision']}/{quote(path, safe='/')}"


def _native_map(graph, project, source, head_paths, budget, focus):
    active = map_v0._injectable_areas(graph)
    gated = map_v0._gated_memory_nodes(graph, active)
    areas = graph["source_state"]["area_resolution"]
    manifest = {entry["path"]: entry["sha256"] for entry in graph["sources"]}
    nodes = []
    for original in graph["nodes"]:
        if original["id"] in gated:
            continue
        node = dict(original)
        node["area_ids"] = sorted(area_id for area_id in active if any(
            anchor["resolved"] == node["id"] or anchor["resolved"] == node["id"].split("#", 1)[0]
            for anchor in areas[area_id]["anchors"]))
        if node["id"].startswith("code://"):
            path = node["id"][7:].split("#", 1)[0]
            exists = path in manifest and node["authority"] == "derived"
            node.update(path=path, exists=exists, source_sha256=manifest.get(path) if exists else None,
                        url=_url(project, source, path, head_paths) if exists else None)
        nodes.append(node)
    ids = {node["id"] for node in nodes}
    edges = [{**edge, "key": map_v0.edge_key(edge)} for edge in graph["edges"]
             if edge["from"] in ids and edge["to"] in ids
             and (edge.get("scope") is None or edge["scope"] in active)]
    selection = map_v0.select_view(graph, budget, focus)
    selection = {key: value for key, value in selection.items() if key not in ("nodes", "edges", "areas")}
    return {"schema": graph["schema"], "nodes": nodes, "edges": edges, "relations": edges,
            "areas": areas, "selection": selection,
            "counts": {"nodes": len(nodes), "edges": len(edges), "selected_nodes": len(selection["node_ids"]),
                       "selected_edges": len(selection["edge_keys"])},
            "authority": "derived_structure_with_asserted_relations"}


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


class EvolutionUnavailable(ValueError):
    pass


def _object_git(root, args, *, binary=False):
    # Revision reads never fetch promisor objects, run filters, or use replace refs.
    environment = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", "--no-replace-objects", "-c", "protocol.allow=never", *args],
                          cwd=root, env=environment, capture_output=True, text=not binary,
                          timeout=30, check=False)


def _revision_snapshot(root, revision, destination):
    listing = _object_git(root, ["ls-tree", "-r", "-z", "--full-tree", revision], binary=True)
    if listing.returncode:
        raise EvolutionUnavailable("baseline_objects_unavailable")
    entries = []
    for record in listing.stdout.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = metadata.decode("ascii").split()
        relative = _relative(raw_path.decode("utf-8"))
        if _generated_path(relative) or any(part in map_v0.IGNORED_PARTS for part in PurePosixPath(relative).parts):
            continue
        if mode == "160000" and kind == "commit":
            continue  # Git submodule contents are not Map's tracked-file inputs.
        if kind != "blob" or mode not in ("100644", "100755", "120000"):
            raise EvolutionUnavailable("baseline_input_unavailable")
        entries.append((relative, mode, object_id))
    environment = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    command = ["git", "--no-replace-objects", "-c", "protocol.allow=never", "cat-file", "--batch"]
    links = []
    process = subprocess.Popen(command, cwd=root, env=environment, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for relative, mode, object_id in entries:
            process.stdin.write((object_id + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split()
            if len(header) != 3 or header[:2] != [object_id, "blob"]:
                raise EvolutionUnavailable("baseline_objects_unavailable")
            remaining = int(header[2])
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write link text as an ordinary file first. Links are only created
            # after all regular writes, preventing a tree entry from redirecting them.
            with target.open("wb") as output:
                while remaining:
                    chunk = process.stdout.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise EvolutionUnavailable("baseline_objects_unavailable")
                    output.write(chunk)
                    remaining -= len(chunk)
            if process.stdout.read(1) != b"\n":
                raise EvolutionUnavailable("baseline_objects_unavailable")
            if mode == "120000":
                links.append((target, target.read_text(encoding="utf-8")))
        for target, link in links:
            if Path(link).is_absolute() or not (target.parent / link).resolve().is_relative_to(destination):
                raise EvolutionUnavailable("baseline_input_unavailable")
            target.unlink()
            target.symlink_to(link)
        # Resolve every completed link again: a link chain may have been created later.
        if any(not target.resolve().is_relative_to(destination) for target, _ in links):
            raise EvolutionUnavailable("baseline_input_unavailable")
    finally:
        process.stdin.close()
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def _evolution(root, base, graph, native, project, source, head_paths, budget, focus):
    empty = {"available": False, "reason": "base_ref_not_supplied", "base_revision": None,
             "current_revision": source["revision"], "dirty": source["dirty"],
             "nodes": {"added": [], "removed": [], "changed": []},
             "edges": {"added": [], "removed": []},
             "areas": {"added": [], "removed": [], "changed": []},
             "files": {"added": [], "removed": [], "modified": []}, "records": [], "summary": {}}
    if not base:
        return empty
    if source["revision"] is None:
        return {**empty, "reason": "git_root_unavailable"}
    try:
        sparse = _git(root, ["ls-files", "-v", "-z"])
        if sparse.returncode or any(item[:2].upper() == "S " for item in sparse.stdout.split("\0")):
            return {**empty, "reason": "current_snapshot_incomplete"}
        verified = _object_git(root, ["rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"])
        if verified.returncode:
            return {**empty, "reason": "base_ref_unavailable"}
        revision = verified.stdout.strip()
        empty["base_revision"] = revision
        with tempfile.TemporaryDirectory(prefix="specmesh-revision-") as temporary:
            snapshot = Path(temporary)
            _revision_snapshot(root, revision, snapshot)
            before_graph = _graph(snapshot)
        before_source = {**source, "revision": revision, "dirty": False}
        before = _native_map(before_graph, project, before_source,
                             {entry["path"] for entry in before_graph["sources"]}, budget, focus)
        old_nodes = {node["id"]: node for node in before["nodes"]}
        new_nodes = {node["id"]: node for node in native["nodes"]}
        changed_nodes = []
        for key in sorted(old_nodes.keys() & new_nodes.keys()):
            old, new = old_nodes[key], new_nodes[key]
            fields = sorted(field for field in (old.keys() | new.keys()) - {"url"}
                            if old.get(field) != new.get(field))
            if fields:
                changed_nodes.append({"id": key, "before": old, "after": new, "fields": fields,
                                      "change_basis": "containing_source_file" if "source_sha256" in fields else "node_metadata"})
        nodes = {"added": [new_nodes[key] for key in sorted(new_nodes.keys() - old_nodes.keys())],
                 "removed": [old_nodes[key] for key in sorted(old_nodes.keys() - new_nodes.keys())],
                 "changed": changed_nodes}
        old_edges = {edge["key"]: edge for edge in before["edges"]}
        new_edges = {edge["key"]: edge for edge in native["edges"]}
        edges = {"added": [new_edges[key] for key in sorted(new_edges.keys() - old_edges.keys())],
                 "removed": [old_edges[key] for key in sorted(old_edges.keys() - new_edges.keys())]}
        old_areas, new_areas = before["areas"], native["areas"]
        areas = {"added": [{"id": key, **new_areas[key]} for key in sorted(new_areas.keys() - old_areas.keys())],
                 "removed": [{"id": key, **old_areas[key]} for key in sorted(old_areas.keys() - new_areas.keys())],
                 "changed": [{"id": key, "before": old_areas[key], "after": new_areas[key]}
                             for key in sorted(old_areas.keys() & new_areas.keys()) if old_areas[key] != new_areas[key]]}
        old_files = {entry["path"]: entry["sha256"] for entry in before_graph["sources"]}
        new_files = {entry["path"]: entry["sha256"] for entry in graph["sources"]}
        files = {"added": sorted(new_files.keys() - old_files.keys()), "removed": sorted(old_files.keys() - new_files.keys()),
                 "modified": sorted(path for path in old_files.keys() & new_files.keys() if old_files[path] != new_files[path])}
        records = []
        for change, paths in files.items():
            for path in paths:
                kind = ("project" if path == "PROJECT.md" else "decision" if path == "docs/DECISIONS.md"
                        else "plan" if path.startswith("plans/") and path.endswith(".md") else None)
                if kind:
                    records.append({"path": path, "kind": kind, "change": change,
                                    "url": _url(project, source, path, head_paths) if path in new_files else None,
                                    "base_url": _url(project, before_source, path, set(old_files)) if path in old_files else None})
        return {**empty, "available": True, "reason": None, "nodes": nodes, "edges": edges, "areas": areas,
                "files": files, "records": records,
                "summary": {name: {change: len(items) for change, items in values.items()}
                            for name, values in (("nodes", nodes), ("edges", edges), ("areas", areas), ("files", files))}}
    except EvolutionUnavailable as error:
        return {**empty, "reason": str(error)}
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return {**empty, "reason": "baseline_input_unavailable"}


def build_architecture(root, model_path=None, *, template_path=None, run_checks=False, results_path=None, base_ref=None,
                       no_model=False, focus=None, budget=None):
    root = Path(root).resolve(strict=True)
    model, model_location = _model(root, model_path, no_model)
    if focus is not None:
        _text(focus, "focus query", 4000)
    if budget is not None and (type(budget) is not int or not 1 <= budget <= 100000):
        raise ValueError("budget must be an integer between 1 and 100000 tokens")
    template_path = Path(template_path or ENGINE_ROOT / "architecture/explorer.html")
    template = template_path.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("viewer template must contain exactly one data placeholder")
    graph = _graph(root)
    config = map_v0.read_context(root)
    budget = budget if budget is not None else int(config["focus_budget_tokens" if focus else "global_budget_tokens"])
    if not 1 <= budget <= 100000:
        raise ValueError("configured Map budget must be between 1 and 100000 tokens")
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
    native = _native_map(graph, model["project"], source, head_paths, budget, focus)
    result = {"schema": VIEW_SCHEMA, "project": model["project"], "source": source, "layers": model["layers"],
              "modules": modules, "relations": relations, "checks": checks,
              "changes": _changes(root, base_ref, modules, relations),
              "map": native, "model": {"available": model_location is not None, "path": model_location},
              "evolution": _evolution(root, base_ref, graph, native, model["project"], source, head_paths, budget, focus),
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
    parser.add_argument("--model", type=Path, help="optional reviewed business modules; auto-detect architecture/architecture.json")
    parser.add_argument("--no-model", action="store_true", help="view the native Map without business modules or checks")
    parser.add_argument("--focus", help="use Map's existing focused selection for this query")
    parser.add_argument("--budget", type=int, help="Map selection token budget; defaults to Map context configuration")
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
        payload = build_architecture(root, args.model, run_checks=args.run_checks, results_path=args.results,
                                     base_ref=args.base_ref, no_model=args.no_model, focus=args.focus, budget=args.budget)
        blocked = any(not module["structure_valid"] for module in payload["modules"]) or any(not e["active"] for e in payload["relations"])
        if not args.check:
            write_bundle(payload, output, root=root)
        evidence_requested = args.run_checks or args.results is not None
        failed_checks = evidence_requested and any(c["status"] != "pass" for c in payload["checks"])
        print(json.dumps({"schema": VIEW_SCHEMA, "output": str(output.resolve()) if not args.check else None,
                          "source": payload["source"], "summary": payload["summary"], "map": payload["map"]["counts"],
                          "evolution": {key: payload["evolution"][key] for key in ("available", "reason", "base_revision")},
                          "structural_validation": "blocked" if blocked else "valid"}, ensure_ascii=False))
        return 1 if blocked or failed_checks else 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
