const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const file=JSON.parse(fs.readFileSync(path.join(__dirname,'../examples/H3-Director-Core-Workspace.json')));
const definition=file.definitions.subgraphs[0];
const callbacks=[];let ext;
function graph(data){
  const g={_nodes:[],links:new Map(),change(){},setDirtyCanvas(){},getNodeById(id){return this._nodes.find(n=>String(n.id)===String(id));}};
  for(const l of data.links){let v=Array.isArray(l)?{id:l[0],origin_id:l[1],origin_slot:l[2],target_id:l[3],target_slot:l[4]}:l;g.links.set(v.id,v);}
  for(const n of data.nodes){const node={...n,comfyClass:n.type,graph:g,widgets:Object.entries(n.widgets_values_named??{}).map(([name,value])=>({name,value})),addWidget(type,name,value,callback,options){const w={type,name,value,callback,options};this.widgets.push(w);return w;},setDirtyCanvas(){},onResize(){}};g._nodes.push(node);}
  return g;
}
// Modern frontend normalizes local node IDs, including -10/-20, to strings.
for (const l of definition.links) { l.origin_id=String(l.origin_id); l.target_id=String(l.target_id); }
const root=graph(file),inner=graph(definition);inner.name=definition.name;inner.inputs=definition.inputs;inner.outputs=definition.outputs;root.getNodeById(15).subgraph=inner;
const host=root.getNodeById(15),snapshot=inner.getNodeById(3),editor=root.getNodeById(11),builder=root.getNodeById(1),flavour=root.getNodeById(14);
const val=(n,k)=>n.widgets.find(w=>w.name===k);
const put=(n,k,v)=>{let w=val(n,k);if(w)w.value=v;else n.widgets.push({name:k,value:v});};
put(snapshot,'materialized',true);put(snapshot,'snapshot_raw_analysis','old');put(snapshot,'snapshot_director_context','old');put(editor,'materialized',true);put(editor,'shot_h3_prompt','p');put(editor,'shot_validation','PASS — valid');put(editor,'shot_analysis','analysis');put(flavour,'genre','auto');put(editor,'Reset Director Context (clear saved state)',null);
put(inner.getNodeById(2),'seed',42);put(inner.getNodeById(6),'seed',43);
const app={graph:root,canvas:{},registerExtension(e){ext=e;},queuePrompt(){return true;}};
const context={app,console:{log(){},warn(...args){throw Error(args.join(' '));}},window:{confirm(){return true;}},requestAnimationFrame(f){f();},setInterval(f){callbacks.push(f);},setTimeout(){},clearTimeout(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/director_state.js'),'utf8').replace(/^import .*\n/,''),context);
const evaluate=(code)=>vm.runInContext(code,context);context.host=host;context.snapshot=snapshot;context.editor=editor;context.builder=builder;
assert.equal(evaluate('upstreamRequestBuilders(snapshot)[0] === builder'),true);assert.equal(evaluate('downstreamEditors(snapshot)[0] === editor'),true);
evaluate('syncDirectorCore()');assert.equal(val(host,'materialized').value,true);assert.match(val(host,'Director Status').value,/^SAVED/);assert.equal(val(editor,'Reset Director Context (clear saved state)').hidden,true);
assert.deepEqual(host.widgets.map(w=>w.name),['analysis_seed','editor_seed','materialized','Director Status','Pass #1 Direction','View Pass #1 Direction','View Status','Re-analyze (refresh Pass #1)','Reset Director Context']);
put(snapshot,'snapshot_raw_analysis',JSON.stringify({intent:{dominant_action:'opens the door'},subjects:[{description:'private inventory'}]}));evaluate('syncDirectorCore()');assert.equal(val(host,'Pass #1 Direction').value,'opens the door');assert.match(val(inner.getNodeById(16),'Pass #1 Direction').value,/opens the door/);assert.doesNotMatch(val(inner.getNodeById(16),'Pass #1 Direction').value,/private inventory/);
val(host,'editor_seed').callback(87);assert.equal(val(inner.getNodeById(6),'seed').value,87);
editor.__directorValidationFresh=true;editor.__directorValidatedPrompt='p';editor.__directorCaptureRevision=1;evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^PASS/);
put(editor,'shot_validation','PASS — valid\nAUTO-NORMALIZED — inserted markers');evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^PASS · repaired/);assert.match(evaluate('buildCoreStatusReport(host)'),/current captured result[\s\S]*Normalization applied; final validator checks passed[\s\S]*AUTO-NORMALIZED — inserted markers/);
put(editor,'shot_validation','FAIL\n- missing speech\nAUTO-NORMALIZED — inserted markers');evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^FAIL · H3 validation — View Status/);assert.match(evaluate('buildCoreStatusReport(host)'),/remaining findings are not waived[\s\S]*missing speech/);
// Viewer uses the same local report and does not run the workflow.
evaluate('viewSavedGen2Trace = (node,key,title,content) => { host.__testStatusReport = content; };');val(host,'View Status').callback();assert.match(host.__testStatusReport,/missing speech/);
put(editor,'shot_validation','WARNING\n- environment <Subject 3> from <Picture 5> is defined but not used in detailed_description\nAUTO-NORMALIZED — inserted markers');evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^WARNING · normalized/);assert.match(evaluate('buildCoreStatusReport(host)'),/advisory warnings remain/);
editor.__directorValidationFresh=false;evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^SAVED WARNING · View Status/);editor.__directorValidationFresh=true;
put(editor,'shot_validation','PASS — valid');evaluate('syncDirectorCore()');
put(editor,'shot_h3_prompt','edited');evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^WARNING/);put(editor,'shot_h3_prompt','p');
put(flavour,'genre','fantasy');evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^SAVED/);
val(host,'Re-analyze (refresh Pass #1)').callback();assert.equal(val(snapshot,'materialized').value,false);assert.equal(val(editor,'materialized').value,false);assert.equal(val(editor,'shot_h3_prompt').value,'p');
val(host,'Reset Director Context').callback();assert.equal(val(snapshot,'snapshot_raw_analysis').value,'');assert.equal(val(editor,'shot_h3_prompt').value,'');evaluate('syncDirectorCore()');assert.match(val(host,'Pass #1 Direction').value,/No analysis/);assert.match(evaluate('buildCoreStatusReport(host)'),/No validation report captured/);assert.doesNotMatch(evaluate('buildCoreStatusReport(host)'),/missing speech/);assert.equal(val(flavour,'genre').value,'fantasy');
console.log('PASS: boundary traversal, mirrored seed/freeze, status invalidation, re-analyze, reset');

// Normal numeric serialized boundary IDs must work as well.
for (const l of inner.links.values()) {l.origin_id=Number(l.origin_id);l.target_id=Number(l.target_id);}
assert.equal(evaluate('upstreamRequestBuilders(snapshot)[0] === builder'),true);
assert.equal(evaluate('downstreamEditors(snapshot)[0] === editor'),true);
// An actually disconnected editor must still show a warning.
for(const o of host.outputs) o.links=[];
evaluate('syncDirectorCore()');assert.match(val(host,'Director Status').value,/^WARNING.*connect Shot Editor/);
console.log('PASS: numeric/string boundary IDs, redundant Reset hidden, actual disconnection warning');
