"""Reset the disposable synthetic example. Never use this with real applicant data.

This deliberately generates a passing *test fixture*, including review flags.
Those flags are not evidence of factual review. Real reviews must be read and
completed by a reviewer; use templates/review.json, whose checks start false.
No model API, network requests or messages are sent.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import jobflow

JOB_ID = "demo-ai-workflow"


def reset():
    if (ROOT / "DEMO_ONLY").read_text(encoding="utf-8").strip() != "SYNTHETIC-DEMO-ONLY":
        raise ValueError("This command only resets the marked synthetic demonstration.")
    # Fail closed if real data has been placed over any of the fixture registers.
    for relative in ("Data/jobs.json", "Profil/fakta.json", "Profil/projekter.json",
                     "Profil/Kilder/github_inventory.json"):
        path = ROOT / relative
        if path.exists() and jobflow.read_json(path).get("demo_only") is not True:
            raise ValueError(f"Refusing to overwrite unmarked data: {relative}")

    now = jobflow.today()
    packet = f"Ansoegninger_Aktive/{JOB_ID}"
    jobflow.atomic_write(ROOT / "demo/evidence.md", """# Synthetic evidence

Every person, project and vacancy in this fixture is invented.

- FACT-DEMO-EDU: Alex Example completed a fictional technical programme.
- PROJ-DEMO-WORKFLOW: Alex used Python and AI assistance to build a local
  document workflow with file hashes, explicit state changes and regression tests.

These are fixture assertions for demonstrating source mapping. They do not
describe Niko, a real applicant, a real repository or measured production results.
""")
    jobflow.atomic_write(ROOT / "System/SKRIVESTIL.md", """# Synthetic writing guide

Use plain language and concrete examples. Distinguish the applicant's own work
from AI assistance and upstream code. Do not claim production results without
evidence. No photographs or age in the sample CV. This guide contains no
private style instructions from the original workspace.
""")
    jobflow.save_json(ROOT / "Profil/fakta.json", {
        "demo_only": True, "facts": [{"id": "FACT-DEMO-EDU", "external_use": True,
                                       "text": "Synthetic technical education",
                                       "source": "demo/evidence.md"}]})
    jobflow.save_json(ROOT / "Profil/projekter.json", {
        "demo_only": True, "projects": [{
            "id": "PROJ-DEMO-WORKFLOW", "name": "Synthetic document workflow",
            "summary": "An invented project used to demonstrate source-mapped writing.",
            "tags": ["Python", "AI-assisted development", "validation"],
            "evidence_level": "Synthetic fixture, not external verification",
            "external_use": True,
            "safe_claim_da": "Alex developed a local document workflow with AI assistance.",
            "limitations": "No real project, runtime benchmark or production claim.",
            "sources": [{"label": "Synthetic evidence", "url": "https://example.invalid/demo-project",
                         "snapshot": "demo/evidence.md"}]}]})
    jobflow.save_json(ROOT / "Profil/Kilder/github_inventory.json", {
        "demo_only": True, "checked_at": now.isoformat(), "repositories": [],
        "note": "Fixture date only. No GitHub inventory was fetched."})
    jobflow.atomic_write(ROOT / f"{packet}/opslag.md", f"""# Synthetic vacancy: AI workflow developer

This is an invented vacancy at Example Workshop. It is not open for applications.
The .invalid URL is a placeholder and no employer website was checked.

- Fixture date: {now.isoformat()}
- Synthetic deadline: {(now + timedelta(days=21)).isoformat()}
- Format: targeted CV only, no photograph or age.
- Tasks: build document workflows, inspect failure cases, maintain tests.
- Location: Example City. Postcode and country are synthetic fixture values.
""")
    jobflow.atomic_write(ROOT / f"{packet}/match.md", """# Synthetic match

| Fictional task | Example evidence |
| --- | --- |
| Build document workflows | PROJ-DEMO-WORKFLOW |
| Inspect failure cases and maintain tests | PROJ-DEMO-WORKFLOW |
| Apply a broad technical foundation | FACT-DEMO-EDU |

The writing is an illustration, not evidence about an actual applicant.
""")
    jobflow.atomic_write(ROOT / f"{packet}/cv.md", """# Alex Example

Synthetic applicant. This CV demonstrates document structure only.

## Profile

I completed a technical programme and developed a local document workflow with
AI assistance. I would like to work on clear handoffs and useful failure checks.

## Technical foundation

- Completed a fictional technical programme.
- Used Python and AI assistance to build a local document workflow with file
  hashes, explicit state changes and regression tests.

## Relevant project

The synthetic document workflow separates source records, drafts and review.
Its checks can detect file changes; a reviewer still decides whether a source
supports the wording.
""")
    job = {
        "id": JOB_ID, "company": "Example Workshop (synthetic)",
        "title": "AI workflow developer (synthetic)",
        "url": "https://example.invalid/jobs/demo-ai-workflow", "url_kind": "direct",
        "language": "en", "created_at": now.isoformat(),
        "deadline": (now + timedelta(days=21)).isoformat(),
        "deadline_note": "Synthetic relative date; no actual vacancy or verified deadline",
        "posting_checked_at": now.isoformat(), "posting_status": "open",
        "requirements": {"format": "cv_only", "no_photo": True, "no_age": True, "max_words": None},
        "status": "needs_review", "history": [], "submission": None,
        "selected_sources": ["FACT-DEMO-EDU", "PROJ-DEMO-WORKFLOW"],
        "joblog_form": {"posting_url": "https://example.invalid/jobs/demo-ai-workflow",
                        "postcode": "0000", "city": "Example City", "country": "Synthetic country",
                        "address": None, "contact_person": None, "email": None, "phone": None,
                        "source_note": "All values are synthetic. Optional contact fields are deliberately empty.",
                        "sources": [{"label": "Invented fixture location", "url": "https://example.invalid/contact"}]},
        "files": {key: f"{packet}/{name}" for key, name in {
            "posting": "opslag.md", "match": "match.md", "cv": "cv.md", "review": "review.json"}.items()},
        "next_action": "Inspect the synthetic package; no real application is possible",
        "follow_up_on": None, "legacy": None,
    }
    jobflow.save_json(ROOT / "Data/jobs.json", {"schema_version": 1, "demo_only": True, "jobs": [job]})
    # Synthetic expected-result fixture only. Never use this for real candidate review.
    jobflow.save_json(ROOT / f"{packet}/review.json", {
        "demo_only": True, "reviewed_by": "Synthetic test fixture, not a factual reviewer",
        "reviewed_at": now.isoformat(), "checks": {key: True for key in jobflow.CHECKS},
        "claims": [{"text": "Completed a fictional technical programme", "source_ids": ["FACT-DEMO-EDU"]},
                   {"text": "Built a synthetic workflow with AI assistance", "source_ids": ["PROJ-DEMO-WORKFLOW"]}],
        "limitations": ["All checks are fixture values. A passing result does not establish truth."],
        "artifact_hashes": jobflow.hashes(ROOT, job),
    })
    jobflow.render(ROOT, jobflow.load(ROOT))
    print("Synthetic example reset. No real job, source verification or factual review was performed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("reset",))
    parser.parse_args()
    reset()


if __name__ == "__main__":
    main()
