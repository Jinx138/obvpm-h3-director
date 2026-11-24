"""Public-safe regression tests for local Reference Authority v0.6.4.dev3 test.

No OBVPM Pro workflow, user images, model weights, or personal Character info.
Run in the Pinokio ComfyUI environment after installing the test overlay.
"""
from fixture_flavour import NEUTRAL_FLAVOUR, neutral_manifests
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = 'h3_prompt_composer_ref_authority_local_test'
spec = importlib.util.spec_from_file_location(
    NAME, ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from h3_prompt_composer_ref_authority_local_test import nodes
from h3_prompt_composer_ref_authority_local_test.reference_roles import parse_overrides
from h3_prompt_composer_ref_authority_local_test.validator import validate_h3_prompt


def context(roles, slots=(1, 4), direction='Alex moves closer to the camera.'):
    return json.dumps({"director_flavour": NEUTRAL_FLAVOUR, "director_skill_manifests": neutral_manifests(),
        'direction': direction,
        'duration_seconds': 5.2,
        'picture_slots': list(slots),
        'reference_roles': {
            'user_overrides': parse_overrides(roles, slots),
            'direction_bindings': {},
        },
        'operation': 'new',
        'continuity_states': {},
    })


def analysis(*, duplicate=False, same_subject_as=None, extra_location=False):
    assets = [
        {'picture': 1, 'primary_role': 'character', 'label': 'Alex', 'description': 'A woman with brown hair'},
        {'picture': 4, 'primary_role': 'character', 'label': '', 'description': 'Close-up of hands',
         'same_subject_as': same_subject_as},
    ]
    subjects = [
        {'subject': 1, 'kind': 'person', 'name': 'Alex', 'source_pictures': [1],
         'description': 'Brown-haired woman', 'importance': 'primary'}
    ]
    if duplicate:
        subjects.append({'subject': 2, 'kind': 'person', 'source_pictures': [4],
                         'description': 'Hands only', 'importance': 'supporting'})
    if extra_location:
        assets.append({'picture': 3, 'primary_role': 'environment', 'description': 'An apartment'})
    return {'asset_analysis': assets, 'subjects': subjects,
            'intent': {'shot_scale': 'close_up', 'dominant_action': 'She gestures.'}}


def composed(data, ctx):
    out = nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(data), ctx)['result']
    return json.loads(out[2]), json.loads(out[3])


class ReferenceIntegrity(unittest.TestCase):
    def test_explicit_secondary_hand_picture_is_merged_and_required(self):
        ctx = context('Picture 1: Alex (character)\nPicture 4: the hands of Alex (character)')
        data, _ = composed(analysis(), ctx)
        self.assertEqual(len(data['subjects']), 1)
        self.assertEqual(data['subjects'][0]['source_pictures'], [1, 4])
        bindings = data['reference_contract']['required_picture_bindings']
        self.assertEqual([(x['picture'], x['subjects']) for x in bindings], [(1, [1]), (4, [1])])

    def test_duplicate_analyst_hand_subject_removed(self):
        ctx = context('Picture 1: Alex (character)\nPicture 4: Alex hands (character)')
        data, _ = composed(analysis(duplicate=True), ctx)
        self.assertEqual([x['subject'] for x in data['subjects']], [1])
        self.assertEqual(data['reference_contract']['allowed_subjects'],
                         [{'subject': 1, 'source_pictures': [1, 4]}])

    def test_analyzer_same_subject_as_picture_number_is_respected(self):
        ctx = context('Picture 1: Alex (character)\nPicture 4: hands detail (character)')
        data, _ = composed(analysis(same_subject_as=1), ctx)
        self.assertEqual(data['subjects'][0]['source_pictures'], [1, 4])

    def test_owned_hands_inferred_character_role_without_suffix(self):
        roles = parse_overrides('Picture 4: Alex\'s hands', [1, 4])
        self.assertEqual(roles['4']['role'], 'character')
        ctx = context('Picture 1: Alex (character)\nPicture 4: Alex\'s hands')
        data, _ = composed(analysis(), ctx)
        self.assertEqual(data['subjects'][0]['source_pictures'], [1, 4])

    def test_character_1_hands_maps_to_picture_1_not_new_subject(self):
        ctx = context('Picture 1: Character 1 (character)\nPicture 4: the hands of Character 1')
        raw = analysis()
        raw['asset_analysis'][0]['label'] = 'Character 1'
        raw['subjects'][0]['name'] = 'Character 1'
        data, _ = composed(raw, ctx)
        self.assertEqual(data['subjects'][0]['source_pictures'], [1, 4])

    def test_ambiguous_character_detail_is_not_assigned_by_guess(self):
        ctx = context('Picture 1: Alex (character)\nPicture 4: hands close-up (character)')
        data, _ = composed(analysis(), ctx)
        unresolved = next(x for x in data['reference_contract']['required_picture_bindings']
                          if x['picture'] == 4)
        self.assertTrue(unresolved['unresolved_subject'])
        problems = validate_h3_prompt('', [1, 4],
                                     required_picture_bindings=data['reference_contract']['required_picture_bindings'])
        self.assertTrue(any('unresolved character reference' in p for p in problems), problems)

    def test_explicit_closeup_environment_remains_required(self):
        roles = 'Picture 1: Alex (character)\nPicture 3: Apartment (environment)\nPicture 4: Alex hands (character)'
        ctx = context(roles, slots=(1, 3, 4))
        data, _ = composed(analysis(extra_location=True), ctx)
        environment = next(x for x in data['reference_contract']['required_picture_bindings']
                           if x['picture'] == 3)
        self.assertNotEqual(environment.get('required_in_shot'), False)

    def test_auto_closeup_environment_still_optional(self):
        ctx = context('Picture 1: Alex (character)\nPicture 4: Alex hands (character)',
                      slots=(1, 3, 4))
        data, _ = composed(analysis(extra_location=True), ctx)
        environment = next(x for x in data['reference_contract']['required_picture_bindings']
                           if x['picture'] == 3)
        self.assertFalse(environment.get('required_in_shot', True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
