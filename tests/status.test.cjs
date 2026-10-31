const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const base=path.join(__dirname,'../docs');
const app=fs.readFileSync(path.join(base,'app.js'),'utf8');
const sample=JSON.parse(fs.readFileSync(path.join(base,'data/status.json'),'utf8'));
const context=vm.createContext({window:{LAB_SAMPLE:sample},document:{getElementById:()=>({})},URL,Date});
vm.runInContext(app.slice(0,app.indexOf("document.addEventListener"))+'\nthis.check=valid;this.escapeText=esc;this.link=safeLink;',context);
assert.equal(context.check(sample),true);
for(const bad of [null,{}, {...sample,sources:[null]}, {...sample,events:[{}]}, {...sample,coverage:{checked:'20'}}, {...sample,mode:'live',generated_at:null}, {...sample,connected:true}]) assert.equal(context.check(bad),false);
assert.equal(context.check({...sample,mode:'live',connected:true,generated_at:new Date().toISOString()}),true);
assert.equal(context.link('javascript:alert(1)'),'#');
assert.equal(context.escapeText('<img src=x onerror=alert(1)>'),'&lt;img src=x onerror=alert(1)&gt;');
assert.equal(sample.sources.length,30);
assert.equal(new Set(sample.sources.map(x=>x.id)).size,30);
console.log('Passed: sample/live validation, malformed snapshots, unsafe URL rejection, text escaping and 30 unique source records.');

