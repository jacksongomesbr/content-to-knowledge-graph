import copy,json,hashlib,tempfile,unittest
from pathlib import Path
from knowledge_store import import_graph,read_store,document_text
from export_site import export_site
from test_pipeline import FIX

class ExportSiteTest(unittest.TestCase):
    def test_default_has_no_source_copy_and_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);old=base/'old.json';old.write_text(json.dumps(FIX));root=import_graph(old,base/'knowledge')
            site=base/'site';report=export_site(root,site)
            self.assertTrue((site/'index.html').is_file());self.assertEqual(report['evidenceMode'],'references')
            self.assertFalse((site/'knowledge').exists());self.assertFalse((site/'index.sqlite').exists())
            graph=json.loads((site/'graph.json').read_text());self.assertTrue(all(not Path(s['sourceFile']).is_absolute() for s in graph['sources'].values()))
            self.assertEqual(json.loads((site/'layout.json').read_text())['graphSha256'],hashlib.sha256((site/'graph.json').read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,'existe'):export_site(root,site)
            self.assertTrue((site/'index.html').is_file())

    def test_paragraphs_are_deduplicated_and_missing_sources_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);old=base/'old.json';old.write_text(json.dumps(FIX));root=import_graph(old,base/'knowledge')
            records=read_store(root)[2];source=next(r for r in records if r.metadata['kind']=='source');source.metadata.update(content_mode='original',content_sha256=hashlib.sha256(b'Paragrafo publicado.').hexdigest());(root/source.path).write_text(document_text(source.metadata,'Paragrafo publicado.'))
            nodes=[r for r in records if r.metadata['kind']=='entity']
            for node in nodes:
                node.metadata['sources']=[source.metadata['id']];node.metadata['evidence']=[dict(source=source.metadata['id'],locator='linha 1',lines=[1,1])];(root/node.path).write_text(document_text(node.metadata,node.body))
            site=base/'site';result=export_site(root,site,evidence_mode='paragraphs');self.assertEqual(result['availableReferences'],len(nodes))
            data=json.loads((site/'evidence-data.json').read_text());items=[i for r in data['records'].values() for i in r['items']];self.assertEqual(len({i['passagePath'] for i in items}),1)
            self.assertEqual(json.loads((site/items[0]['passagePath']).read_text())['text'],'Paragrafo publicado.')
            self.assertTrue(all('text' not in i for i in items))
