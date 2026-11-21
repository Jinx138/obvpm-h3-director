const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { test } = require('node:test');

function makeHarness() {
    const extensions = [];
    const events = [];
    const nodes = new Map();
    const graph = {
        _nodes: [], links: {}, change(){ events.push('graphChange'); },
        setDirtyCanvas(){}, getNodeById(id){ return nodes.get(id); },
    };
    let behavior = () => true;
    const calls = [];
    const app = {
        graph, canvas: {}, registerExtension(ext){ extensions.push(ext); },
        queuePrompt(index, count, options){ calls.push({index,count,options}); return behavior(); },
    };
    const notes = [];
    const sandbox = {
        app, console:{ log(){}, warn(){} }, window:{ alert(s){notes.push(s);}, confirm(){return true;} },
        requestAnimationFrame(f){f();}, setInterval(){}, setTimeout(){}, clearTimeout(){},
        WeakMap, Set, Object, JSON,
    };
    const code = fs.readFileSync(path.join(__dirname,'../web/director_state.js'),'utf8')
        .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/,'');
    vm.runInNewContext(code,sandbox);
    const ext = extensions.find(x=>x.name==='obvpm-director.shot-state');
    assert(ext);
    class Editor {
        constructor(id, frozen=true) {
            this.id=id;this.type='H3DirectorShotState';this.comfyClass=this.type;
            this.widgets=[
                {name:'materialized',value:frozen, callback(){events.push('freezeChange');}},
                {name:'shot_direction',value:'approved direction'},
                {name:'shot_h3_prompt',value:'approved prompt'},
                {name:'shot_analysis',value:'approved analysis'},
            ];
            this.size=[450,850];this.outputs=[];this.properties={};this.graph=graph;
            graph._nodes.push(this);nodes.set(id,this);
            this.onNodeCreated?.();
        }
        addWidget(kind,name,value,callback,options){ const w={kind,name,value,callback,options};this.widgets.push(w);return w;}
        setDirtyCanvas(){} onResize(){}
    }
    ext.beforeRegisterNodeDef(Editor,{name:'H3DirectorShotState'});
    return {graph,calls,notes,events,Editor,setBehavior(fn){behavior=fn}};
}

test('DIRECT is placed immediately below materialized, never serialized', () => {
    const {Editor} = makeHarness();
    const editor = new Editor(42);
    const index=editor.widgets.findIndex(w=>w.name==='materialized');
    const direct=editor.widgets[index+1];
    assert.equal(direct.name,'▶ DIRECT');
    assert.equal(direct.kind,'button');
    assert.equal(direct.options.serialize,false);
    assert.equal(editor.widgets.filter(w=>w.name==='▶ DIRECT').length,1);
});

test('DIRECT unfreezes only editor, queues targeted node, ignores double click', async () => {
    const h=makeHarness(); const editor=new h.Editor(42,true); const snapshot={id:5,materialized:true};
    h.graph._nodes.push(snapshot);
    let done;
    h.setBehavior(()=>new Promise(resolve=>{done=resolve}));
    const action=editor.widgets.find(w=>w.name==='▶ DIRECT').callback;
    const pending=action();
    await action();
    assert.equal(h.calls.length,1);
    assert.equal(h.calls[0].index,0);
    assert.equal(h.calls[0].count,1);
    assert.deepEqual(Array.from(h.calls[0].options.queueNodeIds),['42']);
    assert.equal(editor.widgets.find(w=>w.name==='materialized').value,false);
    assert.equal(snapshot.materialized,true);
    done(true);
    assert.equal(await pending,true);
    assert.equal(editor.widgets.find(w=>w.name==='shot_h3_prompt').value,'approved prompt');
    const next=action();
    assert.equal(h.calls.length,2);
    done(true);await next;
});

test('DIRECT keeps manually unfrozen editor and respects targeted queue', async ()=>{
    const h=makeHarness(); const editor=new h.Editor(13,false);
    h.setBehavior(async()=>true);
    const ok=await editor.widgets.find(w=>w.name==='▶ DIRECT').callback();
    assert.equal(ok,true);assert.equal(editor.widgets[0].value,false);
    assert.deepEqual(Array.from(h.calls[0].options.queueNodeIds),['13']);
});

test('DIRECT restores previous freeze if queue returns false', async ()=>{
    const h=makeHarness(); const editor=new h.Editor(9,true);
    h.setBehavior(async()=>false);
    const ok=await editor.widgets.find(w=>w.name==='▶ DIRECT').callback();
    assert.equal(ok,false);assert.equal(editor.widgets[0].value,true);
    assert.equal(h.notes.length,1);
});

test('DIRECT restores previous freeze if queue throws', async ()=>{
    const h=makeHarness(); const editor=new h.Editor(9,true);
    h.setBehavior(async()=>{throw Error('offline')});
    const ok=await editor.widgets.find(w=>w.name==='▶ DIRECT').callback();
    assert.equal(ok,false);assert.equal(editor.widgets[0].value,true);
    assert.equal(h.notes.length,1);
});

test('DIRECT aborts for non-root node (no unsafe full-workflow fallback)', async ()=>{
    const h=makeHarness(); const editor=new h.Editor(9,true);
    h.graph.getNodeById=()=>null;
    const ok=await editor.widgets.find(w=>w.name==='▶ DIRECT').callback();
    assert.equal(ok,false);assert.equal(editor.widgets[0].value,true);
    assert.equal(h.calls.length,0);assert.equal(h.notes.length,1);
});

test('DIRECT may rematerialize through original onExecuted payload', async ()=>{
    const h=makeHarness(); const editor=new h.Editor(31,true); h.setBehavior(async()=>true);
    assert.equal(await editor.widgets.find(w=>w.name==='▶ DIRECT').callback(),true);
    assert.equal(editor.widgets[0].value,false);
    editor.onExecuted({director_shot_state:[JSON.stringify({
        schema:'shot',schema_version:1,materialized:true,shot_h3_prompt:'new prompt',
        shot_direction:'new direction',shot_analysis:'new analysis',
    })]});
    assert.equal(editor.widgets[0].value,true);
    assert.equal(editor.widgets.find(w=>w.name==='shot_h3_prompt').value,'new prompt');
});
