"""Regression checks for failures found during the UI/script review."""
import copy
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from graph_tools import load_graph,validate
from knowledge_store import import_graph,build,write_lock
from evidence_passages import compile_evidence,read_text_paragraph
from start_viewer import Handler
from test_pipeline import FIX

class ReviewRegressions(unittest.TestCase):
    def test_writer_lock_prevents_interleaved_build_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'graph.json';original.write_text(json.dumps(FIX))
            base=import_graph(original,root/'knowledge')
            with write_lock(base):
                with self.assertRaisesRegex(ValueError,'escrita'): build(base)
            self.assertEqual(build(base)['changed'],4)
            self.assertFalse((base/'.write-lock').exists())

    def test_legacy_graph_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'graph.json').write_text(json.dumps(FIX))
            self.assertEqual(load_graph(tmp)[0],FIX)

    def test_empty_wikipedia_and_nontext_note_are_rejected(self):
        for value in [None,{},dict(title='Internet',url='https://pt.wikipedia.org/wiki/Internet',language='pt',verifiedAt='2026-10-25',note=123)]:
            graph=copy.deepcopy(FIX);graph['nodes'][0]['wikipedia']=value
            self.assertTrue(validate(graph))

    def test_bad_reference_metadata_rejected_before_request(self):
        source=SimpleNamespace(metadata=dict(id='s',kind='source',content_mode='reference',source_sha256='a'*64),path='sources/s.md',body='Metadata')
        for unit in [None,False,-1,{}]:
            node=SimpleNamespace(metadata=dict(id='n',kind='entity',label='N',evidence=[dict(source='s',locator='L1',lines=[1,1],unit=unit)]),key='entity:n',path='entities/n.md')
            with self.assertRaises(ValueError):compile_evidence([source,node],'abc')

    def test_heading_does_not_become_part_of_paragraph(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.md';path.write_text('# Tema\nTexto sem linha vazia\ncontinuação\n\nFim')
            first,last,text,heading=read_text_paragraph(path,[3,3])
            self.assertEqual((first,last,text,heading),(2,3,'Texto sem linha vazia\ncontinuação','Tema'))

    def test_empty_extraction_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'origin').mkdir()
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('extract_corpus.py')),str(root/'origin'),'--output',str(root/'result'),'--json'],capture_output=True,text=True)
            self.assertEqual(result.returncode,3,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'partial')

class ViewerHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);(root/'index.html').write_text('viewer')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.assets=root;self.server.graph_dir=root;self.server.payloads={};self.server.reference_items={};self.server.registered_sources={}
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path='/',headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request('GET',path,headers=headers or {})
        response=connection.getresponse();status=response.status;response.read();connection.close();return status
    def test_local_requests_allowed_foreign_host_and_origin_denied(self):
        self.assertEqual(self.request(),200)
        self.assertEqual(self.request(headers={'Host':'foreign.example'}),403)
        self.assertEqual(self.request(headers={'Origin':'https://foreign.example'}),403)
    def test_arbitrary_path_and_unknown_reference_denied(self):
        self.assertEqual(self.request('/evidence-passage?id=../../etc/passwd'),404)
        self.assertEqual(self.request('/%2e%2e/etc/passwd'),404)
