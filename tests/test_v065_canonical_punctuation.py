"""Canonical dialogue does not need a redundant delivery vocabulary proof."""
import json
import unittest
from test_v065_repeated_dialogue import composed, normalize_punctuation, nodes

LIVE_PROMPT = '''subject_definitions:
<Subject 1> is the older man from <Picture 1>.
<Subject 2> is the younger man from <Picture 2>.
<Subject 3> is the living room from <Picture 5>.

summary:
[reference generation] A celebratory toast between an older man and a younger man to mark the release of version 0.6.4.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 3>: fully_preserved - identity and visible characteristics retained.

detailed_description:
[Shot 1] The video opens with a static medium shot of <Subject 1> and <Subject 2> seated side-by-side on the dark gray sofa in the bright living room. Both men are holding champagne glasses and looking at each other with warm smiles. They bring their glasses together to clink, then simultaneously lift them toward the camera. <Subject 1> (S1) exclaims, <d>[English] Congratulations!</d>. <Subject 2> (S2) replies with a proud smile, <d>[English] To version 0.6.4!</d>. <Subject 1> (S1) concludes with a joyful expression, <d>[English] Hooray.</d>, as both men keep their glasses raised toward the camera.

overall_soundscape:
Audible clink of champagne glasses, followed by the spoken dialogue and a joyful tone.

non_diegetic_music:
N/A'''

class CanonicalPunctuationTests(unittest.TestCase):
    def setUp(self):
        _, _, self.analysis, self.context, _ = composed()
        self.data = json.loads(self.analysis)

    def test_exact_live_prompt(self):
        fixed, count = normalize_punctuation(LIVE_PROMPT, self.data)
        self.assertEqual(count, 1)
        self.assertEqual(fixed, LIVE_PROMPT.replace('Hooray.</d>', 'Hooray</d>'))
        result = nodes.H3DirectorResponseValidator().validate(LIVE_PROMPT, self.analysis, self.context)
        self.assertTrue(result[3].startswith('WARNING'), result[3])
        self.assertIn('environment <Subject 3>', result[3])
        self.assertIn('restored exact user punctuation in 1', result[3])
        self.assertNotIn('FAIL', result[3])
        self.assertEqual(normalize_punctuation(fixed, self.data), (fixed, 0))

    def test_no_delivery_vocabulary_requirement_for_explicit_markers(self):
        for cue in ('concludes with a joyful expression', 'finishes with a flourish', 'beams', 'raises his glass'):
            with self.subTest(cue=cue):
                original = LIVE_PROMPT.replace('concludes with a joyful expression', cue)
                fixed, count = normalize_punctuation(original, self.data)
                self.assertEqual((fixed, count), (original.replace('Hooray.</d>', 'Hooray</d>'), 1))

    def test_conflicts_remain_unrepaired(self):
        for original in (LIVE_PROMPT.replace('(S1) concludes', '(S2) concludes'),
                         LIVE_PROMPT.replace('<Subject 1> (S1) concludes', '<Subject 2> (S1) concludes'),
                         LIVE_PROMPT.replace('(S1) concludes', '(S1) (S3) concludes'),
                         LIVE_PROMPT.replace('(S1) concludes', 'concludes'),
                         LIVE_PROMPT.replace('concludes with a joyful expression', 'watches <Subject 2>'),
                         LIVE_PROMPT.replace('Hooray.', 'Hurrah.'),
                         LIVE_PROMPT.replace('Hooray.', 'Hooray?')):
            with self.subTest(original=original):
                self.assertEqual(normalize_punctuation(original, self.data), (original, 0))
