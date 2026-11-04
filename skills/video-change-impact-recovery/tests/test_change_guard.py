import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("change_guard", ROOT / "scripts" / "change_guard.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def fixture():
    return json.loads((ROOT / "examples" / "timeline-normalized.json").read_text(encoding="utf8"))


class ChangeGuardTests(unittest.TestCase):
    def test_inspect_valid(self):
        self.assertEqual(len(g._node_map(fixture())[0]), 13)

    def test_replace_local_only(self):
        f = fixture()
        p = g.build_plan(f, {"type": "replace_media", "target": "S03", "asset_ref": "asset://v2"})
        self.assertEqual(p["predicted_changes"], {"S03": ["asset_ref"]})
        self.assertTrue(g.verify(f, p["candidate"], p)["passed"])
        self.assertIn("VOICE03", p["impact_ids"])
        self.assertNotIn("S05", p["impact_ids"])

    def test_extend_moves_later_shots_and_sync_audio(self):
        f = fixture()
        p = g.build_plan(f, {"type": "change_duration", "target": "S03", "new_duration_ms": 7000})
        n = g._node_map(p["candidate"])[0]
        self.assertTrue(p["ready_for_write"])
        self.assertEqual(n["S04"]["start_ms"], 17000)
        self.assertEqual(n["S06"]["start_ms"], 27000)
        self.assertEqual(n["VOICE04"]["start_ms"], 17500)
        self.assertEqual(n["SUB04"]["start_ms"], 17500)
        self.assertEqual(n["TRANS_03_04"]["start_ms"], 16700)
        self.assertEqual(n["BGM"]["start_ms"], 0)
        self.assertEqual(n["BGM"]["duration_ms"], 30000)
        self.assertTrue(any("BGM" in w for w in p["warnings"]))
        self.assertTrue(g.verify(f, p["candidate"], p)["passed"])

    def test_absolute_audio_blocks_extend(self):
        f = fixture()
        for n in f["objects"]:
            if n["id"] == "VOICE04":
                n.pop("sync")
                n["deps"] = []
        p = g.build_plan(f, {"type": "change_duration", "target": "S03", "new_duration_ms": 7000})
        self.assertFalse(p["ready_for_write"])
        self.assertIn("VOICE04", " ".join(p["blockers"]))
        self.assertFalse(g.verify(f, p["candidate"], p)["passed"])

    def test_locked_downstream_blocks(self):
        f = fixture()
        for n in f["objects"]:
            if n["id"] == "S05":
                n["locked"] = True
        p = g.build_plan(f, {"type": "change_duration", "target": "S03", "new_duration_ms": 7000})
        self.assertFalse(p["ready_for_write"])

    def test_locked_target_blocks(self):
        f = fixture()
        for n in f["objects"]:
            if n["id"] == "S03":
                n["locked"] = True
        with self.assertRaises(ValueError):
            g.build_plan(f, {"type": "replace_media", "target": "S03", "asset_ref": "asset://v2"})

    def test_injected_unrelated_change_rejected(self):
        f = fixture()
        p = g.build_plan(f, {"type": "replace_media", "target": "S03", "asset_ref": "asset://v2"})
        candidate = copy.deepcopy(p["candidate"])
        for n in candidate["objects"]:
            if n["id"] == "S01":
                n["asset_ref"] = "asset://injected"
        v = g.verify(f, candidate, p)
        self.assertFalse(v["passed"])
        self.assertTrue(any("unapproved" in m for m in v["errors"]))

    def test_unexpected_add_rejected(self):
        f = fixture()
        p = g.build_plan(f, {"type": "replace_media", "target": "S03", "asset_ref": "asset://v2"})
        candidate = copy.deepcopy(p["candidate"])
        candidate["objects"].append({"id": "HACK", "kind": "shot", "start_ms": 30000, "duration_ms": 100, "deps": []})
        self.assertFalse(g.verify(f, candidate, p)["passed"])

    def test_post_revision_can_change(self):
        f = fixture()
        p = g.build_plan(f, {"type": "replace_media", "target": "S03", "asset_ref": "asset://v2"})
        after = copy.deepcopy(p["candidate"])
        after["revision"] = "new-native-revision-token"
        self.assertTrue(g.verify(f, after, p)["passed"])

    def test_stale_base_rejected(self):
        f = fixture()
        p = g.build_plan(f, {"type": "replace_media", "target": "S03", "asset_ref": "asset://v2"})
        f["revision"] = "someone-else-wrote"
        self.assertFalse(g.verify(f, p["candidate"], p)["passed"])

    def test_duplicate_rejected(self):
        f = fixture()
        f["objects"].append(copy.deepcopy(f["objects"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            g._node_map(f)

    def test_missing_dependency_rejected(self):
        f = fixture()
        f["objects"][6]["deps"].append("MISSING")
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            g._node_map(f)

    def test_dependency_cycle_rejected(self):
        f = fixture()
        f["objects"][2]["deps"] = ["VOICE03"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            g._node_map(f)

    def test_transition_change_only(self):
        f = fixture()
        p = g.build_plan(f, {"type": "change_transition", "target": "TRANS_03_04", "asset_ref": "preset:whip"})
        self.assertEqual(p["predicted_changes"], {"TRANS_03_04": ["asset_ref"]})
        self.assertTrue(g.verify(f, p["candidate"], p)["passed"])

    def test_bad_sync_drift_rejected(self):
        f = fixture()
        for n in f["objects"]:
            if n["id"] == "VOICE04":
                n["start_ms"] = 12345
        with self.assertRaisesRegex(ValueError, "sync drift"):
            g._node_map(f)

    def test_ambiguous_overlap_blocks(self):
        f = fixture()
        for n in f["objects"]:
            if n["id"] == "S04":
                n["start_ms"] = 14900
            if n["id"] == "VOICE04":
                n["start_ms"] = 15400
            if n["id"] == "SUB04":
                n["start_ms"] = 15400
        p = g.build_plan(f, {"type": "change_duration", "target": "S03", "new_duration_ms": 7000})
        self.assertFalse(p["ready_for_write"])


if __name__ == "__main__":
    unittest.main()
