'use strict';
let setupToken=new URLSearchParams(location.hash.slice(1)).get('setup')||'';
history.replaceState(null,'',location.pathname);
const form=document.getElementById('password-form'),message=document.getElementById('message');
if(!setupToken){form.hidden=true;message.textContent='Open the private setup link prepared for you. This page alone cannot claim the dashboard.';}
fetch('/auth/status',{cache:'no-store'}).then(r=>r.json()).then(s=>{if(s.configured){form.hidden=true;document.getElementById('heading').textContent='Your password is set';message.textContent='Return to the dashboard and sign in with your password.';}}).catch(()=>{message.textContent='Unable to check the server. Refresh before continuing.';});
form.onsubmit=async e=>{
 e.preventDefault();const password=document.getElementById('password'),confirmation=document.getElementById('confirmation');
 if(password.value!==confirmation.value){message.textContent='The passwords do not match.';return;}
 const remember=document.getElementById('remember').checked,button=document.getElementById('submit');button.disabled=true;
 try{const r=await fetch('/auth/setup',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+setupToken},body:JSON.stringify({password:password.value,remember}),cache:'no-store'});const data=await r.json();password.value='';confirmation.value='';if(!r.ok)throw Error(data.error||'Setup failed');setupToken='';location.replace('https://achkum.github.io/ai-project-lab/#session='+encodeURIComponent(data.token)+'&remember='+(remember?'1':'0'));}
 catch(err){message.textContent=err.message;button.disabled=false;}
};
