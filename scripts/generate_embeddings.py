"""Generate local sentence embeddings for graph entities or extracted text units."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True); source.add_argument('--graph',type=Path); source.add_argument('--units',type=Path)
    p.add_argument('--model', required=True); p.add_argument('--revision',help='Prefer a pinned model commit')
    p.add_argument('--output',type=Path,required=True); p.add_argument('--batch-size',type=int,default=16)
    p.add_argument('--device',default='cpu'); p.add_argument('--local-only',action='store_true')
    p.add_argument('--cache-dir',type=Path); p.add_argument('--overlap-tokens',type=int,default=32)
    a=p.parse_args()
    if a.batch_size<1 or a.overlap_tokens<0: p.error('batch-size deve ser positivo e overlap não negativo.')
    out=a.output.resolve()
    if out.exists() and any(out.iterdir()): p.error('Use uma pasta nova/vazia para não misturar modelos ou resultados.')
    import numpy as np
    from sentence_transformers import SentenceTransformer
    if a.graph:
        from graph_tools import load_graph
        graph,raw=load_graph(a.graph)
        records=[dict(id=n['id'],text='\n'.join([n['label'],n['summary'],n['detail']])) for n in graph['nodes']]
        kind='entities'
    else:
        raw=a.units.read_bytes(); records=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]; kind='chunks'
    if not records: p.error('Nenhum texto para gerar embeddings.')
    if len({r['id'] for r in records})!=len(records): p.error('IDs de entrada duplicados.')
    model=SentenceTransformer(a.model,revision=a.revision,device=a.device,cache_folder=str(a.cache_dir) if a.cache_dir else None,local_files_only=a.local_only,trust_remote_code=False)
    tokenizer=model.tokenizer
    limit=model.max_seq_length-tokenizer.num_special_tokens_to_add(pair=False)
    if limit<1 or a.overlap_tokens>=limit: p.error('Limite de tokens incompatível com overlap.')
    texts=[]; mapping=[]; groups=[]
    for record in records:
        text=record['text']
        if not isinstance(text,str) or not text.strip(): p.error(f"Texto vazio: {record['id']}")
        # Offset mappings retain the exact character locations in the original text.
        tokens=tokenizer(text,add_special_tokens=False,return_offsets_mapping=True,truncation=False,verbose=False)
        offsets=tokens['offset_mapping']; token_ids=tokens['input_ids']; indices=[]
        start=0
        while start<len(token_ids):
            end=min(start+limit,len(token_ids)); char_start=offsets[start][0]; char_end=offsets[end-1][1]
            chunk=text[char_start:char_end]
            # Re-tokenization of a substring may change boundary tokens: shrink to fit.
            while len(tokenizer.encode(chunk,add_special_tokens=True))>model.max_seq_length and end>start+1:
                end-=1; char_end=offsets[end-1][1]; chunk=text[char_start:char_end]
            if not chunk.strip():
                start=end; continue
            if len(tokenizer.encode(chunk,add_special_tokens=True))>model.max_seq_length: raise ValueError('Token isolado excede limite do modelo.')
            indices.append(len(texts)); texts.append(chunk)
            mapping.append(dict(id=f"{record['id']}::chunk-{len(indices)}",parentId=record['id'],charStart=char_start,charEnd=char_end,textSha256=hashlib.sha256(chunk.encode()).hexdigest(),sourceFile=record.get('sourceFile'),locator=record.get('locator')))
            if end==len(token_ids): break
            start=max(start+1,end-a.overlap_tokens)
        groups.append(indices)
    matrix=model.encode(texts,batch_size=a.batch_size,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=True)
    if kind=='entities':
        matrix=np.stack([matrix[g].mean(axis=0) for g in groups])
        norms=np.linalg.norm(matrix,axis=1,keepdims=True)
        if np.any(norms==0): raise ValueError('Vetor agregado nulo.')
        matrix=matrix/norms; ids=[r['id'] for r in records]
    else: ids=[m['id'] for m in mapping]
    matrix=np.asarray(matrix,dtype=np.float32)
    if matrix.ndim!=2 or len(matrix)!=len(ids) or not np.isfinite(matrix).all(): raise ValueError('Matriz de embeddings inválida.')
    if not np.allclose(np.linalg.norm(matrix,axis=1),1,atol=1e-4): raise ValueError('Normas inválidas.')
    resolved=getattr(getattr(model[0],'auto_model',None),'config',None)
    resolved=getattr(resolved,'_commit_hash',None)
    if resolved is None:
        from huggingface_hub import try_to_load_from_cache
        cached=try_to_load_from_cache(a.model,'config.json',revision=a.revision or 'main',cache_dir=str(a.cache_dir) if a.cache_dir else None)
        if isinstance(cached,str) and 'snapshots' in Path(cached).parts:
            parts=Path(cached).parts; resolved=parts[parts.index('snapshots')+1]
    if resolved is None and Path(a.model).is_dir():
        # Local models have no remote revision; record file hashes instead.
        resolved='local-sha256:'+hashlib.sha256(''.join(str(f.relative_to(a.model))+hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(Path(a.model).rglob('*')) if f.is_file()).encode()).hexdigest()
    if resolved is None: raise ValueError('Não foi possível identificar a revisão resolvida do modelo.')
    manifest=dict(model=a.model,requestedRevision=a.revision,resolvedRevision=resolved,device=a.device,kind=kind,dimension=int(matrix.shape[1]),rows=len(ids),dtype='float32',normalized=True,aggregation='mean-of-normalized-chunks-renormalized' if kind=='entities' else None,maxSequenceLength=model.max_seq_length,overlapTokens=a.overlap_tokens,prefix=None,inputSha256=hashlib.sha256(raw).hexdigest(),generatedAt=datetime.now(timezone.utc).isoformat(),versions={n:importlib.metadata.version(n) for n in ['sentence-transformers','torch','numpy']},textHashes={r['id']:hashlib.sha256(r['text'].encode()).hexdigest() for r in records})
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        tmp=Path(temp)
        np.save(tmp/f'{kind}.npy',matrix,allow_pickle=False)
        (tmp/f'{kind}.ids.json').write_text(json.dumps(ids,ensure_ascii=False,indent=2)+'\n')
        (tmp/'chunks.mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
        (tmp/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        out.mkdir(parents=True,exist_ok=True)
        for file in tmp.iterdir(): os.replace(file,out/file.name)
    print(f'{len(ids)} vetores reais de dimensão {matrix.shape[1]} em {out}')

if __name__=='__main__': main()
