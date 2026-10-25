import unittest,sys,json,copy,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from graph_tools import validate,load_graph,layout_for,check_layout
S=Path(__file__).resolve().parent
FIX={'schemaVersion':1,'bookUrl':'http://localhost/','bibliography':{},'sources':{'s':{'chapter':0,'path':'evidence/manual.html','sourceFile':'manual.md','section':'Web e Internet','anchor':'web','citations':[]}},'nodes':[{'id':'web','label':'Web','type':'concept','theme':'web','summary':'Sistema','detail':'Sistema sobre Internet','sources':['s']},{'id':'internet','label':'Internet','type':'concept','theme':'web','summary':'Infraestrutura','detail':'Infraestrutura da Web','sources':['s']}],'edges':[{'id':'uses','source':'web','target':'internet','label':'usa','summary':'A Web usa a Internet','sources':['s']}]}
class GraphTests(unittest.TestCase):
 def test_reference_and_example(self):
  self.assertEqual(validate(FIX),[])
  g=copy.deepcopy(FIX);raw=json.dumps(g).encode()
  layout=layout_for(g,raw);check_layout(layout,g,raw)
  with self.assertRaises(ValueError):check_layout(layout,g,raw+b' ')
 def test_invalid_refs_and_collision(self):
  g=copy.deepcopy(FIX);g['edges'][0]['id']=g['nodes'][0]['id'];g['edges'][0]['sources']=['missing'];g['edges'][0]['target']='absent'
  self.assertGreaterEqual(len(validate(g)),3)
 def test_empty_and_custom_theme(self):
  g=copy.deepcopy(FIX);g['nodes'][0]['theme']='history'; raw=json.dumps(g).encode();check_layout(layout_for(g,raw),g,raw)
  g['nodes']=[];g['edges']=[];raw=json.dumps(g).encode();check_layout(layout_for(g,raw),g,raw)
 def test_extract_preserves_source_excludes_nested_destination(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);f=root/'a.md';f.write_text('# A\nA Web usa a Internet.'); original=f.read_bytes()
   result=subprocess.run([sys.executable,str(S/'extract_corpus.py'),str(root),'--output',str(root/'extracted')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(f.read_bytes(),original)
   units=[json.loads(x) for x in (root/'extracted/units.jsonl').read_text().splitlines()];self.assertEqual(len(units),1)
   result=subprocess.run([sys.executable,str(S/'extract_corpus.py'),str(root),'--output',str(root/'extracted')],capture_output=True)
   self.assertNotEqual(result.returncode,0)
if __name__=='__main__':unittest.main()
