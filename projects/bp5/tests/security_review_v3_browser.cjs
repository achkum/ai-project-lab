// Review proof: execute the real auth event handler with an expired previous owner.
const fs=require('fs'),vm=require('vm'),path=require('path');
const listeners={};
const element={innerHTML:'',open:true,querySelector:()=>element,showModal(){},close(){},addEventListener(k,v){listeners[k]=v}};
const context={console,Headers,FormData:class{get(k){return k==='username'?'bob':'password'}},
 document:{querySelector:()=>element,querySelectorAll:()=>[],addEventListener(){}},
 fetch:async()=>({ok:true,json:async()=>({user:{username:'bob'},csrf:'bob-csrf'})}),
 setTimeout,clearTimeout,AbortController,DOMException};
vm.createContext(context);
let source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8').replace(/boot\(\);\s*$/,'');
vm.runInContext(source+`
 render=()=>{};
 api=async(path)=>path==='api/library'?{situations:[]}:path==='api/missions'?{sessions:[]}:path==='api/profile'?{profile:{}}:{};
 state.user=null; // request() sets this on Alice's expired session.
 state.page='practice';state.session={id:'alice-private-id',turns:[{text:'Alice private conversation'}]};
 state.transcript='Alice private draft';state.legacySessions=[{id:'alice-private-legacy'}];
 state.authMode='login';
 globalThis.inspectState=()=>({user:state.user,session:state.session,transcript:state.transcript,legacySessions:state.legacySessions,page:state.page});
`,context);
(async()=>{
 await listeners.submit({preventDefault(){},target:{id:'auth-form',querySelector(){return {value:'',disabled:false}}}});
 console.log(JSON.stringify(context.inspectState()));
})();
