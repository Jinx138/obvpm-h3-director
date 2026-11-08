"""rc18 dialogue-source-of-truth regressions; synthetic names only."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = 'h3_prompt_composer_rc18_dialogue_tests'
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / '__init__.py', submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc18_dialogue_tests import nodes
from h3_prompt_composer_rc18_dialogue_tests.dialogue_authority import (
    extract_user_dialogue, authoritative_speech_request,
)

DIRECTION = '''Picture 1 is Aster. Picture 2 is Bryn.
Aster and Bryn sit facing each other in the room.
Aster says: "What is that?"
Bryn replies: "A small planet."
Preserve the exact dialogue and speaker order.'''


def analyst(utterances=None, speech_mode='preserve'):
    return {
        'asset_analysis': [
            {'picture': 1, 'primary_role': 'character', 'label': 'Aster', 'description': 'Aster'},
            {'picture': 2, 'primary_role': 'character', 'label': 'Bryn', 'description': 'Bryn'},
            {'picture': 3, 'primary_role': 'environment', 'label': 'room', 'description': 'Sunny room'},
        ],
        'subjects': [
            {'subject': 1, 'source_pictures': [1], 'kind': 'person', 'name': 'Aster', 'description': 'Aster: short hair'},
            {'subject': 2, 'source_pictures': [2], 'kind': 'person', 'name': 'Bryn', 'description': 'Bryn: dark hair'},
        ],
        'intent': {'speech_request': {'mode': speech_mode, 'required': True, 'language': '',
                                      'utterances': [] if utterances is None else utterances}},
        'reference_strategy': {'subject_only_pictures': [1, 2], 'soft_inspiration_pictures': [3]},
    }


def context(direction=DIRECTION):
    return json.dumps({
        'direction': direction, 'picture_slots': [1, 2, 3], 'duration_seconds': 5.2,
        'reference_roles': {'direction_bindings': {}, 'user_overrides': {}},
        'operation': 'new', 'continuity_states': {},
    })


def h3(first='What is that?', second='A small planet.', marked=False,
       flipped_subjects=False):
    first_subject, second_subject = (2, 1) if flipped_subjects else (1, 2)
    s1 = '(S1) ' if marked else ''
    s2 = '(S2) ' if marked else ''
    return (f'subject_definitions:\n<Subject 1> is Aster in <Picture 1>.\n'
            f'<Subject 2> is Bryn in <Picture 2>.\n'
            f'summary:\n[reference generation] Short conversation.\n'
            f'retention_analysis:\n<Subject 1> (appears in [Shot 1]): fully_preserved - known.\n'
            f'<Subject 2> (appears in [Shot 1]): fully_preserved - known.\n'
            f'detailed_description:\n[Shot 1] They sit in the sunny room from <Picture 3>. '
            f'<Subject {first_subject}> {s1}asks, <d>[English] {first}</d> '
            f'<Subject {second_subject}> {s2}answers, <d>[English] {second}</d>\n'
            f'overall_soundscape:\nQuiet room tone.\nnon_diegetic_music:\nN/A')


class TestDialogueAuthority(unittest.TestCase):
    def setUp(self):
        self.compose = nodes.H3DirectorAnalysisCompose()
        self.validator = nodes.H3DirectorResponseValidator()

    def composed(self, raw=None, direction=DIRECTION):
        return self.compose.compose_request(json.dumps(raw or analyst()), context(direction))['result']

    def validated(self, prompt, normalized, ctx):
        return self.validator.validate(prompt, json.dumps(normalized), ctx)

    def test_exact_two_line_user_quotes(self):
        self.assertEqual(extract_user_dialogue(DIRECTION), ['Aster: What is that?', 'Bryn: A small planet.'])

    def test_curly_quotes_and_apostrophes_in_dialogue(self):
        d = 'Aster says: “Don’t move.”\nBryn replies: ‘I won\'t.’'
        self.assertEqual(extract_user_dialogue(d), ['Aster: Don’t move.', "Bryn: I won't."])

    def test_action_before_speech_and_narration_after_quote(self):
        direction = (
            'The younger man looks at his friend and says: "Are you okay? Did it stop?"\n\n'
            'The older man in the green shirt smiles gently and replies: '
            '"Yes, I\'m feeling better." As he speaks, he pats his friend\'s hand.'
        )
        self.assertEqual(extract_user_dialogue(direction), [
            'The younger man: Are you okay? Did it stop?',
            "The older man in the green shirt: Yes, I'm feeling better.",
        ])

    def test_action_bracket_does_not_contaminate_authoritative_context(self):
        direction = (
            'Aster turns to Bryn and asks: "Is it ready?"\n'
            'Bryn smiles and replies: "It is ready now." Then Bryn closes the box.'
        )
        builder = nodes.H3DirectorRequestBuilder()
        ctx = json.loads(builder.build(direction, 11.0)[3])
        self.assertEqual(ctx['duration_seconds'], 11.0)
        self.assertEqual(ctx['authoritative_dialogue']['utterances'], [
            'Aster: Is it ready?', 'Bryn: It is ready now.',
        ])
        _, _, norm, stamped, _ = self.composed(direction=direction)
        self.assertEqual(json.loads(norm)['intent']['speech_request']['utterances'],
                         ['Aster: Is it ready?', 'Bryn: It is ready now.'])
        self.assertEqual(json.loads(stamped)['authoritative_dialogue']['utterances'],
                         ['Aster: Is it ready?', 'Bryn: It is ready now.'])

    def test_same_line_alternating_speakers(self):
        d = 'Aster says: "First." Bryn responds: "Second." Aster whispers: "Third."'
        self.assertEqual(extract_user_dialogue(d), [
            'Aster: First.', 'Bryn: Second.', 'Aster: Third.',
        ])

    def test_same_line_conjoined_reply(self):
        d = 'Aster says: "First." and Bryn replies: "Second."'
        self.assertEqual(extract_user_dialogue(d), ['Aster: First.', 'Bryn: Second.'])

    def test_single_quotes_with_internal_apostrophes(self):
        self.assertEqual(extract_user_dialogue("Aster replies: 'I'm here.'"),
                         ["Aster: I'm here."])

    def test_unattributed_narrative_with_quote_and_no_speech_verb(self):
        self.assertEqual(extract_user_dialogue(
            'Aster finds a card reading "The key". He picks it up quietly.'), [])

    def test_missing_explicit_speaker_does_not_gain_dialogue_authority(self):
        self.assertEqual(extract_user_dialogue('And then says: "Hello."'), [])

    def test_unattributed_text_or_broad_chat_does_not_invent_speech(self):
        self.assertEqual(extract_user_dialogue('Aster and Bryn chat about "fashion".'), [])
        self.assertIsNone(authoritative_speech_request('They are talking about fashion.'))

    def test_request_builder_persists_user_authority_without_new_outputs(self):
        b = nodes.H3DirectorRequestBuilder()
        result = b.build(DIRECTION, 5.2)
        ctx = json.loads(result[3])
        self.assertEqual(ctx['authoritative_dialogue']['utterances'], ['Aster: What is that?', 'Bryn: A small planet.'])
        self.assertEqual(ctx['authoritative_dialogue']['authority'], 'user_direction')
        self.assertEqual(len(result), 7)

    def test_empty_analyst_utterances_repaired_from_direction(self):
        _, composer_prompt, normalized, stamped_ctx, _ = self.composed()
        a = json.loads(normalized)
        speech = a['intent']['speech_request']
        self.assertEqual(speech['mode'], 'preserve')
        self.assertTrue(speech['required'])
        self.assertEqual(speech['utterances'], ['Aster: What is that?', 'Bryn: A small planet.'])
        self.assertEqual(speech['authority'], 'user_direction')
        self.assertIn('Aster: What is that?', composer_prompt)
        self.assertIn('Bryn: A small planet.', composer_prompt)
        self.assertIn('REQUIRED OUTPUT BINDINGS:', composer_prompt)
        self.assertEqual(json.loads(stamped_ctx)['authoritative_dialogue']['utterances'],
                         ['Aster: What is that?', 'Bryn: A small planet.'])

    def test_fabricated_or_reversed_analysis_dialogue_overwritten(self):
        raw = analyst(['Bryn: Fake words.', 'Aster: Contradiction.'], speech_mode='invent')
        normalized = json.loads(self.composed(raw)[2])
        self.assertEqual(normalized['intent']['speech_request']['utterances'],
                         ['Aster: What is that?', 'Bryn: A small planet.'])
        self.assertEqual(normalized['intent']['speech_request']['mode'], 'preserve')

    def test_no_explicit_quotes_does_not_override_authorized_invention(self):
        raw = analyst(['Aster: New invented words.'], speech_mode='invent')
        normalized = json.loads(self.composed(raw, direction='Please invent a line for Aster.')[2])
        self.assertEqual(normalized['intent']['speech_request']['mode'], 'invent')
        self.assertEqual(normalized['intent']['speech_request']['utterances'], ['Aster: New invented words.'])

    def test_missing_speaker_ids_autonormalized_with_empty_raw_analyst_utterances(self):
        _, _, normalized, ctx, _ = self.composed()
        result = self.validated(h3(), json.loads(normalized), ctx)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('AUTO-NORMALIZED', result[3])
        self.assertIn('<Subject 1> (S1) asks', result[1])
        self.assertIn('<Subject 2> (S2) answers', result[1])
        self.assertIn('<d>[English] What is that?</d>', result[1])
        self.assertIn('<d>[English] A small planet.</d>', result[1])

    def test_validator_reasserts_user_dialogue_when_analysis_edited_after_compose(self):
        _, _, norm, ctx, _ = self.composed()
        normalized = json.loads(norm)
        normalized['intent']['speech_request'] = {'mode': 'preserve', 'required': True, 'utterances': []}
        result = self.validated(h3(), normalized, ctx)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertEqual(result[1].count('(S'), 2)
        self.assertEqual(json.loads(result[2])['intent']['speech_request']['utterances'],
                         ['Aster: What is that?', 'Bryn: A small planet.'])

    def test_dialogue_change_or_reversal_fails_without_silent_repair(self):
        _, _, norm, ctx, _ = self.composed()
        for bad in (h3(first='Changed words.'), h3(first='A small planet.', second='What is that?')):
            result = self.validated(bad, json.loads(norm), ctx)
            self.assertTrue(result[3].startswith('FAIL'), result[3])
            self.assertIn('preserved dialogue differs', result[3])
            self.assertNotIn('AUTO-NORMALIZED', result[3])

    def test_required_preserve_without_authorized_utterances_fails_closed(self):
        empty_direction = 'Aster and Bryn talk in the room.'
        _, _, norm, ctx, _ = self.composed(direction=empty_direction)
        result = self.validated(h3(marked=True), json.loads(norm), ctx)
        self.assertIn('required preserved dialogue has no authoritative utterances', result[3])

    def test_wrong_subject_attribution_rejected_even_when_wording_correct(self):
        _, _, norm, ctx, _ = self.composed()
        result = self.validated(h3(marked=True, flipped_subjects=True), json.loads(norm), ctx)
        self.assertIn('attributed to <Subject 2> but user-authorized speaker', result[3])

    def test_frozen_shot_editor_remains_passthrough(self):
        shot = nodes.H3DirectorShotState()
        manually_edited = h3(first='Own user-authored edit.', marked=True)
        result = shot.store(materialized=True, shot_direction='My edit',
                            shot_h3_prompt=manually_edited, shot_analysis='my edited analysis')
        self.assertEqual(result, (manually_edited, 'My edit', 'my edited analysis'))


if __name__ == '__main__':
    unittest.main()
