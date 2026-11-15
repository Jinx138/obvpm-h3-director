/* rc25b.2: successful root-tail advancement, not pin clearing or generic edits. */
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
let extension;
const intervals = [], timeouts = new Map(); let nextTimeout = 1;
const graph = {
  _nodes: [], links: {}, change() {}, setDirtyCanvas() {},
  getNodeById(id) { return this._nodes.find(x => x.id === id); }
};
const app = { graph, canvas: {}, registerExtension(ext) { extension = ext; } };
const sandbox = {
  app, WeakMap, Set, JSON, Object,
  console: { log() {}, warn(...v) { throw Error(v.join(' ')); } },
  requestAnimationFrame(f) { f(); },
  setInterval(f) { intervals.push(f); return intervals.length; },
  setTimeout(f) { const id = nextTimeout++; timeouts.set(id, f); return id; },
  clearTimeout(id) { timeouts.delete(id); },
  window: { alert() { throw Error('unexpected alert'); }, confirm() { return true; } },
};
const js = fs.readFileSync(path.join(__dirname, '../web/director_state.js'), 'utf8')
  .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '');
vm.runInNewContext(js, sandbox, { filename: 'director_state.js' });
function def(type) {
  class Node {
    constructor(id, values) {
      this.id = id; this.type = type; this.comfyClass = type;
      this.widgets = Object.entries(values).map(([name, value]) => ({ name, value }));
      this.properties = {}; this.outputs = []; this.size = [400, 800];
      this.onNodeCreated?.();
    }
    addWidget(kind, name, value, callback, options) {
      const w = { kind, name, value, callback, options }; this.widgets.push(w); return w;
    }
    setDirtyCanvas() {} onResize() {}
  }
  extension.beforeRegisterNodeDef(Node, { name: type }); return Node;
}
const Recipe = def('H3DirectorRecipePrompt');
const Editor = def('H3DirectorShotState');
const Snapshot = def('H3DirectorAnalysisSnapshot');
const recipe = new Recipe(13, { prompt_text: 'ROOT 62' });
const editor = new Editor(14, {
  materialized: true, shot_direction: 'old direction', shot_h3_prompt: 'ROOT 62', shot_analysis: '{}'
});
const snapshot = new Snapshot(15, {
  materialized: true, snapshot_raw_analysis: 'old', snapshot_director_context: '{}'
});
const track = (clips) => ({ id: 'V1', kind: 'video', clips });
const pathClip = (n) => ({ path: `/test/takes/clip_${String(n).padStart(5,'0')}.mp4` });
let doc = { obvpm_timeline: 1, fps: 24, loop: false, tracks: [track([pathClip(62)])],
  next_draft: { values: { '13': { prompt_text: 'ROOT 62' } } } };
const timeline = { id: 100, type: 'H3Timeline', properties: { obvpm_tl_next_sel: true },
  widgets: [{ name: 'sequence', value: JSON.stringify(doc) }] };
graph._nodes = [timeline, snapshot, editor, recipe];
const w = (node, name) => node.widgets.find(x => x.name === name);
function setDoc() { timeline.widgets[0].value = JSON.stringify(doc); }
function tick() { intervals.forEach(f => f()); }
function flush() {
  for (let i = 0; i < 10 && timeouts.size; i++) {
    const todo = [...timeouts.values()]; timeouts.clear(); todo.forEach(f => f());
  }
}
function cycle() { setDoc(); tick(); flush(); }
function freeze(prompt = 'FROZEN') {
  w(snapshot, 'materialized').value = true;
  w(editor, 'materialized').value = true;
  w(recipe, 'prompt_text').value = prompt;
}
function unchanged(where, prompt = 'FROZEN') {
  assert.strictEqual(w(snapshot, 'materialized').value, true, `${where}: snapshot must stay frozen`);
  assert.strictEqual(w(editor, 'materialized').value, true, `${where}: editor must stay frozen`);
  assert.strictEqual(w(recipe, 'prompt_text').value, prompt, `${where}: recipe untouched`);
}
function makeShot(prompt) {
  editor.onExecuted({ director_shot_state: [JSON.stringify({
    schema: 'test', materialized: true, shot_direction: 'new', shot_h3_prompt: prompt, shot_analysis: '{}'
  })] });
}
extension.setup(); assert.strictEqual(intervals.length, 1);
cycle(); unchanged('initial saved Root', 'ROOT 62');
// Selecting and revisiting a Root with no new take is NOT a new generation.
freeze(); timeline.properties.obvpm_tl_next_sel = false; cycle();
timeline.properties.obvpm_tl_next_sel = true; cycle(); unchanged('root revisit');
// Clearing a pin, or moving the root landing marker, must be inert.
doc.next = { role: 'extend', source: 'clip62' }; cycle();
freeze(); delete doc.next; cycle(); unchanged('X/clear');
doc.next = { at: 1800 }; cycle(); unchanged('root placement metadata');
delete doc.next; cycle(); unchanged('no pin again');
// No reset for cuts, seams, gaps, old-clip replacement, repositioning, plans.
doc.tracks[0].clips[0].exit = 128; cycle(); unchanged('trim');
doc.tracks[0].clips[0].seam = { flush: 'none' }; cycle(); unchanged('seam');
doc.tracks[0].clips.push({ gap: 24 }); cycle(); unchanged('gap');
doc.tracks[0].clips.push({ plan: 'planned-123', frames: 121 }); cycle(); unchanged('plan');
doc.tracks[0].clips[0].path = '/test/takes/clip_replaced.mp4'; cycle(); unchanged('replacement');
// Exact splits can append the SAME existing media path; never treat as fresh.
const reused = doc.tracks[0].clips[0].path;
doc.tracks[0].clips.push({ path: reused, enter: 24 }); cycle(); unchanged('same-media split');
doc.tracks[0].clips.pop(); cycle();
doc.tracks[0].clips[0].path = pathClip(62).path; cycle();
// The genuine Add to Timeline event: new, UNIQUE take path at V1 end.
doc.tracks[0].clips.push(pathClip(63)); cycle();
assert.strictEqual(w(recipe, 'prompt_text').value, '', 'new Root must clear old recipe');
assert.strictEqual(w(editor, 'materialized').value, false, 'new Root must unfreeze editor');
assert.strictEqual(w(snapshot, 'materialized').value, false, 'new Root must unfreeze analysis');
makeShot('FRESH ROOT 63');
assert.strictEqual(w(recipe, 'prompt_text').value, 'FRESH ROOT 63', 'materialized shot auto-commits');
const prepared = JSON.parse(JSON.stringify(recipe.properties.director_recipe_prepared_for));
assert.strictEqual(prepared.timeline_id, 100);
assert(prepared.key.includes('clip_00063.mp4'), 'new Root identity must use new tail anchor');
// No repeated reset while the same Root stays selected (including doc drafts).
freeze('PREPARED ROOT 63');
doc.next_draft = { values: { '13': { prompt_text: 'PREPARED ROOT 63' } } }; cycle();
unchanged('draft update', 'PREPARED ROOT 63');
timeline.properties.obvpm_tl_next_sel = false; w(recipe, 'prompt_text').value = 'HISTORICAL'; cycle();
timeline.properties.obvpm_tl_next_sel = true; w(recipe, 'prompt_text').value = 'PREPARED ROOT 63'; cycle();
unchanged('prepared Root revisit', 'PREPARED ROOT 63');
// A second real Root advance must be recognized, and can be filled again.
doc.tracks[0].clips.push(pathClip(64)); cycle();
assert.strictEqual(w(recipe, 'prompt_text').value, '', 'second new Root clears prior prompt');
assert.strictEqual(w(editor, 'materialized').value, false);
assert.strictEqual(w(snapshot, 'materialized').value, false);
makeShot('FRESH ROOT 64');
assert.strictEqual(w(recipe, 'prompt_text').value, 'FRESH ROOT 64');
// Change only clip ordering (not the media set): cannot start a new Root.
freeze();
doc.tracks[0].clips.reverse(); cycle(); unchanged('move/reorder');
// A newly appended clip while a PIN is active is NOT a Root generation.
doc.next = { role: 'extend', source: 'clip64' }; cycle();
freeze(); doc.tracks[0].clips.push(pathClip(65)); cycle(); unchanged('append with pin');
// A new video added while a historic clip is selected is also inert.
delete doc.next; timeline.properties.obvpm_tl_next_sel = false; cycle();
freeze(); doc.tracks[0].clips.push(pathClip(66)); cycle(); unchanged('append while historical selected');
timeline.properties.obvpm_tl_next_sel = true; cycle(); unchanged('late Root selection');
// Switching OBVPM project or project timeline, even where the second
// timeline has an appended clip, is not a newly added Root take.
freeze(); doc.project = { id: 'project-1', timeline: 'timeline-A' }; cycle();
doc.project.timeline = 'timeline-B';
doc.tracks[0].clips.push(pathClip(68)); cycle(); unchanged('project timeline switch');
// Same project/timeline: a new generated Root can still advance normally.
doc.tracks[0].clips.push(pathClip(69)); cycle();
assert.strictEqual(w(recipe,'prompt_text').value,'', 'same project root must clear');
makeShot('PROJECT ROOT');
assert.strictEqual(w(recipe,'prompt_text').value,'PROJECT ROOT');
// A runtime file list is a baseline on reload, never an instruction.
const loaded = { ...doc, tracks: [track([pathClip(62), pathClip(63), pathClip(64), pathClip(65), pathClip(66)])] };
const reloadTimeline = { id: 101, type: 'H3Timeline', properties: { obvpm_tl_next_sel: true },
  widgets: [{ name: 'sequence', value: JSON.stringify(loaded) }] };
graph._nodes.push(reloadTimeline); freeze(); cycle(); unchanged('new timeline node loaded');
// A fresh 015 workflow begins as an empty legacy string, before its
// first JSON store. Accepting its first Root must also prepare the desk.
graph._nodes.pop();
const legacyTimeline = { id: 102, type: 'H3Timeline', properties: { obvpm_tl_next_sel: true },
  widgets: [{ name: 'sequence', value: '\n' }, { name: 'pin_state', value: '' }] };
graph._nodes.push(legacyTimeline);
freeze('LEGACY ROOT'); cycle(); unchanged('empty legacy baseline', 'LEGACY ROOT');
legacyTimeline.widgets[0].value = JSON.stringify({ obvpm_timeline: 1, fps: 24,
  tracks: [track([pathClip(1)])] });
tick(); flush();
assert.strictEqual(w(recipe, 'prompt_text').value, '', 'first Root must clear');
assert.strictEqual(w(editor, 'materialized').value, false);
assert.strictEqual(w(snapshot, 'materialized').value, false);
graph._nodes.pop();
// Multiple Recipe nodes: never auto-wipe any target silently.
const second = new Recipe(30, { prompt_text: 'OTHER' }); graph._nodes.push(second);
freeze(); doc.tracks[0].clips.push(pathClip(67)); cycle(); unchanged('ambiguous Recipe');
assert.strictEqual(w(second, 'prompt_text').value, 'OTHER');
console.log('PASS rc25b.2: Root tail add / unique anchor / auto-prepare / repeated Roots / historical/restore/pin/trim/split/plan guards');
