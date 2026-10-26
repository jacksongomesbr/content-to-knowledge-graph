"""Resolve reviewed line references against a versioned source body, without excerpts."""
import hashlib
import re
from functools import lru_cache


def paragraph(lines, first, last):
    if type(first) is not int or type(last) is not int or not 1 <= first <= last <= len(lines):
        raise ValueError('Intervalo de linhas de evidência inválido.')
    start, end = first - 1, last
    # A list item is a separate paragraph; do not swallow adjacent items/headings.
    def boundary(line):
        import re
        return not line.strip() or bool(re.match(r'^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)', line))
    while start > 0 and not boundary(lines[start]) and not boundary(lines[start-1]): start -= 1
    while end < len(lines) and not boundary(lines[end]): end += 1
    return start + 1, end, '\n'.join(lines[start:end])


def compile_evidence(records, graph_sha256):
    sources = {r.metadata['id']: r for r in records if r.metadata['kind'] == 'source'}
    nodes = {r.metadata['id']: r.metadata for r in records if r.metadata['kind'] == 'entity'}
    for source in sources.values():
        mode=source.metadata.get('content_mode')
        if mode not in (None,'reference','original'): raise ValueError(f'{source.path}: content_mode inválido.')
        if mode=='reference':
            checksum=source.metadata.get('source_sha256')
            if not isinstance(checksum,str) or not re.fullmatch(r'[a-f0-9]{64}',checksum):
                raise ValueError(f'{source.path}: source_sha256 deve ser SHA-256 hexadecimal.')
    result = {}
    for record in records:
        m = record.metadata
        if m['kind'] not in ('entity', 'relation'): continue
        items = []
        for index, ref in enumerate(m.get('evidence', [])):
            source = sources[ref['source']]
            item = dict(id=f'{record.key}:{index}', source=ref['source'], locator=ref['locator'], status='unavailable')
            for field in ('heading','relation_text'):
                if field in ref and (not isinstance(ref[field],str) or not ref[field].strip()): raise ValueError(f'{record.path}: {field} deve ser texto não vazio.')
            if source.metadata.get('content_mode') == 'reference':
                bounds = ref.get('lines')
                if not re.fullmatch(r'[a-f0-9]{64}', source.metadata.get('source_sha256','')):
                    raise ValueError(f'{source.path}: source_sha256 obrigatório para fonte referenciada.')
                if not isinstance(bounds,list) or len(bounds)!=2 or any(type(n) is not int for n in bounds) or not 1 <= bounds[0] <= bounds[1]:
                    raise ValueError(f'{record.path}: intervalo de linhas obrigatório.')
                ids = [m['id']] if m['kind']=='entity' else [m['source'],m['target']]
                terms = [dict(entity=n,text=term,role='entity') for n in ids for term in [nodes[n]['label'],*nodes[n].get('aliases',[])] if term]
                if m['kind']=='relation' and m.get('basis')!='inferred': terms.append(dict(entity=m['source'],text=ref.get('relation_text',m['label']),role='relation'))
                unit=ref.get('unit','document')
                if not ((type(unit) is int and unit>0) or (isinstance(unit,str) and unit.strip())): raise ValueError(f'{record.path}: unit deve ser página positiva ou identificador textual.')
                item.update(status='deferred',lines=bounds,unit=unit,heading=ref.get('heading',''),terms=terms,relationText=ref.get('relation_text'),sourceSha256=source.metadata['source_sha256'])
            if source.metadata.get('content_mode') == 'original':
                digest = hashlib.sha256(source.body.encode()).hexdigest()
                if digest != source.metadata.get('content_sha256'): raise ValueError(f'{source.path}: hash do texto original divergente.')
                bounds = ref.get('lines')
                if not isinstance(bounds, list) or len(bounds) != 2: raise ValueError(f'{record.path}: informe duas linhas para expandir a evidência.')
                first, last, text = paragraph(source.body.splitlines(), *bounds)
                ids = [m['id']] if m['kind'] == 'entity' else [m['source'], m['target']]
                terms = [dict(entity=n, text=term, role='entity') for n in ids for term in [nodes[n]['label'], *nodes[n].get('aliases', [])] if term]
                literal = ref.get('relation_text')
                if literal is not None and (not isinstance(literal, str) or not literal.strip() or literal.casefold() not in text.casefold()):
                    raise ValueError(f'{record.path}: relation_text deve existir literalmente no parágrafo.')
                if m['kind'] == 'relation' and m.get('basis') != 'inferred':
                    terms += [dict(entity=m['source'], text=ref.get('relation_text', m['label']), role='relation')]
                headings = [re.sub(r'^#{1,6}\s+', '', line).strip() for line in source.body.splitlines()[:first] if re.match(r'^#{1,6}\s+', line)]
                item.update(status='available', text=text, lines=[first,last], sourceSha256=digest, terms=terms, heading=headings[-1] if headings else '')
            items.append(item)
        result[record.key] = dict(basis=m.get('basis'), rationale=m.get('rationale'), items=items)
    return dict(schemaVersion=1, graphSha256=graph_sha256, records=result)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


def read_text_paragraph(path, bounds):
    """Stream up to the requested paragraph; retain no document-sized copy."""
    import re
    first, last = bounds
    if type(first) is not int or type(last) is not int or not 1 <= first <= last:
        raise ValueError('Intervalo de linhas inválido.')
    block, start, heading, found = [], 1, '', False
    with path.open(encoding='utf-8-sig') as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.rstrip('\r\n')
            boundary = not line.strip() or bool(re.match(r'^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)', line))
            if number > last and boundary: break
            if number <= first:
                if re.match(r'^#{1,6}\s+', line): heading = re.sub(r'^#{1,6}\s+', '', line).strip()
                if not line.strip(): block, start = [], number+1
                elif re.match(r'^#{1,6}\s+',line) and number < first: block, start = [], number+1
                elif boundary: block, start = [line], number
                else: block.append(line)
            else: block.append(line)
            if number >= last: found = True
    if not found or not block: raise ValueError('Linhas da referência não existem na fonte.')
    return start, start+len(block)-1, '\n'.join(block), heading


def source_signature(stat):
    return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns


@lru_cache(maxsize=128)
def verified_source_hash(path, signature):
    # Cache checksums only, never source text. ctime also detects restored mtime.
    return file_sha256(path)


def resolve_reference(item, sources):
    """Only registered IDs are resolved; request parameters never supply a path."""
    from pathlib import Path
    source = sources.get(item['source'], {})
    if source.get('content_mode') != 'reference': return item if item.get('status')=='available' else dict(item,status='unavailable',message='Esta fonte não possui um leitor de referência cadastrado.')
    result = dict(item, status='unavailable')
    try:
        path = Path(source.get('sourceFile', ''))
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ValueError('A fonte cadastrada está indisponível ou mudou de endereço.')
        before = path.stat()
        if verified_source_hash(path,source_signature(before)) != source['source_sha256']:
            return dict(result, status='changed', message='A fonte foi alterada. Revalide esta referência antes de consultar o parágrafo.')
        bounds = item['lines']
        if path.suffix.lower() in ('.txt', '.md', '.qmd'):
            first,last,text,heading = read_text_paragraph(path,bounds)
        else:
            unit = item.get('unit', 'document')
            if path.suffix.lower() == '.pdf':
                from pypdf import PdfReader
                if type(unit) is not int or unit < 1: raise ValueError('A referência PDF exige o número da página em unit.')
                text = PdfReader(path).pages[unit-1].extract_text() or ''
            else:
                from extract_corpus import iter_extract
                text=next((text for key,text in iter_extract(path) if key==unit),None)
                if text is None: raise ValueError('Unidade da fonte não encontrada.')
            first,last,text = paragraph(text.splitlines(),*bounds); heading=item.get('heading','')
        after = path.stat()
        if source_signature(before) != source_signature(after):
            return dict(result,status='changed',message='A fonte mudou durante a leitura; consulte novamente após revalidá-la.')
        literal = item.get('relationText')
        if literal and literal.casefold() not in text.casefold(): raise ValueError('A expressão da relação não corresponde à referência; revalide-a.')
        return dict(item,status='available',text=text,lines=[first,last],heading=heading,sourceSha256=source['source_sha256'])
    except Exception as exc:  # Reader plugins may raise format-specific exceptions.
        return dict(result,message=str(exc))
