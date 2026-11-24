const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const { test } = require('node:test');
const source = name => fs.readFileSync(path.join(__dirname,'../web',name),'utf8').replace(/^import .*\n/,'');
function stateHarness() {
 const graph={_nodes:[],setDirtyCanvas(){},change(){}};
 const app={graph,registerExtension(){}};
 const ctx=vm.createContext({app,console,requestAnimationFrame(f){f();}});
 vm.runInContext(source('director_state.js'),ctx);
 return {ctx,graph,run:expr=>vm.runInContext(expr,ctx)};
}
test('Apply follows freeze, nonempty prompt, Recipe availability; restores native draw',()=>{
 const h=stateHarness(), draw=()=>{};
 const frozen={name:'materialized',value:false},prompt={name:'shot_h3_prompt',value:'prompt'},button={name:'Apply approved prompt to Recipe',options:{serialize:false},draw};
 h.ctx.editor={type:'H3DirectorShotState',widgets:[frozen,prompt,button],setDirtyCanvas(){}};
 const sync=()=>h.run('syncApplyButton(editor)');
 sync();assert.equal(button.draw,draw);assert.equal(button.options.color,undefined);
 frozen.value=true;sync();assert.equal(button.draw,draw);
 h.graph._nodes.push({type:'H3DirectorRecipePrompt',widgets:[{name:'prompt_text',value:''}]});sync();assert.equal(button.options.color,'#286c43');assert.notEqual(button.draw,draw);
 prompt.value='  ';sync();assert.equal(button.draw,draw);assert.equal(button.options.color,undefined);
 prompt.value='edited prompt';sync();assert.equal(button.options.color,'#286c43');
 h.run('setMaterialized(editor,false)');assert.equal(button.draw,draw);assert.equal(button.options.color,undefined);
});
test('Pass #1 semantic view excludes inventory and handles saved, pending and malformed snapshots',()=>{
 const h=stateHarness(); const obj={asset_analysis:[{description:'INVENTORY_PRIVATE'}],subjects:[{description:'SUBJECT_PRIVATE'}],intent:{dominant_action:'walks through door',behavior_progression:'walk then stop',camera_intent:'steady wide',sound_plan:'room tone'},performance_tracks:[{actor_id:'walker',reference_subject:1,identity:'IDENTITY_PRIVATE',motion_details:'turns head'}],interaction_dynamics:[{coordination:'waits for partner'}]};
 const w={name:'snapshot_raw_analysis',value:'```json\n'+JSON.stringify(obj)+'\n```'},frozen={name:'materialized',value:true};h.ctx.snapshot={widgets:[w,frozen]};
 const view=()=>h.run('passOneDirection(snapshot)');let text=view();assert.match(text,/Captured Pass #1/);for(const s of ['walks through door','walk then stop','steady wide','room tone','turns head','waits for partner']) assert.ok(text.includes(s));assert.doesNotMatch(text,/PRIVATE|reference_subject|asset_analysis/);
 frozen.value=false;assert.match(view(),/refresh pending/);w.value=JSON.stringify(obj)+'}';assert.match(view(),/walks through door/);w.value=JSON.stringify(obj)+JSON.stringify(obj);assert.equal(view(),'');w.value='{"intent": {"dominant_action":"broken"}';assert.equal(view(),'');w.value='';assert.equal(view(),'');
});
test('History DOM buttons use two rows with independent action handlers, nonserialized',()=>{
 let ext; const app={graph:{change(){},setDirtyCanvas(){}},registerExtension(e){ext=e;}};
 const document={createElement(){return {style:{},children:[],events:{},append(child){this.children.push(child);},addEventListener(type,f){this.events[type]=f;}};}};
 const ctx=vm.createContext({app,document,console:{info(){},warn(){}},window:{confirm(){return true;}}});vm.runInContext(source('request_builder_history.js'),ctx);
 class Builder {
  constructor(){this.properties={};this.widgets=[{name:'direction',value:'A'},{name:'reference_roles',value:''}];this.onNodeCreated();}
  addWidget(type,name,value,callback,options){const w={type,name,value,callback,options};this.widgets.push(w);return w;}
  addDOMWidget(name,type,element,options){const w={name,type,element,options};this.widgets.push(w);return w;}
  setDirtyCanvas(){}
 }
 ext.beforeRegisterNodeDef(Builder,{name:'H3DirectorRequestBuilder'}); const b=new Builder();const rows=b.widgets.filter(w=>w.element);assert.equal(rows.length,2);assert.deepEqual(rows.map(w=>w.element.children.map(x=>x.textContent)),[['◀ Previous','Next ▶'],['Save','Delete']]);assert.ok(rows.every(w=>w.serialize===false&&w.options.serialize===false));
 for(const w of rows){
  assert.equal(w.options.getMinHeight(),20);assert.equal(w.options.getMaxHeight(),20);assert.equal(w.options.getHeight(),20);assert.equal(w.options.margin,0);
  for(const css of ['grid-template-rows:20px','min-height:20px!important','max-height:20px!important','--comfy-widget-min-height:20px','--comfy-widget-max-height:20px','align-content:start'])assert.ok(w.element.style.cssText.includes(css),css);
  for(const b of w.element.children)assert.ok(b.style.cssText.includes('max-height:20px'));
 }

 const click=(r,c)=>rows[r].element.children[c].events.click({stopPropagation(){}});
 click(1,0);assert.equal(b.properties.director_request_history_v1.length,1);b.widgets[0].value='B';click(0,0);assert.equal(b.widgets[0].value,'A');click(0,1);assert.equal(b.widgets[0].value,'B');click(1,0);assert.equal(b.properties.director_request_history_v1.length,2);click(1,1);assert.equal(b.properties.director_request_history_v1.length,1);
});

test('Pass #1 readout uses labeled frozen fallback, never pending fallback',()=>{
 const h=stateHarness();h.ctx.snapshot={widgets:[{name:'materialized',value:true},{name:'snapshot_raw_analysis',value:''}]};h.ctx.editor={widgets:[{name:'materialized',value:true},{name:'shot_analysis',value:JSON.stringify({intent:{dominant_action:'opens the door'},subjects:[{description:'PRIVATE'}]})}]};
 assert.match(h.run('passOneDirection(snapshot,editor)'),/^Saved Pass #1 · Composer-normalized/);assert.match(h.run('passOnePreview(passOneDirection(snapshot,editor))'),/^Saved · opens the door$/);assert.doesNotMatch(h.run('passOneDirection(snapshot,editor)'),/PRIVATE/);
 h.ctx.snapshot.widgets[0].value=false;assert.equal(h.run('passOneDirection(snapshot,editor)'),'');
});
test('Internal status readout is read-only, nonserialized, updated and cleared in place',()=>{
 const h=stateHarness(); h.ctx.document={createElement(){return {style:{},value:''}}};
 h.ctx.status={widgets:[],addDOMWidget(name,type,element,options){const w={name,type,element,options};this.widgets.push(w);return w;}};
 h.run('updatePassOneReadout(status,"Captured Pass #1\\nAction: opens the door")');
 const w=h.ctx.status.widgets[0]; assert.equal(w.element.readOnly,true);assert.equal(w.serialize,false);assert.equal(w.options.serialize,false);assert.equal(w.options.getMaxHeight(),240);assert.match(w.element.value,/opens the door/);
 h.run('updatePassOneReadout(status,"")');assert.equal(h.ctx.status.widgets.length,1);assert.match(w.element.value,/No analysis captured/);
});

test('Core status respects final verdict, repair notes, stale state and remaining warnings',()=>{
 const h=stateHarness();
 h.ctx.snapshot={widgets:[{name:'materialized',value:true},{name:'snapshot_raw_analysis',value:'{}'},{name:'snapshot_director_context',value:'{}'}]};
 const report={name:'shot_validation',value:'PASS — valid'};
 h.ctx.editor={widgets:[{name:'materialized',value:true},{name:'shot_h3_prompt',value:'p'},report],__directorValidationFresh:true,__directorValidatedPrompt:'p'};
 const status=()=>h.run('coreStatus(null,snapshot,editor,true)');
 assert.match(status(),/^PASS · H3/);
 report.value+='\nAUTO-NORMALIZED — inserted speaker markers.';assert.match(status(),/^PASS · repaired/);
 report.value='FAIL\n- Missing required speech.\nAUTO-NORMALIZED — bracketed Picture label.';assert.match(status(),/^FAIL · H3 validation — View Status/);
 report.value='EXTEND CONTINUITY MODE\nWARNING — START BOUNDARY FRAME UNAVAILABLE\nPASS — valid\nAUTO-NORMALIZED — corrected prefix.';assert.match(status(),/^WARNING · normalized/);
 report.value='PASS — valid\nNOTICE — context not available';assert.match(status(),/^PASS · H3/);
 report.value='AUTO-NORMALIZED — repaired something.';assert.match(status(),/^WARNING · unrecognized/);
 report.value='PASS — valid\nAUTO-NORMALIZED — corrected prefix.';
 h.ctx.editor.__directorValidationFresh=false;assert.match(status(),/^SAVED/);
 h.ctx.editor.__directorValidationFresh=true;h.ctx.editor.widgets[1].value='edited';assert.match(status(),/^WARNING · prompt edited/);
 h.ctx.editor.widgets[1].value='p';h.ctx.snapshot.widgets[1].value='';assert.match(status(),/^FAIL · frozen snapshot incomplete/);
});
test('Core readouts use two-line fixed-height nonserialized DOM widgets with full tooltip',()=>{
 const h=stateHarness();h.ctx.document={createElement(){return {style:{},children:[],append(...children){this.children.push(...children)}}}};
 h.ctx.node={widgets:[],addDOMWidget(name,type,element,options){const w={name,type,element,options};this.widgets.push(w);return w;},setDirtyCanvas(){}};
 h.run('addCoreReadout(node,"Director Status","IDLE");addCoreReadout(node,"Pass #1 Direction","Action pending")');
 for(const w of h.ctx.node.widgets){assert.equal(w.serialize,false);assert.equal(w.options.serialize,false);assert.equal(w.options.getMinHeight(),42);assert.equal(w.options.getMaxHeight(),42);assert.match(w.element.children[1].style.cssText,/-webkit-line-clamp:2/);}
 h.run('updateReadout(node,node.widgets[0],"PASS · repaired — View Status")');
 const text=h.ctx.node.widgets[0].element.children[1];assert.equal(text.textContent,'PASS · repaired — View Status');assert.equal(text.title,text.textContent);assert.equal(text.style.color,'#86c597');
 h.run('updateReadout(node,node.widgets[0],"FAIL · H3 validation — View Status")');assert.equal(text.style.color,'#e99b96');
 h.run('updateReadout(node,node.widgets[0],"IDLE")');assert.equal(text.style.color,'');
});
