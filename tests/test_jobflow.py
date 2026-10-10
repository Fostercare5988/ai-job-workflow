import copy
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

SPEC = importlib.util.spec_from_file_location("jobflow", Path(__file__).resolve().parents[1] / "tools/jobflow.py")
flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flow)


class JobflowTests(unittest.TestCase):
    def setUp(self):
        # Keep fixtures inside the workspace so sandboxed Windows runs can write them.
        test_dir = Path(__file__).resolve().parent
        self.tmp = tempfile.TemporaryDirectory(prefix=".jobflow-test-", dir=test_dir)
        self.assertTrue(Path(self.tmp.name).resolve().is_relative_to(test_dir))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = date.today()
        self.job = {
            "id": "demo-test-1", "company": "Eksempel", "title": "AI Developer",
            "url": "https://example.org/jobs/123?utm_source=test", "url_kind": "direct",
            "language": "da", "created_at": self.now.isoformat(), "deadline": self.now.isoformat(),
            "deadline_note": "I dag", "posting_checked_at": self.now.isoformat(), "posting_status": "open",
            "requirements": {"format": "cv_only", "no_photo": True, "no_age": True},
            "status": "needs_review", "history": [], "submission": None,
            "joblog_form": {"postcode": "2400", "city": "København NV", "sources": [
                {"label": "Arbejdsgiverens kontaktoplysninger", "url": "https://example.org/contact"}]},
            "files": {k: f"packet/{k}.md" for k in ("posting", "match", "cv")},
            "selected_sources": ["FACT-EDU"]
        }
        self.job["files"]["review"] = "packet/review.json"
        for key in ("posting", "match", "cv"):
            flow.atomic_write(self.root / self.job["files"][key], "Konkret eksempel uden pladsholdere.\n")
        flow.save_json(self.root / "Profil/fakta.json", {"facts": [{"id": "FACT-EDU", "external_use": True}]})
        flow.save_json(self.root / "Profil/projekter.json", {"projects": [{"id": "PRIVATE", "external_use": False}]})
        flow.atomic_write(self.root / "System/SKRIVESTIL.md", "Stilregler")
        self.review = {"reviewed_by": "Testreviewer", "reviewed_at": self.now.isoformat(),
                       "checks": {k: True for k in flow.CHECKS},
                       "claims": [{"text": "Uddannelsesoplysning", "source_ids": ["FACT-EDU"]}],
                       "artifact_hashes": flow.hashes(self.root, self.job)}
        self.save_review()

    def save_review(self):
        flow.save_json(self.root / "packet/review.json", self.review)

    def test_complete_cv_only_packet_passes(self):
        self.assertEqual([], flow.validate(self.root, self.job))

    def test_document_change_invalidates_review(self):
        flow.atomic_write(self.root / "packet/cv.md", "Ændret CV")
        self.assertTrue(any("matcher ikke" in e for e in flow.validate(self.root, self.job)))

    def test_generated_views_do_not_invalidate_their_own_review(self):
        flow.save_json(self.root / "Profil/projekter.json", {"projects": []})
        folder = self.root / "Ansoegninger_Aktive" / self.job["id"]
        folder.mkdir(parents=True)
        for key, name in (("delivery", "AFLEVERING.md"), ("joblog", "JOBLOG.md")):
            path = folder / name
            flow.atomic_write(path, "Før generering")
            self.job["files"][key] = str(path.relative_to(self.root)).replace("\\", "/")
        self.review["artifact_hashes"] = flow.hashes(self.root, self.job)
        self.save_review()
        flow.render(self.root, {"jobs": [self.job]})
        self.assertEqual([], flow.validate(self.root, self.job))
        flow.render(self.root, {"jobs": [self.job]})
        self.assertEqual(self.review["artifact_hashes"], flow.hashes(self.root, self.job))

    def test_document_named_joblog_still_requires_fresh_review(self):
        self.job["files"]["cv"] = "packet/JOBLOG.md"
        flow.atomic_write(self.root / "packet/JOBLOG.md", "Målrettet CV")
        self.review["artifact_hashes"] = flow.hashes(self.root, self.job)
        self.save_review()
        self.assertEqual([], flow.validate(self.root, self.job))
        flow.atomic_write(self.root / "packet/JOBLOG.md", "Ændret CV efter review")
        self.assertTrue(any("matcher ikke" in e for e in flow.validate(self.root, self.job)))

    def test_required_documents_cannot_use_generated_case_pages(self):
        generated = f"Ansoegninger_Aktive/{self.job['id']}/AFLEVERING.md"
        flow.atomic_write(self.root / generated, "Genereret oversigt")
        for role in ("posting", "match", "cv", "letter", "motivation", "review"):
            with self.subTest(role=role):
                job = copy.deepcopy(self.job)
                job["files"][role] = generated
                self.assertTrue(any(f"Dokumentrollen {role}" in e for e in flow.validate(self.root, job)))

    def test_add_rejects_generated_cv_path_before_render_can_overwrite_document(self):
        self.job["status"] = "discovered"
        relative = f"Ansoegninger_Aktive/{self.job['id']}/JOBLOG.md"
        self.job["files"]["cv"] = relative
        flow.atomic_write(self.root / relative, "CV som skal bevares")
        flow.save_json(self.root / "Data/jobs.json", {"schema_version": 1, "jobs": []})
        input_path = self.root / "input.json"
        flow.save_json(input_path, self.job)
        with self.assertRaisesRegex(ValueError, "Dokumentrollen cv"):
            flow.main(["--root", str(self.root), "add", str(input_path)])
        self.assertEqual("CV som skal bevares", (self.root / relative).read_text(encoding="utf-8"))
        self.assertEqual([], flow.load(self.root)["jobs"])

    def test_generated_role_name_does_not_exempt_unrelated_file(self):
        self.job["files"]["delivery"] = "packet/AFLEVERING.md"
        flow.atomic_write(self.root / "packet/AFLEVERING.md", "Ekstra gennemgået dokument")
        before = flow.hashes(self.root, self.job)
        flow.atomic_write(self.root / "packet/AFLEVERING.md", "Ændret dokument")
        self.assertNotEqual(before, flow.hashes(self.root, self.job))

    def test_joblog_change_invalidates_review(self):
        self.job["joblog_form"]["city"] = "København Ø"
        self.assertTrue(any("matcher ikke" in e for e in flow.validate(self.root, self.job)))

    def test_joblog_requires_separate_postcode_city_and_sources(self):
        for key in ("postcode", "city", "sources"):
            with self.subTest(key=key):
                job = copy.deepcopy(self.job)
                del job["joblog_form"][key]
                self.assertTrue(any("Joblog" in e for e in flow.validate(self.root, job)))

    def test_job_requirement_change_invalidates_review(self):
        self.job["requirements"]["no_photo"] = False
        self.assertTrue(any("matcher ikke" in e for e in flow.validate(self.root, self.job)))

    def test_source_bank_change_invalidates_review(self):
        flow.save_json(self.root / "Profil/fakta.json", {"facts": [{"id": "FACT-EDU", "text": "ændret"}]})
        self.assertTrue(any("matcher ikke" in e for e in flow.validate(self.root, self.job)))

    def test_missing_required_cv_fails(self):
        (self.root / "packet/cv.md").unlink()
        self.assertTrue(flow.validate(self.root, self.job))

    def test_letter_required_only_for_letter_format(self):
        self.job["requirements"]["format"] = "cover_letter"
        self.assertIn("Mangler dokument: letter", flow.validate(self.root, self.job))

    def test_expired_job_fails(self):
        self.job["deadline"] = "2020-01-01"
        self.assertIn("Ansøgningsfrist er passeret", flow.validate(self.root, self.job))

    def test_future_verification_fails(self):
        self.job["posting_checked_at"] = "2099-01-01"
        self.assertIn("Opslag skal være kontrolleret inden for tre dage", flow.validate(self.root, self.job))

    def test_stale_verification_fails(self):
        self.job["posting_checked_at"] = "2020-01-01"
        self.assertTrue(flow.validate(self.root, self.job))

    def test_unknown_deadline_with_note_allowed(self):
        self.job["deadline"] = None
        self.job["deadline_note"] = "Løbende, ingen dato i opslaget"
        self.review["artifact_hashes"] = flow.hashes(self.root, self.job)
        self.save_review()
        self.assertEqual([], flow.validate(self.root, self.job))

    def test_unknown_and_private_claims_fail(self):
        for sid in ("INVENTED", "PRIVATE"):
            self.review["claims"][0]["source_ids"] = [sid]
            self.save_review()
            self.assertTrue(any("ukendt/intern" in e for e in flow.validate(self.root, self.job)))

    def test_unfinished_review_fails(self):
        self.review["checks"]["candidate_facts"] = False
        self.save_review()
        self.assertTrue(any("candidate_facts" in e for e in flow.validate(self.root, self.job)))

    def test_photo_restriction(self):
        flow.atomic_write(self.root / "packet/cv.md", '<img src="photo.jpg">')
        self.assertTrue(any("Foto/billede" in e for e in flow.validate(self.root, self.job)))

    def test_path_escape_rejected(self):
        for value in ("../outside.md", "C:/outside.md"):
            with self.assertRaises(ValueError):
                flow.local_path(self.root, value)

    def test_duplicate_tracking_url(self):
        other = copy.deepcopy(self.job)
        other.update(id="demo-test-2", title="Anden titel", url="https://example.org/jobs/123?utm_source=other")
        self.assertTrue(flow.duplicate(self.job, other))

    def test_shared_career_page_is_not_duplicate(self):
        other = copy.deepcopy(self.job)
        self.job["url_kind"] = "listing"
        other.update(id="demo-test-2", title="Anden rolle", url_kind="listing")
        self.assertFalse(flow.duplicate(self.job, other))

    def test_hash_routed_job_ids_are_distinct(self):
        self.job["url"] = "https://example.org/careers/#/jobs/123"
        other = copy.deepcopy(self.job)
        other.update(id="demo-test-2", title="Anden rolle", url="https://example.org/careers/#/jobs/456")
        self.assertFalse(flow.duplicate(self.job, other))

    def test_navigation_fragment_does_not_hide_duplicate(self):
        other = copy.deepcopy(self.job)
        other.update(id="demo-test-2", title="Anden rolle", url=self.job["url"] + "#apply")
        self.assertTrue(flow.duplicate(self.job, other))

    def test_distinct_successfactors_ids_not_duplicate(self):
        self.job["url"] = "https://example.org/career?career_job_req_id=1&company=x"
        other = copy.deepcopy(self.job)
        other.update(id="demo-test-2", title="Anden rolle", url="https://example.org/career?company=x&career_job_req_id=2")
        self.assertFalse(flow.duplicate(self.job, other))

    def test_cannot_submit_draft(self):
        with self.assertRaises(ValueError):
            flow.change_status(self.root, self.job, "submitted", "Test", self.now.isoformat())

    def test_submission_requires_date_and_evidence(self):
        self.job["status"] = "approved"
        with self.assertRaises(ValueError):
            flow.change_status(self.root, self.job, "submitted", "", self.now.isoformat())
        with self.assertRaises(ValueError):
            flow.change_status(self.root, self.job, "submitted", "Kvittering")

    def test_ready_approved_submitted_keeps_history(self):
        flow.change_status(self.root, self.job, "ready", "Gennemgået")
        flow.change_status(self.root, self.job, "approved", "Niko godkendte")
        flow.change_status(self.root, self.job, "submitted", "Kvittering", self.now.isoformat())
        self.assertEqual("submitted", self.job["status"])
        self.assertEqual(3, len(self.job["history"]))
        self.assertEqual(self.now.isoformat(), self.job["submission"]["date"])

    def test_status_correction_preserves_submission_after_rejection(self):
        self.job["status"] = "submitted"
        self.job["submission"] = {"date": self.now.isoformat(), "evidence": "Kvittering"}
        original = copy.deepcopy(self.job["submission"])
        flow.correct_status(self.root, self.job, "rejected", "Niko oplyste afslag")
        self.assertEqual(original, self.job["submission"])
        self.assertIn("Statuskorrektion", self.job["history"][-1]["evidence"])

    def test_explicit_submission_correction_removes_false_send_from_views_and_preserves_history(self):
        flow.save_json(self.root / "Profil/projekter.json", {"projects": []})
        self.job["status"] = "submitted"
        self.job["submission"] = {"date": self.now.isoformat(), "evidence": "Fejlagtig registrering"}
        self.job["history"] = [{"at": self.now.isoformat(), "from": "approved", "to": "submitted", "evidence": "Fejlagtig registrering"}]
        old_submission = copy.deepcopy(self.job["submission"])
        old_history = copy.deepcopy(self.job["history"])
        flow.save_json(self.root / "Data/jobs.json", {"schema_version": 1, "jobs": [self.job]})
        flow.render(self.root, {"jobs": [self.job]})
        current_path = self.root / "AKTUEL_STATUS.md"
        packet_path = self.root / "Ansoegninger_Aktive" / self.job["id"] / "AFLEVERING.md"
        joblog_path = packet_path.with_name("JOBLOG.md")
        self.assertIn(f"— {self.now.isoformat()}", current_path.read_text(encoding="utf-8"))
        with redirect_stdout(StringIO()):
            flow.main(["--root", str(self.root), "correct-status", self.job["id"], "needs_review",
                       "--clear-submission", "--evidence", "Niko bekræfter at pakken aldrig blev sendt"])
        corrected = flow.load(self.root)["jobs"][0]
        self.assertIsNone(corrected["submission"])
        self.assertEqual(old_history, corrected["history"][:-1])
        self.assertEqual(old_submission, corrected["history"][-1]["cleared_submission"])
        self.assertIn("Ingen af de aktive ansøgninger er registreret som faktisk indsendt", current_path.read_text(encoding="utf-8"))
        self.assertIn("Faktisk afsendelse: Ikke oplyst", packet_path.read_text(encoding="utf-8"))
        self.assertIn("- Sendt til arbejdsgiver: Ikke oplyst", joblog_path.read_text(encoding="utf-8"))

    def test_submission_clearing_is_rejected_for_application_outcome_states(self):
        self.job["status"] = "submitted"
        self.job["submission"] = {"date": self.now.isoformat(), "evidence": "Kvittering"}
        original = copy.deepcopy(self.job)
        for target in ("submitted", "interview", "rejected", "legacy_submitted", "legacy_interview"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "clear-submission"):
                flow.correct_status(self.root, self.job, target, "Korrektion", self.now.isoformat(), clear_submission=True)
            self.assertEqual(original, self.job)

    def test_submission_clearing_requires_explicit_evidence(self):
        self.job["status"] = "submitted"
        self.job["submission"] = {"date": self.now.isoformat(), "evidence": "Kvittering"}
        original = copy.deepcopy(self.job)
        with self.assertRaises(ValueError):
            flow.correct_status(self.root, self.job, "closed", " ", clear_submission=True)
        self.assertEqual(original, self.job)

    def test_status_correction_cannot_bypass_review(self):
        self.job["deadline"] = "2020-01-01"
        original = copy.deepcopy(self.job)
        for status in ("ready", "approved"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                flow.correct_status(self.root, self.job, status, "Korrektion")
            self.assertEqual(original, self.job)

    def test_late_submission_correction_needs_actual_date_and_evidence(self):
        self.job["status"] = "closed"
        self.job["deadline"] = "2020-01-01"
        for evidence, sent_on in (("", "2019-12-31"), ("Kvittering", None), ("Kvittering", "2099-01-01")):
            with self.subTest(evidence=evidence, sent_on=sent_on), self.assertRaises(ValueError):
                flow.correct_status(self.root, self.job, "submitted", evidence, sent_on)
        flow.correct_status(self.root, self.job, "submitted", "Niko bekræfter faktisk afsendelse", "2019-12-31")
        self.assertEqual("submitted", self.job["status"])
        self.assertEqual("2019-12-31", self.job["submission"]["date"])

    def test_malformed_job_fields_report_errors_instead_of_crashing(self):
        cases = [("id", []), ("url", None), ("status", []), ("language", {}),
                 ("requirements", {"format": "cv_only", "max_words": "100"}),
                 ("files", {"cv": 17}), ("selected_sources", "FACT-EDU"),
                 ("joblog_form", {"sources": [None]}), ("submission", [])]
        for field, value in cases:
            with self.subTest(field=field):
                job = copy.deepcopy(self.job)
                job[field] = value
                self.assertTrue(flow.validate(self.root, job))
        self.assertTrue(flow.schema_errors([]))

    def test_malformed_review_reports_errors_instead_of_crashing(self):
        reviews = [[], {"checks": []}, {"claims": [None]},
                   {"claims": [{"text": "Påstand", "source_ids": [{}]}]}]
        for review in reviews:
            with self.subTest(review=review):
                flow.save_json(self.root / "packet/review.json", review)
                self.assertTrue(flow.validate(self.root, self.job))

    def test_lock_blocks_concurrent_writes(self):
        with flow.lock(self.root):
            with self.assertRaises(ValueError):
                with flow.lock(self.root):
                    pass

    def test_age_without_gammel_is_rejected(self):
        flow.atomic_write(self.root / "packet/cv.md", "Jeg er 35 år og bor i København.")
        self.assertTrue(any("Alder/fødselsdato" in e for e in flow.validate(self.root, self.job)))

    def test_cli_roundtrip_and_generated_links(self):
        flow.save_json(self.root / "Profil/projekter.json", {"projects": []})
        flow.save_json(self.root / "Profil/Kilder/github_inventory.json", {"checked_at": self.now.isoformat()})
        flow.save_json(self.root / "Data/jobs.json", {"schema_version": 1, "jobs": []})
        fresh = copy.deepcopy(self.job)
        fresh["status"] = "discovered"
        input_path = self.root / "input.json"
        flow.save_json(input_path, fresh)
        base = ["--root", str(self.root)]
        with redirect_stdout(StringIO()):
            self.assertEqual(0, flow.main(base + ["add", str(input_path)]))
            with self.assertRaises(ValueError):
                flow.main(base + ["add", str(input_path)])
            flow.main(base + ["status", fresh["id"], "needs_review", "--evidence", "Udkast produceret"])
            current = flow.load(self.root)["jobs"][0]
            self.review["artifact_hashes"] = flow.hashes(self.root, current)
            self.save_review()
            self.assertEqual(0, flow.main(base + ["validate", fresh["id"]]))
            flow.main(base + ["status", fresh["id"], "ready", "--evidence", "Review bestået"])
            self.assertEqual(0, flow.main(base + ["check"]))
        tracker = (self.root / "Jobsøgning_Tracker.md").read_text(encoding="utf-8")
        self.assertIn("Klar til gennemlæsning", tracker)
        self.assertTrue((self.root / "Ansoegninger_Aktive/demo-test-1/AFLEVERING.md").is_file())
        current = flow.load(self.root)["jobs"][0]
        current["status"] = "submitted"
        flow.save_json(input_path, current)
        with self.assertRaises(ValueError):
            flow.main(base + ["upsert", str(input_path)])
        self.assertEqual("ready", flow.load(self.root)["jobs"][0]["status"])

    def test_submitted_packet_and_joblog_are_regenerated(self):
        folder = self.root / "Ansoegninger_Aktive" / self.job["id"]
        folder.mkdir(parents=True)
        flow.save_json(self.root / "Profil/projekter.json", {"projects": []})
        self.job["joblog_form"] = {
            "posting_url": "https://example.org/jobs/123",
            "address": "Testgade 7", "country": "Danmark",
            "postcode": "2400", "city": "København NV",
            "contact_person": "Test Person", "email": None, "phone": "12 34 56 78",
        }
        self.job["status"] = "submitted"
        self.job["submission"] = {"date": self.now.isoformat(), "evidence": "Kvittering"}
        flow.render(self.root, {"jobs": [self.job]})
        packet = (folder / "AFLEVERING.md").read_text(encoding="utf-8")
        joblog = (folder / "JOBLOG.md").read_text(encoding="utf-8")
        self.assertIn("Status: Sendt", packet)
        self.assertIn("[Felter til Joblog](<JOBLOG.md>)", packet)
        self.assertIn("- Link til stillingsopslag: https://example.org/jobs/123", joblog)
        self.assertIn("- Postnr.*: 2400\n- By*: København NV", joblog)
        self.assertIn(f"- Sendt til arbejdsgiver: {self.now.isoformat()}", joblog)

    def test_next_is_read_only_and_prioritizes_active_work(self):
        history = copy.deepcopy(self.job)
        history.update(id="old-history", status="legacy_draft", deadline="2020-01-01", files={})
        self.job["status"] = "ready"
        self.job["next_action"] = "Send pakken straks"
        flow.atomic_write(self.root / "packet/cv.md", "Ændret efter review")
        flow.save_json(self.root / "Data/jobs.json", {"schema_version": 1, "jobs": [history, self.job]})
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, flow.main(["--root", str(self.root), "next"]))
        result = json.loads(output.getvalue())
        self.assertEqual(self.job["id"], result[0]["id"])
        self.assertTrue(result[0]["issues"])
        self.assertNotIn("Send pakken straks", result[0]["next_action"])
        self.assertEqual([], result[1]["issues"])
        self.assertIn("ingen genansøgning", result[1]["next_action"])
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_next_submission_follow_up_depends_on_date(self):
        self.job["status"] = "submitted"
        self.job["submission"] = {"date": self.now.isoformat(), "evidence": "Kvittering"}
        self.job["follow_up_on"] = self.now.isoformat()
        self.assertIn("Følg op", flow.diagnose(self.root, self.job)["next_action"])
        self.job["follow_up_on"] = (self.now + timedelta(days=1)).isoformat()
        self.assertIn("Afvent svar", flow.diagnose(self.root, self.job)["next_action"])

    def test_legacy_interview_is_not_treated_as_current_appointment(self):
        self.job["status"] = "legacy_interview"
        result = flow.diagnose(self.root, self.job)
        self.assertEqual([], result["issues"])
        self.assertIn("Historikken", result["next_action"])
        self.assertNotIn("aftalte samtale", result["next_action"])

    def test_recent_submission_list_uses_send_date_and_keeps_rejected_applications(self):
        flow.save_json(self.root / "Profil/projekter.json", {"projects": []})
        old = copy.deepcopy(self.job)
        old.update(id="old-created", company="Netop indsendt", created_at="2020-01-01", status="rejected",
                   submission={"date": self.now.isoformat(), "evidence": "Kvittering"})
        self.job.update(status="submitted", submission={"date": "2020-01-01", "evidence": "Kvittering"})
        flow.render(self.root, {"jobs": [self.job, old]})
        current = (self.root / "AKTUEL_STATUS.md").read_text(encoding="utf-8")
        self.assertLess(current.index("Netop indsendt"), current.index("Eksempel"))

    def test_check_does_not_revalidate_submitted_packet_as_new_application(self):
        self.job["status"] = "submitted"
        self.job["deadline"] = "2020-01-01"
        self.job["submission"] = {"date": "2019-12-31", "evidence": "Kvittering"}
        self.job["joblog_form"] = None
        flow.save_json(self.root / "Profil/Kilder/github_inventory.json", {"checked_at": self.now.isoformat()})
        report = flow.check(self.root, {"jobs": [self.job]})
        self.assertEqual([], report["errors"])

    def test_delete_cannot_destroy_history_or_duplicate_basis(self):
        path = self.root / "Data/jobs.json"
        flow.save_json(path, {"schema_version": 1, "jobs": [self.job]})
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "bevar historik"):
            flow.main(["--root", str(self.root), "delete", self.job["id"], "--evidence", "Oprydning"])
        self.assertEqual(before, path.read_bytes())

    def test_generated_overview_uses_actual_checks_instead_of_stale_next_action(self):
        flow.save_json(self.root / "Profil/projekter.json", {"projects": []})
        self.job["status"] = "ready"
        self.job["next_action"] = "Send straks"
        self.job["deadline"] = "2020-01-01"
        flow.render(self.root, {"jobs": [self.job]})
        current = (self.root / "AKTUEL_STATUS.md").read_text(encoding="utf-8")
        self.assertIn("Skal genkontrolleres", current)
        self.assertIn("luk sagen", current)
        self.assertNotIn("Send straks", current)

    def test_project_catalog_supports_local_evidence_and_marks_missing_source_locations(self):
        flow.atomic_write(self.root / "Profil/Kilder/demo-executed.md", "Faktisk syntetisk testresultat")
        flow.save_json(self.root / "Profil/projekter.json", {"projects": [{
            "id": "PROJ-LOCAL", "name": "Lokalt workflow", "summary": "Et lokalt projekt",
            "tags": ["Python"], "evidence_level": "Lokal kode og dokumenteret testkørsel",
            "external_use": True, "safe_claim_da": "Workflowet er kontrolleret lokalt.",
            "limitations": "Ingen produktionsmåling.",
            "sources": [{"label": "Lokalt testresultat", "snapshot": "Profil/Kilder/demo-executed.md"},
                        {"label": "Webkilde", "url": "https://example.org/source"},
                        {"label": "Ufuldstændig kilde"}]}]})
        flow.render(self.root, {"jobs": []})
        catalog = (self.root / "Profil/PROJEKTER.md").read_text(encoding="utf-8")
        self.assertIn("[Lokalt testresultat](<Kilder/demo-executed.md>)", catalog)
        self.assertIn("[Webkilde](https://example.org/source)", catalog)
        self.assertIn("Ufuldstændig kilde (mangler gyldig webadresse eller lokalt snapshot)", catalog)
        self.assertIn("Lokal kode og dokumenteret testkørsel", catalog)
        self.assertNotIn("programmer er ikke kørt", catalog)


if __name__ == "__main__":
    unittest.main()
