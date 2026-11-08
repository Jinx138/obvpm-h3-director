"""rc23: syntactic-only vocal marker normalization with grounded roles.

All fixtures are synthetic, without private workflows or video data.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = 'h3_prompt_composer_rc23_tests'
spec = importlib.util.spec_from_file_location(
    NAME, PACKAGE / '__init__.py', submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc23_tests.speaker_ids import normalize_speaker_ids
from h3_prompt_composer_rc23_tests.nodes import H3DirectorResponseValidator, H3DirectorShotState


def analysis(lines=None):
    return {
        'asset_analysis': [
            {'picture': 1, 'primary_role': 'character', 'label': '',
             'description': 'An older engineer in a blue jacket.'},
            {'picture': 2, 'primary_role': 'character', 'label': '',
             'description': 'A younger engineer in a white shirt.'},
            {'picture': 3, 'primary_role': 'environment', 'label': '',
             'description': 'A workshop with machinery.'},
        ],
        'subjects': [
            {'subject': 1, 'kind': 'person', 'source_pictures': [1],
             'description': 'An older engineer in a blue jacket.'},
            {'subject': 2, 'kind': 'person', 'source_pictures': [2],
             'description': 'A younger engineer in a white shirt.'},
            {'subject': 3, 'kind': 'environment', 'source_pictures': [3],
             'description': 'A workshop with machinery.'},
        ],
        'intent': {'speech_request': {
            'required': True, 'mode': 'preserve', 'authority': 'user_direction',
            'utterances': lines or [
                'The younger engineer: Is it ready?',
                'The older engineer in the blue jacket: Everything is ready.',
            ],
        }},
        'reference_contract': {
            'allowed_subjects': [
                {'subject': 1, 'source_pictures': [1]},
                {'subject': 2, 'source_pictures': [2]},
                {'subject': 3, 'source_pictures': [3]},
            ],
            'required_picture_bindings': [
                {'picture': 1, 'role': 'character', 'subjects': [1]},
                {'picture': 2, 'role': 'character', 'subjects': [2]},
                {'picture': 3, 'role': 'environment', 'subjects': [3]},
            ],
        },
    }


def h3(detail):
    return ('subject_definitions:\n'
            '<Subject 1> is the older engineer in <Picture 1>.\n'
            '<Subject 2> is the younger engineer in <Picture 2>.\n'
            '<Subject 3> is the workshop in <Picture 3>.\n'
            'summary:\n[reference generation] A brief workshop conversation.\n'
            'retention_analysis:\n'
            '<Subject 1> (appears in [Shot 1]): fully_preserved.\n'
            '<Subject 2> (appears in [Shot 1]): fully_preserved.\n'
            '<Subject 3> (appears in [Shot 1]): fully_preserved.\n'
            'detailed_description:\n[Shot 1] ' + detail + '\n'
            'overall_soundscape:\nQuiet room tone.\n'
            'non_diegetic_music:\nN/A')


class TestRC23DescriptiveSpeakers(unittest.TestCase):
    def test_two_descriptive_roles_missing_ids_are_normalized(self):
        original = h3(
            'Both engineers sit at a table in <Subject 3>. '
            '<Subject 2> looks at <Subject 1> and asks, '
            '<d>[English] Is it ready?</d> '
            '<Subject 1> smiles and replies, '
            '<d>[English] Everything is ready.</d>'
        )
        fixed, count = normalize_speaker_ids(original, analysis())
        self.assertEqual(count, 2)
        self.assertIn('<Subject 2> (S1) looks at <Subject 1> and asks', fixed)
        self.assertIn('<Subject 1> (S2) smiles and replies', fixed)
        self.assertEqual(fixed.replace(' (S1)', '').replace(' (S2)', ''), original)

    def test_live_validator_pass_without_extra_llm(self):
        original = h3(
            'The workshop <Subject 3> is visible. '
            '<Subject 2> looks to the older engineer and asks, '
            '<d>[English] Is it ready?</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>'
        )
        direction = ('The younger engineer says: "Is it ready?"\n'
                     'The older engineer in the blue jacket replies: "Everything is ready."')
        context = json.dumps({'direction': direction, 'picture_slots': [1, 2, 3], 'operation': 'new'})
        result = H3DirectorResponseValidator().validate(original, json.dumps(analysis()), context)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('AUTO-NORMALIZED', result[3])
        self.assertEqual(result[1].count('(S1)'), 1)
        self.assertEqual(result[1].count('(S2)'), 1)
        self.assertEqual(result[1].count('<d>'), 2)
        self.assertEqual(result[1].replace(' (S1)', '').replace(' (S2)', ''), original)

    def test_existing_wrong_marker_remains_fail_closed(self):
        original = h3(
            '<Subject 3> surrounds the engineers. '
            '<Subject 2> (S1) asks, <d>[English] Is it ready?</d> '
            '<Subject 1> (S1) replies, <d>[English] Everything is ready.</d>'
        )
        self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))

    def test_existing_adjacent_marker_to_wrong_subject_is_not_changed(self):
        original = h3(
            '<Subject 3> surrounds them. '
            '<Subject 1> (S1) asks, <d>[English] Is it ready?</d> '
            '<Subject 2> (S2) replies, <d>[English] Everything is ready.</d>'
        )
        self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))
        direction = ('The younger engineer says: "Is it ready?"\n'
                     'The older engineer in the blue jacket replies: "Everything is ready."')
        result = H3DirectorResponseValidator().validate(
            original, json.dumps(analysis()),
            json.dumps({'direction': direction, 'picture_slots': [1, 2, 3], 'operation': 'new'})
        )
        self.assertIn('attributed to <Subject 1>', result[3])
        self.assertIn('attributed to <Subject 2>', result[3])

    def test_missing_or_reordered_user_dialogue_not_repaired(self):
        for detail in [
            '<Subject 2> asks, <d>[English] Other words.</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>',
            '<Subject 1> replies, <d>[English] Everything is ready.</d> '
            '<Subject 2> asks, <d>[English] Is it ready?</d>',
            '<Subject 1> replies, <d>[English] Everything is ready.</d>',
        ]:
            original = h3(detail)
            self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))

    def test_ambiguous_descriptive_role_not_guessed(self):
        data = analysis(['The engineer: Is it ready?', 'The engineer: Everything is ready.'])
        original = h3('<Subject 2> asks, <d>[English] Is it ready?</d> '
                      '<Subject 1> replies, <d>[English] Everything is ready.</d>')
        self.assertEqual(normalize_speaker_ids(original, data), (original, 0))

    def test_subject_not_in_local_speech_clause_not_guessed(self):
        original = h3(
            '<Subject 2> is seated across the table. '
            '<Subject 1> starts speaking and asks, <d>[English] Is it ready?</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>'
        )
        self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))

    def test_onlooker_not_falsely_treated_as_speaker(self):
        original = h3(
            '<Subject 2> watches <Subject 1> ask, <d>[English] Is it ready?</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>'
        )
        self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))

    def test_unmentioned_speaker_does_not_create_new_subject(self):
        original = h3(
            '<Subject 3> is dimly lit. A voice asks, <d>[English] Is it ready?</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>'
        )
        self.assertEqual(normalize_speaker_ids(original, analysis()), (original, 0))

    def test_named_first_event_still_checks_existing_marker_if_next_is_unnamed(self):
        data = analysis(['The younger engineer: Is it ready?', 'Everything is ready.'])
        original = h3(
            '<Subject 1> (S1) nods toward <Subject 2> and asks, '
            '<d>[English] Is it ready?</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>'
        )
        # Event 1 has an S1 marker next to the WRONG actor, though the requested
        # speaker is named and a <Subject 2> mention occurs later in its clause.
        self.assertEqual(normalize_speaker_ids(original, data), (original, 0))

    def test_unattributed_offscreen_speaker_does_not_get_vocal_marker(self):
        data = analysis(['The younger engineer: Is it ready?', 'The older engineer in the blue jacket: Everything is ready.'])
        original = h3(
            '<Subject 2> looks at the door. A distant voice asks, '
            '<d>[English] Is it ready?</d> '
            '<Subject 1> replies, <d>[English] Everything is ready.</d>'
        )
        self.assertEqual(normalize_speaker_ids(original, data), (original, 0))

    def test_repeated_descriptive_source_reuses_first_id(self):
        data = analysis(['The younger engineer: First.',
                         'The older engineer in the blue jacket: Second.',
                         'The younger engineer: Third.'])
        original = h3(
            '<Subject 2> asks, <d>[English] First.</d> '
            '<Subject 1> replies, <d>[English] Second.</d> '
            '<Subject 2> adds, <d>[English] Third.</d>'
        )
        fixed, count = normalize_speaker_ids(original, data)
        self.assertEqual(count, 3)
        self.assertEqual(fixed.count('(S1)'), 2)
        self.assertEqual(fixed.count('(S2)'), 1)

    def test_frozen_shot_editor_is_passthrough(self):
        shot = H3DirectorShotState()
        user_edit = h3('<Subject 2> says, <d>[English] My own words.</d>')
        self.assertEqual(shot.store(materialized=True, shot_direction='Own direction',
                                    shot_h3_prompt=user_edit, shot_analysis='Own notes'),
                         (user_edit, 'Own direction', 'Own notes'))


if __name__ == '__main__':
    unittest.main()
