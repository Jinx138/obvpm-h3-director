"""rc18 dialogue-source-of-truth regressions; synthetic names only."""
from fixture_flavour import NEUTRAL_FLAVOUR, neutral_manifests
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
    return json.dumps({"director_flavour": NEUTRAL_FLAVOUR, "director_skill_manifests": neutral_manifests(),
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
        ctx = json.loads(builder.build(direction, 11.0, flavour_profile=NEUTRAL_FLAVOUR)["result"][3])
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
        result = b.build(DIRECTION, 5.2, flavour_profile=NEUTRAL_FLAVOUR)["result"]
        ctx = json.loads(result[3])
        self.assertEqual(ctx['authoritative_dialogue']['utterances'], ['Aster: What is that?', 'Bryn: A small planet.'])
        self.assertEqual(ctx['authoritative_dialogue']['authority'], 'user_direction')
        self.assertEqual(len(result), 6)

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

    def collective(self, direction=None, extra_man=False):
        direction = direction or ('The two men sit one sofa with a glass of champagne, '
                                  'salute to each other and then to the camera and exclamate '
                                  '"Congratulations to version 0.6.4!"')
        raw = analyst([], speech_mode='none')
        raw['intent']['speech_request']['required'] = False
        raw['intent']['dialogue_plan'] = 'Both speak in unison, overlapping naturally.'
        raw['subjects'][0]['description'] = 'Aster: older man, glasses'
        raw['subjects'][1]['description'] = 'Bryn: younger man, dark hair'
        if extra_man:
            raw['subjects'].append({'subject': 3, 'source_pictures': [3], 'kind': 'person', 'name': 'Casey', 'description': 'A man'})
            raw['asset_analysis'][2] = {'picture': 3, 'primary_role': 'character', 'label': 'Casey', 'description': 'A man'}
        return self.composed(raw, direction)

    def test_collective_exclamate_recovers_exact_user_line(self):
        _, composer, norm, ctx, _ = self.collective()
        expected = [dict(speaker=f'<Subject {n}>', text='Congratulations to version 0.6.4!',
                         shared_line=1, delivery='simultaneous') for n in (1, 2)]
        speech = json.loads(norm)['intent']['speech_request']
        self.assertEqual(speech['utterances'], expected)
        self.assertTrue(speech['required'])
        self.assertEqual(speech['authority'], 'user_direction')
        self.assertEqual(json.loads(ctx)['authoritative_dialogue']['utterances'],
                         ['The two men: Congratulations to version 0.6.4!'])
        self.assertIn('Event 1: <Subject 1> (S1)', composer)
        self.assertIn('Event 2: <Subject 2> (S2)', composer)
        self.assertIn('Deliver in unison', composer)
        self.assertIn('Never replace a spoken event', composer)

    def test_collective_missing_or_one_voice_is_fail(self):
        _, _, norm, ctx, _ = self.collective()
        good = h3(first='Congratulations to version 0.6.4!', second='Congratulations to version 0.6.4!', marked=True)
        no_speech = good.replace('<d>[English] Congratulations to version 0.6.4!</d>', 'the line')
        one_voice = good.replace('<Subject 2> (S2) answers, <d>[English] Congratulations to version 0.6.4!</d>', 'The other smiles.')
        for bad in (no_speech, one_voice):
            result = self.validated(bad, json.loads(norm), ctx)
            self.assertTrue(result[3].startswith('FAIL'), result[3])
            self.assertIn('preserved dialogue differs', result[3])
        result = self.validated(good, json.loads(norm), ctx)
        self.assertTrue(result[3].startswith('PASS'), result[3])

    def test_collective_named_and_wrong_attribution(self):
        _, _, norm, ctx, _ = self.collective('Aster and Bryn exclaim in unison: "Well done!"')
        good = h3(first='Well done!', second='Well done!', marked=False)
        result = self.validated(good, json.loads(norm), ctx)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('<Subject 1> (S1)', result[1])
        self.assertIn('<Subject 2> (S2)', result[1])
        bad = h3(first='Well done!', second='Well done!', marked=True, flipped_subjects=True)
        result = self.validated(bad, json.loads(norm), ctx)
        self.assertIn('user-authorized speaker', result[3])

    def test_ambiguous_collective_does_not_guess(self):
        _, composer, norm, ctx, _ = self.collective(extra_man=True)
        speech = json.loads(norm)['intent']['speech_request']
        self.assertEqual(speech['utterances'], ['The two men: Congratulations to version 0.6.4!'])
        self.assertEqual(speech['unresolved_collective_speakers'], ['The two men'])
        self.assertIn('UNRESOLVED collective speaker attribution', composer)
        result = self.validated(h3(first='Congratulations to version 0.6.4!', marked=True), json.loads(norm), ctx)
        self.assertIn('unresolved collective dialogue attribution', result[3])

    def test_explicit_unison_survives_missing_analyst_timing(self):
        raw = analyst([], speech_mode='none')
        raw['intent']['speech_request']['required'] = False
        _, composer, norm, _, _ = self.composed(raw, 'Aster and Bryn exclaim in unison: "Well done!"')
        self.assertEqual([e['delivery'] for e in json.loads(norm)['intent']['speech_request']['utterances']],
                         ['simultaneous', 'simultaneous'])
        self.assertIn('Deliver in unison', composer)

    def test_plural_action_cue_and_exclaim(self):
        self.assertEqual(extract_user_dialogue('Two men sit on a sofa and say "Cheers!"'), ['Two men: Cheers!'])
        self.assertEqual(extract_user_dialogue('Aster exclaims: "Amazing!"'), ['Aster: Amazing!'])
        self.assertEqual(extract_user_dialogue('Both men raise their glasses and exclaim "Cheers!"'), ['Both men: Cheers!'])
        self.assertEqual(extract_user_dialogue('Aster reads a sign called "Welcome".'), [])

    def test_live_shared_placeholder_from_release_toast(self):
        direction = 'The two men sit one sofa with a glass of champagne, salute to each other and then to the camera and exclamate "Congratulations to version 0.6.4!"'
        raw = analyst([], speech_mode='none')
        raw['subjects'][0]['description'] = 'Older man with glasses'
        raw['subjects'][1]['description'] = 'Younger man with dark hair'
        raw['intent']['speech_request']['language'] = 'English'
        raw['intent']['dialogue_plan'] = 'The line is spoken in unison, overlapping naturally as a shared exclamation.'
        system, composer, norm, ctx, _ = self.composed(raw, direction)
        self.assertIn('MANDATORY CURRENT-SHOT DIALOGUE CONTRACT', system)
        self.assertIn('<Subject 2> (S2) says, <d>[English] Congratulations to version 0.6.4!</d>', system)
        prompt = h3().replace('Short conversation.', 'A toast while exclaiming "Congratulations to version 0.6.4!".')
        begin = prompt.index('[Shot 1] They sit')
        end = prompt.index('\noverall_soundscape:', begin)
        detail = ('[Shot 1] They sit in the sunny room from <Picture 3>. <Subject 1> and <Subject 2> raise their glasses. '
                  'Their expressions are bright and joyful as they deliver the line simultaneously with enthusiastic facial expressions. '
                  'They maintain this pose, holding their glasses up and smiling broadly at the camera.')
        prompt = prompt[:begin] + detail + prompt[end:]
        result = self.validated(prompt, json.loads(norm), ctx)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('expanded 2 verbatim', result[3])
        self.assertEqual(result[1].count('<d>[English] Congratulations to version 0.6.4!</d>'), 2)
        self.assertIn('They maintain this pose', result[1])
        result2 = self.validated(result[1], json.loads(norm), ctx)
        self.assertEqual(result[1], result2[1])
        # Missing language cannot silently manufacture a language tag.
        raw['intent']['speech_request']['language'] = ''
        _, _, norm2, ctx2, _ = self.composed(raw, direction)
        bad = self.validated(prompt, json.loads(norm2), ctx2)
        self.assertTrue(bad[3].startswith('FAIL'), bad[3])
        self.assertNotIn('<d>', bad[1])
        # Summary-only, missing or multiple speech anchors stay failures.
        for changed in (prompt.replace('they deliver the line simultaneously', 'they smile'),
                        prompt.replace('they deliver the line simultaneously', 'they deliver the line simultaneously and they deliver the line simultaneously')):
            bad = self.validated(changed, json.loads(norm), ctx)
            self.assertTrue(bad[3].startswith('FAIL'), bad[3])
            self.assertNotIn('<d>', bad[1])

    def test_shared_speaker_markers_with_participial_vocal_cues(self):
        _, _, norm, ctx, _ = self.collective(
            'Both men raise their glasses and exclaim in unison in English: "Well done!"')
        base = h3(first='Well done!', second='Well done!')
        original = base.replace('<Subject 1> asks,',
                                '<Subject 1> lifts his glass, speaking with a slight nod:')
        original = original.replace('<Subject 2> answers,',
                                    '<Subject 2> lifts his glass, delivering the line with high energy:')
        result = self.validated(original, json.loads(norm), ctx)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('inserted 2 unambiguously grounded speaker marker', result[3])
        self.assertIn('<Subject 1> (S1) lifts', result[1])
        self.assertIn('<Subject 2> (S2) lifts', result[1])
        self.assertEqual(result[1].replace(' (S1)', '').replace(' (S2)', ''), original)
        again = self.validated(result[1], json.loads(norm), ctx)
        self.assertEqual(again[1], result[1])
        self.assertTrue(again[3].startswith('PASS'), again[3])
        # An intervening different actor must not acquire the intended actor's ID.
        bad = original.replace('<Subject 1> lifts his glass, speaking',
                               '<Subject 1> watches <Subject 2> speaking')
        rejected = self.validated(bad, json.loads(norm), ctx)
        self.assertTrue(rejected[3].startswith('FAIL'), rejected[3])
        self.assertNotIn('(S1)', rejected[1])

    def test_explicit_shared_dialogue_language_survives_analyst_omission(self):
        request = authoritative_speech_request('Both men raise their glasses and say in unison in English: "Well done!"', {'language': ''})
        self.assertEqual(request['language'], 'English')
        self.assertEqual(request['utterances'], ['Both men: Well done!'])
        self.assertEqual(request['simultaneous_lines'], [1])

    def test_frozen_shot_editor_remains_passthrough(self):
        shot = nodes.H3DirectorShotState()
        manually_edited = h3(first='Own user-authored edit.', marked=True)
        result = shot.store(materialized=True, shot_direction='My edit',
                            shot_h3_prompt=manually_edited, shot_analysis='my edited analysis')
        self.assertEqual(result, (manually_edited, 'My edit', 'my edited analysis', '', '', ''))


if __name__ == '__main__':
    unittest.main()
