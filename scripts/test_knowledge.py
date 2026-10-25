"""Behavioral tests for canonical files, index freshness and legacy export."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from graph_tools import load_graph, entity_records, semantic_input_hash
from knowledge_store import (import_graph, read_store, build, search, neighbors, atomic_write,
                             document_text, update_wikipedia, recover, generated, yaml_load)
from test_pipeline import FIX


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.original = self.parent/'old.json'
        self.original.write_text(json.dumps(FIX))
        self.root = import_graph(self.original, self.parent/'project/knowledge')

    def tearDown(self): self.temporary.cleanup()

    def record(self, kind, identifier):
        return next(r for r in read_store(self.root)[2] if r.metadata['kind']==kind and r.metadata['id']==identifier)

    def change(self, record, metadata=None, body=None):
        atomic_write(self.root/record.path, document_text(metadata or record.metadata, record.body if body is None else body))

    def test_roundtrip_and_original_preserved(self):
        graph, _ = load_graph(self.root)
        self.assertEqual(graph['sources'], FIX['sources'])
        self.assertEqual(sorted(graph['nodes'], key=lambda n:n['id']), sorted(FIX['nodes'], key=lambda n:n['id']))
        self.assertEqual(graph['edges'], FIX['edges'])
        self.assertEqual(json.loads(self.original.read_text()), FIX)
        self.assertTrue(all(r.metadata.get('basis')=='unspecified' for r in read_store(self.root)[2] if r.metadata['kind']=='relation'))
        with self.assertRaises(ValueError): import_graph(self.original, self.root)

    def test_incremental_build_and_rename(self):
        first=build(self.root); second=build(self.root)
        self.assertEqual(first['changed'],4); self.assertEqual(second['changed'],0); self.assertEqual(second['ftsUpdated'],0)
        record=self.record('entity','internet')
        (self.root/record.path).rename(self.root/'entities/another-name.md')
        with self.assertRaisesRegex(ValueError,'desatualizado'):search(self.root,'internet')
        result=build(self.root)
        self.assertEqual(result['changed'],1); self.assertEqual(result['ftsUpdated'],0)
        found=[r for r in search(self.root,'internet',kind='entity') if r['id']=='internet']
        self.assertEqual(found[0]['path'],'entities/another-name.md')

    def test_alias_search_unicode_and_semantic_invalidation(self):
        old=semantic_input_hash(entity_records(self.root))
        record=self.record('entity','internet'); metadata=dict(record.metadata,aliases=['Conexão mundial'])
        self.change(record,metadata)
        result=build(self.root)
        self.assertEqual(result['ftsUpdated'],4)
        self.assertEqual(search(self.root,'conexao mundial')[0]['id'],'internet')
        self.assertNotEqual(old,semantic_input_hash(entity_records(self.root)))
        self.assertEqual(search(self.root,'" OR 1=1 --'),[])

    def test_wikipedia_does_not_invalidate_semantic_hash(self):
        build(self.root)
        before=semantic_input_hash(entity_records(self.root)); graph,_=load_graph(self.root)
        graph['nodes'][0]['wikipedia']=dict(title='Internet',url='https://pt.wikipedia.org/wiki/Internet',language='pt',verifiedAt='2026-10-25')
        self.assertEqual(update_wikipedia(self.root,graph),1)
        self.assertEqual(before,semantic_input_hash(entity_records(self.root)))
        result=build(self.root)
        self.assertEqual(result['changed'],1);self.assertEqual(result['ftsUpdated'],0)

    def test_stale_index_rejected_and_invalid_build_preserves_database(self):
        build(self.root)
        index=generated(self.root)/'index.sqlite'
        connection=sqlite3.connect(index);before=connection.execute('SELECT count(*) FROM documents').fetchone()[0];connection.close()
        record=self.record('relation','uses');meta=dict(record.metadata,target='missing');self.change(record,meta)
        with self.assertRaises(ValueError):build(self.root)
        connection=sqlite3.connect(index);self.assertEqual(connection.execute('SELECT count(*) FROM documents').fetchone()[0],before);connection.close()
        with self.assertRaises(ValueError):search(self.root,'internet')

    def test_deleted_records_removed_from_index_and_export(self):
        build(self.root)
        for kind,identifier in [('relation','uses'),('entity','internet')]:
            record=self.record(kind,identifier);(self.root/record.path).unlink()
        result=build(self.root);self.assertEqual(result['removed'],2)
        self.assertEqual([n['id'] for n in json.loads((generated(self.root)/'graph.json').read_text())['nodes']],['web'])
        self.assertEqual(search(self.root,'infraestrutura',kind='entity'),[])

    def test_traversal_direction_cycles_and_depth(self):
        build(self.root)
        self.assertEqual(neighbors(self.root,'web',direction='out'),[dict(id='internet',distance=1)])
        self.assertEqual(neighbors(self.root,'web',direction='in'),[])
        self.assertEqual(neighbors(self.root,'internet',direction='in'),[dict(id='web',distance=1)])
        with self.assertRaises(ValueError):neighbors(self.root,'web',depth=100)

    def test_yaml_duplicate_unsafe_and_unquoted_date(self):
        with self.assertRaises(ValueError):yaml_load('id: a\nid: b')
        with self.assertRaises(ValueError):yaml_load('!!python/object/apply:os.system [echo bad]')
        self.assertEqual(yaml_load('date: 2026-10-25')['date'],'2026-10-25')

    def test_inference_requires_rationale_and_duplicate_identity_rejected(self):
        record=self.record('relation','uses');self.change(record,dict(record.metadata,basis='inferred'))
        with self.assertRaisesRegex(ValueError,'rationale'):read_store(self.root)
        self.change(record,dict(record.metadata,basis='inferred',rationale='Justificativa explícita'))
        other=self.root/'relations/duplicate.md';other.write_text((self.root/record.path).read_text())
        with self.assertRaisesRegex(ValueError,'duplicada'):read_store(self.root)

    def test_recovery_and_external_edits_protected(self):
        record=self.record('entity','web');target=self.root/record.path;before=target.read_text();after=before+'\nExtra\n'
        target.write_text(after)
        (self.root/'.update-pending.json').write_text(json.dumps([dict(path=record.path,before=before,after=after)]))
        with self.assertRaisesRegex(ValueError,'interrompida'):read_store(self.root)
        recover(self.root);self.assertEqual(target.read_text(),before)
        (self.root/'.update-pending.json').write_text(json.dumps([dict(path=record.path,before=before,after=after)]))
        target.write_text('Edição humana')
        with self.assertRaisesRegex(ValueError,'externa'):recover(self.root)


    def test_wikipedia_cli_updates_canonical_frontmatter(self):
        import enrich_wikipedia
        from test_wikipedia import FakeClient
        report=self.parent/'candidates.json';decisions=self.parent/'decisions.json';audit=self.parent/'audit.json'
        with patch('enrich_wikipedia.Client',return_value=FakeClient()), patch('sys.argv',['enrich_wikipedia.py','discover',str(self.root),'--report',str(report)]):
            self.assertEqual(enrich_wikipedia.main(),0)
        decisions.write_text(json.dumps({'web':dict(pageid=None,reason='Sem correspondência'), 'internet':dict(pageid=42,language='pt',reason='Sentido conferido')}))
        with patch('enrich_wikipedia.Client',return_value=FakeClient()), patch('sys.argv',['enrich_wikipedia.py','apply',str(self.root),'--report',str(report),'--decisions',str(decisions),'--audit',str(audit)]):
            self.assertEqual(enrich_wikipedia.main(),0)
        self.assertEqual(self.record('entity','internet').metadata['wikipedia']['title'],'Internet')
        self.assertTrue(audit.exists())
        self.assertEqual(search(self.root,'internet',kind='entity')[0]['id'],'internet')

    def test_local_evidence_is_generated_and_escaped(self):
        record=self.record('source','s');self.change(record,body='<script>unsafe()</script> Trecho original')
        build(self.root)
        html=(generated(self.root)/'evidence/manual.html').read_text()
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
        self.change(record,dict(record.metadata,path='evidence/../../escape.html'))
        with self.assertRaises(ValueError):build(self.root)

    def test_lexical_retrieval_without_ml(self):
        from search_knowledge import retrieve
        build(self.root)
        self.assertEqual(retrieve(self.root,'infraestrutura')[0]['id'],'internet')
        self.assertEqual(retrieve(self.root,'   '),[])

    def test_alias_order_and_metadata_keep_semantic_hash(self):
        record=self.record('entity','web');self.change(record,dict(record.metadata,aliases=['WWW','World Wide Web']))
        before=semantic_input_hash(entity_records(self.root))
        record=self.record('entity','web');self.change(record,dict(record.metadata,aliases=['World Wide Web','WWW'],reviewedAt='2026-10-25'))
        self.assertEqual(before,semantic_input_hash(entity_records(self.root)))

if __name__=='__main__':unittest.main()
