/* UI-level regression for Save As copies retaining materialized characters. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

let extension;
let asked = 0;
let confirmed = true;
const graph = {
    _nodes: [], links: {}, dirtyCalls: 0, changeCalls: 0,
    setDirtyCanvas() { this.dirtyCalls++; },
    change() { this.changeCalls++; },
    getNodeById(id) { return this._nodes.find(n => n.id === id); },
};
const app = {
    graph,
    canvas: {},
    registerExtension(ext) { extension = ext; },
};
const sandbox = {
    app,
    window: { confirm(text) {
        asked++;
        assert(text.includes('Director Context'));
        return confirmed;
    } },
    console: { log() {}, warn(e) { throw e; } },
    requestAnimationFrame(callback) { callback(); },
    setInterval() {},
    setTimeout() {},
    clearTimeout() {},
    WeakMap, Set, JSON, Object,
};
const code = fs.readFileSync(path.join(__dirname, '../web/director_state.js'), 'utf8')
    .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '');
vm.runInNewContext(code, sandbox, { filename: 'director_state.js' });

function makeDef(type) {
    class FakeNode {
        constructor(id, values) {
            this.id = id;
            this.comfyClass = type;
            this.type = type;
            this.widgets = Object.entries(values).map(([name, value]) => ({ name, value }));
            this.outputs = [];
            this.properties = {};
            this.size = [300, 300];
            this.onNodeCreated?.();
        }
        addWidget(kind, name, value, callback) {
            const w = { kind, name, value, callback };
            this.widgets.push(w);
            return w;
        }
        setDirtyCanvas() {}
        onResize() {}
    }
    extension.beforeRegisterNodeDef(FakeNode, { name: type });
    return FakeNode;
}
function get(node, key) { return node.widgets.find(w => w.name === key)?.value; }
function button(node, key) {
    const w = node.widgets.find(w => w.name === key);
    assert(w && w.kind === 'button', `Missing button ${key}`);
    w.callback();
}
const Snapshot = makeDef('H3DirectorAnalysisSnapshot');
const Editor = makeDef('H3DirectorShotState');
const Reset = makeDef('H3DirectorContextReset');
const Request = makeDef('H3DirectorRequestBuilder');
const snapshot = new Snapshot(1, {
    materialized: true,
    snapshot_raw_analysis: '{"subject":"Alex"}',
    snapshot_director_context: '{"location":"Alex bedroom"}',
});
const editor = new Editor(2, {
    materialized: true,
    shot_direction: 'Alex talks',
    shot_h3_prompt: '<Subject 1> Alex',
    shot_analysis: '{"location":"bedroom"}',
});
const request = new Request(3, { direction: 'New scene: astronaut', duration_seconds: 5.2 });
const extraSnapshot = new Snapshot(4, {
    materialized: true, snapshot_raw_analysis: 'stale', snapshot_director_context: 'stale',
});
const resetNode = new Reset(5, {});
const obvpm = { id: 6, type: 'OBVPM', widgets: [{ name: 'sequence', value: '{"obvpm_timeline":1,"next":{"old":"leave alone"}}' }] };
graph._nodes = [snapshot, editor, request, extraSnapshot, resetNode, obvpm];
const originalTimeline = get(obvpm, 'sequence');
const originalDirection = get(request, 'direction');

// Canceling dialog should preserve frozen state.
confirmed = false;
button(snapshot, 'Reset Director Context (clear saved state)');
assert.strictEqual(get(snapshot, 'materialized'), true);
assert.strictEqual(get(editor, 'shot_h3_prompt'), '<Subject 1> Alex');

// Reset from the optional standalone control: entire open graph, no requeue.
confirmed = true;
button(resetNode, 'Reset Director Context (this workflow)');
for (const n of [snapshot, extraSnapshot]) {
    assert.strictEqual(get(n, 'materialized'), false);
    assert.strictEqual(get(n, 'snapshot_raw_analysis'), '');
    assert.strictEqual(get(n, 'snapshot_director_context'), '');
}
assert.strictEqual(get(editor, 'materialized'), false);
for (const key of ['shot_direction', 'shot_h3_prompt', 'shot_analysis']) {
    assert.strictEqual(get(editor, key), '');
}
assert.strictEqual(get(request, 'direction'), originalDirection);
assert.strictEqual(get(obvpm, 'sequence'), originalTimeline);
assert(graph.changeCalls > 0);

// A JSON save/load of the current widget state must not reintroduce Alex.
const saved = JSON.stringify(graph._nodes.map(node => ({
    type: node.type, widgets_values_named: Object.fromEntries(
        (node.widgets ?? []).filter(w => w.kind !== 'button').map(w => [w.name, w.value])
    ),
})));
assert(!saved.includes('Alex'));
assert(saved.includes('New scene: astronaut'));

// Regression: re-analysis can now store a new context without stale history.
button(editor, 'Reset Director Context (clear saved state)');
assert.strictEqual(get(snapshot, 'snapshot_director_context'), '');
assert.strictEqual(asked, 3);
console.log('PASS frontend context reset: cancel / snapshot / editor / control / serialization / input preservation');
