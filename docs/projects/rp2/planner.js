(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.QuantityPlanner=api;})(globalThis,function(){
'use strict';
function plan(rows,{method='seasonal',uplift=0,waste=1,shortage=1,current=0}={}){
 if(!Array.isArray(rows)||rows.length<21||rows.some(r=>!Number.isFinite(r.value)||r.value<0||r.value>1e9))throw Error('Planning needs at least 21 days of nonnegative daily sales, up to one billion units per day.');
 if(!['seasonal','last'].includes(method)||![uplift,waste,shortage,current].every(Number.isFinite)||uplift< -100||uplift>200||waste<0||shortage<0||waste>1e6||shortage>1e6||current<0||current>1e9)throw Error('Use valid quantities and nonnegative costs; adjustment must be between −100% and +200%.');
 const lag=method==='seasonal'?7:1,quantity=value=>Math.ceil(value*(1+uplift/100));
 const tally=(rule)=>{let excess=0,missing=0;for(let i=7;i<rows.length;i++){const q=rule(i);excess+=Math.max(0,q-rows[i].value);missing+=Math.max(0,rows[i].value-q);}return {excess,missing,cost:excess*waste+missing*shortage,days:rows.length-7};};
 const last=rows.at(-1),tomorrow=new Date(Date.parse(last.date+'T00:00:00Z')+86400000).toISOString().slice(0,10);
 return {date:tomorrow,quantity:quantity(rows[rows.length-lag].value),reference:rows[rows.length-lag],method,uplift,waste,shortage,current,proposed:tally(i=>quantity(rows[i-lag].value)),comparison:tally(()=>current),warning:'Historical simulation, not measured savings. Sales can hide unmet demand when stock runs out. No holiday, weather, promotion or stockout adjustment. The adjustment is applied to every historical day; do not tune it on this window and claim independent validation.'};
}return {plan};});
