(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ReviewAnalysis = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  const condition = /\b(if|unless|provided|assuming|once|after|pending|when)\b/i;
  function time(value, where) {
    if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value)) throw new Error(where + ': use an ISO timestamp with seconds and timezone, e.g. 2026-01-01T10:00:00Z.');
    const m = value.match(/^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d+)?(Z|([+-])(\d\d):(\d\d))$/);
    const y=+m[1], mo=+m[2], d=+m[3], h=+m[4], mi=+m[5], s=+m[6];
    const days = new Date(Date.UTC(y, mo, 0)).getUTCDate();
    if (mo < 1 || mo > 12 || d < 1 || d > days || h > 23 || mi > 59 || s > 59 || (m[7] !== 'Z' && (+m[9] > 23 || +m[10] > 59)) || !Number.isFinite(Date.parse(value))) throw new Error(where + ': invalid timestamp.');
    return Date.parse(value);
  }
  function validate(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data) || data.schema_version !== 1 || !Array.isArray(data.pull_requests)) throw new Error('Expected an object with schema_version: 1 and a pull_requests array.');
    if(data.pull_requests.length>200)throw new Error('Use a bundle of at most 200 pull requests.');
    let totalEvents=0; const prs = new Set();
    data.pull_requests.forEach((pr, i) => {
      const loc = 'PR ' + (i + 1);
      if (!pr || typeof pr !== 'object' || Array.isArray(pr) || typeof pr.id !== 'string' || !pr.id.trim() || prs.has(pr.id)) throw new Error(loc + ': each PR needs a unique nonempty string id.');
      prs.add(pr.id);
      if (!Array.isArray(pr.events)) throw new Error(loc + ': events must be an array.');
      totalEvents+=pr.events.length; if(pr.events.length>500||totalEvents>10000)throw new Error('Use at most 500 events per PR and 10,000 events per bundle.');
      const ids = new Set(); let merges = 0;
      pr.events.forEach((e, j) => {
        const at = loc + ', event ' + (j + 1);
        if (!e || typeof e !== 'object' || Array.isArray(e) || typeof e.id !== 'string' || !e.id.trim() || ids.has(e.id)) throw new Error(at + ': each event needs a unique nonempty string id within its PR.');
        ids.add(e.id);
        if (!['approval','check','merge'].includes(e.type)) throw new Error(at + ': type must be approval, check, or merge.');
        time(e.at, at);
        for (const key of ['revision','actor','actor_kind','body','name','conclusion']) if (e[key] != null && typeof e[key] !== 'string') throw new Error(at + ': ' + key + ' must be a string or null.');
        if (e.actor_kind != null && !['individual','shared','unknown'].includes(e.actor_kind)) throw new Error(at + ': actor_kind must be individual, shared, or unknown.');
        if (e.type === 'merge') merges++;
      });
      if (merges > 1) throw new Error(loc + ': at most one merge event is allowed.');
    });
    return data;
  }
  function inspect(data) {
    validate(data);
    const pull_requests = data.pull_requests.map(pr => {
      const timeline = pr.events.slice().sort((a,b) => time(a.at,'') - time(b.at,'') || a.id.localeCompare(b.id));
      const merge = timeline.find(e => e.type === 'merge');
      const approvals = timeline.filter(e => e.type === 'approval');
      const checks = timeline.filter(e => e.type === 'check');
      const findings = [];
      const add = (claim,status,evidence,explanation) => findings.push({claim,status,evidence,explanation});
      if (!approvals.length) add('Approval on merged revision','unknown',[],'No approval event supplied; omission does not prove none existed.');
      approvals.forEach(a => {
        const refs = [a.id, ...(merge ? [merge.id] : [])]; let status, reason;
        if (!merge) [status,reason] = ['unknown','Merge evidence is missing.'];
        else if (time(a.at,'') > time(merge.at,'')) [status,reason] = ['contradicted','This approval occurred after merge.'];
        else if (time(a.at,'') === time(merge.at,'')) [status,reason] = ['unknown','Equal timestamps leave ordering ambiguous.'];
        else if (!a.revision || !merge.revision) [status,reason] = ['unknown','Revision evidence is missing.'];
        else if (a.revision === merge.revision) [status,reason] = ['supported','Approval names the recorded merge head revision before merge.'];
        else [status,reason] = ['contradicted','Approval names a different revision. This does not establish whether it remained active.'];
        add('Approval ' + a.id + ' names the merged revision before merge',status,refs,reason);
        if (a.actor && a.actor_kind === 'individual') add('Approval ' + a.id + ' has an individually attributed account','supported',[a.id],'The export labels this account individual; this does not authenticate a human or prove independence.');
        else add('Approval ' + a.id + ' has an individually attributed account','unknown',[a.id],'Actor is missing, shared, or not explicitly labelled individual. The person behind the action is not established.');
        const explanation = a.body == null ? 'Review text is missing; conditions cannot be assessed.' : condition.test(a.body) ? 'Possible condition word detected; meaning and fulfillment require human inspection.' : 'No listed condition word detected; conditions may be implicit or phrased differently.';
        add('Approval ' + a.id + ' conditions were fulfilled','unknown',[a.id],explanation);
      });
      if (!checks.length) add('Check completed before merge','unknown',[],'No check completion supplied; required checks and their absence cannot be inferred.');
      checks.forEach(c => {
        const refs = [c.id, ...(merge ? [merge.id] : [])]; let status, reason;
        if (!merge) [status,reason] = ['unknown','Merge time is missing.'];
        else if (time(c.at,'') > time(merge.at,'')) [status,reason] = ['contradicted','This check completion occurred after merge. An earlier run may exist outside the bundle.'];
        else if (time(c.at,'') === time(merge.at,'')) [status,reason] = ['unknown','Equal timestamps leave ordering ambiguous.'];
        else [status,reason] = ['supported','This check completed before merge; its result and whether it was required are not assessed.'];
        add('Check ' + c.id + ' completed before merge',status,refs,reason);
        if (!merge || !c.revision || !merge.revision) [status,reason] = ['unknown','Check or merged revision is missing.'];
        else if (c.revision === merge.revision) [status,reason] = ['supported','Check and merge name the same revision.'];
        else [status,reason] = ['contradicted','Check and merge name different revisions; a test merge commit may be legitimate.'];
        add('Check ' + c.id + ' names the merged revision',status,refs,reason);
      });
      return {id:pr.id,timeline,findings};
    });
    return {schema_version:1,notice:'Claims concern supplied events only. Completeness, review validity, human judgment, policy and compliance are not established.',pull_requests};
  }
  return {validate,inspect};
});
