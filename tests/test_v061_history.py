"""Request Builder execution-result UI history is separate from H3 prompt data."""
from fixture_flavour import NEUTRAL_FLAVOUR
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "director_v061_history_test"
spec = importlib.util.spec_from_file_location(NAME, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
mod = importlib.util.module_from_spec(spec)
sys.modules[NAME] = mod
spec.loader.exec_module(mod)
from director_v061_history_test.nodes import H3DirectorRequestBuilder


class HistoryEmissionTests(unittest.TestCase):
    def test_execution_emits_exact_input_pair_and_retains_six_outputs(self):
        original = "  Aster enters.  \n  "
        roles = "Picture 1: Aster (character)\nPicture 3: room (location)\n"
        image = object()
        returned = H3DirectorRequestBuilder().build(original, 5.2, flavour_profile=NEUTRAL_FLAVOUR, reference_roles=roles, picture_1=image)
        self.assertEqual(set(returned), {"ui", "result"})
        ui_pair = json.loads(returned["ui"]["director_request_history"][0])
        self.assertEqual(ui_pair, {"direction": original, "reference_roles": roles})
        result = returned["result"]
        self.assertEqual(len(result), 6)
        self.assertEqual(result[2], [image])
        self.assertEqual(result[4], "Aster enters.")
        self.assertEqual(json.loads(result[3])["direction"], "Aster enters.")
        self.assertNotIn("director_request_history", json.loads(result[3]))

    def test_history_metadata_does_not_include_media_or_timeline(self):
        image, audio, video = object(), object(), object()
        returned = H3DirectorRequestBuilder().build(
            "Aster turns", 5.2, flavour_profile=NEUTRAL_FLAVOUR, picture_2=image, audio_in=audio, video_in=video,
            reference_roles="Picture 2: Aster (character)",
        )
        self.assertEqual(json.loads(returned["ui"]["director_request_history"][0]), {
            "direction": "Aster turns", "reference_roles": "Picture 2: Aster (character)",
        })
        self.assertEqual(json.loads(returned["result"][3])["picture_slots"], [2])


if __name__ == "__main__":
    unittest.main()
