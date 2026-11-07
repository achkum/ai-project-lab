const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path'), crypto = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8').replace(/boot\(\);\s*$/, '');
const root = {innerHTML: '', focus() {}}, dialog = {querySelector() {return this}, addEventListener() {}, showModal() {}, close() {}};
const document = {querySelector: s => s === '#app' ? root : s === '#auth' ? dialog : null, querySelectorAll: () => [], addEventListener() {}};
const mission = {id: 'm', title: 'Task', goal: 'Ask', opening_sv: 'Hej', steps: [{id: 'step', objective: 'ask', intents: []}], completion_objectives: ['ask'], phrases: []};
const session = {id: 's', mission_id: 'm', current_step: 'step', status: 'in_progress', snapshot: {mission, criteria: [], criterion_links: []}, turns: [{role: 'assistant', text: 'Hej'}], evidence: [], completed_objectives: []};
const message = 'Language checking is temporarily at capacity. Keep your draft and try again shortly.';
const requests = []; let blocked = true;
const env = {document, Headers, AbortController, DOMException, crypto, window: {scrollTo() {}, isSecureContext: true}, navigator: {}, console, setTimeout, clearTimeout, Set, Map, Date, Error, String, Number, Blob, URL,
  fetch: async (url, options) => {
    const body = JSON.parse(options.body); requests.push(body);
    if (blocked) return {ok: false, status: 429, headers: new Headers({'Retry-After': '2'}), json: async () => ({error: message})};
    return {ok: true, status: 200, json: async () => ({session, matched: false, feedback: 'Try another reply.'})};
  }};
vm.createContext(env); vm.runInContext(source, env); env.sessionFixture = session; env.missionFixture = mission;
vm.runInContext("state.user={id:'owner'};state.ownerId='owner';state.csrf='csrf';state.ownerEpoch=1;state.session=sessionFixture;state.mission=missionFixture;state.situation={level:'high'};state.page='practice';state.transcript='  Min långa svenska text.  ';state.originalTranscript='Min långa svenska text.';state.voiceEdited=true;state.support=['hint'];render()", env);
(async () => {
  await vm.runInContext('send()', env);
  assert.equal(vm.runInContext('state.transcript', env), '  Min långa svenska text.  ');
  assert.equal(vm.runInContext('state.originalTranscript', env), 'Min långa svenska text.');
  assert.equal(vm.runInContext('state.voiceEdited', env), true);
  assert.equal(vm.runInContext('state.support.join()', env), 'hint');
  assert.equal(vm.runInContext('state.error', env), message);
  assert.equal(vm.runInContext('state.busy', env), false);
  assert(root.innerHTML.includes('temporarily at capacity'));
  blocked = false; await vm.runInContext('send()', env);
  assert.equal(requests.length, 2); assert.equal(requests[0].request_id, requests[1].request_id);
  assert.equal(requests[1].text, 'Min långa svenska text.');
  assert.equal(requests[1].input_mode, 'voice'); assert.equal(requests[1].transcript_edited, true);
  assert.equal(vm.runInContext('state.transcript', env), '');
  console.log('PASS: capacity rejection preserves draft, voice provenance, support and retry identity');
})().catch(error => {console.error(error); process.exitCode = 1});
