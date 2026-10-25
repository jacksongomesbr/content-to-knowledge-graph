"""Validate Agent Skills frontmatter, including the standard compatibility field."""
from pathlib import Path
import re
from cli_common import Parser, emit, run
from knowledge_store import yaml_load

ALLOWED = {'name','description','license','compatibility','metadata','allowed-tools'}


def validate(root):
    root=Path(root).resolve()
    document=(root/'SKILL.md').read_text(encoding='utf-8-sig')
    match=re.fullmatch(r'---\r?\n(.*?)\r?\n---\r?\n(.*)',document,re.S)
    if not match: raise ValueError('SKILL.md exige frontmatter YAML delimitado por --- e corpo Markdown.')
    metadata=yaml_load(match[1]);errors=[];warnings=[]
    if not isinstance(metadata,dict): raise ValueError('Frontmatter deve ser objeto.')
    name=metadata.get('name');description=metadata.get('description')
    if not isinstance(name,str) or len(name)>64 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name): errors.append('name deve ser slug minúsculo de até 64 caracteres, sem hífens consecutivos.')
    elif name!=root.name: errors.append('name deve corresponder ao nome da pasta da skill.')
    if not isinstance(description,str) or not description.strip() or len(description)>1024: errors.append('description deve ter entre 1 e 1024 caracteres.')
    for key in metadata:
        if key not in ALLOWED: errors.append('Campo desconhecido: '+key)
    for key in ('license','compatibility','allowed-tools'):
        if key in metadata and (not isinstance(metadata[key],str) or not metadata[key].strip()): errors.append(key+' deve ser string não vazia.')
    if isinstance(metadata.get('compatibility'),str) and len(metadata['compatibility'])>500: errors.append('compatibility excede 500 caracteres.')
    if 'metadata' in metadata and (not isinstance(metadata['metadata'],dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in metadata['metadata'].items())): errors.append('metadata deve mapear strings para strings.')
    if not match[2].strip(): errors.append('Corpo da skill está vazio.')
    if len(match[2].splitlines())>500: warnings.append('Corpo extenso: considere mover detalhes para referências.')
    return dict(valid=not errors,name=name,errors=errors,warnings=warnings)


def main():
    parser=Parser(description=__doc__);parser.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    result=validate(args.root)
    emit(result,status='success' if result['valid'] else 'error',error=None if result['valid'] else dict(code='invalid_skill',message='; '.join(result['errors'])))
    return 0 if result['valid'] else 1

if __name__=='__main__':raise SystemExit(run(main))
