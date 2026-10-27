"""Export a deployable static viewer, with optional deduplicated evidence paragraphs."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit
from cli_common import Parser, emit, run
from graph_tools import load_graph, preferred_layout
from knowledge_store import build, locate, generated
from evidence_passages import resolve_reference


def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')


def export_site(graph_path, destination, config=None, evidence_mode='references'):
    destination=Path(destination).resolve();root=locate(graph_path)
    if destination.exists(): raise ValueError('Destino já existe; escolha uma pasta nova para preservar arquivos.')
    if evidence_mode not in ('references','paragraphs'): raise ValueError('Modo de evidência inválido.')
    built=build(root);out=Path(built['generated']);graph,raw=load_graph(out/'graph.json');layout=preferred_layout(root,graph,raw)
    assets=Path(__file__).resolve().parents[1]/'assets/viewer/dist'
    if not (assets/'index.html').is_file(): raise ValueError('Bundle do visualizador ausente.')
    evidence=json.loads((out/'evidence/passages.json').read_text());sources=graph['sources'];available=unavailable=0;unique=set()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        site=Path(temporary)/'site';shutil.copytree(assets,site)
        for record in evidence['records'].values():
            for item in record['items']:
                if evidence_mode=='paragraphs':
                    resolved=resolve_reference(item,sources)
                else:
                    resolved=dict(item,status='unavailable',message='Esta exportação contém somente a referência; o parágrafo exige acesso à fonte no aplicativo local.')
                    resolved.pop('text',None)
                payload={k:resolved[k] for k in ('status','text','lines','heading','sourceSha256','message') if k in resolved}
                checksum=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                relative='evidence/paragraphs/'+checksum+'.json'
                write_json(site/relative,payload);unique.add(checksum)
                item.pop('text',None);item.update(status=resolved['status'],passagePath=relative)
                if resolved['status']=='available':available+=1
                else:unavailable+=1
        # Paths on the author's filesystem are neither usable nor appropriate in a public site.
        for source in graph['sources'].values():
            value=source.get('sourceFile','')
            if urlsplit(value).scheme not in ('https','http'):
                source['sourceFile']=Path(value).name if value else 'Origem local'
        if isinstance(graph.get('originSkills'),list): graph['originSkills']=[Path(value).name for value in graph['originSkills']]
        public_raw=(json.dumps(graph,ensure_ascii=False,indent=2)+'\n').encode();checksum=hashlib.sha256(public_raw).hexdigest()
        layout['graphSha256']=checksum;evidence['graphSha256']=checksum
        viewer=dict(title='Grafo de conhecimento',subtitle=f"{len(graph['nodes'])} entidades · {len(graph['edges'])} relações")
        if config:viewer.update(config)
        viewer['layoutDescription']=('Posições por similaridade semântica dos textos (t-SNE 3D). Vizinhanças aproximadas; distâncias entre grupos não são uma escala global de significado.' if layout['method']=='semantic-tsne-3d-v1' else 'Posições editoriais por tema; distância não mede similaridade semântica.')
        (site/'graph.json').write_bytes(public_raw);write_json(site/'layout.json',layout);write_json(site/'viewer-config.json',viewer);write_json(site/'evidence-data.json',evidence)
        manifest=dict(schemaVersion=1,evidenceMode=evidence_mode,availableReferences=available,unavailableReferences=unavailable,uniquePassageFiles=len(unique),graphSha256=checksum,layoutMethod=layout['method'])
        write_json(site/'export-manifest.json',manifest)
        (site/'DEPLOY.md').write_text('Sirva esta pasta em hospedagem HTTP(S) estática, inclusive em subdiretórios. Não exige Python/Node no servidor. file:// não é suportado. Não há API de leitura de arquivos locais. O modo paragraphs inclui somente parágrafos referenciados, deduplicados; não inclui fontes integrais. Referências indisponíveis são informadas na modal. Revise direitos e conteúdo antes de publicar.\n',encoding='utf-8')
        # No merge/overwrite: destination must still be absent at publication time.
        site.rename(destination)
    return dict(directory=str(destination),**manifest)


def main():
    p=Parser(description=__doc__);p.add_argument('--graph',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--evidence',choices=['references','paragraphs'],default='references');a=p.parse_args()
    config=json.loads(a.config.read_text()) if a.config else None
    result=export_site(a.graph,a.output,config,a.evidence);partial=a.evidence=='paragraphs' and result['unavailableReferences']>0
    emit(result,status='partial' if partial else 'success');return 3 if partial else 0

if __name__=='__main__':run(main)
