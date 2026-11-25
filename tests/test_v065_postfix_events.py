import json
import unittest
from importlib import import_module
from test_v065_dialogue_clause_authority import data, context, nodes, NAME

DIRECTION = ('The two men sit one sofa with a glass of champange, salute to each other and then to the camera. '
             'the old man exclamates "Congratulations!" and the younger one smilingly says: "To version 0.6.4!"')
PROMPT = '''subject_definitions:
<Subject 1> is the older man with glasses and a light blue button-down shirt, from <Picture 1>.
<Subject 2> is the younger man with dark hair and a white button-down shirt, from <Picture 2>.
<Subject 3> is the bright living room with a grey sofa and light-colored wooden floors, from <Picture 5>.

summary:
[reference generation] A medium shot of two men sitting on a grey sofa in a living room, holding champagne glasses. They clink their glasses together, then turn toward the camera, raising their glasses. The older man exclaims "Congratulations!" and the younger man smiles and says "To version 0.6.4!".

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.

detailed_description:
[Shot 1] A static medium shot of <Subject 3>. <Subject 1> and <Subject 2> are seated side-by-side on the grey sofa, both holding champagne glasses. They lean slightly forward and clink their glasses together. Immediately after the clink, they pivot their torsos and heads toward the camera, raising their glasses higher. <Subject 1>'s face is warm and proud; his mouth opens wide as he exclaims with a hearty expression. <Subject 2> maintains a bright, proud smile, tilting his head slightly as he looks directly into the lens.
<d>[English] Congratulations!</d> (S1)
<d>[English] To version 0.6.4!</d> (S2)

overall_soundscape:
Audible room tone, the distinct 'clink' of champagne flutes, and the vocal delivery of the lines.

non_diegetic_music:
N/A'''
normalize = import_module(NAME + '.vocal_events').normalize_detached_postfix_events

def composed():
    raw = data()
    raw['asset_analysis'][2]['picture'] = 5
    raw['subjects'].append({'subject':3,'kind':'environment','name':'room','source_pictures':[5],'description':'Bright living room'})
    raw['reference_strategy']['soft_inspiration_pictures'] = [5]
    ctx = json.loads(context(DIRECTION)); ctx['picture_slots'] = [1,2,5]
    _, _, normalized, stamped, _ = nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(raw), json.dumps(ctx))['result']
    return normalized, stamped

class PostfixEvents(unittest.TestCase):
    def test_exact_live_prompt(self):
        normalized, stamped = composed()
        v = nodes.H3DirectorResponseValidator().validate(PROMPT, normalized, stamped)
        self.assertTrue(v[3].startswith('PASS'), v[3])
        self.assertIn('canonicalized 2 detached dialogue event(s)', v[3])
        expected = PROMPT.replace('<d>[English] Congratulations!</d> (S1)', '<Subject 1> (S1) <d>[English] Congratulations!</d>').replace('<d>[English] To version 0.6.4!</d> (S2)', '<Subject 2> (S2) <d>[English] To version 0.6.4!</d>')
        self.assertEqual(v[1].strip(), expected.strip())
        self.assertEqual(normalize(expected,json.loads(normalized)),(expected,0))

    def test_reject_conflicts(self):
        normalized, _ = composed(); raw = json.loads(normalized)
        for text in (PROMPT.replace('</d> (S1)', '</d> (S2)',1),
                     PROMPT.replace('Congratulations!</d>', 'Cheers!</d>'),
                     PROMPT.replace('<d>[English] To version 0.6.4!</d> (S2)','<Subject 1> (S2) <d>[English] To version 0.6.4!</d>'),
                     PROMPT.replace('<d>[English] To version 0.6.4!</d> (S2)','[Shot 2] <d>[English] To version 0.6.4!</d> (S2)'),
                     PROMPT.replace('<d>[English] To version 0.6.4!</d> (S2)','He walks away.\n<d>[English] To version 0.6.4!</d> (S2)')):
            with self.subTest(text=text[-300:]):
                self.assertEqual(normalize(text,raw),(text,0))

    def test_reject_unknown_authority_and_missing_staged_subject(self):
        normalized, _ = composed(); raw = json.loads(normalized)
        text = PROMPT.replace('<Subject 2> are seated','the younger man is seated').replace('<Subject 2> maintains','the younger man maintains')
        self.assertEqual(normalize(text,raw),(text,0))
        raw['intent']['speech_request']['authority']='analyst'
        self.assertEqual(normalize(PROMPT,raw),(PROMPT,0))

    def test_first_speaker_not_subject_one_repeats(self):
        raw=data(); raw['intent']['speech_request'].update(authority='user_direction',utterances=['the younger one: First.', 'the old man: Second.', 'the younger one: Third.'])
        text = PROMPT.replace('<d>[English] Congratulations!</d> (S1)\n<d>[English] To version 0.6.4!</d> (S2)', '<d>[English] First.</d> (S1)\n<d>[English] Second.</d> (S2)\n<d>[English] Third.</d> (S1)')
        fixed, count = normalize(text,raw)
        self.assertEqual(count,3)
        self.assertIn('<Subject 2> (S1) <d>[English] First.</d>',fixed)
        self.assertIn('<Subject 1> (S2) <d>[English] Second.</d>',fixed)
        self.assertIn('<Subject 2> (S1) <d>[English] Third.</d>',fixed)
