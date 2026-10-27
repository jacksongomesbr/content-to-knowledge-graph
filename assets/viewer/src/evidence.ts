import { data, entities, relations, types } from './model';

import { highlighted, type Term } from './evidence-highlight';
type Passage = {id:string; source:string; locator:string; status:string; passagePath?:string; text?:string; lines?:number[]; terms?:Term[]; heading?:string; sourceSha256?:string; message?:string};
type Entry = {basis?:string; rationale?:string; items:Passage[]};
let records: Record<string,Entry> = {};
const escape = (s:string) => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export async function loadEvidence() {
  try {
    const response = await fetch('./evidence-data.json');
    if (response.ok) records = (await response.json()).records || {};
  } catch { records = {}; }
}
function referenceContext(key:string, p:Passage):string {
  const id=key.slice(key.indexOf(':')+1);
  const edge=key.startsWith('relation:')?relations.get(id):undefined;
  const topic=edge?`${entities.get(edge.source)?.label || ''} · ${entities.get(edge.target)?.label || ''}`:entities.get(id)?.label;
  return [topic,p.heading].filter(Boolean).join(' — ');
}
export function evidenceMarkup(key:string, sourceKeys:string[]):string {
  const entry = records[key];
  const items = entry?.items || [];
  return `<section class="sources"><h3>Referências no conteúdo</h3>${items.map((p,i) => `<button class="source-link evidence-reference" data-evidence-record="${escape(key)}" data-evidence-index="${i}" aria-haspopup="dialog"><strong class="evidence-reference-title">${escape(data.sources[p.source]?.section || 'Fonte')}</strong><span class="evidence-reference-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/></svg></span><small class="evidence-reference-location">${escape(referenceContext(key,p))}</small></button>`).join('')}${items.length ? '' : '<p class="source-note">Não há referência por frase ou parágrafo disponível para esta seleção.</p>'}${sourceKeys.filter(s => !items.some(p => p.source===s)).map(s => `<p class="source-note">${escape(data.sources[s]?.section || s)} — localizador não disponível.</p>`).join('')}</section>`;
}
let dialog:HTMLDialogElement;
let requestSequence=0;
let requestController:AbortController | undefined;
export function initializeEvidence() {
  dialog=document.createElement('dialog'); dialog.className='evidence-dialog'; dialog.setAttribute('aria-labelledby','evidence-title');
  document.body.append(dialog);
  dialog.addEventListener('close',()=>requestController?.abort());
  dialog.addEventListener('click',e=>{
    const rect=dialog.getBoundingClientRect();
    const outside=e.clientX<rect.left || e.clientX>rect.right || e.clientY<rect.top || e.clientY>rect.bottom;
    if ((e.target===dialog && outside) || (e.target as HTMLElement).closest('[data-close-evidence]')) dialog.close();
  });
  document.addEventListener('click',async e=>{
    const button=(e.target as HTMLElement).closest<HTMLButtonElement>('[data-evidence-record]');
    if (!button) return;
    const entry=records[button.dataset.evidenceRecord!]; let p=entry?.items[Number(button.dataset.evidenceIndex)]; if(!p) return;
    const request=++requestSequence;
    requestController?.abort(); requestController=new AbortController();
    const controller=requestController;
    const timeout=setTimeout(()=>controller.abort(),15000);
    dialog.innerHTML='<div class="evidence-dialog-header"><h2 id="evidence-title">Contexto da referência</h2><button data-close-evidence aria-label="Fechar contexto">×</button></div><p role="status">Consultando referência…</p>';
    if (!dialog.open) dialog.showModal();
    try {
      const passageUrl=p.passagePath ? new URL(p.passagePath, location.href) : new URL('./evidence-passage?id='+encodeURIComponent(p.id), location.href);
      if (passageUrl.origin!==location.origin || !passageUrl.pathname.startsWith(new URL('./',location.href).pathname)) throw new Error('Caminho de referência inválido.');
      const response=await fetch(passageUrl,{signal:controller.signal});
      if (!response.ok) throw new Error('Referência indisponível no servidor.');
      p={...p,...await response.json()} as Passage;
    } catch { p={...p,status:'unavailable',message:'Não foi possível consultar a fonte. Verifique o acesso ao arquivo e tente novamente.'}; }
    finally { clearTimeout(timeout); }
    if (!dialog.open || request!==requestSequence) return;
    const h=highlighted(p.text || '',p.terms || [],id=>types[entities.get(id)?.type || 'concept']?.color || '#21675c');
    const unique=[...new Set((p.terms || []).filter(t=>t.role==='entity' && entities.has(t.entity)).map(t=>t.entity))];
    const absent=unique.filter(id=>!h.matched.has(id));
    const isRelation=button.dataset.evidenceRecord!.startsWith('relation:');
    dialog.innerHTML=`<div class="evidence-dialog-header"><div><p class="eyebrow">CONTEXTO DA REFERÊNCIA</p><h2 id="evidence-title">${escape(data.sources[p.source]?.section || 'Fonte')}</h2></div><button data-close-evidence aria-label="Fechar contexto">×</button></div><p class="source-note">${escape(referenceContext(button.dataset.evidenceRecord!,p))}</p>${p.status==='available'?`<div class="evidence-paragraph">${h.html}</div>`:`<p role="status">${escape(p.message || 'A origem desta referência não está acessível.')}</p>`}<div class="evidence-legend">${unique.map(id=>`<span><i style="background:${escape(types[entities.get(id)!.type].color)}"></i>${escape(entities.get(id)!.label)}</span>`).join('')}</div>${p.status==='available' && absent.length?`<p class="source-note">Sem menção literal reconhecida neste parágrafo: ${absent.map(id=>escape(entities.get(id)!.label)).join(', ')}. O destaque usa nomes e aliases revisados; não confirma a afirmação.</p>`:''}${p.status==='available' && isRelation && entry.basis!=='inferred' && !h.matched.has('relation')?'<p class="source-note">A formulação da relação não aparece literalmente neste parágrafo.</p>':''}${entry.basis==='inferred'?`<p class="evidence-inference"><strong>Relação inferida</strong> · ${escape(entry.rationale || 'Interpretação apoiada no contexto, sem expressão literal da relação.')}</p>`:''}<details class="evidence-source-details"><summary>Detalhes da fonte</summary><dl><dt>Arquivo ou origem</dt><dd>${escape(data.sources[p.source]?.sourceFile || 'Não informado')}</dd>${p.heading?`<dt>Seção</dt><dd>${escape(p.heading)}</dd>`:''}${p.lines?`<dt>Linhas</dt><dd>${escape(p.lines.join('–'))}</dd>`:''}<dt>Localizador</dt><dd>${escape(p.locator)}</dd>${p.sourceSha256?`<dt>Versão da fonte · SHA-256</dt><dd><code>${escape(p.sourceSha256)}</code></dd>`:''}</dl></details>`;
    dialog.querySelector<HTMLButtonElement>('[data-close-evidence]')?.focus();
  });
}
export function evidenceIsOpen():boolean { return !!dialog?.open; }
