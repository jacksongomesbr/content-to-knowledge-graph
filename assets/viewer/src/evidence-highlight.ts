export type Term = {entity:string; text:string; role:string};
const escape = (s:string) => s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function highlighted(text:string, terms:Term[], colorFor:(id:string)=>string):{html:string; matched:Set<string>} {
  const candidates = terms.filter(t => t.text.trim()).sort((a,b)=>b.text.length-a.text.length);
  const matched = new Set<string>();
  const spans:{start:number; end:number;term:Term}[]=[];
  for (const term of candidates) {
    const needle = term.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(needle, 'giu');
    for (const m of text.matchAll(re)) {
      const start=m.index!,end=start+m[0].length;
      if (/[\p{L}\p{N}_]/u.test(text.slice(0,start).slice(-1)) || /[\p{L}\p{N}_]/u.test(text.slice(end,end+1))) continue;
      if (spans.some(s=>start<s.end && end>s.start)) continue;
      spans.push({start,end,term}); matched.add(term.role==='relation'?'relation':term.entity);
    }
  }
  spans.sort((a,b)=>a.start-b.start);
  let pos=0, html='';
  for (const s of spans) {
    const color=colorFor(s.term.entity);
    html+=escape(text.slice(pos,s.start))+`<mark class="evidence-highlight ${s.term.role==='relation'?'relation-highlight':''}" style="--evidence-color:${escape(color)}">${escape(text.slice(s.start,s.end))}</mark>`;
    pos=s.end;
  }
  return {html:html+escape(text.slice(pos)),matched};
}
