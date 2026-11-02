const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('comparison follows local selection across search and batch changes without crossing lanes',()=>{
 const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/app.js'),'utf8');
 const nodes={}; for(const id of ['thesis-cards','project-cards'])nodes[id]={innerHTML:'',querySelector:()=>null};
 const sample={thesis:{research_run:{id:'new',date:'2026-11-02',state:'investigating',investigated_topics:0,target_topics:10}},project:{current_batch:{id:'p',project_ids:['P1'],published_at:'2026-11-01'}},opportunities:[{id:'T1',lane:'Thesis',shortlist:'old',title:'Alpha',summary:'one'},{id:'T2',lane:'Thesis',shortlist:'new',title:'Beta',summary:'two'},{id:'P1',lane:'Project',title:'Gamma',summary:'three'}]};
 const context={window:{LAB_SAMPLE:sample},document:{getElementById:id=>nodes[id]},URL,Date}; vm.createContext(context);
 vm.runInContext(code.slice(0,code.indexOf('document.addEventListener'))+'\nconst selectedIdeas=new Set(); this.selectedIdeas=selectedIdeas; this.renderCards=renderCards;',context);
 context.selectedIdeas.add('T1');context.renderCards('Thesis');assert.ok(!nodes['thesis-cards'].innerHTML.includes('Compare at a glance'));
 context.selectedIdeas.add('T2');context.selectedIdeas.add('P1');context.renderCards('Thesis','Beta');
 const html=nodes['thesis-cards'].innerHTML;assert.ok(html.includes('Compare at a glance'));assert.ok(html.includes('T1 ·'));assert.ok(html.includes('T2 ·'));assert.ok(!html.includes('P1 ·'));
 context.renderCards('Project');assert.ok(!nodes['project-cards'].innerHTML.includes('Compare at a glance'));
 context.renderCards('Thesis');assert.deepEqual([...context.selectedIdeas],['T1','T2','P1']);assert.ok(nodes['thesis-cards'].innerHTML.includes('CURRENT RESEARCH · 2 Nov 2026'));assert.ok(nodes['thesis-cards'].innerHTML.includes('0 / 10 topics investigated'));
});
