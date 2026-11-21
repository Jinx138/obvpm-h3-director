/* v0.6.1-dev2: executed/manual direction+roles history persists in the owning
   Request Builder's ComfyUI workflow JSON; no cross-workflow localStorage. */
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert');
let extension;
let storageAccesses = 0;
let confirms = 0, allowDelete = true;
const graph = { _nodes:[], setDirtyCanvas() {}, change() {} };
const app = { graph, canvas:{}, registerExtension(e) { extension = e; } };
const sandbox = {
  app, console: {info(){},warn(...args){throw new Error(args.join(' '));}},
  window: {get localStorage(){storageAccesses++;throw new Error('global browser history forbidden');},
    confirm(){confirms++;return allowDelete;}},
};
const file = path.join(__dirname, '../web/request_builder_history.js');
const code = fs.readFileSync(file, 'utf8').replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '');
vm.runInNewContext(code, sandbox, {filename:file});
class Builder {
  constructor(id, direction='Fresh direction', reference_roles='') {
    this.id=id; this.type='H3DirectorRequestBuilder'; this.comfyClass=this.type;
    this.properties={};
    this.widgets=[{name:'direction',value:direction},{name:'reference_roles',value:reference_roles},
      {name:'duration_seconds',value:5.2}]; this.outputs=[];
    this.onNodeCreated?.();
  }
  addWidget(kind,name,value,callback,options={}) {
    const widget={kind,name,value,callback,options};this.widgets.push(widget);return widget;
  }
  setDirtyCanvas() {}
  serialize() {
    return JSON.parse(JSON.stringify({
      properties:this.properties,
      widgets_values_named:Object.fromEntries(this.widgets.filter(x=>x.options?.serialize!==false).map(x=>[x.name,x.value])),
    }));
  }
  configure(saved) {
    this.properties=JSON.parse(JSON.stringify(saved.properties));
    for(const [name,value] of Object.entries(saved.widgets_values_named)) {
      const w=this.widgets.find(w=>w.name===name);if(w)w.value=value;
    }
    this.onConfigure?.(saved);
  }
}
extension.beforeRegisterNodeDef(Builder,{name:'H3DirectorRequestBuilder'});
const get = (b,n) => b.widgets.find(w=>w.name===n);
const press=(b,name)=>{const w=get(b,name); assert(w && w.kind==='button',`No button ${name}`);w.callback();};
const pairs=b=>b.properties.director_request_history_v1||[];
const executed=(b,d,r)=>b.onExecuted({director_request_history:[JSON.stringify({direction:d,reference_roles:r})]});
const a=new Builder(1,'Unsaved A','Picture 1: Aster (character)');
const initial=a.widgets.map(x=>x.name);
for(const label of ['History · Save','History · Delete','History · ◀ Previous','History · Next ▶']) {
  const w=get(a,label); assert(w && w.options.serialize===false);
}
assert(get(a,'director_history_status').options.serialize===false);
assert.strictEqual(pairs(a).length,0,'typing does not add history');
press(a,'History · Save');
assert.strictEqual(pairs(a).length,1);
assert.strictEqual(pairs(a)[0].direction,'Unsaved A');
executed(a,'Unsaved A','Picture 1: Aster (character)');
assert.strictEqual(pairs(a).length,1,'repeated runs deduplicate a pair');
get(a,'direction').value='Performed B';
get(a,'reference_roles').value='Picture 2: Bryn (character)';
executed(a,'Performed B','Picture 2: Bryn (character)');
assert.strictEqual(pairs(a).length,2);
press(a,'History · ◀ Previous');
assert.strictEqual(get(a,'direction').value,'Unsaved A');
assert.strictEqual(get(a,'reference_roles').value,'Picture 1: Aster (character)');
get(a,'direction').value='Edited A';
press(a,'History · Next ▶');
assert.strictEqual(get(a,'direction').value,'Performed B');
press(a,'History · Next ▶');
assert.strictEqual(get(a,'direction').value,'Edited A','edited draft restored');
press(a,'History · Save');
assert.strictEqual(pairs(a).length,3);
assert.strictEqual(pairs(a)[2].direction,'Edited A');
allowDelete=false; press(a,'History · Delete');
assert.strictEqual(pairs(a).length,3);
allowDelete=true; press(a,'History · Delete');
assert.strictEqual(pairs(a).length,2);assert.strictEqual(confirms,2);
assert.strictEqual(get(a,'duration_seconds').value,5.2);

// Another workflow (even with the same node ID) starts with no history.
const b=new Builder(1,'Different workflow direction','Different role');
assert.strictEqual(pairs(b).length,0);
press(b,'History · ◀ Previous');
assert.strictEqual(get(b,'direction').value,'Different workflow direction');
executed(b,'B execution','Picture 4: Room');
assert.strictEqual(pairs(b).length,1);
assert.strictEqual(pairs(a).length,2,'workflow B execution must not mutate workflow A');
assert.notStrictEqual(pairs(a)[0].direction,pairs(b)[0].direction);

// Saved workflow JSON retains history; reloading restores both history and form.
const workflowJSON=a.serialize();
assert(Array.isArray(workflowJSON.properties.director_request_history_v1));
assert(!Object.keys(workflowJSON.widgets_values_named).some(x=>x.includes('history')),
  'no history buttons / status serialized as input widgets');
const aReloaded=new Builder(1);
aReloaded.configure(workflowJSON);
assert.strictEqual(pairs(aReloaded).length,2);
assert.strictEqual(get(aReloaded,'direction').value,get(a,'direction').value);
press(aReloaded,'History · ◀ Previous');
assert.strictEqual(get(aReloaded,'direction').value,pairs(aReloaded).at(-1).direction);
assert.strictEqual(pairs(b).length,1,'reload of A must not touch B');

// Queued execution payload still stores actual submitted fields, not later edits.
get(b,'direction').value='Draft created during long render';
executed(b,'Previously executed','Picture 3: Town');
assert.strictEqual(get(b,'direction').value,'Draft created during long render');
press(b,'History · ◀ Previous');
press(b,'History · Next ▶');
assert.strictEqual(get(b,'direction').value,'Draft created during long render');
assert.strictEqual(storageAccesses,0,'must not touch localStorage');
assert(initial.every(name=>get(a,name)));
assert(get(a,'director_history_status').value.startsWith('History:'));
console.log('PASS v0.6.1 history: workflow-local storage / serialized reload / isolated workflows / execution / manual save / delete / navigation / edited drafts');
