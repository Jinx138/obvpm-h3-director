"""v0.6.3-dev1: timing priority, stable sockets, portable example integrity."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'director_v063_portable_test'
spec = importlib.util.spec_from_file_location(NAME, ROOT / '__init__.py',
                                          submodule_search_locations=[str(ROOT)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from director_v063_portable_test.nodes import H3DirectorRequestBuilder

class StableSocketContracts(unittest.TestCase):
    def test_duration_is_connectable_float_and_tooltips_explain_priority(self):
        spec = H3DirectorRequestBuilder.INPUT_TYPES()
        dtype, options = spec['required']['duration_seconds']
        self.assertEqual(dtype, 'FLOAT')
        self.assertFalse(options.get('socketless', False))
        self.assertIn('connect', options['tooltip'])
        self.assertIn('priority', options['tooltip'])
        fixed = list(spec['optional'])
        self.assertEqual(fixed[:3], ['pin_specs','audio_in','video_in'])
        self.assertEqual(fixed[3:6], ['length','hunting','hunt_count'])
        self.assertEqual(fixed[6:], [f'picture_{i}' for i in range(1, 10)])
        self.assertIn('priority', spec['optional']['length'][1]['tooltip'])
        for k in ('hunting','hunt_count'):
            self.assertIn('diagnostic', spec['optional'][k][1]['tooltip'].lower())

    def test_connected_duration_and_widget_share_backend_value(self):
        for seconds in (3.7, 5.2, 7.0, 11.5):
            payload = H3DirectorRequestBuilder().build('Vanilla H3 shot.', seconds)
            ctx = json.loads(payload['result'][3])
            self.assertEqual(ctx['duration_seconds'], seconds)
            self.assertNotIn('duration_frames', ctx)

    def test_length_always_overrides_duration(self):
        payload = H3DirectorRequestBuilder().build('OBVPM shot.', 12.5,
                                                   length=124, hunting=False,
                                                   hunt_count=1)
        ctx = json.loads(payload['result'][3])
        self.assertAlmostEqual(ctx['duration_seconds'], 124/24)
        self.assertEqual(ctx['duration_frames'], 124)
        self.assertEqual(ctx['duration_source'], 'timeline_length_frames')

    def test_portable_workflow_layout_and_no_saved_freeze(self):
        root = ROOT / 'examples'
        self.assertFalse((root / 'H3-Director-Recipe-MVP.json').exists())
        data = json.loads((root / 'H3-Director-Portable-Workspace.json').read_text())
        self.assertEqual((len(data['nodes']),len(data['links'])),(13,23))
        builder = next(n for n in data['nodes'] if n['type']=='H3DirectorRequestBuilder')
        self.assertEqual([x['name'] for x in builder['inputs'][:7]],
                         ['pin_specs','audio_in','video_in','length','duration_seconds','hunting','hunt_count'])
        self.assertEqual(builder['inputs'][7]['name'],'picture_1')
        self.assertEqual(builder['inputs'][4]['type'],'FLOAT')
        self.assertIsNone(builder['inputs'][4]['link'])
        nodes = {n['id']:n for n in data['nodes']}
        self.assertEqual(len([n for n in nodes.values() if n['type']=='LlamaCppMtmd_PrefillProfile']),1)
        for n in nodes.values():
            if n['type'] in ('H3DirectorShotState','H3DirectorAnalysisSnapshot'):
                self.assertIs(n['widgets_values_named']['materialized'],False)
                self.assertIs(n['widgets_values'][0],False)
            if n['type']=='OllamaImageList_LlamaCppProfiledGenerate':
                self.assertEqual(n['widgets_values_named']['seed'],42)
                self.assertEqual(n['widgets_values_named']['control_after_generate'],'fixed')
                self.assertEqual(n['widgets_values_named']['stop'],'')
                self.assertEqual(n['widgets_values'][6:9],[42,'fixed',''])
        for link in data['links']:
            link_id, origin, origin_slot, target, target_slot, *_ = link
            self.assertEqual(nodes[target]['inputs'][target_slot]['link'],link_id)
            self.assertIn(link_id,nodes[origin]['outputs'][origin_slot]['links'])

if __name__=='__main__':
    unittest.main()
