"""Check actual selected skill payloads and preserved protocol, not LLM quality."""
import itertools
import json
import unittest
from test_v066_external_skills import skills, assembler


class CreativeSkills(unittest.TestCase):
    def test_all_profile_combinations_select_only_requested_modules(self):
        for genre, style, perf, tone, operation, stage in itertools.product(
            skills.GENRES, skills.STYLES, skills.PERFORMANCE, skills.INTIMACY_TONES,
            ('new','extend','prepend','bridge'), ('analyst','composer')):
            profile = skills.make_profile(genre, style, perf, tone)
            modules = [m['name'] for m in skills.manifest(profile, stage, operation)['modules']]
            self.assertEqual([m for m in modules if m.startswith('styles/')], [f'styles/{style}_{stage}.txt'])
            self.assertEqual([m for m in modules if m.startswith('genres/')], [f'genres/{genre}_{stage}.txt'])
            self.assertEqual([m for m in modules if m.startswith('continuity_')], [] if operation == 'new' else [f'continuity_{stage}.txt'])
            self.assertEqual([m for m in modules if m.startswith('performance/')], [] if perf == 'adaptive' else [f'performance/{perf}.txt'])
            self.assertEqual([m for m in modules if m.startswith('tones/')], [f'tones/{tone}.txt'] if style == 'adult_nsfw' and tone != 'adaptive' else [])
            self.assertEqual('dialogue/composer.txt' in modules, stage == 'composer')

    def test_analysis_schema_shape(self):
        text = skills._read('system_analyst.txt')
        schema = json.JSONDecoder().raw_decode(text.split('RETURN STRICT JSON — REQUIRED ROOT KEYS AND SHAPE\n',1)[1])[0]
        self.assertEqual(set(schema), {'asset_analysis','subjects','intent','reference_strategy','performance_tracks','interaction_dynamics','director_notes'})
        self.assertEqual(set(schema['intent']), {'operation_hint','story_goal','user_action_anchor','micro_scene_concept','interpersonal_dynamic','specific_story_beat','visual_reason_for_shot','dominant_action','behavior_progression','micro_motion_progression','camera_intent','shot_scale','framing_priority','visible_domains','suppressed_domains','framing_transition','visibility_notes','start_state_assumption','end_state','speech_request','dialogue_plan','sound_plan'})
        self.assertEqual(set(schema['performance_tracks'][0]), {'actor_id','reference_subject','identity','user_owned_action','start_state','motion_details','response_to','timing','end_state'})
        self.assertEqual(set(schema['interaction_dynamics'][0]), {'actors','shared_action','coordination','timing_relation','contact_or_spacing'})

    def test_composer_preserves_raw_detail_and_speech_with_all_styles(self):
        analysis = {'performance_tracks':[{'actor_id':'red_car','reference_subject':None,'motion_details':'Brake at the curve; nose dips, rear unloads.'}], 'intent': {'speech_request': {'required':True,'mode':'preserve','language':'English','utterances':[{'speaker':'commentator','text':'Watch the curve!'}]}}}
        raw = json.dumps(analysis)
        for style in skills.STYLES:
            profile = skills.make_profile('auto',style)
            sys = skills.compose_system(profile,'composer')
            user = assembler.composer_user_prompt('A race commentator says "Watch the curve!"', 22.0, [], raw)
            self.assertIn(raw,user)
            self.assertIn('22.00 seconds',user)
            self.assertIn('Event 1: speaker \'commentator\' (Subject unresolved) (S1)', user)
            self.assertIn('Correct: S1, S2, S1, S2.',sys)
            self.assertIn('PERFORMANCE FIDELITY',sys)
            self.assertNotIn('5–15-second',sys)

    def test_operation_specific_prefixes(self):
        profile = skills.make_profile('auto','general')
        for op in ('new','extend','prepend','bridge'):
            sys = skills.compose_system(profile,'composer',op)
            self.assertEqual('[video continuation + reference generation]' in sys,op!='new')
            self.assertIn('`[reference generation]`',sys)


if __name__ == '__main__':
    unittest.main()
