"""Mechanism unit tests on an explicitly synthetic eight-state fixture."""

import unittest
from itertools import combinations

from verification_probe import (
    Check, Evidence, UNIVERSE, Verifier, World, deterministic_check,
    guard_counterexamples, next_check, opposite_pairs,
)


def evidence(event="e1", predicate="visible_clear", observed=True, seq=0,
             source="photo-1", device="toy-1", grade="fixture_verified"):
    return Evidence(event, source, device, predicate, observed, seq, grade)


class VerificationProbeTests(unittest.TestCase):
    def test_clean_appearance_does_not_prove_function(self):
        verifier = Verifier()
        verifier.add_evidence(evidence())
        self.assertEqual(len(verifier.belief()), 4)
        self.assertEqual(len(opposite_pairs(verifier.belief())), 3)
        self.assertEqual(verifier.closure_grade(), "NOT_VERIFIED")

    def test_reported_action_does_not_assume_execution_success(self):
        verifier = Verifier({World(False, True, True)})
        verifier.record_action("clean", frozenset({"visible_clear", "seated_ok"}))
        self.assertEqual(verifier.belief(), frozenset({
            World(False, False, True), World(False, True, True),
            World(True, False, True), World(True, True, True),
        }))
        self.assertEqual(verifier.closure_grade(), "NOT_VERIFIED")

    def test_only_affected_evidence_is_invalidated(self):
        verifier = Verifier()
        verifier.add_evidence(evidence())
        verifier.add_evidence(evidence("identity", "model", "SYNTHETIC_DEVICE"))
        verifier.add_evidence(evidence("seated", "seated_ok"))
        verifier.record_action("a1", frozenset({"visible_clear"}))
        self.assertEqual({item.event_id for item in verifier.active()}, {"identity", "seated"})

    def test_functional_evidence_expires_after_relevant_action(self):
        verifier = Verifier()
        verifier.add_evidence(evidence(predicate="function_ok"))
        self.assertEqual(verifier.closure_grade(), "MODEL_SUPPORTED_IN_FIXTURE")
        verifier.record_action("a1", frozenset({"seated_ok"}))
        self.assertEqual(verifier.closure_grade(), "NOT_VERIFIED")

    def test_reuploading_old_photo_does_not_refresh_capture_order(self):
        verifier = Verifier()
        verifier.record_action("a1", frozenset({"visible_clear"}))
        verifier.add_evidence(evidence(event="new-upload-id", seq=0))
        self.assertEqual(verifier.active(), ())

    def test_unknown_capture_order_is_not_a_current_observation(self):
        verifier = Verifier()
        verifier.add_evidence(evidence(seq=None))
        self.assertEqual(verifier.belief(), UNIVERSE)

    def test_wrong_device_and_future_sequence_are_not_accepted(self):
        verifier = Verifier()
        verifier.add_evidence(evidence(device="toy-2"))
        verifier.add_evidence(evidence("future", seq=2))
        self.assertEqual(verifier.active(), ())

    def test_photo_and_ocr_are_not_independent_sources(self):
        verifier = Verifier()
        verifier.add_evidence(evidence("photo"))
        verifier.add_evidence(evidence("ocr"))
        self.assertEqual(verifier.source_group_count(), 1)
        self.assertEqual(len(verifier.belief()), 4)

    def test_candidate_model_output_and_user_report_are_not_verified(self):
        verifier = Verifier()
        verifier.add_evidence(evidence(predicate="function_ok", grade="vlm_candidate"))
        verifier.add_evidence(evidence("report", "function_ok", grade="user_report"))
        self.assertEqual(verifier.belief(), UNIVERSE)
        self.assertEqual(verifier.closure_grade(), "NOT_VERIFIED")

    def test_contradiction_cannot_pass_through_empty_set(self):
        verifier = Verifier()
        verifier.add_evidence(evidence("positive", "function_ok", True))
        verifier.add_evidence(evidence("negative", "function_ok", False, source="test-2"))
        self.assertEqual(verifier.belief(), frozenset())
        self.assertEqual(verifier.closure_grade(), "CONFLICT")
        with self.assertRaises(ValueError):
            verifier.record_action("a1", frozenset({"visible_clear"}))

    def test_unknown_scope_blocks_positive_fixture_result(self):
        verifier = Verifier()
        verifier.add_evidence(evidence(predicate="function_ok"))
        verifier.out_of_scope = True
        self.assertEqual(verifier.closure_grade(), "OUT_OF_SCOPE")

    def test_component_observations_cannot_replace_functional_contract(self):
        verifier = Verifier()
        for predicate in ("visible_clear", "seated_ok", "other_ok"):
            verifier.add_evidence(evidence(predicate, predicate))
        self.assertEqual(verifier.belief(), frozenset({World(True, True, True)}))
        self.assertEqual(verifier.closure_grade(), "NOT_VERIFIED")

    def test_duplicate_events_are_idempotent(self):
        verifier = Verifier()
        item = evidence()
        verifier.add_evidence(item)
        verifier.add_evidence(item)
        self.assertEqual(len(verifier.evidence), 1)
        verifier.record_action("a1", frozenset({"visible_clear"}))
        first_belief = verifier.belief()
        verifier.record_action("a1", frozenset({"visible_clear"}))
        self.assertEqual(verifier.seq, 1)
        self.assertEqual(verifier.belief(), first_belief)
        with self.assertRaises(ValueError):
            verifier.add_evidence(evidence(observed=False))

    def test_cross_type_event_id_collision_is_rejected(self):
        verifier = Verifier()
        verifier.add_evidence(evidence())
        with self.assertRaises(ValueError):
            verifier.record_action("e1", frozenset({"visible_clear"}))

    def test_same_appearance_opposite_outcome_requires_functional_check(self):
        states = frozenset({World(True, True, True), World(True, True, False)})
        checks = (deterministic_check("another_photo", "visible_clear", 1),
                  deterministic_check("functional_trial", "function_ok", 3))
        self.assertEqual(next_check(states, checks), "functional_trial")

    def test_unavailable_or_uninformative_checks_return_none(self):
        states = frozenset({World(True, True, True), World(True, True, False)})
        checks = (deterministic_check("another_photo", "visible_clear"),
                  deterministic_check("functional_trial", "function_ok", available=False))
        self.assertIsNone(next_check(states, checks))

    def test_ambiguous_observation_model_is_not_treated_as_certain(self):
        states = frozenset({World(True, True, True), World(True, True, False)})
        noisy = Check("noisy", 1, lambda world: frozenset({"pass", "fail"}))
        self.assertIsNone(next_check(states, (noisy,)))

    def test_mutating_check_is_not_used_as_passive_discriminator(self):
        states = frozenset({World(True, True, True), World(True, True, False)})
        mutating = Check("repair_and_test", 1,
                         lambda world: frozenset({str(world.function_ok)}),
                         mutates_state=True)
        self.assertIsNone(next_check(states, (mutating,)))

    def test_offline_guard_audit_returns_counterexamples(self):
        self.assertEqual(len(guard_counterexamples({"visible_clear": True})), 3)
        self.assertEqual(guard_counterexamples({"function_ok": True}), ())

    def test_all_255_nonempty_beliefs_choose_informative_fixture_test(self):
        worlds = sorted(UNIVERSE)
        check = deterministic_check("functional_trial", "function_ok")
        count = 0
        for size in range(1, len(worlds) + 1):
            for subset in combinations(worlds, size):
                states = frozenset(subset)
                expected = "functional_trial" if opposite_pairs(states) else None
                self.assertEqual(next_check(states, (check,)), expected)
                count += 1
        self.assertEqual(count, 255)


if __name__ == "__main__":
    unittest.main(verbosity=2)
