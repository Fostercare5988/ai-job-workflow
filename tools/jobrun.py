"""Small run journal for the assistant. No model calls, network or job status writes."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

import jobflow

ROOT = Path(__file__).resolve().parents[1]
PHASES = ("orient", "research", "match", "write", "review", "deliver", "maintenance")


def run_path(root, run_id):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,100}", run_id):
        raise ValueError("Kørsels-id skal være 3-101 små ASCII-bogstaver, tal eller bindestreger")
    if run_id.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("Reserveret filnavn")
    return jobflow.local_path(root, f"Koersler/Forloeb/{run_id}.json")


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} må ikke være tom")
    return value.strip()


def job_references(root, ids):
    db = jobflow.load(root)
    for job_id in ids:
        jobflow.find(db, job_id)
    return list(dict.fromkeys(ids))


def read_run(path):
    run = jobflow.read_json(path)
    if (not isinstance(run, dict) or run.get("schema_version") != 1
            or run.get("run_state") not in {"open", "closed"}
            or not isinstance(run.get("events"), list)
            or not isinstance(run.get("job_ids"), list)
            or not all(isinstance(x, str) for x in run["job_ids"])):
        raise ValueError("Ugyldig kørselslog; gendan fra originalen før ændringer")
    return run


def event(phase, evidence, next_action):
    return {"at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "phase": phase, "evidence": required_text(evidence, "Evidens"),
            "next_action": required_text(next_action, "Næste handling")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("id")
    request = start.add_mutually_exclusive_group(required=True)
    request.add_argument("--request")
    request.add_argument("--request-file")
    start.add_argument("--job-id", action="append", default=[])
    start.add_argument("--next-action", required=True)
    note = sub.add_parser("note")
    note.add_argument("id")
    note.add_argument("--phase", choices=PHASES, required=True)
    note.add_argument("--evidence", required=True)
    note.add_argument("--next-action", required=True)
    note.add_argument("--job-id", action="append", default=[])
    resume = sub.add_parser("resume")
    resume.add_argument("id")
    finish = sub.add_parser("finish")
    finish.add_argument("id")
    finish.add_argument("--outcome", choices=("delivered", "no_matches", "blocked"), required=True)
    finish.add_argument("--summary", required=True)
    finish.add_argument("--next-action", required=True)
    finish.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = run_path(root, args.id)
    if args.command == "resume":
        run = read_run(path)
        db = jobflow.load(root)
        jobs = [{"id": job_id, "status_now": jobflow.find(db, job_id)["status"],
                 "diagnose_command": f"python tools/jobflow.py next {job_id}"}
                for job_id in run["job_ids"]]
        print(json.dumps({"run": run, "jobs_from_current_register": jobs,
                          "instruction": "Genlæs AGENTS.md og kør check/next. Loggen er en overlevering, ikke et review eller en indsendelsestilladelse."},
                         ensure_ascii=False, indent=2))
        return 0
    # Same short-lived lock as the register: no interleaved read/modify/write.
    with jobflow.lock(root):
        if args.command == "start":
            if path.exists():
                raise ValueError("Kørslen findes allerede; brug resume/note")
            request_text = args.request
            if args.request_file:
                request_text = jobflow.local_path(root, args.request_file).read_text(encoding="utf-8-sig")
            run = {"schema_version": 1, "id": args.id, "run_state": "open",
                   "request": required_text(request_text, "Bestilling"),
                   "job_ids": job_references(root, args.job_id),
                   "events": [event("orient", "Bestilling gemt; arbejde er endnu ikke verificeret", args.next_action)]}
        else:
            run = read_run(path)
            if run["run_state"] != "open":
                raise ValueError("Kørslen er afsluttet; start et nyt forløb ved nyt arbejde")
            if args.command == "note":
                ids = job_references(root, run["job_ids"] + args.job_id)
                run["events"].append(event(args.phase, args.evidence, args.next_action))
                run["job_ids"] = ids
            else:
                artifacts = list(dict.fromkeys(args.artifact))
                for relative in artifacts:
                    if not jobflow.local_path(root, relative).is_file():
                        raise ValueError(f"Leverancefil findes ikke: {relative}")
                if args.outcome == "delivered" and not artifacts:
                    raise ValueError("En afleveret kørsel skal pege på mindst én eksisterende leverancefil")
                run["events"].append(event("deliver", args.summary, args.next_action))
                run.update(run_state="closed", outcome=args.outcome, artifacts=artifacts)
        jobflow.save_json(path, run)
    print(path.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"FEJL: {error}", file=sys.stderr)
        sys.exit(1)
