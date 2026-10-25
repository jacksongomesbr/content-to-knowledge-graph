"""Local lexical, semantic or hybrid retrieval from the Markdown knowledge index."""
import argparse
import hashlib
import json
from pathlib import Path

from graph_tools import entity_records, semantic_input_hash
from knowledge_store import generated, require_fresh, search


def retrieve(root, query, mode='lexical', limit=10, embeddings=None, cache_dir=None, allow_download=False):
    if not 1 <= limit <= 100: raise ValueError('limit deve estar entre 1 e 100.')
    if not query.strip(): return []
    lexical = search(root, query, 'entity', 100) if mode in ('lexical','hybrid') else []
    if mode == 'lexical': return lexical[:limit]
    if mode not in ('semantic','hybrid'): raise ValueError('Modo desconhecido.')
    connection = require_fresh(root)
    try:
        documents = {row['id']:dict(metadata=json.loads(row['metadata']),path=row['path']) for row in connection.execute("SELECT * FROM documents WHERE kind='entity'")}
    finally: connection.close()
    folder = Path(embeddings) if embeddings else generated(root)/'embeddings'
    manifest = json.loads((folder/'manifest.json').read_text())
    if manifest.get('kind') != 'entities' or manifest.get('semanticInputSha256') != semantic_input_hash(entity_records(root)):
        raise ValueError('Embeddings ausentes/desatualizados. Execute generate_embeddings.py para a base atual.')
    import numpy as np
    from sentence_transformers import SentenceTransformer
    ids_file=folder/'entities.ids.json'; matrix_file=folder/'entities.npy'
    if hashlib.sha256(ids_file.read_bytes()).hexdigest()!=manifest.get('idsSha256') or hashlib.sha256(matrix_file.read_bytes()).hexdigest()!=manifest.get('matrixSha256'):
        raise ValueError('Integridade dos embeddings inválida.')
    ids = json.loads(ids_file.read_text()); matrix=np.load(matrix_file, allow_pickle=False)
    if matrix.ndim!=2 or matrix.shape!=(len(ids),manifest['dimension']) or len(set(ids))!=len(ids) or set(ids)!=set(documents) or not np.isfinite(matrix).all() or not np.allclose(np.linalg.norm(matrix,axis=1),1,atol=1e-4):
        raise ValueError('Matriz inválida ou desalinhada.')
    revision = manifest['resolvedRevision']; local = revision.startswith('local-sha256:')
    model = SentenceTransformer(manifest['model'], revision=None if local else revision, device='cpu', cache_folder=str(cache_dir) if cache_dir else None, local_files_only=not allow_download, trust_remote_code=False)
    from generate_embeddings import resolve_revision
    if resolve_revision(model,manifest['model'],None if local else revision,cache_dir)!=revision:
        raise ValueError('O modelo local difere da revisão usada nos vetores.')
    if len(model.tokenizer.encode(query,add_special_tokens=True))>model.max_seq_length:
        raise ValueError('Consulta excede o limite de tokens do modelo; reduza o texto.')
    vector = model.encode([query], normalize_embeddings=True, convert_to_numpy=True, prompt="")[0]
    scores = matrix @ vector
    semantic = [dict(id=ids[i], cosine=float(scores[i])) for i in np.argsort(-scores,kind='stable')[:100]]
    lexical_ranks = {item['id']:rank for rank,item in enumerate(lexical,1)}
    semantic_ranks = {item['id']:rank for rank,item in enumerate(semantic,1)}
    cosine = {item['id']:item['cosine'] for item in semantic}
    identifiers = set(semantic_ranks) | set(lexical_ranks)
    results=[]
    for identifier in identifiers:
        score = cosine.get(identifier,-1) if mode=='semantic' else (1/(60+lexical_ranks[identifier]) if identifier in lexical_ranks else 0)+(1/(60+semantic_ranks[identifier]) if identifier in semantic_ranks else 0)
        doc=documents[identifier]
        results.append(dict(id=identifier,label=doc['metadata']['label'],path=doc['path'],score=score,cosine=cosine.get(identifier),lexicalRank=lexical_ranks.get(identifier),semanticRank=semantic_ranks.get(identifier)))
    return sorted(results,key=lambda item:(-item['score'],item['id']))[:limit]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('query');parser.add_argument('--mode',choices=['lexical','semantic','hybrid'],default='lexical')
    parser.add_argument('--limit',type=int,default=10);parser.add_argument('--embeddings',type=Path);parser.add_argument('--cache-dir',type=Path);parser.add_argument('--allow-download',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(retrieve(args.root,args.query,args.mode,args.limit,args.embeddings,args.cache_dir,args.allow_download),ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,ImportError) as exc: parser.exit(1,f'Busca: {exc}\n')

if __name__=='__main__':main()
