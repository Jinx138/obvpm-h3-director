import unittest,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
SEMVER=re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$')
class Metadata(unittest.TestCase):
 def test_workflows(self):
  version=re.search(r'^version = "([^"]+)"', (ROOT/'pyproject.toml').read_text(),re.M)[1]
  self.assertEqual(version,'0.6.6');self.assertIsNotNone(SEMVER.fullmatch(version));self.assertIsNone(SEMVER.fullmatch('0.6.4.dev11'))
  for p in (ROOT/'examples').glob('*.json'):
   data=json.loads(p.read_text());graphs=[data,*data.get('definitions',{}).get('subgraphs',[])]
   for g in graphs:
    for n in g['nodes']:
     v=n.get('properties',{}).get('ver')
     if v is not None:self.assertTrue(v=='unknown' or re.fullmatch(r'[0-9a-fA-F]{40}',v) or SEMVER.fullmatch(v),(p.name,n['id'],v))
     if n['type'].startswith('H3Director'):self.assertEqual(v,version);self.assertEqual(n['properties']['cnr_id'],'h3-obvpm-director')
 def test_setup_note_unconnected(self):
  d=json.loads((ROOT/'examples/H3-Director-Core-Workspace.json').read_text());g=d['definitions']['subgraphs'][0]
  notes=[n for n in g['nodes'] if n['type']=='MarkdownNote'];self.assertEqual(len(notes),1);n=notes[0]
  self.assertEqual(n['inputs'],[]);self.assertEqual(n['outputs'],[])
  for l in g['links']: self.assertNotIn(n['id'],[l['origin_id'],l['target_id']])
  self.assertIn('mradermacher',n['widgets_values'][0]);self.assertIn('8192',n['widgets_values'][0]);self.assertGreaterEqual(g['state']['lastNodeId'],n['id'])
