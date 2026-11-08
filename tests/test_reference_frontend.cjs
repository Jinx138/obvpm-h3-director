/* rc14: status is compact, non-serialized, and follows the actual upstream Request Builder. */
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert');
let extension;
const graph = {
  links: {}, _nodes: [],
  getNodeById(id) { return this._nodes.find(n => n.id === id); },
  setDirtyCanvas() {}, change() {},
};
const app = { graph, canvas: {}, registerExtension(e) { extension = e; } };
const sandbox = { app, console, WeakMap, Set, JSON, Object, window: { confirm: () => true },
  requestAnimationFrame: cb=>cb(), setInterval(){}, setTimeout(){}, clearTimeout(){} };
const script = fs.readFileSync(path.join(__dirname, '../web/director_state.js'),'utf8')
  .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '');
vm.runInNewContext(script,sandbox);
function define(type) {
  class Node {
    constructor(id, fields) {
      this.id=id; this.type=type; this.comfyClass=type;
      this.widgets=Object.entries(fields || {}).map(([name,value])=>({name,value}));
      this.inputs=[]; this.outputs=[]; this.size=[460,300];
      this.onNodeCreated?.();
    }
    addWidget(kind,name,value,callback,options={}) {
      const w={kind,name,value,callback,options}; this.widgets.push(w); return w;
    }
    setDirtyCanvas(){}
    onResize(){}
  }
  extension.beforeRegisterNodeDef(Node,{name:type});
  return Node;
}
const Builder=define('H3DirectorRequestBuilder');
const Snapshot=define('H3DirectorAnalysisSnapshot');
const Compose=define('H3DirectorAnalysisCompose');
const b=new Builder(1,{direction:'Alex smiles',reference_roles:''});
const g=new Snapshot(2,{materialized:true});
const c=new Compose(3,{});
graph._nodes=[b,g,c];
graph.links={ 12:{origin_id:1,target_id:2},13:{origin_id:2,target_id:3} };
g.inputs=[{name:'director_context',link:12}];
c.inputs=[{name:'director_context',link:13}];
const status = n=>n.widgets.find(w=>w.name==='director_reference_status');
assert(status(b)); assert(status(c));
assert.strictEqual(status(b).options.serialize,false);
assert.strictEqual(status(c).options.serialize,false);
const result={director_reference_status:[JSON.stringify({summary:'◆ P1 Alex [character; user prompt] · ● P2 Living Room [environment; auto]'})]};
c.onExecuted(result);
assert(status(b).value.includes('P1 Alex')); assert(status(c).value.includes('P2 Living Room'));
const dir=b.widgets.find(w=>w.name==='direction');
dir.value='new story'; dir.callback(dir.value);
assert(status(b).value.includes('Re-analyze'));
console.log('PASS frontend reference status: propagated, non-serialized, invalidated on edit');
