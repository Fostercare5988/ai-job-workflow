"""Local job records, validation and Markdown views. No network or submission.

Run with Python 3.10+. All paths are relative to the workspace; stdlib only.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
STATES = {
    "discovered": "Fundet", "drafting": "Under udarbejdelse",
    "needs_review": "Skal gennemgås", "ready": "Klar til gennemlæsning",
    "approved": "Godkendt af ansøgeren", "submitted": "Sendt",
    "interview": "Samtale", "rejected": "Afslag", "withdrawn": "Trukket tilbage",
    "closed": "Opslag lukket", "legacy_submitted": "Søgt ifølge tidligere tracker",
    "legacy_interview": "Samtale ifølge tidligere tracker",
    "legacy_draft": "Ældre udkast, ikke genkontrolleret"
}
TRANSITIONS = {
    "discovered": {"drafting", "needs_review", "closed", "withdrawn"},
    "drafting": {"needs_review", "ready", "closed", "withdrawn"},
    "needs_review": {"drafting", "ready", "closed", "withdrawn"},
    "ready": {"needs_review", "approved", "closed", "withdrawn"},
    "approved": {"needs_review", "submitted", "closed", "withdrawn"},
    "submitted": {"interview", "rejected", "withdrawn"},
    "interview": {"rejected", "withdrawn"},
    "legacy_draft": {"drafting", "needs_review", "closed", "withdrawn", "submitted"},
    "legacy_submitted": {"interview", "rejected", "withdrawn"},
    "legacy_interview": {"rejected", "withdrawn"},
    "closed": {"discovered"}, "withdrawn": set(), "rejected": set()
}
CHECKS = ["posting_and_deadline", "requirements_and_format", "candidate_facts",
          "project_attribution", "job_specific_match", "style_and_language", "all_claims_mapped"]
REQUIRED = ["id", "company", "title", "url", "url_kind", "language", "created_at",
            "status", "requirements", "files", "history"]
ACTIVE_STATES = {"discovered", "drafting", "needs_review", "ready", "approved"}
GENERATED_ROLES = {"delivery": "AFLEVERING.md", "joblog": "JOBLOG.md"}
DOCUMENT_ROLES = {"posting", "match", "cv", "letter", "motivation", "review"}


def today():
    return date.today()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".jobflow-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def save_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


@contextmanager
def lock(root):
    path = root / "Data/.jobflow.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("Registeret er låst af en anden kørsel. Kontrollér processen før en gammel lås fjernes.")
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def local_path(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or re.match(r"^[A-Za-z]:", relative):
        raise ValueError(f"Forventede relativ sti: {relative}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Sti uden for projekt: {relative}")
    return path


def iso(value):
    return date.fromisoformat(value) if value else None


def web_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not any(c.isspace() for c in value)
    except ValueError:
        return False


def normalize_url(url):
    p = urlsplit(url)
    query = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                   if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"})
    # Hash-routed career sites put the actual job identity after '#/'.
    fragment = p.fragment if p.fragment.startswith(("/", "!")) else ""
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(query), fragment))


def normalized(text):
    return re.sub(r"\W+", " ", text.casefold()).strip()


def duplicate(a, b):
    if a["id"] == b["id"]:
        return True
    if a.get("url_kind") == b.get("url_kind") == "direct" and normalize_url(a["url"]) == normalize_url(b["url"]):
        return True
    return normalized(a["company"]) == normalized(b["company"]) and normalized(a["title"]) == normalized(b["title"])


def schema_errors(job):
    if not isinstance(job, dict):
        return ["En sag skal være et objekt"]
    errors = [f"Mangler felt {key}" for key in REQUIRED if key not in job]
    if errors:
        return errors
    if not isinstance(job["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,100}", job["id"]):
        errors.append("ID skal være 3-101 små ASCII-bogstaver, tal eller bindestreger")
    for key in ("company", "title"):
        if not isinstance(job[key], str) or not job[key].strip():
            errors.append(f"Tomt felt {key}")
    if not web_url(job["url"]):
        errors.append("Job-URL mangler")
    if not isinstance(job["status"], str) or job["status"] not in STATES:
        errors.append("Ukendt status")
    if job["url_kind"] not in ("direct", "listing", "unknown"):
        errors.append("Ukendt URL-type")
    if job["language"] not in ("da", "en", "unknown"):
        errors.append("Sprog skal være da, en eller unknown")
    if not isinstance(job["files"], dict) or not isinstance(job["history"], list):
        errors.append("Ugyldigt files/history format")
    elif any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() for k, v in job["files"].items()):
        errors.append("Dokumentnavne og filstier skal være tekst")
    if not isinstance(job["requirements"], dict) or job["requirements"].get("format") not in ("cover_letter", "cv_only", "short_motivation", "unknown"):
        errors.append("Ugyldigt dokumentformat")
    elif job["requirements"].get("max_words") is not None:
        limit = job["requirements"]["max_words"]
        if type(limit) is not int or limit < 1:
            errors.append("Ordgrænse skal være et positivt heltal")
    if isinstance(job["requirements"], dict):
        for key in ("no_photo", "no_age"):
            if key in job["requirements"] and type(job["requirements"][key]) is not bool:
                errors.append(f"Dokumentkravet {key} skal være true eller false")
    selected = job.get("selected_sources", [])
    if not isinstance(selected, list) or any(not isinstance(sid, str) or not sid.strip() for sid in selected):
        errors.append("selected_sources skal være en liste af kilde-id'er")
    for key in ("submission", "joblog", "legacy"):
        if job.get(key) is not None and not isinstance(job[key], dict):
            errors.append(f"{key} skal være et objekt eller null")
    joblog_form = job.get("joblog_form")
    if joblog_form is not None:
        if not isinstance(joblog_form, dict):
            errors.append("joblog_form skal være et objekt")
        else:
            if joblog_form.get("postcode") and not re.fullmatch(r"\d{4}", str(joblog_form["postcode"])):
                errors.append("Joblog-postnummer skal være fire cifre")
            if joblog_form.get("posting_url") and not web_url(joblog_form["posting_url"]):
                errors.append("Joblog-opslagslink skal være en webadresse")
            for key in ("address", "country", "city", "contact_person", "email", "phone", "source_note"):
                if joblog_form.get(key) is not None and not isinstance(joblog_form[key], str):
                    errors.append(f"Joblog-{key} skal være tekst eller null")
            sources = joblog_form.get("sources", [])
            if not isinstance(sources, list) or any(not isinstance(source, dict) or not isinstance(source.get("label"), str) or not source["label"].strip() or not web_url(source.get("url")) for source in sources):
                errors.append("Joblog-kilder skal have label og webadresse")
    for key in ("created_at", "deadline", "posting_checked_at", "follow_up_on"):
        if job.get(key):
            try:
                iso(job[key])
            except (ValueError, TypeError):
                errors.append(f"Ugyldig ISO-dato i {key}")
    if not job.get("created_at"):
        errors.append("Oprettelsesdato mangler")
    for key in ("submission", "joblog"):
        record = job.get(key)
        if isinstance(record, dict) and record.get("date"):
            try:
                iso(record["date"])
            except (ValueError, TypeError):
                errors.append(f"Ugyldig ISO-dato i {key}.date")
    return errors


def load(root):
    db = read_json(root / "Data/jobs.json")
    if not isinstance(db, dict) or db.get("schema_version") != 1 or not isinstance(db.get("jobs"), list):
        raise ValueError("Ugyldigt registerformat")
    ids = set()
    for job in db["jobs"]:
        errors = schema_errors(job)
        if not errors:
            errors = artifact_path_errors(root, job)
        if errors:
            raise ValueError(f"{job.get('id') if isinstance(job, dict) else 'Ukendt sag'}: {'; '.join(errors)}")
        if job["id"] in ids:
            raise ValueError("Dubleret ID")
        ids.add(job["id"])
    return db


def find(db, job_id):
    for job in db["jobs"]:
        if job["id"] == job_id:
            return job
    raise ValueError(f"Ukendt sag: {job_id}")


def hashes(root, job):
    result = {}
    reviewed_files = {}
    generated = generated_paths(root, job)
    for key, relative in job["files"].items():
        path = local_path(root, relative)
        if key == "review" or generated.get(key) == path:
            continue
        reviewed_files[key] = relative
        if path.is_file():
            result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in ("Profil/fakta.json", "Profil/projekter.json", "System/SKRIVESTIL.md"):
        path = local_path(root, relative)
        if path.is_file():
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = {k: job.get(k) for k in ("company", "title", "url", "url_kind", "deadline", "deadline_note", "language", "posting_checked_at", "posting_status", "requirements", "selected_sources", "files", "joblog_form")}
    context["files"] = reviewed_files
    result["job_context"] = hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def generated_paths(root, job):
    folder = root / "Ansoegninger_Aktive" / job["id"]
    return {role: (folder / name).resolve() for role, name in GENERATED_ROLES.items()}


def artifact_path_errors(root, job):
    errors = []
    generated = set(generated_paths(root, job).values())
    for key, relative in job["files"].items():
        try:
            path = local_path(root, relative)
            if key in DOCUMENT_ROLES and path in generated:
                errors.append(f"Dokumentrollen {key} må ikke pege på en genereret sagsside: {relative}")
        except ValueError as ex:
            errors.append(str(ex))
    return errors


def source_registry(root):
    facts = read_json(root / "Profil/fakta.json")["facts"]
    projects = read_json(root / "Profil/projekter.json")["projects"]
    return {x["id"]: x for x in facts + projects}


def submission_errors(job, as_of=None):
    as_of = as_of or today()
    record = job.get("submission") or {}
    errors = []
    try:
        sent = iso(record.get("date"))
        if not sent or sent > as_of:
            errors.append("Sendt kræver en faktisk, ikke fremtidig dato")
    except (ValueError, TypeError):
        errors.append("Ugyldig afsendelsesdato")
    if not isinstance(record.get("evidence"), str) or not record["evidence"].strip():
        errors.append("Sendt kræver kvittering eller ansøgerens udtrykkelige besked som grundlag")
    return errors


def validate(root, job, as_of=None):
    as_of = as_of or today()
    errors = schema_errors(job)
    if not errors:
        errors = artifact_path_errors(root, job)
    if errors:
        return errors
    if job.get("posting_status") != "open" or job.get("url_kind") != "direct":
        errors.append("Et åbent konkret opslag skal være kontrolleret")
    checked = iso(job.get("posting_checked_at"))
    if not checked or not 0 <= (as_of - checked).days <= 3:
        errors.append("Opslag skal være kontrolleret inden for tre dage")
    deadline = iso(job.get("deadline"))
    if deadline and deadline < as_of:
        errors.append("Ansøgningsfrist er passeret")
    if not deadline and (not isinstance(job.get("deadline_note"), str) or not job["deadline_note"].strip()):
        errors.append("Manglende forklaring på ukendt frist")
    if job["language"] == "unknown":
        errors.append("Sprog skal være afklaret")
    info = job.get("joblog_form") or {}
    if not info.get("postcode") or not (info.get("city") or "").strip():
        errors.append("Joblog kræver særskilt postnummer og by i joblog_form")
    if not info.get("sources"):
        errors.append("Joblog mangler kilder til adresse og kontakt (uoplyste felter forklares i source_note)")
    fmt = job["requirements"].get("format")
    needed = {"posting", "match", "cv", "review"}
    if fmt == "cover_letter":
        needed.add("letter")
    elif fmt == "short_motivation":
        needed.add("motivation")
    elif fmt != "cv_only":
        errors.append("Dokumentkrav skal være afklaret")
    for key in needed:
        if key not in job["files"]:
            errors.append(f"Mangler dokument: {key}")
    for key, relative in job["files"].items():
        try:
            path = local_path(root, relative)
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"Manglende/tom fil: {relative}")
                continue
            if key not in {"cv", "letter", "motivation"}:
                continue
            content = path.read_text(encoding="utf-8-sig")
            if re.search(r"\b(?:TODO|TBD|INDSÆT|PLACEHOLDER)\b|\{\{.*?\}\}", content, re.I):
                errors.append(f"Udfyld pladsholdere i {key}")
            if job["requirements"].get("no_photo") and re.search(r"<img\b|!\[.*?\]\(", content, re.I):
                errors.append(f"Foto/billede ikke tilladt i {key}")
            if job["requirements"].get("no_age") and re.search(r"\b(?:jeg er\s+)?\d{2}\s*(?:år(?: gammel)?|years old)\b|fødselsdato|date of birth", content, re.I):
                errors.append(f"Alder/fødselsdato i {key}")
            if key in {"letter", "motivation"}:
                if "—" in content or "–" in content or "**" in content:
                    errors.append(f"Ret tankestreger/fed skrift i {key}")
                limit = job["requirements"].get("max_words")
                if limit and len(content.split()) > limit:
                    errors.append(f"{key} overskrider ordgrænsen {limit}")
        except (ValueError, OSError, UnicodeError) as ex:
            errors.append(str(ex))
    registry = source_registry(root)
    selected = job.get("selected_sources", [])
    if not selected:
        errors.append("Ingen erfarings-/projektkilder valgt")
    for sid in selected:
        if sid not in registry or registry[sid].get("external_use") is False:
            errors.append(f"Ukendt eller intern kilde: {sid}")
    review_path = job["files"].get("review")
    if review_path:
        try:
            review = read_json(local_path(root, review_path))
            if not isinstance(review, dict):
                raise ValueError("Review skal være et objekt")
            if not isinstance(review.get("reviewed_by"), str) or not review["reviewed_by"].strip():
                errors.append("Reviewer mangler")
            reviewed = iso(review.get("reviewed_at"))
            if not reviewed or not 0 <= (as_of - reviewed).days <= 3:
                errors.append("Reviewdato mangler eller er forældet")
            checks = review.get("checks")
            if not isinstance(checks, dict):
                checks = {}
                errors.append("Review-checks skal være et objekt")
            for check in CHECKS:
                if checks.get(check) is not True:
                    errors.append(f"Reviewer har ikke bestået: {check}")
            claims = review.get("claims", [])
            if not isinstance(claims, list):
                errors.append("Review-claims skal være en liste")
                claims = []
            if not claims:
                errors.append("Ingen påstande kortlagt i review")
            for claim in claims:
                if not isinstance(claim, dict):
                    errors.append("En påstand skal være et objekt")
                    continue
                source_ids = claim.get("source_ids")
                if not isinstance(claim.get("text"), str) or not claim["text"].strip() or not isinstance(source_ids, list) or not source_ids:
                    errors.append("Påstand mangler tekst eller kilde")
                for sid in source_ids if isinstance(source_ids, list) else []:
                    if not isinstance(sid, str) or sid not in registry or registry[sid].get("external_use") is False:
                        errors.append(f"Påstand bruger ukendt/intern kilde: {sid}")
            if review.get("artifact_hashes") != hashes(root, job):
                errors.append("Review matcher ikke de aktuelle filer/jobfakta; gennemgå igen")
        except (ValueError, OSError, TypeError, UnicodeError) as ex:
            errors.append(f"Review kan ikke læses: {ex}")
    return errors


def cell(value):
    return str(value if value not in (None, "") else "Ikke oplyst").replace("|", " / ").replace("\n", " ")


def joblog_text(root, job, folder):
    info = job.get("joblog_form") or {}
    old_city = job.get("city") or ""
    match = re.fullmatch(r"(\d{4})\s+(.+)", old_city)
    postcode = info.get("postcode") or (match.group(1) if match else None)
    city = info.get("city") or (match.group(2) if match else old_city or None)
    fields = [
        ("Stilling*", job["title"]),
        ("Link til stillingsopslag", info.get("posting_url") or job["url"]),
        ("Virksomhed*", job["company"]),
        ("Adresse", info.get("address") or job.get("address")),
        ("Land", info.get("country")),
        ("Postnr.*", postcode),
        ("By*", city),
        ("Kontaktperson", info.get("contact_person") or job.get("contact")),
        ("E-mail", info.get("email")),
        ("Tlf.", info.get("phone")),
    ]
    lines = [f"# Joblog: {job['title']}", "", "Kopiér felterne til Joblog. Stjerne (*) betyder, at Joblog kræver feltet.", ""]
    lines += [f"- {label}: {cell(value)}" for label, value in fields]
    application = job["files"].get("letter") or job["files"].get("motivation")
    lines += ["", f"- Ansøgning/motivation: {file_link(root, application, folder) if application else 'Ikke påkrævet'}",
              f"- CV: {file_link(root, job['files']['cv'], folder) if job['files'].get('cv') else 'Ikke oplyst'}",
              f"- Sendt til arbejdsgiver: {cell((job.get('submission') or {}).get('date'))}",
              f"- Registreret i Joblog: {cell((job.get('joblog') or {}).get('date'))}", ""]
    if info.get("source_note"):
        lines += [f"Adresse- og kontaktnote: {info['source_note']}", ""]
    for source in info.get("sources", []):
        lines.append(f"- Kilde: [{source['label']}]({source['url']})")
    lines += ["", "Denne fil er et overførselsgrundlag; den opretter ikke en post i Joblog.", ""]
    return "\n".join(lines)


def file_link(root, relative, from_dir, label=None):
    path = local_path(root, relative)
    if not path.is_file():
        return f"Mangler: `{relative}`"
    target = os.path.relpath(path, from_dir).replace("\\", "/")
    return f"[{label or path.name}](<{target}>)"


def display_status(root, job, issues=None):
    label = STATES[job["status"]]
    if job["status"] in {"ready", "approved"} and (validate(root, job) if issues is None else issues):
        return "Skal genkontrolleres (ændret eller forældet)"
    if job["status"] in {"legacy_draft", "needs_review", "drafting", "discovered"} and job.get("deadline") and iso(job["deadline"]) < today():
        return label + "; registreret frist passeret"
    return label


def diagnose(root, job, as_of=None):
    """Derive the next action without changing the job or producing files."""
    as_of = as_of or today()
    status = job["status"]
    issues = validate(root, job, as_of) if status in ACTIVE_STATES else []
    if status in ACTIVE_STATES:
        deadline = iso(job.get("deadline"))
        if deadline and deadline < as_of:
            action = "Afklar om ansøgningen faktisk blev sendt; ellers luk sagen og bevar historikken"
        elif any("opslag" in issue.lower() for issue in issues):
            action = "Genkontrollér det konkrete opslag, frist og dokumentkrav før videre arbejde"
        elif any("Mangler dokument" in issue or "Manglende/tom fil" in issue for issue in issues):
            action = "Færdiggør de manglende dokumenter og det målrettede CV, og gennemgå pakken"
        elif issues:
            action = "Ret de konkrete kontrolpunkter, gennemgå kilder og dokumenter, og kør validate igen"
        elif status == "ready":
            action = "Ansøgeren gennemlæser jobpakken"
        elif status == "approved":
            action = "Eksportér/indsend efter den givne instruktion; registrér kun sendt med faktisk dokumentation"
        else:
            action = "Pakken består filkontrollen; gennemgå dokumenter og kilder, før pakken markeres klar"
    elif status == "submitted":
        issues.extend(submission_errors(job, as_of))
        follow_up = iso(job.get("follow_up_on"))
        action = "Afklar dokumentation og dato for afsendelsen" if issues else "Følg op på den indsendte ansøgning" if follow_up and follow_up <= as_of else "Afvent svar"
        if follow_up and follow_up > as_of:
            action += f"; opfølgning {follow_up.isoformat()}"
    elif status == "interview":
        action = "Forbered den aftalte samtale; bevar ansøgnings- og afsendelseshistorik"
    elif status == "legacy_interview":
        action = "Historikken nævner en samtale; afklar kun ved relevant opfølgning, og undgå genansøgning"
    elif status == "legacy_submitted":
        action = "Bevar som tidligere søgt; afklar kun historikken ved relevant opfølgning"
    else:
        action = "Bevar historikken; ingen genansøgning til samme opslag"
    return {"id": job["id"], "status": status, "issues": issues, "next_action": action}


def next_cases(root, db, as_of=None):
    as_of = as_of or today()
    results = [(job, diagnose(root, job, as_of)) for job in db["jobs"]]

    def order(item):
        job, diagnosis = item
        follow_up = iso(job.get("follow_up_on"))
        if job["status"] in ACTIVE_STATES:
            priority = 0 if diagnosis["issues"] else 1
        elif job["status"] == "submitted" and follow_up and follow_up <= as_of:
            priority = 2
        elif job["status"] == "interview":
            priority = 3
        elif job["status"] == "submitted":
            priority = 4
        else:
            priority = 5
        return priority, job.get("deadline") or "9999-12-31", job["id"]

    return [diagnosis for _, diagnosis in sorted(results, key=order)]


def render(root, db):
    jobs = sorted(db["jobs"], key=lambda j: (j["created_at"], j["id"]), reverse=True)
    active = [j for j in jobs if j["status"] in ACTIVE_STATES]
    diagnoses = {j["id"]: diagnose(root, j) for j in jobs}
    header = f"# Jobsøgningsoverblik\n\nGenereret fra `Data/jobs.json` den {today().isoformat()}. Assistenten vedligeholder registeret.\n\n"
    table = "| Virksomhed og stilling | Frist | Status | Næste handling |\n| --- | --- | --- | --- |\n"
    for j in active:
        packet = f"Ansoegninger_Aktive/{j['id']}/AFLEVERING.md"
        diagnosis = diagnoses[j["id"]]
        table += f"| [{cell(j['company'])}: {cell(j['title'])}](<{packet}>) | {cell(j.get('deadline') or j.get('deadline_note'))} | {display_status(root,j,diagnosis['issues'])} | {cell(diagnosis['next_action'])} |\n"
    if not active:
        table += "| Ingen aktive pakker | | | Skriv: Find to AI-jobs og ansøg dem |\n"
    tracker = header + "## Aktive sager\n\n" + table
    submitted = sorted((j for j in jobs if (j.get("submission") or {}).get("date")),
                       key=lambda j: (j["submission"]["date"], j["created_at"], j["id"]), reverse=True)
    current = header + "## Aktive ansøgninger\n\n" + table
    current += "\n## Senest faktisk indsendt\n\n"
    if submitted:
        for j in submitted[:10]:
            packet = f"Ansoegninger_Aktive/{j['id']}/AFLEVERING.md"
            sent_on = (j.get("submission") or {}).get("date") or "dato mangler"
            current += f"- [{j['company']}: {j['title']}](<{packet}>) — {sent_on}\n"
    else:
        current += "Ingen af de aktive ansøgninger er registreret som faktisk indsendt.\n"
    current += "\nEn dato i Joblog er ikke dokumentation for, at arbejdsgiveren har modtaget ansøgningen. Status `sendt` kræver en kvittering eller ansøgerens udtrykkelige besked.\n"
    tracker += "\n## Historik og jobloggrundlag\n\n"
    if db.get("demo_only"):
        tracker += "Alle sager og statusoplysninger i denne demo er fiktive. Ingen historik er importeret fra en rigtig tracker, og intet er registreret i ekstern Jobnet/Joblog.\n\n"
    else:
        tracker += "Historiske statusser er importeret fra den tidligere tracker. Ekstern Jobnet/Joblog er ikke genkontrolleret.\n\n"
    latest = "# Seneste aktive jobpakker\n\nGenereret fra det fælles register. En gammel agentgodkendelse er ikke en ny kvalitetskontrol.\n\n"
    for j in jobs:
        folder = root / "Ansoegninger_Aktive" / j["id"]
        if not folder.is_dir():
            if j not in active:
                continue
            folder.mkdir(parents=True)
        atomic_write(folder / "JOBLOG.md", joblog_text(root, j, folder))
        diagnosis = diagnoses[j["id"]]
        packet = f"# {j['company']}\n\n{j['title']}\n\nStatus: {display_status(root,j,diagnosis['issues'])}\n\nFrist: {j.get('deadline') or j.get('deadline_note') or 'Ikke oplyst'}\n\n[Jobopslag]({j['url']})\n\nNæste handling: {diagnosis['next_action']}\n\n## Dokumenter\n\n"
        for key, relative in j["files"].items():
            packet += f"- {key}: {file_link(root,relative,folder)}\n"
        if diagnosis["issues"]:
            packet += "\n## Kontrolpunkter før videre arbejde\n\n" + "".join(f"- {issue}\n" for issue in diagnosis["issues"])
        packet += "\n## Joblog\n\n[Felter til Joblog](<JOBLOG.md>)\n\n"
        packet += "Faktisk afsendelse: " + cell((j.get("submission") or {}).get("date")) + "\n\nDenne fil registrerer ikke noget i Joblog.\n"
        atomic_write(folder / "AFLEVERING.md", packet)
        if j in active:
            latest += f"- [{j['company']}: {j['title']}](<../Ansoegninger_Aktive/{j['id']}/AFLEVERING.md>) · {cell(j.get('deadline'))} · {display_status(root,j)}\n"
    for j in jobs:
        tracker += f"### {j['company']}: {j['title']}\n\n"
        for key, field in [("ID","id"),("Adresse","address"),("Postnr/by","city"),("Kontaktperson","contact"),("Sprog","language"),("Udarbejdet","created_at")]:
            tracker += f"- {key}: {cell(j.get(field))}\n"
        tracker += f"- Opslag: [{j['url']}]({j['url']})\n- Frist: {cell(j.get('deadline') or j.get('deadline_note'))}\n- Status: {display_status(root,j)}\n"
        if j.get("legacy"):
            tracker += f"- Oprindelig status: {cell(j['legacy'].get('status_text'))}\n"
        for relative in j["files"].values():
            tracker += f"- Fil: {file_link(root,relative,root)}\n"
        if j.get("submission"):
            tracker += f"- Afsendelsesoplysning: {cell(j['submission'])}\n"
        if j.get("joblog"):
            tracker += f"- Joblogdato: {cell(j['joblog'].get('date'))} (registreret, ikke dokumentation for afsendelse)\n"
        tracker += "\n"
    atomic_write(root / "Jobsøgning_Tracker.md", tracker)
    atomic_write(root / "AKTUEL_STATUS.md", current)
    atomic_write(root / "Ansøgninger/_SENESTE_UDKAST.md", latest)
    projects = read_json(root / "Profil/projekter.json")["projects"]
    catalog = "# Projektbank\n\nGenereret fra `projekter.json`. Kontrolniveau, kilder og begrænsninger er angivet for hvert projekt. En kildehenvisning dokumenterer ikke i sig selv en testkørsel.\n\n"
    for p in projects:
        catalog += f"## {p['name']} ({p['id']})\n\n{p['summary']}\n\n- Anvendelse: {', '.join(p['tags'])}\n- Kontrolniveau: {p['evidence_level']}\n- Ekstern brug: {'ja' if p['external_use'] else 'nej'}\n- Formulering: {p['safe_claim_da']}\n- Begrænsning: {p['limitations']}\n"
        for s in p["sources"]:
            label = s.get("label") or "Kilde uden navn"
            if web_url(s.get("url")):
                catalog += f"- Kilde: [{label}]({s['url']})\n"
            elif s.get("snapshot"):
                catalog += f"- Lokal kilde: {file_link(root, s['snapshot'], root / 'Profil', label)}\n"
            else:
                catalog += f"- Kilde: {label} (mangler gyldig webadresse eller lokalt snapshot)\n"
        catalog += "\n"
    atomic_write(root / "Profil/PROJEKTER.md", catalog)


def check(root, db):
    errors, warnings = [], []
    facts = read_json(root / "Profil/fakta.json")["facts"]
    projects = read_json(root / "Profil/projekter.json")["projects"]
    source_ids = [s["id"] for s in facts + projects]
    if len(source_ids) != len(set(source_ids)):
        errors.append("Dublerede kilde-id'er i fakta-/projektregister")
    for fact in facts:
        if fact.get("source") and not local_path(root, fact["source"]).is_file():
            errors.append(f"Faktakilde mangler: {fact['source']}")
    for project in projects:
        for source in project.get("sources", []):
            if source.get("snapshot") and not local_path(root, source["snapshot"]).is_file():
                errors.append(f"Projektsnapshot mangler: {source['snapshot']}")
    jobs = db["jobs"]
    for i, j in enumerate(jobs):
        for other in jobs[:i]:
            if duplicate(j, other):
                warnings.append(f"Mulig dublet: {j['id']} / {other['id']}")
        for relative in j["files"].values():
            try:
                if not local_path(root, relative).is_file():
                    (warnings if j.get("legacy") else errors).append(f"{j['id']}: fil mangler: {relative}")
            except ValueError as ex:
                errors.append(str(ex))
        if j["status"] in {"ready", "approved"}:
            errors.extend(f"{j['id']}: {e}" for e in validate(root, j))
        if j["status"] == "submitted":
            errors.extend(f"{j['id']}: {issue}" for issue in submission_errors(j))
        if j.get("deadline") and iso(j["deadline"]) < today() and j["status"] in {"legacy_draft", "drafting", "needs_review", "ready", "approved"}:
            warnings.append(f"{j['id']}: registreret frist passeret; afklar før genbrug")
    inv = read_json(root / "Profil/Kilder/github_inventory.json")
    try:
        inventory_date = iso(inv.get("checked_at"))
    except (ValueError, TypeError):
        inventory_date = None
    if not inventory_date or inventory_date > today():
        errors.append("GitHub-inventaret mangler en faktisk kontroldato")
    elif (today() - inventory_date).days > 7:
        warnings.append("GitHub-grundlaget er over syv dage gammelt; opdatér før nye ansøgninger")
    report = {"checked_at": today().isoformat(), "jobs": len(jobs), "errors": errors, "warnings": warnings}
    save_json(root / "Data/kontrol.json", report)
    atomic_write(root / "System/KONTROL.md", "# Seneste registerkontrol\n\n" + f"{report['checked_at']}: {len(jobs)} sager, {len(errors)} fejl og {len(warnings)} opmærksomhedspunkter.\n\n" + "\n".join(f"- FEJL: {x}" for x in errors) + "\n" + "\n".join(f"- OBS: {x}" for x in warnings) + "\n\nDette er fil- og registerkontrol, ikke et automatisk semantisk faktatjek.\n")
    return report


def change_status(root, job, target, evidence, submitted_on=None, as_of=None):
    as_of = as_of or today()
    if not evidence or not evidence.strip():
        raise ValueError("Angiv grundlag med --evidence")
    if target not in TRANSITIONS.get(job["status"], set()):
        raise ValueError(f"Ugyldig overgang: {job['status']} -> {target}")
    if target in {"ready", "approved"} or (target == "submitted" and job["status"] != "legacy_draft"):
        errors = validate(root, job, as_of)
        if errors:
            raise ValueError("; ".join(errors))
    if target == "submitted":
        sent = iso(submitted_on)
        if not sent or sent > as_of:
            raise ValueError("Sendt kræver en faktisk, ikke fremtidig dato med --date")
        job["submission"] = {"date": submitted_on, "evidence": evidence}
    job["history"].append({"at": datetime.now().isoformat(timespec="seconds"), "from": job["status"], "to": target, "evidence": evidence})
    job["status"] = target
    job["next_action"] = {"ready": "Ansøgeren gennemlæser jobpakken", "approved": "Eksportér/indsend efter den givne instruktion", "submitted": "Afvent svar", "interview": "Forbered samtale", "rejected": "Registrér eventuel feedback"}.get(target, "Se sagens noter")


def correct_status(root, job, target, evidence, submitted_on=None, as_of=None, clear_submission=False):
    """Record a factual correction, including late registration of actual submission."""
    as_of = as_of or today()
    if not evidence or not evidence.strip():
        raise ValueError("Angiv grundlag med --evidence")
    if target not in STATES:
        raise ValueError("Ukendt status")
    if clear_submission and target not in ACTIVE_STATES | {"closed", "withdrawn", "legacy_draft"}:
        raise ValueError("--clear-submission kræver en arbejds- eller lukkestatus; en søgt sag bevarer afsendelsen")
    if target in {"ready", "approved"}:
        errors = validate(root, job, as_of)
        if errors:
            raise ValueError("; ".join(errors))
    if target == "submitted":
        sent = iso(submitted_on)
        if not sent or sent > as_of:
            raise ValueError("Historisk afsendelse kræver faktisk dato med --date og dokumenteret grundlag")
        job["submission"] = {"date": submitted_on, "evidence": evidence}
    previous = job["status"]
    event = {"at": datetime.now().isoformat(timespec="seconds"), "from": previous,
             "to": target, "evidence": f"Statuskorrektion: {evidence}"}
    if clear_submission:
        event["cleared_submission"] = deepcopy(job.get("submission"))
        job["submission"] = None
    job["history"].append(event)
    job["status"] = target
    job["next_action"] = diagnose(root, job, as_of)["next_action"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "render", "list"):
        sub.add_parser(command)
    sub.add_parser("next", help="Read-only JSON: prioriterede sager, kontrolpunkter og næste handling").add_argument("id", nargs="?")
    for command in ("validate", "fingerprints"):
        sub.add_parser(command).add_argument("id")
    for command in ("add", "upsert"):
        sub.add_parser(command).add_argument("input", type=Path)
    delete = sub.add_parser("delete")
    delete.add_argument("id", nargs="+")
    delete.add_argument("--evidence", required=True)
    correction = sub.add_parser("correct-status")
    correction.add_argument("id")
    correction.add_argument("target", choices=STATES)
    correction.add_argument("--evidence", required=True)
    correction.add_argument("--date", help="Faktisk dato ved korrektion til submitted")
    correction.add_argument("--clear-submission", action="store_true",
                            help="Tilbagekald fejlagtig afsendelse ved korrektion til arbejds-/lukkestatus; bevar den i historikken")
    joblog = sub.add_parser("joblog")
    joblog.add_argument("id")
    joblog.add_argument("date")
    joblog.add_argument("--evidence", required=True)
    status = sub.add_parser("status")
    status.add_argument("id")
    status.add_argument("target", choices=STATES)
    status.add_argument("--evidence", required=True)
    status.add_argument("--date")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "next":
        db = load(root)
        result = diagnose(root, find(db, args.id)) if args.id else next_cases(root, db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    with lock(root):
        db = load(root)
        if args.command == "list":
            print("\n".join(f"{j['id']} | {display_status(root,j)} | {j['company']}" for j in db["jobs"]))
        elif args.command == "fingerprints":
            print(json.dumps(hashes(root, find(db, args.id)), indent=2))
        elif args.command == "validate":
            errors = validate(root, find(db, args.id))
            print("\n".join(errors) if errors else "PASS: dokumenter, kildehenvisninger og review er konsistente; fakta er reviewerens vurdering.")
            return 1 if errors else 0
        elif args.command == "check":
            print(json.dumps(check(root, db), ensure_ascii=False, indent=2))
            return 1 if read_json(root / "Data/kontrol.json")["errors"] else 0
        elif args.command == "render":
            render(root, db)
            print("Overblik, afleveringer og projektbank opdateret.")
        elif args.command == "delete":
            raise ValueError("Sager slettes ikke: bevar historik og dubletgrundlag. Brug status closed/withdrawn med grundlag.")
        elif args.command == "correct-status":
            job = find(db, args.id)
            previous = job["status"]
            correct_status(root, job, args.target, args.evidence, args.date, clear_submission=args.clear_submission)
            save_json(root / "Data/jobs.json", db)
            render(root, db)
            print(f"Status korrigeret: {args.id} {previous} -> {args.target}")
        elif args.command == "joblog":
            job = find(db, args.id)
            logged_on = iso(args.date)
            if not logged_on or logged_on > today() or not args.evidence.strip():
                raise ValueError("Joblog kræver faktisk dato og grundlag")
            job["joblog"] = {
                "date": args.date,
                "registered": True,
                "evidence": args.evidence,
            }
            save_json(root / "Data/jobs.json", db)
            render(root, db)
            print(f"Joblog registreret: {args.id} -> {args.date}")
        elif args.command in {"add", "upsert"}:
            job = read_json(args.input)
            errors = schema_errors(job)
            if not errors:
                errors = artifact_path_errors(root, job)
            if errors:
                raise ValueError("; ".join(errors))
            existing = next((j for j in db["jobs"] if j["id"] == job["id"]), None)
            if existing and args.command == "add":
                raise ValueError("Sags-ID findes allerede")
            if args.command == "upsert" and not existing:
                raise ValueError("Brug add til nye sager")
            for other in db["jobs"]:
                if other["id"] != job["id"] and duplicate(job, other):
                    raise ValueError(f"Dublet af {other['id']}; fortsæt den eksisterende sag")
            if existing:
                if job["status"] != existing["status"] or job.get("submission") != existing.get("submission") or job["history"] != existing["history"]:
                    raise ValueError("Brug status-kommandoen til status, historik og afsendelse")
                if job.get("joblog") != existing.get("joblog"):
                    raise ValueError("Brug joblog-kommandoen til ekstern Joblog-registrering")
                db["jobs"][db["jobs"].index(existing)] = job
            else:
                if job["status"] != "discovered" or job.get("submission") or job["history"]:
                    raise ValueError("Ny sag skal starte som discovered uden indsendelse/historik")
                db["jobs"].append(job)
            save_json(root / "Data/jobs.json", db)
            render(root, db)
            print(f"Gemt: {job['id']}")
        elif args.command == "status":
            change_status(root, find(db, args.id), args.target, args.evidence, args.date)
            save_json(root / "Data/jobs.json", db)
            render(root, db)
            print(f"Status opdateret: {args.id} -> {args.target}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"FEJL: {error}", file=sys.stderr)
        sys.exit(1)
