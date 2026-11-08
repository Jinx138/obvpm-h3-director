"""rc12 snapshot: unit-level lazy gating and two-pass interchange regression."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "h3_prompt_composer_rc12", PACKAGE / "__init__.py",
    submodule_search_locations=[str(PACKAGE)],
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
nodes = sys.modules["h3_prompt_composer_rc12.nodes"]


class TestAnalysisSnapshot(unittest.TestCase):
    def setUp(self):
        self.gate = nodes.H3DirectorAnalysisSnapshot()
        self.raw = json.dumps({
            "subjects": [{"subject": 1, "source_pictures": [1], "kind": "person"}],
            "asset_analysis": [],
            "intent": {"dominant_action": "steps forward"},
        })
        self.ctx = json.dumps({
            "direction": "Subject 1 steps forward",
            "picture_slots": [1], "duration_seconds": 5.2, "operation": "new",
            "continuity_states": {}, "continuity_note": "",
        })

    def test_frozen_snapshot_does_not_request_any_upstream_input(self):
        self.assertEqual(
            [], self.gate.check_lazy_status(materialized=True)
        )
        self.assertEqual(
            [], self.gate.check_lazy_status(materialized=True,
                                            raw_analysis=None, director_context=None)
        )

    def test_capture_requests_both_inputs(self):
        self.assertEqual(
            ["raw_analysis", "director_context"],
            self.gate.check_lazy_status(materialized=False),
        )
        self.assertEqual(
            ["director_context"],
            self.gate.check_lazy_status(materialized=False, raw_analysis=self.raw),
        )

    def test_capture_and_recompose_from_same_snapshot(self):
        capture = self.gate.snapshot(False, raw_analysis=self.raw,
                                     director_context=self.ctx)
        self.assertEqual(capture["result"][0], self.raw)
        self.assertEqual(json.loads(capture["result"][1])["direction"], "Subject 1 steps forward")
        snapshot_payload = json.loads(capture["ui"]["director_analysis_snapshot"][0])
        self.assertTrue(snapshot_payload["materialized"])
        self.assertEqual(snapshot_payload["snapshot_raw_analysis"], self.raw)
        self.assertEqual(json.loads(snapshot_payload["snapshot_director_context"])["reference_roles_resolved"][0]["role"], "unknown")
        reused = self.gate.snapshot(True,
                                    snapshot_raw_analysis=snapshot_payload["snapshot_raw_analysis"],
                                    snapshot_director_context=snapshot_payload["snapshot_director_context"])
        self.assertEqual(reused[:2], capture["result"][:2])
        composed_result = nodes.H3DirectorAnalysisCompose().compose_request(reused[0], reused[1])
        composed = composed_result["result"]
        self.assertIn("Subject 1 steps forward", composed[1])
        self.assertIn('"subject": 1', composed[2])
        self.assertEqual(json.loads(composed[3])["direction"], "Subject 1 steps forward")

    def test_invalid_capture_does_not_freeze(self):
        with self.assertRaisesRegex(ValueError, "JSON"):
            self.gate.snapshot(False, raw_analysis="not JSON", director_context=self.ctx)
        with self.assertRaisesRegex(ValueError, "Director Context"):
            self.gate.snapshot(False, raw_analysis=self.raw, director_context="xxx")

    def test_blank_frozen_snapshot_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, "empty stored"):
            self.gate.snapshot(True, snapshot_raw_analysis=self.raw,
                               snapshot_director_context="")

    def test_reset_control_has_no_generation_side_effects(self):
        reset_type = nodes.H3DirectorContextReset
        self.assertIn("H3DirectorContextReset", nodes.NODE_CLASS_MAPPINGS)
        self.assertEqual(reset_type.CATEGORY, "obvpm/director")
        self.assertEqual(reset_type.RETURN_TYPES, ())
        self.assertEqual(reset_type().noop(), ())
        self.assertFalse(getattr(reset_type, "OUTPUT_NODE", False))

    def test_cleared_snapshot_captures_fresh_context(self):
        # UI reset clears both saved strings and unfreezes, so no Alex/old
        # context is available to the backend until live inputs are resolved.
        fresh_ctx = json.dumps({"direction": "New scene in a spaceship",
                                "operation": "new", "picture_slots": [],
                                "duration_seconds": 5.2, "continuity_states": {}})
        self.assertEqual(
            ["raw_analysis", "director_context"],
            self.gate.check_lazy_status(materialized=False,
                                        snapshot_raw_analysis="",
                                        snapshot_director_context=""),
        )
        result = self.gate.snapshot(False, snapshot_raw_analysis="",
                                    snapshot_director_context="",
                                    raw_analysis=self.raw,
                                    director_context=fresh_ctx)
        state = json.loads(result["ui"]["director_analysis_snapshot"][0])
        self.assertEqual(json.loads(state["snapshot_director_context"])["direction"], "New scene in a spaceship")
        self.assertNotIn("Alex", state["snapshot_director_context"])

    def test_editor_remains_lazy_and_stable_id(self):
        self.assertEqual([], nodes.H3DirectorShotState.check_lazy_status(materialized=True))
        self.assertEqual(
            ["current_direction", "current_h3_prompt", "current_analysis"],
            nodes.H3DirectorShotState.check_lazy_status(materialized=False),
        )
        self.assertIn("H3DirectorAnalysisSnapshot", nodes.NODE_CLASS_MAPPINGS)
        self.assertIn("H3DirectorShotState", nodes.NODE_CLASS_MAPPINGS)
        self.assertEqual(nodes.NODE_DISPLAY_NAME_MAPPINGS["H3DirectorShotState"],
                         "H3 Director Shot Editor (obvpm)")
        self.assertFalse(getattr(nodes.H3DirectorAnalysisSnapshot, "OUTPUT_NODE", False))


if __name__ == "__main__":
    unittest.main()
