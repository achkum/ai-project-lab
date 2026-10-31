'use strict';
const QUEUE_API='https://198.44.116.159.sslip.io';
const selectedIdeas=new Set();
let liveJobs=[],workerInfo=null,queueError='',sending=false,lastQueueSignature='';
let dashboardKey='';try{dashboardKey=sessionStorage.getItem('lab-dashboard-key')||'';}catch{}
function selectionControl(x){
 return '<label class="select-idea"><input type="checkbox" data-select-idea="'+esc(x.id)+'" '+(selectedIdeas.has(x.id)?'checked':'')+'> Select '+esc(x.id)+' <span>'+esc(x.batch==='applied-ai'?'New · applied AI':'Earlier option')+'</span></label>';
}
function jobControls(lane){
 const count=data.opportunities.filter(x=>x.lane===lane&&selectedIdeas.has(x.id)).length;
 const jobs=liveJobs.filter(x=>x.lane===lane.toLowerCase());
 return '<section class="job-panel"><div class="job-toolbar"><div><strong>'+count+' selected</strong><p>Select several options; each gets a separate job.</p></div><button class="primary" data-start-lane="'+lane+'" '+(!count||sending?'disabled':'')+'>'+(lane==='Thesis'?'Investigate selected':'Build selected')+'</button><button data-connect-queue>'+(dashboardKey?'Connection settings':'Connect dashboard')+'</button></div><p class="queue-state" role="status">'+esc(queueError||(dashboardKey?(workerInfo?.online?'Laptop worker online · jobs run one at a time.':'VPS queue connected · laptop offline or starting. Jobs stay queued.'):'Connect once with your private dashboard key to start work.'))+'</p>'+jobs.map(j=>'<article class="job-row"><div><strong>'+esc(j.candidate)+' · '+esc(j.state.replaceAll('_',' '))+'</strong><p>'+esc(j.message)+'</p>'+(j.result?.url?'<a href="'+esc(safeLink(j.result.url))+'" target="_blank" rel="noopener noreferrer">Open private review artifacts ↗</a>':'')+'</div><div>'+(['queued','running'].includes(j.state)?'<button data-job-action="pause" data-job-id="'+esc(j.id)+'">Pause</button>':'')+(['paused','needs_attention','quota_wait'].includes(j.state)?'<button data-job-action="resume" data-job-id="'+esc(j.id)+'">Resume</button>':'')+(!['review_ready','cancelled'].includes(j.state)?'<button data-job-action="cancel" data-job-id="'+esc(j.id)+'">Cancel</button>':'')+'</div></article>').join('')+'</section>';
}
function singleJobAction(x){return '<div class="choice-actions"><strong>Start a bounded '+(x.lane==='Thesis'?'investigation':'build')+'</strong><p>This queues only '+esc(x.id)+'. Other selected ideas are kept. The worker uses your subscription allowance and pauses if it cannot verify availability.</p><button class="primary" data-start-one="'+esc(x.id)+'">'+(x.lane==='Thesis'?'Start investigation':'Start build')+'</button></div>';}
function redrawJobs(){renderCards('Thesis',$('thesis-search').value);renderCards('Project');}
async function queueRequest(path,body){
 if(!dashboardKey)throw Error('Connect the dashboard first.');
 const r=await fetch(QUEUE_API+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+dashboardKey,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(15000)});
 const v=await r.json();if(!r.ok)throw Error(v.error||'Queue request failed');return v;
}
async function loadJobs(){
 if(!dashboardKey)return;
 try{const r=await queueRequest('/jobs');
 const signature=JSON.stringify({jobs:r.jobs.map(({updated,created,...rest})=>rest),worker:{online:r.worker.online,detail:r.worker.detail}});
 liveJobs=r.jobs;workerInfo=r.worker;const unchanged=signature===lastQueueSignature&&!queueError;queueError='';lastQueueSignature=signature;if(unchanged)return;}
 catch(e){queueError='Could not reach the queue: '+e.message;}
 redrawJobs();
}
function connectQueue(){
 $('detail-content').innerHTML='<span class="tag">PRIVATE OWNER ACCESS</span><h2>Connect this dashboard</h2><p>Use the private dashboard key generated on your laptop. This key controls only this lab’s jobs; it is not a GitHub, ChatGPT or SSH credential. It stays in this browser tab’s session storage.</p><label for="dashboard-key">Dashboard key</label><input type="password" id="dashboard-key" autocomplete="off" placeholder="Paste your private dashboard key"><p class="muted">Retrieve it locally with: python -m engine.dashboard_key. Never put it in a GitHub issue or commit it.</p><button class="primary" id="save-dashboard-key">Connect</button> <button id="forget-dashboard-key">Disconnect</button><p id="connection-result" role="status"></p>';
 $('save-dashboard-key').onclick=async()=>{
 const candidate=$('dashboard-key').value.trim();if(candidate.length<30){$('connection-result').textContent='Enter the full private dashboard key.';return;}
 const old=dashboardKey;dashboardKey=candidate;
 try{const r=await queueRequest('/jobs');sessionStorage.setItem('lab-dashboard-key',dashboardKey);liveJobs=r.jobs;workerInfo=r.worker;queueError='';$('detail').close();redrawJobs();}
 catch(e){dashboardKey=old;$('connection-result').textContent='Connection failed: '+e.message;}
 };
 $('forget-dashboard-key').onclick=()=>{dashboardKey='';sessionStorage.removeItem('lab-dashboard-key');liveJobs=[];workerInfo=null;queueError='';$('detail').close();redrawJobs();};
 $('detail').showModal();
}
function confirmStart(ids){
 if(!dashboardKey){connectQueue();return;}
 const cards=ids.map(id=>data.opportunities.find(x=>x.id===id)).filter(Boolean);
 if(!cards.length)return;
 $('detail-content').innerHTML='<span class="tag">START '+cards.length+' SEPARATE JOB'+(cards.length===1?'':'S')+'</span><h2>Review the selected work</h2><ul>'+cards.map(c=>'<li><strong>'+esc(c.id)+' · '+esc(c.title)+'</strong><p>'+esc(c.deliverable)+'</p></li>').join('')+'</ul><p>Thesis jobs produce investigation briefs. Project jobs produce bounded drafts for review. Jobs run one at a time on the laptop; the VPS holds the queue while it is off. No paid model fallback.</p><button id="confirm-start-jobs" class="primary">Confirm & queue '+cards.length+' job'+(cards.length===1?'':'s')+'</button><p id="start-result" role="status"></p>';
 $('detail').showModal();
 const requestId=crypto.randomUUID();
 $('confirm-start-jobs').onclick=async()=>{
 if(sending)return;sending=true;$('confirm-start-jobs').disabled=true;
 try{const r=await queueRequest('/jobs',{request_id:requestId,items:cards.map(c=>({id:c.id,version:c.version}))});liveJobs=r.jobs;workerInfo=r.worker;queueError='';cards.forEach(c=>selectedIdeas.delete(c.id));$('detail').close();}
 catch(e){$('start-result').textContent='Not confirmed: '+e.message+' You can retry safely.';$('confirm-start-jobs').disabled=false;}
 finally{sending=false;redrawJobs();}
 };
}
document.addEventListener('change',e=>{
 const el=e.target.closest('[data-select-idea]');if(!el)return;
 if(el.checked)selectedIdeas.add(el.dataset.selectIdea);else selectedIdeas.delete(el.dataset.selectIdea);
 redrawJobs();
});
document.addEventListener('click',async e=>{
 if(e.target.closest('[data-connect-queue]')){connectQueue();return;}
 const one=e.target.closest('[data-start-one]');if(one){confirmStart([one.dataset.startOne]);return;}
 const batch=e.target.closest('[data-start-lane]');if(batch){confirmStart(data.opportunities.filter(x=>x.lane===batch.dataset.startLane&&selectedIdeas.has(x.id)).map(x=>x.id));return;}
 const action=e.target.closest('[data-job-action]');if(action){
 action.disabled=true;
 try{const r=await queueRequest('/control',{id:action.dataset.jobId,action:action.dataset.jobAction});liveJobs=r.jobs;workerInfo=r.worker;queueError='';}
 catch(err){queueError=err.message;}redrawJobs();
 }
});
redrawJobs();loadJobs();setInterval(loadJobs,15000);
