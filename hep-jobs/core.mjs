// Pure catalog rules shared by rendering and regression checks. Cutoffs come
// from the Python builder so timezone/DST interpretation has one authority.
export function status(job, now = Date.now()) {
  const ds = job.deadlines.filter(d => d.active !== false);
  const closes = d => d.stage === 'national-application' ? d.kind === 'hard' && d.closesOpportunity !== false : ['hard','eoi'].includes(d.kind) && d.closesStage !== false;
  const expired = ds.some(d => closes(d) && now >= Date.parse(d.cutoffAt));
  const closed = !!job.explicitClosed || expired;
  const review = job.verification !== 'verified';
  const milestones = ds.filter(d => d.stage !== 'national-application');
  const next = milestones.filter(d => now < Date.parse(d.cutoffAt)).sort((a,b)=>Date.parse(a.cutoffAt)-Date.parse(b.cutoffAt))[0] || null;
  const pastSoft = milestones.some(d => !closes(d) && now >= Date.parse(d.cutoffAt));
  const today = new Date(now).toISOString().slice(0,10);
  const days = next ? Math.round((Date.parse(next.date)-Date.parse(today))/86400000) : null;
  return { closed, review, next, pastSoft, days, eligible:!closed&&!review,
    urgency:closed?'archived':days===null?'neutral':days<=7?'red':days<=30?'amber':'blue' };
}
export function matches(job, inst, filters, now = Date.now()) {
  const s = status(job, now);
  if (!filters.closed && s.closed || !filters.review && s.review) return false;
  if (filters.q && ![job.institutionName,job.title,job.city,job.summary,...job.fields,...job.rank].join(' ').toLowerCase().includes(filters.q.toLowerCase().trim())) return false;
  if (filters.field && !job.fieldTags.includes(filters.field)) return false;
  if (filters.country && job.countryCode!==filters.country) return false;
  if (filters.scope && job.scope!==filters.scope) return false;
  if (filters.kind && (filters.kind==='formal-vacancy' ? job.kind!=='formal-vacancy' : job.kind==='formal-vacancy')) return false;
  if (filters.profile) {
    const cs=inst.officialClassifications.map(c=>c.designation || 'no-designation');
    if (['R1','R2','RCU'].includes(filters.profile) && !cs.includes(filters.profile)) return false;
    if (filters.profile==='no-designation' && (inst.countryCode!=='US'||!cs.some(c=>!['R1','R2','RCU'].includes(c)))) return false;
    if (['international-university','research-institute'].includes(filters.profile) && inst.profileCategory!==filters.profile) return false;
  }
  if (filters.due==='none' && s.next) return false;
  if (filters.due && filters.due!=='none' && (!s.next||s.closed||s.days>Number(filters.due))) return false;
  return true;
}
export function sortJobs(jobs, now = Date.now()) {
  return [...jobs].sort((a,b)=>{
    const x=status(a,now), y=status(b,now);
    return Number(x.closed)-Number(y.closed) || Number(x.review)-Number(y.review) ||
      (x.next ? Date.parse(x.next.cutoffAt):Infinity)-(y.next?Date.parse(y.next.cutoffAt):Infinity) || a.institutionName.localeCompare(b.institutionName) || a.id.localeCompare(b.id);
  });
}
// Stable world-pixel grid, independent of pan offset. Union nearby points to
// keep densely overlapping clusters clickable; positions never modify data.
export function clusterPoints(points, distance=42) {
  const parent=points.map((_,i)=>i), buckets=new Map();
  const find=i=>{while(parent[i]!==i){parent[i]=parent[parent[i]];i=parent[i]}return i};
  points.forEach((p,i)=>{
    const gx=Math.floor(p.x/distance),gy=Math.floor(p.y/distance);
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++) {
      for(const j of buckets.get(`${gx+dx},${gy+dy}`)||[]) if(Math.hypot(p.x-points[j].x,p.y-points[j].y)<distance) parent[find(i)]=find(j);
    }
    const key=`${gx},${gy}`;if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(i);
  });
  const groups=new Map();points.forEach((p,i)=>{const key=find(i);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p)});
  return [...groups.values()].map(members=>({members,x:members.reduce((a,p)=>a+p.x,0)/members.length,y:members.reduce((a,p)=>a+p.y,0)/members.length}));
}
