import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.drive_evidence import drive_evidence

SPEC = "specmesh://engineering/simulation/flight-baseline"
AREA = "simulation"
PROJECT = "robot-lab"
SHA = "0123456789abcdef0123456789abcdef01234567"
FILE_ID = "1AbcdEfgh_0123-hello"


class AdapterTests(unittest.TestCase):
    def check(self, rows, revision=SHA):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            path.write_text(json.dumps({"schema_version": 1, "items": rows}), encoding="utf-8")
            return drive_evidence(path, SPEC, AREA, PROJECT, revision)

    def row(self, **updates):
        return {
            "file_id": FILE_ID, "spec_uri": SPEC, "area": AREA, "project": PROJECT,
            "revision": SHA, "title": "Bench run log", "observed_at": "2026-11-21T22:10:00Z",
            **updates,
        }

    def test_canonical_result_ignores_supplied_links_and_unrelated_rows(self):
        actual = self.check([self.row(url="https://example.org/evil"), self.row(project="robot-lab-old")])
        self.assertEqual(actual["status"], "matched")
        self.assertFalse(actual["live_verified"])
        self.assertEqual([x["url"] for x in actual["items"]], [f"https://drive.google.com/file/d/{FILE_ID}/view"])

    def test_wrong_spec_area_project_or_revision_never_falls_back(self):
        for changed in [
            {"spec_uri": SPEC + "-copy"}, {"area": "other"}, {"project": PROJECT + "/other"},
            {"revision": "f" * 40},
        ]:
            self.assertEqual(self.check([self.row(**changed)])["status"], "no_match")

    def test_candidate_requires_full_commit_safe_id_and_utc(self):
        for changed in [
            {"file_id": "../secrets/read"}, {"revision": SHA[:7]}, {"title": ""},
            {"observed_at": "2026-02-30T10:00:00Z"}, {"observed_at": "2026-02-28T10:00:00"},
        ]:
            self.assertEqual(self.check([self.row(**changed)])["status"], "unbound")
        self.assertEqual(self.check([self.row()], SHA[:7])["status"], "unbound")

    def test_no_manifest_and_failed_manifest_are_distinct(self):
        self.assertEqual(drive_evidence(None, SPEC, AREA, PROJECT, SHA)["status"], "not_checked")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "not-yet.json"
            self.assertEqual(drive_evidence(path, SPEC, AREA, PROJECT, SHA)["reason"], "manifest_not_found")
            path.write_text("not JSON", encoding="utf-8")
            self.assertEqual(drive_evidence(path, SPEC, AREA, PROJECT, SHA)["status"], "failed")

    def test_duplicate_observation_retains_latest_but_title_conflict_is_unbound(self):
        later = "2026-11-23T22:10:00Z"
        matched = self.check([self.row(), self.row(observed_at=later)])
        self.assertEqual(len(matched["items"]), 1)
        self.assertEqual(matched["items"][0]["observed_at"], later)
        conflict = self.check([self.row(), self.row(title="Different evidence")])
        self.assertEqual(conflict["status"], "unbound")


if __name__ == "__main__":
    unittest.main()
