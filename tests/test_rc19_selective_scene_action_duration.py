"""rc19 regressions: visibility-aware scene contracts, narrow action fidelity, FLOAT passthrough.

Synthetic reference names; no OBVPM Pro workflows or private user media.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = 'h3_prompt_composer_rc19_tests'
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / '__init__.py', submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc19_tests import nodes
from h3_prompt_composer_rc19_tests.action_fidelity import (
    explicit_pin_roles, action_role_checks,
)
from h3_prompt_composer_rc19_tests.validator import validate_h3_prompt


def environment_bindings(scale, direction='The two move on the floor.'):
    return nodes._required_picture_bindings(
        [{'picture': 1, 'role': 'character'},
         {'picture': 2, 'role': 'character'},
         {'picture': 3, 'role': 'environment'}],
        [{'subject': 1, 'source_pictures': [1]},
         {'subject': 2, 'source_pictures': [2]},
         {'subject': 3, 'source_pictures': [3]}],
        intent={'shot_scale': scale}, direction=direction,
    )


def h3(visible_room=True, room_definition=True, detail=None):
    room = '<Subject 3> is the airy studio in <Picture 3>.\n' if room_definition else ''
    if detail is None:
        detail = '<Subject 1> and <Subject 2> sit on a rug.'
        if visible_room:
            detail += ' Behind them is <Subject 3>.'
    return (f'subject_definitions:\n<Subject 1> is Aster in <Picture 1>.\n'
            f'<Subject 2> is Bryn in <Picture 2>.\n{room}'
            f'summary:\n[reference generation] A short physical scene.\n'
            f'retention_analysis:\n<Subject 1> (appears in [Shot 1]): fully_preserved - identity.\n'
            f'<Subject 2> (appears in [Shot 1]): fully_preserved - identity.\n'
            f'detailed_description:\n[Shot 1] {detail}\n'
            f'overall_soundscape:\nQuiet breathing.\nnon_diegetic_music:\nN/A')


class TestDurationPassthrough(unittest.TestCase):
    def test_existing_float_input_and_new_output_no_extra_node(self):
        b = nodes.H3DirectorRequestBuilder
        self.assertEqual(b.INPUT_TYPES()['required']['duration_seconds'][0], 'FLOAT')
        self.assertNotIn('timeline_length_frames', b.INPUT_TYPES()['optional'])
        self.assertEqual(b.RETURN_NAMES[-1], 'duration_seconds')
        self.assertEqual(b.RETURN_TYPES[-1], 'FLOAT')
        self.assertNotIn('H3DirectorDuration', nodes.NODE_CLASS_MAPPINGS)
        result = b().build('Aster and Bryn move on the carpet.', 5.2)
        self.assertEqual(len(result), 7)
        self.assertEqual(result[-1], 5.2)
        ctx = json.loads(result[3])
        self.assertEqual(ctx['duration_seconds'], 5.2)
        self.assertNotIn('generation_frames', ctx)
        self.assertNotIn('duration_source', ctx)
        self.assertNotIn('requested_duration_seconds', ctx)


class TestSelectiveEnvironment(unittest.TestCase):
    def test_closeup_scene_identity_remains_without_visible_requirement(self):
        bindings = environment_bindings('close_up')
        self.assertFalse(bindings[2]['required_in_shot'])
        self.assertTrue(bindings[0].get('required_in_shot', True))
        self.assertFalse(validate_h3_prompt(h3(visible_room=False, room_definition=False),
                                            [1, 2, 3], required_picture_bindings=bindings))

    def test_environment_citation_must_be_correct_when_voluntarily_defined(self):
        bindings = environment_bindings('close_up')
        problems = validate_h3_prompt(h3(visible_room=False, room_definition=True).replace(
            '<Subject 3> is the airy studio in <Picture 3>.',
            '<Subject 3> is the airy studio in <Picture 2>.'),
            [1, 2, 3], required_picture_bindings=bindings)
        self.assertTrue(any('reference binding missing' in p for p in problems), problems)

    def test_wide_shot_requires_location_binding(self):
        bindings = environment_bindings('wide')
        self.assertNotIn('required_in_shot', bindings[2])
        problems = validate_h3_prompt(h3(visible_room=False), [1, 2, 3],
                                      required_picture_bindings=bindings)
        self.assertTrue(any('environment <Subject 3>' in p for p in problems), problems)

    def test_closeup_explicitly_visible_room_keeps_requirement(self):
        bindings = environment_bindings('close_up', 'Show the room behind Aster.')
        self.assertNotIn('required_in_shot', bindings[2])


class TestUserActionFidelity(unittest.TestCase):
    names = {'aster': 1, 'bryn': 2}
    direction = 'Aster rolls across Bryn. Bryn prevails and pins Aster’s hands to the floor.'

    def test_extract_only_explicit_user_owned_hand_pin(self):
        self.assertEqual(explicit_pin_roles(self.direction, self.names), [
            {'action': 'pin_hands', 'actor_subject': 2, 'target_subject': 1,
             'source': 'user_direction'}])
        self.assertEqual(explicit_pin_roles('They wrestle and one wins.', self.names), [])

    def test_correct_composer_pinning_passes(self):
        required = explicit_pin_roles(self.direction, self.names)
        detail = ('<Subject 1> rolls over <Subject 2>. <Subject 2> counters and '
                  'pins both of <Subject 1>\'s hands down to the floor.')
        self.assertEqual(action_role_checks(detail, required), [])

    def test_extra_reversed_pinning_fails_even_if_correct_pin_also_occurs(self):
        required = explicit_pin_roles(self.direction, self.names)
        detail = ('<Subject 1> pins <Subject 2>\'s hands briefly. '
                  '<Subject 2> counters, pinning <Subject 1>\'s wrists.')
        self.assertTrue(any('role reversal' in p for p in action_role_checks(detail, required)))

    def test_missing_required_pin_fails(self):
        required = explicit_pin_roles(self.direction, self.names)
        self.assertTrue(any('required hand-pin action' in p for p in
                            action_role_checks('<Subject 1> rolls away.', required)))

    def test_no_action_contract_keeps_other_choreography_free(self):
        self.assertEqual(action_role_checks('<Subject 1> spins around <Subject 2>.', []), [])

    def test_validator_reasserts_direction_even_when_analysis_drops_action(self):
        analyst = {
            'asset_analysis': [
                {'picture': 1, 'primary_role': 'character', 'label': 'Aster'},
                {'picture': 2, 'primary_role': 'character', 'label': 'Bryn'},
            ],
            'subjects': [
                {'subject': 1, 'source_pictures': [1], 'kind': 'person', 'name': 'Aster'},
                {'subject': 2, 'source_pictures': [2], 'kind': 'person', 'name': 'Bryn'},
            ],
            'intent': {'shot_scale': 'medium', 'speech_request': {'mode': 'none', 'required': False}},
        }
        context = json.dumps({
            'direction': self.direction, 'duration_seconds': 5.2,
            'picture_slots': [1, 2], 'operation': 'new',
            'reference_roles': {'direction_bindings': {}, 'user_overrides': {}},
            'continuity_states': {},
        })
        composer = nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(analyst), context)['result']
        analysis = json.loads(composer[2])
        self.assertEqual(len(analysis['action_contract']), 1)
        analysis['action_contract'] = []  # simulate stale/manual materialized edit
        bad_h3 = h3(room_definition=False, detail=(
            '<Subject 1> rolls across <Subject 2>. <Subject 1> pins <Subject 2>\'s hands.'
        ))
        bad_report = nodes.H3DirectorResponseValidator().validate(
            bad_h3, json.dumps(analysis), composer[3])[3]
        self.assertIn('unrequested hand-pin role reversal', bad_report)
        ok_h3 = h3(room_definition=False, detail=(
            '<Subject 1> rolls across <Subject 2>. <Subject 2> pins <Subject 1>\'s hands.'
        ))
        ok_result = nodes.H3DirectorResponseValidator().validate(
            ok_h3, json.dumps(analysis), composer[3])
        self.assertTrue(ok_result[3].startswith('PASS'), ok_result[3])
        self.assertEqual(json.loads(ok_result[2])['action_contract'],
                         explicit_pin_roles(self.direction, self.names))


if __name__ == '__main__':
    unittest.main()
