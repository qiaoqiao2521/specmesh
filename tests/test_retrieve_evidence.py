import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
