"""Offline tests of the consolidated dev10e engine; no model inference."""
import importlib.util, itertools, json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
NAME='director_dev11_engine'
spec=importlib.util.spec_from_file_location(NAME,ROOT/'__init__.py',submodule_search_locations=[str(ROOT)])
pkg=importlib.util.module_from_spec(spec);sys.modules[NAME]=pkg;spec.loader.exec_module(pkg)
nodes=sys.modules[NAME+'.nodes']; skills=sys.modules[NAME+'.flavour_skills']
class Engine(unittest.TestCase):
 def test_all_skill_combinations(self):
  for genre,style,perf,tone,stage,op in itertools.product(skills.GENRES,skills.STYLES,skills.PERFORMANCE,skills.INTIMACY_TONES,('analyst','composer'),('new','extend','prepend','bridge')):
   p=skills.make_profile(genre,style,perf,tone); m=skills.manifest(p,stage,op)
   names=[x['name'] for x in m['modules']]; self.assertEqual([x for x in names if x.startswith('styles/')],[f'styles/{style}_{stage}.txt']); self.assertTrue(m['sha256'])
 def test_pipeline_and_frozen_state(self):
  profile=nodes.H3DirectorFlavour().render('auto','general','adaptive','adaptive','')[0]
  request=nodes.H3DirectorRequestBuilder().build('A curtain moves gently.',5.2,profile)['result']
  raw=json.dumps({'asset_analysis':[],'subjects':[],'intent':{'dominant_action':'A curtain moves gently.'}})
  gate=nodes.H3DirectorAnalysisSnapshot(); captured=gate.snapshot(False,raw_analysis=raw,director_context=request[3])['result']; self.assertEqual(gate.check_lazy_status(materialized=True),[])
  result=nodes.H3DirectorAnalysisCompose().compose_request(*captured[:2])['result']; self.assertEqual(json.loads(result[3])['direction'],'A curtain moves gently.')
  self.assertEqual(json.loads(result[2])['director_flavour']['directing_style'],'general')
  edited=nodes.H3DirectorShotState(); out=edited.store(materialized=False,current_direction='test',current_h3_prompt='prompt',current_analysis=result[2],current_validation='PASS')['result']; self.assertEqual(out[0],'prompt'); self.assertEqual(out[-1],'PASS'); self.assertEqual(edited.check_lazy_status(materialized=True),[])
 def test_portable_graph(self):
  for path in (ROOT/'examples').glob('*.json'):
   d=json.loads(path.read_text()); nd={n['id']:n for n in d['nodes']}; self.assertEqual(len(nd),len(d['nodes']))
   for lid,s,si,t,ti,typ in d['links']:
    self.assertIn(lid,nd[s]['outputs'][si]['links']);self.assertEqual(nd[t]['inputs'][ti]['link'],lid)
   b=next(n for n in nd.values() if n['type']=='H3DirectorRequestBuilder'); self.assertIsNotNone(next(i for i in b['inputs'] if i['name']=='flavour_profile')['link'])
if __name__=='__main__': unittest.main()
