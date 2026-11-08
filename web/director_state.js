import { app } from "../../scripts/app.js";

function applyWidgetValues(node, state, keys) {
    for (const key of keys) {
        const w = node.widgets?.find(x => x.name === key);
        if (w && Object.prototype.hasOwnProperty.call(state, key)) {
            w.value = state[key] ?? "";
            if (w.callback) w.callback(w.value, app.canvas, node, w);
        }
    }
    node.setDirtyCanvas(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

const SHOT_STATE_WIDGET_RATIOS = {
    shot_direction: 25,
    shot_h3_prompt: 50,
    shot_analysis: 25,
};

function applyShotStateWidgetLayout(node) {
    for (const [name, percent] of Object.entries(SHOT_STATE_WIDGET_RATIOS)) {
        const w = node.widgets?.find(x => x.name === name);
        if (!w) continue;
        w.options = w.options || {};
        // Current ComfyUI DOM multiline widgets support percentage preferred
        // heights. This keeps the manually edited H3 prompt at half of the
        // flexible text area, with direction/analysis at one quarter each.
        w.options.getHeight = () => `${percent}%`;
        w.options.getMinHeight = () => 60;
        if (w.element?.style) {
            w.element.style.setProperty("--comfy-widget-height", `${percent}%`);
            w.element.style.setProperty("--comfy-widget-min-height", "60px");
        }
    }
    requestAnimationFrame(() => {
        node.onResize?.(node.size);
        node.setDirtyCanvas?.(true, true);
        app.graph?.setDirtyCanvas?.(true, true);
    });
}

// Compact status line. It is UI-only, never part of the execution payload or
// serialized workflow. Accepted role bindings live in Director Context / Shot Analysis.
function attachReferenceStatus(node) {
    if (node.widgets?.some(w => w.name === "director_reference_status")) return;
    const w = node.addWidget("text", "director_reference_status",
        "○ Reference roles: awaiting analysis", null,
        { serialize: false, readOnly: true });
    if (w) {
        w.options = { ...(w.options || {}), serialize: false, readOnly: true };
        w.disabled = true;
    }
}

function updateReferenceStatus(node, summary) {
    const w = node?.widgets?.find(x => x.name === "director_reference_status");
    if (!w) return;
    w.value = String(summary || "○ Reference roles: awaiting analysis");
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function upstreamRequestBuilders(start) {
    const pending = [start];
    const seen = new Set();
    const result = [];
    while (pending.length && seen.size < 500) {
        const node = pending.shift();
        if (!node || seen.has(node.id)) continue;
        seen.add(node.id);
        if (node.comfyClass === "H3DirectorRequestBuilder" || node.type === "H3DirectorRequestBuilder") {
            result.push(node);
            continue;
        }
        for (const input of node.inputs ?? []) {
            if (input.link == null) continue;
            const link = app.graph?.links?.[input.link];
            const originId = link?.origin_id ?? (Array.isArray(link) ? link[1] : undefined);
            if (originId != null) pending.push(app.graph?.getNodeById?.(originId));
        }
    }
    return result;
}

function isAnalysisSnapshotNode(node) {
    return node?.comfyClass === "H3DirectorAnalysisSnapshot"
        || node?.type === "H3DirectorAnalysisSnapshot"
        || node?.constructor?.comfyClass === "H3DirectorAnalysisSnapshot";
}

function setMaterialized(node, value) {
    const w = node?.widgets?.find(x => x.name === "materialized");
    if (!w) return false;
    if (w.value === value) return false;
    w.value = value;
    w.callback?.(w.value, app.canvas, node, w);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
    return true;
}

function downstreamEditors(start) {
    const seen = new Set([start.id]);
    const pending = [start];
    const found = [];
    while (pending.length && seen.size < 1000) {
        const node = pending.shift();
        for (const output of node.outputs ?? []) {
            for (const id of output.links ?? []) {
                const link = app.graph?.links?.[id];
                const targetId = link?.target_id ?? (Array.isArray(link) ? link[3] : undefined);
                const target = targetId === undefined ? null : app.graph?.getNodeById?.(targetId);
                if (!target || seen.has(target.id)) continue;
                seen.add(target.id);
                if (isShotStateNode(target)) found.push(target);
                pending.push(target);
            }
        }
    }
    return found;
}

function addActionButton(node, name, callback) {
    if (node.widgets?.some(w => w.name === name)) return;
    node.addWidget("button", name, null, callback, { serialize: false });
}

function isShotStateNode(node) {
    return node?.comfyClass === "H3DirectorShotState"
        || node?.type === "H3DirectorShotState"
        || node?.constructor?.comfyClass === "H3DirectorShotState";
}

// Explicit project-template reset. Unlike Re-analyze/Recompose or the
// timeline.next unfreeze, this *erases the stored text* as well as the gates.
// Deliberately limited to Director-owned materialized widgets: the user's
// current Request Builder direction, references, model settings and OBVPM
// timeline/sidecars remain untouched.
function clearDirectorMaterializedData() {
    let snapshots = 0;
    let editors = 0;
    for (const node of app.graph?._nodes ?? []) {
        if (isAnalysisSnapshotNode(node)) {
            applyWidgetValues(node, {
                snapshot_raw_analysis: "",
                snapshot_director_context: "",
                materialized: false,
            }, ["snapshot_raw_analysis", "snapshot_director_context", "materialized"]);
            snapshots++;
        } else if (isShotStateNode(node)) {
            applyWidgetValues(node, {
                shot_direction: "",
                shot_h3_prompt: "",
                shot_analysis: "",
                materialized: false,
            }, ["shot_direction", "shot_h3_prompt", "shot_analysis", "materialized"]);
            editors++;
        }
    }
    for (const node of app.graph?._nodes ?? []) {
        if (node?.comfyClass === "H3DirectorRequestBuilder" || node?.type === "H3DirectorRequestBuilder"
            || node?.comfyClass === "H3DirectorAnalysisCompose" || node?.type === "H3DirectorAnalysisCompose") {
            updateReferenceStatus(node, "○ Reference roles: awaiting new analysis");
        }
    }
    console.log(
        `[OBVPM Director] cleared stored Director context: ${snapshots} Analysis Snapshot(s), ` +
        `${editors} Shot Editor(s); current inputs and OBVPM timeline preserved.`
    );
    app.graph?.change?.();
    app.graph?.setDirtyCanvas?.(true, true);
    return { snapshots, editors };
}

function requestDirectorContextReset() {
    const ok = window.confirm(
        "Reset ALL saved Director state in this workflow?\n\n" +
        "Clear saved Analysis, Director Context, Shot Direction, H3 Prompt and Shot Analysis " +
        "in all Director Snapshot / Shot Editor nodes, then unlock both passes.\n\n" +
        "Current Request Builder inputs, reference connections, models and OBVPM timeline " +
        "will NOT be modified.\n\n" +
        "Finish or cancel queued/running jobs before resetting: old results could refill " +
        "the fields. Save the copied workflow after clearing."
    );
    if (!ok) return;
    clearDirectorMaterializedData();
}

function resetMaterializedShotStates(reason) {
    let changedEditors = 0;
    let changedSnapshots = 0;
    for (const node of app.graph?._nodes ?? []) {
        if (isShotStateNode(node) && setMaterialized(node, false)) changedEditors++;
        if (isAnalysisSnapshotNode(node) && setMaterialized(node, false)) changedSnapshots++;
    }
    if (changedEditors || changedSnapshots) {
        for (const node of app.graph?._nodes ?? []) {
            if (node?.comfyClass === "H3DirectorRequestBuilder" || node?.type === "H3DirectorRequestBuilder"
                || node?.comfyClass === "H3DirectorAnalysisCompose" || node?.type === "H3DirectorAnalysisCompose") {
                updateReferenceStatus(node, "○ Reference roles: new timeline context — re-analyze");
            }
        }
        console.log(
            `[OBVPM Director] new Timeline generation context (${reason}); ` +
            `reset ${changedEditors} Shot Editor(s) and ${changedSnapshots} Analysis Snapshot(s).`
        );
    }
}

function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
        const out = {};
        for (const key of Object.keys(value).sort()) out[key] = canonical(value[key]);
        return out;
    }
    return value;
}

function timelineNextFingerprint(node) {
    const sequence = node.widgets?.find(w => w.name === "sequence");
    const raw = sequence?.value;
    if (typeof raw !== "string" || !raw.trim().startsWith("{")) return null;

    try {
        const doc = JSON.parse(raw);
        if (doc?.obvpm_timeline !== 1 || !("next" in doc)) return null;
        return JSON.stringify(canonical(doc.next ?? null));
    } catch (_) {
        return null;
    }
}

// We intentionally watch OBVPM's serialized timeline.next contract rather than
// private button handlers. +plan and changing the next root/extend/prepend/bridge
// target all advance this authoritative state. Ordinary cuts/moves which leave
// next untouched do not reset the Director state.
const timelineSeen = new WeakMap();
const pendingReset = new WeakMap();

function watchTimelineNext() {
    for (const node of app.graph?._nodes ?? []) {
        const fp = timelineNextFingerprint(node);
        if (fp === null) continue;

        if (!timelineSeen.has(node)) {
            // Baseline only: opening/reloading a workflow must not invalidate a
            // restored/materialized Shot State.
            timelineSeen.set(node, fp);
            continue;
        }

        const previous = timelineSeen.get(node);
        if (previous === fp) continue;
        timelineSeen.set(node, fp);

        const oldTimer = pendingReset.get(node);
        if (oldTimer) clearTimeout(oldTimer);

        // Let OBVPM finish +plan / timeline serialization first. By the time
        // timeline.next is committed, the plan snapshot is already being kept;
        // the short debounce also coalesces multi-step UI updates.
        const timer = setTimeout(() => {
            pendingReset.delete(node);
            if (timelineNextFingerprint(node) !== fp) return;
            resetMaterializedShotStates("timeline.next changed");
        }, 500);
        pendingReset.set(node, timer);
    }
}

app.registerExtension({
    name: "obvpm-director.shot-state",

    setup() {
        // Frontend-only observer; no polling of the server and no dependency on
        // private OBVPM implementation details.
        setInterval(watchTimelineNext, 250);
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "H3DirectorRequestBuilder") {
            const created = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = created?.apply(this, arguments);
                attachReferenceStatus(this);
                for (const key of ["direction", "reference_roles"]) {
                    const widget = this.widgets?.find(w => w.name === key);
                    if (!widget || widget.__directorReferenceWatch) continue;
                    const previous = widget.callback;
                    widget.callback = (...args) => {
                        const r = previous?.apply(widget, args);
                        updateReferenceStatus(this, "○ Reference roles: input changed — Re-analyze to refresh");
                        return r;
                    };
                    widget.__directorReferenceWatch = true;
                }
                return result;
            };
        }
        if (nodeData.name === "H3DirectorAnalysisCompose") {
            const created = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = created?.apply(this, arguments);
                attachReferenceStatus(this);
                return result;
            };
            const executed = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                executed?.apply(this, arguments);
                try {
                    const raw = message?.director_reference_status?.[0]
                        ?? message?.director_reference_status;
                    if (!raw) return;
                    const state = typeof raw === "string" ? JSON.parse(raw) : raw;
                    const summary = state?.summary ?? "○ Reference roles: unresolved";
                    updateReferenceStatus(this, summary);
                    for (const builder of upstreamRequestBuilders(this)) {
                        updateReferenceStatus(builder, summary);
                    }
                } catch (error) {
                    console.warn("[OBVPM Director] reference status update failed", error);
                }
            };
        }
        if (nodeData.name === "H3DirectorContextReset") {
            const originalCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = originalCreated?.apply(this, arguments);
                addActionButton(this, "Reset Director Context (this workflow)",
                    requestDirectorContextReset);
                return result;
            };
        }
        if (nodeData.name === "H3DirectorAnalysisSnapshot") {
            const originalCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = originalCreated?.apply(this, arguments);
                addActionButton(this, "Reset Director Context (clear saved state)",
                    requestDirectorContextReset);
                addActionButton(this, "Re-analyze (refresh Pass #1)", () => {
                    setMaterialized(this, false);
                    for (const builder of upstreamRequestBuilders(this)) {
                        updateReferenceStatus(builder, "○ Reference roles: waiting for refreshed Pass #1");
                    }
                    const editors = downstreamEditors(this);
                    for (const editor of editors) setMaterialized(editor, false);
                    console.log(
                        `[OBVPM Director] analysis unfrozen; ${editors.length} connected Shot Editor(s) ` +
                        `unfrozen. Execute the graph to recapture Pass #1.`
                    );
                });
                return result;
            };
            const originalExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                originalExecuted?.apply(this, arguments);
                try {
                    const raw = message?.director_analysis_snapshot?.[0]
                        ?? message?.director_analysis_snapshot;
                    if (!raw) return;
                    const state = typeof raw === "string" ? JSON.parse(raw) : raw;
                    applyWidgetValues(this, state, [
                        "snapshot_raw_analysis", "snapshot_director_context", "materialized"
                    ]);
                    console.log("[OBVPM Director] Pass #1 analysis and context materialized.");
                } catch (e) {
                    console.warn("[OBVPM Director] could not materialize analysis snapshot", e);
                }
            };
        }
        if (nodeData.name === "H3DirectorShotState") {
            const originalCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = originalCreated?.apply(this, arguments);
                applyShotStateWidgetLayout(this);
                addActionButton(this, "Reset Director Context (clear saved state)",
                    requestDirectorContextReset);
                addActionButton(this, "Recompose (keep analysis)", () => {
                    setMaterialized(this, false);
                    console.log(
                        "[OBVPM Director] Shot Editor unfrozen; Analysis Snapshot remains frozen. " +
                        "Execute the graph to rerun Pass #2."
                    );
                });
                return result;
            };

            const originalConfigured = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function() {
                const result = originalConfigured?.apply(this, arguments);
                applyShotStateWidgetLayout(this);
                return result;
            };

            const originalExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                if (originalExecuted) originalExecuted.apply(this, arguments);
                try {
                    const raw = message?.director_shot_state?.[0] ?? message?.director_shot_state;
                    if (!raw) return;
                    const state = typeof raw === "string" ? JSON.parse(raw) : raw;
                    this.properties = this.properties || {};
                    if (state?.schema) this.properties.director_state_schema = state.schema;
                    if (state?.schema_version !== undefined) {
                        this.properties.director_state_schema_version = state.schema_version;
                    }
                    applyWidgetValues(this, state, [
                        "shot_direction", "shot_h3_prompt", "shot_analysis", "materialized"
                    ]);
                    applyShotStateWidgetLayout(this);
                    console.log("[OBVPM Director] Shot State materialized; Composer branch is now lazy-blocked.");
                } catch (e) {
                    console.warn("[OBVPM Director] could not materialize shot state widgets", e);
                }
            };
        }
    },
});
