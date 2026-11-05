const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const code=fs.readFileSync(path.join(__dirname,'../docs/ltu-research.js'),'utf8');
const directory='https://www.ltu.se/en/research/research-subjects';

function load(fetch){
 const context={window:{},URL,fetch};
 vm.runInNewContext(code,context);
 return context.window.LtuResearch;
}

function sample(){
 return {schema_version:1,generated_at:'2026-11-04T08:00:00Z',directory_url:directory,
  coverage:{directory_subjects:3,topic_listings_indexed:858,topics_reviewed:858,note:'Topic coverage <partial>'},subjects:[
   {id:'ml',name:'Machine Learning',review_status:'reviewed',checked_at:'2026-11-03',url:directory+'/machine-learning',
    topics:[
     {id:'energy',title:'Energy forecasts <script>',summary:'Neural networks for weather',status:'ongoing',status_basis:'explicit_topic_statement',
      status_evidence:'Project page calls the work ongoing',ai_connection:'Uses <neural networks>',
      review_scope:'full_topic_page',url:'https://www.ltu.se/project?language=en&view=detail',checked_at:'2026-11-04',source_updated_at:'2026-10-28'},
     {id:'wind',title:'Wind monitoring',status:'completed',ai_connection:'Not stated',
      url:'javascript:alert(1)'}]},
   {id:'design',name:'Design',review_status:'not_reviewed'},
   {id:'rocks',name:'Mining and Rock Engineering',review_status:'inaccessible',
    topics:[{id:'ore',title:'Ore monitoring',url:'https://name@www.ltu.se/project'}]}
  ]};
}

test('renders exact subject groups, distinct review coverage and safe primary links',()=>{
 const container={};
 load().render(container,sample());
 const html=container.innerHTML;
 assert.match(html,/3 directory subjects<\/strong> · 1 reviewed · 1 not reviewed · 1 inaccessible/);
 assert.match(html,/Topic listings indexed · 858 · Topic pages reviewed · 1/);
 assert.match(html,/LTU review still in progress/);
 assert.equal((html.match(/Topic page reviewed/g)||[]).length,1);
 assert.equal((html.match(/Listed on a subject or project index\. Full topic page not reviewed\./g)||[]).length,2);
 assert.match(html,/Showing 3 of 3 subjects · 3 listings/);
 assert.equal((html.match(/<details class="ltu-subject">/g)||[]).length,3);
 for(const name of ['Machine Learning','Design','Mining and Rock Engineering']){
  assert.ok(html.includes('class="ltu-subject-name">'+name+'<'));
 }
 assert.match(html,/Energy forecasts &lt;script&gt;/);
 assert.match(html,/Topic coverage &lt;partial&gt;/);
 assert.match(html,/Uses &lt;neural networks&gt;/);
 assert.match(html,/href="https:\/\/www\.ltu\.se\/project\?language=en&amp;view=detail"/);
 assert.match(html,/Topic page updated<\/dt><dd>2026-10-28<\/dd>.*Checked<\/dt><dd>2026-11-04<\/dd>/);
 for(const label of ['Subject page reviewed','Ongoing','Status not stated'])assert.ok(html.includes('>'+label+'<'));
 assert.doesNotMatch(html,/<script>|javascript:|https:\/\/name@/);
});

test('topic review count uses record evidence and completion requires an explicit flag',()=>{
 const catalog=sample();
 catalog.coverage={directory_subjects:3,exhausted:true,topic_listings_indexed:-1};
 catalog.subjects[0].topics[1].review_status='reviewed';
 const container={};
 load().render(container,catalog);
 assert.match(container.innerHTML,/Topic listings indexed · 3 · Topic pages reviewed · 2/);
 assert.match(container.innerHTML,/Listing counts include index entries\. Review counts cover full topic pages\./);
 assert.doesNotMatch(container.innerHTML,/LTU review still in progress/);
});

test('search finds topic content within subject groups and AI filter requires evidence',()=>{
 const renderer=load();
 const catalog=sample();
 const container={};
 renderer.render(container,catalog,{query:'machine weather'});
 assert.match(container.innerHTML,/Showing 1 of 3 subjects · 1 listing/);
 assert.match(container.innerHTML,/<details class="ltu-subject" open>/);
 assert.doesNotMatch(container.innerHTML,/Wind monitoring|Ore monitoring/);
 renderer.render(container,catalog,{aiOnly:true});
 assert.match(container.innerHTML,/data-ltu-ai type="checkbox" checked/);
 assert.match(container.innerHTML,/Showing 1 of 3 subjects · 1 listing/);
 assert.match(container.innerHTML,/Energy forecasts/);
 assert.doesNotMatch(container.innerHTML,/Wind monitoring/);
 renderer.render(container,catalog,{query:'"missing<subject>"'});
 assert.match(container.innerHTML,/value="&quot;missing&lt;subject&gt;&quot;"/);
 assert.match(container.innerHTML,/Showing 0 of 3 subjects · 0 listings/);
 assert.match(container.innerHTML,/No subjects or topics match these filters/);
 catalog.subjects[0].topics[0].ai_connection='AI connection not documented in the source';
 renderer.render(container,catalog);
 assert.doesNotMatch(container.innerHTML,/data-ltu-ai/);
});

test('initializer surfaces fetch and schema errors, retries once per click and keeps search controls mounted',async()=>{
 const handlers={};
 const results={};
 const container={addEventListener(type,handler){handlers[type]=handler;},querySelector(){return results;}};
 const requests=[];
 const responses=[{ok:false},{ok:true,json:async()=>({...sample(),mode:'sample'})},
  {ok:true,json:async()=>sample()},{ok:true,json:async()=>({...sample(),generated_at:'2026-11-05'})}];
 const renderer=load(async url=>{requests.push(url);return responses.shift();});
 await renderer.init(container);
 assert.match(container.innerHTML,/role="alert"/);
 assert.match(container.innerHTML,/Try again/);
 const retry=()=>handlers.click({target:{closest:selector=>selector.includes('[data-ltu-retry]')}});
 retry();
 await renderer.init(container);
 assert.match(container.innerHTML,/role="alert"/);
 assert.doesNotMatch(container.innerHTML,/reviewed ·/);
 retry();
 await renderer.init(container);
 assert.match(container.innerHTML,/Showing 3 of 3 subjects/);
 const before=container.innerHTML;
 handlers.input({target:{matches:selector=>selector==='[data-ltu-query]',value:'weather'}});
 assert.equal(container.innerHTML,before);
 assert.match(results.innerHTML,/Showing 1 of 3 subjects · 1 listing/);
 assert.match(container.innerHTML,/Refresh LTU catalogue/);
 handlers.click({target:{closest:selector=>selector.includes('[data-ltu-refresh]')}});
 await renderer.init(container);
 assert.match(container.innerHTML,/Catalog generated · 2026-11-05/);
 assert.match(container.innerHTML,/value="weather"/);
 assert.match(container.innerHTML,/Showing 1 of 3 subjects · 1 listing/);
 assert.deepEqual(requests,Array(4).fill('data/ltu-research.json'));
});

test('status basis and source-specific dates survive full topic review without stronger claims',()=>{
 const catalog=sample();
 catalog.subjects[0].topics=[
  {title:'Index says current',status:'ongoing',status_basis:'listing_heading',review_scope:'full_topic_page',
   url:'https://www.ltu.se/topic',status_evidence:'Current <projects>',status_source_url:'https://www.ltu.se/status-index',
   original_published_at:'2020-02-01',source_updated_at:'2026-11-01',source_date_kind:'listing_page_updated',
   source_url:'https://www.ltu.se/date-index',checked_at:'2026-11-05'},
  {title:'Index says completed',status:'completed',status_basis:'listing_heading',review_status:'reviewed'},
  {title:'Future schedule',status:'ongoing',status_basis:'published_schedule'},
  {title:'Elapsed schedule',status:'completed',status_basis:'elapsed_schedule_uncertain'},
  {title:'No basis',status:'ongoing',status_basis:'unknown',source_updated_at:'2026-10-01',url:'https://www.ltu.se/only-primary'}
 ];
 const container={};
 load().render(container,catalog);
 const html=container.innerHTML;
 assert.match(html,/Listed as current/);
 assert.match(html,/Listed as completed/);
 assert.match(html,/Within published project period/);
 assert.match(html,/Published period elapsed\. Current status uncertain/);
 assert.match(html,/Confirm activity and availability with the project/);
 assert.match(html,/Original publication<\/dt><dd>2020-02-01/);
 assert.match(html,/Listing page updated<\/dt><dd>2026-11-01/);
 assert.match(html,/Checked<\/dt><dd>2026-11-05/);
 assert.match(html,/href="https:\/\/www\.ltu\.se\/status-index"[^>]*>Open status source/);
 assert.match(html,/href="https:\/\/www\.ltu\.se\/date-index"[^>]*>Open date source/);
 assert.match(html,/Status evidence · Current &lt;projects&gt;/);
 const unknown=html.slice(html.indexOf('<h4>No basis</h4>'),html.indexOf('</article>',html.indexOf('<h4>No basis</h4>')));
 assert.match(unknown,/>Status not stated</);
 assert.match(unknown,/Topic page updated<\/dt><dd>2026-10-01/);
 assert.doesNotMatch(unknown,/Open date source/);
});

test('additional thesis listing routes are collapsed and keep safe sources and date evidence distinct',()=>{
 const catalog=sample();
 catalog.thesis_listing_sources=[{id:'route',title:'Thesis <routes>',kind:'department_index',summary:'Explore & discuss',
  availability_note:'Confirm <availability>',url:'https://www.ltu.se/thesis-route',review_scope:'listing_page',
  original_published_at:'2021-01-01',source_updated_at:'2026-10-20',checked_at:'2026-11-05',
  related_links:[{url:'https://www.ltu.se/related',label:'Related <guidance>'},{url:'javascript:alert(1)',label:'Unsafe related'}]}];
 const container={};
 load().render(container,catalog);
 const html=container.innerHTML;
 assert.match(html,/<details class="ltu-listing-sources"><summary>Other places LTU lists thesis work<\/summary>/);
 assert.ok(html.indexOf('Other places LTU lists thesis work')<html.indexOf('class="ltu-toolbar"'));
 assert.match(html,/Confirm each offer’s availability and course fit with its provider/);
 assert.match(html,/Thesis &lt;routes&gt;/);
 assert.match(html,/Confirm &lt;availability&gt;/);
 assert.match(html,/href="https:\/\/www\.ltu\.se\/thesis-route"[^>]*>Open listing source/);
 assert.match(html,/Source page updated<\/dt><dd>2026-10-20/);
 assert.match(html,/Related &lt;guidance&gt;/);
 assert.doesNotMatch(html,/Unsafe related|javascript:/);
});
