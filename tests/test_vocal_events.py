"""Vocal event transaction regressions, with synthetic alternating speakers."""
import json
import unittest
from test_rc18_dialogue_authority import (NAME, nodes, analyst, context, h3, extract_user_dialogue)
from importlib import import_module
normalize = import_module(NAME + '.vocal_events').normalize_vocal_events
validator = import_module(NAME + '.validator')._speech_checks

DIRECTION = ('Picture 1 is Aster. Picture 2 is Bryn.\n'
             'Bryn whispers in English: "Did you hear that?"\n'
             'Aster murmurs in English: "Only the wind."\n'
             'Bryn breathes in English: "I hope so."\n'
             'Aster sighs in English: "We should go."')
LINES = ['Bryn: Did you hear that?', 'Aster: Only the wind.', 'Bryn: I hope so.', 'Aster: We should go.']
BODY = ('<Subject 2> whispering: "Did you hear that?" '
        '<Subject 1> (S2) murmurs, <d>Only the wind.</d> '
        '<Subject 2> breathes, <d>[English] I hope so.</d> '
        '<Subject 1> sighs: “We should go.”')

def prompt(body=BODY):
    base = h3()
    a = base.index('<Subject 1> asks,', base.index('detailed_description:'))
    b = base.index('\noverall_soundscape:', a)
    return base[:a] + body + base[b:]

def data():
    raw = analyst(LINES)
    raw['intent']['speech_request'].update(authority='user_direction', language='English')
    return raw

class VocalEventTests(unittest.TestCase):
    def test_authority_shared_vocabulary(self):
        self.assertEqual(extract_user_dialogue(DIRECTION), LINES)
        for verb in ('whispering', 'moaning', 'breathing', 'murmuring', 'sighing', 'gasping', 'stammering', 'croaking', 'singing', 'rapping'):
            self.assertEqual(extract_user_dialogue(f'Aster {verb}: "Hello."'), ['Aster: Hello.'])
        self.assertEqual(extract_user_dialogue('Aster whispers softly: "Hello."'), ['Aster: Hello.'])
        self.assertEqual(extract_user_dialogue('Aster reads a sign called "Hello".'), [])
        self.assertEqual(extract_user_dialogue('Aster breathes deeply and sighs.'), [])

    def test_mixed_errors_alternating_speakers(self):
        original = prompt()
        fixed, tags, ids = normalize(original, data())
        self.assertEqual((tags, ids), (3, 3))
        self.assertIn('<Subject 2> (S1) whispering: <d>[English] Did you hear that?</d>', fixed)
        self.assertIn('<Subject 1> (S2) murmurs, <d>[English] Only the wind.</d>', fixed)
        self.assertIn('<Subject 2> (S1) breathes, <d>[English] I hope so.</d>', fixed)
        self.assertIn('<Subject 1> (S2) sighs: <d>[English] We should go.</d>', fixed)
        self.assertEqual(normalize(fixed, data()), (fixed, 0, 0))
        self.assertEqual(validator(fixed, data()['intent']['speech_request'], {'aster':1, 'bryn':2}), [])

    def test_live_pipeline(self):
        _, _, normalized, stamped, _ = nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(data()), context(DIRECTION))["result"]
        result = nodes.H3DirectorResponseValidator().validate(prompt(), normalized, stamped)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('restored 3 canonical dialogue tag(s)', result[3])
        self.assertIn('inserted 3 unambiguously grounded speaker', result[3])

    def test_refuse_atomic_conflicts(self):
        for body in (BODY.replace('Did you hear that?', 'Did you see that?'),
                     BODY.replace('<Subject 1> (S2)', '<Subject 1> (S1)'),
                     BODY.replace('<Subject 2> whispering', '<Subject 1> whispering'),
                     BODY.replace('<Subject 2> whispering', '<Subject 2> watches <Subject 1> whispering'),
                     BODY.replace('<Subject 2> whispering', '<Subject 2> imagines whispering'),
                     BODY.replace('<Subject 2> whispering', '<Subject 2> points at a sign reading'),
                     BODY.replace('<Subject 2> whispering', '<Subject 2> whispers, then points at a sign reading'),
                     BODY.replace('<d>Only the wind.</d>', '<d>Only the wind.'),
                     BODY.replace('[English] I hope so.', '[German] I hope so.'),
                     BODY.replace('“We should go.”', 'the line'),
                     BODY.replace('“We should go.”', 'We should go.')):
            with self.subTest(body=body):
                original = prompt(body)
                self.assertEqual(normalize(original, data()), (original, 0, 0))

    def test_missing_authority_or_language_no_new_tag(self):
        for key, value in [('authority','analyst'), ('language',''), ('language','auto')]:
            raw = data()
            raw['intent']['speech_request'][key] = value
            original = prompt()
            self.assertEqual(normalize(original, raw), (original, 0, 0))

    def test_explicit_empty_reference_contract_refuses(self):
        raw = data(); raw['reference_contract'] = {'allowed_subjects': []}
        original = prompt()
        self.assertEqual(normalize(original, raw), (original, 0, 0))

    def test_summary_only_not_repaired(self):
        original = prompt('<Subject 2> sighs and <Subject 1> breathes quietly.').replace('Short conversation.', '"Did you hear that?"')
        self.assertEqual(normalize(original, data()), (original, 0, 0))

    def test_apostrophes_and_single_quotes(self):
        raw = data()
        raw['intent']['speech_request']['utterances'] = ["Bryn: I'm ready."]
        original = prompt("<Subject 2> whispers: 'I'm ready.'")
        fixed, tags, ids = normalize(original, raw)
        self.assertEqual((tags, ids), (1,1))
        self.assertIn("<d>[English] I'm ready.</d>", fixed)

    def test_multilingual_contract_does_not_guess_global_language(self):
        f = import_module(NAME + '.dialogue_authority').authoritative_speech_request
        speech = f('Aster says in English: "Hello."\nBryn whispers in German: "Hallo."', {'language':'English'})
        self.assertEqual(speech['language'], '')

    def test_validator_pairs_both_directions_and_explicit_language(self):
        fixed, _, _ = normalize(prompt(), data())
        speech = dict(data()['intent']['speech_request'], language_authority='user_direction')
        mapping = {'aster':1,'bryn':2}
        cases = [(fixed.replace('[English]', '[German]', 1), 'not user-authorized'),
                 (fixed.replace('<Subject 2> (S1) whispering', '<Subject 2> (S1) (S3) whispering', 1), 'multiple preceding speaker IDs'),
                 (fixed.replace('We should go.</d>', 'We should go.</d> (S2)'), 'without a following'),
                 (fixed.replace('<Subject 2> (S1) whispering', '(S1) whispering', 1), 'no grounded attribution')]
        for text, error in cases:
            with self.subTest(error=error):
                self.assertTrue(any(error in item for item in validator(text, speech, mapping)), validator(text, speech, mapping))
