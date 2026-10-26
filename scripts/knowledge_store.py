"""Canonical Markdown knowledge store, validated JSON export and SQLite/FTS5 index."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

COLLECTIONS = {'entities': 'entity', 'relations': 'relation', 'sources': 'source', 'bibliography': 'bibliography'}
INDEX_VERSION = 'markdown-fts-v1'


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def yaml_module():
    try:
        import yaml
    except ImportError as exc:
        raise ValueError('Markdown requer PyYAML. Execute prepare_environment.py ou instale PyYAML no ambiente selecionado.') from exc
    return yaml


def yaml_load(text):
    yaml = yaml_module()
    class Loader(yaml.SafeLoader):
        pass
    Loader.yaml_implicit_resolvers = {key: [(tag, pattern) for tag, pattern in values if tag != 'tag:yaml.org,2002:timestamp'] for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()}
    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError(f'Chave YAML duplicada ou não textual: {key!r}')
            result[key] = loader.construct_object(value_node, deep=deep)
        return result
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        result = yaml.load(text, Loader=Loader)
        json.dumps(result, allow_nan=False)
        return result
    except (yaml.YAMLError, TypeError, ValueError) as exc:
        raise ValueError(f'YAML inválido: {exc}') from exc


def yaml_dump(value):
    return yaml_module().safe_dump(value, allow_unicode=True, sort_keys=False, width=1000)


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content.encode() if isinstance(content, str) else content)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists(): temporary.unlink()


def locate(path):
    path = Path(path).resolve()
    for candidate in (path, path / 'knowledge'):
        if (candidate / 'knowledge.yml').is_file():
            if (candidate / '.update-pending.json').exists():
                raise ValueError('Atualização Markdown interrompida. Execute knowledge.py recover antes de continuar.')
            return candidate
    raise ValueError(f'Base Markdown não encontrada em {path}; knowledge.yml é obrigatório.')


def generated(root):
    root = locate(root)
    return (root.parent if root.name == 'knowledge' else root) / '.generated'


def input_files(root):
    root = locate(root)
    if (root / 'knowledge.yml').is_symlink(): raise ValueError('knowledge.yml não pode ser symlink.')
    files = [root / 'knowledge.yml']
    for folder in COLLECTIONS:
        directory = root / folder
        if directory.is_symlink(): raise ValueError(f'Coleção não pode ser symlink: {directory}')
        if directory.exists():
            for file in sorted(directory.rglob('*.md')):
                if file.is_symlink() or not file.resolve().is_relative_to(root):
                    raise ValueError(f'Arquivo fora da base ou symlink: {file}')
                files.append(file)
    return files


def fingerprint(root):
    root = locate(root)
    return digest([(str(p.relative_to(root)), digest(p.read_bytes())) for p in input_files(root)])


@dataclass
class Record:
    path: str
    metadata: dict
    body: str
    file_hash: str

    @property
    def key(self): return self.metadata['kind'] + ':' + self.metadata['id']

    @property
    def semantic_text(self):
        m = self.metadata
        if m.get('semantic_description'):
            if not isinstance(m['semantic_description'], str): raise ValueError('semantic_description deve ser texto.')
            return m.get('label', '') + '\n' + m['semantic_description']
        return '\n'.join([m.get('label', ''), *sorted(m.get('aliases', [])), m.get('summary', ''), *([m['math']] if m.get('math') else []), self.body])

    @property
    def search_fields(self):
        m = self.metadata
        return (m.get('label', m.get('title', m['id'])), ' '.join(m.get('aliases', [])), m.get('summary', m.get('section', '')), self.body)


def parse_document(path, raw, root):
    text = raw.decode('utf-8-sig')
    match = re.fullmatch(r'---\r?\n(.*?)\r?\n---\r?\n(.*)', text, re.S)
    if not match: raise ValueError(f'{path}: frontmatter YAML delimitado por --- é obrigatório.')
    metadata = yaml_load(match[1])
    if not isinstance(metadata, dict): raise ValueError(f'{path}: metadados devem ser objeto.')
    return Record(str(path.relative_to(root)), metadata, match[2].strip(), digest(raw))


def read_store(path, cache=None):
    root = locate(path)
    config = yaml_load((root / 'knowledge.yml').read_text(encoding='utf-8'))
    if not isinstance(config, dict) or (type(config.get('schema_version')) is not int or config.get('schema_version') != 1):
        raise ValueError('knowledge.yml deve declarar schema_version: 1.')
    records, identities = [], set()
    for file in input_files(root)[1:]:
        relative = str(file.relative_to(root)); raw = file.read_bytes()
        old = (cache or {}).get(relative)
        record = Record(relative, old['metadata'], old['body'], old['file_hash']) if old and old['file_hash'] == digest(raw) else parse_document(file, raw, root)
        m = record.metadata
        expected = COLLECTIONS[Path(relative).parts[0]]
        if m.get('kind') != expected or not isinstance(m.get('id'), str) or not m['id'].strip():
            raise ValueError(f'{relative}: kind deve ser {expected}; id textual é obrigatório.')
        if record.key in identities: raise ValueError(f'Identidade duplicada: {record.key}')
        identities.add(record.key)
        aliases = m.get('aliases', [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases) or len(set(aliases)) != len(aliases):
            raise ValueError(f'{relative}: aliases devem ser strings únicas.')
        if expected == 'relation':
            if m.get('basis') not in ('explicit', 'inferred', 'unspecified'):
                raise ValueError(f'{relative}: basis deve ser explicit, inferred ou unspecified.')
            if m.get('basis') == 'inferred' and (not isinstance(m.get('rationale'), str) or not m['rationale'].strip()):
                raise ValueError(f'{relative}: inferência exige rationale.')
        if expected in ('source', 'bibliography') and str(m.get('path','')).startswith('evidence/'):
            relative_evidence = Path(m['path'])
            if '..' in relative_evidence.parts or relative_evidence.suffix.lower() != '.html':
                raise ValueError(f'{relative}: caminho de evidência inválido.')
        records.append(record)
    graph = export_graph(config, records)
    from graph_tools import validate
    errors = validate(graph)
    if errors: raise ValueError('\n'.join(errors))
    # Validate the richer canonical references, beyond the viewer contract.
    source_ids = set(graph['sources'])
    for record in records:
        evidence = record.metadata.get('evidence', [])
        if not isinstance(evidence, list): raise ValueError(f'{record.path}: evidence deve ser lista.')
        for item in evidence:
            if not isinstance(item, dict) or item.get('source') not in source_ids or (not isinstance(item.get('locator'), str) or not item['locator'].strip()) or (record.metadata['kind'] in ('entity','relation') and item.get('source') not in record.metadata.get('sources', [])):
                raise ValueError(f'{record.path}: evidence exige source existente e locator.')
    from evidence_passages import compile_evidence
    compile_evidence(records, '')  # Validate snapshots and bounds before mutating the index.
    return root, config, records, graph


def export_graph(config, records):
    graph = dict(config.get('graph_metadata', {}), schemaVersion=1, bookUrl=config.get('book_url', ''), bibliography={}, sources={}, nodes=[], edges=[])
    for record in sorted(records, key=lambda r: r.key):
        m = record.metadata; kind = m['kind']
        if kind == 'entity':
            item = {k: v for k, v in m.items() if k not in ('kind', 'entity_type', 'evidence')}
            item.update(type=m.get('entity_type'), detail=record.body)
            graph['nodes'].append(item)
        elif kind == 'relation':
            item = {k: v for k, v in m.items() if k not in ('kind', 'predicate', 'basis', 'rationale', 'evidence')}
            if record.body: item['summary'] = record.body
            graph['edges'].append(item)
        elif kind == 'source':
            item = {k: v for k, v in m.items() if k not in ('id', 'kind', 'source_kind', 'aliases', 'evidence')}
            if m.get('source_kind'): item['kind'] = m['source_kind']
            graph['sources'][m['id']] = item
        else:
            graph['bibliography'][m['id']] = {k: v for k, v in m.items() if k not in ('id', 'kind', 'aliases', 'evidence')}
    return graph


def graph_bytes(graph):
    return (json.dumps(graph, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def semantic_records(path):
    _, _, records, _ = read_store(path)
    return [dict(id=r.metadata['id'], text=r.semantic_text) for r in sorted(records, key=lambda r: r.key) if r.metadata['kind'] == 'entity']


def semantic_hash(records):
    return digest(sorted((r['id'], r['text']) for r in records))


def document_text(metadata, body):
    return '---\n' + yaml_dump(metadata) + '---\n\n' + (body.strip() + '\n' if body.strip() else '')


def filename(identifier):
    slug = re.sub(r'[^a-z0-9-]+', '-', identifier.lower()).strip('-')[:60] or 'record'
    return slug + '--' + hashlib.sha256(identifier.encode()).hexdigest()[:16] + '.md'


def import_graph(graph_path, destination):
    from graph_tools import load_graph
    graph, _ = load_graph(graph_path)
    destination = Path(destination).resolve()
    if destination.exists(): raise ValueError('Destino da migração já existe; use pasta nova.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        root = Path(tmp) / 'knowledge'; root.mkdir()
        config = dict(schema_version=1, book_url=graph['bookUrl'], graph_metadata={k: v for k, v in graph.items() if k not in ('schemaVersion', 'bookUrl', 'nodes', 'edges', 'sources', 'bibliography')})
        (root / 'knowledge.yml').write_text(yaml_dump(config), encoding='utf-8')
        for directory in COLLECTIONS: (root / directory).mkdir()
        for node in graph['nodes']:
            meta = dict(node); body = meta.pop('detail'); meta.update(kind='entity', entity_type=meta.pop('type'))
            (root / 'entities' / filename(meta['id'])).write_text(document_text(meta, body), encoding='utf-8')
        for edge in graph['edges']:
            meta = dict(edge); body = meta.pop('summary'); meta.update(kind='relation', basis=meta.pop('basis', 'unspecified'))
            (root / 'relations' / filename(meta['id'])).write_text(document_text(meta, body), encoding='utf-8')
        for collection, kind in [('sources', 'source'), ('bibliography', 'bibliography')]:
            for key, value in graph[collection].items():
                meta = dict(value)
                if collection == 'sources' and 'kind' in meta: meta['source_kind'] = meta.pop('kind')
                meta.update(id=key, kind=kind)
                (root / collection / filename(key)).write_text(document_text(meta, ''), encoding='utf-8')
        read_store(root)
        os.replace(root, destination)
    return destination


def update_wikipedia(path, enriched, expected_fingerprint=None):
    with write_lock(path):
        if expected_fingerprint is not None and fingerprint(path)!=expected_fingerprint: raise ValueError("A base mudou antes da escrita; refaça a revisão.")
        return _update_wikipedia(path,enriched)


def _update_wikipedia(path, enriched):
    """Write only wikipedia fields, with recovery journal for interrupted batches."""
    root, _, records, current = read_store(path)
    from graph_tools import validate
    errors = validate(enriched)
    if errors: raise ValueError('\n'.join(errors))
    if {n['id'] for n in current['nodes']} != {n['id'] for n in enriched['nodes']}:
        raise ValueError('Entidades divergentes; enriquecimento não pode mudar a base.')
    nodes = {n['id']: n for n in enriched['nodes']}
    updates = []
    for record in records:
        if record.metadata['kind'] != 'entity': continue
        metadata = dict(record.metadata); metadata.pop('wikipedia', None)
        if 'wikipedia' in nodes[metadata['id']]: metadata['wikipedia'] = nodes[metadata['id']]['wikipedia']
        if metadata == record.metadata: continue
        original = (root / record.path).read_text(encoding='utf-8')
        updates.append(dict(path=record.path, before=original, after=document_text(metadata, record.body)))
    if not updates: return 0
    journal = root / '.update-pending.json'
    atomic_write(journal, json.dumps(updates, ensure_ascii=False))
    try:
        for update in updates: atomic_write(root / update['path'], update['after'])
    except BaseException:
        for update in updates: atomic_write(root / update['path'], update['before'])
        journal.unlink()
        raise
    journal.unlink()
    return len(updates)


def recover(path):
    with write_lock(path): return _recover(path)


def _recover(path):
    path = Path(path).resolve()
    root = path if (path / 'knowledge.yml').exists() else path / 'knowledge'
    journal = root / '.update-pending.json'
    if not journal.is_file(): raise ValueError('Nenhuma atualização interrompida encontrada.')
    if journal.is_symlink(): raise ValueError('Journal não pode ser symlink.')
    updates = json.loads(journal.read_text())
    for update in updates:
        raw_target = root/update['path']
        target = raw_target.resolve()
        if not target.is_relative_to(root) or raw_target.is_symlink(): raise ValueError('Caminho inválido no journal.')
        if target.read_text(encoding='utf-8') not in (update['before'], update['after']):
            raise ValueError('Arquivo recebeu edição externa; restauração automática recusada.')
    for update in updates: atomic_write(root / update['path'], update['before'])
    journal.unlink()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(key TEXT PRIMARY KEY,kind TEXT NOT NULL,id TEXT NOT NULL,path TEXT NOT NULL UNIQUE,file_hash TEXT NOT NULL,metadata TEXT NOT NULL,body TEXT NOT NULL,search_hash TEXT NOT NULL,semantic_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS document_kind ON documents(kind,id);
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(key UNINDEXED,label,aliases,summary,body,tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY,document TEXT NOT NULL REFERENCES documents(key));
CREATE TABLE IF NOT EXISTS edges(id TEXT PRIMARY KEY,source TEXT NOT NULL REFERENCES nodes(id),target TEXT NOT NULL REFERENCES nodes(id),predicate TEXT,label TEXT NOT NULL,basis TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS edge_source ON edges(source);
CREATE INDEX IF NOT EXISTS edge_target ON edges(target);
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,document TEXT NOT NULL REFERENCES documents(key));
CREATE TABLE IF NOT EXISTS bibliography(id TEXT PRIMARY KEY,document TEXT NOT NULL REFERENCES documents(key));
CREATE TABLE IF NOT EXISTS source_refs(owner TEXT REFERENCES documents(key),source TEXT REFERENCES sources(id),PRIMARY KEY(owner,source));
CREATE INDEX IF NOT EXISTS source_ref_target ON source_refs(source);
CREATE TABLE IF NOT EXISTS citations(source TEXT REFERENCES sources(id),reference TEXT REFERENCES bibliography(id),PRIMARY KEY(source,reference));
'''


def connect(db):
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


@contextmanager
def write_lock(path):
    path=Path(path).resolve()
    root=path if (path/'knowledge.yml').is_file() else path/'knowledge'
    if not (root/'knowledge.yml').is_file(): raise ValueError('Base Markdown não encontrada.')
    lock=root/'.write-lock'
    try:
        fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        raise ValueError('Outra escrita está ativa ou foi interrompida (.write-lock). Aguarde; após falha, confirme que não há escritor antes de remover o lock.') from None
    try:
        with os.fdopen(fd,'w') as stream: json.dump(dict(pid=os.getpid()),stream)
        yield
    finally: lock.unlink(missing_ok=True)


def build(path):
    with write_lock(path): return _build(path)


def _build(path):
    root = locate(path); output = generated(root)
    if output.is_symlink(): raise ValueError('.generated não pode ser symlink.')
    output.mkdir(parents=True, exist_ok=True)
    database = output / 'index.sqlite'
    if database.is_symlink(): raise ValueError('index.sqlite não pode ser symlink.')
    connection = connect(database)
    try:
        connection.executescript(SCHEMA)
        old_version = connection.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        if old_version and old_version[0] != INDEX_VERSION: raise ValueError('Versão do índice incompatível. Remova apenas .generated/index.sqlite e reconstrua.')
        cached = {row['path']: dict(metadata=json.loads(row['metadata']), body=row['body'], file_hash=row['file_hash']) for row in connection.execute('SELECT * FROM documents')}
        initial_fingerprint = fingerprint(root)
        root, config, records, graph = read_store(root, cached)
        current_fingerprint = fingerprint(root)
        if current_fingerprint != initial_fingerprint: raise ValueError('A base mudou durante a leitura; execute build novamente.')
        prior = {row['key']: row for row in connection.execute('SELECT * FROM documents')}
        stats = dict(changed=0, unchanged=0, removed=len(set(prior) - {r.key for r in records}), ftsUpdated=0)
        with connection:
            # These small relational projections are regenerated transactionally;
            # documents and FTS rows are updated only when their hashes change.
            for table in ('citations', 'source_refs', 'edges', 'nodes', 'sources', 'bibliography'):
                connection.execute('DELETE FROM '+table)
            for key in set(prior) - {r.key for r in records}:
                connection.execute('DELETE FROM search WHERE key=?', (key,))
                connection.execute('DELETE FROM documents WHERE key=?', (key,))
            # A rename can swap paths; temporary unique values free old locations.
            for record in records:
                if record.key in prior and prior[record.key]['path'] != record.path:
                    connection.execute('UPDATE documents SET path=? WHERE key=?', ('__index_previous__/'+record.key, record.key))
            for record in records:
                old = prior.get(record.key); search_hash = digest(record.search_fields)
                semantic = digest(record.semantic_text) if record.metadata['kind'] == 'entity' else ''
                values = (record.key, record.metadata['kind'], record.metadata['id'], record.path, record.file_hash, json.dumps(record.metadata, ensure_ascii=False), record.body, search_hash, semantic)
                unchanged = old and old['file_hash'] == record.file_hash and old['path'] == record.path and old['search_hash'] == search_hash and old['semantic_hash'] == semantic
                if unchanged:
                    stats['unchanged'] += 1
                else:
                    connection.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET kind=excluded.kind,id=excluded.id,path=excluded.path,file_hash=excluded.file_hash,metadata=excluded.metadata,body=excluded.body,search_hash=excluded.search_hash,semantic_hash=excluded.semantic_hash', values)
                    stats['changed'] += 1
                if not old or old['search_hash'] != search_hash:
                    connection.execute('DELETE FROM search WHERE key=?', (record.key,))
                    connection.execute('INSERT INTO search VALUES(?,?,?,?,?)', (record.key, *record.search_fields))
                    stats['ftsUpdated'] += 1
            for record in records:
                m = record.metadata
                table = {'entity': 'nodes', 'source': 'sources', 'bibliography': 'bibliography'}.get(m['kind'])
                if table: connection.execute('INSERT INTO '+table+' VALUES(?,?)', (m['id'], record.key))
            for record in records:
                m = record.metadata
                if m['kind'] == 'relation':
                    connection.execute('INSERT INTO edges VALUES(?,?,?,?,?,?)', (m['id'], m['source'], m['target'], m.get('predicate'), m['label'], m['basis']))
                for source in set(m.get('sources', [])):
                    connection.execute('INSERT INTO source_refs VALUES(?,?)', (record.key, source))
                if m['kind'] == 'source':
                    for ref in set(m.get('citations', [])): connection.execute('INSERT INTO citations VALUES(?,?)', (m['id'], ref))
            for key, value in dict(version=INDEX_VERSION, fingerprint=current_fingerprint, root=str(root), config=json.dumps(config)).items():
                connection.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, value))
        raw = graph_bytes(graph)
        from graph_tools import layout_for, preferred_layout
        provenance = {r.key: dict(path=r.path, evidence=r.metadata.get('evidence', []), aliases=r.metadata.get('aliases', []), basis=r.metadata.get('basis'), rationale=r.metadata.get('rationale')) for r in records}
        outputs = {'graph.json': raw, 'layout.json': json.dumps(preferred_layout(root, graph, raw), ensure_ascii=False, indent=2)+'\n', 'provenance.json': json.dumps(provenance, ensure_ascii=False, indent=2)+'\n'}
        from evidence_passages import compile_evidence
        outputs['evidence/passages.json'] = json.dumps(compile_evidence(records, hashlib.sha256(raw).hexdigest()), ensure_ascii=False, indent=2)+'\n'
        # Local source pages are rebuilt from canonical source documents.
        pages = {}
        for record in records:
            if record.metadata['kind'] not in ('source', 'bibliography'): continue
            m = record.metadata; destination = m.get('path', '')
            if not destination.startswith('evidence/'): continue
            destination = str(Path(destination))
            target = (output / destination).resolve()
            if not target.is_relative_to(output.resolve()) or target.suffix.lower() != '.html':
                raise ValueError('Caminho de evidência local inválido.')
            title = m.get('section', m.get('label', m['id']))
            body = record.body or 'O texto original não foi incorporado. Consulte o localizador indicado.'
            section = '<section id="'+html.escape(m.get('anchor',''), quote=True)+'"><h2>'+html.escape(title)+'</h2><pre style="white-space:pre-wrap">'+html.escape(body)+'</pre><p>'+html.escape(m.get('sourceFile', ''))+'</p></section>'
            pages.setdefault(destination, []).append(section)
        for name, sections in pages.items():
            outputs[name] = '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Fontes do grafo</title><main>'+''.join(sections)+'</main></html>\n'
        from agent_index import navigation_outputs
        outputs.update(navigation_outputs(root, records, output, COLLECTIONS))
        previous_manifest = output / 'manifest.json'
        old_files = json.loads(previous_manifest.read_text()).get('files', []) if previous_manifest.exists() else []
        for name in old_files:
            target = output/name
            if name not in outputs and str(name).startswith(('evidence/','index/')) and target.resolve().is_relative_to(output.resolve()) and target.is_file(): target.unlink()
        for name, content in outputs.items():
            file = output / name
            if not file.resolve().is_relative_to(output.resolve()): raise ValueError('Artefato gerado fora de .generated; symlink recusado.')
            content = content.encode() if isinstance(content, str) else content
            if not file.exists() or file.read_bytes() != content: atomic_write(file, content)
        atomic_write(output / 'manifest.json', json.dumps(dict(version=INDEX_VERSION, fingerprint=current_fingerprint, graphSha256=digest(raw), files=sorted(outputs)), indent=2)+'\n')
        return dict(root=str(root), generated=str(output), **stats)
    finally:
        connection.close()


def require_fresh(path):
    root = locate(path); database = generated(root) / 'index.sqlite'
    if not database.exists(): raise ValueError('Índice ausente. Execute knowledge.py build.')
    connection = connect(database)
    metadata = dict(connection.execute('SELECT key,value FROM meta').fetchall())
    if metadata.get('version') != INDEX_VERSION or metadata.get('fingerprint') != fingerprint(root):
        connection.close(); raise ValueError('Índice desatualizado. Execute knowledge.py build.')
    return connection


def search(path, query, kind=None, limit=20):
    if not 1 <= limit <= 100: raise ValueError('limit deve estar entre 1 e 100.')
    tokens = re.findall(r'\w+', query, re.UNICODE)
    if not tokens: return []
    expression = ' AND '.join('"'+t+'"' for t in tokens)
    connection = require_fresh(path)
    try:
        sql = '''SELECT d.id,d.kind,d.path,s.label,bm25(search,0,10,7,3,1) AS rank,
        snippet(search,4,'[',']',' … ',24) AS snippet FROM search s JOIN documents d ON d.key=s.key
        WHERE search MATCH ?'''
        params = [expression]
        if kind: sql += ' AND d.kind=?'; params.append(kind)
        sql += ' ORDER BY rank,d.key LIMIT ?'; params.append(limit)
        return [dict(row) for row in connection.execute(sql, params)]
    finally: connection.close()


def neighbors(path, identifier, depth=1, direction='both'):
    if not 1 <= depth <= 10 or direction not in ('both','in','out'): raise ValueError('Profundidade 1..10; direção both/in/out.')
    connection = require_fresh(path)
    try:
        if not connection.execute('SELECT 1 FROM nodes WHERE id=?', (identifier,)).fetchone(): raise ValueError('Entidade inexistente.')
        condition = {'out':'e.source=w.id','in':'e.target=w.id','both':'e.source=w.id OR e.target=w.id'}[direction]
        endpoint = 'e.target' if direction == 'out' else 'e.source' if direction == 'in' else 'CASE WHEN e.source=w.id THEN e.target ELSE e.source END'
        sql = f'''WITH RECURSIVE walk(id,depth) AS (SELECT ?,0 UNION SELECT {endpoint},w.depth+1 FROM edges e JOIN walk w ON {condition} WHERE w.depth<?)
        SELECT id,min(depth) AS distance FROM walk WHERE id<>? GROUP BY id ORDER BY distance,id'''
        return [dict(row) for row in connection.execute(sql, (identifier,depth,identifier))]
    finally: connection.close()
