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
 Array.isArray(d.opportunities) && d.opportunities.every(x=>strings(x,['id','title','lane','status','summary','contribution','feasibility','venture','next','evidence'])&&['Thesis','Project'].includes(x.lane)&&
 (x.flow===undefined||(Array.isArray(x.flow)&&x.flow.every(s=>typeof s==='string')))&&
 (x.provenance===undefined||(Array.isArray(x.provenance)&&x.provenance.every(s=>strings(s,['title','url','kind','finding']))))) &&
 Array.isArray(d.events) && d.events.every(x=>strings(x,['title','detail'])) &&
 (d.decisions===undefined||(Array.isArray(d.decisions)&&d.decisions.every(x=>strings(x,['id','lane','state','url','recommended'])&&['thesis','project'].includes(x.lane)&&date(x.deadline)&&decisionLink(x.url)!=='#'))) &&

 (d.mode==='sample'?d.connected===false:typeof d.generated_at==='string'&&Number.isFinite(Date.parse(d.generated_at))));
}
function decisionLink(value) { return /^https:\/\/github\.com\/achkum\/ai-thesis-lab\/issues\/[1-9][0-9]*$/.test(value) ? value : '#'; }
function renderDecisions(lane) {
 const rows=(data.decisions||[]).filter(x=>(!lane||x.lane===lane)&&data.opportunities.some(c=>c.shortlist===x.id));
 return rows.map(d=>{
 const c=data.opportunities.find(x=>x.id===(d.selected||d.recommended)&&x.shortlist===d.id);
 return '<article class="decision-summary"><span class="tag">'+esc(d.lane)+' · '+esc(pretty(d.state))+'</span><h3>'+esc(c?.title||d.id)+'</h3><p>'+(d.selected?'Selected for the manual run.': 'Recommendation ready. Review until '+esc(when(d.deadline,'not set'))+'.')+'</p><a class="text-link" href="#'+(d.lane==='project'?'projects':'thesis')+'">Explore the options →</a></article>';
 }).join('')||'<p class="muted">Discovery is collecting the next set of possibilities.</p>';
}
function ideaFlow(x) {
 return '<ol class="idea-flow">'+(x.flow||[]).map((s,i)=>'<li><span>'+String(i+1).padStart(2,'0')+'</span><p>'+esc(s)+'</p></li>').join('')+'</ol>';
}
function presentIdea(x){
 const copy=data.opportunity_copy?.[x.id];
 if(!copy)return x;
 const view={...x,technical:x};
 const fields=['title','summary','why_it_matters','proposed_fix','example','flow','deliverable','contribution','question','measure','audience','effort','market','feasibility','next','risk','venture','customer_test','week_test','reason'];
 for(const field of fields)if(copy[field]!==undefined)view[field]=copy[field];
 return view;
}
function sourcePreview(x){
 const s=(x.provenance||[])[0];
 return s?'<div class="source-preview"><span class="label">PROBLEM / EVIDENCE SOURCE</span><a href="'+esc(safeLink(s.url))+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+' ↗</a><small>'+esc(s.kind)+' · '+esc(s.published_at||'Date unknown')+' · Novelty unverified</small></div>':'';
}
function provenanceDetails(x){
 return '<section class="provenance-panel"><h3>Where this idea came from</h3>'+(x.provenance||[]).map(s=>'<article><span class="tag">'+esc(s.kind)+'</span><a class="text-link" href="'+esc(safeLink(s.url))+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+' ↗</a><p>'+esc(s.finding)+'</p><small>Published: '+esc(s.published_at||'Unknown')+' · Checked: '+esc(s.verified_at||'Not recorded')+'</small><p>Read scope: '+esc(s.read_scope||'Not recorded')+'</p></article>').join('')+'<h3>What already exists</h3><p>'+esc(x.baseline||x.alternative)+'</p><h3>What we propose to add or test</h3><p>'+esc(x.proposed_difference||x.question)+'</p><p class="originality-note">'+esc(x.originality||'Novelty has not been established.')+'</p></section>';
}
function outcomeSummary(x) {
 const pairs=x.investigation_result ? [['Investigation result',x.investigation_result],['What was done',x.completed_work],['What we found',x.finding],['What is still needed',x.remaining_work]] : [];
 return pairs.length?'<div class="idea-outcome"><p><strong>'+esc(pairs[0][0])+': </strong>'+esc(pairs[0][1])+'</p><details><summary>What the investigation found</summary>'+pairs.slice(1).map(([k,v])=>'<p><strong>'+esc(k)+': </strong>'+esc(v)+'</p>').join('')+'<a class="text-link" href="'+esc(safeLink(x.artifact_url))+'" target="_blank" rel="noopener noreferrer">Read the full investigation ↗</a></details></div>':'';
}
function ideaCard(x) {
 const thesis=x.lane==='Thesis';
 const facts=thesis?[['What we would find out',x.question],['Main difficulty',x.risk]]:[['Who could pay',x.buyer||x.audience],['Why they would return',x.business_case?.repeat_use||x.market||'Not established']];
 const badge=x.status==='completed'?'Completed prototype':x.investigation_result?'Investigated — see findings':thesis?'Research idea':'Business hypothesis';
 return '<article class="idea-card '+(x.selected?'chosen':'')+'">'+(typeof selectionControl==='function'?selectionControl(x):'')+'<div class="idea-top"><span class="tag">'+esc(x.domain||x.lane)+'</span><span class="idea-badge">'+badge+'</span></div><h2>'+esc(x.title)+'</h2><p class="idea-intro">'+esc(x.summary)+'</p>'+outcomeSummary(x)+ideaFlow(x)+'<div class="idea-outcome"><span class="label">WHAT YOU GET</span><strong>'+esc(x.deliverable||'To assess')+'</strong></div><div class="idea-facts">'+facts.map(([label,value])=>'<div><span class="label">'+esc(label)+'</span><strong>'+esc(value)+'</strong></div>').join('')+'</div>'+sourcePreview(x)+'<p class="idea-audience"><span>For</span> '+esc(x.audience||'To investigate')+'</p><button class="idea-open" data-detail="'+esc(x.id)+'">'+(thesis?'Explain ':'Explore ')+esc(x.id)+' →</button></article>';
}
function comparison(rows) {
 const fields=rows[0]?.lane==='Thesis'?[['Who it helps','audience'],['What we would test','question'],['What you would produce','deliverable'],['Main difficulty','risk']]:[['First customer','audience'],['Working first version','deliverable'],['Why someone would pay','buyer'],['Demand test','customer_test'],['Main risk','risk']];
 return '<section class="comparison"><div class="section-title"><h2>Compare at a glance</h2><span class="tag">No invented scores</span></div><div class="table-wrap"><table><thead><tr><th>Consideration</th>'+rows.map(x=>'<th>'+esc(x.id)+' · '+esc(x.domain)+'</th>').join('')+'</tr></thead><tbody>'+fields.map(([label,key])=>'<tr><th scope="row">'+label+'</th>'+rows.map(x=>'<td>'+esc(x[key]||'To assess')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></section>';
}
function businessDetails(x){
 const b=x.business_case;
 const grid=items=>'<div class="detail-grid">'+items.filter(([,v])=>v).map(([k,v])=>'<section><h3>'+esc(k)+'</h3><p>'+esc(v)+'</p></section>').join('')+'</div>';
 return '<span class="tag">'+esc(x.id)+' / Business hypothesis · '+esc(x.assessment)+'</span><h2>'+esc(x.title)+'</h2>'+grid([
  ['What goes wrong?',x.summary],['Who has this problem?',x.audience],['A concrete example',x.example],['What would we build?',x.proposed_fix],['Why might someone pay?',x.buyer],['Working first version',x.deliverable]
 ])+ideaFlow(x)+'<p class="callout">'+esc(x.evidence_level)+' '+esc(x.risk)+'</p><details class="evidence-details"><summary>The business: alternatives, repeat use and how to test demand</summary>'+grid([
  ['A specific first customer',b.first_customer],['Why they would return',b.repeat_use],['Existing alternatives',b.current_alternatives],['Our proposed difference',b.proposed_difference],['How to find the first customers',b.first_customer_route],['A cheap reason to stop',b.kill_test],['Beyond the first week',b.next_90_days],['Costs and support',b.costs]
 ])+'</details><details class="evidence-details"><summary>The first build: workflow, acceptance checks and data</summary>'+grid([
  ['Complete first-week workflow',b.week_one],['How we check it works',b.week_one_acceptance],['Data we can actually use',b.data_access],['Model approach',x.model_plan],['Why use a model?',x.why_ml],['Where it runs',x.technical_scope]
 ])+'</details><details class="evidence-details"><summary>Sources, dates and what is still unproven</summary>'+provenanceDetails(x)+'<p>'+esc(x.evidence)+'</p></details>'+(typeof singleJobAction==='function'?singleJobAction(x):'')+'<div class="discussion-actions"><button data-conversation="ask" data-lane="project" data-idea="'+esc(x.id)+'">Ask about this idea</button><button data-conversation="refine" data-lane="project" data-idea="'+esc(x.id)+'">Refine this direction</button></div>';
}
function safeLink(value) { try { const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'#'; } catch{return '#';} }
function showView(){
 const key=location.hash.slice(1);const v=['overview','thesis','projects','sources','setup'].includes(key)?key:'overview';
 document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!=='view-'+v);
 document.querySelectorAll('nav a').forEach(el=>{el.classList.toggle('active',el.dataset.view===v);if(el.dataset.view===v)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
 const meta={overview:['TWO LANES. ONE WORKSPACE.','A clear view of your next move.','Daily research, continuous building. Progress without opening a terminal.'],thesis:['01 / THESIS DISCOVERY','Find a problem worth studying.','What goes wrong, what you could try and what you would find out.'],projects:['02 / PROJECT STUDIO','Build towards a business.','A customer, a recurring problem and a working first version.'],sources:['DISCOVERY NETWORK','Look beyond your usual sources.','Research, communities, engineering and real-world problems.'],setup:['YOUR LAB, YOUR DIRECTION','Set the boundaries.','Choose your interests and prepare the machines for autonomous work.']};
 [$('eyebrow').textContent,$('title').textContent,$('subtitle').textContent]=meta[v];
}
function openConversation(mode,lane,id) {
 const x=data.opportunities.find(c=>c.id===id);
 const heading=mode==='new'?'Explore different directions':mode==='refine'?'Shape this idea with the agent':'Ask about this idea';
 const context=x?x.id+' — '+x.title:lane+' possibilities';
 $('detail-content').innerHTML='<span class="tag">ON DEMAND · NO NEED TO WAIT</span><h2>'+heading+'</h2><p>'+esc(context)+'</p><div class="conversation-note">This prepares a message for our Codex chat. It does not call a model or change your selection from this page.</div><label for="agent-question">What would you like to change or understand?</label><textarea id="agent-question" rows="4" placeholder="'+(mode==='new'?'For example: explore food-industry operations, avoid another generic tracking app.':mode==='refine'?'For example: make the first version useful to a small restaurant.':'For example: who would pay for this, and what already solves it?')+'"></textarea><div class="question-suggestions"><button data-suggest="Who would use this, and what evidence suggests they need it?">Who needs it?</button><button data-suggest="What already exists, and what would make this meaningfully different?">Is this already solved?</button><button data-suggest="Show a concrete example of the user experience.">Show me an example</button></div><label for="preference-duration">How should this affect future discovery?</label><select id="preference-duration"><option value="once">This discussion only</option><option value="persistent">Remember as a discovery preference</option></select><p class="muted">Questions leave the current selection unchanged. A replacement request pauses affected work before the direction changes.</p><button class="primary" id="prepare-agent-message">Prepare message</button><div id="agent-message-area" hidden><label for="agent-message">Message to send in our Codex chat</label><textarea id="agent-message" rows="7" readonly></textarea><button id="copy-agent-message">Copy message</button><p id="agent-copy-status" role="status">Paste it into this chat to start immediately. Nothing has been sent yet.</p></div>';
 $('prepare-agent-message').onclick=()=>{
 const q=$('agent-question').value.trim();
 const persistence=$('preference-duration').value==='persistent'?'Remember my stated interests as editable ranking preferences, while keeping broad discovery.':'Apply this request only to this discussion; do not change my long-term discovery preferences.';
 const instruction=mode==='new'?'I want a fresh set of '+lane+' options now. Research 3–5 additional alternatives and update the visual dashboard before building. Preserve all existing jobs unless I explicitly request replacing or cancelling one.':mode==='refine'?'Refine '+context+' now. Preserve existing work and show the revised scope on the dashboard before continuing implementation.':'Explain '+context+' now. This is a question, not a selection change or approval to build.';
 $('agent-message').value=instruction+'\n\n'+(q||'Help me assess the problem, potential outcome, existing alternatives, feasibility and market uncertainty.')+'\n\n'+persistence;
 $('agent-message-area').hidden=false;
 };
 $('copy-agent-message').onclick=async()=>{
 try{await navigator.clipboard.writeText($('agent-message').value);$('agent-copy-status').textContent='Copied. Paste into this Codex chat and send to start now.';}catch{$('agent-copy-status').textContent='Select and copy the message above, then paste it into this chat.';}
 };
 $('detail').showModal();
}
function renderCards(lane,query=''){
 const rows=data.opportunities.map(presentIdea).filter(x=>x.lane===lane&&(x.title+' '+x.summary+' '+(x.domain||'')).toLowerCase().includes(query.toLowerCase()));
 const dest=$(lane==='Thesis'?'thesis-cards':'project-cards');
 const chosen=rows.find(x=>x.selected),recommended=rows.find(x=>x.recommended);
 const focus=data.audit?.hold?null:chosen||recommended;
 const intro=focus?'<div class="lane-focus"><div><span class="tag">'+(chosen?'YOUR CURRENT DIRECTION':'OUR RECOMMENDATION')+'</span><p><strong>'+esc(focus.id)+'</strong> · '+esc(focus.reason||focus.title)+'</p></div><span class="pill">'+(chosen?esc(pretty(focus.status)):'Ready to review')+'</span></div>':'';
 const conversation='<div class="explore-again"><div><strong>Not your direction?</strong><p>Question the recommendation, change the angle or explore a fresh set now.</p></div><button data-conversation="new" data-lane="'+lane.toLowerCase()+'">Find different ideas →</button></div>';
 const signals=data.discovery_signals;
 const radar=signals?'<details class="provenance-panel"><summary><strong>What is getting attention now · GitHub & LinkedIn · '+esc(signals.checked_at)+'</strong></summary><p>'+esc(signals.scope)+'</p><div class="detail-grid">'+signals.items.map(s=>'<section><span class="tag">'+esc(s.source)+'</span><h3><a href="'+esc(safeLink(s.url))+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+' ↗</a></h3><p>'+esc(s.signal)+'</p><p><strong>Possible direction: </strong>'+esc(s.possibility)+'</p><p><strong>Still unknown: </strong>'+esc(s.limit)+'</p></section>').join('')+'</div></details>':'';
 const run=data.discovery_run;
 const research=run?'<div class="lane-focus"><div><span class="tag">DISCOVERY · '+esc(pretty(run.lane_states?.[lane]||run.state))+'</span><p>'+esc(run.lane_notes?.[lane]||run.note)+'</p></div></div>':'';
 const reviewed=lane==='Project'&&run?.reviewed_directions?.length?'<details class="provenance-panel"><summary><strong>What the replacement review found</strong></summary><p>These are research findings, not a new build shortlist. Existing competitors do not rule out a business; we still need a concrete reason a customer would choose us.</p><div class="detail-grid">'+run.reviewed_directions.map(r=>'<section><span class="tag">'+esc(r.verdict)+'</span><h3>'+esc(r.title)+'</h3><p>'+esc(r.problem)+'</p><p><strong>Why it was not shortlisted: </strong>'+esc(r.finding)+'</p><a class="text-link" href="'+esc(safeLink(r.source_url))+'" target="_blank" rel="noopener noreferrer">'+esc(r.source_label)+' ↗</a></section>').join('')+'</div></details>':'';
 const empty=lane==='Project'&&!query?'No replacement business shortlist is ready. The rejected small tools are archived; previous builds and their files remain available.':'No matching ideas. Try another search.';
 dest.innerHTML=research+(typeof jobControls==='function'?jobControls(lane):'')+conversation+reviewed+radar+(rows.length?intro+'<div class="idea-grid">'+rows.map(ideaCard).join('')+'</div>'+comparison(rows):'<div class="empty">'+empty+'</div>');
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
 if(typeof redrawJobs==='function')redrawJobs();else{renderCards('Thesis',$('thesis-search').value);renderCards('Project');}renderSources();showView();
}
async function refresh(){
 $('refresh').disabled=true;
 try {
  if(location.protocol==='file:'){lastError='Local sample preview · Serve over HTTP or open GitHub Pages to fetch snapshots.';}
  else {const r=await fetch('data/status.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const next=await r.json();if(!valid(next))throw Error('Invalid status schema');data=next;lastError='';}
 }catch(e){lastError='Snapshot update failed ('+e.message+'). '+(data.mode==='sample'?'Showing labelled sample data; no live connection.':'Retaining the last snapshot; check its age.');}
 finally{render();$('refresh').disabled=false;}
}
document.addEventListener('click',async e=>{
 const convo=e.target.closest('[data-conversation]');
 if(convo){openConversation(convo.dataset.conversation,convo.dataset.lane,convo.dataset.idea);return;}
 const suggestion=e.target.closest('[data-suggest]');
 if(suggestion){$('agent-question').value=suggestion.dataset.suggest;return;}
 const copy=e.target.closest('[data-copy-choice]');
 if(copy){
  const x=data.opportunities.find(x=>x.id===copy.dataset.copyChoice);if(!x)return;
  const command='/lab select '+x.shortlist+' v'+x.version+' '+x.id;
  try{await navigator.clipboard.writeText(command);copy.textContent='Copied — paste in the private decision thread';}
  catch{copy.textContent='Copy this: '+command;}
  return;
 }
 const b=e.target.closest('[data-detail]');if(!b)return;
 const original=data.opportunities.find(x=>x.id===b.dataset.detail);if(!original)return;
 const x=presentIdea(original);
 if(x.lane==='Project'&&x.business_case){$('detail-content').innerHTML=businessDetails(x);$('detail').showModal();return;}
 if(x.lane==='Thesis'){
   const sections=[['What goes wrong?',x.summary],['Why does this matter?',x.why_it_matters||x.reason],['A simple example',x.example],['What would we try?',x.proposed_fix],['What would the thesis test?',x.question],['What would you produce?',x.deliverable],['What is the main difficulty?',x.risk]];
   const details=[['Methods to compare',original.model_plan],['How to measure the result',original.measure],['Data and permission to use it',original.data_plan],['The first experiment',original.week_test],['Closest existing work',original.baseline],['What this study might add',original.proposed_difference]];
   const grid=items=>'<div class="detail-grid">'+items.filter(([,v])=>v).map(([k,v])=>'<section><h3>'+esc(k)+'</h3><p>'+esc(v)+'</p></section>').join('')+'</div>';
   $('detail-content').innerHTML='<span class="tag">'+esc(x.id)+' / Thesis idea</span><h2>'+esc(x.title)+'</h2>'+grid(sections)+ideaFlow(x)+outcomeSummary(x)+'<details class="evidence-details"><summary>Research methods and data — optional detail</summary>'+grid(details)+'</details><details class="evidence-details"><summary>Sources, dates and what already exists</summary>'+provenanceDetails(original)+'</details>'+(typeof singleJobAction==='function'?singleJobAction(x):'')+'<div class="discussion-actions"><button data-conversation="ask" data-lane="thesis" data-idea="'+esc(x.id)+'">Ask about this idea</button></div>';
   $('detail').showModal();return;
 }
 $('detail-content').innerHTML='<span class="tag">'+esc(x.id)+' / '+esc(x.domain||x.lane)+'</span><h2>'+esc(x.title)+'</h2><p class="detail-lead">'+esc(x.summary)+'</p>'+outcomeSummary(x)+sourcePreview(x)+ideaFlow(x)+'<div class="detail-grid">'+[
 ['The problem',x.summary],['Why it matters',x.why_it_matters||x.reason],['What we would build',x.proposed_fix||x.deliverable],['A concrete example',x.example||x.flow?.join(' → ')],['The question worth testing',x.question||x.summary],
 ...(x.buyer?[["Who could pay",x.buyer],["One-week product test",x.week_test],["How to test customer demand",x.customer_test],["Path beyond week one",x.growth_path]]:[]),
 ...(x.model_plan?[['Model approach',x.model_plan],['Why ML here?',x.why_ml],['Data access & evaluation inputs',x.data_plan]]:[]),
 ['What success would look like',x.measure||x.contribution],
 ['Who might use it—and why',x.venture],
 ['Why consider this option',x.reason||x.feasibility],
 ['What could make us drop it',x.risk||x.feasibility]
 ].map(([k,v])=>'<section><h3>'+esc(k)+'</h3><p>'+esc(v)+'</p></section>').join('')+'</div>'+provenanceDetails(x)+'<div class="next-step"><span class="tag">BOUNDED NEXT STEP · '+esc(x.effort||'TO ASSESS')+'</span><p>'+esc(x.next)+'</p><p class="muted">'+esc(x.feasibility)+'</p></div><details class="evidence-details"><summary>Evidence & uncertainty</summary><p>'+esc(x.evidence)+'</p>'+(x.evidence_url?'<a class="text-link" href="'+esc(safeLink(x.evidence_url))+'" target="_blank" rel="noopener noreferrer">Read the original source ↗</a>':'')+'</details>'+(typeof singleJobAction==='function'?singleJobAction(x):'');
 $('detail-content').insertAdjacentHTML('beforeend','<div class="discussion-actions"><button data-conversation="ask" data-lane="'+x.lane.toLowerCase()+'" data-idea="'+esc(x.id)+'">Ask about this idea</button><button data-conversation="refine" data-lane="'+x.lane.toLowerCase()+'" data-idea="'+esc(x.id)+'">Refine this direction</button></div>');
 $('detail').showModal();
});
$('close-detail').onclick=()=>$('detail').close();
$('refresh').onclick=refresh;
$('thesis-search').oninput=()=>renderCards('Thesis',$('thesis-search').value);
$('source-search').oninput=renderSources;$('source-category').onchange=renderSources;
window.addEventListener('hashchange',showView);
function list(id){return $(id).value.split(/[,;\n]/).map(x=>x.trim()).filter(Boolean);}
$('profile-form').onsubmit=e=>{
 e.preventDefault();const p={schema_version:1,timezone:'Europe/Stockholm',interests:list('interests'),domains:list('domains'),exclusions:list('exclusions'),hours_per_week:$('hours').value===''?null:Number($('hours').value),monthly_budget_sek:0,setup_complete:false};
 let saved=true;try{localStorage.setItem('lab-profile-draft',JSON.stringify(p));}catch{saved=false;}
 const blob=new Blob([JSON.stringify(p,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='profile.draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 $('profile-message').textContent=(saved?'Draft saved in this browser and exported.':'Exported; browser storage is unavailable.')+' Workflow settings are unchanged; apply the draft through the private coordinator.';
};
try{const p=JSON.parse(localStorage.getItem('lab-profile-draft'));if(p){for(const k of ['interests','domains','exclusions'])$(k).value=(p[k]||[]).join(', ');$('hours').value=p.hours_per_week??'';}}catch{}
$('budget').value=0;
render();refresh();setInterval(refresh,60000);

