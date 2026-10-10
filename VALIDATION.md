# Local validation record

Executed on 10 October 2026 in the isolated public snapshot directory, using
Python 3.14.4 on Windows. No private working register was used by these commands.

| Command | Observed result |
| --- | --- |
| `python demo.py reset` | Created the marked synthetic example and generated Markdown views. |
| `python tools/jobflow.py check` | One synthetic case, zero errors, zero warnings. |
| `python tools/jobflow.py next demo-ai-workflow` | `needs_review`, no consistency issues, explicit next action. |
| `python tools/jobflow.py validate demo-ai-workflow` | Passed document, source-ID and review consistency checks. |
| `python -m unittest discover -s tests -q` | 60 tests passed. |

The tests include a changed-CV regression, correct handling of generated-file
hashes, preservation and explicit retraction of submission evidence, run journal
boundaries, refusal to reset unmarked registers, and relative project-catalog
links to local evidence alongside web sources. The final local run was repeated
after adding the local-source rendering regression.
The final demo rendering was also inspected to confirm it describes fictional
records and does not claim imported real tracker history. The test suite was
repeated after this text change and the addition of `.gitattributes`.

A separate text scan of the prepared payload found no private home paths, email
addresses, original employer/project names or repository URLs. This scan is a
limited check; the publication file list was also deliberately constructed from
synthetic material and code copies rather than exported from application folders.
No actual prompts, receipts, applicant records or job histories were copied.

The two tools and two original test files were checked against their local source
SHA-256 values. Exact copy hashes are recorded in PROVENANCE.json. The final
publication manifest can be checked with `python tools/verify_manifest.py`.

The [first published GitHub Actions run](https://github.com/Fostercare5988/ai-job-workflow/actions/runs/38054723757)
passed on 10 October 2026 at commit
`79ffab5b6e10bd37415c2a54496c4a1df4e428a2`. All four matrix jobs passed:
Ubuntu with Python 3.11 and 3.13, and Windows with Python 3.11 and 3.13.

After that run, `actions/checkout` and `actions/setup-python` were updated to
`@v7` to address the reported Node.js 20 deprecation. Follow-up CI for this
dependency update is pending. Local tests were not repeated for this workflow
version and documentation change; the publication manifest was verified.

Passing tests does not prove semantic accuracy of an application, successful
hiring, or production reliability.
