"""Local embeddings with semantic hashes and reusable per-entity vectors."""
from cli_common import Parser, emit, run
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import os

from graph_tools import load_graph, entity_records, semantic_input_hash

MANAGED = 'content-to-knowledge-graph/embeddings-v2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def resolve_revision(model, name, revision, cache):
    config = getattr(getattr(model[0], 'auto_model', None), 'config', None)
    resolved = getattr(config, '_commit_hash', None)
    if not resolved:
        from huggingface_hub import try_to_load_from_cache
        cached = try_to_load_from_cache(name, 'config.json', revision=revision or 'main', cache_dir=str(cache) if cache else None)
        if isinstance(cached, str) and 'snapshots' in Path(cached).parts:
            parts = Path(cached).parts; resolved = parts[parts.index('snapshots') + 1]
    if not resolved and Path(name).is_dir():
        resolved = 'local-sha256:' + sha(''.join(str(f.relative_to(name)) + sha(f.read_bytes()) for f in sorted(Path(name).rglob('*')) if f.is_file()).encode())
    if not resolved: raise ValueError('Não foi possível identificar a revisão resolvida do modelo.')
    return resolved


def chunks_for(model, record, overlap):
    tokenizer = model.tokenizer
    limit = model.max_seq_length - tokenizer.num_special_tokens_to_add(pair=False)
    if limit < 1 or overlap >= limit: raise ValueError('Limite de tokens incompatível com overlap.')
    text = record['text']
    if not isinstance(text, str) or not text.strip(): raise ValueError(f"Texto vazio: {record['id']}")
    tokens = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False, verbose=False)
    offsets = tokens['offset_mapping']; token_ids = tokens['input_ids']; start = 0
    chunks, mapping = [], []
    while start < len(token_ids):
        end = min(start + limit, len(token_ids)); char_start = offsets[start][0]; char_end = offsets[end-1][1]
        chunk = text[char_start:char_end]
        while len(tokenizer.encode(chunk, add_special_tokens=True)) > model.max_seq_length and end > start + 1:
            end -= 1; char_end = offsets[end-1][1]; chunk = text[char_start:char_end]
        if chunk.strip():
            if len(tokenizer.encode(chunk, add_special_tokens=True)) > model.max_seq_length: raise ValueError('Token excede o limite do modelo.')
            chunks.append(chunk)
            mapping.append(dict(id=f"{record['id']}::chunk-{len(chunks)}", parentId=record['id'], charStart=char_start, charEnd=char_end, textSha256=sha(chunk.encode()), sourceFile=record.get('sourceFile'), locator=record.get('locator')))
        if end == len(token_ids): break
        start = max(start + 1, end-overlap)
    if not chunks: raise ValueError(f"Tokenização vazia: {record['id']}")
    return chunks, mapping


def load_cache(output, signature, np):
    manifest_path = output / 'manifest.json'
    if not manifest_path.exists(): return {}, {}, []
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('managedBy') != MANAGED: raise ValueError('Saída existente não é um cache gerenciado v2. Use pasta nova.')
    if manifest.get('cacheSignature') != signature or manifest.get('kind') != 'entities': return {}, {}, []
    try:
        matrix_file = output/'entities.npy'; ids_file = output/'entities.ids.json'
        if sha(matrix_file.read_bytes()) != manifest['matrixSha256'] or sha(ids_file.read_bytes()) != manifest['idsSha256']:
            return {}, {}, []
        matrix = np.load(matrix_file, allow_pickle=False); ids = json.loads(ids_file.read_text())
        if matrix.ndim != 2 or len(matrix) != len(ids) or len(set(ids)) != len(ids) or matrix.shape[1] != manifest['dimension'] or not np.isfinite(matrix).all(): return {}, {}, []
        if not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-4): return {}, {}, []
        mapping = json.loads((output/'chunks.mapping.json').read_text())
        return dict(zip(ids, matrix)), manifest['textHashes'], mapping
    except (OSError, ValueError, KeyError):
        return {}, {}, []


def embed_entities(model, records, output, signature, batch_size, overlap, np):
    vectors, old_hashes, old_mapping = load_cache(output, signature, np)
    hashes = {r['id']: sha(r['text'].encode()) for r in records}
    reused = {r['id'] for r in records if r['id'] in vectors and old_hashes.get(r['id']) == hashes[r['id']]}
    all_chunks, mapping, groups = [], [m for m in old_mapping if m['parentId'] in reused], {}
    for record in records:
        if record['id'] in reused: continue
        chunks, locators = chunks_for(model, record, overlap)
        groups[record['id']] = list(range(len(all_chunks), len(all_chunks)+len(chunks)))
        all_chunks.extend(chunks); mapping.extend(locators)
    if all_chunks:
        encoded = model.encode(all_chunks, batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True, prompt="")
        for identifier, indices in groups.items():
            vector = encoded[indices].mean(axis=0); norm = np.linalg.norm(vector)
            if not np.isfinite(norm) or norm == 0: raise ValueError('Vetor agregado inválido.')
            vectors[identifier] = vector / norm
    ids = [r['id'] for r in records]
    matrix = np.stack([vectors[identifier] for identifier in ids])
    return matrix, ids, mapping, hashes, dict(reused=len(reused), computed=len(records)-len(reused))


def main():
    parser = Parser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--graph', type=Path, help='Base Markdown ou graph.json legado'); source.add_argument('--units', type=Path)
    parser.add_argument('--model', required=True); parser.add_argument('--revision')
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--device', default='cpu'); parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--cache-dir', type=Path); parser.add_argument('--overlap-tokens', type=int, default=32)
    args = parser.parse_args()
    if args.batch_size < 1 or args.overlap_tokens < 0: parser.error('batch-size deve ser positivo e overlap não negativo.')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()) and not (output/'manifest.json').exists(): parser.error('Pasta de saída não é cache gerenciado. Use pasta nova.')
    if (output/'manifest.json').exists() and json.loads((output/'manifest.json').read_text()).get('managedBy') != MANAGED: parser.error('Pasta existente não é gerenciada por embeddings-v2; use pasta nova.')
    if (output/'manifest.json').exists() and json.loads((output/'manifest.json').read_text()).get('kind') != ('entities' if args.graph else 'chunks'): parser.error('Não misture chunks e entidades na mesma pasta.')
    import numpy as np
    from sentence_transformers import SentenceTransformer
    if args.graph:
        graph, raw = load_graph(args.graph); records = entity_records(args.graph, graph); kind = 'entities'
    else:
        raw = args.units.read_bytes(); records = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]; kind = 'chunks'
    if not records or len({r['id'] for r in records}) != len(records): parser.error('Textos ausentes ou IDs duplicados.')
    model = SentenceTransformer(args.model, revision=args.revision, device=args.device, cache_folder=str(args.cache_dir) if args.cache_dir else None, local_files_only=args.local_only, trust_remote_code=False)
    revision = resolve_revision(model, args.model, args.revision, args.cache_dir)
    versions = {name: importlib.metadata.version(name) for name in ('sentence-transformers','torch','numpy')}
    parameters = dict(model=args.model, revision=revision, versions=versions, device=args.device, maxSequenceLength=model.max_seq_length, overlapTokens=args.overlap_tokens, normalized=True, dtype='float32', prefix='', kind=kind, aggregation='mean-of-normalized-chunks-renormalized' if kind=='entities' else None)
    signature = sha(json.dumps(parameters, sort_keys=True).encode())
    if kind == 'entities':
        matrix, ids, mapping, text_hashes, stats = embed_entities(model, records, output, signature, args.batch_size, args.overlap_tokens, np)
    else:
        texts, mapping = [], []
        for record in records:
            chunks, locators = chunks_for(model, record, args.overlap_tokens); texts.extend(chunks); mapping.extend(locators)
        matrix = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True, prompt="")
        ids = [m['id'] for m in mapping]; text_hashes = {r['id']:sha(r['text'].encode()) for r in records}; stats = dict(reused=0, computed=len(ids))
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim != 2 or len(matrix) != len(ids) or not np.isfinite(matrix).all() or not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-4): raise ValueError('Matriz de embeddings inválida.')
    manifest = dict(parameters, managedBy=MANAGED, cacheSignature=signature, requestedRevision=args.revision, resolvedRevision=revision, dimension=int(matrix.shape[1]), rows=len(ids), inputSha256=sha(raw), semanticInputSha256=semantic_input_hash(records), generatedAt=datetime.now(timezone.utc).isoformat(), textHashes=text_hashes, stats=stats)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        tmp = Path(temporary)
        np.save(tmp/f'{kind}.npy', matrix, allow_pickle=False)
        (tmp/f'{kind}.ids.json').write_text(json.dumps(ids, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        (tmp/'chunks.mapping.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        manifest.update(matrixSha256=sha((tmp/f'{kind}.npy').read_bytes()), idsSha256=sha((tmp/f'{kind}.ids.json').read_bytes()))
        output.mkdir(parents=True, exist_ok=True)
        for file in tmp.iterdir(): os.replace(file, output/file.name)
        from knowledge_store import atomic_write
        atomic_write(output/'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    emit(dict(output=str(output), rows=len(ids), dimension=int(matrix.shape[1]), **stats))

if __name__ == '__main__': raise SystemExit(run(main))
