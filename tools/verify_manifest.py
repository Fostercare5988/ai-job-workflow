"""Verify the publication snapshot without modifying it.

Normal verification also works in a ZIP extraction. --strict-tracked additionally
requires Git and checks the index against the explicit publication file list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "PUBLICATION_MANIFEST.json"


def tracked_paths(root):
    """Read this checkout's index; never fall back to a containing repository."""
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True,
        )
        if Path(top.stdout.decode("utf-8", errors="surrogateescape").strip()).resolve() != root:
            raise ValueError("Strict tracking requires this directory to be the Git repository root.")
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True, capture_output=True,
        )
    except FileNotFoundError as exc:
        raise ValueError("Strict tracking requires Git to be installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("Strict tracking requires a readable Git checkout and index.") from exc
    return set(result.stdout.decode("utf-8", errors="surrogateescape").split("\0")) - {""}


def verify_snapshot(root, strict_tracked=False):
    root = Path(root).resolve()
    errors = []
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return 0, [f"Cannot read publication manifest: {exc}"]
    if (not isinstance(manifest, dict)
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1
            or manifest.get("self") != MANIFEST
            or not isinstance(manifest.get("files"), list)
            or not manifest["files"]):
        return 0, ["Malformed publication manifest: expected schema_version 1, self name and nonempty files list."]

    expected = {MANIFEST}
    for index, item in enumerate(manifest["files"]):
        if not isinstance(item, dict):
            errors.append(f"Malformed file entry {index}: expected an object.")
            continue
        relative = item.get("path")
        # Require one portable spelling per path; reject Windows escapes even
        # when verifying on POSIX. resolve() also catches symlinks out of root.
        if (not isinstance(relative, str) or not relative
                or "\\" in relative or ":" in relative or "\0" in relative
                or any(part in {"", ".", ".."} for part in relative.split("/"))):
            errors.append(f"Invalid publication path in entry {index}: {relative!r}")
            continue
        if relative in expected:
            errors.append(f"Duplicate or self-referencing publication path: {relative}")
            continue
        expected.add(relative)
        checksum, size = item.get("sha256"), item.get("bytes")
        if (not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum)
                or type(size) is not int or size < 0):
            errors.append(f"Malformed hash or byte count: {relative}")
            continue
        try:
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                errors.append(f"Outside repository: {relative}")
                continue
            if not path.is_file():
                errors.append(f"Missing file: {relative}")
                continue
            content = path.read_bytes()
            if len(content) != size:
                errors.append(f"Byte count differs: {relative}")
            if hashlib.sha256(content).hexdigest() != checksum:
                errors.append(f"Changed SHA-256: {relative}")
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"Cannot inspect {relative}: {exc}")

    if strict_tracked:
        try:
            tracked = tracked_paths(root)
            errors.extend(f"Unlisted tracked file: {path}" for path in sorted(tracked - expected))
            errors.extend(f"Manifest file is not tracked: {path}" for path in sorted(expected - tracked))
        except ValueError as exc:
            errors.append(str(exc))
    return len(manifest["files"]), errors


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-tracked", action="store_true",
                        help="Also require the Git index to match the manifest exactly.")
    args = parser.parse_args(argv)
    count, errors = verify_snapshot(root, strict_tracked=args.strict_tracked)
    if errors:
        print("\n".join(errors))
        return 1
    suffix = " Git tracked files match the allowlist." if args.strict_tracked else ""
    print(f"PASS: {count} listed snapshot files match byte counts and SHA-256.{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
