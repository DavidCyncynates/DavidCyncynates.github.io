const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateText=value=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'));
const states={current:'Current cycle',unverified:'Availability unconfirmed',archive:'Archive'};
export function rumorCard(source){
  const url=new URL(source.url);
  if(!['https:','http:'].includes(url.protocol)||!states[source.status])throw Error('Invalid rumor source');
  const action=source.status==='archive'?'Open archive':source.status==='unverified'?'Visit source':'Open rumor mill';
  return `<article class="rumor-card"><div class="rumor-card-top"><p class="rumor-region">${esc(source.region)}</p><span class="rumor-state ${source.status}">${esc(source.status==='current'?source.cycle:states[source.status])}</span></div><h3>${esc(source.name)}</h3><p class="rumor-field">${esc(source.field)}</p><p class="rumor-description">${esc(source.description)}</p>${source.note?`<p class="rumor-note">${esc(source.note)}</p>`:''}<a class="rumor-open" href="${esc(url.href)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(action+' — '+source.name)}">${action} <span aria-hidden="true">↗</span></a><p class="rumor-checked">${source.status==='unverified'?'Last attempted':'Link checked'} ${esc(dateText(source.checkedOn))}${source.sourceUpdatedOn?' · Source updated '+esc(dateText(source.sourceUpdatedOn)):''}</p></article>`;
}
export async function loadRumors(doc,fetcher=fetch){
  const target=doc.querySelector('#rumor-sources');
  try{
    const response=await fetcher('data/rumor-mills.json');
    if(!response.ok)throw Error('Rumor directory unavailable');
    const data=await response.json();
    const current=data.sources.filter(s=>s.status==='current');
    const other=data.sources.filter(s=>s.status!=='current');
    target.innerHTML=`<div class="rumor-grid">${current.map(rumorCard).join('')}</div>${other.length?`<section class="rumor-other" aria-labelledby="other-rumors-title"><h3 id="other-rumors-title">Other regional sources</h3><div class="rumor-grid">${other.map(rumorCard).join('')}</div></section>`:''}`;
  }catch{
    target.innerHTML='<p class="rumor-error" role="status">The directory could not load. Please reload, or <a href="https://sites.google.com/site/postdocrumor/" target="_blank" rel="noopener noreferrer">browse the source index ↗</a>.</p>';
  }
}
