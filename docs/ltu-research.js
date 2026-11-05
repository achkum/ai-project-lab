(function () {
 'use strict';

 const directoryUrl='https://www.ltu.se/en/research/research-subjects';
 const reviewLabels={reviewed:'Subject page reviewed',not_reviewed:'Not reviewed',inaccessible:'Inaccessible'};
 const topicLabels={ongoing:'Ongoing',completed:'Completed',not_stated:'Status not stated'};
 const mounted=new WeakMap();
 const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
 const words=value=>String(value??'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase();
 const topicsFor=subject=>Array.isArray(subject.topics)?subject.topics:[];
 const reviewOf=subject=>Object.hasOwn(reviewLabels,subject.review_status)?subject.review_status:'not_reviewed';
 const topicReviewed=topic=>topic.review_status==='reviewed'||topic.review_scope==='full_topic_page';

 function evidenceNote(topic) {
  if(typeof topic.ai_connection!=='string')return '';
  const note=topic.ai_connection.trim();
  const uncertain=/^(?:no|none|not|unknown|unclear|unverified|potential|possible|n\/a)\b/i;
  const absent=/\b(?:not stated|not documented|not evidenced|no (?:explicit )?(?:evidence|mention))\b/i;
  return uncertain.test(note)||absent.test(note)?'':note;
 }

 function safeUrl(value) {
  if(typeof value!=='string')return '';
  try {
   const url=new URL(value);
   return url.protocol==='https:'&&!url.username&&!url.password?url.href:'';
  } catch{return '';}
 }

 function link(url,label) {
  const href=safeUrl(url);
  return href?'<a class="ltu-source" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+' ↗</a>':'';
 }

 function date(value,fallback) {
  return typeof value==='string'&&value.trim()?esc(value):fallback;
 }

 function topicStatus(topic) {
  const status=Object.hasOwn(topicLabels,topic.status)?topic.status:'not_stated';
  if(topic.status_basis==='listing_heading'){
   return status==='ongoing'?'Listed as current':status==='completed'?'Listed as completed':topicLabels.not_stated;
  }
  if(topic.status_basis==='published_schedule'){
   return status==='ongoing'?'Within published project period':status==='completed'?'Published project period ended':topicLabels.not_stated;
  }
  if(topic.status_basis==='elapsed_schedule_uncertain')return 'Published period elapsed. Current status uncertain';
  return topic.status_basis==='explicit_topic_statement'?topicLabels[status]:topicLabels.not_stated;
 }

 function sourceDates(record,updatedLabel) {
  const label=record.source_date_kind==='listing_page_updated'?'Listing page updated':updatedLabel;
  return '<dl class="ltu-dates"><div><dt>Original publication</dt><dd>'+date(record.original_published_at,'Not stated')+'</dd></div>'+
   '<div><dt>'+label+'</dt><dd>'+date(record.source_updated_at,'Not stated')+'</dd></div>'+
   '<div><dt>Checked</dt><dd>'+date(record.checked_at,'Not recorded')+'</dd></div></dl>'+
   link(record.source_url,'Open date source');
 }

 function thesisListingSources(catalog) {
  const sources=Array.isArray(catalog.thesis_listing_sources)?catalog.thesis_listing_sources.filter(source=>source&&typeof source.title==='string'):[];
  if(!sources.length)return '';
  return '<details class="ltu-listing-sources"><summary>Other places LTU lists thesis work</summary>'+
   '<p>These pages provide routes for finding thesis work. Confirm each offer’s availability and course fit with its provider.</p>'+
   '<div class="ltu-topics">'+sources.map(source=>{
    const related=Array.isArray(source.related_links)?source.related_links.filter(item=>item&&typeof item.label==='string').map(item=>link(item.url,item.label)).filter(Boolean):[];
    return '<article class="ltu-topic"><h4>'+esc(source.title)+'</h4>'+
     (source.kind?'<p class="ltu-evidence">'+esc(String(source.kind).replaceAll('_',' '))+'</p>':'')+
     (source.summary?'<p>'+esc(source.summary)+'</p>':'')+
     (source.availability_note?'<p>'+esc(source.availability_note)+'</p>':'')+
     link(source.url,'Open listing source')+
     (source.review_scope?'<p class="ltu-evidence">Review scope · '+esc(source.review_scope)+'</p>':'')+
     sourceDates(source,'Source page updated')+
     (related.length?'<div class="ltu-related">'+related.join(' ')+'</div>':'')+'</article>';
   }).join('')+'</div></details>';
 }

 function assertCatalog(catalog) {
  if(catalog?.schema_version!==1||catalog.mode==='sample'||!Array.isArray(catalog.subjects)||
     catalog.subjects.some(subject=>typeof subject?.name!=='string'||!subject.name.trim()||
      topicsFor(subject).some(topic=>typeof topic?.title!=='string'||!topic.title.trim()))){
   throw new Error('Unsupported research catalog');
  }
 }

 function select(catalog,filters) {
  const terms=words(filters.query).trim().split(/\s+/).filter(Boolean);
  const hasAiEvidence=catalog.subjects.some(subject=>topicsFor(subject).some(evidenceNote));
  const aiOnly=hasAiEvidence&&filters.aiOnly===true;
  const matches=fields=>{
   const text=words(fields.join(' '));
   return terms.every(term=>text.includes(term));
  };
  const groups=[];
  for(const subject of catalog.subjects){
   const subjectFields=[subject.name,subject.summary];
   const topics=topicsFor(subject).filter(topic=>(!aiOnly||evidenceNote(topic))&&matches([
    ...subjectFields,topic.title,topic.summary,topic.status_evidence,evidenceNote(topic),topicStatus(topic)
   ]));
   if(topics.length||(!aiOnly&&matches(subjectFields)))groups.push({subject,topics});
  }
  return {groups,hasAiEvidence,aiOnly,filtered:terms.length>0||aiOnly};
 }

 function topicCard(topic) {
  const status=topicStatus(topic);
  const ai=evidenceNote(topic);
  return '<article class="ltu-topic"><h4>'+esc(topic.title)+'</h4><span class="ltu-badge">'+status+'</span>'+
   '<p class="ltu-evidence">'+(topicReviewed(topic)?'Topic page reviewed':'Listed on a subject or project index. Full topic page not reviewed.')+'</p>'+
   (topic.summary?'<p>'+esc(topic.summary)+'</p>':'')+
   (topic.status_evidence?'<p class="ltu-evidence">Status evidence · '+esc(topic.status_evidence)+'</p>':'')+
   link(topic.status_source_url,'Open status source')+
   (topic.status_basis==='published_schedule'?'<p class="ltu-evidence">Published dates describe the project schedule. Confirm activity and availability with the project.</p>':'')+
   (ai?'<p class="ltu-evidence">AI connection · '+esc(ai)+'</p>':'')+
   sourceDates(topic,'Topic page updated')+
   link(topic.url,'Open topic source')+'</article>';
 }

 function subjectGroup({subject,topics},filtered) {
  const review=reviewOf(subject);
  const total=topicsFor(subject).length;
  const count=filtered&&topics.length!==total?topics.length+' of '+total:String(total);
  const empty=total?'No topics in this subject match the filters.':
   review==='reviewed'?'No topic pages were recorded in this review.':
   review==='inaccessible'?'The subject page could not be accessed during review.':'Topic pages have yet to be reviewed.';
  return '<details class="ltu-subject"'+(filtered&&topics.length?' open':'')+'><summary>'+
   '<span class="ltu-subject-name">'+esc(subject.name)+'</span>'+
   '<span class="ltu-subject-meta"><span class="ltu-badge ltu-review-'+review+'">'+reviewLabels[review]+'</span>'+
   '<span>'+count+' '+(total===1?'listing':'listings')+'</span></span></summary>'+
   '<div class="ltu-subject-body">'+(subject.summary?'<p>'+esc(subject.summary)+'</p>':'')+
   '<p class="ltu-evidence">Subject checked · '+date(subject.checked_at,'Not recorded')+'</p>'+
   link(subject.url,'Open LTU subject page')+
   (topics.length?'<div class="ltu-topics">'+topics.map(topicCard).join('')+'</div>':'<p class="ltu-empty">'+empty+'</p>')+
   '</div></details>';
 }

 function resultsHtml(catalog,selection) {
  const {groups,filtered}=selection;
  const topicCount=groups.reduce((count,group)=>count+group.topics.length,0);
  return '<p class="ltu-result-count" role="status">Showing '+groups.length+' of '+catalog.subjects.length+
   ' subjects · '+topicCount+' '+(topicCount===1?'listing':'listings')+'</p>'+
   (groups.length?'<div class="ltu-subjects">'+groups.map(group=>subjectGroup(group,filtered)).join('')+'</div>':
    '<p class="ltu-empty">'+(filtered?'No subjects or topics match these filters.':'The catalog contains no subject records.')+'</p>');
 }

 function render(container,catalog,filters={}) {
  assertCatalog(catalog);
  const selection=select(catalog,filters);
  const counts={reviewed:0,not_reviewed:0,inaccessible:0};
  for(const subject of catalog.subjects)counts[reviewOf(subject)]++;
  const allTopics=catalog.subjects.flatMap(topicsFor);
  const listedCount=catalog.coverage?.topic_listings_indexed;
  const indexed=Number.isInteger(listedCount)&&listedCount>=0?listedCount:allTopics.length;
  const reviewedTopics=allTopics.filter(topicReviewed).length;
  const officialCount=catalog.coverage?.directory_subjects;
  const directoryCount=Number.isInteger(officialCount)&&officialCount>=0?officialCount:catalog.subjects.length;
  const source=link(catalog.directory_url,'Open the official LTU directory')||link(directoryUrl,'Open the official LTU directory');
  container.innerHTML='<div class="ltu-catalog"><div class="ltu-intro">'+
   '<p>Browse LTU research subjects and topics from its public pages. Proposed thesis studies are in the Thesis tab. Confirm supervision and student access to resources separately.</p>'+
   source+'</div><section class="ltu-coverage" aria-label="Catalog coverage">'+
   '<p><strong>'+directoryCount+' directory subjects</strong> · '+counts.reviewed+' reviewed · '+counts.not_reviewed+
   ' not reviewed · '+counts.inaccessible+' inaccessible</p>'+
   '<p>Topic listings indexed · '+indexed+' · Topic pages reviewed · '+reviewedTopics+'</p>'+
   (catalog.coverage?.exhausted===true?'':'<p><strong>LTU review still in progress</strong></p>')+
   (catalog.generated_at?'<p>Catalog generated · '+date(catalog.generated_at,'Not recorded')+'</p>':'')+
   '<p>'+(catalog.coverage?.note?esc(catalog.coverage.note):'Listing counts include index entries. Review counts cover full topic pages.')+'</p></section>'+
   thesisListingSources(catalog)+'<div class="ltu-toolbar"><label>Search subjects and topics<input data-ltu-query type="search" value="'+esc(filters.query)+
   '" placeholder="Search names, topics or research methods"></label>'+
   (selection.hasAiEvidence?'<label class="ltu-check"><input data-ltu-ai type="checkbox"'+(selection.aiOnly?' checked':'')+
    '> AI connection evidenced</label>':'')+
   '<button type="button" data-ltu-refresh>Refresh LTU catalogue</button></div>'+
   '<div data-ltu-results>'+resultsHtml(catalog,selection)+'</div></div>';
 }

 function init(container) {
  if(!container)return;
  if(mounted.has(container))return mounted.get(container).pending;
  const state={catalog:null,filters:{query:'',aiOnly:false},pending:null};
  mounted.set(container,state);

  function applyFilters(event,selector,key,value) {
   if(!state.catalog||!event.target.matches(selector))return;
   state.filters[key]=value;
   const results=container.querySelector('[data-ltu-results]');
   results.innerHTML=resultsHtml(state.catalog,select(state.catalog,state.filters));
  }

  async function load() {
   container.innerHTML='<p class="ltu-empty" role="status">Loading the LTU research catalog…</p>';
   try {
    const response=await fetch('data/ltu-research.json',{cache:'no-cache'});
    if(!response.ok)throw new Error('Catalog fetch failed');
    const catalog=await response.json();
    render(container,catalog,state.filters);
    state.catalog=catalog;
   } catch {
    state.catalog=null;
    container.innerHTML='<div class="ltu-empty ltu-error" role="alert"><p>The LTU research catalog could not be loaded.</p>'+
     '<button type="button" data-ltu-retry>Try again</button> '+link(directoryUrl,'Open the official LTU directory')+'</div>';
   }
  }

  container.addEventListener('input',event=>applyFilters(event,'[data-ltu-query]','query',event.target.value));
  container.addEventListener('change',event=>applyFilters(event,'[data-ltu-ai]','aiOnly',event.target.checked));
  container.addEventListener('click',event=>{
   if(event.target.closest('[data-ltu-retry], [data-ltu-refresh]'))state.pending=load();
  });
  state.pending=load();
  return state.pending;
 }

 window.LtuResearch={render,init};
}());
