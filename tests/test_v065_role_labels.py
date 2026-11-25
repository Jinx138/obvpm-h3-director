"""User prompt with a reconstructed cross-mentioned Analyst role context."""
import json
import unittest
from test_v065_dialogue_clause_authority import data, context, nodes, resolve
from test_v065_repeated_dialogue import DIRECTION
DIRECTION=DIRECTION.replace('To version 0.6.4!', 'To version oh six five!')
PROMPT='''subject_definitions:
<Subject 1> is the older man, a middle-aged to older man with greyish-brown hair, wearing glasses and a light blue button-down shirt, from <Picture 1>.
<Subject 2> is the younger man, a younger man with dark wavy hair, wearing a white button-down shirt, from <Picture 2>.
<Subject 3> is the living room setting featuring the grey sofa where the men are seated, from <Picture 5>.

summary:
[reference generation] A medium shot of two men sitting on a grey sofa with champagne glasses. They salute each other and then to the camera. The older man exclaims "Congratulations!" and the younger one smilingly says: "To version oh six five!". Then the older one calls "Hooray".

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - identity and visible characteristics retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - environment and setting retained.

detailed_description:
[Shot 1] A brightly lit modern living room with a large grey fabric sofa and light-colored wooden floors. <Subject 1> and <Subject 2> sit side by side on the sofa, holding champagne glasses. They raise their glasses and clink them together. <Subject 1> exclaims, <d>[English] Congratulations!</d> <Subject 2> smiles and says, <d>[English] To version oh six five!</d> Both men then turn their glasses toward the camera. <Subject 1> calls out, <d>[English] Hooray</d> with a wide, joyful expression, while <Subject 2> maintains a warm smile.

overall_soundscape:
Audible room tone, the clink of champagne glasses, and the vocal exclamations of the men.

non_diegetic_music:
N/A'''
def composed():
    raw=data()
    raw['subjects'][1]['description']='The younger man smiles at the older man.'
    raw['asset_analysis'][2].update(picture=5, description='living room', label='living room')
    raw['subjects'].append({'subject':3,'source_pictures':[5],'kind':'environment','description':'living room'})
    raw['reference_strategy']['soft_inspiration_pictures']=[5]
    ctx=json.loads(context(DIRECTION)); ctx['picture_slots']=[1,2,5]
    return nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(raw),json.dumps(ctx))['result']
class ExplicitRoleLabels(unittest.TestCase):
    def test_full_user_prompt_with_cross_mentioned_role(self):
        _, _, normalized, stamped, _ = composed()
        analysis = json.loads(normalized)
        self.assertEqual([resolve(s, analysis) for s in ['the old man', 'the younger one', 'the older one']], [1, 2, 1])
        result = nodes.H3DirectorResponseValidator().validate(PROMPT, normalized, stamped)
        self.assertTrue(result[3].startswith('WARNING'), result[3])
        self.assertIn('inserted 3 unambiguously grounded speaker', result[3])
        self.assertEqual(result[1].strip(), PROMPT.replace('<Subject 1> exclaims', '<Subject 1> (S1) exclaims').replace('<Subject 2> smiles and says', '<Subject 2> (S2) smiles and says').replace('<Subject 1> calls out', '<Subject 1> (S1) calls out').strip())

    def test_duplicate_explicit_roles_remain_unresolved(self):
        raw = data()
        raw['subjects'][1]['name'] = 'older-man'
        raw['asset_analysis'][1]['label'] = 'old man'
        self.assertIsNone(resolve('the older one', raw))

    def test_conflicting_explicit_labels_remain_unresolved(self):
        raw = data()
        raw['asset_analysis'][0]['label'] = 'younger man'
        self.assertIsNone(resolve('the older one', raw))
        self.assertIsNone(resolve('the younger one', raw))

    def test_wrong_speaker_is_not_repaired(self):
        _, _, normalized, stamped, _ = composed()
        bad = PROMPT.replace('<Subject 1> calls out', '<Subject 2> calls out')
        result = nodes.H3DirectorResponseValidator().validate(bad, normalized, stamped)
        self.assertTrue(result[3].startswith('FAIL'), result[3])
        self.assertNotIn('inserted 3 unambiguously grounded speaker', result[3])

if __name__ == '__main__':
    unittest.main()
