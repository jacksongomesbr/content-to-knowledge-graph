"""Serve the bundled browser viewer with a graph; Markdown requires PyYAML; legacy JSON uses the standard library."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit
import webbrowser
from graph_tools import load_graph, layout_for, check_layout


class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.respond(False)
    def do_HEAD(self): self.respond(True)
    def respond(self, head):
        path=unquote(urlsplit(self.path).path)
        try:
            if path in self.server.payloads:
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
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path,help='base Markdown, graph.json ou diretório que o contém')
    p.add_argument('--layout',type=Path); p.add_argument('--config',type=Path,help='JSON com title, subtitle, types e themes opcionais')
    p.add_argument('--port',type=int,default=0,help='0 escolhe uma porta livre'); p.add_argument('--no-open',action='store_true')
    p.add_argument('--title',default='Grafo de conhecimento'); p.add_argument('--export-layout',type=Path)
    a=p.parse_args()
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
        else: layout=layout_for(graph,raw)
        config=dict(title=a.title,subtitle=f"{len(graph['nodes'])} entidades · {len(graph['edges'])} relações")
        if a.config: config.update(json.loads(a.config.read_text()))
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
    try: server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    except OSError as exc: p.exit(1,f'Não foi possível iniciar servidor: {exc}\n')
    server.assets=assets; server.graph_dir=graph_path.resolve().parent
    server.payloads={'/graph.json':raw,'/layout.json':json.dumps(layout).encode(),'/viewer-config.json':json.dumps(config).encode()}
    url=f'http://127.0.0.1:{server.server_port}/'
    print(f'Visualizador: {url}\nDados: {graph_path.resolve()}\nCtrl+C para encerrar.',flush=True)
    if not a.no_open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
