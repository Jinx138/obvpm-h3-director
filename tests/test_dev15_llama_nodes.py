"""Offline contracts for the current upstream llama.cpp session-based examples."""
import json
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CurrentNodes(unittest.TestCase):
 def test_current_workflows(self):
  for path in (ROOT/'examples').glob('*.json'):
   doc=json.loads(path.read_text()); graphs=[doc,*doc.get('definitions',{}).get('subgraphs',[])]
   for g in graphs:
    nodes={n['id']:n for n in g['nodes']}
    links={l['id']:l for l in [dict(zip(('id','origin_id','origin_slot','target_id','target_slot','type'),v)) if isinstance(v,list) else v for v in g['links']]}
    for lid,l in links.items():
     a,b,ai,bi=l['origin_id'],l['target_id'],l['origin_slot'],l['target_slot']; t=l['type']
     source=g['inputs'][ai] if a==-10 else nodes[a]['outputs'][ai]; dest=g['outputs'][bi] if b==-20 else nodes[b]['inputs'][bi]
     self.assertEqual(source['type'],t);self.assertEqual(dest['type'],t);self.assertIn(lid,source['linkIds'] if a==-10 else source['links']);self.assertTrue(lid in dest['linkIds'] if b==-20 else dest['link']==lid)
    self.assertFalse(any(n['type'].startswith('OllamaImageList_LlamaCpp') for n in nodes.values()))
    gen=[n for n in nodes.values() if n['type']=='LlamaCppMtmd_Generate']
    if not gen:continue
    self.assertEqual(len(gen),2)
    def src(n,k):return nodes[links[next(i['link'] for i in n['inputs'] if i['name']==k)]['origin_id']]
    sessions=[src(n,'session') for n in gen];self.assertEqual(len(set(n['id'] for n in sessions)),2)
    self.assertEqual(sessions[0]['widgets_values_named']['n_ctx'],8192)
    for i,(n,s) in enumerate(zip(gen,sessions)):
     self.assertEqual(s['type'],'LlamaCppMtmd_CreateSession');self.assertEqual(s['widgets_values_named']['mmproj_path'],'[none]');self.assertEqual(n['widgets_values_named']['session_unload'],True)
     self.assertEqual([x['name'] for x in n['inputs']],['session','images','audio','video','model_profile','system','prompt','max_tokens','seed','stop','video_with_audio','session_unload'])
     self.assertEqual([x['name'] for x in s['inputs']],['model_profile','custom_chat_template','hardware_profile','reasoning','speculative','prefill_profile','model_path','mmproj_path','custom_handler','n_ctx','verbose'])
     self.assertEqual(src(s,'model_profile')['type'],'LlamaCppMtmd_ModelProfile');self.assertEqual(src(s,'prefill_profile')['type'],'LlamaCppMtmd_PrefillProfile')
     self.assertEqual(src(s,'model_profile')['widgets_values_named']['profile'],'Qwen 3.5+ Non-thinking')
     self.assertEqual(len(src(s,'model_profile')['widgets_values']),7)
     self.assertEqual(src(n,'system')['type'],'H3DirectorVRAMHandoff' if i==0 else 'H3DirectorAnalysisCompose')
     self.assertEqual(src(n,'prompt')['id'],src(n,'system')['id'])
     self.assertEqual(next(x['link'] for x in n['inputs'] if x['name']=='images') is not None,i==0)
    for k in ('model_profile','prefill_profile'):self.assertNotEqual(src(sessions[0],k)['id'],src(sessions[1],k)['id'])
