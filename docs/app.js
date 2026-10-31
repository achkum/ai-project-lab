'use strict';
const $ = id => document.getElementById(id);
let data = window.LAB_SAMPLE;
let lastError = '';
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = s => String(s || 'Unknown').replaceAll('_',' ');
const when = (s,fallback) => s && Number.isFinite(Date.parse(s)) ? new Date(s).toLocaleString('en-GB',{timeZone:'Europe/Stockholm',dateStyle:'medium',timeStyle:'short'}) : fallback;
function valid(d) {
 return d && d.schema_version===1 && ['sample','live'].includes(d.mode) && typeof d.connected==='boolean' &&
 d.thesis && d.project && d.coverage && d.usage && Number.isFinite(d.releases_last_7_days) &&
 Array.isArray(d.sources) && d.sources.every(x=>typeof x.name==='string'&&typeof x.category==='string'&&typeof x.url==='string') &&
 Array.isArray(d.opportunities) && d.opportunities.every(x=>typeof x.id==='string'&&typeof x.title==='string'&&['Thesis','Project'].includes(x.lane)) &&
 Array.isArray(d.events) && (d.mode==='sample'||Number.isFinite(Date.parse(d.generated_at)));
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
 dest.innerHTML=filtered.length?filtered.map(x=>'<article class="panel opportunity"><span class="tag">'+esc(x.id)+' / '+esc(x.status)+'</span><h2>'+esc(x.title)+'</h2><p>'+esc(x.summary)+'</p><button data-detail="'+esc(x.id)+'">Inspect possibility →</button></article>').join(''):'<div class="empty">No matching opportunities. Nothing is generated to fill a quota.</div>';
}
function renderSources(){
 const q=$('source-search').value.toLowerCase(),cat=$('source-category').value;
 const rows=data.sources.filter(x=>(cat==='All categories'||x.category===cat)&&(x.name+' '+x.access).toLowerCase().includes(q));
 $('source-count').textContent=rows.length+' sources shown';
 $('source-rows').innerHTML=rows.length?rows.map(x=>'<tr><td><a href="'+esc(safeLink(x.url))+'" target="_blank" rel="noopener noreferrer">'+esc(x.name)+' ↗</a></td><td>'+esc(x.category)+'</td><td>'+esc(x.access)+'</td><td><span class="pill">'+esc(pretty(x.status))+'</span></td></tr>').join(''):'<tr><td colspan="4">No matching sources.</td></tr>';
}
function render(){
 const sample=data.mode==='sample',age=data.generated_at?Date.now()-Date.parse(data.generated_at):null,stale=!sample&&age>3600000;
 $('notice').textContent=lastError || (sample?'Sample mode · Illustrative records only. No workflow is connected.':!data.connected?'Not connected · Backend setup is incomplete.':stale?'Stale snapshot · The last update is over one hour old. Check the coordinator.':'Live snapshot · Public-safe status only. Private details stay in GitHub.');
 $('notice').classList.toggle('error',!!lastError||stale);
 $('connection').textContent=sample||!data.connected?'Not connected':stale?'Snapshot stale':'Snapshot connected';
 $('freshness').textContent=sample?'Awaiting first live snapshot':'Updated '+when(data.generated_at,'Unknown');
 const stats=[['Thesis cadence','Daily','Owner-selected interests'],['Delivery window','7 days','No fixed weekday stages'],['Source coverage',data.coverage.checked+' / '+data.coverage.target,data.coverage.registered+' candidate sources'],['Releases this week',data.releases_last_7_days,'Actual releases only']];
 $('stats').innerHTML=stats.map(([l,v,n])=>'<div class="stat"><div class="label">'+esc(l)+'</div><div class="value">'+esc(v)+'</div><div class="note">'+esc(n)+'</div></div>').join('');
 $('thesis-state').textContent=pretty(data.thesis.state);$('project-state').textContent=pretty(data.project.state);
 $('thesis-last').textContent=when(data.thesis.last_success,'Not run');$('thesis-next').textContent=when(data.thesis.next_run,'Not scheduled');
 $('project-stage').textContent=data.project.stage;$('project-target').textContent=when(data.project.target_at,'Starts with first selection');
 $('activity').innerHTML=data.events.map(x=>'<div class="event"><strong>'+esc(x.title)+'</strong><p>'+esc(x.detail)+'</p></div>').join('');
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
 $('profile-message').textContent=(saved?'Draft saved in this browser and exported.':'Exported; browser storage is unavailable.')+' VPS settings are unchanged.';
};
try{const p=JSON.parse(localStorage.getItem('lab-profile-draft'));if(p){for(const k of ['interests','domains','exclusions'])$(k).value=(p[k]||[]).join(', ');$('hours').value=p.hours_per_week??'';$('budget').value=p.monthly_budget_sek??'';}}catch{}
render();refresh();setInterval(refresh,60000);

