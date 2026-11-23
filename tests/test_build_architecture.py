import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import build_architecture as explorer


class ArchitectureExplorerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.template = self.base / "engine/architecture/explorer.html"
        self.template.parent.mkdir(parents=True)
        self.template.write_text('<!doctype html><meta charset="utf-8"><script id="architecture-data" '
                                 'type="application/json">__SPECMESH_DATA__</script><main>Viewer</main>')
        self.write("src/input.py", "def read_input():\n    return 1\n")
        self.write("src/output.py", "def render_output():\n    return 2\n")
        self.model = {
            "schema": explorer.MODEL_SCHEMA,
            "project": {"id": "example/project", "title": "Architecture", "subtitle": "Human view",
                        "repository_url": "https://github.com/example/project"},
            "layers": [{"id": "input", "label": "Input"}, {"id": "output", "label": "Output"}],
            "modules": [
                {"id": "input", "title": "Input", "summary": "Read", "layer": "input", "order": 1,
                 "paths": ["src/input.py"], "anchors": ["code://src/input.py#read_input"], "checks": ["unit"]},
                {"id": "output", "title": "Output", "summary": "Show", "layer": "output", "order": 0,
                 "paths": ["src/output.py"], "checks": []},
            ],
            "relations": [{"from": "input", "to": "output", "kind": "data", "label": "input data",
                           "authority": "asserted", "evidence": ["src/input.py"]}],
            "checks": [{"id": "unit", "label": "Unit checks", "command": [sys.executable, "-c", "print('passed')"],
                        "timeout_seconds": 10}],
        }
        self.model_path = self.root / "architecture/architecture.json"
        self.save_model()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def save_model(self):
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_path.write_text(json.dumps(self.model), encoding="utf-8")

    def build(self, **kwargs):
        return explorer.build_architecture(self.root, template_path=self.template, **kwargs)

    def save_results(self, view, name="previous"):
        dest = self.base / name
        explorer.write_bundle(view, dest, root=self.root, template_path=self.template)
        return dest / "status.json"

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def init_git(self):
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic tester")
        self.git("config", "user.email", "tester@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def test_default_is_read_only_and_existing_files_are_not_test_passes(self):
        self.model["checks"][0]["command"] = [sys.executable, "-c", "open('SHOULD_NOT_EXIST', 'w').write('x')"]
        self.save_model()
        view = self.build()
        self.assertEqual(view["modules"][0]["status"], "unknown")
        self.assertTrue(view["modules"][0]["structure_valid"])
        self.assertEqual(view["checks"][0]["reason"], "not_run")
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())
        self.assertFalse((self.root / "dist").exists())

    def test_actual_pass_failure_and_unavailable_commands_remain_distinct(self):
        for command, expected in (([sys.executable, "-c", "print('ok')"], "pass"),
                                  ([sys.executable, "-c", "raise SystemExit(3)"], "fail"),
                                  (["definitely-not-a-real-specmesh-test-command"], "unknown")):
            with self.subTest(expected=expected):
                self.model["checks"][0]["command"] = command
                self.save_model()
                view = self.build(run_checks=True)
                self.assertEqual(view["checks"][0]["status"], expected)
                self.assertEqual(view["modules"][0]["status"], expected)
                self.assertEqual(view["modules"][1]["status"], "unknown")
                self.assertIsNotNone(view["checks"][0]["observed_at"])

    def test_timeout_is_failed_not_passed(self):
        self.model["checks"][0].update(command=[sys.executable, "-c", "import time; time.sleep(5)"], timeout_seconds=1)
        self.save_model()
        view = self.build(run_checks=True)
        self.assertEqual(view["checks"][0]["status"], "fail")
        self.assertEqual(view["checks"][0]["reason"], "timeout")

    def test_invalid_reviewed_model_fails_loudly(self):
        variants = []
        item = copy.deepcopy(self.model)
        item["modules"][1]["id"] = "input"
        variants.append(item)
        item = copy.deepcopy(self.model)
        item["relations"][0]["to"] = "unknown"
        variants.append(item)
        item = copy.deepcopy(self.model)
        item["project"]["repository_url"] = "javascript:alert(1)"
        variants.append(item)
        item = copy.deepcopy(self.model)
        item["modules"][0]["paths"] = ["../private"]
        variants.append(item)
        item = copy.deepcopy(self.model)
        item["relations"][0]["authority"] = "derived"
        variants.append(item)
        for item in variants:
            with self.subTest(item=item), self.assertRaises(ValueError):
                explorer.validate_model(item)

    def test_missing_paths_block_without_fabricating_a_test_failure(self):
        (self.root / "src/input.py").unlink()
        view = self.build()
        self.assertEqual(view["modules"][0]["status"], "blocked")
        self.assertFalse(view["relations"][0]["active"])
        self.assertEqual(view["checks"][0]["status"], "unknown")
        self.assertTrue(any("path_not_in_current_sources" in r for r in view["modules"][0]["reasons"]))

    def test_source_symlink_cannot_escape_selected_repository(self):
        outside = self.base / "outside.py"
        outside.write_text("secret = 1\n")
        (self.root / "src/input.py").unlink()
        (self.root / "src/input.py").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.build()

    def test_existing_area_requires_current_anchors_even_with_unique_rename_candidate(self):
        self.write(".specmesh/repo-areas.v0.yaml", "areas:\n  - id: area:input\n    purpose: Input responsibility\n"
                   "    anchors:\n      - code://src/input.py#read_input\n")
        self.write(".specmesh/memory/core.md", "- relation: implemented_by | from: `spec://input` | "
                   "to: `code://src/input.py` | provenance: asserted | scope: area:input\n")
        self.model["modules"][0]["area"] = "area:input"
        self.save_model()
        before = self.build()
        self.assertEqual(before["modules"][0]["area_status"], "current")
        (self.root / "src/input.py").rename(self.root / "src/renamed.py")
        after = self.build()
        self.assertEqual(after["modules"][0]["area_status"], "candidate_rebind")
        self.assertEqual(after["modules"][0]["status"], "blocked")
        self.assertFalse(after["relations"][0]["active"])
        self.assertFalse(any(e.get("scope") == "area:input" for e in after["map"]["relations"]))
        self.assertNotIn("spec://input", {node["id"] for node in after["map"]["nodes"]})
        self.assertNotIn("spec://input", after["map"]["selection"]["node_ids"])
        self.assertNotIn("code://src/input.py", {node["id"] for node in after["map"]["nodes"]})

    def test_map_config_inputs_must_be_local_and_manifest_bound_before_replaying_results(self):
        self.init_git()
        previous = self.save_results(self.build(run_checks=True))
        external = self.base / "synthetic-memory.md"
        external.write_text("- relation: implements | from: `mem://external` | "
                            "to: `code://src/input.py` | provenance: asserted\n")
        context = ".specmesh/context.md"
        memory = ".specmesh/memory/core.md"
        areas = ".specmesh/repo-areas.v0.yaml"
        cases = [("outside-memory", context, "memory_root: ../synthetic-memory.md\n", None),
                 ("absolute-memory", context, f"memory_root: {external}\n", None),
                 ("outside-areas", context, "area_overlay: ../synthetic-memory.md\n", None),
                 ("symlink-context", context, None, "symlink"),
                 ("symlink-memory", memory, None, "symlink"),
                 ("symlink-areas", areas, None, "symlink"),
                 ("ignored-context", context, "memory_root: .specmesh/memory/core.md\n", "ignored"),
                 ("ignored-memory", memory, external.read_text(), "ignored"),
                 ("ignored-areas", areas, "areas:\n", "ignored")]
        for label, relative, content, mode in cases:
            with self.subTest(input=label):
                for old in (context, memory, areas, ".gitignore"):
                    (self.root / old).unlink(missing_ok=True)
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if mode == "symlink":
                    path.symlink_to(external)
                else:
                    self.write(relative, content)
                if mode == "ignored":
                    self.write(".gitignore", relative + "\n")
                with patch.object(explorer.map_v0, "build_graph", side_effect=AssertionError("unsafe Map read")), \
                        self.assertRaises(ValueError):
                    self.build(results_path=previous)

    def test_prior_results_are_exactly_bound_to_content_template_and_actual_git_revision(self):
        self.init_git()
        previous = self.save_results(self.build(run_checks=True))
        self.assertEqual(self.build(results_path=previous)["checks"][0]["status"], "pass")
        path = self.root / "src/input.py"
        stat, original = path.stat(), path.read_bytes()
        path.write_bytes(original.replace(b"return 1", b"return 9"))
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        stale = self.build(results_path=previous)
        self.assertEqual(stale["checks"][0]["status"], "stale")
        self.assertEqual(stale["checks"][0]["observed_status"], "pass")
        path.write_bytes(original)
        self.assertEqual(self.build(results_path=previous)["checks"][0]["status"], "pass")
        template = self.template.read_text()
        self.template.write_text(template + "\n<!-- layout changed -->")
        self.assertEqual(self.build(results_path=previous)["checks"][0]["status"], "stale")
        self.template.write_text(template)
        self.git("commit", "--allow-empty", "-qm", "new source identity")
        self.assertEqual(self.build(results_path=previous)["checks"][0]["status"], "stale")

    def test_missing_result_metadata_cannot_be_reported_as_verified_pass(self):
        path = self.save_results(self.build(run_checks=True))
        record = json.loads(path.read_text())
        record["checks"][0]["observed_at"] = None
        path.write_text(json.dumps(record))
        current = self.build(results_path=path)
        self.assertEqual(current["checks"][0]["status"], "unknown")
        self.assertEqual(current["checks"][0]["reason"], "unverifiable_result_metadata")

    def test_changes_during_check_execution_invalidate_success(self):
        self.model["checks"][0]["command"] = [sys.executable, "-c", "open('src/input.py','a').write('# changed\\n')"]
        self.save_model()
        view = self.build(run_checks=True)
        self.assertEqual(view["checks"][0]["status"], "stale")
        self.assertEqual(view["checks"][0]["observed_status"], "pass")
        self.assertEqual(view["checks"][0]["reason"], "sources_changed_during_checks")

    def test_external_template_changes_during_checks_are_stale_and_later_changes_require_rebuild(self):
        command = f"from pathlib import Path; p = Path({str(self.template)!r}); p.write_text(p.read_text() + '<!-- changed -->')"
        self.model["checks"][0]["command"] = [sys.executable, "-c", command]
        self.save_model()
        view = self.build(run_checks=True)
        self.assertEqual(view["checks"][0]["status"], "stale")
        self.assertEqual(view["checks"][0]["observed_status"], "pass")
        self.save_results(view)
        self.template.write_text(self.template.read_text() + "<!-- changed again -->")
        with self.assertRaisesRegex(ValueError, "template changed"):
            self.save_results(view, "rejected")

    def test_generated_bundle_is_offline_and_embedded_data_cannot_close_its_script(self):
        self.model["modules"][0]["title"] = '</script><img src=x onerror="alert(1)">'
        self.save_model()
        payload = self.build()
        output = self.base / "output"
        explorer.write_bundle(payload, output, root=self.root, template_path=self.template)
        html = (output / "index.html").read_text()
        self.assertEqual(html.count("</script>"), 1)
        self.assertNotIn('<img src=x', html)
        self.assertNotIn(explorer.PLACEHOLDER, html)
        embedded = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(embedded)["modules"][0]["title"], self.model["modules"][0]["title"])
        self.assertEqual(json.loads((output / "architecture.json").read_text()), payload)

    def test_output_cannot_overwrite_sources_unowned_directories_or_symlinks(self):
        for path in (self.root, self.root / "architecture", self.root / "src/new", self.base):
            with self.subTest(path=path), self.assertRaises(ValueError):
                explorer.validate_output(self.root, path)
        existing = self.base / "unowned"
        existing.mkdir()
        (existing / "index.html").write_text("human document")
        with self.assertRaisesRegex(ValueError, "nonempty"):
            explorer.validate_output(self.root, existing)
        target = self.base / "target"
        target.mkdir()
        symlink = self.base / "symlink"
        symlink.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            explorer.validate_output(self.root, symlink)

    def test_generated_outputs_do_not_invalidate_their_own_source_binding(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned):
                if versioned:
                    self.init_git()
                first = self.build(run_checks=True)
                output = self.root / "dist/architecture"
                explorer.write_bundle(first, output, root=self.root, template_path=self.template)
                second = self.build(results_path=output / "status.json")
                self.assertEqual(second["source"]["source_fingerprint"], first["source"]["source_fingerprint"])
                self.assertEqual(second["checks"][0]["status"], "pass")
                explorer.write_bundle(second, output, root=self.root, template_path=self.template)

    def test_git_changes_report_direct_and_declared_downstream_impact(self):
        self.init_git()
        self.write("src/input.py", "def read_input():\n    return 7\n")
        self.write("unmapped.txt", "new file")
        view = self.build(base_ref="HEAD")
        self.assertTrue(view["changes"]["available"])
        self.assertEqual(view["changes"]["direct_modules"], ["input"])
        self.assertEqual(view["changes"]["affected_modules"], ["input", "output"])
        self.assertEqual(view["changes"]["unmapped_files"], ["unmapped.txt"])
        self.assertTrue(view["source"]["dirty"])
        self.assertIn(self.git("rev-parse", "HEAD"), view["modules"][0]["files"][0]["url"])
        self.assertEqual(explorer.affected_modules(["src/input.py"], view["modules"],
                                                  [{**view["relations"][0], "active": False}])["affected_modules"], ["input"])

    def test_uncommitted_new_files_do_not_get_nonexistent_head_links(self):
        self.init_git()
        self.write("src/new.py", "value = 1\n")
        self.model["modules"][1]["paths"] = ["src/new.py"]
        self.save_model()
        view = self.build()
        existing, new = (m["files"][0] for m in view["modules"])
        self.assertIsNotNone(existing["url"])
        self.assertTrue(new["exists"])
        self.assertIsNone(new["url"])
        self.assertIsNone(new["url_basis"])

    def test_missing_diff_base_is_unavailable_not_a_verified_zero_change_result(self):
        self.init_git()
        view = self.build(base_ref="not-a-real-ref")
        self.assertFalse(view["changes"]["available"])
        self.assertEqual(view["changes"]["reason"], "base_ref_unavailable")
        self.assertFalse(view["evolution"]["available"])
        self.assertEqual(view["evolution"]["reason"], "base_ref_unavailable")
        self.assertEqual(view["evolution"]["files"], {"added": [], "removed": [], "modified": []})

    def test_native_map_needs_no_model_and_uses_only_a_real_origin_for_links(self):
        self.model_path.unlink()
        self.init_git()
        local = self.build()
        self.assertFalse(local["model"]["available"])
        self.assertEqual(local["modules"], [])
        self.assertEqual(local["checks"], [])
        self.assertEqual(local["project"]["title"], self.root.name)
        self.assertIsNone(local["project"]["repository_url"])
        self.assertTrue(all(node.get("url") is None for node in local["map"]["nodes"]))
        self.git("remote", "add", "origin", "git@github.com:example/native-project.git")
        linked = self.build()
        node = next(node for node in linked["map"]["nodes"] if node["id"] == "code://src/input.py#read_input")
        self.assertEqual(linked["project"]["repository_url"], "https://github.com/example/native-project")
        self.assertEqual(node["url"], "https://github.com/example/native-project/blob/" + self.git("rev-parse", "HEAD") + "/src/input.py")
        self.assertEqual(node["authority"], "derived")
        self.assertTrue(any(edge["relation"] == "defines" for edge in linked["map"]["edges"]))
        with self.assertRaises(FileNotFoundError):
            explorer.build_architecture(self.root, "missing.json", template_path=self.template)
        self.save_model()
        self.assertEqual(self.build(no_model=True)["modules"], [])

    def test_focus_selection_reuses_map_and_does_not_invalidate_check_replay(self):
        self.init_git()
        original = self.build(run_checks=True)
        previous = self.save_results(original)
        focused = self.build(results_path=previous, focus="read_input", budget=150, base_ref="HEAD")
        self.assertEqual(focused["checks"], original["checks"])
        self.assertEqual(focused["check_binding"], original["check_binding"])
        expected = explorer.map_v0.select_view(explorer._graph(self.root), 150, "read_input")
        self.assertEqual(focused["map"]["selection"]["node_ids"], expected["node_ids"])
        self.assertEqual(focused["map"]["selection"]["edge_keys"], expected["edge_keys"])
        self.assertLessEqual(focused["map"]["selection"]["token_count"], 150)
        self.assertTrue(focused["evolution"]["available"])
        self.assertEqual(focused["evolution"]["nodes"], {"added": [], "removed": [], "changed": []})

    def test_evolution_reads_two_real_commits_and_reports_source_area_and_record_changes(self):
        sentinel = self.base / "BASELINE_MUST_NOT_EXECUTE"
        self.write("danger.py", f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n")
        self.write("removed.py", "def removed():\n    return 0\n")
        self.write("PROJECT.md", "# Original intent\n")
        self.write("docs/DECISIONS.md", "# Old decision\n")
        self.write("plans/current/task_plan.md", "# Initial plan\n")
        self.write(".specmesh/repo-areas.v0.yaml", "areas:\n  - id: area:output\n    purpose: Output\n"
                   "    anchors:\n      - code://src/output.py#render_output\n")
        self.init_git()
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        base = self.git("rev-parse", "HEAD")
        self.write("src/input.py", "def read_input():\n    return 9\n")
        (self.root / "src/output.py").rename(self.root / "src/renamed.py")
        (self.root / "removed.py").unlink()
        self.write("added.py", "def added():\n    return 3\n")
        self.write("PROJECT.md", "# Updated intent\n")
        (self.root / "docs/DECISIONS.md").unlink()
        self.write("plans/current/task_plan.md", "# Updated plan\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "evolve sources and intent")
        current = self.git("rev-parse", "HEAD")
        evolution = self.build(no_model=True, base_ref=base)["evolution"]
        self.assertTrue(evolution["available"], evolution["reason"])
        self.assertEqual((evolution["base_revision"], evolution["current_revision"]), (base, current))
        self.assertFalse(evolution["dirty"])
        removed = {node["id"]: node for node in evolution["nodes"]["removed"]}
        added = {node["id"]: node for node in evolution["nodes"]["added"]}
        changed = {node["id"]: node for node in evolution["nodes"]["changed"]}
        self.assertIn("code://src/output.py#render_output", removed)
        self.assertIn("code://src/renamed.py#render_output", added)
        self.assertIn(base, removed["code://src/output.py"]["url"])
        self.assertEqual(changed["code://src/input.py#read_input"]["fields"], ["source_sha256"])
        self.assertEqual(changed["code://src/input.py#read_input"]["change_basis"], "containing_source_file")
        self.assertTrue(evolution["edges"]["added"])
        self.assertTrue(evolution["edges"]["removed"])
        area = evolution["areas"]["changed"][0]
        self.assertEqual((area["before"]["state"], area["after"]["state"]), ("current", "candidate_rebind"))
        self.assertIn("removed.py", evolution["files"]["removed"])
        self.assertIn("added.py", evolution["files"]["added"])
        self.assertIn("src/input.py", evolution["files"]["modified"])
        records = {record["path"]: record for record in evolution["records"]}
        self.assertEqual(records["PROJECT.md"]["kind"], "project")
        self.assertIn(current, records["PROJECT.md"]["url"])
        self.assertEqual(records["docs/DECISIONS.md"]["change"], "removed")
        self.assertIsNone(records["docs/DECISIONS.md"]["url"])
        self.assertIn(base, records["docs/DECISIONS.md"]["base_url"])
        self.assertEqual(records["plans/current/task_plan.md"]["kind"], "plan")
        self.assertFalse(sentinel.exists())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_evolution_preserves_unicode_and_quoted_path_identity(self):
        paths = ["目录/启动工具.sh", "docs/空格 文档.md", 'notes/quoted"name.txt']
        for relative in paths:
            self.write(relative, "synthetic unchanged source\n")
        self.init_git()
        self.git("config", "core.quotePath", "true")
        base = self.git("rev-parse", "HEAD")
        self.write("src/input.py", "def read_input():\n    return 8\n")
        self.git("add", ".")
        self.git("commit", "-qm", "change one source only")
        result = self.build(base_ref=base)
        self.assertTrue(result["evolution"]["available"], result["evolution"]["reason"])
        self.assertEqual(result["evolution"]["files"],
                         {"added": [], "removed": [], "modified": ["src/input.py"]})
        self.assertEqual(result["evolution"]["nodes"]["removed"], [])
        self.assertEqual(result["evolution"]["nodes"]["added"], [])
        self.assertTrue({"code://" + path for path in paths}.issubset(
            {node["id"] for node in result["map"]["nodes"]}))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_evolution_reports_missing_git_objects_instead_of_empty_changes(self):
        self.init_git()
        base = self.git("rev-parse", "HEAD")
        old_blob = self.git("rev-parse", "HEAD:src/input.py")
        self.write("src/input.py", "def read_input():\n    return 8\n")
        self.git("add", ".")
        self.git("commit", "-qm", "replace old blob")
        (self.root / ".git/objects" / old_blob[:2] / old_blob[2:]).unlink()
        result = self.build(base_ref=base)["evolution"]
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "baseline_objects_unavailable")
        self.assertEqual(result["nodes"], {"added": [], "removed": [], "changed": []})

    def test_evolution_refuses_escaping_git_tree_symlinks_and_sparse_worktrees(self):
        outside = self.base / "outside-memory.md"
        outside.write_text("synthetic outside content\n")
        context = self.root / ".specmesh/context.md"
        context.parent.mkdir(parents=True)
        context.symlink_to(outside)
        self.init_git()
        base = self.git("rev-parse", "HEAD")
        context.unlink()
        self.write(".specmesh/context.md", "memory_root: .specmesh/memory/core.md\n")
        self.git("add", ".")
        self.git("commit", "-qm", "use repository context")
        result = self.build(base_ref=base)["evolution"]
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "baseline_input_unavailable")
        self.git("update-index", "--skip-worktree", "src/output.py")
        self.git("update-index", "--assume-unchanged", "src/output.py")
        self.assertIn("s src/output.py", self.git("ls-files", "-v"))
        result = self.build(base_ref="HEAD")["evolution"]
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "current_snapshot_incomplete")

    def test_cli_without_model_builds_native_focus_and_explicit_missing_model_fails(self):
        self.model_path.unlink()
        output = self.base / "native-cli"
        with patch.object(explorer, "ENGINE_ROOT", self.template.parents[1]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(explorer.main(["--root", str(self.root), "--output", str(output),
                                            "--focus", "read_input", "--budget", "150"]), 0)
            payload = json.loads((output / "architecture.json").read_text())
            self.assertEqual(payload["map"]["selection"]["mode"], "focus")
            self.assertEqual(payload["modules"], [])
            self.assertEqual(explorer.main(["--root", str(self.root), "--model", "absent.json", "--check"]), 2)

    def test_cli_check_does_not_execute_or_write_and_failed_run_still_emits_page(self):
        self.model["checks"][0]["command"] = [sys.executable, "-c", "raise SystemExit(4)"]
        self.save_model()
        output = self.base / "cli-output"
        with patch.object(explorer, "ENGINE_ROOT", self.template.parents[1]), contextlib.redirect_stdout(io.StringIO()):
            code = explorer.main(["--root", str(self.root), "--output", str(output), "--check"])
            self.assertEqual(code, 0)
            self.assertFalse(output.exists())
            code = explorer.main(["--root", str(self.root), "--output", str(output), "--run-checks"])
            self.assertEqual(code, 1)
            self.assertTrue((output / "index.html").exists())
            self.assertEqual(json.loads((output / "status.json").read_text())["checks"][0]["status"], "fail")

    def test_cli_result_replay_gates_nonpasses_without_executing_checks_and_keeps_page(self):
        cases = (("pass", [sys.executable, "-c", "print('passed')"]),
                 ("fail", [sys.executable, "-c", "raise SystemExit(4)"]),
                 ("unknown", ["definitely-not-a-real-specmesh-test-command"]),
                 ("stale", [sys.executable, "-c", "print('passed')"]))
        for expected, command in cases:
            with self.subTest(status=expected):
                self.model["checks"][0]["command"] = command
                self.save_model()
                previous = self.save_results(self.build(run_checks=True), "prior-" + expected)
                if expected == "stale":
                    self.write("src/input.py", "def read_input():\n    return 9\n")
                output = self.base / ("replayed-" + expected)
                with patch.object(explorer, "ENGINE_ROOT", self.template.parents[1]), \
                        patch.object(explorer, "_run_check", side_effect=AssertionError("replay executed a check")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    code = explorer.main(["--root", str(self.root), "--results", str(previous),
                                          "--output", str(output)])
                self.assertEqual(code, 0 if expected == "pass" else 1)
                self.assertTrue((output / "index.html").exists())
                replayed = json.loads((output / "status.json").read_text())
                self.assertEqual(replayed["checks"][0]["status"], expected)


if __name__ == "__main__":
    unittest.main()
