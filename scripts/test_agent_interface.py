"""Cross-agent CLI and bounded navigation tests, offline and independent of a host."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote
from unittest.mock import patch

from knowledge_store import import_graph, build, generated, read_store, document_text, atomic_write
from test_pipeline import FIX

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
COMMANDS = ['validate_skill','knowledge','validate_graph','search_knowledge','generate_embeddings','analyze_graph','extract_corpus','enrich_wikipedia','prepare_environment','start_viewer']


class AgentInterfaceTests(unittest.TestCase):
    def command(self, name, *arguments):
        process = subprocess.run([sys.executable,str(SCRIPTS/(name+'.py')),*map(str,arguments),'--json'],capture_output=True,text=True,cwd=ROOT)
        payload = json.loads(process.stdout)
        self.assertEqual(set(payload),{'schemaVersion','ok','status','data','error'})
        self.assertEqual(payload['schemaVersion'],1)
        return process,payload

    def test_all_commands_offer_machine_help(self):
        for name in COMMANDS:
            with self.subTest(name=name):
                process,payload=self.command(name,'--help')
                self.assertEqual(process.returncode,0,process.stderr)
                self.assertTrue(payload['ok'])
                self.assertIn('--json',process.stderr)

    def test_usage_and_invalid_data_errors(self):
        process,payload=self.command('knowledge')
        self.assertEqual(process.returncode,2);self.assertEqual(payload['error']['code'],'usage_error')
        process,payload=self.command('validate_graph',ROOT/'examples/absent.json')
        self.assertEqual(process.returncode,1);self.assertFalse(payload['ok']);self.assertTrue(payload['error']['message'])

    def test_partial_output_has_distinct_exit_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);origin=root/'empty.md';origin.write_text('')
            process,payload=self.command('extract_corpus',origin,'--output',root/'out')
            self.assertEqual(process.returncode,3,process.stderr)
            self.assertEqual(payload['status'],'partial');self.assertFalse(payload['ok'])
            self.assertTrue((root/'out/coverage.json').exists())

    def test_skill_cli_accepts_current_directory(self):
        process,payload=self.command('validate_skill','.')
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertTrue(payload['data']['valid'])

    def test_core_check_emits_single_result(self):
        process,payload=self.command('prepare_environment','--check','--profile','core')
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertTrue(payload['data']['packages']['sqlite_fts5']['ok'])

    def test_wikipedia_progress_does_not_pollute_json(self):
        import enrich_wikipedia
        from cli_common import run
        from test_wikipedia import FakeClient
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);graph=root/'graph.json';graph.write_text(json.dumps(FIX))
            output=io.StringIO()
            with patch('enrich_wikipedia.Client',return_value=FakeClient()), patch('sys.argv',['enrich_wikipedia.py','discover',str(graph),'--report',str(root/'report.json'),'--json']), redirect_stdout(output):
                self.assertEqual(run(enrich_wikipedia.main),0)
            payload=json.loads(output.getvalue());self.assertEqual(payload['data']['entities'],2)

    def test_paginated_indexes_links_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary);graph=copy.deepcopy(FIX)
            prototype=graph['nodes'][0]
            graph['nodes']=[dict(prototype,id=f'n{i:03d}',label=f'Entidade [{i}]') for i in range(205)]
            graph['edges']=[]
            source=parent/'graph.json';source.write_text(json.dumps(graph));root=import_graph(source,parent/'project/knowledge')
            build(root);out=generated(root)
            self.assertEqual(len(list((out/'index').glob('entities-*.md'))),3)
            for file in [out/'INDEX.md',out/'llms.txt',*list((out/'index').glob('*.md'))]:
                for target in re.findall(r'\]\(([^)]+)\)',file.read_text()):
                    self.assertTrue((file.parent/unquote(target)).is_file(),f'{file}: {target}')
            last=next(r for r in read_store(root)[2] if r.metadata['id']=='n204');(root/last.path).unlink()
            # Remove enough files to shrink the number of pages.
            for record in read_store(root)[2]:
                if record.metadata['kind']=='entity' and record.metadata['id']>='n199': (root/record.path).unlink()
            build(root)
            self.assertFalse((out/'index/entities-003.md').exists())
            self.assertIn('\\[', (out/'index/entities-001.md').read_text())

    def test_standard_compatibility_field_and_invalid_metadata(self):
        from validate_skill import validate
        self.assertTrue(validate(ROOT)['valid'])
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)/'example-skill';folder.mkdir()
            path=folder/'SKILL.md'
            path.write_text('---\nname: example-skill\ndescription: Exemplo\ncompatibility: Python\n---\n\nInstruções.')
            self.assertTrue(validate(folder)['valid'])
            path.write_text('---\nname: bad--name\ndescription: Exemplo\nunsupported: true\n---\n\nInstruções.')
            self.assertFalse(validate(folder)['valid'])

    def test_documentation_discovery_links(self):
        content=(ROOT/'llms.txt').read_text()
        self.assertTrue(content.startswith('# '))
        for target in re.findall(r'\]\(([^)]+)\)',content):
            if not target.startswith('https://'):self.assertTrue((ROOT/target).is_file(),target)
        self.assertTrue((ROOT/'AGENTS.md').is_file())

if __name__=='__main__':unittest.main()
