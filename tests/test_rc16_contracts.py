"""rc16: synthetic, public-safe reproductions of D/E/F regression classes.

No user-owned image, private character name, prompt or OBVPM Pro workflow is
included in this test module.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = "h3_prompt_composer_rc16_contract_tests"
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc16_contract_tests import nodes


def analysis(environment_subject=False):
    subjects = [
        {"subject": 1, "source_pictures": [1], "kind": "person", "description": "Actor A", "importance": "primary"},
        {"subject": 2, "source_pictures": [2], "kind": "person", "description": "Actor B", "importance": "primary"},
    ]
    if environment_subject:
        subjects.append({"subject": 3, "source_pictures": [3], "kind": "environment", "description": "A bright room", "importance": "supporting"})
    return {
        "asset_analysis": [
            {"picture": 1, "primary_role": "character", "description": "Actor A", "label": "Actor A"},
            {"picture": 2, "primary_role": "character", "description": "Actor B", "label": "Actor B"},
            {"picture": 3, "primary_role": "environment", "description": "Bright living room", "label": ""},
        ],
        "subjects": subjects,
        "intent": {
            "speech_request": {"required": True, "mode": "preserve", "language": "English",
                               "utterances": ["Actor A: Is it blue?", "Actor B: It is green."]}
        },
        "reference_strategy": {"subject_only_pictures": [1, 2], "soft_inspiration_pictures": [3]},
    }


def context():
    return json.dumps({
        "direction": "Actor A and Actor B speak in a bright living room.",
        "duration_seconds": 5.2, "picture_slots": [1, 2, 3], "operation": "new",
        "continuity_states": {}, "reference_roles": {"direction_bindings": {}, "user_overrides": {}},
    })


def prompt(location=True, environment_subject=False, speaker2=True, keyframe=False):
    defs = "<Subject 1> is Actor A in <Picture 1>.\n<Subject 2> is Actor B in <Picture 2>.\n"
    if environment_subject:
        defs += "<Subject 3> is the bright living room" + (" in <Picture 3>.\n" if location else ".\n")
    ret = ("<Subject 1> (appears in [Shot 1]): fully_preserved - source identity.\n"
           "<Subject 2> (appears in [Shot 1]): fully_preserved - source identity.\n")
    if environment_subject:
        ret += "<Subject 3> (appears in [Shot 1]): fully_preserved - source room.\n"
    loc = ("<Subject 3> surrounds the actors. " if environment_subject and location else
           "They sit in the room in <Picture 3>. " if location else
           "They sit on the rug. ")
    marker = "(S2) " if speaker2 else ""
    task = "keyframe completion + reference generation" if keyframe else "reference generation"
    return f"""subject_definitions:
{defs}
summary:
[{task}] A brief exchange.
retention_analysis:
{ret}
detailed_description:
[Shot 1] {loc}<Subject 1> (S1) asks, <d>[English] Is it blue?</d> <Subject 2> {marker}replies, <d>[English] It is green.</d>
overall_soundscape:
Quiet interior with dialogue.
non_diegetic_music:
N/A"""


class TestRC16Contracts(unittest.TestCase):
    def setUp(self):
        self.ctx = context()
        self.compose = nodes.H3DirectorAnalysisCompose()
        self.validate = nodes.H3DirectorResponseValidator()

    def composed(self, environment_subject=False, data=None, ctx=None):
        result = self.compose.compose_request(json.dumps(data or analysis(environment_subject)), ctx or self.ctx)["result"]
        return json.loads(result[2]), result[3], result[1]

    def problems(self, text, normalized, ctx):
        return self.validate.validate(text, json.dumps(normalized), ctx)[3]

    def test_reference_contract_requires_picture3_without_environment_subject(self):
        norm, ctx, composer_prompt = self.composed()
        self.assertEqual(norm["reference_contract"]["required_picture_bindings"], [
            {"picture": 1, "role": "character", "subjects": [1]},
            {"picture": 2, "role": "character", "subjects": [2]},
            {"picture": 3, "role": "environment", "subjects": []},
        ])
        self.assertIn("detailed_description cites <Picture 3>", composer_prompt)
        self.assertEqual(self.problems(prompt(), norm, ctx).startswith("PASS"), True)

    def test_vanilla_D_location_omission_is_no_longer_pass(self):
        norm, ctx, _ = self.composed()
        status = self.problems(prompt(location=False), norm, ctx)
        self.assertIn("environment reference missing", status)
        self.assertIn("<Picture 3>", status)

    def test_vanilla_E_environment_subject_not_bounded_is_no_longer_pass(self):
        norm, ctx, _ = self.composed(environment_subject=True)
        self.assertEqual(norm["reference_contract"]["allowed_subjects"][-1]["subject"], 3)
        status = self.problems(prompt(location=False, environment_subject=True), norm, ctx)
        self.assertIn("<Subject 3> must cite <Picture 3>", status)
        self.assertIn("not used in detailed_description", status)

    def test_environment_subject_bound_and_used_passes(self):
        norm, ctx, _ = self.composed(environment_subject=True)
        self.assertTrue(self.problems(prompt(environment_subject=True), norm, ctx).startswith("PASS"))

    def test_missing_second_speaker_id_normalized_before_validation(self):
        norm, ctx, _ = self.composed()
        result = self.validate.validate(prompt(speaker2=False), json.dumps(norm), ctx)
        self.assertTrue(result[3].startswith("PASS"))
        self.assertIn("AUTO-NORMALIZED", result[3])
        self.assertIn("<Subject 2> (S2) replies", result[1])

    def test_reused_id_for_two_subjects_rejected(self):
        norm, ctx, _ = self.composed()
        bad = prompt().replace("<Subject 2> (S2) replies", "<Subject 2> (S1) replies")
        self.assertIn("assigned to both", self.problems(bad, norm, ctx))

    def test_preserved_wording_and_order_checked(self):
        norm, ctx, _ = self.composed()
        bad = prompt().replace("It is green.", "It is red.")
        self.assertIn("preserved dialogue differs", self.problems(bad, norm, ctx))

    def test_unsupported_keyframe_prefix_rejected(self):
        norm, ctx, _ = self.composed()
        self.assertIn("no connected concrete keyframe", self.problems(prompt(keyframe=True), norm, ctx))
        self.assertIn("omit 'keyframe completion'", self.composed()[2])

    def test_end_keyframe_role_allows_keyframe_prefix_when_used(self):
        data = analysis()
        data["asset_analysis"].append({"picture": 4, "primary_role": "end_keyframe", "description": "last frame"})
        c = json.loads(context()); c["picture_slots"].append(4)
        norm, ctx, _ = self.composed(data=data, ctx=json.dumps(c))
        self.assertEqual(norm["reference_contract"]["concrete_keyframe_pictures"], [4])
        text = prompt(keyframe=True).replace("They sit in the room in <Picture 3>.", "They sit in the room in <Picture 3> and arrive at <Picture 4>.")
        self.assertTrue(self.problems(text, norm, ctx).startswith("PASS"))

    def test_target_perspective_does_not_authorize_keyframe_prefix(self):
        data = analysis()
        data["asset_analysis"].append({"picture": 4, "primary_role": "target_perspective", "description": "camera composition"})
        c = json.loads(context()); c["picture_slots"].append(4)
        norm, ctx, _ = self.composed(data=data, ctx=json.dumps(c))
        text = prompt(keyframe=True).replace("They sit in the room in <Picture 3>.", "They sit in the room in <Picture 3> and approach the view of <Picture 4>.")
        self.assertIn("no connected concrete keyframe", self.problems(text, norm, ctx))

    def test_nested_valid_fragment_in_truncated_json_rejected(self):
        malformed = ('{"asset_analysis": [{"picture": 1, "primary_role": "character"}], '
                     '"subjects": [{"subject": 1, "source_pictures": [1]}], "intent": {')
        with self.assertRaisesRegex(ValueError, "Incomplete or malformed"):
            nodes._extract_json_tolerant(malformed)
        with self.assertRaisesRegex(ValueError, "invalid"):
            nodes.H3DirectorAnalysisSnapshot().snapshot(False, raw_analysis=malformed, director_context=self.ctx)
        with self.assertRaisesRegex(ValueError, "malformed analysis JSON"):
            self.compose.compose_request(malformed, self.ctx)

    def test_frozen_manually_edited_fragment_is_rejected(self):
        bad = '"subjects": [{"subject": 1}]'
        with self.assertRaisesRegex(ValueError, "Frozen Analysis Snapshot"):
            nodes.H3DirectorAnalysisSnapshot().snapshot(True, snapshot_raw_analysis=bad, snapshot_director_context=self.ctx)

    def test_complete_fenced_json_still_works(self):
        raw = "```json\n" + json.dumps(analysis()) + "\n```"
        self.assertEqual(len(nodes._assert_analysis_contract(nodes._extract_json_tolerant(raw))["subjects"]), 2)

    def test_one_inner_object_is_rejected_as_analysis(self):
        with self.assertRaisesRegex(ValueError, "missing the root"):
            self.compose.compose_request('{"picture": 1, "primary_role": "character"}', self.ctx)

    def test_validator_preserves_existing_repair_path(self):
        norm, ctx, _ = self.composed()
        result = self.validate.validate(prompt(location=False, speaker2=False, keyframe=True), json.dumps(norm), ctx)
        self.assertTrue(result[3].startswith("FAIL"))
        self.assertIn("VALIDATION ERRORS:", result[6])
        self.assertIn("<Picture 3>", result[6])
        self.assertIn('"required_picture_bindings"', result[6])
        self.assertIn('"utterances"', result[6])
        self.assertEqual(
            result[1],
            prompt(location=False, speaker2=False, keyframe=True).replace(
                "<Subject 2> replies", "<Subject 2> (S2) replies"
            ),
        )


if __name__ == "__main__":
    unittest.main()
