(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.Pilot=factory()})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
function parseCSV(text){
 if(typeof text!=='string')throw Error('Choose a UTF-8 CSV file.');
 const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/); if(lines.length<2)throw Error('CSV needs a header and at least one observation.');
 const headers=lines[0].split(',').map(x=>x.trim().toLowerCase()); const di=headers.indexOf('date'),vi=headers.indexOf('value');
 if(di<0||vi<0||new Set(headers).size!==headers.length)throw Error('CSV needs unique date,value headers.');
 let prev; return lines.slice(1).map((line,j)=>{const fields=line.split(',');if(fields.length!==headers.length)throw Error(`Row ${j+2}: expected ${headers.length} comma-separated fields (quoted CSV is not supported).`);const d=fields[di].trim(),s=fields[vi].trim();
 if(!/^\d{4}-\d{2}-\d{2}$/.test(d))throw Error(`Row ${j+2}: date must be YYYY-MM-DD.`);const t=Date.parse(d+'T00:00:00Z');if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,10)!==d)throw Error(`Row ${j+2}: invalid calendar date.`);
 if(!s||!/^[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i.test(s)||!Number.isFinite(Number(s)))throw Error(`Row ${j+2}: value must be a finite number.`);
 if(prev!==undefined&&t-prev!==86400000)throw Error(`Row ${j+2}: dates must be unique, sorted and consecutive daily observations.`);prev=t;return {date:d,value:Number(s)};});
}
function mean(a){return a.reduce((x,y)=>x+y,0)/a.length}
function interval(a,seed=2026,reps=1000,block=7){let state=seed>>>0;function rand(){state=(Math.imul(1664525,state)+1013904223)>>>0;return state/4294967296}let out=[];for(let r=0;r<reps;r++){let s=0,n=0;while(n<a.length){let start=Math.floor(rand()*a.length);for(let j=0;j<block&&n<a.length;j++,n++)s+=a[(start+j)%a.length]}out.push(s/a.length)}out.sort((x,y)=>x-y);return [out[Math.floor(.025*(reps-1))],out[Math.floor(.975*(reps-1))]]}
function evaluate(rows,start){const i=rows.findIndex(r=>r.date===start);if(i<0)throw Error('Evaluation start must match a date in the file.');if(i<7)throw Error('At least 7 daily observations must precede the evaluation start.');if(rows.length-i<14)throw Error('At least 14 evaluation targets are required.');let points=rows.slice(i).map((r,j)=>{let k=i+j,last=rows[k-1].value,seasonal=rows[k-7].value;return {date:r.date,actual:r.value,last,seasonal,lastError:Math.abs(r.value-last),seasonalError:Math.abs(r.value-seasonal)}});let a=points.map(p=>p.lastError),b=points.map(p=>p.seasonalError),d=a.map((v,k)=>v-b[k]);if([...a,...b,...d].some(x=>!Number.isFinite(x))||!Number.isFinite(a.reduce((x,y)=>x+y,0))||!Number.isFinite(b.reduce((x,y)=>x+y,0)))throw Error('Values are too large to calculate finite errors; rescale the series.');return {startIndex:i,points,last:{mae:mean(a),interval:interval(a)},seasonal:{mae:mean(b),interval:interval(b)},difference:{mean:mean(d),interval:interval(d)}}}
return {parseCSV,evaluate,interval};});

