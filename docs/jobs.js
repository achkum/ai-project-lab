'use strict';
const QUEUE_API='https://198.44.116.159.sslip.io';
const selectedIdeas=new Set();
let liveJobs=[],workerInfo=null,queueError='',sending=false,lastQueueSignature='';
let dashboardKey='';
function saveLogin(token,remember){sessionStorage.removeItem('lab-dashboard-key');localStorage.removeItem('lab-dashboard-key');(remember?localStorage:sessionStorage).setItem('lab-dashboard-key',token);dashboardKey=token;}
try{
 const incoming=new URLSearchParams(location.hash.slice(1));
 if(incoming.has('session')){saveLogin(incoming.get('session'),incoming.get('remember')==='1');history.replaceState(null,'',location.pathname+'#thesis');showView();}
 dashboardKey=sessionStorage.getItem('lab-dashboard-key')||localStorage.getItem('lab-dashboard-key')||'';
}catch{}

function selectionControl(x){
 return '<label class="select-idea"><input type="checkbox" data-select-idea="'+esc(x.id)+'" '+(selectedIdeas.has(x.id)?'checked':'')+'> Select '+esc(x.id)+' <span>'+esc(x.batch==='applied-ai'?'New Â· applied AI':'Earlier option')+'</span></label>';
}
function jobControls(lane){
 const count=data.opportunities.filter(x=>x.lane===lane&&selectedIdeas.has(x.id)).length;
 const jobs=liveJobs.filter(x=>x.lane===lane.toLowerCase());
 return '<section class="job-panel"><div class="job-toolbar"><div><strong>'+count+' selected</strong><p>Select several options; each gets a separate job.</p></div><button class="primary" data-start-lane="'+lane+'" '+(!count||sending?'disabled':'')+'>'+(lane==='Thesis'?'Investigate selected':'Build selected')+'</button><button data-connect-queue>'+(dashboardKey?'Account & sign out':'Sign in')+'</button></div><p class="queue-state" role="status">'+esc(queueError||(dashboardKey?(workerInfo?.online?'Laptop worker online Â· jobs run one at a time.':'VPS queue connected Â· laptop offline or starting. Jobs stay queued.'):'Sign in with your password to start work. Viewing ideas is public.'))+'</p>'+jobs.map(j=>'<article class="job-row"><div><strong>'+esc(j.candidate)+' Â· '+esc(j.state.replaceAll('_',' '))+'</strong><p>'+esc(j.message)+'</p>'+(j.result?.url?'<a href="'+esc(safeLink(j.result.url))+'" target="_blank" rel="noopener noreferrer">Open private review artifacts â†—</a>':'')+'</div><div>'+(['queued','running'].includes(j.state)?'<button data-job-action="pause" data-job-id="'+esc(j.id)+'">Pause</button>':'')+(['paused','needs_attention','quota_wait'].includes(j.state)?'<button data-job-action="resume" data-job-id="'+esc(j.id)+'">Resume</button>':'')+(!['review_ready','cancelled'].includes(j.state)?'<button data-job-action="cancel" data-job-id="'+esc(j.id)+'">Cancel</button>':'')+'</div></article>').join('')+'</section>';
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
async function connectQueue(){
 $('detail-content').innerHTML='<span class="tag">PRIVATE OWNER ACCESS</span><h2>Dashboard sign-in</h2><p id="auth-status">Checking password setup…</p><form id="login-form" hidden><label for="login-password">Password</label><input id="login-password" type="password" autocomplete="current-password" required maxlength="128"><label class="remember-login"><input id="remember-login" type="checkbox"> Remember this browser for 30 days</label><button type="submit" class="primary">Sign in</button></form><button id="sign-out">Sign out of this browser</button><p id="connection-result" role="status"></p>';
 $('detail').showModal();
 $('sign-out').onclick=async()=>{
 try{if(dashboardKey)await queueRequest('/auth/logout',{});}catch{}
 dashboardKey='';sessionStorage.removeItem('lab-dashboard-key');localStorage.removeItem('lab-dashboard-key');liveJobs=[];workerInfo=null;queueError='';$('detail').close();redrawJobs();
 };
 $('login-form').onsubmit=async e=>{
 e.preventDefault();const input=$('login-password'),button=e.submitter;button.disabled=true;
 try{const r=await fetch(QUEUE_API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:input.value,remember:$('remember-login').checked}),cache:'no-store',signal:AbortSignal.timeout(15000)});const result=await r.json();input.value='';if(!r.ok)throw Error(result.error||'Sign-in failed');saveLogin(result.token,$('remember-login').checked);queueError='';$('detail').close();await loadJobs();}
 catch(err){$('connection-result').textContent=err.message;}finally{button.disabled=false;}
 };
 try{const r=await fetch(QUEUE_API+'/auth/status',{cache:'no-store'});const status=await r.json();if(status.configured){$('auth-status').textContent='Use your password. It is sent directly to your VPS over HTTPS; it is not saved in this browser.';$('login-form').hidden=false;}else{$('auth-status').textContent='Your password has not been set yet. Use the private setup page opened for you in this chat. Once set, return here to sign in.';}}
 catch(err){$('auth-status').textContent='Could not reach sign-in service. Try again shortly.';}
}
function confirmStart(ids){
 if(!dashboardKey){connectQueue();return;}
 const cards=ids.map(id=>data.opportunities.find(x=>x.id===id)).filter(Boolean);
 if(!cards.length)return;
 $('detail-content').innerHTML='<span class="tag">START '+cards.length+' SEPARATE JOB'+(cards.length===1?'':'S')+'</span><h2>Review the selected work</h2><ul>'+cards.map(c=>'<li><strong>'+esc(c.id)+' Â· '+esc(c.title)+'</strong><p>'+esc(c.deliverable)+'</p></li>').join('')+'</ul><p>Thesis jobs produce investigation briefs. Project jobs produce bounded drafts for review. Jobs run one at a time on the laptop; the VPS holds the queue while it is off. No paid model fallback.</p><button id="confirm-start-jobs" class="primary">Confirm & queue '+cards.length+' job'+(cards.length===1?'':'s')+'</button><p id="start-result" role="status"></p>';
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
