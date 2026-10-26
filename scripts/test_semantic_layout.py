import unittest
from knowledge_store import Record

class SemanticDescriptionTest(unittest.TestCase):
    def test_context_changes_embedding_without_changing_display_text(self):
        m=dict(id='semaforo',kind='entity',label='Semáforo',summary='Resumo')
        r=Record('',m,'Corpo original','hash')
        old=r.semantic_text
        m['semantic_description']='Sincronização de processos concorrentes.'
        self.assertNotEqual(old,r.semantic_text)
        self.assertEqual(r.semantic_text,'Semáforo\nSincronização de processos concorrentes.')
        self.assertEqual(r.body,'Corpo original')

class ProjectionReuseTest(unittest.TestCase):
    def test_input_changes_invalidate_projection_and_metadata_changes_preserve_it(self):
        import tempfile,json,hashlib
        from pathlib import Path
        from unittest.mock import patch
        from graph_tools import preferred_layout,semantic_input_hash
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); out=root/'.generated'; (out/'embeddings').mkdir(parents=True)
            (root/'knowledge.yml').write_text('title: Test')
            vectors=b'vectors'; (out/'embeddings/entities.npy').write_bytes(vectors)
            h=hashlib.sha256(vectors).hexdigest(); records=[dict(id='one',text='definition')]
            layout=dict(method='semantic-tsne-3d-v1',matrixSha256=h,semanticInputSha256=semantic_input_hash(records),positions={'one':dict(x=1,y=2,z=3)})
            (out/'semantic-layout.json').write_text(json.dumps(layout)); (out/'embeddings/manifest.json').write_text(json.dumps(dict(matrixSha256=h)))
            graph={'nodes':[dict(id='one',theme='topic')]}
            with patch('graph_tools.entity_records',return_value=records):
                result=preferred_layout(root,graph,b'new graph metadata')
                self.assertEqual(result['method'],'semantic-tsne-3d-v1')
                self.assertEqual(result['positions'],layout['positions'])
                self.assertEqual(result['graphSha256'],hashlib.sha256(b'new graph metadata').hexdigest())
            with patch('graph_tools.entity_records',return_value=[dict(id='one',text='changed definition')]):
                self.assertIn('fallbackReason',preferred_layout(root,graph,b'graph'))
            (out/'embeddings/entities.npy').write_bytes(b'corrupt')
            with patch('graph_tools.entity_records',return_value=records):
                self.assertIn('fallbackReason',preferred_layout(root,graph,b'graph'))
