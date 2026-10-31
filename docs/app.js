'use strict';
const $ = id => document.getElementById(id);
let data = window.LAB_SAMPLE;
let lastError = '';
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = s => String(s || 'Unknown').replaceAll('_',' ');
const when = (s,fallback) => s && Number.isFinite(Date.parse(s)) ? new Date(s).toLocaleString('en-GB',{timeZone:'Europe/Stockholm',dateStyle:'medium',timeStyle:'short'}) : fallback;
function valid(d) {
 const obj=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
 const strings=(x,keys)=>obj(x)&&keys.every(k=>typeof x[k]==='string');
 const count=x=>Number.isInteger(x)&&x>=0;
 const date=x=>x===null||(typeof x==='string'&&Number.isFinite(Date.parse(x)));
 return !!(obj(d) && d.schema_version===1 && ['sample','live'].includes(d.mode) && typeof d.connected==='boolean' &&
 strings(d.thesis,['state']) && date(d.thesis.last_success) && date(d.thesis.next_run) &&
 strings(d.project,['state','stage']) && date(d.project.window_start) && date(d.project.target_at) &&
 obj(d.coverage) && ['checked','target','registered','blocked'].every(k=>count(d.coverage[k])) &&
 obj(d.usage) && ['spent_sek','limit_sek'].every(k=>d.usage[k]===null||(Number.isFinite(d.usage[k])&&d.usage[k]>=0)) && count(d.releases_last_7_days) &&
 Array.isArray(d.sources) && d.sources.every(x=>strings(x,['id','name','category','url','access','status'])) &&
 Array.isArray(d.opportunities) && d.opportunities.every(x=>strings(x,['id','title','lane','status','summary','contribution','feasibility','venture','next','evidence'])&&['Thesis','Project'].includes(x.lane)) &&
 Array.isArray(d.events) && d.events.every(x=>strings(x,['title','detail'])) &&
 (d.decisions===undefined||(Array.isArray(d.decisions)&&d.decisions.every(x=>strings(x,['id','lane','state','url','recommended'])&&['thesis','project'].includes(x.lane)&&date(x.deadline)&&decisionLink(x.url)!=='#'))) &&

 (d.mode==='sample'?d.connected===false:typeof d.generated_at==='string'&&Number.isFinite(Date.parse(d.generated_at))));
}
function decisionLink(value) { return /^https:\/\/github\.com\/achkum\/ai-thesis-lab\/issues\/[1-9][0-9]*$/.test(value) ? value : '#'; }
function renderDecisions(lane) {
 const rows=(data.decisions||[]).filter(x=>!lane||x.lane===lane);
 return rows.length?rows.map(x=>'<article class="panel"><span class="tag">'+esc(x.lane)+' / '+esc(pretty(x.state))+'</span><h2>'+esc(x.id)+'</h2><p>Recommended: '+esc(x.recommended)+'. '+(x.selected?'Selected: '+esc(x.selected)+' ('+esc(pretty(x.selection_origin))+').':'Choose an option or hold the shortlist.')+'</p><p>Review deadline: <strong>'+esc(when(x.deadline,'Not published'))+'</strong> · Stockholm</p><p>No response selects the recommendation on the next successful check after the deadline.</p><a class="button primary" href="'+esc(decisionLink(x.url))+'" target="_blank" rel="noopener noreferrer">Review options & choose privately ↗</a></article>').join(''):'<div class="empty">No shortlist awaiting review. Discovery continues across domains.</div>';
}
function safeLink(value) { try { const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'#'; } catch{return '#';} }
function showView(){
 const key=location.hash.slice(1);const v=['overview','thesis','projects','sources','setup'].includes(key)?key:'overview';
 document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!=='view-'+v);
 document.querySelectorAll('nav a').forEach(el=>{el.classList.toggle('active',el.dataset.view===v);if(el.dataset.view===v)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
 const meta={overview:['TWO LANES. ONE WORKSPACE.','A clear view of your next move.','Daily research, continuous building. Progress without opening a terminal.'],thesis:['01 / THESIS DISCOVERY','Follow the evidence.','Achievable Applied AI questions, shaped by your interests.'],projects:['02 / PROJECT STUDIO','Build something worth sharing.','Flexible stages. Small releases. Useful feedback.'],sources:['DISCOVERY NETWORK','Look beyond your usual sources.','Research, communities, engineering and real-world problems.'],setup:['YOUR LAB, YOUR DIRECTION','Set the boundaries.','Choose your interests and prepare the machines for autonomous work.']};
 [$('eyebrow').textContent,$('title').textContent,$('subtitle').textContent]=meta[v];
}
function renderCards(lane,query=''){
 const filtered=data.opportunities.filter(x=>x.lane===lane&&(x.title+' '+x.summary).toLowerCase().includes(query.toLowerCase()));
 const dest=$(lane==='Thesis'?'thesis-cards':'project-cards');
 dest.innerHTML=renderDecisions(lane.toLowerCase())+(filtered.length?filtered.map(x=>'<article class="panel opportunity"><span class="tag">'+esc(x.id)+' / '+esc(x.status)+'</span><h2>'+esc(x.title)+'</h2><p>'+esc(x.summary)+'</p><button data-detail="'+esc(x.id)+'">Inspect possibility →</button></article>').join(''):'<div class="empty">No matching opportunities. Nothing is generated to fill a quota.</div>');
}
function renderSources(){
 const q=$('source-search').value.toLowerCase(),cat=$('source-category').value;
 const rows=data.sources.filter(x=>(cat==='All categories'||x.category===cat)&&(x.name+' '+x.access).toLowerCase().includes(q));
 $('source-count').textContent=rows.length+' sources shown';
 $('source-rows').innerHTML=rows.length?rows.map(x=>'<tr><td><a href="'+esc(safeLink(x.url))+'" target="_blank" rel="noopener noreferrer">'+esc(x.name)+' ↗</a></td><td>'+esc(x.category)+'</td><td>'+esc(x.access)+'</td><td><span class="pill">'+esc(pretty(x.status))+'</span></td></tr>').join(''):'<tr><td colspan="4">No matching sources.</td></tr>';
}
function render(){
 const sample=data.mode==='sample',age=data.generated_at?Date.now()-Date.parse(data.generated_at):null,stale=!sample&&age>10800000;
 $('notice').textContent=lastError || (sample?'Sample mode · Illustrative records only. No workflow is connected.':!data.connected?'Not connected · Backend setup is incomplete.':stale?'Stale snapshot · The last update is over three hours old. Check the coordinator.':'Live snapshot · Public-safe status only. Private details stay in GitHub.');
 $('notice').classList.toggle('error',!!lastError||stale);
 $('connection').textContent=sample||!data.connected?'Not connected':stale?'Snapshot stale':'Snapshot connected';
 $('freshness').textContent=sample?'Awaiting first live snapshot':'Updated '+when(data.generated_at,'Unknown');
 const stats=[['Thesis cadence','Daily','Broad discovery, personalised ranking'],['Delivery window','7 days','No fixed weekday stages'],['Source coverage',data.coverage.checked+' / '+data.coverage.target,data.coverage.registered+' channels · '+(data.coverage.source_families??'—')+' source families'],['Releases this week',data.releases_last_7_days,'Actual releases only']];
 $('stats').innerHTML=stats.map(([l,v,n])=>'<div class="stat"><div class="label">'+esc(l)+'</div><div class="value">'+esc(v)+'</div><div class="note">'+esc(n)+'</div></div>').join('');
 $('thesis-state').textContent=pretty(data.thesis.state);$('project-state').textContent=pretty(data.project.state);
 $('thesis-last').textContent=when(data.thesis.last_success,'Not run');$('thesis-next').textContent=when(data.thesis.next_run,'Not scheduled');
 $('project-stage').textContent=data.project.stage;$('project-target').textContent=when(data.project.target_at,'Starts with first selection');
 $('activity').innerHTML=data.events.map(x=>'<div class="event"><strong>'+esc(x.title)+'</strong><p>'+esc(x.detail)+'</p></div>').join('');
 $('decision-list').innerHTML=renderDecisions();
 $('source-notice').textContent=data.mode==='sample'?'Sample source catalogue. No checks represented.':data.coverage.checked+' channels returned records across '+data.coverage.source_families+' independent source families in seven days. Empty channels do not count as successful coverage. Source breadth is not proof of demand.';
 renderCards('Thesis',$('thesis-search').value);renderCards('Project');renderSources();showView();
}
async function refresh(){
 $('refresh').disabled=true;
 try {
  if(location.protocol==='file:'){lastError='Local sample preview · Serve over HTTP or open GitHub Pages to fetch snapshots.';}
  else {const r=await fetch('data/status.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const next=await r.json();if(!valid(next))throw Error('Invalid status schema');data=next;lastError='';}
 }catch(e){lastError='Snapshot update failed ('+e.message+'). '+(data.mode==='sample'?'Showing labelled sample data; no live connection.':'Retaining the last snapshot; check its age.');}
 finally{render();$('refresh').disabled=false;}
}
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-detail]');if(!b)return;
 const x=data.opportunities.find(x=>x.id===b.dataset.detail);if(!x)return;
 $('detail-content').innerHTML='<span class="tag">'+esc(x.lane)+' / '+esc(x.status)+'</span><h2>'+esc(x.title)+'</h2>'+[['Problem',x.summary],['Possible contribution',x.contribution],['Feasibility',x.feasibility],['Venture hypothesis',x.venture],['Evidence status',x.evidence],['Next investigation',x.next]].map(([k,v])=>'<h3>'+esc(k)+'</h3><p>'+esc(v)+'</p>').join('');
 $('detail').showModal();
});
$('close-detail').onclick=()=>$('detail').close();
$('refresh').onclick=refresh;
$('thesis-search').oninput=()=>renderCards('Thesis',$('thesis-search').value);
$('source-search').oninput=renderSources;$('source-category').onchange=renderSources;
window.addEventListener('hashchange',showView);
function list(id){return $(id).value.split(/[,;\n]/).map(x=>x.trim()).filter(Boolean);}
$('profile-form').onsubmit=e=>{
 e.preventDefault();const p={schema_version:1,timezone:'Europe/Stockholm',interests:list('interests'),domains:list('domains'),exclusions:list('exclusions'),hours_per_week:$('hours').value===''?null:Number($('hours').value),monthly_budget_sek:$('budget').value===''?null:Number($('budget').value),setup_complete:false};
 let saved=true;try{localStorage.setItem('lab-profile-draft',JSON.stringify(p));}catch{saved=false;}
 const blob=new Blob([JSON.stringify(p,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='profile.draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 $('profile-message').textContent=(saved?'Draft saved in this browser and exported.':'Exported; browser storage is unavailable.')+' Workflow settings are unchanged; apply the draft through the private coordinator.';
};
try{const p=JSON.parse(localStorage.getItem('lab-profile-draft'));if(p){for(const k of ['interests','domains','exclusions'])$(k).value=(p[k]||[]).join(', ');$('hours').value=p.hours_per_week??'';$('budget').value=p.monthly_budget_sek??'';}}catch{}
render();refresh();setInterval(refresh,60000);

