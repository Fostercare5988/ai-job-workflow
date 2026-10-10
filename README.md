# AI-assisted job application workflow

A local workflow for turning a short request into a targeted CV, motivation,
source notes and an explicit handoff. The problem is keeping useful drafts
separate from verified facts, fresh reviews and actual submission.

This public snapshot contains **synthetic data only**. The applicant, employer,
project and vacancy are invented. URLs use `.invalid`; nothing is being applied
for. The original working project remains separate.

## What does the work?

An AI assistant researches available sources, selects relevant examples, writes
the documents and reviews their wording. One responsible assistant owns the
register; optional delegated tasks get separate files and explicit boundaries.
The assistant runs through research, drafting, review and correction, with a
limit of three correction rounds before documenting a remaining problem.

The Python tools check structure, files, deadlines, source IDs, duplicate cases,
review fingerprints and status transitions. They maintain a run journal and
generate readable Markdown views. They **do not call a model API, browse, send
applications, update external job portals or run in the background**.

This is a harness for work carried out by an assistant with tools available in
its own environment. The Python scripts alone do not research or write a CV.

## Quickstart

Python 3.10 or newer, standard library only. Run these commands from this
repository's root, using `python3` if that is your Python command:

```text
python demo.py reset
python tools/jobflow.py next demo-ai-workflow
python tools/jobflow.py check
python tools/jobflow.py validate demo-ai-workflow
python -m unittest discover -s tests -v
```

The reset creates a disposable fictional package with dates relative to today.
It refuses to overwrite register files that lack the `demo_only` marker. It also
generates a **passing test review fixture**, whose flags are expected test values,
not a claim that a real vacancy or applicant has been checked. Do not run this
reset script on real applicant data.

The example remains `needs_review`. A successful `validate` checks consistency;
it does not approve an application or establish that a sentence is true. Edit
the sample CV and run `validate` again to see the fingerprint mismatch. Use
`python demo.py reset` to restore the fictional example.

## Follow the files

- [Workflow and boundaries](FRAMEWORK.md): responsibilities and exit conditions.
- [Example CV](Ansoegninger_Aktive/demo-ai-workflow/cv.md): a targeted fictional draft.
- [Source mapping](Ansoegninger_Aktive/demo-ai-workflow/match.md) and
  [synthetic evidence](demo/evidence.md): claims have explicit source IDs.
- [Review fixture](Ansoegninger_Aktive/demo-ai-workflow/review.json): dated checks
  and file hashes, explicitly marked synthetic.
- [Generated handoff](Ansoegninger_Aktive/demo-ai-workflow/AFLEVERING.md) and
  [overview](AKTUEL_STATUS.md): current checks and the next action.
- [Blank review template](templates/review.json): real review checks start false.

The inherited tools retain Danish file names and user-facing messages from the
original workflow. The README and fictional source documents are in English.

## Record and resume work

`Data/jobs.json` is the single job status register. A separate journal keeps the
request, actual work performed, references to job IDs and the next step. It does
not copy the job statuses. `resume` reads their current values from the register.

```text
python tools/jobrun.py start demo-run --request "Inspect the synthetic example" --job-id demo-ai-workflow --next-action "Read sources and run checks"
python tools/jobrun.py note demo-run --phase review --evidence "Inspected the fictional sources and current check output" --next-action "Document any remaining issue"
python tools/jobrun.py resume demo-run
```

Only record work that was actually performed. Run journals created locally are
ignored by the publication allowlist. The tracked snapshot contains no private
requests, receipts or application histories.

For real use, start from the blank templates in a separate private workspace.
Replace the fictional evidence with actual sources and perform a genuine review.
Do not turn synthetic fixture flags into an automatic reviewer.

## Practical limits

- A valid source ID and an unchanged hash do not prove a claim is supported.
  A reviewer must read the source and document.
- Duplicate matching is conservative. Similar titles can need manual judgment;
  tracking parameters and job identity fragments are handled explicitly.
- A passing review goes stale when documents, requirements or source registers
  change. Current posting and review dates are required for a new ready state.
- Approval, PDF export, actual submission and external job-log registration are
  different events. A submitted state requires dated evidence; the tool cannot
  authenticate that evidence or an assistant's permission to act.
- One short-lived local lock prevents interleaved writes through the tools.
  This is a local file workflow, not a multi-user service or secure audit system.

Tests cover state transitions, historical corrections, duplicate URLs, changed
documents, malformed input, path boundaries, run handoffs and synthetic setup.
See [the actual validation record](VALIDATION.md) for commands executed for this
snapshot. There are no benchmark or hiring-success claims.

## Provenance and publication

Niko directed the original workflow and reviews its use. Its development and
this public preparation were AI-assisted. The tools and their original tests
are copied from the local framework; this directory is a separate snapshot and
does not sync private data. [PROVENANCE.json](PROVENANCE.json) records relative
source paths and SHA-256 values for those copies.

[PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json) lists the public files and
their hashes. Verify the untouched snapshot with:

```text
python tools/verify_manifest.py
```

Resetting demo dates or editing files intentionally changes those hashes.
The manifest describes the publication snapshot, not a live integrity service.
`.gitattributes` disables Git line-ending conversion so a fresh clone preserves
the recorded byte hashes, including when `core.autocrlf` is enabled.
The default-deny `.gitignore` is an extra boundary; publishing should still stage
only the reviewed manifest files. No license has been selected in this snapshot.
