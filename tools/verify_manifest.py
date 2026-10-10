"""Verify listed publication snapshot files. Does not update the manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "PUBLICATION_MANIFEST.json").read_text(encoding="utf-8"))
    errors = []
    for item in manifest["files"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            errors.append(f"Outside repository: {item['path']}")
        elif not path.is_file():
            errors.append(f"Missing: {item['path']}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(f"Changed: {item['path']}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: {len(manifest['files'])} listed snapshot files match SHA-256.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
