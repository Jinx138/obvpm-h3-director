/* Test the actual rc24 UI extension without loading ComfyUI. No graph rewrite. */
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert');
let extension;
const scheduled = [];
const graph = { links: {}, setDirtyCanvas(){} };
const app = { graph, registerExtension(ext) { extension = ext; } };
const sandbox = {
  app, console, Array, Set, JSON, Object,
  setTimeout(callback) { scheduled.push(callback); return scheduled.length; },
};
const script = fs.readFileSync(path.join(__dirname, '../web/request_builder_inputs.js'), 'utf8')
  .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '');
vm.runInNewContext(script, sandbox);
function flush() { while (scheduled.length) scheduled.shift()(); }
class Node {
  constructor() {
    this.inputs = [
      {name:'pin_specs',type:'OBVPM_H3_PINSPECS',link:null},
      ...Array.from({length:4}, (_,i)=>({name:`picture_${i+1}`,type:'IMAGE',link:null})),
    ];
    this.widgets = [
      {name:'direction',value:'Direction...',options:{}},
      {name:'reference_roles',value:'',options:{}},
      {name:'duration_seconds',value:5.2,options:{}},
    ];
    this.graph=graph;
    this.size=[480,830];
    this.resizeCalls=0;
    this.onResize=()=>{this.resizeCalls++;};
    this.onNodeCreated?.();
  }
  addInput(name,type) { this.inputs.push({name,type,link:null}); }
  removeInput(index) {
    if(this.inputs[index].link != null) throw new Error('Removed linked slot!');
    this.inputs.splice(index,1);
    for(const [i,slot] of this.inputs.entries()) {
      if(slot.link!=null && graph.links[slot.link]) graph.links[slot.link].target_slot=i;
    }
  }
  disconnectInput(index) {
    const old = this.inputs[index].link;
    this.inputs[index].link = null;
    if (old != null) delete graph.links[old];
  }
  setDirtyCanvas() {}
}
extension.beforeRegisterNodeDef(Node,{name:'H3DirectorRequestBuilder'});
const node = new Node();
flush();
assert.deepStrictEqual(node.inputs.map(s=>s.name), [
  'pin_specs','audio_in','video_in','picture_1','length','hunting','hunt_count']);
// The serialized typed pin from older workflows must become a wildcard
// so it can accept Unbundle's '*' output in the frontend.
assert.strictEqual(node.inputs.find(s=>s.name==='pin_specs').type, '*');
assert.deepStrictEqual(node.widgets.map(w=>w.name),
  ['direction','reference_roles','duration_seconds']);
assert.strictEqual(node.widgets[2].value,5.2);
assert(node.widgets[0].options.getMinHeight()>node.widgets[1].options.getMinHeight());
assert(node.widgets[0].options.getMinHeight()>=220);
assert(node.widgets[1].options.getMaxHeight()<=96);
assert(node.widgets[1].options.getMinHeight()<=56);
assert(node.resizeCalls>0, 'layout recalculated after DOM widget sizing');
node.inputs.find(s=>s.name==='picture_1').link=11;
graph.links[11]={target_slot:3};
node.onConnectionsChange(1,3,true,graph.links[11],node.inputs[3]);
flush();
assert.deepStrictEqual(node.inputs.map(s=>s.name),[
  'pin_specs','audio_in','video_in','picture_1','picture_2','length','hunting','hunt_count']);
node.inputs.find(s=>s.name==='picture_2').link=12;
graph.links[12]={target_slot:4};
node.onConnectionsChange(1,4,true,graph.links[12],node.inputs[4]);
flush();
assert(node.inputs.some(s=>s.name==='picture_3'));
assert.strictEqual(graph.links[11].target_slot,3);
assert.strictEqual(graph.links[12].target_slot,4);

// Old rc23/rc24 workflow widgets had direction, duration, reference_roles.
// After the schema reorder, the duration must still be numeric and roles text.
const oldSaved = new Node();
oldSaved.onConfigure({widgets_values:['legacy direction', 8.3, 'Picture 1: Farrah (character)', '']});
flush();
assert.strictEqual(oldSaved.widgets.find(w=>w.name==='duration_seconds').value,8.3);
assert.strictEqual(oldSaved.widgets.find(w=>w.name==='reference_roles').value,'Picture 1: Farrah (character)');
const newSaved = new Node();
newSaved.onConfigure({widgets_values:['current direction', 'Picture 2: room (location)', 12.0, ''],
  widgets_values_named:{direction:'current direction', reference_roles:'Picture 2: room (location)', duration_seconds:12.0}});
flush();
assert.strictEqual(newSaved.widgets.find(w=>w.name==='duration_seconds').value,12.0);
assert.strictEqual(newSaved.widgets.find(w=>w.name==='reference_roles').value,'Picture 2: room (location)');

// Configure an old rc23 node with a sparse connected picture_4; its link
// must be reindexed when audio/video sockets appear before it.
const legacy=new Node();
legacy.inputs=[
  {name:'pin_specs',type:'OBVPM_H3_PINSPECS',link:null},
  ...Array.from({length:4},(_,i)=>({name:`picture_${i+1}`,type:'IMAGE',link:i===3?44:null})),
];
graph.links[44]=[44,3,0,100,4,'IMAGE'];
legacy.onConfigure?.();
flush();
assert(legacy.inputs.some(s=>s.name==='picture_4' && s.link===44));
assert.strictEqual(legacy.inputs.find(s=>s.name==='pin_specs').type, '*');
assert(legacy.inputs.some(s=>s.name==='picture_5' && s.link===null));
assert(!legacy.inputs.some(s=>s.name==='picture_6'));
assert.strictEqual(graph.links[44][4],6);

// Unlinking 2 removes only the trailing empty 3 while retaining connected 1.
node.inputs.find(s=>s.name==='picture_2').link=null;
node.onConnectionsChange(1,4,false,null,node.inputs[4]);
flush();
assert(!node.inputs.some(s=>s.name==='picture_3'));
assert(node.inputs.some(s=>s.name==='picture_2'));
// New native widget order puts duration below both text areas.
assert.strictEqual(node.widgets[2].value,5.2);
console.log('PASS rc24 frontend: dynamic picture sockets / old-workflow links / widgets preserved');

// Regression: an externally connected widget input was previously sorted
// ahead of the images, shifting the picture link indices by one per reload.
// UI5 removes this legacy socket entirely. The FLOAT widget remains.
const reload = (saved, iteration) => {
  app.configuringGraph = true;
  const loaded = new Node();
  loaded.type = 'H3DirectorRequestBuilder';
  loaded.inputs = saved.inputs.map(x => ({...x}));
  loaded.onConfigure(saved);
  // Simulate a frontend whose initial live link target_slot is stale; the
  // extension must rebind from the saved names only AFTER graph configure.
  graph._nodes = [loaded];
  app.configuringGraph = false;
  extension.afterConfigureGraph();
  flush();
  assert(!loaded.inputs.some(x=>x.name==='duration_seconds'),
    `round ${iteration}: legacy duration socket must be gone`);
  assert(!loaded.inputs.some(x=>x.name==='total_frames'),
    `round ${iteration}: legacy total_frames must be renamed`);
  assert(loaded.inputs.some(x=>x.name==='length' && x.link===205));
  for (const slot of loaded.inputs) {
    if (slot.link != null) {
      const target = graph.links[slot.link];
      assert.strictEqual(target.target_slot,
        loaded.inputs.indexOf(slot),`round ${iteration}: ${slot.name}`);
    }
  }
  return {inputs:loaded.inputs.map(x=>({...x})), widgets_values:['','','5.2']};
};
let saved = {
  inputs: [
    {name:'pin_specs',type:'*',link:201},
    {name:'audio_in',type:'AUDIO',link:null},
    {name:'video_in',type:'VIDEO',link:null},
    {name:'picture_1',type:'IMAGE',link:202},
    {name:'picture_2',type:'IMAGE',link:203},
    {name:'picture_3',type:'IMAGE',link:204},
    {name:'picture_4',type:'IMAGE',link:null},
    {name:'total_frames',type:'*',link:205}, // UI4 serialized name
    {name:'duration_seconds',type:'FLOAT',link:206},
  ],
  widgets_values_named:{reference_roles:'',duration_seconds:5.2},
};
for (const id of [201,202,203,204,205,206])
  graph.links[id] = {target_slot:0};
for (let i=0;i<6;i++) saved=reload(saved,i);
assert.deepStrictEqual(saved.inputs.filter(x=>x.link!=null).map(x=>x.name),
  ['pin_specs','picture_1','picture_2','picture_3','length']);
assert.deepStrictEqual(Object.fromEntries(saved.inputs.filter(x=>x.link!=null).map(x=>[x.name,x.link])), {
  pin_specs:201,picture_1:202,picture_2:203,picture_3:204,
  length:205
});
// Follow-up: hunt diagnostic sockets appended after length must also survive
// repeated graph reloads without stealing any numbered picture connection.
let huntedSaved = {
  ...saved,
  inputs: saved.inputs.map(x => ({...x})).concat([
    {name:'hunting',type:'*',link:207},
    {name:'hunt_count',type:'*',link:208},
  ]),
};
graph.links[207]={target_slot:0}; graph.links[208]={target_slot:0};
for (let i=0; i<6; i++) huntedSaved=reload(huntedSaved,'hunt-'+i);
assert.deepStrictEqual(Object.fromEntries(huntedSaved.inputs.filter(x=>x.link!=null).map(x=>[x.name,x.link])),{
  pin_specs:201,picture_1:202,picture_2:203,picture_3:204,length:205,
  hunting:207,hunt_count:208,
});
console.log('PASS repeated reload: hunt/length/picture connections preserved');

console.log('PASS repeated reload: no target_slot or connection name drift');

// New UI5 graph never creates a duration_seconds socket.
const fresh = new Node();
flush();
assert(!fresh.inputs.some(x => x.name === 'duration_seconds'));
assert(fresh.inputs.some(x => x.name === 'length'));
assert(fresh.inputs.some(x => x.name === 'hunting' && x.type === '*'));
assert(fresh.inputs.some(x => x.name === 'hunt_count' && x.type === '*'));
assert(fresh.widgets.some(x => x.name === 'duration_seconds' && x.value === 5.2));
console.log('PASS UI5: duration FLOAT stays widget-only; length is timeline socket');
