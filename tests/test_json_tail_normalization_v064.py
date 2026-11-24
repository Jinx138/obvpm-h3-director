"""v0.6.4.dev4: strict JSON root with a single redundant closing-brace tolerance."""
from fixture_flavour import NEUTRAL_FLAVOUR, neutral_manifests
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = "h3_director_test_json_tail_v064"
spec = importlib.util.spec_from_file_location(
    NAME, PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_director_test_json_tail_v064.nodes import (
    _extract_json_tolerant, _assert_analysis_contract, H3DirectorAnalysisSnapshot
)


class JSONTailNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.obj = {
            "asset_analysis": [], "subjects": [], "intent": {},
            "reference_strategy": {"subject_only_pictures": [1, 2, 3, 4],
                                   "soft_inspiration_pictures": [5]},
            "director_notes": "An eight-second single continuous shot."
        }
        self.valid = json.dumps(self.obj)

    def test_valid_unchanged(self):
        self.assertEqual(_extract_json_tolerant(self.valid), self.obj)

    def test_exactly_one_redundant_brace(self):
        parsed = _extract_json_tolerant(self.valid + "\n}")
        self.assertEqual(_assert_analysis_contract(parsed), self.obj)

    def test_exactly_one_redundant_brace_in_code_fence(self):
        source = "```json\n" + self.valid + "\n}\n" + "```"
        self.assertEqual(_extract_json_tolerant(source), self.obj)

    def test_snapshot_can_capture_repaired_json(self):
        raw = self.valid + "\n}"
        context = json.dumps({"director_flavour": NEUTRAL_FLAVOUR, "director_skill_manifests": neutral_manifests(),
            "direction": "Single continuous shot", "picture_slots": [],
            "reference_roles": {}, "duration_seconds": 8.0,
            "operation": "new", "continuity": {}
        })
        snapshot = H3DirectorAnalysisSnapshot().snapshot(
            materialized=False, raw_analysis=raw, director_context=context)
        self.assertEqual(snapshot["result"][0], raw)

    def test_truncated_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Incomplete or malformed"):
            _extract_json_tolerant(self.valid[:-1])

    def test_two_extra_braces_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "trailing structured data"):
            _extract_json_tolerant(self.valid + "}}")

    def test_concatenated_json_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "trailing structured data"):
            _extract_json_tolerant(self.valid + "\n{}")

    def test_malformed_interior_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Incomplete or malformed"):
            _extract_json_tolerant('{"asset_analysis": [], "subjects": [ }')

    def test_extra_brace_with_prose_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "trailing structured data"):
            _extract_json_tolerant(self.valid + "} Other text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
