"""Extract document text to JSONL units with locators. No semantic graph extraction."""
import argparse
import hashlib
import json
from pathlib import Path

SUPPORTED = {'.txt','.md','.qmd','.html','.htm','.pdf','.docx','.epub'}
SKIP = {'.git','node_modules','.venv','dist','_output','__pycache__'}


def extract(path):
    ext = path.suffix.lower()
    if ext == '.pdf':
        from pypdf import PdfReader
        return [(i+1, page.extract_text() or '') for i, page in enumerate(PdfReader(path).pages)]
    if ext == '.docx':
        from docx import Document
        doc = Document(path)
        return [('document', '\n'.join([p.text for p in doc.paragraphs] + [' | '.join(c.text for c in row.cells) for t in doc.tables for row in t.rows]))]
    if ext == '.epub':
        import zipfile
        from bs4 import BeautifulSoup
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(path) as z:
            container = ET.fromstring(z.read('META-INF/container.xml'))
            opf = next(e.attrib['full-path'] for e in container.iter() if e.tag.endswith('rootfile'))
            root = ET.fromstring(z.read(opf)); manifest = {e.attrib['id']:e.attrib['href'] for e in root.iter() if e.tag.endswith('item')}
            import posixpath
            units = []
            for e in root.iter():
                if e.tag.endswith('itemref'):
                    name = posixpath.normpath(posixpath.join(posixpath.dirname(opf), manifest[e.attrib['idref']]))
                    units.append((name, BeautifulSoup(z.read(name), 'html.parser').get_text('\n')))
            return units
    text = path.read_text(encoding='utf-8')
    if ext in ('.html','.htm'):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, 'html.parser')
        for el in soup(['script','style']): el.decompose()
        text = soup.get_text('\n')
    return [('document', text)]


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('origins', nargs='+', type=Path); p.add_argument('--output', required=True, type=Path)
    a=p.parse_args(); output=a.output.resolve()
    if output.exists() and any(output.iterdir()): p.error('Use uma pasta de extração nova/vazia para preservar resultados existentes.')
    output.mkdir(parents=True,exist_ok=True); units=[]; coverage=[]; seen=set()
    for origin in a.origins:
        origin=origin.resolve()
        if not origin.exists(): p.error(f'Origem inexistente: {origin}')
        files=sorted(origin.rglob('*')) if origin.is_dir() else [origin]
        for file in files:
            if not file.is_file() or file.is_symlink() or file.suffix.lower() not in SUPPORTED or any(x in SKIP for x in file.parts): continue
            actual=file.resolve()
            if output == actual or output in actual.parents or actual in seen: continue
            if origin.is_dir() and not actual.is_relative_to(origin): continue
            seen.add(actual)
            item={'path':str(actual),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
            try:
                texts=extract(file); nonempty=0
                for locator,text in texts:
                    if not text.strip(): continue
                    nonempty+=1
                    uid=hashlib.sha256(f'{actual}:{locator}'.encode()).hexdigest()[:20]
                    units.append(dict(id=uid,sourceFile=str(actual),locator=locator,text=text,textSha256=hashlib.sha256(text.encode()).hexdigest()))
                item.update(status='read' if nonempty == len(texts) and texts else 'partial', units=nonempty, totalUnits=len(texts))
                if nonempty != len(texts) or not texts: item['limitation']='Unidades sem texto extraível; OCR pode ser necessário.'
            except Exception as exc: item.update(status='blocked',error=str(exc))
            coverage.append(item)
    (output/'units.jsonl').write_text(''.join(json.dumps(u,ensure_ascii=False)+'\n' for u in units))
    (output/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(units)} unidades; {len(coverage)} arquivos. Extração textual não equivale a revisão semântica.')
    return 1 if any(c['status']!='read' for c in coverage) else 0

if __name__=='__main__': raise SystemExit(main())
