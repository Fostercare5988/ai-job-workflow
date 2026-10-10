import importlib.util
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("jobrun", TOOLS / "jobrun.py")
runflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runflow)


class JobrunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="jobrun-test-", dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "Data").mkdir()
        self.db = {"schema_version": 1, "jobs": []}
        self.write_db()

    def write_db(self):
        (self.root / "Data/jobs.json").write_text(json.dumps(self.db), encoding="utf-8")

    def call(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            runflow.main(["--root", str(self.root), *args])
        return output.getvalue()

    def start(self, *extra):
        self.call("start", "demo-run", "--request", "Forbedr projektet.",
                  "--next-action", "Læs grundlaget", *extra)

    def read_run(self):
        return json.loads((self.root / "Koersler/Forloeb/demo-run.json").read_text(encoding="utf-8"))

    def test_run_journal_never_modifies_job_register(self):
        original = (self.root / "Data/jobs.json").read_bytes()
        self.start()
        self.call("note", "demo-run", "--phase", "review", "--evidence", "Kørte kontrollen",
                  "--next-action", "Ret fund")
        self.assertEqual(original, (self.root / "Data/jobs.json").read_bytes())
        self.assertEqual(2, len(self.read_run()["events"]))

    def test_duplicate_start_preserves_existing_log(self):
        self.start()
        original = self.read_run()
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(original, self.read_run())

    def test_run_id_and_artifact_cannot_escape_workspace(self):
        for bad in ("../escape", "C:/escape", "con"):
            with self.assertRaises(ValueError):
                runflow.run_path(self.root, bad)
        self.start()
        with self.assertRaises(ValueError):
            self.call("finish", "demo-run", "--outcome", "delivered", "--summary", "Færdig",
                      "--next-action", "Læs", "--artifact", "../secret.txt")

    def test_unknown_job_reference_rejected(self):
        with self.assertRaises(ValueError):
            self.start("--job-id", "does-not-exist")
        self.assertFalse((self.root / "Koersler/Forloeb/demo-run.json").exists())

    def test_finish_requires_existing_deliverable_and_preserves_failed_run(self):
        self.start()
        for extra in ([], ["--artifact", "missing.md"]):
            with self.assertRaises(ValueError):
                self.call("finish", "demo-run", "--outcome", "delivered", "--summary", "Færdig",
                          "--next-action", "Læs", *extra)
        self.assertEqual("open", self.read_run()["run_state"])

    def test_closed_run_cannot_be_silently_rewritten(self):
        self.start()
        (self.root / "report.md").write_text("Resultat", encoding="utf-8")
        self.call("finish", "demo-run", "--outcome", "delivered", "--summary", "Kontrolleret",
                  "--next-action", "Læs rapporten", "--artifact", "report.md")
        original = self.read_run()
        with self.assertRaises(ValueError):
            self.call("note", "demo-run", "--phase", "write", "--evidence", "Ny tekst",
                      "--next-action", "Review")
        self.assertEqual(original, self.read_run())

    def test_lock_prevents_lost_updates(self):
        self.start()
        with runflow.jobflow.lock(self.root):
            with self.assertRaises(ValueError):
                self.call("note", "demo-run", "--phase", "review", "--evidence", "Check",
                          "--next-action", "Læs")
        self.assertEqual(1, len(self.read_run()["events"]))

    def test_request_file_keeps_actual_multiline_request(self):
        request = "Første linje.\nAnden linje."
        (self.root / "request.md").write_text(request, encoding="utf-8")
        self.call("start", "demo-run", "--request-file", "request.md", "--next-action", "Læs")
        self.assertEqual(request, self.read_run()["request"])


if __name__ == "__main__":
    unittest.main()
