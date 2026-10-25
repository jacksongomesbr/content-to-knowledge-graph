"""Shared graph validation and deterministic editorial layout; stdlib only."""
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


def validate(graph):
    errors = []
    if not isinstance(graph, dict):
        return ['A raiz deve ser objeto.']
    if graph.get('schemaVersion') != 1:
        errors.append('schemaVersion deve ser 1.')
    if urlparse(str(graph.get('bookUrl', ''))).scheme not in ('http', 'https') or not urlparse(str(graph.get('bookUrl', ''))).netloc:
        errors.append('bookUrl deve ser URL HTTP(S) absoluta.')
    for key, cls in [('sources', dict), ('bibliography', dict), ('nodes', list), ('edges', list)]:
        if not isinstance(graph.get(key), cls):
            errors.append(f'{key}: formato inválido.')
    if errors:
        return errors
    sources, bibliography = graph['sources'], graph['bibliography']
    def strings(item, fields, where, nonempty=True):
        for key in fields:
            if not isinstance(item.get(key), str) or (nonempty and not item[key].strip()):
                errors.append(f'{where}.{key}: string inválida.')
    def refs(value, available, where, nonempty=False):
        if not isinstance(value, list) or (nonempty and not value):
            errors.append(f'{where}: lista inválida.'); return
        for key in value:
            if not isinstance(key, str) or key not in available:
                errors.append(f'{where}: referência desconhecida {key!r}.')
    for key, source in sources.items():
        if not isinstance(source, dict):
            errors.append(f'Fonte {key} inválida.'); continue
        strings(source, ['path', 'sourceFile', 'section'], key)
        strings(source, ['anchor'], key, False)
        if not isinstance(source.get('chapter'), (int, float)) or isinstance(source.get('chapter'), bool) or not math.isfinite(source['chapter']):
            errors.append(f'{key}.chapter inválido.')
        if 'kind' in source and source['kind'] not in ('book', 'bibliography'):
            errors.append(f'{key}.kind inválido.')
        refs(source.get('citations'), bibliography, f'{key}.citations')
        if urlparse(str(source.get('path', ''))).scheme not in ('', 'http', 'https'):
            errors.append(f'{key}.path: protocolo proibido.')
    for key, ref in bibliography.items():
        if not isinstance(ref, dict):
            errors.append(f'Bibliografia {key} inválida.'); continue
        strings(ref, ['label', 'path'], key); strings(ref, ['anchor'], key, False)
        if urlparse(ref.get('path', '')).scheme not in ('', 'http', 'https'):
            errors.append(f'{key}.path: protocolo proibido.')
    ids = set()
    node_ids = {n.get('id') for n in graph['nodes'] if isinstance(n, dict) and isinstance(n.get('id'), str)}
    for kind, items in [('node', graph['nodes']), ('edge', graph['edges'])]:
        for item in items:
            if not isinstance(item, dict):
                errors.append(f'{kind}: objeto inválido.'); continue
            strings(item, ['id', 'label', 'summary'] + (['type', 'theme', 'detail'] if kind == 'node' else ['source', 'target']), kind)
            key = item.get('id')
            if isinstance(key, str):
                if key in ids: errors.append(f'ID repetido: {key}')
                ids.add(key)
            refs(item.get('sources'), sources, f'{key}.sources', True)
            if kind == 'edge' and any(not isinstance(item.get(k), str) or item[k] not in node_ids for k in ('source', 'target')):
                errors.append(f'Extremidade inválida: {key}')
            if kind == 'node':
                for field in ('type', 'theme'):
                    if not isinstance(item.get(field), str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', item[field]): errors.append(f'{key}.{field}: use slug em minúsculas.')
            wiki = item.get('wikipedia')
            if wiki:
                if not isinstance(wiki, dict):
                    errors.append(f'Wikipédia inválida: {key}'); continue
                u = urlparse(str(wiki.get('url', '')))
                if wiki.get('language') not in ('pt', 'en') or u.scheme != 'https' or u.netloc != f"{wiki.get('language')}.wikipedia.org" or not u.path.startswith('/wiki/'):
                    errors.append(f'Wikipédia inválida: {key}')
                strings(wiki, ['title', 'verifiedAt'], f'{key}.wikipedia')
                try: date.fromisoformat(wiki.get('verifiedAt',''))
                except (ValueError,TypeError): errors.append(f'Data Wikipédia inválida: {key}')
    return errors


def load_graph(path):
    raw = Path(path).read_bytes()
    graph = json.loads(raw)
    errors = validate(graph)
    if errors:
        raise ValueError('\n'.join(errors))
    return graph, raw


def layout_for(graph, raw):
    themes = sorted({n['theme'] for n in graph['nodes']})
    positions = {}
    for t, theme in enumerate(themes):
        angle = t * 2 * math.pi / len(themes)
        center = (260 * math.cos(angle), 260 * math.sin(angle), 80 * (t % 3 - 1))
        for i, node in enumerate(sorted((n for n in graph['nodes'] if n['theme'] == theme), key=lambda n: n['id'])):
            a = i * math.pi * (3 - math.sqrt(5)); r = 30 + 12 * math.sqrt(i)
            positions[node['id']] = dict(x=center[0] + math.cos(a)*r, y=center[1] + math.sin(a)*r, z=center[2] + (i % 5 - 2)*24)
    return dict(method='editorial-topics-generic-v1', graphSha256=hashlib.sha256(raw).hexdigest(), positions=positions)


def check_layout(layout, graph, raw):
    if layout.get('graphSha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('Hash do layout difere do graph.json.')
    positions = layout.get('positions', {})
    if set(positions) != {n['id'] for n in graph['nodes']}:
        raise ValueError('IDs de posições diferem dos nós.')
    if any(not isinstance(p, dict) or any(not isinstance(p.get(k), (int, float)) or isinstance(p.get(k), bool) or not math.isfinite(p[k]) for k in ('x','y','z')) for p in positions.values()):
        raise ValueError('Coordenadas inválidas.')
