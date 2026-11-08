"""rc14: text-first reference mapping, user correction, persist and safe continuity."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

P = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("h3_prompt_composer_rc14", P / "__init__.py", submodule_search_locations=[str(P)])
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
from h3_prompt_composer_rc14 import nodes
from h3_prompt_composer_rc14.reference_roles import parse_overrides, make_reference_brief, resolve_reference_roles
from h3_prompt_composer_rc14.continuity import extract_scene_contract

class TestReferenceRoles(unittest.TestCase):
    def setUp(self):
        self.builder = nodes.H3DirectorRequestBuilder()
        self.raw = {
            "asset_analysis": [
                {"picture": 1, "primary_role": "character", "label": "Alex", "description": "A person with pink hair"},
                {"picture": 2, "primary_role": "environment", "label": "", "description": "living room"},
            ],
            "subjects": [{"subject": 1, "kind": "person", "source_pictures": [1], "description": "A woman", "importance": "primary"}],
            "intent": {"dominant_action": "she takes off her jacket"},
        }
        self.builder_args = dict(direction="Alex sits in the room. POV.", duration_seconds=5.2, picture_1="pic1", picture_2="pic2")

    def test_explicit_numbered_labels_and_guard_on_nonexistent_slot(self):
        parsed = parse_overrides("Picture 1: Alex (character)\nP2 = living room / location\nPicture 4: Wrong", [1, 2])
        self.assertEqual(parsed["1"], {"role": "character", "label": "Alex"})
        self.assertEqual(parsed["2"], {"role": "environment", "label": "living room"})
        self.assertNotIn("4", parsed)
        self.assertEqual(parse_overrides("AUTO", [1]), {})

    def test_user_direction_prepass_before_vision(self):
        result = self.builder.build(**self.builder_args)
        self.assertIn("REFERENCE ROLE PREPASS", result[1])
        self.assertLess(result[1].index("REFERENCE ROLE PREPASS"), result[1].index("CURRENT H3 REFERENCE IMAGE SLOTS") if "CURRENT H3 REFERENCE IMAGE SLOTS" in result[1] else result[1].index("CONNECTED REFERENCE IMAGE SLOTS"))
        ctx = json.loads(result[3])
        self.assertEqual(ctx["picture_slots"], [1, 2])
        self.assertEqual(ctx["reference_roles"], {"user_overrides": {}, "direction_bindings": {}})
        self.assertEqual(len(result[2]), 2)

    def test_free_form_user_name_only_from_direction_not_guess(self):
        _, _, _, ctx, *_ = self.builder.build(**self.builder_args)
        roles = resolve_reference_roles(json.loads(json.dumps(self.raw)), json.loads(ctx))
        self.assertEqual(roles[0]["label"], "Alex")
        self.assertEqual(roles[0]["source"], "auto: user prompt match")
        self.assertEqual(roles[1]["role"], "environment")
        self.assertFalse(roles[1]["label"])

    def test_explicit_user_override_wins_and_persists_through_snapshot_and_compose(self):
        input_kwargs = dict(self.builder_args)
        input_kwargs["reference_roles"] = "Picture 1: Alex (character)\nPicture 2: Green Living Room (location)"
        data = self.builder.build(**input_kwargs)
        ctx = json.loads(data[3])
        self.assertEqual(ctx["reference_roles"]["user_overrides"]["2"]["label"], "Green Living Room")
        snapshot = nodes.H3DirectorAnalysisSnapshot().snapshot(materialized=False, raw_analysis=json.dumps(self.raw), director_context=data[3])
        snap_ctx = json.loads(snapshot["result"][1])
        self.assertEqual(snap_ctx["reference_roles_resolved"][1]["source"], "user override")
        composed = nodes.H3DirectorAnalysisCompose().compose_request(*snapshot["result"][:2])
        norm = json.loads(composed["result"][2])
        new_ctx = json.loads(composed["result"][3])
        role2 = norm["reference_contract"]["picture_roles"][1]
        self.assertEqual(role2["label"], "Green Living Room")
        self.assertEqual(role2["role"], "environment")
        self.assertEqual(new_ctx["reference_roles_resolved"], norm["reference_contract"]["picture_roles"])
        self.assertIn("P2 Green Living Room", json.loads(composed["ui"]["director_reference_status"][0])["summary"])
        saved = extract_scene_contract(composed["result"][2], [])
        self.assertEqual(saved["picture_roles"][1]["label"], "Green Living Room")
        self.assertNotIn("takes off her jacket", json.dumps(saved))

    def test_direction_explicit_binding(self):
        result = self.builder.build(direction="Picture 2 shows living room. Alex is in Picture 1. She moves.", duration_seconds=5.2, picture_1="p1", picture_2="p2")
        brief = json.loads(result[3])["reference_roles"]
        self.assertEqual(brief["direction_bindings"]["1"]["label"], "Alex")
        self.assertEqual(brief["direction_bindings"]["2"]["role"], "environment")
        self.assertEqual(brief["direction_bindings"]["2"]["label"], "living room")

    def test_unknown_is_not_fabricated(self):
        data = self.builder.build(direction="POV. A person looks into the lens.", duration_seconds=5.2, picture_1="p1")
        roles = resolve_reference_roles({"asset_analysis": [{"picture": 1, "primary_role": "unknown", "description": "ambiguous collage"}]}, json.loads(data[3]))
        self.assertEqual(roles[0]["role"], "unknown")
        self.assertEqual(roles[0]["source"], "unresolved")

    def test_old_workflow_works_without_new_optional_widget(self):
        data = self.builder.build(direction="Hello", duration_seconds=5.2, picture_1="p1")
        self.assertIn("picture_slots", data[3])
        self.assertIn("reference_roles", nodes.H3DirectorRequestBuilder.INPUT_TYPES()["optional"])

    def test_target_perspective_and_end_keyframe_overrides(self):
        parsed = parse_overrides("""Picture 4: target perspective
Picture 3: end keyframe""", [3, 4])
        self.assertEqual(parsed["4"]["role"], "target_perspective")
        self.assertEqual(parsed["3"]["role"], "end_keyframe")

    def test_scene_contract_keeps_target_perspective_picture_role(self):
        analysis = {
            "reference_contract": {
                "picture_roles": [
                    {"picture": 4, "role": "target_perspective", "label": "Window-side end view", "source": "user override"},
                    {"picture": 3, "role": "end_keyframe", "label": "Exact last frame", "source": "user override"},
                ]
            },
            "asset_analysis": [],
            "subjects": []
        }
        saved = extract_scene_contract(json.dumps(analysis), [])
        roles = {item["picture"]: item["role"] for item in saved["picture_roles"]}
        self.assertEqual(roles[4], "target_perspective")
        self.assertEqual(roles[3], "end_keyframe")

if __name__ == "__main__": unittest.main()
