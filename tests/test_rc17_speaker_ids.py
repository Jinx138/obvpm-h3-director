"""rc17 synthetic speaker normalization regressions (public-safe)."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = "h3_prompt_composer_rc17_speaker_tests"
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc17_speaker_tests import nodes
from h3_prompt_composer_rc17_speaker_tests.speaker_ids import normalize_speaker_ids
from h3_prompt_composer_rc17_speaker_tests.validator import validate_h3_prompt


def analysis(utterances=None):
    return {
        "subjects": [
            {"subject": 3, "source_pictures": [1], "kind": "person", "name": "Aster", "description": "Aster: actor"},
            {"subject": 7, "source_pictures": [2], "kind": "person", "name": "Bryn", "description": "Bryn: actor"},
            {"subject": 8, "source_pictures": [3], "kind": "environment", "description": "studio"},
        ],
        "asset_analysis": [
            {"picture": 1, "label": "Aster", "primary_role": "character"},
            {"picture": 2, "label": "Bryn", "primary_role": "character"},
            {"picture": 3, "label": "studio", "primary_role": "environment"},
        ],
        "intent": {"speech_request": {
            "required": True,
            "mode": "preserve",
            "language": "English",
            "utterances": utterances or ["Bryn: First line.", "Aster: Second line."],
        }},
    }


def prompt(body):
    return ("subject_definitions:\n<Subject 3> is Aster in <Picture 1>.\n"
            "<Subject 7> is Bryn in <Picture 2>.\nsummary:\n[reference generation] Test.\n"
            "retention_analysis:\n<Subject 3> (appears in [Shot 1]): fully_preserved - known.\n"
            "<Subject 7> (appears in [Shot 1]): fully_preserved - known.\n"
            "detailed_description:\n[Shot 1] " + body + "\n"
            "overall_soundscape:\nRoom tone.\nnon_diegetic_music:\nN/A")


class TestRC17SpeakerIDs(unittest.TestCase):
    def test_reversed_subject_order_yields_vocal_order(self):
        original = prompt(
            "<Subject 7> looks up and asks, <d>[English] First line.</d> "
            "<Subject 3> responds, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual(count, 2)
        self.assertIn("<Subject 7> (S1) looks up", fixed)
        self.assertIn("<Subject 3> (S2) responds", fixed)
        self.assertTrue(validate_h3_prompt(fixed, [1, 2], allowed_subjects=[3, 7], expected_speech=analysis()["intent"]["speech_request"]) == [])

    def test_name_authority_disambiguates_multi_subject_lead(self):
        original = prompt(
            "<Subject 7> looks toward <Subject 3> and asks, <d>[English] First line.</d> "
            "<Subject 3> looks back toward <Subject 7> and answers, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual(count, 2)
        self.assertIn("<Subject 7> (S1) looks toward <Subject 3>", fixed)
        self.assertIn("<Subject 3> (S2) looks back toward <Subject 7>", fixed)
        self.assertNotIn("<Subject 8> (S", fixed)

    def test_repeated_speaker_reuses_stable_id(self):
        data = analysis(["Bryn: One.", "Aster: Two.", "Bryn: Three."])
        original = prompt(
            "<Subject 7> says, <d>[English] One.</d> "
            "<Subject 3> answers, <d>[English] Two.</d> "
            "<Subject 7> adds, <d>[English] Three.</d>"
        )
        fixed, count = normalize_speaker_ids(original, data)
        self.assertEqual(count, 3)
        self.assertEqual(fixed.count("(S1)"), 2)
        self.assertEqual(fixed.count("(S2)"), 1)
        self.assertEqual(fixed.count("<d>"), 3)

    def test_already_correct_passes_through_byte_exact(self):
        original = prompt(
            "<Subject 7> (S1) says, <d>[English] First line.</d> "
            "<Subject 3> (S2) answers, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual((fixed, count), (original, 0))

    def test_one_existing_one_missing_adds_only_missing(self):
        original = prompt(
            "<Subject 7> (S1) says, <d>[English] First line.</d> "
            "<Subject 3> answers, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual(count, 1)
        self.assertEqual(fixed.count("(S1)"), 1)
        self.assertIn("<Subject 3> (S2) answers", fixed)

    def test_wrong_existing_id_is_not_overwritten(self):
        original = prompt(
            "<Subject 7> (S2) says, <d>[English] First line.</d> "
            "<Subject 3> answers, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual((fixed, count), (original, 0))

    def test_user_dialogue_mismatch_no_silent_fix(self):
        original = prompt(
            "<Subject 7> asks, <d>[English] Different words.</d> "
            "<Subject 3> replies, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual((fixed, count), (original, 0))

    def test_unnamed_ambiguous_speaker_untouched(self):
        data = analysis()
        data["intent"]["speech_request"] = {"mode": "none"}
        original = prompt(
            "<Subject 7> greets <Subject 3>, <d>[English] First line.</d> "
            "<Subject 3> replies, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, data)
        self.assertEqual((fixed, count), (original, 0))

    def test_environment_is_not_speaker(self):
        data = analysis()
        data["intent"]["speech_request"] = {"mode": "none"}
        original = prompt("<Subject 8> hums, <d>[English] Hello.</d>")
        fixed, count = normalize_speaker_ids(original, data)
        self.assertEqual((fixed, count), (original, 0))

    def test_offscreen_unmapped_name_no_assigned_subject(self):
        data = analysis(["Offscreen visitor: First line.", "Aster: Second line."])
        original = prompt(
            "<Subject 7> looks around, <d>[English] First line.</d> "
            "<Subject 3> replies, <d>[English] Second line.</d>"
        )
        fixed, count = normalize_speaker_ids(original, data)
        self.assertEqual((fixed, count), (original, 0))

    def test_no_vocal_events_untouched(self):
        original = prompt("<Subject 7> sits in silence.")
        self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))

    def test_materialized_editor_bypasses_live_validator(self):
        editor = nodes.H3DirectorShotState()
        stored = prompt("<Subject 7> asks, <d>[English] First line.</d>")
        self.assertEqual(editor.check_lazy_status(materialized=True), [])
        returned = editor.store(materialized=True, shot_direction="Edited", shot_h3_prompt=stored,
                                shot_analysis="The user's own notes")
        self.assertEqual(returned, (stored, "Edited", "The user's own notes"))

    def test_repair_outputs_unmodified_when_normalization_passes(self):
        data = analysis()
        data["reference_contract"] = {
            "allowed_subjects": [{"subject": 3}, {"subject": 7}],
            "picture_roles": [{"picture": 1, "role": "character"}, {"picture": 2, "role": "character"}],
            "required_picture_bindings": [],
        }
        context = json.dumps({"direction": "Two actors have a short conversation", "picture_slots": [1, 2], "operation": "new"})
        original = prompt("<Subject 7> says, <d>[English] First line.</d> <Subject 3> says, <d>[English] Second line.</d>")
        result = nodes.H3DirectorResponseValidator().validate(original, json.dumps(data), context)
        self.assertTrue(result[3].startswith("PASS"), result[3])
        self.assertIn("AUTO-NORMALIZED", result[3])
        self.assertEqual(result[5], "")
        self.assertEqual(result[6], "")
        self.assertEqual(result[1].count("(S1)"), 1)
        self.assertEqual(result[1].count("(S2)"), 1)
        self.assertEqual(result[1].count("<d>"), 2)


if __name__ == "__main__":
    unittest.main()
