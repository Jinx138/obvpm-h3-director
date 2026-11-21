/* Regression: modern LinkMap, nested subgraph, dynamic images, legacy saved layout. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const timers=[];
let extension;
const root={_nodes:[],links:new Map(),setDirtyCanvas(){}};
const app={graph:root,configuringGraph:false,registerExtension(ext){extension=ext;}};
const code=fs.readFileSync(path.join(__dirname,'../web/request_builder_inputs.js'),'utf8')
  .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/,'');
vm.runInNewContext(code,{app,console,setTimeout(f){timers.push(f);},requestAnimationFrame(f){timers.push(f);}});
function flush(){let n=0;while(timers.length){timers.shift()();if(++n>120)throw Error('timer loop');}}
class Request {
  constructor(graph,saved) {
    this.type='H3DirectorRequestBuilder';this.graph=graph;
    this.size=[450,700];this.inputs=saved.inputs.map(s=>({...s}));
    this.widgets=[
      {name:'direction',options:{},value:'action'},
      {name:'reference_roles',options:{},value:''},
      {name:'duration_seconds',options:{},value:5.2},
    ];
  }
  addInput(name,type){this.inputs.push({name,type,link:null});}
  removeInput(index){
    assert.equal(this.inputs[index].link,null,'cannot remove connected input');
    this.inputs.splice(index,1);
  }
  setDirtyCanvas(){}
  onResize(){}
}
extension.beforeRegisterNodeDef(Request,{name:'H3DirectorRequestBuilder'});
const subgraph={_nodes:[],links:new Map(),setDirtyCanvas(){}};
root._nodes=[{type:'SubgraphNode',subgraph}];
const wiring={pin_specs:100,length:101,duration_seconds:102,hunting:103,hunt_count:104,picture_1:105,picture_2:106};
for(const id of Object.values(wiring))subgraph.links.set(id,{id,target_slot:0});
let saved={inputs:[
  {name:'pin_specs',type:'*',link:100},
  {name:'audio_in',type:'AUDIO',link:null},
  {name:'video_in',type:'VIDEO',link:null},
  {name:'picture_1',type:'IMAGE',link:105},
  {name:'picture_2',type:'IMAGE',link:106},
  {name:'picture_3',type:'IMAGE',link:null},
  {name:'length',type:'*',link:101},
  {name:'hunting',type:'*',link:103},
  {name:'hunt_count',type:'*',link:104},
  {name:'duration_seconds',type:'FLOAT',link:102},
]};
const fixed=['pin_specs','audio_in','video_in','length','duration_seconds','hunting','hunt_count'];
function validate(node,label){
  const actual=node.inputs.map(s=>s.name);
  assert.deepEqual(actual.slice(0,7),fixed,`${label}: fixed order`);
  for(const [name,id] of Object.entries(wiring)){
    const slot=node.inputs.find(s=>s.name===name);
    assert.equal(slot?.link,id,`${label}: ${name} link ID`);
    assert.equal(subgraph.links.get(id)?.target_slot,node.inputs.indexOf(slot),`${label}: ${name} target_slot`);
  }
  assert.equal(new Set(node.inputs.filter(s=>s.link!=null).map(s=>s.link)).size,Object.keys(wiring).length,`${label}: no link ID duplicated`);
}
for(let round=0;round<6;round++){
  const node=new Request(subgraph,saved);subgraph._nodes=[node];
  app.configuringGraph=true;
  node.onConfigure(saved);
  app.configuringGraph=false;
  // Simulate stale target indices on workflow restore.
  for(const id of Object.values(wiring)) subgraph.links.get(id).target_slot=0;
  extension.afterConfigureGraph();flush();
  validate(node,`reload ${round}`);
  saved={inputs:node.inputs.map(s=>({...s}))};
}
const node=subgraph._nodes[0];
let fixedBefore=Object.fromEntries(fixed.map(k=>[k,node.inputs.findIndex(s=>s.name===k)]));
let slot=node.inputs.find(s=>s.name==='picture_3');
slot.link=107;wiring.picture_3=107;subgraph.links.set(107,{id:107,target_slot:node.inputs.indexOf(slot)});
node.onConnectionsChange?.(1,node.inputs.indexOf(slot),true,subgraph.links.get(107),slot);flush();
validate(node,'add picture 3');
assert(node.inputs.some(s=>s.name==='picture_4'));
assert.deepEqual(Object.fromEntries(fixed.map(k=>[k,node.inputs.findIndex(s=>s.name===k)])),fixedBefore);
// Connecting/disconnecting an IMAGE never moves the three timeline diagnostics.
slot.link=null;wiring.picture_3=undefined;delete wiring.picture_3;
subgraph.links.delete(107);
node.onConnectionsChange?.(1,node.inputs.indexOf(slot),false,null,slot);flush();
validate(node,'disconnect picture 3');
assert(!node.inputs.some(s=>s.name==='picture_4'));
console.log('PASS v0.6.3: Map-backed links, nested subgraph reload x6, fixed slot stability');
