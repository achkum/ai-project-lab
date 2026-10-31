(function(){
  'use strict';
  const $ = id => document.getElementById(id);
  let report = null, selected = 0, source = '';
  function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text != null) node.textContent = text; return node; }
  function load(data, label) {
    try {
      const next = ReviewAnalysis.inspect(data);
      report = next; selected = 0; source = label; $('error').hidden = true; $('results').hidden = false; $('source').textContent = label + ' · ' + report.pull_requests.length + ' pull request(s)'; $('filter').value = 'all'; render(); $('results').scrollIntoView({behavior:'smooth'});
    } catch (error) { report = null; $('results').hidden = true; $('error').textContent = 'Could not open this bundle: ' + error.message; $('error').hidden = false; }
  }
  $('sample').addEventListener('click', () => { $('filename').textContent = 'Synthetic sample'; load(window.SYNTHETIC_SAMPLE, 'Synthetic sample · fictional data'); });
  $('file').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    $('filename').textContent = file.name;
    if (file.size > 5 * 1024 * 1024) { report = null; $('results').hidden = true; $('error').textContent = 'File is larger than 5 MB. Choose a smaller normalized bundle.'; $('error').hidden = false; event.target.value = ''; return; }
    try { const content = await file.text(); let data; try { data = JSON.parse(content); } catch (_) { throw new Error('Invalid JSON. Check the file syntax and try again.'); } load(data, 'Local file: ' + file.name); } catch (error) { report = null; $('results').hidden = true; $('error').textContent = 'Could not read file: ' + error.message; $('error').hidden = false; }
    event.target.value = '';
  });
  function render() {
    const all = report.pull_requests.flatMap(pr => pr.findings); $('summary').replaceChildren();
    [['contradicted','Contradicted'],['unknown','Unknown'],['supported','Supported']].forEach(([key,label]) => { const box=el('div','stat'); box.append(el('b',key,String(all.filter(f=>f.status===key).length)),el('span','',label + ' claims')); $('summary').append(box); });
    $('pr-count').textContent = report.pull_requests.length; $('pr-buttons').replaceChildren();
    report.pull_requests.forEach((pr,i) => { const b=el('button','pr-button' + (i===selected?' active':''),pr.id); b.type='button'; if(i===selected)b.setAttribute('aria-current','true'); b.addEventListener('click',()=>{selected=i;render();}); $('pr-buttons').append(b); });
    const pr=report.pull_requests[selected]; $('findings').replaceChildren(); $('timeline').replaceChildren();
    if (!pr) { $('pr-title').textContent='No pull requests supplied'; $('findings').append(el('p','','This bundle contains no PRs to inspect.')); return; }
    $('pr-title').textContent=pr.id;
    const findings=pr.findings.filter(f=>$('filter').value==='all'||f.status===$('filter').value);
    if (!findings.length) $('findings').append(el('p','','No findings in this category.'));
    findings.forEach(f=>{ const row=el('div','finding'), content=el('div'); content.append(el('strong','',f.claim),el('p','',f.explanation),el('div','refs','Evidence: ' + (f.evidence.join(', ') || 'none supplied'))); row.append(el('div','badge '+f.status,f.status),content); $('findings').append(row); });
    if (!pr.timeline.length) $('timeline').append(el('p','','No events supplied.'));
    pr.timeline.forEach(e=>{ const row=el('div','event'); row.append(el('strong','',e.type.toUpperCase()+' · '+e.id),el('time','',e.at),el('pre','',JSON.stringify(e,null,2))); $('timeline').append(row); });
  }
  $('filter').addEventListener('change',render);
  $('export').addEventListener('click',()=>{ if(!report)return; const exported={...report,source_label:source,remedies:['Investigate stale-review dismissal, last-push approval, required checks and bypasses in actual repository settings.','Consider separate named accounts and credential control; account labels do not prove human identity.','Compare existing native controls and Kosli evidence before adding another service.']}; const url=URL.createObjectURL(new Blob([JSON.stringify(exported,null,2)+'\n'],{type:'application/json'})); const a=document.createElement('a'); a.href=url; a.download='review-evidence-report.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); });
})();

