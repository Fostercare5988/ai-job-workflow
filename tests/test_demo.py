import importlib.util
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("demo", Path(__file__).resolve().parents[1] / "demo.py")
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class DemoTests(unittest.TestCase):
    def setUp(self):
        test_dir = Path(__file__).resolve().parent
        self.tmp = tempfile.TemporaryDirectory(prefix=".demo-test-", dir=test_dir)
        self.root = Path(self.tmp.name)
        self.assertTrue(self.root.resolve().is_relative_to(test_dir))
        self.addCleanup(self.tmp.cleanup)
        self.root.joinpath("DEMO_ONLY").write_text("SYNTHETIC-DEMO-ONLY\n", encoding="utf-8")
        self.root_patch = patch.object(demo, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def reset(self):
        with redirect_stdout(StringIO()):
            demo.reset()

    def test_synthetic_package_passes_local_checks(self):
        self.reset()
        db = demo.jobflow.load(self.root)
        self.assertTrue(db["demo_only"])
        self.assertEqual("needs_review", db["jobs"][0]["status"])
        self.assertEqual([], demo.jobflow.validate(self.root, db["jobs"][0]))
        self.assertEqual([], demo.jobflow.check(self.root, db)["errors"])

    def test_reset_refuses_unmarked_data_before_any_write(self):
        path = self.root / "Data/jobs.json"
        path.parent.mkdir()
        path.write_text('{"schema_version": 1, "jobs": []}', encoding="utf-8")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "unmarked"):
            self.reset()
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_changed_cv_requires_review_and_explicit_reset_restores_fixture(self):
        self.reset()
        job = demo.jobflow.load(self.root)["jobs"][0]
        path = self.root / job["files"]["cv"]
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\nChanged synthetic content.\n", encoding="utf-8")
        self.assertTrue(any("matcher ikke" in issue for issue in demo.jobflow.validate(self.root, job)))
        self.reset()
        self.assertEqual(original, path.read_text(encoding="utf-8"))
        self.assertEqual([], demo.jobflow.validate(self.root, demo.jobflow.load(self.root)["jobs"][0]))


if __name__ == "__main__":
    unittest.main()
