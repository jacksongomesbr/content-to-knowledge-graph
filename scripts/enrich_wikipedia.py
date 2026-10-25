"""Discover Wikipedia articles, then apply reviewed matches to grafo-do-livro data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from graph_tools import load_graph, validate

USER_AGENT = 'ContentKnowledgeGraph/1.0 (https://github.com/jacksongomesbr/uft-cc-dwm; local research tool)'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if not unicodedata.combining(c)).strip()


def valid_url(url, language):
    parsed = urlparse(url)
    return language in ('pt', 'en') and parsed.scheme == 'https' and parsed.netloc == f'{language}.wikipedia.org' and parsed.path.startswith('/wiki/') and not parsed.fragment


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists(): temporary.unlink()


class Client:
    def __init__(self, cache, user_agent=USER_AGENT, delay=0.5, timeout=20):
        self.cache = Path(cache)
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self.last_request = 0

    def query(self, language, parameters, refresh=False):
        if language not in ('pt', 'en'): raise ValueError('Idioma não permitido.')
        params = dict(action='query', format='json', formatversion=2, maxlag=5, **parameters)
        url = f'https://{language}.wikipedia.org/w/api.php?' + urlencode(params)
        cached = self.cache / (hashlib.sha256(url.encode()).hexdigest()+'.json')
        if cached.exists() and not refresh:
            entry = json.loads(cached.read_text())
            if time.time()-entry['fetchedAt'] < 86400: return entry['response']
        for attempt in range(3):
            time.sleep(max(0, self.delay-(time.monotonic()-self.last_request)))
            self.last_request = time.monotonic()
            try:
                request = Request(url, headers={'User-Agent': self.user_agent, 'Accept':'application/json'})
                with urlopen(request, timeout=self.timeout) as response:
                    data = json.load(response)
                if 'error' in data:
                    if data['error'].get('code') in ('maxlag','ratelimited') and attempt < 2:
                        time.sleep(2**(attempt+1)); continue
                    raise ValueError(f"MediaWiki: {data['error'].get('code')}")
                atomic_json(cached, dict(fetchedAt=time.time(),response=data))
                return data
            except HTTPError as exc:
                if exc.code not in (429, 502, 503, 504) or attempt == 2: raise
                wait = exc.headers.get('Retry-After','')
                time.sleep(min(30, int(wait)) if wait.isdigit() else 2**(attempt+1))
            except (URLError, TimeoutError):
                if attempt == 2: raise
                time.sleep(2**(attempt+1))
        raise ValueError('Número máximo de tentativas atingido.')

    def pages(self, language, lookup, refresh=False):
        params = dict(prop='info|pageprops|extracts|revisions', inprop='url', ppprop='disambiguation', exintro=1, explaintext=1, exsentences=3, rvprop='ids|timestamp', redirects=1, **lookup)
        data = self.query(language, params, refresh)
        candidates = []
        for page in data.get('query',{}).get('pages',[]):
            if page.get('missing') or page.get('ns') != 0 or 'disambiguation' in page.get('pageprops',{}): continue
            url = page.get('fullurl','')
            if not valid_url(url,language): continue
            revision = page.get('revisions',[{}])[0]
            candidates.append(dict(pageid=page['pageid'], title=page['title'], url=url, language=language, extract=page.get('extract','')[:800], revision=revision.get('revid'), fetchedAt=datetime.now(timezone.utc).date().isoformat()))
        return candidates


def discover(graph, raw, client):
    entries = []
    for node in graph['nodes']:
        entry = dict(id=node['id'],label=node['label'],summary=node['summary'],status='review',candidates=[],errors=[])
        for language in ('pt','en'):
            try:
                exact = client.pages(language, dict(titles=node['label']))
                candidates = exact or client.pages(language, dict(generator='search', gsrsearch=node['label'], gsrnamespace=0, gsrlimit=3))
                for candidate in candidates:
                    candidate['titleMatch'] = normalized(candidate['title']) == normalized(node['label'])
                    entry['candidates'].append(candidate)
            except (OSError, ValueError, TimeoutError) as exc:
                entry['errors'].append(dict(language=language,error=str(exc)))
        if not entry['candidates']: entry['status'] = 'blocked' if entry['errors'] else 'no_candidates'
        entries.append(entry)
        print(f"{node['id']}: {len(entry['candidates'])} candidatos",flush=True)
    return dict(schemaVersion=1,graphSha256=hashlib.sha256(raw).hexdigest(),generatedAt=datetime.now(timezone.utc).isoformat(),note='Candidatos, não correspondências aprovadas. Revise o sentido no contexto, priorizando português.',entities=entries)


def apply_matches(graph, raw, report, decisions, client):
    if report.get('graphSha256') != hashlib.sha256(raw).hexdigest(): raise ValueError('O grafo mudou após a descoberta; execute discover novamente.')
    entries = {e['id']:e for e in report['entities']}
    node_ids = {n['id'] for n in graph['nodes']}
    if len(entries) != len(report['entities']) or set(entries) != node_ids: raise ValueError('Relatório não cobre exatamente os nós do grafo.')
    if not isinstance(decisions,dict) or set(decisions) != node_ids: raise ValueError('Decisões devem cobrir todos os IDs, inclusive os sem correspondência.')
    results = []
    for node in graph['nodes']:
        decision = decisions[node['id']]
        if not isinstance(decision,dict) or 'pageid' not in decision or not isinstance(decision.get('reason'),str) or not decision['reason'].strip(): raise ValueError(f"Justificativa ausente: {node['id']}")
        node.pop('wikipedia',None)
        if decision.get('pageid') is None:
            results.append(dict(id=node['id'],status='blocked' if entries[node['id']]['errors'] else 'no_match',reason=decision['reason']))
            continue
        chosen = next((c for c in entries[node['id']]['candidates'] if c['pageid']==decision['pageid'] and c['language']==decision.get('language')),None)
        if chosen is None: raise ValueError(f"Candidato não consta do relatório: {node['id']}")
        # Fresh server lookup validates canonical URL, redirects and disambiguation.
        current = client.pages(chosen['language'],dict(pageids=chosen['pageid']),refresh=True)
        current = next((c for c in current if c['pageid']==chosen['pageid']),None)
        if current is None: raise ValueError(f"Artigo não está mais disponível ou virou desambiguação: {node['id']}")
        if current['revision'] != chosen['revision'] or current['title'] != chosen['title']:
            raise ValueError(f"Artigo mudou desde a revisão: {node['id']}; refaça discover e a decisão.")
        wiki = {k:current[k] for k in ('title','url','language')}
        wiki['verifiedAt'] = datetime.now(timezone.utc).date().isoformat()
        if decision.get('note'):
            if not isinstance(decision['note'],str): raise ValueError('note deve ser string.')
            wiki['note'] = decision['note']
        node['wikipedia'] = wiki
        results.append(dict(id=node['id'],status='linked',reason=decision['reason'],pageid=current['pageid'],revision=current['revision'],**wiki))
    errors = validate(graph)
    if errors: raise ValueError('\n'.join(errors))
    return graph, dict(inputSha256=hashlib.sha256(raw).hexdigest(),generatedAt=datetime.now(timezone.utc).isoformat(),entities=results)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    for name in ('discover','apply'):
        sub=commands.add_parser(name);sub.add_argument('graph',type=Path)
        sub.add_argument('--report',type=Path,required=True);sub.add_argument('--cache',type=Path)
        sub.add_argument('--user-agent',default=USER_AGENT);sub.add_argument('--delay',type=float,default=0.5);sub.add_argument('--timeout',type=float,default=20)
        if name=='apply':
            sub.add_argument('--decisions',type=Path,required=True);sub.add_argument('--output',type=Path,help='Obrigatório para JSON; omitido para atualizar a base Markdown');sub.add_argument('--audit',type=Path,required=True)
    a=p.parse_args()
    if a.delay<0 or a.timeout<=0: p.error('delay deve ser não negativo; timeout deve ser positivo.')
    if not a.user_agent.strip(): p.error('User-Agent não pode estar vazio.')
    canonical = a.graph.is_dir()
    protected = {a.graph.resolve()}
    if a.command == 'apply' and not canonical and not a.output: p.error('--output é obrigatório para JSON.')
    if a.command == 'apply' and canonical and a.output: p.error('Para Markdown, omita --output: apenas os campos wikipedia dos documentos serão atualizados.')
    if a.command=='discover':
        if a.report.resolve() in protected or a.report.exists(): p.error('Use caminho novo para o relatório.')
    else:
        paths=[x for x in [a.report,a.decisions,a.output,a.audit] if x is not None]
        if len({x.resolve() for x in paths})!=len(paths) or (a.output and (a.output.resolve() in protected or a.output.exists())) or a.audit.resolve() in protected or a.audit.exists():
            p.error('Use arquivos distintos e novos para output/audit; a origem é preservada.')
    try:
        graph,raw=load_graph(a.graph)
        if canonical:
            from knowledge_store import fingerprint, update_wikipedia, build
            source_fingerprint = fingerprint(a.graph)
        client=Client(a.cache or a.report.parent/'.wikipedia-cache',a.user_agent,a.delay,a.timeout)
        if a.command=='discover':
            report=discover(graph,raw,client)
            if canonical: report['knowledgeFingerprint'] = source_fingerprint
            atomic_json(a.report,report)
            return 1 if any(e['errors'] for e in report['entities']) else 0
        report=json.loads(a.report.read_text())
        if canonical and report.get('knowledgeFingerprint') != source_fingerprint: raise ValueError('A base Markdown mudou; refaça discover e a revisão.')
        enriched,audit=apply_matches(graph,raw,report,json.loads(a.decisions.read_text()),client)
        if canonical:
            if fingerprint(a.graph) != source_fingerprint: raise ValueError('A base mudou durante a verificação; nada foi escrito.')
            changed=update_wikipedia(a.graph,enriched)
            built=build(a.graph)
            audit.update(updatedDocuments=changed,knowledgeFingerprint=fingerprint(a.graph))
            target=Path(built['generated'])/'graph.json'
        else:
            atomic_json(a.output,enriched)
            target=a.output
        audit['outputSha256']=hashlib.sha256(target.read_bytes()).hexdigest();atomic_json(a.audit,audit)
        print(f"{sum(e['status']=='linked' for e in audit['entities'])} links em {a.graph if canonical else a.output}")
        return 1 if any(e['status']=='blocked' for e in audit['entities']) else 0
    except (OSError,ValueError,KeyError,TypeError) as exc: p.exit(1,f'Wikipédia: {exc}\n')

if __name__=='__main__': raise SystemExit(main())
