import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.retrieve_evidence import retrieve


PROJECT = "example/demo"
SHA = "a" * 40
SPEC = "spec://map-v0"
AREA = "area:map-derivation"


class RetrieveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.write(".specmesh/repo-areas.v0.yaml",
                   "areas:\n  - id: area:map-derivation\n    purpose: map\n    anchors:\n      - code://src/cache.py#cache_is_fresh\n")
        self.write(".specmesh/memory/core.md", "\n".join(
            f"- relation: {relation} | from: `{SPEC}` | to: `code://{file}` | provenance: asserted | scope: {AREA}"
            for relation, file in (("implemented_by", "src/cache.py"), ("verified_by", "tests/test_cache.py"))))
        self.write("src/cache.py", "def cache_is_fresh():\n    return True\n")
        self.write("tests/test_cache.py", "def test_cache():\n    assert True\n")
        self.write("plans/map-v0-spike/findings.md", "A historical candidate")
        self.scope = dict(project=PROJECT, revision=SHA, spec_uri=SPEC, area=AREA)

    def write(self, path, body):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return p

    def external(self, name, data):
        p = self.root.parent / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def call(self, query="修改 Map v0 缓存 cache_is_fresh", **kw):
        return retrieve(self.root, query, project=PROJECT, revision=SHA, **kw)

    def test_real_graph_uses_current_sources_and_does_not_touch_cache(self):
        stale = self.write(".specmesh/cache/repo-map.json", "stale junk")
        r = self.call()
        self.assertEqual(r["identity"]["spec_uri"], SPEC)
        self.assertEqual(r["identity"]["area"], AREA)
        self.assertEqual(r["identity"]["revision_basis"], "caller_supplied")
        code = r["sources"]["code"]
        self.assertEqual(code["status"], "matched")
        self.assertIn("code://src/cache.py#cache_is_fresh", [i["uri"] for i in code["items"]])
        self.assertEqual(code["tests"][0]["uri"], "code://tests/test_cache.py")
        self.assertEqual(code["repository_documents"][0]["verification"], "candidate_only")
        self.assertEqual(stale.read_text(), "stale junk")

    def test_unknown_spec_and_noncurrent_area_do_not_inject(self):
        self.assertEqual(self.call("another task")["sources"]["code"]["status"], "no_match")
        self.assertEqual(self.call(area="area:unknown")["sources"]["code"]["status"], "unbound")
        self.write("src/cache.py", "def renamed():\n    return True\n")
        r = self.call()
        self.assertEqual(r["sources"]["code"]["reason"], "area_not_current")
        self.assertFalse(r["sources"]["code"]["items"])

    def test_missing_test_is_partial_and_non_authoritative(self):
        (self.root / "tests/test_cache.py").unlink()
        r = self.call()["sources"]["code"]
        self.assertEqual(r["status"], "partial")
        self.assertIn("code://tests/test_cache.py", r["unresolved"])

    def test_external_sources_differentiate_not_checked_failed_no_match(self):
        self.assertEqual(self.call()["sources"]["drive"]["status"], "not_checked")
        bad = self.external("bad.json", [])
        self.assertEqual(self.call(control_export=bad)["sources"]["control"]["status"], "failed")
        empty = self.external("empty.json", {"schema": "controlmesh-receipts-v0", "items": []})
        self.assertEqual(self.call(control_export=empty)["sources"]["control"]["status"], "no_match")
        binding = self.external("binding.json", {"schema": "specmesh-history-binding-v0", **self.scope, "search_status": "not_indexed"})
        self.assertEqual(self.call(history_binding=binding)["sources"]["history"]["status"], "not_indexed")

    def test_native_history_binds_revision_and_returns_only_selected_positions(self):
        fields = {"source": "codex", "session_id": "session-a", "store_id": "store-a", "index_revision": "indexed-v1"}
        binding = self.external("binding.json", {"schema": "specmesh-history-binding-v0", **self.scope, **fields})
        loc = {"message_index": 12, "text_offset": 0, "raw_ref": {"line_no": 8}, "path": "/private/path", "index_revision": "indexed-v1"}
        packet = {"schema_version": "history.indexed-materials.v1", "authorization": "context_only",
                  "binding": "index_revision", "redacted": True, "context_only": True, **fields,
                  "items": [{**fields, "locator": loc, "message_index": 12, "text_offset": 0, "redacted": True,
                             "context_only": True, "text": "private text"}]}
        path = self.external("materials.json", packet)
        r = self.call(history_materials=path, history_binding=binding)["sources"]["history"]
        self.assertEqual(r["status"], "matched")
        self.assertEqual(r["items"][0]["line_no"], 8)
        self.assertFalse(r["live_verified"])
        self.assertNotIn("private", json.dumps(r))
        self.external("materials.json", {**packet, "index_revision": "changed"})
        r = self.call(history_materials=path, history_binding=binding)["sources"]["history"]
        self.assertEqual(r["status"], "unbound")

    def test_control_failed_receipt_is_returned_as_failed_outcome_not_success(self):
        items = [{**self.scope, "task_id": "t-1", "run_id": "r-1", "event_id": "e-1",
                  "outcome": "failed", "stdout": "do not copy"}]
        path = self.external("control.json", {"schema": "controlmesh-receipts-v0", "items": items})
        r = self.call(control_export=path)["sources"]["control"]
        self.assertEqual(r["status"], "matched")
        self.assertEqual(r["items"][0]["outcome"], "failed")
        self.assertNotIn("stdout", r["items"][0])

    def test_legacy_history_store_binding_stays_exact_without_namespace_translation(self):
        fields = {"source": "codex", "store_id": "legacy-local-store",
                  "session_id": "session-a", "index_revision": "indexed-v1"}
        binding = {"schema": "specmesh-history-binding-v0", **self.scope, **fields}
        packet = {"schema_version": "history.indexed-materials.v1", "authorization": "context_only",
                  "binding": "index_revision", "redacted": True, "context_only": True, **fields,
                  "items": [{**fields, "message_index": 3, "text_offset": 0,
                             "redacted": True, "context_only": True,
                             "locator": {"message_index": 3, "text_offset": 0,
                                         "index_revision": fields["index_revision"]}}]}
        path = self.external("legacy-materials.json", packet)
        reviewed = self.external("legacy-binding.json", binding)
        history = self.call(history_materials=path, history_binding=reviewed)["sources"]["history"]
        self.assertEqual(history["status"], "matched")
        self.assertEqual(history["items"][0]["store_id"], fields["store_id"])
        self.external("legacy-binding.json", {**binding, "store_id": "different-linux-store"})
        history = self.call(history_materials=path, history_binding=reviewed)["sources"]["history"]
        self.assertEqual(history["status"], "unbound")
        self.assertEqual(history["reason"], "history_source_or_revision_mismatch")

    @unittest.skipUnless(os.environ.get("AGENTTRACEMESH_CHECKOUT"),
                         "set AGENTTRACEMESH_CHECKOUT to run the optional native contract")
    def test_optional_native_compress_recall_materials_join(self):
        checkout = Path(os.environ["AGENTTRACEMESH_CHECKOUT"]).expanduser().resolve()
        self.assertTrue((checkout / "history_core/__main__.py").is_file(),
                        "AGENTTRACEMESH_CHECKOUT must name an existing source checkout")
        source = self.root.parent / "native-source"
        source.mkdir()
        cache = self.root.parent / "native-cache"
        cases = self.root.parent / "native-cases"
        session = "specmesh-native-contract"
        project = "/synthetic/specmesh-native-contract"
        records = [{"type": "session_meta", "timestamp": "2026-11-21T00:00:00Z",
                    "payload": {"id": session, "cwd": project}}]

        def event(payload):
            records.append({"type": "response_item",
                            "timestamp": f"2026-11-21T00:00:{len(records):02d}Z",
                            "payload": payload})

        def message(role, text):
            event({"type": "message", "role": role,
                   "content": [{"type": "input_text" if role == "user" else "output_text",
                                "text": text}]})

        message("user", "请验证 Map v0 cache_is_fresh 修改内容后必须拒绝旧缓存。")
        event({"type": "reasoning", "summary": [
            {"type": "summary_text", "text": "PRIVATE_NATIVE_CONTRACT_SENTINEL"}]})
        event({"type": "function_call", "name": "exec_command", "call_id": "check-cache",
               "arguments": json.dumps({"cmd": "inspect-cache"})})
        event({"type": "function_call_output", "call_id": "check-cache",
               "output": "Exit code: 0\nOutput:\ncache inspected; behavior unchecked"})
        message("assistant", "已经修好，全部通过。")
        message("user", "不对，旧缓存仍然被接受，先停止，核对当前实现。")
        transcript = source / "session.jsonl"
        transcript.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                              encoding="utf-8")
        original = transcript.read_bytes()

        def native(*args, allow_partial=False):
            completed = subprocess.run([sys.executable, "-B", "-m", "history_core", *args],
                                       cwd=checkout, capture_output=True, text=True, timeout=30)
            self.assertIn(completed.returncode, (0, 1) if allow_partial else (0,), completed.stderr)
            result = json.loads(completed.stdout)
            if completed.returncode == 1:
                self.assertTrue(result.get("partial"), completed.stdout)
            return result

        selected_source = ["--source", "codex", "--source-path", str(source), "--data-dir", str(cache)]
        native(*selected_source, "refresh")
        compressed = native(*selected_source, "compress", session, "--save", "--case-dir", str(cases),
                            allow_partial=True)
        recalled = native("recall", "--directory", str(cases), "--project", project,
                          "--query", "Map v0 cache_is_fresh", allow_partial=True)
        case_id = compressed["cases"][0]["id"]
        compact = next(item for item in recalled["items"] if item["id"] == case_id)
        request = self.external("context-request.json", {
            "schema_version": "history.context-request.v1",
            "task": "Map v0 cache_is_fresh",
            "next_action": "核对当前实现后修复缓存失效",
            "project": project,
            "state_revision": "cache-review-1",
            "needs": [{"id": "prior-correction", "kind": "history", "status": "missing",
                       "question": "之前 cache_is_fresh 的完成声明为何被用户纠正？",
                       "reason": "需要先定位原始纠正，避免重复采用被否决的修复。",
                       "query": "Map v0 cache_is_fresh",
                       "required_evidence": "同一会话原需求和后续用户纠正的精确修订与消息位置"}],
        })
        recovery_args = ["context", "--request", str(request), "--retrieve",
                         "--directory", str(cases), *selected_source]
        recovery = native(*recovery_args)
        self.assertEqual(recovery["status"], "needs_review")
        self.assertEqual(recovery["retrieval_calls"], 1)
        self.assertEqual(recovery["authorization"], "context_only")
        selected = next(item for item in recovery["gaps"][0]["candidates"] if item["id"] == case_id)
        self.assertEqual(selected["current_verification"], "not_performed")
        receipt = self.external("context-receipt.json", recovery)
        repeated = native(*recovery_args, "--previous", str(receipt))
        self.assertEqual(repeated["retrieval_calls"], 0)
        self.assertTrue(repeated["gaps"][0]["reused"])
        self.assertEqual(repeated["status"], "needs_review")
        full = native("cases", "--directory", str(cases), "show", case_id)["case"]
        evidence = {item["message_index"]: item for item in full["evidence"] if item["kind"] == "message"}
        self.assertGreater(len(full["evidence"]), len(compact["evidence"]))
        self.assertIn(5, evidence)  # Later user correction lies beyond the compact evidence list.
        self.assertNotIn(1, evidence)  # Private reasoning keeps its slot without becoming evidence.
        self.assertEqual(full["now"]["task_status"], "unknown")
        first, correction = evidence[0], evidence[5]
        materials = native(*selected_source, "materials", session, "--index-revision", first["index_revision"],
                           "--message", f"{first['message_index']}:{first['text_offset']}",
                           "--message", f"{correction['message_index']}:{correction['text_offset']}")
        fields = ("source", "store_id", "session_id", "index_revision")
        for key in fields:
            self.assertEqual(materials[key], first[key], f"native {key} must survive compression to export")
            self.assertEqual(correction[key], first[key])
        binding = {"schema": "specmesh-history-binding-v0", **self.scope,
                   **{key: first[key] for key in fields}}
        path = self.external("native-materials.json", materials)
        reviewed = self.external("native-binding.json", binding)
        rejected = self.call(history_materials=receipt, history_binding=reviewed)["sources"]["history"]
        self.assertEqual(rejected["status"], "failed")
        self.assertEqual(rejected["reason"], "history_materials_schema_invalid")
        history = self.call(history_materials=path, history_binding=reviewed)["sources"]["history"]
        self.assertEqual(history["status"], "matched")
        self.assertEqual([item["message_index"] for item in history["items"]], [0, 5])
        self.assertEqual([item["line_no"] for item in history["items"]], [2, 7])
        self.assertFalse(history["live_verified"])
        self.assertNotIn("PRIVATE_NATIVE_CONTRACT_SENTINEL", json.dumps(materials))
        self.assertNotIn("text", history["items"][0])
        self.assertNotIn("path", history["items"][0])
        self.assertEqual(transcript.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
