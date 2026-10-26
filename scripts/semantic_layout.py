"""Measured 3D neighborhood projection of validated sentence embeddings."""
import hashlib
import json
from pathlib import Path
from cli_common import Parser, emit, run
from graph_tools import load_graph, entity_records, semantic_input_hash, layout_for


def metrics(x, y):
    import numpy as np
    from scipy.stats import spearmanr
    from scipy.spatial.distance import pdist, squareform
    from sklearn.manifold import trustworthiness
    n=len(x); k=min(10, max(1,(n-1)//2))
    a=squareform(pdist(x,'cosine')); b=squareform(pdist(y))
    np.fill_diagonal(a,np.inf); np.fill_diagonal(b,np.inf)
    neighbors_a=np.argsort(a,axis=1)[:,:k]; neighbors_b=np.argsort(b,axis=1)[:,:k]
    return dict(k=k, neighborRecall=float(np.mean([len(set(i)&set(j))/k for i,j in zip(neighbors_a,neighbors_b)])), trustworthiness=float(trustworthiness(x,y,n_neighbors=k,metric='cosine')), distanceSpearman=float(spearmanr(pdist(x,'cosine'),pdist(y)).statistic))


def main():
    p=Parser(description=__doc__); p.add_argument('--graph',type=Path,required=True); a=p.parse_args()
    import numpy as np
    from sklearn.manifold import TSNE
    import sklearn
    from knowledge_store import locate, generated, atomic_write, write_lock
    with write_lock(locate(a.graph)):
        graph,raw=load_graph(a.graph); out=generated(locate(a.graph)); emb=out/'embeddings'
        manifest=json.loads((emb/'manifest.json').read_text()); ids=json.loads((emb/'entities.ids.json').read_text())
        vector_bytes=(emb/'entities.npy').read_bytes()
        if manifest['semanticInputSha256'] != semantic_input_hash(entity_records(a.graph)): raise ValueError('Embeddings desatualizados.')
        if hashlib.sha256(vector_bytes).hexdigest()!=manifest['matrixSha256'] or hashlib.sha256((emb/'entities.ids.json').read_bytes()).hexdigest()!=manifest['idsSha256']: raise ValueError('Hash dos embeddings inválido.')
        x=np.load(emb/'entities.npy',allow_pickle=False)
        if manifest.get('kind')!='entities' or not manifest.get('resolvedRevision') or x.ndim!=2 or len(x)!=len(ids) or len(set(ids))!=len(ids) or set(ids)!={n['id'] for n in graph['nodes']} or not np.isfinite(x).all() or not np.allclose(np.linalg.norm(x,axis=1),1,atol=1e-4): raise ValueError('Vetores inválidos.')
        if len(ids)<4: raise ValueError('Projeção avaliada requer ao menos quatro entidades.')
        # Fixed policy, independent of hand-selected concept pairs.
        perplexity=min(10.0,(len(ids)-1)/3)
        y=TSNE(n_components=3,metric='cosine',perplexity=perplexity,init='pca',random_state=42,learning_rate='auto',max_iter=1500).fit_transform(x)
        score=metrics(x,y)
        if not all(np.isfinite(v) for v in score.values()): raise ValueError('Métricas indefinidas; verifique vetores duplicados ou degenerados.')
        editorial=layout_for(graph,raw)
        old=np.array([[editorial['positions'][i][axis] for axis in ('x','y','z')] for i in ids])
        y-=y.mean(axis=0); scale=float(np.max(np.linalg.norm(y,axis=1)))
        if not scale>0: raise ValueError('Projeção degenerada.')
        y*=450/scale
        result=dict(method='semantic-tsne-3d-v1',graphSha256=hashlib.sha256(raw).hexdigest(),semanticInputSha256=manifest['semanticInputSha256'],matrixSha256=manifest['matrixSha256'],model=manifest['model'],revision=manifest['resolvedRevision'],parameters=dict(perplexity=perplexity,seed=42,iterations=1500,dimensions=3,metric='cosine'),sklearnVersion=sklearn.__version__,metrics=score,editorialBaseline=metrics(x,old),positions={i:dict(zip(('x','y','z'),map(float,v))) for i,v in zip(ids,y)})
        text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        atomic_write(out/'semantic-layout.json',text); atomic_write(out/'layout.json',text)
        emit(dict(path=str(out/'semantic-layout.json'),metrics=score,editorialBaseline=result['editorialBaseline']))

if __name__=='__main__': run(main)
