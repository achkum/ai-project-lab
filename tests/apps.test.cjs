const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../docs/projects');
const forecast=require(path.join(root,'rp2/analysis.js'));
const review=require(path.join(root,'rp1/analysis.js'));
function sample(app,name){const context={window:{}};vm.runInNewContext(fs.readFileSync(path.join(root,app,'sample.js'),'utf8'),context);return context.window[name];}
test('shipped forecast sample binds a CSV string and completes evaluation',()=>{
 const csv=sample('rp2','SYNTHETIC_CSV');assert.equal(typeof csv,'string');
 const rows=forecast.parseCSV(csv),result=forecast.evaluate(rows,'2025-04-11');
 assert.equal(result.points.length,40);assert.ok(Number.isFinite(result.last.mae));
});
test('shipped review sample completes evidence inspection',()=>{
 const result=review.inspect(sample('rp1','SYNTHETIC_SAMPLE'));
 assert.equal(result.pull_requests.length,5);
 assert.equal(result.pull_requests[0].findings[0].status,'contradicted');
});
test('future observations cannot change earlier forecast predictions',()=>{
 const rows=forecast.parseCSV(sample('rp2','SYNTHETIC_CSV'));
 const before=forecast.evaluate(rows,rows[100].date);rows[130].value+=10000;
 const after=forecast.evaluate(rows,rows[100].date);
 assert.deepEqual(after.points.slice(0,30),before.points.slice(0,30));
});
test('oversized inputs fail before expensive evaluation or rendering',()=>{
 assert.throws(()=>forecast.parseCSV('date,value\n'+'2025-01-01,1\n'.repeat(5001)),/5,000/);
 assert.throws(()=>review.inspect({schema_version:1,pull_requests:Array(201).fill({})}),/200/);
});
test('arithmetic overflow is reported instead of displaying invalid scores',()=>{
 const rows=forecast.parseCSV(sample('rp2','SYNTHETIC_CSV'));
 rows[99].value=-1e308;rows[100].value=1e308;
 assert.throws(()=>forecast.evaluate(rows,rows[100].date),/rescale/);
});
