import {status,matches,sortJobs,clusterPoints} from './core.mjs';
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const publicURL=u=>{try{const x=new URL(u);return ['https:','http:'].includes(x.protocol)?x.href:'#'}catch{return '#'}};
const link=(u,text,cls='')=>`<a class="${cls}" href="${esc(publicURL(u))}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>`;
const dateText=d=>new Date(d+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
const countries=new Intl.DisplayNames(['en'],{type:'region'});
const country=c=>countries.of(c)||c;
const kindLabel=k=>k==='formal-vacancy'?'Advertised vacancy':'Expression of interest';
const dateKind={hard:'Deadline',priority:'Full consideration','review-start':'Review begins',listed:'Listed date',eoi:'Host EOI deadline'};
const fieldLabel=s=>s.replaceAll('-',' ').replace(/\b\w/g,c=>c.toUpperCase()).replace('Ai ','AI ');
const themeKey='davidcyncynates:color-theme';
$('#theme').addEventListener('click',()=>{document.documentElement.classList.toggle('dark');try{localStorage.setItem(themeKey,document.documentElement.classList.contains('dark')?'dark':'light')}catch{}updateTheme()});
function updateTheme(){const dark=document.documentElement.classList.contains('dark');$('#theme').setAttribute('aria-label',`Switch to ${dark?'light':'dark'} theme`);document.querySelector('meta[name="theme-color"]').content=dark?'#191a18':'#f4f0e7';if(land)land.setStyle(landStyle());}
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const landStyle=()=>({color:css('--border'),weight:.65,fillColor:css('--land'),fillOpacity:1});
let catalog,byInst,filtered=[],region=null,map,land,markers,selected=null,dirSources;
let now=Date.now();
function filters(){return {q:$('#search').value,field:$('#field').value,country:$('#country').value,kind:$('#kind').value,scope:$('#scope').value,profile:$('#profile').value,due:$('#due').value,closed:$('#closed').checked,review:$('#review').checked}}
function location(j){return j.location?.verification==='verified'?j.location:byInst.get(j.institutionId)?.location}
function plotReady(j){const p=location(j);return p?.verification==='verified'&&Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)}
function institutionBadges(i){return i.officialClassifications.map(c=>`<span class="badge">${esc(['R1','R2','RCU'].includes(c.designation)?c.designation:'No Carnegie research designation')} · ${c.year}</span>`).join('')+(i.profile?`<span class="badge">${esc(i.profile)}</span>`:'')}
function timing(j){const s=status(j,now);if(s.closed)return j.explicitClosed?'Closed by institution':'Deadline passed';if(s.next)return `${dateKind[s.next.kind]} · ${dateText(s.next.date)}`;if(s.pastSoft)return 'Review / priority date passed';return j.openUntilFilled?'Open until filled':'Date unconfirmed'}
function render(){
  const f=filters();filtered=sortJobs(catalog.jobs.filter(j=>matches(j,byInst.get(j.institutionId),f,now)),now);
  const n=Object.entries(f).filter(([k,v])=>k!=='q'&&v).length;$('#filter-count').textContent=n||'';
  if(region){region=new Set([...region].filter(id=>filtered.some(j=>j.id===id)));if(!region.size)region=null}
  renderList();renderMarkers();
}
function renderList(){
  const jobs=region?filtered.filter(j=>region.has(j.id)):filtered;
  $('#result-count').textContent=`${jobs.length} ${jobs.length===1?'search':'searches'}${region?' in this region':''}`;
  const missing=jobs.filter(j=>!plotReady(j)).length;
  $('#result-note').textContent=`Sorted by next milestone${missing?` · ${missing} not yet located`:''}`;
  $('#clear-region').hidden=!region;
  $('#job-list').innerHTML=jobs.length?jobs.map(j=>{const s=status(j,now);return `<button class="job-card" data-job="${esc(j.id)}" aria-label="View ${esc(j.title)} at ${esc(j.institutionName)}"><span class="place">${esc(j.city)} · ${esc(country(j.countryCode))}</span><strong>${esc(j.institutionName)}</strong><span class="title">${esc(j.title)}</span><span class="date"><i class="dot ${s.urgency} ${j.kind!=='formal-vacancy'?'outline':''}"></i>${esc(timing(j))}</span>${s.review?'<span class="badge">Needs verification</span>':''}${j.kind!=='formal-vacancy'?'<span class="badge">Expression of interest</span>':''}${j.scope!=='core'?`<span class="badge">${j.scope==='adjacent'?'Adjacent field':'Broad physics'}</span>`:''}</button>`}).join(''):'<p class="empty">No searches match these filters. Try another research area or include closed searches.</p>';
}
function renderMarkers(){
  if(!map)return;markers.clearLayers();
  const points=filtered.filter(plotReady).map(j=>{const p=location(j), xy=map.project([p.latitude,p.longitude],map.getZoom());return {x:xy.x,y:xy.y,job:j}});
  for(const c of clusterPoints(points)){
    const jobs=c.members.map(p=>p.job), allClosed=jobs.every(j=>status(j,now).closed), states=jobs.map(j=>status(j,now));
    const urgency=allClosed?'archived':['red','amber','blue','neutral'].find(u=>states.some(s=>!s.closed&&s.urgency===u))||'neutral';
    const eois=jobs.filter(j=>j.kind!=='formal-vacancy').length;
    const shape=eois===jobs.length?'eoi':eois?'mixed-kind':'';
    const count=jobs.length,size=count===1?17:Math.min(46,25+Math.log2(count)*5);
    const label=count===1?`${jobs[0].institutionName}: ${jobs[0].title}`:`${count} searches in this region`;
    const icon=L.divIcon({className:'map-marker',html:`<div class="marker-dot ${urgency} ${shape} ${allClosed?'is-closed':''} ${states.every(s=>s.review)?'is-review':''}"><span>${count>1?count:''}</span></div>`,iconSize:[size,size],iconAnchor:[size/2,size/2]});
    const marker=L.marker(map.unproject([c.x,c.y],map.getZoom()),{icon,title:label,alt:label,keyboard:true,riseOnHover:true}).addTo(markers);
    marker.getElement()?.setAttribute('aria-label',label);
    marker.bindTooltip(`<strong>${esc(count===1?jobs[0].institutionName:count+' searches')}</strong><br>${esc(count===1?timing(jobs[0]):[...new Set(jobs.map(j=>j.city))].join(' · '))}${count>1?`<br>${jobs.length-eois} advertised · ${eois} EOI<br>${states.filter(s=>!s.closed&&s.urgency==='red').length} within 7 days · ${states.filter(s=>!s.closed&&s.urgency==='amber').length} within 8–30 days<br>Click to explore`:''}`,{direction:'top',offset:[0,-size/2]});
    marker.on('click',()=>{
      if(count===1){showJob(jobs[0].id);return}
      region=new Set(jobs.map(j=>j.id));renderList();$('#job-list').scrollTop=0;
      const bounds=L.latLngBounds(jobs.map(j=>{const p=location(j);return [p.latitude,p.longitude]}));
      if(bounds.getNorthEast().distanceTo(bounds.getSouthWest())>1500&&map.getZoom()<8)map.fitBounds(bounds,{padding:[60,60],maxZoom:Math.min(8,map.getZoom()+2),animate:!matchMedia('(prefers-reduced-motion: reduce)').matches});
      $('#result-count').focus({preventScroll:true});
    });
  }
}
function fitResults(){if(!map)return;const jobs=filtered.filter(plotReady);if(jobs.length)map.fitBounds(L.latLngBounds(jobs.map(j=>{const p=location(j);return[p.latitude,p.longitude]})),{padding:[55,55],maxZoom:6,animate:false});else map.fitBounds([[-55,-170],[73,170]],{animate:false});}
function showJob(id){
 const j=catalog.jobs.find(j=>j.id===id);if(!j)return;selected=id;const i=byInst.get(j.institutionId),s=status(j,now),loc=location(j);
 $('#detail-body').innerHTML=`<p class="eyebrow">${esc(country(j.countryCode))} · ${esc(kindLabel(j.kind))}</p><h2 class="detail-title" id="detail-title">${esc(j.institutionName)}</h2><p class="detail-job">${esc(j.title)}</p>${institutionBadges(i)}${s.review?'<p class="warning">This lead needs further verification. See the notes below before relying on its dates or scope.</p>':''}${s.closed?'<p class="warning">This search is closed or its hard deadline has passed.</p>':''}${link(j.sourceUrls[0],'Read the advertisement','advert-link')}<p class="detail-summary">${esc(j.summary)}</p><div class="detail-section"><h3>Dates and application stages</h3>${j.deadlines.length?'<ul>'+j.deadlines.filter(d=>d.active!==false).map(d=>`<li><strong>${esc(dateText(d.date))}${d.time?' · '+esc(d.time):''}${d.timezone?' ('+esc(d.timezone)+')':''}</strong> — ${esc(dateKind[d.kind])}${d.stage==='national-application'?' (national application)':''}<p>${esc(d.description)}</p>${link(d.sourceUrl,'Date source')}</li>`).join('')+'</ul>':'<p>No verified application date.</p>'}${j.deadlines.some(d=>!d.timezone)?'<p class="muted">The source does not specify a timezone for every date. Confirm the exact cutoff in the advertisement.</p>':''}</div><div class="detail-section"><h3>Research and appointment</h3><p>${esc(j.fields.join(' · '))}</p><p>${esc(j.rank.join(' · '))}</p>${j.startDate?'<p>Anticipated start: '+esc(dateText(j.startDate))+'</p>':''}<p>Search scope: ${j.scope==='core'?'explicit HEP / cosmology fit':j.scope==='adjacent'?'adjacent field':'broad physics'}.</p>${j.notes.length?'<ul>'+j.notes.map(n=>`<li>${esc(n)}</li>`).join('')+'</ul>':''}</div><div class="detail-section"><h3>Evidence and location</h3><p>Last checked ${esc(dateText(j.checkedOn))}. ${esc(j.cycleEvidence)}</p><p>${esc(j.city)} · ${loc?.verification==='verified'?esc(loc.precision)+' location':'Location awaiting verification'}${loc?.sourceUrl?' · '+link(loc.sourceUrl,'Location source'):''}</p><p class="detail-source">${j.sourceUrls.map((u,n)=>link(u,'Source '+(n+1))).join(' · ')}</p>${i.officialClassifications.map(c=>'<p>'+link(c.sourceUrl,`${c.institutionName}: Carnegie ${c.year}`)+'</p>').join('')}${i.profileSourceUrl?'<p>'+link(i.profileSourceUrl,'Institution profile source')+'</p>':''}</div>`;
 const dialog=$('#detail');if(!dialog.open)dialog.showModal();dialog.scrollTop=0;const u=new URL(locationHref());u.searchParams.set('job',id);history.replaceState(null,'',u);
}
function locationHref(){return window.location.href}
function clearSelection(){selected=null;const u=new URL(locationHref());u.searchParams.delete('job');history.replaceState(null,'',u)}
$('#close-detail').addEventListener('click',()=>$('#detail').close());$('#detail').addEventListener('close',clearSelection);
$('#detail').addEventListener('click',e=>{if(e.target===$('#detail')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}});
$('#job-list').addEventListener('click',e=>{const b=e.target.closest('[data-job]');if(b)showJob(b.dataset.job)});
$('#filter-toggle').addEventListener('click',()=>{const b=$('#filter-toggle'),show=b.getAttribute('aria-expanded')!=='true';b.setAttribute('aria-expanded',show);$('#filter-options').hidden=!show;map?.invalidateSize()});
$('#filters').addEventListener('submit',e=>e.preventDefault());let searchTimer;
$('#filters').addEventListener('input',e=>{if(!catalog)return;region=null;if(e.target.id==='search'){clearTimeout(searchTimer);searchTimer=setTimeout(render,90)}else render()});
$('#filters').addEventListener('reset',()=>{clearTimeout(searchTimer);region=null;setTimeout(()=>{render();fitResults()},0)});
$('#clear-region').addEventListener('click',()=>{region=null;renderList()});$('#fit').addEventListener('click',()=>{region=null;renderList();fitResults()});
$('#directory-search').addEventListener('input',renderDirectory);
function renderDirectory(){const q=$('#directory-search').value.toLowerCase().trim();const rows=catalog.institutions.filter(i=>[i.name,i.city,country(i.countryCode)].join(' ').toLowerCase().includes(q));$('#directory-list').innerHTML=rows.length?rows.map(i=>`<article class="institution"><h3>${esc(i.name)}</h3><p>${esc(i.city)} · ${esc(country(i.countryCode))}</p>${institutionBadges(i)}<div>${i.sourceIds.map((id,n)=>{const s=dirSources.get(id);return s?link(s.url,s.kind==='department'?'Department':s.kind==='group'?'Research group':s.kind==='recruitment'?'Job board':'Vacancy source'):''}).join('')}</div><p class="source-status">${i.lastFullScan?'Source scan: '+esc(i.lastFullScan):'Complete vacancy scan pending'}</p></article>`).join(''):'<p class="empty">No institutions match.</p>'}
async function init(){
 try{
  const res=await fetch('data/catalog.json');if(!res.ok)throw Error('Catalog unavailable');catalog=await res.json();byInst=new Map(catalog.institutions.map(i=>[i.id,i]));dirSources=new Map(catalog.sources.map(s=>[s.id,s]));
  for(const [selector,values,label] of [['#field',[...new Set(catalog.jobs.flatMap(j=>j.fieldTags))].sort(),fieldLabel],['#country',[...new Set(catalog.jobs.map(j=>j.countryCode))].sort((a,b)=>country(a).localeCompare(country(b))),country]])for(const value of values){const option=new Option(label(value),value);$(selector).add(option)}
  $('#coverage').textContent=`Initial coverage · ${catalog.jobs.filter(j=>j.verification==='verified').length} verified searches, ${catalog.jobs.filter(j=>j.verification!=='verified').length} leads awaiting review · Latest evidence check ${dateText(catalog.jobs.map(j=>j.checkedOn).sort().at(-1))}. Not an exhaustive global survey.`;
  if(!window.L)throw Error('Map library unavailable');
  map=L.map('map',{minZoom:0,maxZoom:8,zoomSnap:.25,zoomDelta:.5,wheelPxPerZoomLevel:120,wheelDebounceTime:60,scrollWheelZoom:true,touchZoom:true,dragging:true,maxBounds:[[-85,-190],[85,190]],maxBoundsViscosity:.7,attributionControl:true});
  map.attributionControl.setPrefix('<a href="https://leafletjs.com/">Leaflet</a>');map.attributionControl.addAttribution('<a href="https://www.naturalearthdata.com/">Natural Earth</a>');
  markers=L.layerGroup().addTo(map);map.fitBounds([[-55,-170],[73,170]],{padding:[10,10],animate:false});map.on('zoomend',renderMarkers);
  const observer=new ResizeObserver(()=>map.invalidateSize({pan:false}));observer.observe($('#map'));
  render();renderDirectory();updateTheme();
  try{const world=await fetch('assets/world.geojson');if(!world.ok)throw Error();land=L.geoJSON(await world.json(),{style:landStyle,interactive:false}).addTo(map);land.bringToBack()}catch{const message=document.createElement('p');message.className='map-error';message.textContent='The background map could not load. Job locations and the list remain available.';$('.map-panel').append(message)}
  const id=new URL(locationHref()).searchParams.get('job');if(id)showJob(id);
  let statusKey=JSON.stringify(catalog.jobs.map(j=>status(j,now)));
  const refreshDates=()=>{now=Date.now();const nextKey=JSON.stringify(catalog.jobs.map(j=>status(j,now)));if(nextKey!==statusKey){statusKey=nextKey;render();if(selected)showJob(selected)}};
  setInterval(refreshDates,60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshDates()});
 }catch(error){$('#result-count').textContent='Unable to load the map';$('#job-list').innerHTML='<p class="empty">Please reload, or <a href="catalog.html">open the readable catalog</a>.</p>';console.error(error)}
}
init();
