"""Publication boundaries exercised with invented files and isolated Git indexes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "verify_manifest", Path(__file__).resolve().parents[1] / "tools/verify_manifest.py")
publication = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publication)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=".publication-test-", dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.content = b"Synthetic publication example.\n"
        (self.root / "example.txt").write_bytes(self.content)
        self.entry = {"path": "example.txt", "bytes": len(self.content),
                      "sha256": hashlib.sha256(self.content).hexdigest()}
        self.manifest = {"schema_version": 1, "self": publication.MANIFEST,
                         "files": [self.entry]}
        self.write_manifest()

    def write_manifest(self):
        (self.root / publication.MANIFEST).write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def errors(self, strict=False):
        return publication.verify_snapshot(self.root, strict_tracked=strict)[1]

    def init_git(self):
        if not shutil.which("git"):
            self.skipTest("Git is required for strict index integration tests")
        self.git("init", "-q")
        self.git("add", "--", "example.txt", publication.MANIFEST)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              check=True, capture_output=True)

    def test_zip_verification_never_invokes_git(self):
        with patch.object(publication.subprocess, "run", side_effect=AssertionError("No Git call")):
            self.assertEqual((1, []), publication.verify_snapshot(self.root))

    def test_unreadable_or_invalid_json_returns_failure(self):
        path = self.root / publication.MANIFEST
        for content in (b"{", b"\xff"):
            path.write_bytes(content)
            self.assertIn("Cannot read publication manifest", self.errors()[0])
        path.unlink()
        self.assertIn("Cannot read publication manifest", self.errors()[0])

    def test_malformed_manifest_shapes_fail_closed(self):
        for malformed in ([], {}, {**self.manifest, "schema_version": True},
                          {**self.manifest, "self": "other.json"},
                          {**self.manifest, "files": {}}, {**self.manifest, "files": []}):
            with self.subTest(manifest=malformed):
                (self.root / publication.MANIFEST).write_text(json.dumps(malformed), encoding="utf-8")
                self.assertIn("Malformed publication manifest", self.errors()[0])

    def test_malformed_entries_and_metadata_fail_closed(self):
        for malformed in (None, [], {**self.entry, "sha256": "x" * 64},
                          {**self.entry, "sha256": None}, {**self.entry, "bytes": True},
                          {**self.entry, "bytes": -1}, {**self.entry, "bytes": "30"}):
            with self.subTest(entry=malformed):
                self.manifest["files"] = [malformed]
                self.write_manifest()
                self.assertTrue(self.errors())

    def test_duplicate_and_manifest_self_reference_are_rejected(self):
        for entries in ([self.entry, dict(self.entry)],
                        [{**self.entry, "path": publication.MANIFEST}]):
            with self.subTest(entries=entries):
                self.manifest["files"] = entries
                self.write_manifest()
                self.assertTrue(any("Duplicate or self-referencing" in e for e in self.errors()))

    def test_nonportable_and_escaping_paths_are_rejected(self):
        for relative in (None, "", "../outside.txt", "/outside.txt", "C:/outside.txt",
                         "C:outside.txt", "\\\\host\\share", "folder\\example.txt",
                         "./example.txt", "folder/../example.txt", "folder//example.txt", "bad\0name"):
            with self.subTest(path=relative):
                self.manifest["files"] = [{**self.entry, "path": relative}]
                self.write_manifest()
                self.assertTrue(any("Invalid publication path" in e for e in self.errors()))

    def test_resolved_path_outside_root_is_rejected(self):
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == self.root / "example.txt":
                return self.root.parent / "outside.txt"
            return original_resolve(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve):
            self.assertEqual(["Outside repository: example.txt"], self.errors())

    def test_missing_file_or_directory_cannot_pass(self):
        path = self.root / "example.txt"
        path.unlink()
        self.assertEqual(["Missing file: example.txt"], self.errors())
        path.mkdir()
        self.assertEqual(["Missing file: example.txt"], self.errors())

    def test_byte_count_and_same_length_content_change_are_detected(self):
        self.entry["bytes"] += 1
        self.write_manifest()
        self.assertEqual(["Byte count differs: example.txt"], self.errors())
        self.entry["bytes"] -= 1
        self.write_manifest()
        (self.root / "example.txt").write_bytes(b"X" + self.content[1:])
        self.assertEqual(["Changed SHA-256: example.txt"], self.errors())

    def test_strict_mode_requires_git(self):
        with patch.object(publication.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(["Strict tracking requires Git to be installed."], self.errors(strict=True))

    def test_strict_mode_rejects_missing_checkout(self):
        failure = subprocess.CalledProcessError(128, ["git"])
        with patch.object(publication.subprocess, "run", side_effect=failure):
            self.assertIn("requires a readable Git checkout", self.errors(strict=True)[0])

    def test_strict_mode_rejects_containing_repository(self):
        result = subprocess.CompletedProcess([], 0, stdout=str(self.root.parent).encode())
        with patch.object(publication.subprocess, "run", return_value=result):
            self.assertIn("requires this directory to be the Git repository root", self.errors(strict=True)[0])

    def test_strict_index_accepts_exact_set_and_ignores_untracked_files(self):
        self.init_git()
        (self.root / "untracked.txt").write_text("Invented local scratch data", encoding="utf-8")
        self.assertEqual([], self.errors(strict=True))

    def test_strict_index_rejects_unlisted_tracked_file_with_spaces(self):
        self.init_git()
        (self.root / "extra example.txt").write_text("Invented extra payload", encoding="utf-8")
        self.git("add", "--", "extra example.txt")
        self.assertEqual(["Unlisted tracked file: extra example.txt"], self.errors(strict=True))

    def test_strict_index_rejects_manifest_entry_absent_from_index(self):
        self.init_git()
        self.git("rm", "--cached", "--", "example.txt")
        self.assertEqual(["Manifest file is not tracked: example.txt"], self.errors(strict=True))

    def test_strict_index_requires_manifest_itself_to_be_tracked(self):
        self.init_git()
        self.git("rm", "--cached", "--", publication.MANIFEST)
        self.assertEqual([f"Manifest file is not tracked: {publication.MANIFEST}"], self.errors(strict=True))


if __name__ == "__main__":
    unittest.main()
