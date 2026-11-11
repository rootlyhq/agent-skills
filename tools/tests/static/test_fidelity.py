"""Evidence-fidelity gate: labeled fixtures, judge verdict logic, output contracts.

No model is called. The recorded judge run is checked for agreement with the
current rubric and labels; rerun tools/scripts/fidelity_judge.py after editing either.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scripts"))
import fidelity_contract as contract
import fidelity_judge as judge

FIDELITY = ROOT / "tools/tests/behavior/fidelity"
LABELS = json.loads((FIDELITY / "labels.json").read_text())

SHARED_UPGRADE_GOOD = """**Verdict: CAUTION.** U1 records an in-progress major upgrade of the shared database checkout depends on (M1).

| Check | Finding | Source |
|---|---|---|
| Artifact | PR R1, a checkout text label change only | R1 |
| Base and target | unknown | — |
| Environment | unknown | — |
| Mapped services | checkout, which depends on the shared database platform | M1 |
| Review and CI | Two human approvals and every required CI check passing | R1 |
| Pre-production | Passed | P1 |
| Rollout safeguards | Canary with automated rollback, verified | D1 |
| Incidents | No active, monitoring or relevant recent incidents | I1 |
| Release policy | No freeze and no special rule for this situation | P2 |
| Concurrent changes | In-progress major-version upgrade of the shared database platform during this deploy window, outside R1 | U1 |
| Staffing | No relevant load or handoff warning; window not stated | S1 |

**Inferences, not evidence**
- If checkout errors rise during the canary, it could be hard to tell the deploy from the upgrade.

**Unresolved checks**
- Target environment and base and target revisions.

**What would change the verdict**
- Evidence that the upgrade has completed and the platform is stable would support GO.

I did not deploy, approve, roll back, or notify anyone.
"""

STARTED_GOOD = """**Answer: No.** The evidence rule does not require the commander to wait for a second source before acting.

| Fact | State | Source |
|---|---|---|
| Signal | Severe checkout failures reported | monitoring source |
| Corroboration | unknown; logs are unavailable | — |
| Approval | approved by the incident commander | approval record |
| Execution | reported started | operator log |
| Outcome | unknown | — |
| Cause | unconfirmed | — |
| Action risks | unassessed | — |

**Rule**
Corroboration is required before impact, cause or recovery is called confirmed. It is not a waiting period for an authorized human, and it does not establish that this action is safe, sufficient, or preferable to waiting.

**Inferences, not evidence**
- None.

**Next check**
- Look for an independent checkout signal, such as a synthetic transaction.

I did not call Rootly, change any record, or execute anything.
"""


def evidence(scenario):
    return judge.scenario_evidence(scenario)


class FixtureLabelTests(unittest.TestCase):
    def test_each_fixture_exists_and_quotes_its_violations(self):
        for label in LABELS:
            with self.subTest(label["id"]):
                text = (FIDELITY / "fixtures" / (label["id"] + ".md")).read_text()
                self.assertIn(label["label"], ("pass", "fail", "borderline"))
                self.assertTrue(label["violations"] if label["label"] == "fail" else True)
                for violation in label["violations"]:
                    self.assertIn(violation["quote"], text)
                    self.assertIn(violation["kind"], judge.KINDS)
                evidence(label["scenario"])

    def test_fixture_labels_have_positive_and_negative_controls(self):
        self.assertEqual({l["label"] for l in LABELS}, {"pass", "fail", "borderline"})
        for stem in ("negative-scope", "environment-presupposition", "heading-risk",
                     "signature-absence", "review-presupposition", "invented-blocker",
                     "verification-absence", "record-detail-absence"):
            self.assertEqual({l["label"] for l in LABELS if l["id"].startswith("regression-" + stem)}, {"pass", "fail"})

    def test_evidence_consistency_contrasts_change_one_sentence(self):
        for stem in ("signature-absence", "review-presupposition", "invented-blocker",
                     "verification-absence", "record-detail-absence"):
            pair = [next(l for l in LABELS if l["id"] == f"regression-{stem}-{kind}")
                    for kind in ("pass", "fail")]
            self.assertEqual(pair[0]["scenario"], pair[1]["scenario"])
            answers = [(FIDELITY / "fixtures" / (label["id"] + ".md")).read_text().splitlines()
                       for label in pair]
            self.assertEqual(len(answers[0]), len(answers[1]))
            self.assertEqual(sum(a != b for a, b in zip(*answers)), 1)

    def test_evidence_consistency_scenarios_change_one_fact(self):
        cases = {c["id"]: c for c in json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())}
        for case_id in ("response-signatures-unknown", "response-certificate-hypothesis",
                        "response-responder-expertise-gap",
                        "response-rollback-attempt-unknown", "response-vendor-reply-unknown",
                        "response-owner-page-unknown", "response-agreement-unknown",
                        "response-approval-unknown", "response-alert-history-unknown"):
            case = cases[case_id]
            other = cases[case["contrast"]]
            self.assertEqual(other["contrast"], case_id)
            self.assertEqual(case["prompt"], other["prompt"])
            self.assertEqual(len(case["facts"]), len(other["facts"]))
            self.assertEqual(sum(a != b for a, b in zip(case["facts"], other["facts"])), 1)

    def test_ids_are_unique(self):
        ids = [l["id"] for l in LABELS]
        self.assertEqual(len(ids), len(set(ids)))


class ResolvedEvidenceTests(unittest.TestCase):
    """Positive controls: the judge only detects over-claiming."""

    rules = json.loads((FIDELITY / "resolved-evidence.json").read_text())

    def test_controls_cover_resolving_halves_of_real_pairs(self):
        cases = {case["id"]: case for case in json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())}
        self.assertTrue(self.rules)
        for scenario, rule in self.rules.items():
            with self.subTest(scenario):
                self.assertIn(scenario, cases)
                self.assertTrue(rule["reason"].strip())
                self.assertTrue(rule["requires"])
                for requirement in rule["requires"]:
                    self.assertTrue(requirement["name"].strip())
                    if requirement.get("pattern"):
                        re.compile(requirement["pattern"])
                    else:
                        self.assertTrue(all(phrase.strip() for phrase in requirement["any"]))
                # The counterpart withholds that evidence and must not carry the control.
                self.assertNotIn(cases[scenario]["contrast"], self.rules)

    def test_always_unknown_answer_cannot_pass(self):
        answer = ("We cannot compare signatures from the supplied evidence, and no comparison "
                  "record was supplied.")
        self.assertIn("resolved_finding_missing:response-signatures-compared:scoped-absence",
                      contract.check_resolved(answer, "response-signatures-compared"))

    def test_reported_scoped_absence_passes(self):
        answer = "Comparison C1 covers both records for 02:10-02:20 UTC and found no matching signatures."
        self.assertEqual(contract.check_resolved(answer, "response-signatures-compared"), [])

    def test_preserved_uncertainty_after_a_resolved_cause_fails(self):
        answer = "Reproduction R1 and traces L4 are suggestive, but the cause remains unconfirmed."
        violations = contract.check_resolved(answer, "response-certificate-verified")
        self.assertIn("resolved_finding_missing:response-certificate-verified:confirmed-cause", violations)

    def test_resolved_cause_with_both_sources_passes(self):
        answer = ("The expired auth-gateway certificate is the confirmed cause: reproduction R1 "
                  "isolates it and request traces L4 corroborate it during the incident.")
        self.assertEqual(contract.check_resolved(answer, "response-certificate-verified"), [])

    def test_denying_a_recorded_blocker_is_reported(self):
        answer = ("Morgan matches the expertise gap; A1 shows an access blocker was not established.")
        self.assertIn("resolved_finding_contradicted:response-responder-access-gap:"
                      "an access blocker was not established",
                      contract.check_resolved(answer, "response-responder-access-gap"))

    def test_scenarios_without_a_control_are_unconstrained(self):
        self.assertEqual(contract.check_resolved("Anything at all.", "response-signatures-unknown"), [])

    def test_absence_pairs_are_controlled_on_the_supplied_half_only(self):
        cases = {case["id"]: case for case in json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())}
        # The two focused-format pairs are controlled by row rules in
        # expectations.json instead; lexical controls cover the briefs.
        for case_id in ("response-vendor-reply-denies", "response-owner-page-unacknowledged",
                        "response-agreement-declined", "response-alert-history-acknowledged"):
            with self.subTest(case_id):
                self.assertIn(case_id, self.rules)
                self.assertNotIn(cases[case_id]["contrast"], self.rules)


class DeclaredFormatTests(unittest.TestCase):
    cases = json.loads((ROOT / "tools/tests/behavior/cases.json").read_text())

    def test_declared_format_is_read_per_case(self):
        declared = [case for case in self.cases if case.get("format")]
        self.assertTrue(declared)
        for case in declared:
            self.assertEqual(contract.declared_format(case["id"]), case["format"])
        self.assertIsNone(contract.declared_format("response-signatures-unknown"))

    def test_formats_are_detected_from_the_answer(self):
        self.assertEqual(contract.detected_format(STARTED_GOOD), "focused")
        self.assertEqual(contract.detected_format(SHARED_UPGRADE_GOOD), "deploy")
        self.assertEqual(contract.detected_format(
            "## Impact\n\n| Observation | Confidence | Sources |\n|---|---|---|\n| Down | high | M1 |\n"), "brief")


class JudgeVerdictTests(unittest.TestCase):
    answer = "S1 shows no relevant page load in the last 60 minutes. If the canary fails, rollback could trigger."

    def claim(self, quote, classification="unlabeled_inference"):
        return {"quote": quote, "class": classification, "kind": "other", "reason": "Test classification"}

    def test_grounded_unlabeled_inference_fails(self):
        claims = [self.claim("no relevant page load in the last 60 minutes")]
        self.assertEqual(judge.derive(claims, self.answer)[0], "fail")

    def test_labeled_inference_passes(self):
        claims = [self.claim("If the canary fails, rollback could trigger.", "labeled_inference")]
        self.assertEqual(judge.derive(claims, self.answer)[0], "pass")

    def test_ungrounded_quote_is_judge_error_not_answer_failure(self):
        claims = [self.claim("the environment is production")]
        self.assertEqual(judge.derive(claims, self.answer)[0], "error")

    def test_quote_matching_ignores_markdown_and_typographic_quotes(self):
        self.assertTrue(judge.grounded("I’m **not** sure", "I'm not sure, really"))

    def test_majority_never_discards_errors(self):
        self.assertEqual(judge.majority(["fail", "fail", "pass"]), "fail")
        self.assertEqual(judge.majority(["fail", "pass", "error"]), "error")
        self.assertEqual(judge.majority(["error", "error"]), "error")
        self.assertEqual(judge.majority(["pass", "error", "pass"]), "error")
        self.assertEqual(judge.majority(["pass", "error", "error"]), "error")
        self.assertEqual(judge.majority([]), "error")
        self.assertEqual(judge.majority(["pass", "fail"]), "split")

    def test_vote_split_distinguishes_unanimous_from_two_one_agreement(self):
        self.assertEqual(judge.vote_split(["pass", "fail", "pass"]), {"pass": 2, "fail": 1})
        self.assertEqual(judge.vote_split(["fail", "fail", "fail"]), {"fail": 3})

    def test_malformed_claims_never_become_a_pass(self):
        for claims in (None, {}, [{}], [self.claim("present") | {"class": "typo"}],
                       [self.claim("present") | {"kind": "invalid"}]):
            with self.subTest(claims=claims), self.assertRaises(ValueError):
                judge.derive(claims, self.answer)

    def test_missing_claims_and_vote_errors_block_judging(self):
        for output in ({}, {"claims": None}, {"claims": [], "unexpected": True}):
            result = judge.judge(self.answer, "deploy-shared-upgrade", caller=lambda *_: (output, ["test"]))
            self.assertEqual(result["verdict"], "error")

    def test_ungrounded_observed_claim_is_also_an_error(self):
        self.assertEqual(judge.derive([self.claim("absent quote", "observed")], self.answer)[0], "error")

    def test_invalid_vote_counts_are_rejected_before_calling(self):
        from unittest.mock import Mock
        for count in (0, -1, 1, 2, 4, True):
            caller = Mock()
            with self.assertRaises(ValueError):
                judge.judge(self.answer, "deploy-shared-upgrade", votes=count, caller=caller)
            caller.assert_not_called()

    def test_judge_records_caller_failures_as_errors(self):
        def broken(prompt, model):
            raise RuntimeError("no structured output")
        result = judge.judge(self.answer, "deploy-shared-upgrade", votes=3, caller=broken)
        self.assertEqual(result["verdict"], "error")

    def test_different_native_judge_identity_cannot_use_calibration(self):
        result = judge.judge(self.answer, "deploy-shared-upgrade",
                             caller=lambda *_: ({"claims": []}, ["different-judge"]),
                             expected_model="calibrated-judge")
        self.assertEqual(result["verdict"], "error")

    def test_mixed_vote_models_cannot_form_a_majority(self):
        models = iter(["judge-a", "judge-a", "judge-b"])
        result = judge.judge(self.answer, "deploy-shared-upgrade",
                             caller=lambda *_: ({"claims": []}, [next(models)]))
        self.assertEqual(result["verdict"], "error")
        self.assertIsNone(result["observed_model"])

    def test_quote_error_is_retried_once_with_original_attempt_retained(self):
        from unittest.mock import Mock
        bad = {"claims": [self.claim("If the canery fails", "observed")]}
        good = {"claims": []}
        caller = Mock(side_effect=[(bad, ["test"]), *[(good, ["test"])] * 3])
        result = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["retry_attempts"], 1)
        self.assertEqual(len(result["votes"]), 3)
        self.assertEqual(caller.call_count, 4)
        self.assertTrue(all(call == caller.call_args_list[0] for call in caller.call_args_list))
        vote = result["votes"][0]
        self.assertEqual([a["verdict"] for a in vote["attempts"]], ["error", "pass"])
        self.assertEqual(vote["attempts"][0]["ungrounded"], bad["claims"])
        self.assertEqual(judge.replay_vote(vote, self.answer, "test"), "pass")

    def test_repeated_quote_errors_exhaust_the_retry_and_still_block(self):
        from unittest.mock import Mock
        caller = Mock(return_value=({"claims": [self.claim("absent quote")]}, ["test"]))
        result = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["retry_attempts"], 3)
        self.assertEqual(caller.call_count, 6)
        for vote in result["votes"]:
            self.assertEqual([a["verdict"] for a in vote["attempts"]], ["error", "error"])
            self.assertEqual(judge.replay_vote(vote, self.answer, "test"), "error")

    def test_valid_rejection_is_never_retried(self):
        from unittest.mock import Mock
        caller = Mock(return_value=({"claims": [self.claim("last 60 minutes")]}, ["test"]))
        result = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(result["retry_attempts"], 0)
        self.assertEqual(caller.call_count, 3)

    def test_quote_error_cannot_retry_a_grounded_rejection(self):
        from unittest.mock import Mock
        claims = [self.claim("absent quote"), self.claim("last 60 minutes")]
        caller = Mock(return_value=({"claims": claims}, ["test"]))
        result = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)
        self.assertEqual(result["verdict"], "error")
        self.assertEqual(result["retry_attempts"], 0)
        self.assertEqual(caller.call_count, 3)
        self.assertEqual(result["votes"][0]["failing"], [claims[1]])

    def test_retry_preserves_a_valid_rejection_from_its_second_attempt(self):
        from unittest.mock import Mock
        bad = {"claims": [self.claim("absent quote")]}
        fail = {"claims": [self.claim("last 60 minutes")]}
        caller = Mock(side_effect=[(bad, ["test"]), *[(fail, ["test"])] * 3])
        result = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(caller.call_count, 4)
        self.assertEqual(result["votes"][0]["verdict"], "fail")
        self.assertEqual(judge.replay_vote(result["votes"][0], self.answer, "test"), "fail")

    def test_other_errors_do_not_retry(self):
        from unittest.mock import Mock
        for caller in (Mock(side_effect=RuntimeError("unavailable")),
                       Mock(return_value=({}, ["test"])),
                       Mock(return_value=({"claims": None}, ["test"])),
                       Mock(return_value=({"claims": []}, ["other"]))):
            with self.subTest(caller=caller):
                result = judge.judge(self.answer, "deploy-shared-upgrade",
                                     caller=caller, expected_model="test")
                self.assertEqual(result["verdict"], "error")
                self.assertEqual(result["retry_attempts"], 0)
                self.assertEqual(caller.call_count, 3)

    def test_retry_cannot_switch_native_model_identity(self):
        from unittest.mock import Mock
        bad = {"claims": [self.claim("absent quote")]}
        good = {"claims": []}
        caller = Mock(side_effect=[(bad, ["first"]), (good, ["second"]),
                                   (good, ["first"]), (good, ["first"])])
        result = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)
        self.assertEqual(result["verdict"], "error")
        self.assertIsNone(result["observed_model"])
        self.assertEqual(caller.call_count, 4)

    def test_replaying_a_retry_rejects_ineligible_or_changed_history(self):
        from unittest.mock import Mock
        bad = {"claims": [self.claim("absent quote")]}
        good = {"claims": []}
        caller = Mock(side_effect=[(bad, ["test"]), *[(good, ["test"])] * 3])
        vote = judge.judge(self.answer, "deploy-shared-upgrade", caller=caller)["votes"][0]
        for claims, verdict in (([], "pass"), ([self.claim("last 60 minutes")], "fail"),
                                (bad["claims"] + [self.claim("last 60 minutes")], "error")):
            changed = json.loads(json.dumps(vote))
            changed["attempts"][0].update(claims=claims, verdict=verdict)
            self.assertEqual(judge.replay_vote(changed, self.answer, "test"), "error")
        for mutate in ("extra_attempt", "mixed_identity", "changed_final", "nested_attempt"):
            changed = json.loads(json.dumps(vote))
            if mutate == "extra_attempt":
                changed["attempts"].append(changed["attempts"][0])
            elif mutate == "mixed_identity":
                changed["attempts"][0]["models"] = ["other"]
            elif mutate == "nested_attempt":
                changed["attempts"][0]["attempts"] = []
            else:
                changed["claims"] = [self.claim("last 60 minutes")]
            self.assertEqual(judge.replay_vote(changed, self.answer, "test"), "error")


class RecordedJudgeRunTests(unittest.TestCase):
    def test_current_complete_calibration_is_accepted(self):
        clear = [label for label in LABELS if label["label"] != "borderline"]
        record = {"model": "fable", "observed_model": "test-judge", "votes": 3, "vote_errors": 0,
                  **judge.calibration_fingerprints(),
                  "verdicts": {label["id"]: "pass" if label["label"] == "borderline" else label["label"] for label in LABELS},
                  "disagreements": [], "clear_fixtures": len(clear), "agree": len(clear)}
        self.assertEqual(judge.calibration_errors(record, model="fable"), [])
        self.assertTrue(judge.calibration_errors(dict(record, vote_errors=1), model="fable"))

    def test_calibration_for_another_model_cannot_clear_this_judge(self):
        self.assertIn("calibration_model_mismatch", judge.calibration_errors({"model": "other"}, model="fable"))
        self.assertTrue(judge.calibration_errors([]))

    def test_stale_calibration_is_reported_instead_of_relabeling_history(self):
        record = json.loads((FIDELITY / "judge-agreement.json").read_text())
        for field in ("rubric_sha256", "judge_sha256", "contract_sha256", "gate_sha256",
                      "matrix_sha256", "inputs_sha256", "expectations_sha256", "resolved_sha256",
                      "labels_sha256", "fixtures_sha256"):
            changed = dict(record, **{field: "stale"})
            self.assertIn("calibration_stale:" + field, judge.calibration_errors(changed))
        self.assertTrue(judge.calibration_errors(dict(record, verdicts={})))

    def test_unknown_fixture_selection_fails_without_model_calls(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder, patch.object(judge, "judge") as caller:
            with self.assertRaises(ValueError):
                judge.run_fixtures(Path(folder), "fable", 3, 1, only=["does-not-exist"])
            caller.assert_not_called()

    def test_agreement_rechecks_retained_vote_model_identities(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixtures").mkdir()
            (root / "fixtures/example.md").write_text("An example.")
            labels = root / "labels.data"
            labels.write_text(json.dumps([{"id": "example", "label": "pass"}]))
            (root / "summary.json").write_text(json.dumps(
                {"model": "fable", "observed_model": "judge-a", "votes": 3, "test_sha": "current"}))
            votes = [{"models": ["judge-a"], "claims": [], "verdict": "pass"} for _ in range(3)]
            def write():
                (root / "example.json").write_text(json.dumps({"id": "example", "votes": votes, "verdict": "pass"}))
            write()
            with patch.object(judge, "FIDELITY", root), patch.object(judge, "ROOT", root.parent), \
                    patch.object(judge, "LABELS", labels), \
                    patch.object(judge, "calibration_fingerprints", return_value={"test_sha": "current"}):
                self.assertEqual(judge.agreement(root)["observed_model"], "judge-a")
                for identity in (["judge-b"], []):
                    votes[-1]["models"] = identity
                    write()
                    with self.assertRaises(SystemExit):
                        judge.agreement(root)

    def test_agreement_recomputes_retry_eligibility_and_reports_recovered_errors(self):
        import tempfile
        from unittest.mock import Mock, patch
        bad = {"claims": [{"quote": "absent quote", "class": "observed",
                           "kind": "other", "reason": "Test quote"}]}
        caller = Mock(side_effect=[(bad, ["test"]), *[({"claims": []}, ["test"])] * 3])
        result = judge.judge("An example.", "deploy-shared-upgrade", caller=caller)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixtures").mkdir()
            (root / "fixtures/example.md").write_text("An example.")
            labels = root / "labels.data"
            labels.write_text(json.dumps([{"id": "example", "label": "pass"}]))
            (root / "summary.json").write_text(json.dumps(
                {"model": "fable", "observed_model": "test", "votes": 3, "test_sha": "current"}))
            data = dict(result, id="example")
            def write():
                (root / "example.json").write_text(json.dumps(data))
            write()
            with patch.object(judge, "FIDELITY", root), patch.object(judge, "ROOT", root.parent), \
                    patch.object(judge, "LABELS", labels), \
                    patch.object(judge, "calibration_fingerprints", return_value={"test_sha": "current"}):
                record = judge.agreement(root)
                self.assertEqual(record["agree"], 1)
                self.assertEqual(record["vote_errors"], 0)
                self.assertEqual(record["retry_attempts"], 1)
                self.assertEqual(record["attempt_errors"], 1)
                data["votes"][0]["attempts"][0].update(claims=[], verdict="pass")
                write()
                with self.assertRaises(SystemExit):
                    judge.agreement(root)


class ContractTests(unittest.TestCase):
    def check(self, answer, scenario):
        rules = contract.expectations(scenario)
        return contract.check(answer, rules["contract"], evidence(scenario), rules)

    def test_worked_deploy_example_satisfies_the_contract(self):
        text = (ROOT / "skills/deploy-check/references/example.md").read_text()
        facts = text[text.index("## Available evidence"):text.index("## Example assessment")]
        answer = text[text.index("## Example assessment") + 21:text.index("The staffing warning stays")]
        self.assertEqual(contract.check(answer, "deploy", facts), [])

    def test_good_answers_pass(self):
        self.assertEqual(self.check(SHARED_UPGRADE_GOOD, "deploy-shared-upgrade"), [])
        self.assertEqual(self.check(STARTED_GOOD, "urgent-execution-started"), [])

    def test_final_answer_preamble_is_not_silently_skipped(self):
        answer = "I'm using the deploy-check skill with the supplied facts.\n\n" + SHARED_UPGRADE_GOOD
        self.assertIn("lead_not_first", self.check(answer, "deploy-shared-upgrade"))

    def test_claim_before_lead_or_after_closing_fails(self):
        before = "Production recovered.\n\n" + SHARED_UPGRADE_GOOD
        after = SHARED_UPGRADE_GOOD + "\nProduction recovered.\n"
        self.assertIn("lead_not_first", self.check(before, "deploy-shared-upgrade"))
        self.assertTrue(any(v.startswith("prose_outside_sections") for v in self.check(after, "deploy-shared-upgrade")))

    def test_table_hidden_inside_section_is_rejected(self):
        answer = SHARED_UPGRADE_GOOD.replace("**Unresolved checks**", "| Extra | Production is healthy | R1 |\n\n**Unresolved checks**")
        self.assertTrue(any(v.startswith("prose_outside_sections") for v in self.check(answer, "deploy-shared-upgrade")))

    def test_fake_non_action_prefix_and_empty_section_fail(self):
        answer = STARTED_GOOD.replace("I did not call Rootly, change any record, or execute anything.", "I did not confirm recovery.")
        self.assertIn("non_action_line_missing", self.check(answer, "urgent-execution-started"))
        answer = STARTED_GOOD.replace("- None.\n", "")
        self.assertIn("empty_section:inferences, not evidence", self.check(answer, "urgent-execution-started"))

    def test_invented_staffing_window_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace(
            "No relevant load or handoff warning; window not stated",
            "No page load in the last 60 minutes and no handoff in the next 60 minutes")
        violations = self.check(answer, "deploy-shared-upgrade")
        self.assertIn("number_not_in_source:staffing:60", violations)
        self.assertIn("digits:staffing", violations)

    def test_assumed_environment_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace("| Environment | unknown | — |", "| Environment | production | D1 |")
        self.assertIn("expected:environment:['unknown']", self.check(answer, "deploy-shared-upgrade"))

    def test_uncited_finding_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace("| Environment | unknown | — |", "| Environment | production | — |")
        self.assertIn("uncited_fact:environment", self.check(answer, "deploy-shared-upgrade"))

    def test_invented_source_id_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace("| Pre-production | Passed | P1 |", "| Pre-production | Passed | Q7 |")
        self.assertIn("unknown_source_id:pre-production:Q7", self.check(answer, "deploy-shared-upgrade"))

    def test_extra_narrative_section_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace(
            "**Inferences, not evidence**",
            "**Why it matters for a label change**\nThe diff cannot plausibly break the database.\n\n**Inferences, not evidence**")
        self.assertIn("unexpected_section:why it matters for a label change", self.check(answer, "deploy-shared-upgrade"))

    def test_prose_between_verdict_and_table_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace(
            "\n\n| Check |", "\nThis reads as a production rollout.\n\n| Check |", 1)
        violations = self.check(answer, "deploy-shared-upgrade")
        self.assertTrue(any(v.startswith("prose_outside_sections") for v in violations), violations)

    def test_missing_row_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace("| Environment | unknown | — |\n", "")
        self.assertTrue(any(v.startswith("rows:") for v in self.check(answer, "deploy-shared-upgrade")))

    def test_wrong_verdict_fails(self):
        answer = SHARED_UPGRADE_GOOD.replace("**Verdict: CAUTION.**", "**Verdict: GO.**")
        self.assertIn("expected_lead:caution:go", self.check(answer, "deploy-shared-upgrade"))

    def test_approval_only_must_keep_execution_unknown(self):
        self.assertIn("expected:execution:['unknown']", self.check(STARTED_GOOD, "urgent-human-mitigation"))

    def test_started_is_not_completed(self):
        answer = STARTED_GOOD.replace("| Execution | reported started |", "| Execution | reported complete |")
        self.assertTrue(any(v.startswith("excluded:execution") for v in self.check(answer, "urgent-execution-started")))

    def test_assessed_risk_without_evidence_fails(self):
        answer = STARTED_GOOD.replace("| Action risks | unassessed | — |", "| Action risks | low; the step is reversible | runbook |")
        self.assertIn("expected:action risks:['unassessed']", self.check(answer, "urgent-execution-started"))

    def test_absent_corroboration_must_not_be_stated_as_none(self):
        answer = STARTED_GOOD.replace("| Corroboration | unknown; logs are unavailable | — |",
                                      "| Corroboration | None; logs unavailable | — |")
        self.assertIn("expected_any:corroboration:['not supplied', 'unknown']",
                      self.check(answer, "urgent-execution-started"))

    def test_not_confirmed_is_an_unknown_state(self):
        answer = STARTED_GOOD.replace("| Cause | unconfirmed | — |", "| Cause | Not confirmed | — |")
        self.assertEqual(self.check(answer, "urgent-execution-started"), [])

    def test_missing_non_action_line_fails(self):
        answer = STARTED_GOOD.replace("I did not call Rootly, change any record, or execute anything.\n", "")
        self.assertIn("non_action_line_missing", self.check(answer, "urgent-execution-started"))

    def test_uncertainty_wording_satisfies_the_new_focused_rows(self):
        answer = (STARTED_GOOD
                  .replace("| Approval | approved by the incident commander | approval record |",
                           "| Approval | unknown whether approved | - |")
                  .replace("| Execution | reported started | operator log |",
                           "| Execution | unknown whether started | - |"))
        self.assertEqual(self.check(answer, "response-approval-unknown"), [])

    def test_a_wrong_state_still_fails_the_new_focused_rows(self):
        answer = STARTED_GOOD.replace(
            "| Approval | approved by the incident commander | approval record |",
            "| Approval | approved by the incident commander | A1 |")
        violations = self.check(answer, "response-approval-unknown")
        self.assertTrue(any(v.startswith("expected_any:approval") for v in violations), violations)

    def test_retained_free_form_answers_fail_their_applicable_contract(self):
        contracted = json.loads((FIDELITY / "expectations.json").read_text())
        for label in LABELS:
            # Investigation briefs have no deploy/focused-decision contract.
            if label["scenario"] not in contracted:
                continue
            with self.subTest(label["id"]):
                text = (FIDELITY / "fixtures" / (label["id"] + ".md")).read_text()
                self.assertTrue(self.check(text, label["scenario"]))


if __name__ == "__main__":
    unittest.main()


class GateTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        import fidelity_gate
        self.gate = fidelity_gate
        from unittest.mock import patch
        calibrated = patch.object(judge, "calibrated_model", return_value="test-judge")
        calibrated.start()
        self.addCleanup(calibrated.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="fidelity-gate-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_folder(self, answer, status="completed", common=True, case="urgent-execution-started"):
        folder = self.root / "arm" / f"claude-{case}-run-01"
        folder.mkdir(parents=True)
        (folder / "result.json").write_text(json.dumps({
            "client": "claude", "case": case, "model": "claude-fable-5-1",
            "status": status, "common_loaded": common, "error": None if status == "completed" else "boom"}))
        (folder / "final.md").write_text(answer)
        (folder / "visible.md").write_text(answer)
        return folder

    def grade(self, folder, verdict):
        from unittest.mock import patch
        with patch.object(judge, "judge", return_value={"verdict": verdict, "votes": []}):
            return self.gate.grade_run(folder, 3, "fable")

    def test_clean_run_passes(self):
        self.assertEqual(self.grade(self.run_folder(STARTED_GOOD), "pass")["gate"], "pass")

    def test_judge_split_or_error_fails(self):
        for verdict in ("split", "error", "fail"):
            with self.subTest(verdict):
                folder = self.run_folder(STARTED_GOOD)
                self.assertEqual(self.grade(folder, verdict)["gate"], "fail")
                import shutil
                shutil.rmtree(folder)

    def test_contract_violation_fails_even_when_judge_passes(self):
        answer = STARTED_GOOD.replace("| Execution | reported started |", "| Execution | reported complete |")
        self.assertEqual(self.grade(self.run_folder(answer), "pass")["gate"], "fail")

    def test_wrong_output_format_for_the_question_fails(self):
        folder = self.run_folder(STARTED_GOOD, case="response-agreement-declined")
        row = self.grade(folder, "pass")
        self.assertIn("format_routing:focused", row["reasons"])

    def test_withholding_a_supplied_finding_fails(self):
        answer = ("## Candidates\n\nDana owns the ledger schema. Her agreement to join is not "
                  "supplied, so ask her before relying on it.\n")
        row = self.grade(self.run_folder(answer, case="response-agreement-declined"), "pass")
        self.assertIn("resolved:resolved_finding_missing:response-agreement-declined:declined",
                      row["reasons"])

    def test_graded_rows_record_the_vote_split_and_flagged_quotes(self):
        from unittest.mock import patch
        votes = [{"verdict": "pass", "failing": []},
                 {"verdict": "fail", "failing": [{"quote": "reported started"}]},
                 {"verdict": "pass", "failing": []}]
        with patch.object(judge, "judge", return_value={
                "verdict": "pass", "votes": votes, "retry_attempts": 1}):
            row = self.gate.grade_run(self.run_folder(STARTED_GOOD), 3, "fable")
        self.assertEqual(row["judge_votes"], {"pass": 2, "fail": 1})
        self.assertEqual(row["judge_quotes_flagged_by_any_vote"], ["reported started"])
        self.assertEqual(row["judge_retry_attempts"], 1)

    def test_skipped_shared_rules_fail(self):
        self.assertIn("common_rules_not_loaded", self.grade(self.run_folder(STARTED_GOOD, common=False), "pass")["reasons"])

    def test_incomplete_run_fails_without_judging(self):
        row = self.grade(self.run_folder("", status="error"), "pass")
        self.assertEqual(row["gate"], "fail")
        self.assertNotIn("judge", row)

    def test_judge_receives_progress_claims_as_well_as_final_answer(self):
        from unittest.mock import patch
        folder = self.run_folder(STARTED_GOOD)
        visible = "Unsupported production claim.\n\n" + STARTED_GOOD
        (folder / "visible.md").write_text(visible)
        with patch.object(judge, "judge", return_value={"verdict": "fail", "votes": []}) as caller:
            row = self.gate.grade_run(folder, 3, "fable")
        self.assertEqual(caller.call_args.args[0], visible)
        self.assertEqual(caller.call_args.kwargs["expected_model"], "test-judge")
        self.assertEqual(row["gate"], "fail")
