"""dev.6: literal words + Analyst actor attribution; shot-local endpoint IDs.

Synthetic reference records reconstructed from the reported scenario; not live
LLM output or an OBVPM Pro workflow.
"""
import copy
import json
import unittest
from importlib import import_module
from test_rc18_dialogue_authority import NAME, nodes, analyst, context
from fixture_flavour import neutral_manifests

mod = import_module(NAME + '.dialogue_authority')
refs = import_module(NAME + '.reference_bindings')
resolve = import_module(NAME + '.prompt_skill')._delivery_speaker_subject

DIRECTION = ('The Android Director in Picture 3 walks in and says: "Yes yes, guys, thank you very much, now drink your french bubblewine.. ", '
             'then he toruns to the Camera, clears his throat and says "Okay, but they are right! Lets get to the new features!"')
FIRST = 'Yes yes, guys, thank you very much, now drink your french bubblewine.. '
SECOND = 'Okay, but they are right! Lets get to the new features!'
BAD = '''subject_definitions:
<Subject 1> is the older man from <Picture 1>.
<Subject 2> is the younger man from <Picture 2>.
<Subject 3> is the living room from <Picture 5>.
<Subject 4> is the modern living room from <Picture 5>.
summary:
[video continuation + reference generation] The Android Director enters and speaks.
retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - identity retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - identity retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - identity retained.
detailed_description:
[Shot 1] The Android Director walks in. He uses the megaphone to project his first line at the men. <Subject 1> and <Subject 2> remain seated. The Android Director turns to face the camera. He delivers his second line directly to the viewer.
overall_soundscape:
Mechanical whirring and metallic echo.
non_diegetic_music:
N/A'''
GOOD = BAD.replace('<Subject 3> is the living room from <Picture 5>.', '<Subject 3> is the Android Director from <Picture 3>.').replace(
    '[Shot 1] The Android Director walks in. He uses the megaphone to project his first line at the men. <Subject 1> and <Subject 2> remain seated. The Android Director turns to face the camera. He delivers his second line directly to the viewer.',
    '[Shot 1] In <Subject 4>, <Subject 3> walks in. <Subject 3> says, <d>[English] ' + FIRST.strip() + '</d>. <Subject 1> and <Subject 2> remain seated. <Subject 3> turns to face the camera, clears his throat. <Subject 3> says, <d>[English] ' + SECOND + '</d>.')


def data():
    raw = analyst()
    raw['subjects'] = [
        {'subject': 1, 'kind': 'person', 'source_pictures': [1], 'name': 'older_man', 'description': 'Older man'},
        {'subject': 2, 'kind': 'person', 'source_pictures': [2], 'name': 'younger_man', 'description': 'Younger man'},
        {'subject': 3, 'kind': 'person', 'source_pictures': [3], 'description': 'White robot holding a megaphone'},
        {'subject': 4, 'kind': 'environment', 'source_pictures': [5], 'description': 'Living room'},
    ]
    raw['asset_analysis'] = [
        {'picture': n, 'primary_role': role, 'label': label, 'description': label}
        for n, role, label in [(1,'character','older_man'),(2,'character','younger_man'),(3,'character','Android Director'),(5,'environment','living room')]
    ]
    raw['performance_tracks'] = [{'actor_id': 'android_director', 'reference_subject': 3, 'identity': 'White robot'}]
    raw['intent']['speech_request'] = {'mode': 'preserve', 'required': True, 'language': 'English', 'utterances': [
        {'speaker': 'android_director', 'text': FIRST}, {'speaker': 'android_director', 'text': SECOND}]}
    return raw


def extend_context(operation='extend'):
    c = json.loads(context(DIRECTION))
    c.update(operation=operation, picture_slots=[1,2,3,5], director_skill_manifests=neutral_manifests(operation))
    endpoint = {'subjects': [{'subject': n, 'source_pictures': [p], 'definition': f'<Subject {n}> is {label} from <Picture {p}>.'} for n,p,label in [(1,1,'older man'),(2,2,'younger man'),(3,5,'living room')]],
                'environment_subjects': [{'subject':3,'source_pictures':[5], 'description':'Living room'}],
                'picture_roles': [{'picture':5,'role':'environment','label':'living room'}]}
    c['continuity_states'] = {'start': {'scene_contract': endpoint}}
    if operation == 'bridge':
        c['continuity_states']['target'] = {'scene_contract': copy.deepcopy(endpoint)}
    return json.dumps(c)


class SemanticDialogueContinuity(unittest.TestCase):
    def composed(self, raw=None, operation='extend'):
        return nodes.H3DirectorAnalysisCompose().compose_request(json.dumps(raw or data()), extend_context(operation))['result']

    def test_literal_coverage_independent_of_speaker(self):
        speech = mod.authoritative_speech_request(DIRECTION)
        self.assertEqual(len(speech['utterances']), 2)
        self.assertEqual(speech['utterances'][1], {'speaker':'', 'text':SECOND})
        self.assertEqual(speech['unresolved_dialogue_events'], [2])
        self.assertTrue(speech['utterances'][0].endswith(FIRST))

    def test_exact_analyst_attribution_with_typo_and_pronoun(self):
        speech = mod.authoritative_speech_request(DIRECTION, data()['intent']['speech_request'])
        self.assertEqual(speech['utterances'], ['The Android Director in Picture 3: '+FIRST, 'android_director: '+SECOND])
        self.assertNotIn('unresolved_dialogue_events', speech)

    def test_missing_paraphrased_or_extra_analyst_words(self):
        evidence = data()['intent']['speech_request']
        evidence['utterances'][1]['text'] = 'Wrong words.'
        evidence['utterances'].append({'speaker':'older_man','text':'Invented.'})
        speech = mod.authoritative_speech_request(DIRECTION, evidence)
        self.assertEqual(speech['unresolved_dialogue_events'], [2])
        self.assertEqual(speech['utterances'][1]['text'], SECOND)
        self.assertEqual(len(speech['utterances']), 2)

    def test_literal_order_and_explicit_speaker_override(self):
        d = 'Aster says "First." Then she says "Second."'
        previous = {'mode':'preserve', 'utterances':['Aster: Second.', 'Bryn: First.']}
        self.assertEqual(mod.authoritative_speech_request(d, previous)['utterances'], ['Aster: First.','Aster: Second.'])

    def test_additional_analyst_confirmed_quote_and_non_speech(self):
        d = 'Aster points to a sign reading "Exit". Aster adds "Come along."'
        previous = {'mode':'preserve','utterances':['Aster: Come along.']}
        self.assertEqual(mod.authoritative_speech_request(d, previous)['utterances'], ['Aster: Come along.'])
        self.assertIsNone(mod.authoritative_speech_request('Aster reads a sign called "Exit".'))

    def test_duplicate_quote_needs_occurrence_alignment(self):
        d = 'Aster says "Yes." Then she says "Yes."'
        previous = {'mode':'preserve','utterances':['Aster: Yes.']}
        self.assertEqual(mod.authoritative_speech_request(d, previous)['unresolved_dialogue_events'], [2])
        previous['utterances'].append('Aster: Yes.')
        self.assertEqual(mod.authoritative_speech_request(d, previous)['utterances'], ['Aster: Yes.','Aster: Yes.'])

    def test_extend_and_bridge_picture_ownership(self):
        for operation in ('extend','bridge'):
            with self.subTest(operation=operation):
                system, composer, normalized, stamped, _ = self.composed(operation=operation)
                a = json.loads(normalized)
                self.assertEqual({x['subject']:x['source_pictures'] for x in a['reference_contract']['allowed_subjects']}, {1:[1],2:[2],3:[3],4:[5]})
                self.assertIn('endpoint_subject', a['continuity_contract']['start_scene']['subjects'][2])
                self.assertNotIn('subject', a['continuity_contract']['start_scene']['subjects'][2])
                self.assertEqual(resolve('The Android Director in Picture 3', a), 3)
                self.assertEqual(resolve('android_director', a), 3)
                self.assertIn('Event 1: <Subject 3> (S1)', system)
                self.assertIn('Event 2: <Subject 3> (S1)', system)
                self.assertIn('endpoint Subject numbers are historical', composer)

    def test_bad_output_rejected_corrected_output_passes(self):
        _, _, normalized, stamped, _ = self.composed()
        validator = nodes.H3DirectorResponseValidator()
        bad = validator.validate(BAD, normalized, stamped)
        self.assertIn('required speech has no canonical', bad[3]); self.assertIn('<Subject 3> must cite <Picture 3>', bad[3])
        good = validator.validate(GOOD, normalized, stamped)
        self.assertNotIn('FAIL', good[3], good[3])
        self.assertEqual(good[1].count('<Subject 3> (S1) says'), 2)
        self.assertEqual(good[1].count('<d>'), 2)
        wrong = GOOD.replace('<Subject 3> says, <d>[English] '+SECOND, '<Subject 2> (S2) says, <d>[English] '+SECOND)
        self.assertIn('FAIL', validator.validate(wrong, normalized, stamped)[3])
        # Validator recomputes from the original frozen Analyst evidence.
        edited = json.loads(normalized)
        edited['intent']['speech_request']['utterances'] = ['older_man: Fake.']
        again = validator.validate(GOOD, json.dumps(edited), stamped)
        self.assertNotIn('FAIL', again[3], again[3])

    def test_unresolved_explicit_speech_blocks_false_pass(self):
        raw = data(); raw['intent']['speech_request']['utterances'].pop()
        _, _, normalized, stamped, _ = self.composed(raw)
        result = nodes.H3DirectorResponseValidator().validate(GOOD, normalized, stamped)
        self.assertIn('unresolved user dialogue speaker attribution for event(s): 2', result[3])

    def test_endpoint_only_collision_and_unconnected_reference(self):
        bindings, issues = refs.reconcile_endpoint_subjects({3:{3}}, [{'subjects':[{'subject':3,'source_pictures':[5]},{'subject':9,'source_pictures':[9]}]}], [{'picture':3,'role':'character'},{'picture':5,'role':'environment'}], {3,5})
        self.assertEqual(bindings,{3:{3},4:{5}})
        self.assertTrue(issues)

    def test_reused_picture_role_does_not_inherit(self):
        bindings, _ = refs.reconcile_endpoint_subjects({}, [{'subjects':[{'subject':3,'source_pictures':[5]}], 'picture_roles':[{'picture':5,'role':'environment'}]}], [{'picture':5,'role':'character'}], {5})
        self.assertEqual(bindings,{})

    def test_bridge_conflicting_endpoint_only_identities_not_inherited(self):
        scenes = [{'subjects':[{'subject':3,'source_pictures':[5]}],
                   'picture_roles':[{'picture':5,'role':'character','label':label}]}
                  for label in ('Aster','Bryn')]
        bindings, issues = refs.reconcile_endpoint_subjects({}, scenes, [{'picture':5,'role':'character'}], {5})
        self.assertEqual(bindings,{})
        self.assertTrue(issues)


if __name__ == '__main__':
    unittest.main()
