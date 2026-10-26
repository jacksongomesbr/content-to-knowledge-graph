"""Serve the bundled browser viewer with a graph; Markdown requires PyYAML; legacy JSON uses the standard library."""
from cli_common import Parser, emit, run
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs
import webbrowser
from graph_tools import load_graph, layout_for, check_layout, preferred_layout


class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.respond(False)
    def do_HEAD(self): self.respond(True)
    def respond(self, head):
        # Host/Origin checks prevent a foreign page from rebinding this local reader.
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host','').lower() not in allowed:
            self.send_error(403); return
        origin=self.headers.get('Origin')
        if origin and (urlsplit(origin).scheme!='http' or urlsplit(origin).netloc.lower() not in allowed):
            self.send_error(403); return
        path=unquote(urlsplit(self.path).path)
        try:
            if path == '/evidence-passage':
                key = parse_qs(urlsplit(self.path).query).get('id', [''])[0]
                item = self.server.reference_items.get(key)
                if item is None: self.send_error(404); return
                from evidence_passages import resolve_reference
                content=json.dumps(resolve_reference(item,self.server.registered_sources)).encode(); mime='application/json; charset=utf-8'
            elif path in self.server.payloads:
                content=self.server.payloads[path]; mime='application/json; charset=utf-8'
            else:
                # Serve only bundled assets and explicitly named evidence folders.
                relative=path.lstrip('/') or 'index.html'
                base=self.server.graph_dir if relative.startswith('evidence/') else self.server.assets
                target=(base/relative).resolve()
                if not target.is_relative_to(base.resolve()) or not target.is_file(): self.send_error(404); return
                content=target.read_bytes(); mime=mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
            self.send_response(200); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
            if not head: self.wfile.write(content)
        except (OSError,ValueError): self.send_error(404)


def main():
    p=Parser(description=__doc__)
    p.add_argument('graph',type=Path,help='base Markdown, graph.json ou diretório que o contém')
    p.add_argument('--layout',type=Path); p.add_argument('--config',type=Path,help='JSON com title, subtitle, types e themes opcionais')
    p.add_argument('--port',type=int,default=0,help='0 escolhe uma porta livre'); p.add_argument('--no-open',action='store_true')
    p.add_argument('--title',default='Grafo de conhecimento'); p.add_argument('--export-layout',type=Path)
    a=p.parse_args()
    if not 0 <= a.port <= 65535: p.error('port deve estar entre 0 e 65535.')
    try:
        canonical = a.graph.is_dir() and ((a.graph/'knowledge.yml').exists() or (a.graph/'knowledge/knowledge.yml').exists())
        if canonical:
            from knowledge_store import build
            built = build(a.graph)
            graph_path = Path(built['generated'])/'graph.json'
        else:
            graph_path=a.graph/'graph.json' if a.graph.is_dir() else a.graph
        graph,raw=load_graph(graph_path)
        if a.layout:
            layout=json.loads(a.layout.read_text()); check_layout(layout,graph,raw)
        else: layout=preferred_layout(a.graph,graph,raw) if canonical else layout_for(graph,raw)
        config=dict(title=a.title,subtitle=f"{len(graph['nodes'])} entidades · {len(graph['edges'])} relações")
        if a.config: config.update(json.loads(a.config.read_text()))
        config['layoutDescription'] = ('Posições calculadas por similaridade semântica dos textos (t-SNE 3D). Vizinhanças são aproximadas; distâncias entre grupos não são uma escala global de significado.' if layout.get('method') == 'semantic-tsne-3d-v1' else 'Posições editoriais por tema; distância não mede similaridade semântica.')
        if not isinstance(config.get('title'),str) or not isinstance(config.get('subtitle'),str): raise ValueError('Título e subtítulo devem ser strings.')
        for value in config.get('types',{}).values():
            import re
            if not all(isinstance(value.get(k),str) for k in ['label','plural','color','shape']) or not re.fullmatch(r'#[a-fA-F0-9]{6}',value['color']): raise ValueError('Catálogo de tipos inválido.')
        if not all(isinstance(v,str) for v in config.get('themes',{}).values()): raise ValueError('Catálogo de temas inválido.')
    except (OSError,ValueError,TypeError,AttributeError) as exc: p.exit(1,f'Não foi possível abrir o grafo: {exc}\n')
    assets=Path(__file__).resolve().parents[1]/'assets/viewer/dist'
    if not (assets/'index.html').exists(): p.exit(1,'Visualizador compilado ausente; veja references/running.md.\n')
    if a.export_layout:
        with a.export_layout.open('x') as stream: json.dump(layout,stream,ensure_ascii=False,indent=2)
    passages = graph_path.parent/'evidence/passages.json'
    try:
        evidence = json.loads(passages.read_text()) if passages.exists() else {'schemaVersion': 1, 'records': {}}
        import hashlib
        if not isinstance(evidence,dict) or not isinstance(evidence.get('records'),dict): raise ValueError('Formato de evidências inválido.')
        if evidence.get('graphSha256') and evidence['graphSha256'] != hashlib.sha256(raw).hexdigest():
            raise ValueError('Evidências desatualizadas; reconstrua a base.')
        items=[item for record in evidence['records'].values() for item in record['items']]
        if len({item['id'] for item in items})!=len(items): raise ValueError('IDs de evidência duplicados.')
    except (OSError,ValueError,KeyError,TypeError) as exc: p.exit(1,f'Não foi possível carregar as referências: {exc}\n')
    try: server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    except OSError as exc: p.exit(1,f'Não foi possível iniciar servidor: {exc}\n')
    server.assets=assets; server.graph_dir=graph_path.resolve().parent
    server.registered_sources = graph.get('sources', {})
    server.reference_items = {item['id']:item for record in evidence['records'].values() for item in record['items']}
    server.payloads={'/evidence-data.json': json.dumps(evidence).encode(), '/graph.json':raw,'/layout.json':json.dumps(layout).encode(),'/viewer-config.json':json.dumps(config).encode()}
    url=f'http://127.0.0.1:{server.server_port}/'
    emit(dict(url=url, graph=str(graph_path.resolve()), host='127.0.0.1', port=server.server_port), human=f'Visualizador: {url}\nDados: {graph_path.resolve()}\nCtrl+C para encerrar.', status='ready')
    if not a.no_open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    emit(dict(url=url), human='Visualizador encerrado.', status='stopped')

if __name__ == '__main__': raise SystemExit(run(main))
