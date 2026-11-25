"""Regression: staging must not turn individual quotes into collective speech."""
import json
import unittest
from importlib import import_module
from test_rc18_dialogue_authority import (NAME, nodes, extract_user_dialogue, context, analyst, h3)
from test_vocal_events import prompt

# User-reported sentence structure and natural-language role descriptions;
# synthetic words, with no private assets or workflows.
DIRECTION = ('The two men sit on a sofa with a glass of champagne, salute to each other '
             'and then to the camera. the old man exclamates "Congratulations!" '
             'and the younger one smilingly says: "To the new version!"')
LINES = ['the old man: Congratulations!', 'the younger one: To the new version!']
resolve = import_module(NAME + '.prompt_skill')._delivery_speaker_subject


def data():
    raw = analyst()
    for i, age in enumerate(('older','younger')):
        role = age + '_man'
        raw['subjects'][i].update(name=role, description=f'The {age} man wearing a shirt.')
        raw['asset_analysis'][i].update(label=role, description=f'A {age} man.')
    raw['intent']['speech_request'].update(language='English', utterances=[])
    return raw


class DialogueClauseAuthority(unittest.TestCase):
    def test_two_individual_events_after_staging(self):
        self.assertEqual(extract_user_dialogue(DIRECTION), LINES)

    def test_repeated_speaker_and_preceding_staging(self):
        d = 'Aster and Bryn sit. Aster whispers: "First." Bryn smiles and replies: "Second." Aster murmurs: "Third."'
        self.assertEqual(extract_user_dialogue(d), ['Aster: First.', 'Bryn: Second.', 'Aster: Third.'])

    def test_modifier_before_and_after_speech_verb(self):
        self.assertEqual(extract_user_dialogue('Aster smilingly says: "First." Bryn whispers breathlessly: "Second."'), ['Aster: First.', 'Bryn: Second.'])

    def test_title_abbreviation_and_real_collective(self):
        self.assertEqual(extract_user_dialogue('They sit. Dr. Bryn says: "Hello."'), ['Dr. Bryn: Hello.'])
        self.assertEqual(extract_user_dialogue('The two men sit. Both men say in unison: "Cheers!"'), ['Both men: Cheers!'])

    def test_unattributed_second_sentence_not_given_previous_actor(self):
        self.assertEqual(extract_user_dialogue('Aster sits. And then says: "Hello."'), [])

    def test_elliptical_age_role_is_unique_or_unresolved(self):
        raw = data()
        self.assertEqual(resolve('the old man', raw), 1)
        self.assertEqual(resolve('the younger one', raw), 2)
        raw['subjects'][0].update(name='younger_man', description='A younger man.')
        raw['asset_analysis'][0].update(label='younger_man', description='A younger man.')
        self.assertIsNone(resolve('the younger one', raw))
        self.assertIsNone(resolve('the one', raw))

    def test_full_compose_and_validator_two_vocal_events(self):
        raw = data()
        _, _, normalized, stamped, _ = nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(raw), context(DIRECTION))['result']
        speech = json.loads(normalized)['intent']['speech_request']
        self.assertEqual(speech['utterances'], LINES)
        body = ('<Subject 1> exclaims, <d>[English] Congratulations!</d> '
                '<Subject 2> smilingly says, <d>[English] To the new version!</d>')
        result = nodes.H3DirectorResponseValidator().validate(prompt(body), normalized, stamped)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('<Subject 1> (S1) exclaims', result[1])
        self.assertIn('<Subject 2> (S2) smilingly says', result[1])
        self.assertEqual(result[1].count('<d>'), 2)
        extra = nodes.H3DirectorResponseValidator().validate(prompt(body + ' <Subject 2> says, <d>[English] Cheers!</d>'), normalized, stamped)
        self.assertIn('preserved dialogue differs', extra[3])

if __name__ == '__main__':
    unittest.main()
