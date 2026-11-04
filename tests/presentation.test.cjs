const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('source publication, revision and project dates remain distinct',()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/app.js'),'utf8');
 const context={window:{LAB_SAMPLE:{}},document:{getElementById:()=>({})},URL,Date};vm.createContext(context);
 vm.runInContext(code.slice(0,code.indexOf('document.addEventListener'))+'\nthis.provenance=provenanceDetails;',context);
 const out=context.provenance({provenance:[{title:'Research group',url:'https://www.ltu.se/research',
  published_at:null,revised_at:'2026-10-26',event_date:'2026-11-01',verified_at:'2026-11-04',
  date_notes:'Original date unknown <script>',read_scope:'Full project page'}]});
 assert.match(out,/Published: Unknown/);assert.match(out,/Revised \/ page updated: 2026-10-26/);
 assert.match(out,/Project event: 2026-11-01/);assert.match(out,/Checked: 2026-11-04/);
 assert.match(out,/Original date unknown &lt;script&gt;/);assert.doesNotMatch(out,/Published: 2026-10-26|<script>/);
});
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
test('Thesis Study details disclose proposed LTU fit and protect institutional evidence',async()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/app.js'),'utf8');
 const fit={study_type:'Comparative evaluation',student_contribution:'Build the benchmark',
  research_connection:'Compare to related work',alignment_kind:'indirect',limits:'Confirm dataset access',
  institutional_sources:[{title:'LTU <course>',url:'https://www.ltu.se/course?lang=en&view=full'},
   {title:'Comparable research group',url:'https://www.uu.se/research'},
   {title:'Unsecured source',url:'http://www.ltu.se/course'},
   {title:'Credentials source',url:'https://name@www.ltu.se/course'},
   {title:'Unsafe source',url:'javascript:alert(1)'}]};
 const reviewed={id:'T1',title:'Reviewed study',lane:'Thesis',academic_fit:fit};
 const legacy={id:'T2',title:'Older study',lane:'Thesis'};
 const project={id:'P1',title:'Project',lane:'Project',academic_fit:fit};
 const nodes={'detail-content':{innerHTML:'',insertAdjacentHTML(){}},detail:{showModal(){}}};
 let onClick;
 const context={window:{LAB_SAMPLE:{opportunities:[reviewed,legacy,project],opportunity_copy:{
  T1:{academic_fit:{student_contribution:'Design <img> and test',alignment_kind:'direct',
    institutional_sources:[{title:'Overridden source',url:'https://ltu.se/other'}]}},
  T2:{academic_fit:fit}}}},document:{getElementById:id=>nodes[id],addEventListener:(_,handler)=>{onClick=handler;}},URL,Date};
 vm.createContext(context);vm.runInContext(code.slice(0,code.indexOf("$('close-detail')")),context);
 async function open(id){
  await onClick({target:{closest:selector=>selector==='[data-detail]'?{dataset:{detail:id}}:null}});
  return nodes['detail-content'].innerHTML;
 }
 const out=await open('T1');
 assert.match(out,/<details class="evidence-details"><summary>Why this fits an Applied AI thesis<\/summary>/);
 assert.match(out,/Proposed fit for LTU’s Applied AI thesis course · Indirect alignment/);
 assert.match(out,/Comparative evaluation/);
 assert.match(out,/Design &lt;img&gt; and test/);
 assert.match(out,/Compare to related work/);
 assert.match(out,/Confirm dataset access/);
 assert.match(out,/Course approval and access to supervision, data and computing resources require separate confirmation/);
 assert.match(out,/href="https:\/\/www\.ltu\.se\/course\?lang=en&amp;view=full"/);
 assert.match(out,/LTU &lt;course&gt;/);
 assert.match(out,/Research and course sources/);
 assert.match(out,/href="https:\/\/www\.uu\.se\/research"/);
 assert.doesNotMatch(out,/<img>|Unsecured source|Credentials source|Unsafe source|Overridden source/);
 assert.equal(fit.student_contribution,'Build the benchmark');
 assert.match(await open('T2'),/LTU course fit has not yet been reviewed/);
 assert.doesNotMatch(await open('P1'),/Why this fits an Applied AI thesis|LTU course fit/);
});
test('local completion is not labelled a public live app',()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/jobs.js'),'utf8');
 const excerpt=code.slice(code.indexOf('function isLocalApp'),code.indexOf('function manualStartAllowed'));
 const context={};vm.createContext(context);vm.runInContext(excerpt+'\nthis.label=jobLabel;this.link=appLinkLabel;',context);
 const job={lane:'project',state:'completed',result:{demo_url:'http://127.0.0.1:19123/'}};
 assert.equal(context.label(job),'Local prototype ready');assert.equal(context.link(job),'Open on this laptop →');
 assert.equal(context.label({...job,result:{demo_url:'https://achkum.github.io/ai-project-lab/projects/rp1/'}}),'App live');
});
