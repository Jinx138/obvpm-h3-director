/* rc25b: separate historical take from NEW purple reservation + safe auto-commit. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
let extension;
const intervals=[],timeouts=new Map(); let nextTimeout=1;
const graph={_nodes:[],links:{},changeCount:0,change(){this.changeCount++;},setDirtyCanvas(){},getNodeById(id){return this._nodes.find(x=>x.id===id);}};
const app={graph,canvas:{},registerExtension(e){extension=e;}};
const sandbox={app,WeakMap,Set,JSON,Object,console:{log(){},warn(...v){throw Error(v.join(' '));}},
    requestAnimationFrame(cb){cb();},
    setInterval(cb){intervals.push(cb);return intervals.length;},
    setTimeout(cb){const id=nextTimeout++;timeouts.set(id,cb);return id;},
    clearTimeout(id){timeouts.delete(id);},
    window:{alert(){throw Error('unexpected alert')},confirm(){return true}},
};
const src=fs.readFileSync(path.join(__dirname,'../web/director_state.js'),'utf8')
 .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/,'');
vm.runInNewContext(src,sandbox,{filename:'director_state.js'});
function def(name){
 class Node{
  constructor(id,values){this.id=id;this.type=name;this.comfyClass=name;this.widgets=Object.entries(values)
    .map(([name,value])=>({name,value}));this.outputs=[];this.properties={};this.size=[400,800];
    this.onNodeCreated?.();}
  addWidget(kind,name,value,callback,options){const w={kind,name,value,callback,options};this.widgets.push(w);return w;}
  setDirtyCanvas(){}onResize(){}
 }
 extension.beforeRegisterNodeDef(Node,{name});return Node;
}
const Recipe=def('H3DirectorRecipePrompt');
const Editor=def('H3DirectorShotState');
const Snapshot=def('H3DirectorAnalysisSnapshot');
const recipe=new Recipe(13,{prompt_text:'HISTORICAL'});
const editor=new Editor(14,{materialized:true,shot_direction:'old',shot_h3_prompt:'OLD PROMPT',shot_analysis:'{}'});
const snapshot=new Snapshot(15,{materialized:true,snapshot_raw_analysis:'old',snapshot_director_context:'{}'});
const doc={obvpm_timeline:1,tracks:[],fps:24,next_draft:null};
const timeline={id:100,type:'H3Timeline',properties:{obvpm_tl_next_sel:false},
 widgets:[{name:'sequence',value:JSON.stringify(doc)}]};
graph._nodes=[timeline,editor,snapshot,recipe];
function w(n,name){return n.widgets.find(x=>x.name===name);}
function setDoc(){timeline.widgets[0].value=JSON.stringify(doc);}
function tick(){intervals.forEach(f=>f());}
function flush(){for(let i=0;i<10&&timeouts.size;i++){
  const todo=[...timeouts.values()];timeouts.clear();todo.forEach(f=>f());
 }}
function makeShot(prompt){editor.onExecuted({director_shot_state:[JSON.stringify({schema:'test',materialized:true,
  shot_direction:'new',shot_h3_prompt:prompt,shot_analysis:'{}'})]});}
extension.setup();assert(intervals.length===1);
tick();flush();assert(w(recipe,'prompt_text').value==='HISTORICAL');
// Purple after Extend is NEW: erase historical text and unfreeze the desk.
doc.next={role:'extend',source:'clipA'};timeline.properties.obvpm_tl_next_sel=true;
setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'');
assert.strictEqual(w(editor,'materialized').value,false);
assert.strictEqual(w(snapshot,'materialized').value,false);
// A genuinely new materialization will auto-commit byte-for-byte.
makeShot('NEW <Subject 1> prompt');
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
assert.deepStrictEqual(JSON.parse(JSON.stringify(recipe.properties.director_recipe_prepared_for)),
  {timeline_id:100,key:JSON.stringify({role:'extend',source:'clipA',source2:null})});
// The user clears the OLD pin before choosing the next Extend. This is NOT
// a generation command: both materialized gates and the prepared Recipe
// stay untouched, whether next is null or a root placement record.
w(snapshot,'materialized').value=true;
doc.next=null;setDoc();tick();flush();
assert.strictEqual(w(editor,'materialized').value,true,'X/clear must not unfreeze Shot Editor');
assert.strictEqual(w(snapshot,'materialized').value,true,'X/clear must not unfreeze Snapshot');
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
doc.next={at:48};setDoc();tick();flush();
assert.strictEqual(w(editor,'materialized').value,true,'root placement must not unfreeze Shot Editor');
assert.strictEqual(w(snapshot,'materialized').value,true,'root placement must not unfreeze Snapshot');
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
// Re-arming even the EXACT SAME operation after a clear must now unfreeze.
doc.next={role:'extend',source:'clipA'};setDoc();tick();flush();
assert.strictEqual(w(editor,'materialized').value,false,'re-arm must unfreeze Shot Editor');
assert.strictEqual(w(snapshot,'materialized').value,false,'re-arm must unfreeze Snapshot');
assert.strictEqual(w(recipe,'prompt_text').value,'','re-arm must clear Recipe');
makeShot('NEW <Subject 1> prompt');
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
// Leave purple and view an old clip: neither field may change by our watcher.
doc.next_draft={values:{'13':{prompt_text:'NEW <Subject 1> prompt'}}};
timeline.properties.obvpm_tl_next_sel=false;w(recipe,'prompt_text').value='HISTORICAL';
setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'HISTORICAL');
assert.strictEqual(w(editor,'materialized').value,true);
// Return to the EXISTING purple reservation: the saved draft stays intact.
timeline.properties.obvpm_tl_next_sel=true;w(recipe,'prompt_text').value='NEW <Subject 1> prompt';
setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
assert.strictEqual(w(editor,'materialized').value,true);
// Adjusting window or a queue's temporary .plan is NOT a new operation.
doc.next.window='70';setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
doc.next.plan={id:'planned-123'};setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'NEW <Subject 1> prompt');
delete doc.next.plan;
// A NEW bridge replaces the previous reservation; an old frozen replay
// can NOT auto-fill the empty prompt, a fresh Editor result can.
doc.next={role:'bridge',source:'clipA',source2:'clipB'};setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'');
assert.strictEqual(w(editor,'materialized').value,false);
editor.widgets.find(x=>x.name==='materialized').value=true;
makeShot('SHOULD NOT AUTO-APPLY FROZEN');
assert.strictEqual(w(recipe,'prompt_text').value,'');
editor.widgets.find(x=>x.name==='materialized').value=false;
makeShot('NEW BRIDGE');
assert.strictEqual(w(recipe,'prompt_text').value,'NEW BRIDGE');
// Back to clip, next_draft for bridge is independent and must restore.
doc.next_draft={values:{'13':{prompt_text:'NEW BRIDGE'}}};
timeline.properties.obvpm_tl_next_sel=false;w(recipe,'prompt_text').value='HISTORICAL';
setDoc();tick();flush();
// Even if the pin temporarily changes while a clip is selected, selecting
// the already prepared purple band must not erase a correctly saved draft.
doc.next={role:'extend',source:'clipZ'};setDoc();tick();flush();
doc.next={role:'bridge',source:'clipA',source2:'clipB'};
timeline.properties.obvpm_tl_next_sel=true;w(recipe,'prompt_text').value='NEW BRIDGE';
setDoc();tick();flush();
assert.strictEqual(w(recipe,'prompt_text').value,'NEW BRIDGE');
// No implicit automatic copy when target Recipe node is ambiguous.
const extra=new Recipe(42,{prompt_text:'SEPARATE'});graph._nodes.push(extra);
doc.next={role:'extend',source:'clipC'};setDoc();tick();flush();
assert.strictEqual(w(extra,'prompt_text').value,'SEPARATE');
// Legacy workflow without Recipe node: clear must still not unfreeze, but
// arming a real pin must retain the established UI5 auto-unfreeze behavior.
graph._nodes=[timeline,editor,snapshot];
w(editor,'materialized').value=true;w(snapshot,'materialized').value=true;
doc.next=null;setDoc();tick();flush();
assert.strictEqual(w(editor,'materialized').value,true);
assert.strictEqual(w(snapshot,'materialized').value,true);
doc.next={role:'prepend',source:'clipZ'};setDoc();tick();flush();
assert.strictEqual(w(editor,'materialized').value,false);
assert.strictEqual(w(snapshot,'materialized').value,false);
console.log('PASS rc25b: clear pin stays frozen / re-arm unlocks / auto-commit / historical clip / existing draft / frozen guard / ambiguity');
