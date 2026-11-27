"""External skills: selection, request rendering and frozen provenance."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NAME = 'director_v066_external_skills_tests'
spec = importlib.util.spec_from_file_location(NAME, ROOT/'__init__.py', submodule_search_locations=[str(ROOT)])
pkg = importlib.util.module_from_spec(spec)
sys.modules[NAME] = pkg
spec.loader.exec_module(pkg)
skills = sys.modules[NAME+'.flavour_skills']
assembler = sys.modules[NAME+'.prompt_skill']
nodes = sys.modules[NAME+'.nodes']


class ExternalSkills(unittest.TestCase):
    def setUp(self):
        self.profile = skills.make_profile('auto', 'casual_comedy', 'restrained', 'tender', 'Notes {literal}')

    def test_selected_only_and_stage_specific(self):
        for stage in ('analyst', 'composer'):
            manifest = skills.manifest(self.profile, stage, 'new')
            modules = [x['name'] for x in manifest['modules']]
            self.assertEqual([x for x in modules if x.startswith('styles/')], [f'styles/casual_comedy_{stage}.txt'])
            self.assertEqual([x for x in modules if x.startswith('genres/')], [f'genres/auto_{stage}.txt'])
            self.assertIn('performance/restrained.txt', modules)
            self.assertFalse(any(x.startswith(('tones/', 'continuity_')) for x in modules))
            self.assertEqual('dialogue/composer.txt' in modules, stage == 'composer')
            self.assertIn('Notes {literal}', skills.compose_system(self.profile, stage))
        self.assertIn('continuity_analyst.txt', [x['name'] for x in skills.manifest(self.profile, 'analyst', 'extend')['modules']])

    def test_tone_only_when_applicable(self):
        selected = skills.make_profile('auto', 'adult_nsfw', 'adaptive', 'playful')
        modules = [x['name'] for x in skills.manifest(selected, 'analyst')['modules']]
        self.assertEqual([x for x in modules if x.startswith('tones/')], ['tones/playful.txt'])
        self.assertFalse(any(x.startswith('performance/') for x in modules))

    def test_user_braces_are_not_template_syntax(self):
        direction = 'A sign reads "{not a template}".'
        analysis = json.dumps({'intent': {'speech_request': {'required': False}}, 'note': '{raw}'})
        for operation in ('new', 'extend', 'prepend', 'bridge'):
            a = assembler.analysis_user_prompt(direction, 5.2, [1], operation=operation)
            c = assembler.composer_user_prompt(direction, 5.2, [1], analysis, operation=operation)
            self.assertIn(direction, a)
            self.assertIn(direction, c)
            self.assertIn(analysis, c)

    def test_alternating_speaker_contract_in_full_composer_input(self):
        data = {'subjects': [
            {'subject': 1, 'kind': 'person', 'name': 'Aster', 'source_pictures': [1]},
            {'subject': 2, 'kind': 'person', 'name': 'Bryn', 'source_pictures': [2]},
        ], 'intent': {'speech_request': {'required': True, 'mode': 'preserve', 'language': 'English',
            'utterances': ['Bryn: Ready?', 'Aster: Yes.', 'Bryn: Really?', 'Aster: Absolutely.']}}}
        system = skills.compose_system(self.profile, 'composer')
        user = assembler.composer_user_prompt('Alternate speakers.', 8, [1, 2], json.dumps(data))
        self.assertIn('Correct: S1, S2, S1, S2.', system)
        self.assertNotIn('assigned in actual vocal order', system)
        for i, subject, speaker in [(1, 2, 1), (2, 1, 2), (3, 2, 1), (4, 1, 2)]:
            self.assertIn(f'Event {i}: <Subject {subject}> (S{speaker})', user)
        self.assertIn('Event numbers are NOT speaker numbers', user)

    def test_edited_template_changes_provenance_and_rejects_old_capture(self):
        profile = skills.make_profile('auto', 'general')
        request = nodes.H3DirectorRequestBuilder().build('A curtain moves.', 5.2, profile)['result']
        raw = json.dumps({'asset_analysis': [], 'subjects': [], 'intent': {'dominant_action': 'A curtain moves.'}})
        old = skills.manifest(profile, 'analyst')
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'flavour_skills'
            shutil.copytree(skills._DIR, directory)
            with patch.object(skills, '_DIR', directory):
                path = directory/'templates/analyst_new.txt'
                path.write_text(path.read_text()+'\nReturn the JSON object.', encoding='utf-8')
                current = skills.manifest(profile, 'analyst')
                self.assertEqual(old['sha256'], current['sha256'])
                self.assertNotEqual(old['request_templates']['sha256'], current['request_templates']['sha256'])
                with self.assertRaisesRegex(ValueError, 'Director skill mismatch for analyst'):
                    nodes.H3DirectorAnalysisCompose().compose_request(raw, request[3])

    def test_unused_operation_template_does_not_change_new_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'flavour_skills'
            shutil.copytree(skills._DIR, directory)
            before = skills.manifest(self.profile, 'composer', 'new')
            with patch.object(skills, '_DIR', directory):
                path = directory/'templates/composer_continuity.txt'
                path.write_text(path.read_text()+'\nExtra operation instruction.', encoding='utf-8')
                self.assertEqual(before, skills.manifest(self.profile, 'composer', 'new'))


if __name__ == '__main__':
    unittest.main()
