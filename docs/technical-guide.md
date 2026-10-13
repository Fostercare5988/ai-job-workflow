# JobFlow: technical guide

[Dansk](technical-guide.da.md) · [Try the demo first](getting-started.md) · [Project](../README.md)

## The moving parts

| File or tool | Responsibility |
| --- | --- |
| `Data/jobs.json` | The single current job-status register. |
| `Profil/fakta.json` and `Profil/projekter.json` | Facts and project evidence identified by source IDs. |
| `Ansoegninger_Aktive/<id>/` | Posting notes, source mapping, drafts and review for one case. |
| `tools/jobflow.py` | Record operations, consistency checks, review fingerprints and generated Markdown views. |
| `tools/jobrun.py` | Requests, actual work performed and the next action for a work session. |
| `AGENTS.md` and `FRAMEWORK.md` | Instructions for the assistant using the files. |

One responsible assistant owns the job register. Other agents can research or review bounded tasks in separate files. The run journal references cases; it does not maintain a second set of job statuses.

These are local Python tools using the standard library. They do not call a model API, browse websites, send applications or messages, update external job portals, or run in the background. An assistant's available tools determine which research and writing work it can perform.

## Useful commands

Run commands from the repository root. The [getting-started guide](getting-started.md) explains how to create the disposable example.

```text
python tools/jobflow.py check
python tools/jobflow.py next demo-ai-workflow
python tools/jobflow.py fingerprints demo-ai-workflow
python tools/jobflow.py validate demo-ai-workflow
python tools/jobflow.py render
python -m unittest discover -s tests -v
```

`check` writes a register report. `next` reads the current case and describes the next action. `fingerprints` calculates hashes for the relevant documents, source registers, writing guide and case context. `validate` compares the saved review with the current material. `render` regenerates the overview, case handoffs and project catalogue; edit the underlying records rather than those generated views.

Reading a source and recording a genuine review must happen before updating review hashes. A matching hash proves that the recorded bytes have not changed, not that their contents are true. The demo is an exception only because its review is explicitly synthetic test data.

The [validation record](../VALIDATION.md) distinguishes recorded runs from test code that merely exists. The CI workflow runs tests and demo checks on its declared Python and operating-system matrix.

## Record and resume a work session

After resetting the demo, the following commands create and resume a local example journal:

```text
python tools/jobrun.py start demo-run --request "Inspect the synthetic example" --job-id demo-ai-workflow --next-action "Read the sources and run checks"
python tools/jobrun.py note demo-run --phase review --evidence "Read the fictional source mapping and current check output" --next-action "Record any remaining issue"
python tools/jobrun.py resume demo-run
```

Run `note` only after doing the work described in its evidence. `resume` reads current job statuses from `Data/jobs.json`. A journal entry is neither approval nor evidence that a check passed. Locally created journals are not included in the public file allowlist. Use a new run ID if `demo-run` already exists.

## Adapt the approach to your own job search

This repository is a demonstration, not a configured service that finds and applies for jobs on installation. A real setup needs a private workspace, actual candidate sources, writing preferences and an AI assistant with appropriate research tools.

1. Make a separate private working copy. Keep this public demo for experiments, and keep real applicant data out of the public repository.
2. In the private copy, replace the fictional job register with an empty one: `{"schema_version": 1, "jobs": []}`. Start the fact and project registers with `{"facts": []}` and `{"projects": []}`. Remove fictional case files and replace the synthetic evidence with your own documented sources.
3. Record the provenance of your actual source material. The inventory file at `Profil/Kilder/github_inventory.json` needs an actual `checked_at` date for source review; do not copy a demo date and present it as a GitHub check.
4. Adapt `AGENTS.md`, `FRAMEWORK.md` and `System/SKRIVESTIL.md` to your needs and voice. File names and generated text are partly Danish; adapt them in your own copy if needed.
5. Use the blank [job template](../templates/job.json) for real cases and the [review template](../templates/review.json) for genuine review. The review checks deliberately start false. Fill the posting, source mapping, complete targeted CV and required motivation format before recording a package as ready.
6. Let your assistant perform the research and document work, then inspect the deliverables. Provide only the access needed for that work. The Python scripts remain local record and checking tools.

Do not use `demo.py reset` in the private working copy. It is designed to replace the synthetic registers, not maintain personal data. Review, PDF export, applicant approval, submission and external Joblog registration are distinct events. Record an application as sent only from an actual receipt or the applicant's explicit confirmation.

## Boundaries

- A valid source ID does not establish that the source supports a sentence. Someone must read both.
- Changes to reviewed documents, source registers or case requirements can make a review stale. Re-read the relevant material rather than merely replacing hashes.
- Duplicate detection is conservative. Similar jobs can still need manual comparison.
- The local file lock prevents overlapping tool writes. This is not a multi-user service or a tamper-proof audit trail.
- A recorded submission date and evidence text cannot authenticate an external submission or the assistant's authority to make it.
- Stop after three concrete correction rounds if a problem remains, and describe the gap. Do not mark unfinished work ready to clear a warning.

## Provenance and publication

Niko directs the original workflow; development and preparation of this demonstration were AI-assisted. The public demo is separate from the private working project. [PROVENANCE.json](../PROVENANCE.json) records the origins of copied code, while [PUBLICATION_MANIFEST.json](../PUBLICATION_MANIFEST.json) lists the reviewed public files and their hashes.

To check an untouched publication snapshot, run:

```text
python tools/verify_manifest.py
```

Resetting demo dates or editing files intentionally changes the listed hashes. The manifest describes the publication snapshot, not a live security or integrity service. A default-deny `.gitignore` is an additional publishing boundary; it is not a substitute for reviewing the exact staged files.

No license has been selected in this snapshot. Check the repository's current license information before redistributing or incorporating its code elsewhere.
