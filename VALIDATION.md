# Validation record

## Refresh: 13 October 2026

Executed in the separate public demonstration on Windows with Python 3.14.4.
The private job register was not used. All commands below completed successfully.

| Command | Observed result |
| --- | --- |
| `python demo.py reset` | Recreated one marked fictional job package with current relative dates. |
| `python -m unittest discover -s tests -q` | 76 tests passed. |
| `python tools/jobflow.py check` | One synthetic case; zero errors and zero warnings. |
| `python tools/jobflow.py validate demo-ai-workflow` | Passed consistency checks. |
| `python tools/jobflow.py next demo-ai-workflow` | `needs_review`, no issues; next step is to read documents and sources. |

The suite includes the changed-CV failure case: modifying a reviewed document
invalidates its old review. Sixteen publication tests exercise malformed manifests,
duplicate paths, byte/hash mismatches, path boundaries and exact Git-index checks.
The English and Danish presentation PDFs were rendered and visually inspected:
one A4 page each, no overlap or clipping, only the intended contact mail link.
README and guide links were checked against the reviewed public file list.

The demo's applicant and vacancy data is fictional. The approved personal case
presentation describes Niko's actual project and intentionally includes his name,
professional title, city and contact email. No private application, receipt, street
address or actual internal request is included. Publication uses an explicit file
list; a text scan supplements that review and does not prove the absence of all
possible private content.

`PUBLICATION_MANIFEST.json` is generated after final file changes. Verify a fresh
checkout with `python tools/verify_manifest.py --strict-tracked`, or a ZIP download
with `python tools/verify_manifest.py`. Resetting demo dates intentionally changes
snapshot hashes. The CI workflow verifies the untouched snapshot before reset.
The current refresh's CI result can be checked in the repository's Actions tab.

## Earlier checks: 10 October 2026

The original public demo passed 60 local tests. The first published CI run passed
on Ubuntu and Windows with Python 3.11 and 3.13 at commit
`79ffab5b6e10bd37415c2a54496c4a1df4e428a2`.

The [follow-up run after updating the CI actions](https://github.com/Fostercare5988/jobflow/actions/runs/38055034729)
also completed successfully at commit
`513ca7e2dbe2a0a5e22b29ca17b9c33ed379a06e`. Its result was re-read on 13 October;
the former pending note has been resolved. Original records and code-copy hashes
are retained in Git history and `PROVENANCE.json`.

Passing checks does not establish the factual accuracy of a real application,
hiring success, automatic submission or production reliability.
