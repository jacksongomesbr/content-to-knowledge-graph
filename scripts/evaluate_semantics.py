"""Score frozen domain comparisons without changing texts or embeddings."""
import hashlib
import json
import math
from pathlib import Path
from cli_common import Parser, emit, run
from graph_tools import entity_records, semantic_input_hash


def wilson(correct, total):
    z=1.96; p=correct/total; d=1+z*z/total
    center=(p+z*z/(2*total))/d
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [center-radius,center+radius]


def evaluate(graph, directory, benchmark):
    import numpy as np
    directory=Path(directory); manifest=json.loads((directory/'manifest.json').read_text())
    for filename,key in [('entities.npy','matrixSha256'),('entities.ids.json','idsSha256')]:
        if hashlib.sha256((directory/filename).read_bytes()).hexdigest()!=manifest[key]: raise ValueError('Hash dos vetores/IDs inválido.')
    if manifest.get('semanticInputSha256')!=semantic_input_hash(entity_records(graph)): raise ValueError('Embeddings desatualizados.')
    ids=json.loads((directory/'entities.ids.json').read_text()); x=np.load(directory/'entities.npy',allow_pickle=False)
    if manifest.get('kind')!='entities' or x.ndim!=2 or len(x)!=len(ids) or len(set(ids))!=len(ids) or not np.isfinite(x).all() or not np.allclose(np.linalg.norm(x,axis=1),1,atol=1e-4): raise ValueError('Matriz inválida.')
    if set(ids)!={r['id'] for r in entity_records(graph)}: raise ValueError('IDs não correspondem à base.')
    index={key:i for i,key in enumerate(ids)}; rows=[]; seen=set()
    for item in benchmark['comparisons']:
        triple=tuple(item[k] for k in ('anchor','closer','farther'))
        if len(set(triple))!=3 or triple in seen: raise ValueError('Comparação repetida ou degenerada.')
        seen.add(triple)
        a,b,c=[index[i] for i in triple]; close=float(x[a]@x[b]); far=float(x[a]@x[c])
        rows.append(dict(item,closerCosine=close,fartherCosine=far,margin=close-far,correct=close>far))
    if not rows: raise ValueError('Amostra vazia.')
    correct=sum(r['correct'] for r in rows)
    return dict(model=manifest['model'],revision=manifest['resolvedRevision'],prefix=manifest.get('prefix',''),matrixSha256=manifest['matrixSha256'],semanticInputSha256=manifest['semanticInputSha256'],correct=correct,total=len(rows),accuracy=correct/len(rows),wilson95=wilson(correct,len(rows)),comparisons=rows)


def main():
    p=Parser(description=__doc__);p.add_argument('--graph',type=Path,required=True);p.add_argument('--embeddings',type=Path,required=True);p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.benchmark.read_bytes();benchmark=json.loads(raw)
    result=evaluate(a.graph,a.embeddings,benchmark);result['benchmarkSha256']=hashlib.sha256(raw).hexdigest();result['protocol']=benchmark.get('protocol','')
    from knowledge_store import atomic_write
    atomic_write(a.output,json.dumps(result,ensure_ascii=False,indent=2)+'\n');emit({k:v for k,v in result.items() if k!='comparisons'})

if __name__=='__main__':run(main)
