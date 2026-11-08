"""rc22 delivery-contract regressions using synthetic, public-safe assets."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = 'h3_prompt_composer_rc22_tests'
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / '__init__.py',
    submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc22_tests.prompt_skill import (
    _composer_delivery_contract, _delivery_speaker_subject, composer_user_prompt,
)


def sample():
    return {
        'asset_analysis': [
            {'picture': 1, 'primary_role': 'character', 'label': '',
             'description': 'An older engineer with gray hair in a blue jacket.'},
            {'picture': 2, 'primary_role': 'character', 'label': '',
             'description': 'A younger engineer with black hair in a white jacket.'},
            {'picture': 3, 'primary_role': 'environment', 'label': '',
             'description': 'A machine room with pipes.'},
        ],
        'subjects': [
            {'subject': 1, 'kind': 'person', 'source_pictures': [1],
             'description': 'An older engineer with gray hair in a blue jacket.'},
            {'subject': 2, 'kind': 'person', 'source_pictures': [2],
             'description': 'A younger engineer with black hair in a white jacket.'},
            {'subject': 3, 'kind': 'environment', 'source_pictures': [3],
             'description': 'A machine room with pipes.'},
        ],
        'intent': {'speech_request': {
            'required': True, 'mode': 'preserve', 'utterances': [
                'The younger engineer: Is the pressure okay?',
                'The older engineer in a blue jacket: Yes, it is stable.',
            ],
        }},
        'reference_contract': {'required_picture_bindings': [
            {'picture': 1, 'role': 'character', 'subjects': [1]},
            {'picture': 2, 'role': 'character', 'subjects': [2]},
            {'picture': 3, 'role': 'environment', 'subjects': [3]},
        ], 'concrete_keyframe_pictures': []},
    }


class TestRC22Delivery(unittest.TestCase):
    def test_desc_speakers_get_explicit_canonical_ids(self):
        contract = _composer_delivery_contract(json.dumps(sample()))
        self.assertIn('Event 1: <Subject 2> (S1)', contract)
        self.assertIn('Event 2: <Subject 1> (S2)', contract)
        self.assertIn('"Is the pressure okay?"', contract)
        self.assertIn('"Yes, it is stable."', contract)
        self.assertIn('Visible environment: cite <Subject 3> in detailed_description', contract)

    def test_no_matching_generic_noun_is_guessed(self):
        self.assertIsNone(_delivery_speaker_subject('the engineer', sample()))
        self.assertIsNone(_delivery_speaker_subject('someone', sample()))

    def test_ambiguous_role_stays_unresolved(self):
        data = sample()
        data['subjects'][0]['description'] = 'An engineer in a blue jacket.'
        data['subjects'][1]['description'] = 'An engineer in a blue jacket.'
        data['asset_analysis'][0]['description'] = 'An engineer in a blue jacket.'
        data['asset_analysis'][1]['description'] = 'An engineer in a blue jacket.'
        self.assertIsNone(_delivery_speaker_subject('the engineer in blue', data))
        data['intent']['speech_request']['utterances'] = ['The engineer in blue: Hello.']
        contract = _composer_delivery_contract(json.dumps(data))
        self.assertIn('Subject unresolved', contract)
        self.assertNotIn('Event 1: <Subject 1>', contract)

    def test_same_named_subject_reuses_speaker_id(self):
        data = sample()
        data['subjects'][0]['name'] = 'Aster'
        data['subjects'][1]['name'] = 'Bryn'
        data['intent']['speech_request']['utterances'] = [
            'Aster: First.', 'Bryn: Second.', 'Aster: Third.',
        ]
        contract = _composer_delivery_contract(json.dumps(data))
        self.assertIn('Event 1: <Subject 1> (S1)', contract)
        self.assertIn('Event 2: <Subject 2> (S2)', contract)
        self.assertIn('Event 3: <Subject 1> (S1)', contract)

    def test_explicit_subject_only_when_authorized(self):
        self.assertEqual(_delivery_speaker_subject('<Subject 2>', sample()), 2)
        self.assertIsNone(_delivery_speaker_subject('<Subject 3>', sample()))
        self.assertIsNone(_delivery_speaker_subject('<Subject 4>', sample()))

    def test_mapping_does_not_override_explicit_allowed_subject_boundary(self):
        data = sample()
        data['reference_contract']['allowed_subjects'] = [
            {'subject': 1, 'source_pictures': [1]},
        ]
        self.assertIsNone(_delivery_speaker_subject('The younger engineer', data))
        self.assertEqual(_delivery_speaker_subject('The older engineer', data), 1)

    def test_environment_offscreen_does_not_force_visible_citation(self):
        data = sample()
        data['reference_contract']['required_picture_bindings'][2]['required_in_shot'] = False
        contract = _composer_delivery_contract(json.dumps(data))
        self.assertIn('Optional offscreen environment <Subject 3> / <Picture 3>', contract)
        self.assertNotIn('Visible environment: cite <Subject 3>', contract)

    def test_environment_without_subject_required_and_optional(self):
        data = sample()
        binding = data['reference_contract']['required_picture_bindings'][2]
        binding['subjects'] = []
        required = _composer_delivery_contract(json.dumps(data))
        self.assertIn('detailed_description cites <Picture 3>', required)
        binding['required_in_shot'] = False
        optional = _composer_delivery_contract(json.dumps(data))
        self.assertNotIn('detailed_description cites <Picture 3>', optional)
        self.assertIn('not a required visible citation', optional)

    def test_no_unrequested_dialogue_in_delivery(self):
        data = sample()
        data['intent']['speech_request'] = {'mode': 'none', 'required': False,
                                            'utterances': []}
        contract = _composer_delivery_contract(json.dumps(data))
        self.assertNotIn('Event 1:', contract)
        self.assertNotIn('Authoritative user dialogue', contract)

    def test_new_and_extend_contract_is_last_and_no_third_llm(self):
        data = sample()
        blob = json.dumps(data)
        for operation in ('new', 'extend', 'prepend', 'bridge'):
            prompt = composer_user_prompt('The two engineers talk.', 8.0,
                [1, 2, 3], blob, operation=operation)
            self.assertIn('REQUIRED OUTPUT BINDINGS:', prompt)
            self.assertIn('Event 1: <Subject 2> (S1)', prompt)
            self.assertTrue(prompt.rstrip().endswith('keep the quoted words byte-for-byte.'))
            self.assertEqual(prompt.count('REQUIRED OUTPUT BINDINGS:'), 1)

    def test_non_dict_bad_analysis_is_safe(self):
        self.assertIn('normalized reference_contract', _composer_delivery_contract('[]'))
        self.assertIn('normalized reference_contract', _composer_delivery_contract('invalid-json'))

if __name__ == '__main__':
    unittest.main()
