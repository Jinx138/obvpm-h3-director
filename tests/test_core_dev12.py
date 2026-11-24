import unittest,json,pathlib,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Core(unittest.TestCase):
 def test_links(self):
  d=json.loads((ROOT/'examples/H3-Director-Core-Workspace.json').read_text()); g=d['definitions']['subgraphs'][0]; host=next(n for n in d['nodes'] if n['type']==g['id'])
  self.assertEqual({n['type'] for n in d['nodes'] if n['id'] in [1,14]}, {'H3DirectorFlavour','H3DirectorRequestBuilder'})
  self.assertEqual(len([n for n in g['nodes'] if n['type']=='H3DirectorStatus']),1)
  for graph in [d,g]:
   nodes={n['id']:n for n in graph['nodes']}
   for l in graph['links']:
    lid,a,ai,b,bi,ty= l if isinstance(l,list) else [l[k] for k in ('id','origin_id','origin_slot','target_id','target_slot','type')]
    if a==-10:self.assertIn(lid,graph['inputs'][ai]['linkIds']);self.assertEqual(ty,graph['inputs'][ai]['type'])
    else:self.assertIn(lid,nodes[a]['outputs'][ai]['links']);self.assertEqual(ty,nodes[a]['outputs'][ai]['type'])
    if b==-20:self.assertIn(lid,graph['outputs'][bi]['linkIds']);self.assertEqual(ty,graph['outputs'][bi]['type'])
    else:self.assertEqual(lid,nodes[b]['inputs'][bi]['link']);self.assertEqual(ty,nodes[b]['inputs'][bi]['type'])
  self.assertEqual([p['name'] for p in host['inputs']],[p['name'] for p in g['inputs']]);self.assertEqual([p['name'] for p in host['outputs']],[p['name'] for p in g['outputs']])
 def test_independent_profiles_and_context(self):
  d=json.loads((ROOT/'examples/H3-Director-Core-Workspace.json').read_text()); g=d['definitions']['subgraphs'][0]
  nodes={n['id']:n for n in g['nodes']}; links={l['id']:l for l in g['links']}
  gen=[nodes[2],nodes[6]]; sessions=[nodes[links[next(i['link'] for i in n['inputs'] if i['name']=='session')]['origin_id']] for n in gen]; self.assertEqual(sessions[0]['widgets_values_named']['n_ctx'],8192); self.assertEqual(sessions[0]['widgets_values'][3],8192)
  for role in ['model_profile','prefill_profile']:
   ids=[links[next(i['link'] for i in n['inputs'] if i['name']==role)]['origin_id'] for n in sessions]
   self.assertNotEqual(*ids)
   for i in ids:self.assertFalse(nodes[i]['flags'].get('collapsed',False))
  self.assertGreaterEqual(g['state']['lastNodeId'],max(nodes))
 def test_status_is_passthrough(self):
  spec=importlib.util.spec_from_file_location('status',ROOT/'director_status.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  for v in ['PASS — checks passed','FAIL\n- test','WARNING — missing boundary']:
   self.assertEqual(m.H3DirectorStatus().inspect(v)['result'],(v,))
  self.assertFalse(getattr(m.H3DirectorStatus,'OUTPUT_NODE',False))
