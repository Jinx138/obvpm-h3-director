"""User-reported S1/S2/S1 sequence and exact punctuation repair."""
import json
import unittest
from importlib import import_module
from test_v065_dialogue_clause_authority import data, context, nodes, extract_user_dialogue, NAME

DIRECTION = ('The two men sit one sofa with a glass of champange, salute to each other and then to the camera. '
             'the old man exclamates "Congratulations!" and the younger one smilingly says: "To version 0.6.4!" '
             'Then the older one calls "Hooray".')
LINES = ['the old man: Congratulations!', 'the younger one: To version 0.6.4!', 'the older one: Hooray']
PROMPT = '''subject_definitions:
<Subject 1> is the older man from <Picture 1>.
<Subject 2> is the younger man from <Picture 2>.
<Subject 3> is the living room from <Picture 5>.

summary:
[reference generation] A celebratory toast between an older man and a younger man to mark the release of version 0.6.4, featuring specific dialogue and a final cheer.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - environment and setting retained.

detailed_description:
[Shot 1] A static medium shot captures <Subject 1> and <Subject 2> seated on the dark gray sofa in <Subject 3>, holding champagne glasses. They begin by looking at each other with smiles, then clink their glasses together in a mutual salute. Following this, they simultaneously shift their gaze and raise their arms toward the camera. <Subject 1> (S1) exclaims, <d>[English] Congratulations!</d>. <Subject 2> (S2) responds with a proud smile, <d>[English] To version 0.6.4!</d>. Finally, <Subject 1> calls out, <d>[English] Hooray!</d>, accompanied by a joyful expression and a slight lift of his glass.

overall_soundscape:
Audible clink of champagne glasses, followed by the spoken dialogue and a joyful tone.

non_diegetic_music:
N/A'''
normalize_punctuation = import_module(NAME + '.vocal_events').normalize_authorized_terminal_punctuation

def composed():
    raw = data()
    raw['asset_analysis'][2].update(picture=5, description='living room', label='living room')
    raw['subjects'].append({'subject':3,'source_pictures':[5],'kind':'environment','description':'living room'})
    raw['reference_strategy']['soft_inspiration_pictures'] = [5]
    ctx = json.loads(context(DIRECTION)); ctx['picture_slots'] = [1,2,5]
    return nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(raw), json.dumps(ctx))['result']

class RepeatedDialogue(unittest.TestCase):
    def test_exact_direction(self):
        self.assertEqual(extract_user_dialogue(DIRECTION), LINES)

    def test_call_out_and_non_speech(self):
        for cue in ('calls', 'call', 'calls out', 'called out', 'calling out'):
            self.assertEqual(extract_user_dialogue(f'Aster {cue} "Hooray".'), ['Aster: Hooray'])
        for line in ('Aster reads a sign called "Hello".', 'Aster calls the dog "Hello".', 'Aster calls out into the room.'):
            self.assertEqual(extract_user_dialogue(line), [])

    def test_full_pipeline_exact_prompt(self):
        _, _, normalized, stamped, _ = composed()
        self.assertEqual(json.loads(normalized)['intent']['speech_request']['utterances'], LINES)
        result = nodes.H3DirectorResponseValidator().validate(PROMPT, normalized, stamped)
        self.assertTrue(result[3].startswith('PASS'), result[3])
        self.assertIn('restored exact user punctuation in 1', result[3])
        self.assertIn('inserted 1 unambiguously grounded speaker', result[3])
        self.assertEqual(result[1].strip(), PROMPT.replace('<Subject 1> calls out','<Subject 1> (S1) calls out').replace('Hooray!</d>','Hooray</d>').strip())

    def test_lexical_changes_and_wrong_speakers_remain_failures(self):
        _, _, normalized, stamped, _ = composed()
        for bad in (PROMPT.replace('Hooray!', 'Hurrah!'),
                    PROMPT.replace('Hooray!', 'Hooray?'),
                    PROMPT.replace('Congratulations!</d>', 'Congratulations.</d>'),
                    PROMPT.replace('<Subject 1> calls out','<Subject 2> calls out'),
                    PROMPT.replace('<Subject 1> calls out','<Subject 1> (S3) calls out'),
                    PROMPT.replace('Hooray!</d>', 'Hooray!</d> <Subject 1> (S1) calls out, <d>[English] Hooray</d>')):
            with self.subTest(bad=bad):
                self.assertEqual(normalize_punctuation(bad, json.loads(normalized)), (bad,0))
                result = nodes.H3DirectorResponseValidator().validate(bad, normalized, stamped)
                self.assertTrue(result[3].startswith('FAIL'), result[3])

    def test_idempotent(self):
        _, _, normalized, stamped, _ = composed()
        result = nodes.H3DirectorResponseValidator().validate(PROMPT, normalized, stamped)
        self.assertEqual(normalize_punctuation(result[1], json.loads(normalized)), (result[1],0))
