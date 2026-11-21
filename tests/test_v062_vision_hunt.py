"""v0.6.2-dev1: per-image conservative vision cap + independent hunt diagnostics."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import torch

ROOT = Path(__file__).resolve().parents[1]
NAME = 'director_v062_vision_hunt_test'
spec = importlib.util.spec_from_file_location(NAME, ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from director_v062_vision_hunt_test.nodes import (H3DirectorRequestBuilder,
                                                   VISION_MAX_PIXELS,
                                                   _limit_vision_image,
                                                   _normalize_hunting)

class VisionCapTests(unittest.TestCase):
    def test_large_image_reduced_without_modifying_source(self):
        original = torch.rand((1, 1200, 1600, 3), dtype=torch.float32)
        copy = original.clone()
        out, info = _limit_vision_image(original)
        self.assertTrue(info['scaled'])
        self.assertLessEqual(out.shape[1] * out.shape[2], VISION_MAX_PIXELS)
        self.assertEqual(out.shape[0], 1)
        self.assertEqual(out.shape[-1], 3)
        self.assertEqual(out.dtype, original.dtype)
        self.assertTrue(torch.equal(original, copy), 'the connected H3 source image must not be modified')
        self.assertNotEqual(out.data_ptr(), original.data_ptr())
        self.assertAlmostEqual(out.shape[2]/out.shape[1], 1600/1200, delta=.004)

    def test_small_and_exact_cap_are_never_upscaled(self):
        for hw in ((500, 600), (1000, 1000), (200, 160)):
            original = torch.zeros(1, hw[0], hw[1], 3)
            out, info = _limit_vision_image(original)
            self.assertIs(out, original)
            self.assertFalse(info['scaled'])

    def test_batch_images_each_under_limit(self):
        original = torch.ones(2, 1040, 1040, 3)
        out, info = _limit_vision_image(original)
        self.assertEqual(out.shape[0], 2)
        self.assertLessEqual(out.shape[1]*out.shape[2], 1_000_000)
        self.assertEqual(original.shape, (2, 1040, 1040, 3))

    def test_sparse_references_have_correct_slots_after_vision_scaling(self):
        a = torch.rand((1, 1150, 1200, 3))
        b = torch.rand((1, 540, 780, 3))
        result = H3DirectorRequestBuilder().build('The two subjects move.', 5.2,
            picture_1=a, picture_7=b, length=124, hunting=False)['result']
        images = result[2]
        ctx = json.loads(result[3])
        continuity = json.loads(result[5])
        self.assertEqual(ctx['picture_slots'], [1,7])
        self.assertEqual(len(images), 2)
        self.assertLessEqual(images[0].shape[1] * images[0].shape[2], VISION_MAX_PIXELS)
        self.assertIs(images[1], b)
        self.assertEqual(continuity['vision_input_scaling']['images'][0]['source'], 'picture_1')
        self.assertEqual(continuity['vision_input_scaling']['images'][1]['source'], 'picture_7')
        self.assertEqual(ctx['duration_frames'], 124)
        self.assertEqual(continuity['hunting'], False)
        self.assertEqual(continuity['warnings'], [])

    def test_unchanged_picture_transport_with_unconnected_slots(self):
        r = H3DirectorRequestBuilder().build('No images connected.',5.2)
        self.assertEqual(r['result'][2], [])
        self.assertEqual(json.loads(r['result'][3])['picture_slots'], [])
        self.assertEqual(json.loads(r['result'][5])['vision_input_scaling']['images'], [])

    def test_picture_numbers_not_changed_by_hunt_meta(self):
        a = torch.zeros(1, 512, 512, 3)
        raw = H3DirectorRequestBuilder().build('Picture test.',5.2,picture_4=a,
                                               hunting='True',hunt_count='1')
        data = raw['result']
        continuity = json.loads(data[5])
        self.assertEqual(json.loads(data[3])['picture_slots'],[4])
        self.assertIs(data[2][0],a)
        self.assertIs(continuity['hunting'],True)
        self.assertEqual(continuity['hunt_count'],1)
        self.assertTrue(any('Seed Hunt' in message for message in continuity['warnings']))

class HuntSignalTests(unittest.TestCase):
    def test_hunting_truth_values(self):
        for raw, want in ((True,True),(False,False),(1,True),(0,False),
                          ('True',True),('FALSE',False),('off',False),
                          ('yes',True),(None,None),('maybe',None)):
            with self.subTest(raw=raw):
                self.assertIs(_normalize_hunting(raw),want)
    def test_optional_schema_extends_after_length_and_picture_nine(self):
        keys=list(H3DirectorRequestBuilder.INPUT_TYPES()['optional'])
        self.assertEqual(keys[3:6], ['length','hunting','hunt_count'])
        self.assertEqual(keys.index('hunt_count')+1,keys.index('picture_1'))
        self.assertEqual(H3DirectorRequestBuilder.INPUT_TYPES()['optional']['hunting'][0],'*')
        self.assertEqual(H3DirectorRequestBuilder.RETURN_NAMES[2],'llm_images')

if __name__=='__main__': unittest.main()
