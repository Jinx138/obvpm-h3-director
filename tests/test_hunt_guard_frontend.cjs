const assert = require('node:assert/strict');
const fs = require('fs'), vm = require('vm'), path = require('path');
const { test } = require('node:test');

function harness({ dropFrontendScope = false, dropApiScope = false } = {}) {
    const actions = [], submitted = [], messages = [];
    const editor = { id: 42, type: 'H3DirectorShotState', widgets: [{name:'materialized',value:true}] };
    const timeline = { id: 55, type: 'H3Timeline', outputs:[{name:'hunting'}] };
    const app = {
        graph: { _nodes:[editor,timeline] }, processingQueue:false,
        registerExtension(ext) { this.extension = ext; },
    };
    const api = {
        fetchApi(route, init) {
            const data = JSON.parse(init.body);submitted.push(data);
            return Promise.resolve({status:200,json: async () => ({prompt_id:'fake',number:0})});
        },
        queuePrompt(number, data, options) {
            const opts = dropApiScope ? {} : options;
            const body = JSON.stringify({ prompt:data.output, ...(opts?.partialExecutionTargets && {
                partial_execution_targets:opts.partialExecutionTargets
            }) });
            return this.fetchApi('/prompt', {method:'POST',body});
        },
    };
    app.queuePrompt = async function(number, batch, opts) {
        actions.push({ number,batch,opts });
        const ids = Array.isArray(opts) ? opts : opts?.queueNodeIds;
        // Simulate third-party app wrapper dropping target options.
        const partialExecutionTargets = dropFrontendScope ? undefined : ids;
        app.processingQueue = true;
        try {
            return await api.queuePrompt(number, {output: { '42': {class_type: 'H3DirectorShotState',inputs:{}} },workflow:{}},
                {partialExecutionTargets});
        } finally { app.processingQueue = false; }
    };
    const sandbox = {app,api,console:{info(x){messages.push(x);},warn(x){messages.push(x);}},Array,Set,JSON};
    const code = fs.readFileSync(path.join(__dirname,'../web/director_hunt_guard.js'),'utf8')
        .replace(/^import \{ app \} from "\.\.\/\.\.\/scripts\/app\.js";\s*/, '')
        .replace(/^import \{ api \} from "\.\.\/\.\.\/scripts\/api\.js";\s*/, '');
    vm.runInNewContext(code,sandbox);
    app.extension.setup();
    return {app,api,editor,timeline,actions,submitted,messages};
}

test('No confirmation on normal Full Run, including frozen Editor and Hunt Timeline', async () => {
    const h = harness();const response = await h.app.queuePrompt(0,1);
    assert(response);assert.equal(h.actions.length,1);assert.equal(h.submitted.length,1);
    assert.equal(h.submitted[0].partial_execution_targets,undefined);
    assert.equal(h.editor.widgets[0].value,true);
});

test('DIRECT targets only Editor and clamps batch to one', async () => {
    const h=harness();await h.app.queuePrompt(0,4,{queueNodeIds:['42']});
    assert.equal(h.actions.length,1);assert.equal(h.actions[0].batch,1);
    assert.deepEqual(JSON.parse(JSON.stringify(h.actions[0].opts.queueNodeIds)),['42']);
    assert.deepEqual(JSON.parse(JSON.stringify(h.submitted[0].partial_execution_targets)),['42']);
});

test('Native selected Run cannot include H3-generation descendants alongside Editor',async()=>{
    const h=harness();await h.app.queuePrompt(0,6,{queueNodeIds:['42','70','80']});
    assert.equal(h.actions.length,1);assert.equal(h.actions[0].batch,1);
    assert.deepEqual(JSON.parse(JSON.stringify(h.submitted[0].partial_execution_targets)),['42']);
});

test('Even if a frontend extension drops queueNodeIds, the API request stays scoped',async()=>{
    const h=harness({dropFrontendScope:true});await h.app.queuePrompt(0,1,{queueNodeIds:['42']});
    assert.deepEqual(JSON.parse(JSON.stringify(h.submitted[0].partial_execution_targets)),['42']);
});

test('Even if an API extension drops partial targets, the POST body stays scoped',async()=>{
    const h=harness({dropApiScope:true});await h.app.queuePrompt(0,1,{queueNodeIds:['42']});
    assert.deepEqual(JSON.parse(JSON.stringify(h.submitted[0].partial_execution_targets)),['42']);
});

test('Extra app.queuePrompt from beforeQueued hook is rejected',async()=>{
    const h=harness();const orig=h.api.queuePrompt;
    h.api.queuePrompt=async function(...args){
        const extra = await h.app.queuePrompt(0,3);
        assert.equal(extra,false);
        return orig.apply(this,args);
    };
    await h.app.queuePrompt(0,1,{queueNodeIds:['42']});
    assert.equal(h.submitted.length,1);assert.match(h.messages.join(' '),/suppressed/);
});

test('Extra direct API submission is rejected, not converted into a second Director job',async()=>{
    const h=harness(); const origFetch=h.api.fetchApi;
    h.api.fetchApi=function(route,init) {return origFetch.call(this,route,init)};
    const originalApp=h.app.queuePrompt;
    h.app.queuePrompt=async (...args)=>{
        // The underlying guarded API itself refuses duplicate calls within the same scope.
        return originalApp(...args);
    };
    const oldApi=h.api.queuePrompt;let ignored;
    // Simulate an extension calling api.queuePrompt twice during one app queue.
    h.api.queuePrompt=async function(...args) {
        const res=await oldApi.apply(this,args);
        ignored=await oldApi.apply(this,args);
        return res;
    };
    await h.app.queuePrompt(0,1,{queueNodeIds:['42']});
    assert.equal(h.submitted.length,1);
    assert.equal(ignored.prompt_id,null);
    assert.match(h.messages.join(' '),/suppressed/);
});

test('Unrelated selected node remains unmodified',async()=>{
    const h=harness();await h.app.queuePrompt(0,2,{queueNodeIds:['91']});
    assert.equal(h.actions[0].batch,2);
    assert.deepEqual(JSON.parse(JSON.stringify(h.submitted[0].partial_execution_targets)),['91']);
});

test('Multi-editor target is not silently redirected to one Editor',async()=>{
    const h=harness();h.app.graph._nodes.push({id:73,type:'H3DirectorShotState'});
    await h.app.queuePrompt(0,2,{queueNodeIds:['42','73']});
    assert.equal(h.actions[0].batch,2);
    assert.deepEqual(JSON.parse(JSON.stringify(h.submitted[0].partial_execution_targets)),['42','73']);
});

test('If queue hooks are missing, targeted Director request is refused',async()=>{
    const h=harness();h.api.fetchApi=null;
    const response=await h.app.queuePrompt(0,1,{queueNodeIds:['42']});
    assert.equal(response,false);assert.equal(h.submitted.length,0);
});

test('Scope is restored after an API error', async()=>{
    const h=harness();h.api.queuePrompt=()=>{throw Error('test exception')};
    await assert.rejects(h.app.queuePrompt(0,1,{queueNodeIds:['42']}),/test exception/);
    // Full run must still be allowed and unscoped after exception.
    h.api.queuePrompt=async ()=>true;
    await h.app.queuePrompt(0,1);
    assert.equal(h.actions.length,2);
});

test('Idempotent setup does not double-wrap app.queuePrompt',async()=>{
    const h=harness();let q=h.app.queuePrompt;h.app.extension.setup();
    assert.equal(h.app.queuePrompt,q);
});


test('A second low-level POST is ignored without triggering a ComfyUI error modal', async () => {
    const h = harness();
    const oldApi = h.api.queuePrompt;
    let synthetic;
    h.api.queuePrompt = async function (...args) {
        const first = await oldApi.apply(this, args);
        const duplicate = await h.api.fetchApi('/prompt', {
            method: 'POST',
            body: JSON.stringify({prompt:{'99':{class_type:'UnrelatedGenerator',inputs:{}}}}),
        });
        synthetic = await duplicate.json();
        return first;
    };
    await h.app.queuePrompt(0, 1, {queueNodeIds: ['42']});
    assert.equal(h.submitted.length,1);
    assert.equal(synthetic.prompt_id,null);
    assert.equal(h.messages.filter(m => m.includes('suppressed')).length, 1);
});

test('A third low-level POST is ignored but warning is logged only once',async()=>{
    const h=harness(); const oldApi=h.api.queuePrompt;
    h.api.queuePrompt=async function(...args) {
        const original=await oldApi.apply(this,args);
        for(let i=0;i<2;i++){
            const ignored=await h.api.fetchApi('/prompt', {method:'POST',body:'{}'});
            assert.equal(ignored.status,200);
            assert.equal((await ignored.json()).prompt_id,null);
        }
        return original;
    };
    await h.app.queuePrompt(0,1,{queueNodeIds:['42']});
    assert.equal(h.submitted.length,1);
    assert.equal(h.messages.filter(x=>x.includes('suppressed')).length,1);
});
