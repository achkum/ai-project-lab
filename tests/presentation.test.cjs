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
test('business detail keeps plain workflow visible and technical evidence optional',()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/app.js'),'utf8');
 const context={window:{LAB_SAMPLE:{}},document:{getElementById:()=>({})},URL,Date};vm.createContext(context);
 vm.runInContext(code.slice(0,code.indexOf('document.addEventListener'))+'\nthis.detail=businessDetails;',context);
 const card={id:'BP',title:'A workflow',business_case:{repeat_use:'RETURN',week_one_acceptance:'ACCEPTANCE'},summary:'<script>alert(1)</script>',flow:['Import','Review','Save'],provenance:[],risk:'Unproven',model_plan:'METHOD'};
 const out=context.detail(card);
 assert.ok(out.includes('&lt;script&gt;'));assert.ok(!out.includes('<script>'));
 assert.ok(out.indexOf('What goes wrong?')<out.indexOf('<details'));
 assert.ok(out.indexOf('ACCEPTANCE')>out.indexOf('<details'));
 assert.ok(out.includes('Sources, dates and what is still unproven'));
});
test('local completion is not labelled a public live app',()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/jobs.js'),'utf8');
 const excerpt=code.slice(code.indexOf('function isLocalApp'),code.indexOf('function manualStartAllowed'));
 const context={};vm.createContext(context);vm.runInContext(excerpt+'\nthis.label=jobLabel;this.link=appLinkLabel;',context);
 const job={lane:'project',state:'completed',result:{demo_url:'http://127.0.0.1:19123/'}};
 assert.equal(context.label(job),'Local prototype ready');assert.equal(context.link(job),'Open on this laptop →');
 assert.equal(context.label({...job,result:{demo_url:'https://achkum.github.io/ai-project-lab/projects/rp1/'}}),'App live');
});
