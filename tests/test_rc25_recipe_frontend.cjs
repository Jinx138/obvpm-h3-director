/* Exact UI extension test: explicit handoff, no automatic sync, no hidden widgets. */
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
let extension;
let confirms = 0, alerts = [];
let confirmValue = true;
let chosenId = null;
const graph = {
  _nodes: [], links: {}, changes: 0,
  change() { this.changes++; },
  setDirtyCanvas() {},
};
const app = { graph, canvas: {}, registerExtension(ext) {extension = ext;} };
const sandbox = {
  app, console: {log() {}, warn(e) {throw new Error(e);}},
  window: {
    alert(m) {alerts.push(m);},
    confirm(m) {confirms++; return confirmValue;},
    prompt(_text) { return chosenId; },
  },
  requestAnimationFrame(callback) {callback();},
  setInterval() {}, setTimeout() {}, clearTimeout() {}, WeakMap, Set, JSON, Object,
};
const script = fs.readFileSync(path.join(__dirname, '../web/director_state.js'), 'utf8')
  .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '');
vm.runInNewContext(script, sandbox, {filename: 'director_state.js'});

function nodeDef(name) {
  class Node {
    constructor(id, widgets) {
      this.id=id; this.type=name; this.comfyClass=name;
      this.widgets=Object.entries(widgets).map(([name,value])=>({name,value}));
      this.outputs=[]; this.size=[450,850]; this.properties={};
      this.onNodeCreated?.();
    }
    addWidget(kind,name,value,callback,options) {
      const w={kind,name,value,callback,options}; this.widgets.push(w); return w;
    }
    setDirtyCanvas() {}
    onResize() {}
  }
  extension.beforeRegisterNodeDef(Node,{name});
  return Node;
}
const Editor=nodeDef('H3DirectorShotState');
const Recipe=nodeDef('H3DirectorRecipePrompt');
const recipe=new Recipe(12,{prompt_text:''});
const editor=new Editor(11,{
  materialized:false,shot_direction:'a',shot_analysis:'{}',shot_h3_prompt:'FIRST',
});
graph._nodes=[editor,recipe];
function w(n,k){return n.widgets.find(x=>x.name===k);}
function apply(){w(editor,'Apply approved prompt to Recipe').callback();}
// Unmaterialized editor MUST NOT copy stale text left in the widget.
apply(); assert.strictEqual(w(recipe,'prompt_text').value,'');
assert(alerts.at(-1).includes('Freeze/materialize'));
// Deliberate application has exact prompt text and no new wire.
w(editor,'materialized').value=true;
const value='subject_definitions:\n<Subject 1> Farrah\n\n<d>[English] Hello</d>';
w(editor,'shot_h3_prompt').value=value;
apply(); assert.strictEqual(w(recipe,'prompt_text').value,value);
assert.strictEqual(w(editor,'shot_h3_prompt').value,value);
assert(graph.changes>0);
assert.strictEqual(recipe.inputs,undefined);
// OBVPM Sync may replace Recipe prompt on clip selection: Director cannot mutate it.
w(recipe,'prompt_text').value='HISTORICAL CLIP';
assert.strictEqual(w(editor,'shot_h3_prompt').value,value);
// Applying a new prompt to a historical clip requires explicit confirmation.
confirmValue=false; apply();
assert.strictEqual(w(recipe,'prompt_text').value,'HISTORICAL CLIP');
confirmValue=true; apply();
assert.strictEqual(w(recipe,'prompt_text').value,value);
assert.strictEqual(confirms,2);
// With multiple Recipe nodes, never choose silently.
const extra=new Recipe(15,{prompt_text:'other clip'});
graph._nodes.push(extra);
w(editor,'shot_h3_prompt').value='second approved prompt';
chosenId=null; apply();
assert.strictEqual(w(recipe,'prompt_text').value,value);
assert.strictEqual(w(extra,'prompt_text').value,'other clip');
chosenId='15'; apply();
assert.strictEqual(w(extra,'prompt_text').value,'second approved prompt');
assert.strictEqual(w(recipe,'prompt_text').value,value);
// Do not overwrite Director state just because Recipe got restored.
assert.strictEqual(w(editor,'shot_h3_prompt').value,'second approved prompt');
console.log('PASS rc25a: explicit recipe handoff / clip sync isolation / multi-target safety');
