import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Director-only queue isolation. This does NOT read or change OBVPM's Hunt
// settings. A native "Run selected node" or ▶ DIRECT targeting a Shot Editor
// must send ONE partial-execution request for that Editor, not a whole-graph
// request or extra Hunt jobs, even when another extension drops queue options.
//
// The frontend calls beforeQueued() on every widget in the graph, even during
// partial execution, so an extension can inadvertently enqueue more work.
// The guard refuses reentrant requests during a Director-targeted submission.
// For normal full Run, including frozen Directors, it does absolutely nothing.

const EDITOR = "H3DirectorShotState";
let activeScope = null;

// A duplicate is NOT an accepted job. Return a valid but empty receipt to
// callers that expect a response; never synthesize a prompt_id.
function duplicateReceipt() {
    return { prompt_id: null, number: 0, node_errors: {} };
}

function reportSuppressed(scope) {
    if (scope.duplicateLogged) return;
    scope.duplicateLogged = true;
    console.info(`[OBVPM Director] Extra Director queue request suppressed (Editor #${scope.editorId}); no additional job queued.`);
}

function ignoredFetchResponse() {
    // ComfyApi.queuePrompt expects a 200 Response with .json(). A 204 or
    // rejected promise becomes a large execution-error modal in ComfyUI.
    const json = JSON.stringify(duplicateReceipt());
    if (typeof Response === "function") {
        return Promise.resolve(new Response(json, {
            status: 200, headers: { "Content-Type": "application/json" },
        }));
    }
    return Promise.resolve({ status: 200, ok: true,
        json: async () => duplicateReceipt(),
        text: async () => json,
    });
}

function rootNodes() {
    return app.graph?._nodes ?? app.graph?.nodes ?? [];
}

function isShotEditor(node) {
    return node && (node.type === EDITOR || node.comfyClass === EDITOR);
}

function editorById(value) {
    if (value === undefined || value === null) return null;
    const strId = String(value);
    return rootNodes().find(node => isShotEditor(node) && String(node.id) === strId) ?? null;
}

function getIds(optionsOrIds) {
    if (Array.isArray(optionsOrIds)) return optionsOrIds;
    return Array.isArray(optionsOrIds?.queueNodeIds) ? optionsOrIds.queueNodeIds : [];
}

function selectedEditor(optionsOrIds) {
    const ids = getIds(optionsOrIds);
    if (!ids.length) return null;
    const editors = ids.map(editorById).filter(Boolean);
    // If several different editors are requested at once, do not silently
    // guess which one should run. Avoid altering deliberate multi-editor runs.
    return editors.length === 1 ? editors[0] : null;
}

function isPromptUrl(route) {
    return typeof route === "string" && /^\/?(?:api\/)?prompt(?:\?.*)?$/.test(route);
}

function preparePromptBody(init, scope) {
    if (!init || typeof init.body !== "string") {
        throw new Error("[OBVPM Director] Cannot verify the scoped /prompt payload; Director job refused.");
    }
    let body;
    try { body = JSON.parse(init.body); }
    catch { throw new Error("[OBVPM Director] Invalid /prompt JSON; Director job refused."); }
    if (!body || typeof body !== "object" || !body.prompt || typeof body.prompt !== "object") {
        throw new Error("[OBVPM Director] Invalid /prompt structure; Director job refused.");
    }
    // Reject rather than risk an unscoped run if the target disappears during
    // ComfyUI's async queue preparation.
    if (!editorById(scope.editorId)) {
        throw new Error("[OBVPM Director] Shot Editor disappeared before submission; queue refused.");
    }
    body.partial_execution_targets = [scope.editorId];
    return { ...init, body: JSON.stringify(body) };
}

app.registerExtension({
    name: "obvpm-director.targeted-queue-safety",
    setup() {
        if (typeof app.queuePrompt !== "function" || app.queuePrompt.__obvpmDirectorTargetGuard) return;

        // Lowest-level backstop: this is where ComfyUI sends the actual /prompt
        // request. Restore partial_execution_targets if a third-party wrapper
        // dropped it; never submit a whole-workflow prompt for Director-only.
        if (typeof api?.fetchApi === "function" && !api.fetchApi.__obvpmDirectorTargetGuard) {
            const originalFetch = api.fetchApi;
            const guardedFetch = function(route, init, ...rest) {
                if (!activeScope || !isPromptUrl(route) || init?.method?.toUpperCase() !== "POST") {
                    return originalFetch.call(this, route, init, ...rest);
                }
                if (activeScope.submitted) {
                    reportSuppressed(activeScope);
                    return ignoredFetchResponse();
                }
                const scopedInit = preparePromptBody(init, activeScope);
                activeScope.submitted = true;
                console.info(`[OBVPM Director] Scoped /prompt to Shot Editor #${activeScope.editorId}.`);
                return originalFetch.call(this, route, scopedInit, ...rest);
            };
            guardedFetch.__obvpmDirectorTargetGuard = true;
            api.fetchApi = guardedFetch;
        }

        if (typeof api?.queuePrompt === "function" && !api.queuePrompt.__obvpmDirectorTargetGuard) {
            const originalApiQueue = api.queuePrompt;
            const guardedApiQueue = function(number, data, options, ...rest) {
                if (!activeScope) return originalApiQueue.call(this, number, data, options, ...rest);
                if (activeScope.apiRequests++) {
                    reportSuppressed(activeScope);
                    return Promise.resolve(duplicateReceipt());
                }
                const scopedOptions = { ...(options ?? {}), partialExecutionTargets: [activeScope.editorId] };
                return originalApiQueue.call(this, number, data, scopedOptions, ...rest);
            };
            guardedApiQueue.__obvpmDirectorTargetGuard = true;
            api.queuePrompt = guardedApiQueue;
        }

        const originalAppQueue = app.queuePrompt;
        const guardedAppQueue = async function(number, batchCount = 1, optionsOrIds = {}) {
            // Suppress any nested/reentrant requests emitted by widget hooks or
            // other extensions while the Director-targeted request is pending.
            if (activeScope) {
                reportSuppressed(activeScope);
                return false;
            }
            const editor = selectedEditor(optionsOrIds);
            if (!editor) return originalAppQueue.call(this, number, batchCount, optionsOrIds);

            // If ComfyUI is already submitting another job, do not let this
            // request slip into its async internal queue after our guard exits.
            if (app.processingQueue) {
                console.warn("[OBVPM Director] Queue submission already in progress; retry DIRECT when idle.");
                return false;
            }
            if (typeof api?.fetchApi !== "function" || typeof api?.queuePrompt !== "function") {
                console.warn("[OBVPM Director] Queue safety hooks unavailable; refusing potentially unscoped run.");
                return false;
            }
            const editorId = String(editor.id);
            const options = Array.isArray(optionsOrIds)
                ? { queueNodeIds: [editorId] }
                : { ...optionsOrIds, queueNodeIds: [editorId] };
            activeScope = { editorId, apiRequests: 0, submitted: false, duplicateLogged: false };
            try {
                // Exactly one Editor run, regardless of global batch count or
                // incidental extra targets from UI/custom-node extensions.
                return await originalAppQueue.call(this, number, 1, options);
            } finally {
                activeScope = null;
            }
        };
        guardedAppQueue.__obvpmDirectorTargetGuard = true;
        app.queuePrompt = guardedAppQueue;
    },
});
