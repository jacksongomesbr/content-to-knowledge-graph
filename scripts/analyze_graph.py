"""Graph metrics and optional embedding neighbors; candidates are not factual edges."""
import argparse
import json
from pathlib import Path
from graph_tools import load_graph


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('graph',type=Path); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--embeddings',type=Path); p.add_argument('--neighbors',type=int,default=5); a=p.parse_args()
    if a.neighbors<1: p.error('--neighbors deve ser positivo')
    if a.output.exists(): p.error('Arquivo de saída existe; use um novo caminho.')
    import networkx as nx
    graph,raw=load_graph(a.graph); net=nx.MultiDiGraph()
    net.add_nodes_from(n['id'] for n in graph['nodes']); net.add_edges_from((e['source'],e['target']) for e in graph['edges'])
    report=dict(nodes=net.number_of_nodes(),edges=net.number_of_edges(),isolated=sorted(nx.isolates(net)),weakComponents=[sorted(c) for c in nx.weakly_connected_components(net)],strongComponents=[sorted(c) for c in nx.strongly_connected_components(net)],degree=dict(net.degree()),note='Métricas estruturais e candidatos semânticos não demonstram relações factuais.')
    if a.embeddings:
        import numpy as np
        from sklearn.neighbors import NearestNeighbors
        import hashlib
        manifest=json.loads((a.embeddings/'manifest.json').read_text())
        if manifest.get('kind')!='entities' or manifest.get('inputSha256')!=hashlib.sha256(raw).hexdigest(): p.error('Embeddings não correspondem aos nós e aos bytes deste grafo.')
        ids=json.loads((a.embeddings/'entities.ids.json').read_text()); vectors=np.load(a.embeddings/'entities.npy',allow_pickle=False)
        if vectors.ndim!=2 or len(vectors)!=len(ids) or len(set(ids))!=len(ids) or set(ids)!=set(net) or vectors.shape[1]!=manifest['dimension'] or not np.isfinite(vectors).all(): p.error('Embeddings inválidos ou desalinhados.')
        if np.any(np.linalg.norm(vectors,axis=1)==0): p.error('Vetor nulo.')
        k=min(a.neighbors+1,len(ids)); distances,indices=NearestNeighbors(n_neighbors=k,metric='cosine',algorithm='brute').fit(vectors).kneighbors(vectors)
        pairs={}
        for i,row in enumerate(indices):
            for d,j in zip(distances[i],row):
                if i==j: continue
                key=tuple(sorted((ids[i],ids[j]))); pairs[key]=float(1-d)
        report['similarityCandidates']=[dict(source=i,target=j,cosine=score) for (i,j),score in sorted(pairs.items(),key=lambda item:-item[1])]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print(f'Análise em {a.output}')

if __name__=='__main__': main()
