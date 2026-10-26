import hashlib
import unittest
from types import SimpleNamespace
from evidence_passages import paragraph, compile_evidence

class EvidencePassagesTests(unittest.TestCase):
    def test_expands_wrapped_paragraph_without_next_item(self):
        lines=['# Título','','Uma frase com entidade,','seguida de contexto completo.','','- Item A','- Item B']
        self.assertEqual(paragraph(lines,4,4),(3,4,'Uma frase com entidade,\nseguida de contexto completo.'))
        self.assertEqual(paragraph(lines,6,6),(6,6,'- Item A'))

    def test_invalid_range(self):
        for bounds in [(0,1),(2,1),(1,3),(True,1)]:
            with self.assertRaises(ValueError): paragraph(['texto'],*bounds)

    def test_snapshot_integrity_and_no_legacy_excerpt_fallback(self):
        body='Parágrafo inteiro com contexto.'
        source=SimpleNamespace(metadata={'id':'s','kind':'source','content_mode':'original','content_sha256':hashlib.sha256(body.encode()).hexdigest()},body=body,path='sources/s.md')
        node=SimpleNamespace(metadata={'id':'a','kind':'entity','label':'Contexto','aliases':[],'evidence':[{'source':'s','locator':'linha 1','lines':[1,1],'excerpt':'recorte errado'}]},key='entity:a',path='entities/a.md')
        payload=compile_evidence([source,node],'abc')
        self.assertEqual(payload['records']['entity:a']['items'][0]['text'],body)
        source.body='Texto alterado'
        with self.assertRaises(ValueError): compile_evidence([source,node],'abc')
        source.metadata.pop('content_mode')
        self.assertEqual(compile_evidence([source,node],'abc')['records']['entity:a']['items'][0]['status'],'unavailable')

    def test_external_source_read_and_changes(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from evidence_passages import file_sha256, resolve_reference
        with TemporaryDirectory() as folder:
            path=Path(folder)/'source.md';path.write_text('# Tema\n\nPrimeira linha\ncom contexto.\n\nOutro parágrafo.\n')
            sources={'s':{'content_mode':'reference','sourceFile':str(path),'source_sha256':file_sha256(path)}}
            ref={'id':'entity:a:0','source':'s','lines':[4,4],'status':'deferred'}
            result=resolve_reference(ref,sources)
            self.assertEqual(result['text'],'Primeira linha\ncom contexto.')
            self.assertEqual(result['heading'],'Tema')
            path.write_text('Conteúdo alterado')
            self.assertEqual(resolve_reference(ref,sources)['status'],'changed')
            path.unlink()
            self.assertEqual(resolve_reference(ref,sources)['status'],'unavailable')

    def test_external_index_contains_no_source_text_and_rejects_unknown_source(self):
        from evidence_passages import resolve_reference
        source=SimpleNamespace(metadata={'id':'s','kind':'source','content_mode':'reference','source_sha256':'a'*64},body='Somente descrição.',path='sources/s.md')
        node=SimpleNamespace(metadata={'id':'a','kind':'entity','label':'A','evidence':[{'source':'s','locator':'linha 1','lines':[1,1]}]},key='entity:a',path='entities/a.md')
        item=compile_evidence([source,node],'abc')['records']['entity:a']['items'][0]
        self.assertNotIn('text',item)
        self.assertEqual(item['status'],'deferred')
        self.assertNotEqual(resolve_reference(item,{})['status'],'available')
