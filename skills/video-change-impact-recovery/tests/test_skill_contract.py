import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_frontmatter(self):
        x = (ROOT / "SKILL.md").read_text(encoding="utf8")
        self.assertTrue(x.startswith("---\nname: video-change-impact-recovery\n"))
        self.assertIn("\ndescription: ", x[:500])
        self.assertLess(len(x.splitlines()), 500)

    def test_references_exist(self):
        for name in ("nodetool-contract.md", "continuity.md", "integration.md", "audit-schema.md"):
            self.assertTrue((ROOT / "references" / name).is_file())

    def test_cli_mutation_off_by_default(self):
        spec = importlib.util.spec_from_file_location("nodetool_cli", ROOT / "scripts" / "nodetool_cli.py")
        obj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(obj)
        with patch.dict(os.environ, {}, clear=True), patch("sys.argv", ["nodetool_cli", "snapshot", "test-timeline-id"]):
            self.assertEqual(obj.main(), 2)

    def test_cli_cannot_restore_different_timeline(self):
        spec = importlib.util.spec_from_file_location("nodetool_cli", ROOT / "scripts" / "nodetool_cli.py")
        obj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(obj)
        with patch.dict(os.environ, {"NODETOOL_ALLOW_MUTATION": "yes"}, clear=True), patch("sys.argv", ["nodetool_cli", "rollback", "real-1", "7", "--confirmed-timeline-id", "real-2"]):
            self.assertEqual(obj.main(), 2)


if __name__ == "__main__":
    unittest.main()
