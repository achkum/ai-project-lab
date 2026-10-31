(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.PublicPR=api;})(globalThis,function(){
'use strict';
function path(url){const m=/^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+)\/pull\/([1-9]\d*)(?:[/?#].*)?$/.exec(url.trim());if(!m)throw Error('Paste a public GitHub pull request URL, for example https://github.com/owner/repo/pull/123.');return `/repos/${m[1]}/${m[2]}/pulls/${m[3]}`;}
async function inspect(url,fetcher=fetch){
 const p=path(url),base=p.split('/pulls/')[0];
 async function get(route){const r=await fetcher('https://api.github.com'+route,{headers:{Accept:'application/vnd.github+json'},credentials:'omit',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error(r.status===403||r.status===429?'GitHub rate limit or access restriction. Try later; no token is required for public PRs.':`GitHub returned ${r.status}. Check that the PR is public.`);return r.json();}
 async function list(route,key){let all=[];for(let page=1;page<=3;page++){const d=await get(route+(route.includes('?')?'&':'?')+'per_page=100&page='+page),items=key?d[key]:d;if(!Array.isArray(items))throw Error('Unexpected GitHub response.');all.push(...items);if(items.length<100)return all;}throw Error('This PR exceeds the 300-record limit. No partial report was produced.');}
 const pr=await get(p);if(!/^[a-f0-9]{40,64}$/i.test(pr.head?.sha||''))throw Error('GitHub did not return a valid head revision.');
 const [reviews,checks,statuses]=await Promise.all([list(p+'/reviews'),list(base+'/commits/'+pr.head.sha+'/check-runs?filter=latest','check_runs'),list(base+'/commits/'+pr.head.sha+'/statuses')]);
 const after=await get(p);if(after.head.sha!==pr.head.sha||after.updated_at!==pr.updated_at)throw Error('This PR changed while loading. Run the check again.');
 const latest=new Map();for(const r of reviews)if(r.state!=='COMMENTED'&&r.state!=='PENDING')latest.set(r.user?.login||String(r.id),r);
 const findings=[];const add=(title,detail,link)=>findings.push({title,detail,url:link||pr.html_url});
 for(const r of latest.values()){
  if(r.state==='CHANGES_REQUESTED')add('Reviewer requested changes',r.user.login+': '+(r.body||'Read the review on GitHub.'),r.html_url);
  if(r.state==='APPROVED'&&r.commit_id!==pr.head.sha)add('Approval is for an older revision',r.user.login+' approved '+r.commit_id+'. Check whether the later changes need another review.',r.html_url);
  if(r.state==='APPROVED'&&/\b(if|unless|provided|assuming|once|after|pending|when)\b/i.test(r.body||''))add('Read this possible approval condition',r.body+' — keyword match only; meaning and resolution are not determined.',r.html_url);
 }
 for(const c of checks)if(c.status!=='completed'||!['success','neutral','skipped'].includes(c.conclusion))add('Check needs attention: '+c.name,c.status==='completed'?'Result: '+c.conclusion:'Still '+c.status,c.html_url);
 const statusMap=new Map();for(const s of statuses)if(!statusMap.has(s.context))statusMap.set(s.context,s);
 for(const s of statusMap.values())if(s.state!=='success')add('Status needs attention: '+s.context,s.state+' — '+(s.description||''),s.target_url);
 if(![...latest.values()].some(r=>r.state==='APPROVED'&&r.commit_id===pr.head.sha))add('No approval on the current revision was returned','This does not mean your repository requires one. Check its review rules.');
 if(!checks.length&&!statuses.length)add('No checks were returned for the current head','Checks may run against a test merge commit or a fork. This is missing information, not a failed test.');
 return {title:pr.title,url:pr.html_url,state:pr.merged?'merged':pr.state,head:pr.head.sha,checked_at:new Date().toISOString(),findings,counts:{reviews:reviews.length,checks:checks.length,statuses:statuses.length},limits:'Current public API snapshot only. Branch rules, inline discussion resolution, test-merge checks, prior merge-time state and human identity are not verified. This report never grants permission to merge.'};
}
return {path,inspect};});
