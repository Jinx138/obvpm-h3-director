"""rc24 P0/P1 regressions: A1 transport and up to nine stable one-based pictures."""
from fixture_flavour import NEUTRAL_FLAVOUR
import importlib.util
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "director_rc24_media_test"
spec = importlib.util.spec_from_file_location(NAME, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
mod = importlib.util.module_from_spec(spec)
sys.modules[NAME] = mod
spec.loader.exec_module(mod)
from director_rc24_media_test.continuity import classify_pin_specs
from director_rc24_media_test.nodes import H3DirectorRequestBuilder

# The Builder now emits ComfyUI history UI metadata alongside its original
# six data outputs. These legacy tests exercise the original data contract.
class _BuilderResultsOnly(H3DirectorRequestBuilder):
    def build(self, *args, **kwargs):
        return super().build(*args, **kwargs)["result"]

H3DirectorRequestBuilder = _BuilderResultsOnly

A1 = {"place": "track", "kind": "pinned_audio", "track": "A1", "items": []}
BEFORE = {"place": "before", "source_start": 0, "source_frames": 124, "source_path": "unused.mp4"}
AFTER = {"place": "after", "source_start": 0, "source_frames": 124, "source_path": "unused.mp4"}


class TestA1Compatibility(unittest.TestCase):
    def test_audio_is_not_a_video_endpoint(self):
        for pins, expected, count in (
            ([], "new", 0),
            ([A1], "new", 0),
            ([BEFORE, A1], "extend", 1),
            ([A1, AFTER], "prepend", 1),
            ([A1, BEFORE, AFTER], "bridge", 2),
            ([BEFORE, AFTER, A1, A1], "bridge", 2),
        ):
            with self.subTest(pins=pins):
                result = classify_pin_specs(pins)
                self.assertEqual(result["operation"], expected)
                self.assertEqual(result["pin_count"], count)
                self.assertEqual(result["audio_track_count"], sum(p is A1 for p in pins))
                self.assertEqual(result["warnings"], [])

    def test_unknown_or_duplicate_video_pins_still_fail_closed(self):
        pins = [BEFORE, {"place": "sideways"}, A1]
        bad = classify_pin_specs(pins)
        self.assertEqual(bad["operation"], "new")
        self.assertTrue(bad["warnings"])
        dupe = classify_pin_specs([BEFORE, BEFORE, A1])
        self.assertEqual(dupe["operation"], "new")
        self.assertTrue(dupe["warnings"])


class TestReservedInputsAndPictureNumbering(unittest.TestCase):
    def test_schema_keeps_old_widgets_and_exposes_nine_stable_pictures(self):
        spec = H3DirectorRequestBuilder.INPUT_TYPES()
        self.assertEqual(list(spec["required"]), ["flavour_profile", "direction", "reference_roles", "duration_seconds"])
        # OBVPM's Unbundle declares dynamic outputs as '*'; the Director
        # must accept that connector without changing the pin payload.
        self.assertEqual(spec["optional"]["pin_specs"][0], "*")
        self.assertTrue(H3DirectorRequestBuilder.VALIDATE_INPUTS({"pin_specs": "*"}))
        self.assertEqual(spec["optional"]["audio_in"][0], "AUDIO")
        self.assertEqual(spec["optional"]["video_in"][0], "VIDEO")
        self.assertEqual(spec["optional"]["length"][0], "*")
        self.assertNotIn("socketless", spec["required"]["duration_seconds"][1])
        self.assertIn("Unbundle", spec["optional"]["length"][1]["tooltip"])
        for i in range(1, 10):
            self.assertEqual(spec["optional"][f"picture_{i}"][0], "IMAGE")
        self.assertEqual(spec["required"]["reference_roles"][0], "STRING")

    def test_example_graph_has_no_duration_output_and_preserves_restore_group(self):
        example = json.loads((ROOT / 'examples' / 'H3-Director-Core-Workspace.json').read_text())
        builder = next(n for n in example['nodes'] if n['type'] == 'H3DirectorRequestBuilder')
        self.assertEqual([o['name'] for o in builder['outputs']],
                         list(H3DirectorRequestBuilder.RETURN_NAMES))
        self.assertEqual([w for w in builder['widgets_values'][:3]], ['', '', 5.2])
        self.assertIn('Director Prompt [restore]', [g['title'] for g in example['groups']])
        core = example['definitions']['subgraphs'][0]
        self.assertEqual(len([n for n in core['nodes'] if n['type'] == 'LlamaCppMtmd_PrefillProfile']), 2)
        names = [i['name'] for i in builder['inputs']]
        self.assertIn('length', names)
        self.assertNotIn('total_frames', names)
        self.assertIn('duration_seconds', names)

    def test_nine_images_preserve_picture_indices_and_transport_order(self):
        images = [object() for _ in range(9)]
        result = H3DirectorRequestBuilder().build("Nine picture reference test.", 5.2, flavour_profile=NEUTRAL_FLAVOUR, **{
            f"picture_{i + 1}": image for i, image in enumerate(images)
        })
        self.assertEqual(result[2], images)
        ctx = json.loads(result[3])
        self.assertEqual(ctx["picture_slots"], list(range(1, 10)))
        self.assertEqual(len(result), 6)
        self.assertEqual(json.loads(result[3])["duration_seconds"], 5.2)
        self.assertIn("Picture 9", result[1])

    def test_sparse_pictures_are_not_renumbered(self):
        first, ninth = object(), object()
        out = H3DirectorRequestBuilder().build("Two images.", 8.4, flavour_profile=NEUTRAL_FLAVOUR,
            picture_1=first, picture_9=ninth)
        self.assertEqual(out[2], [first, ninth])
        self.assertEqual(json.loads(out[3])["picture_slots"], [1, 9])

    def test_timeline_frame_length_is_authoritative_at_24fps(self):
        for frames in (22, 39, 124, 157, 192, 209):
            with self.subTest(frames=frames):
                result = H3DirectorRequestBuilder().build(
                    "Timeline length test.", 5.2, flavour_profile=NEUTRAL_FLAVOUR, length=frames,
                )
                ctx = json.loads(result[3])
                self.assertEqual(ctx["duration_frames"], frames)
                self.assertEqual(ctx["duration_source"], "timeline_length_frames")
                self.assertAlmostEqual(ctx["duration_seconds"], frames / 24.0)
                self.assertIn(f"{frames / 24.0:.2f}", result[1])

    def test_legacy_total_frames_keyword_still_accepted(self):
        result = H3DirectorRequestBuilder().build("UI4 old input.", 5.2, flavour_profile=NEUTRAL_FLAVOUR, total_frames=124)
        ctx = json.loads(result[3])
        self.assertEqual(ctx["duration_frames"], 124)
        self.assertAlmostEqual(ctx["duration_seconds"], 124 / 24)

    def test_without_timeline_frames_duration_widget_is_fallback(self):
        result = H3DirectorRequestBuilder().build("Standalone.", 8.2, flavour_profile=NEUTRAL_FLAVOUR)
        ctx = json.loads(result[3])
        self.assertEqual(ctx["duration_seconds"], 8.2)
        self.assertNotIn("duration_frames", ctx)
        self.assertNotIn("duration_source", ctx)

    def test_invalid_total_frames_fails_instead_of_silent_fallback(self):
        for value in (0, -1, 1.5, "foo", float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                H3DirectorRequestBuilder().build("Invalid.", 5.2, flavour_profile=NEUTRAL_FLAVOUR,
                                                 length=value)

    def test_reserved_media_does_not_trigger_media_analysis(self):
        audio, video = object(), object()
        base = H3DirectorRequestBuilder().build("An evening scene.", 5.2, flavour_profile=NEUTRAL_FLAVOUR)
        with_media = H3DirectorRequestBuilder().build("An evening scene.", 5.2, flavour_profile=NEUTRAL_FLAVOUR,
            audio_in=audio, video_in=video)
        self.assertEqual(base, with_media)


if __name__ == "__main__":
    unittest.main()
