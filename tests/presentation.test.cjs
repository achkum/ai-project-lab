const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('plain language cannot alter source evidence or selected job identity',()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/app.js'),'utf8');
 const original={id:'NT1',version:1,title:'Technical title',lane:'Thesis',provenance:[{url:'https://example.com/paper'}],model_plan:'Original methods',auto_eligible:false};
 const context={window:{LAB_SAMPLE:{opportunity_copy:{NT1:{title:'A simple question',id:'OTHER',version:9,lane:'Project',provenance:[],model_plan:'Different experiment',auto_eligible:true}}}},document:{getElementById:()=>({})},URL,Date};
 vm.createContext(context);vm.runInContext(code.slice(0,code.indexOf('document.addEventListener'))+'\nthis.present=presentIdea;',context);
 const view=context.present(original);
 assert.equal(view.title,'A simple question');assert.equal(original.title,'Technical title');
 for(const key of ['id','version','lane','provenance','model_plan','auto_eligible'])assert.equal(view[key],original[key]);
});
