"""Offline behavioral tests for Wikipedia enrichment; no external requests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from enrich_wikipedia import Client, apply_matches, discover, valid_url
from test_pipeline import FIX

ARTICLE=dict(pageid=42,title='Internet',url='https://pt.wikipedia.org/wiki/Internet',language='pt',extract='Sistema global de redes de computadores interligadas.',revision=123,fetchedAt='2026-10-25')

class FakeClient:
    def pages(self, language, lookup, refresh=False):
        return [copy.deepcopy(ARTICLE)] if language=='pt' else []

class WikipediaTests(unittest.TestCase):
    def test_disambiguation_missing_and_unsafe_urls_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            client=Client(t)
            payload={'query':{'pages':[
                dict(pageid=1,title='Mercúrio',ns=0,pageprops={'disambiguation':''},fullurl='https://pt.wikipedia.org/wiki/Mercúrio'),
                dict(pageid=2,title='Unsafe',ns=0,fullurl='javascript:alert(1)'),
                dict(pageid=3,title='Internet',ns=0,fullurl=ARTICLE['url'],revisions=[dict(revid=123)]),
                dict(pageid=4,title='Missing',missing=True,ns=0)
            ]}}
            with patch.object(client,'query',return_value=payload):
                pages=client.pages('pt',{'titles':'Web'})
            self.assertEqual([p['pageid'] for p in pages],[3])
            self.assertEqual(pages[0]['title'],'Internet')
        for url in ['https://pt.wikipedia.org.evil.test/wiki/X','https://pt.wikipedia.org:443/wiki/X','javascript:alert(1)']:
            self.assertFalse(valid_url(url,'pt'))
    def test_review_required_and_no_match(self):
        graph=copy.deepcopy(FIX);raw=json.dumps(graph).encode()
        report=discover(graph,raw,FakeClient())
        # Candidates do not alter the graph or imply approved matches.
        self.assertTrue(all('wikipedia' not in n for n in graph['nodes']))
        decisions={'web':dict(pageid=None,reason='Artigo é sobre outra entidade.'),'internet':dict(pageid=42,language='pt',reason='Título e introdução correspondem ao conceito de infraestrutura de redes.')}
        enriched,audit=apply_matches(graph,raw,report,decisions,FakeClient())
        self.assertNotIn('wikipedia',enriched['nodes'][0])
        self.assertEqual(enriched['nodes'][1]['wikipedia']['url'],ARTICLE['url'])
        self.assertEqual(audit['entities'][0]['status'],'no_match')
    def test_changed_graph_and_unreviewed_candidate_rejected(self):
        graph=copy.deepcopy(FIX);raw=json.dumps(graph).encode();report=discover(graph,raw,FakeClient())
        decisions={n['id']:dict(pageid=None,reason='Sem correspondência') for n in graph['nodes']}
        with self.assertRaises(ValueError):apply_matches(graph,raw+b' ',report,decisions,FakeClient())
        decisions['web']=dict(pageid=999,language='pt',reason='Inexistente')
        with self.assertRaises(ValueError):apply_matches(graph,raw,report,decisions,FakeClient())
    def test_revision_change_rejected(self):
        graph=copy.deepcopy(FIX);raw=json.dumps(graph).encode();report=discover(graph,raw,FakeClient())
        decisions={n['id']:dict(pageid=42,language='pt',reason='Correspondência revisada') for n in graph['nodes']}
        class Changed(FakeClient):
            def pages(self,*args,**kwargs):
                article=copy.deepcopy(ARTICLE);article['revision']=124;return [article]
        with self.assertRaises(ValueError):apply_matches(graph,raw,report,decisions,Changed())
    def test_english_fallback(self):
        class English:
            def pages(self, language, lookup, refresh=False):
                a=copy.deepcopy(ARTICLE);a.update(language='en',url='https://en.wikipedia.org/wiki/Internet')
                return [a] if language=='en' else []
        graph=copy.deepcopy(FIX);raw=json.dumps(graph).encode();report=discover(graph,raw,English())
        self.assertEqual(report['entities'][0]['candidates'][0]['language'],'en')

if __name__=='__main__':unittest.main()
