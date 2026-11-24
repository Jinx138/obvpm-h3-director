import { app } from "../../scripts/app.js";

// Persist the native Snapshot's three named widgets, including when nested.
// Do not introduce a separate project cache or reconstruct raw context from a
// normalized Shot Editor. The workflow remains the sole persistence source.
const SNAPSHOT_KEYS = ["materialized", "snapshot_raw_analysis", "snapshot_director_context"];
function snapshotWidgetValues(node) {
    const result = {};
    for (const key of SNAPSHOT_KEYS) {
        const w = node?.widgets?.find(v => v.name === key);
        if (w) result[key] = w.value;
    }
    return result;
}
function writeSnapshotSerialization(node, data) {
    if (!data || typeof data !== "object") return;
    const values = snapshotWidgetValues(node);
    if (!SNAPSHOT_KEYS.every(k => Object.prototype.hasOwnProperty.call(values,k))) return;
    data.widgets_values_named = {...(data.widgets_values_named ?? {}), ...values};
    // The three backend widgets are in fixed order; leave unrelated widgets intact.
    const old = Array.isArray(data.widgets_values) ? [...data.widgets_values] : [];
    for (let i=0;i<SNAPSHOT_KEYS.length;i++) old[i]=values[SNAPSHOT_KEYS[i]];
    data.widgets_values=old;
}
function snapshotComplete(node) {
    const v = snapshotWidgetValues(node);
    return typeof v.snapshot_raw_analysis === "string" && !!v.snapshot_raw_analysis.trim() &&
        typeof v.snapshot_director_context === "string" && !!v.snapshot_director_context.trim();
}
function restoreSnapshotSerialization(node, data) {
    const named=data?.widgets_values_named;
    if (!named || !SNAPSHOT_KEYS.every(k => Object.prototype.hasOwnProperty.call(named,k))) return;
    // Explicit saved blanks are authoritative; never resurrect previous data.
    if (typeof named.materialized !== "boolean" || typeof named.snapshot_raw_analysis !== "string" ||
        typeof named.snapshot_director_context !== "string") return;
    for (const key of SNAPSHOT_KEYS) {
        const w = node.widgets?.find(v=>v.name===key);
        if (w) w.value=named[key];
    }
}
function applyWidgetValues(node, state, keys) {
    for (const key of keys) {
        const w = node.widgets?.find(x => x.name === key);
        if (w && Object.prototype.hasOwnProperty.call(state, key)) {
            w.value = state[key] ?? "";
            if (w.callback) w.callback(w.value, app.canvas, node, w);
        }
    }
    if (isAnalysisSnapshotNode(node)) {
        writeSnapshotSerialization(node,node);
        node.graph?.change?.();
        if (node.graph !== app.graph) app.graph?.change?.();
    }
    node.setDirtyCanvas(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

// Hide presentation only. The underlying widget objects, names, values and
// serialisation order remain intact for frozen state and old workflow restore.
function hideDirectorWidget(w) {
    if (!w) return;
    w.options = w.options || {};
    w.options.getHeight = () => 0;
    w.options.getMinHeight = () => 0;
    w.options.getMaxHeight = () => 0;
    w.computeSize = () => [0, -4];
    w.draw = () => {};
    try { w.hidden = true; } catch (_) {}
    if (w.element?.style) w.element.style.display = "none";
}
function applyShotStateWidgetLayout(node) {
    for (const name of ["shot_direction", "shot_analysis", "shot_gen2_thinking", "shot_gen2_raw_json", "shot_validation",
        "View saved Gen #2 Thinking", "View saved Gen #2 Raw JSON", "View / Copy Director Debug Report"]) {
        hideDirectorWidget(node.widgets?.find(w => w.name === name));
    }
    const w = node.widgets?.find(w => w.name === "shot_h3_prompt");
    if (w) {
        w.options = w.options || {};
        w.options.getHeight = () => "100%";
        w.options.getMinHeight = () => 100;
        if (w.element?.style) {
            w.element.style.setProperty("--comfy-widget-height", "100%");
            w.element.style.setProperty("--comfy-widget-min-height", "100px");
        }
    }
    requestAnimationFrame(() => {
        node.onResize?.(node.size);
        node.setDirtyCanvas?.(true, true);
    });
}

// H3-DIRECTOR-GEN2-TRACE-DEV5
// View persisted diagnostic widgets locally. No queue, fetch or LLM evaluation.
function viewSavedGen2Trace(node, key, title, providedContent = null) {
    const content = typeof providedContent === "string"
        ? providedContent : node.widgets?.find(w => w.name === key)?.value;
    if (typeof content !== "string" || !content.trim()) {
        recipeNotice(`${title} is empty. Connect Generate #2's matching output to the ` +
            "Shot Editor's optional input and run DIRECT once to capture it.");
        return;
    }
    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.7);" +
        "z-index:2147483640;display:flex;align-items:center;justify-content:center;padding:3vh 3vw;";
    const panel = document.createElement("div");
    panel.style.cssText = "display:flex;flex-direction:column;gap:12px;width:min(1150px,96vw);" +
        "height:min(850px,92vh);padding:18px;border-radius:12px;background:var(--comfy-menu-bg,#242424);" +
        "color:var(--input-text,#eee);box-shadow:0 10px 35px #0009;box-sizing:border-box;";
    const header = document.createElement("div");
    header.style.cssText = "display:flex;gap:8px;align-items:center;justify-content:space-between;";
    const heading = document.createElement("strong");
    heading.textContent = `${title} · ${isCore(node) ? "Director Core" : isAnalysisSnapshotNode(node) ? "Analysis Snapshot" : node.type === "H3DirectorStatus" ? "Director Status" : "Shot Editor"} #${node.id}`;
    const controls = document.createElement("div");
    controls.style.cssText = "display:flex;gap:8px;";
    const copy = document.createElement("button");
    copy.textContent = "Copy";
    const close = document.createElement("button");
    close.textContent = "Close";
    for (const button of [copy, close]) button.style.cssText = "padding:6px 12px;cursor:pointer;";
    const text = document.createElement("textarea");
    text.readOnly = true;
    text.spellcheck = false;
    text.value = content;
    text.style.cssText = "flex:1;min-height:0;width:100%;box-sizing:border-box;resize:none;" +
        "padding:12px;border-radius:6px;background:var(--comfy-input-bg,#151515);" +
        "color:var(--input-text,#eee);font:13px/1.5 ui-monospace,monospace;" +
"white-space:pre-wrap;overflow-wrap:anywhere;";
    const dismiss = () => { document.removeEventListener("keydown", onKeyDown); overlay.remove(); };
    const onKeyDown = event => { if (event.key === "Escape") dismiss(); };
    close.addEventListener("click", dismiss);
    overlay.addEventListener("click", event => { if (event.target === overlay) dismiss(); });
    copy.addEventListener("click", async () => {
        try {
            if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(content);
            else { text.select(); document.execCommand("copy"); }
            copy.textContent = "Copied";
        } catch (error) { console.warn("[OBVPM Director] trace copy failed", error); text.select(); }
    });
    controls.append(copy, close);
    header.append(heading, controls);
    panel.append(header, text);
    overlay.append(panel);
    document.body.append(overlay);
    document.addEventListener("keydown", onKeyDown);
    close.focus();
}

// H3-DIRECTOR-DEBUG-REPORT-DEV6
// Single read-only snapshot of three existing pipeline results. No queue, fetch,
// ComfyUI output linking or extra model execution occurs when viewing/copying.
function buildDirectorDebugReport(node) {
    const stored = key => {
        const value = node.widgets?.find(w => w.name === key)?.value;
        return typeof value === "string" && value.trim() ? value : "[NOT CAPTURED]";
    };
    const prettyJson = value => {
        if (value === "[NOT CAPTURED]") return value;
        try { return JSON.stringify(JSON.parse(value), null, 2); }
        catch (_) { return value; }
    };
    const materialized = node.widgets?.find(w => w.name === "materialized")?.value === true;
    return [
        `OBVPM DIRECTOR — SHOT DEBUG REPORT`,
        `Shot Editor #${node.id} | materialized=${materialized}`,
        `Local saved values only; opening this report does NOT execute either LLM.`,
        ``,
        `========== 1 / 3 — SHOT ANALYSIS JSON ==========`,
        prettyJson(stored("shot_analysis")),
        ``,
        `========== 2 / 3 — GENERATE #2 RAW JSON ==========`,
        prettyJson(stored("shot_gen2_raw_json")),
        ``,
        `========== 3 / 3 — RESPONSE VALIDATION ==========`,
        stored("shot_validation"),
    ].join("\n");
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

// Resolve boundaries by graph identity, not by numeric node ID. Subgraph
// interface pseudo-nodes -10/-20 connect to the corresponding host slots.
function graphNodes(graph) { return graph?._nodes ?? graph?.nodes ?? []; }
function allDirectorGraphNodes(root = app.graph) {
    const result = [], seen = new Set();
    function walk(graph, host = null) {
        if (!graph || seen.has(graph)) return;
        seen.add(graph);
        for (const node of graphNodes(graph)) {
            result.push({node, graph, host});
            if (node.subgraph) walk(node.subgraph, node);
        }
    }
    walk(root); return result;
}
function getGraphLink(graph, id) {
    if (id == null) return undefined;
    return graph?.getLink?.(id) ?? graph?.links?.get?.(id) ?? graph?.links?.[id];
}
function linkEnd(link, upstream) {
    return upstream ? [link?.origin_id ?? link?.[1], link?.origin_slot ?? link?.[2]]
        : [link?.target_id ?? link?.[3], link?.target_slot ?? link?.[4]];
}
function directorReachable(start, upstream) {
    const entries = allDirectorGraphNodes(), byNode = new Map(entries.map(e => [e.node,e]));
    const seen = new Set(), found = [], pending = [start];
    function follow(graph, id, depth = 0) {
        if (depth > 15 || id == null) return;
        const link = getGraphLink(graph,id);
        if (!link) return;
        const [nodeId,slot] = linkEnd(link,upstream);
        // Recent ComfyUI frontends normalize boundary node IDs to strings.
        if ((upstream && String(nodeId) === "-10") || (!upstream && String(nodeId) === "-20")) {
            for (const e of entries.filter(e => e.node.subgraph === graph)) {
                if (upstream) follow(e.graph,e.node.inputs?.[slot]?.link,depth+1);
                else for (const l of e.node.outputs?.[slot]?.links ?? []) follow(e.graph,l,depth+1);
            }
            return;
        }
        const node = graph?.getNodeById?.(nodeId) ?? graphNodes(graph).find(n => String(n.id) === String(nodeId));
        if (!node) return;
        if (node.subgraph) {
            const ports = upstream ? node.subgraph.outputs : node.subgraph.inputs;
            const port = ports?.[slot];
            for (const l of port?.linkIds ?? port?.links ?? []) follow(node.subgraph,l,depth+1);
        } else pending.push(node);
    }
    while (pending.length && seen.size < 1500) {
        const node = pending.shift(); if (!node || seen.has(node)) continue;
        seen.add(node); if (node !== start) found.push(node);
        const graph = byNode.get(node)?.graph ?? node.graph ?? app.graph;
        if (upstream) for (const i of node.inputs ?? []) follow(graph,i.link);
        else for (const o of node.outputs ?? []) for (const l of o.links ?? []) follow(graph,l);
    }
    return found;
}
function upstreamRequestBuilders(start) {
    return directorReachable(start,true).filter(n => n.type === "H3DirectorRequestBuilder" || n.comfyClass === "H3DirectorRequestBuilder");
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
    if (!value && isShotStateNode(node)) node.__directorValidationFresh = false;
    w.callback?.(w.value, app.canvas, node, w);
    if (isShotStateNode(node)) syncApplyButton(node);
    if (isAnalysisSnapshotNode(node)) {
        writeSnapshotSerialization(node,node);
        node.graph?.change?.();
    }
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
    return true;
}

function downstreamEditors(start) { return directorReachable(start,false).filter(isShotStateNode); }

function colorButton(w, color) {
    if (!w) return;
    w.options = {...(w.options || {}), color, serialize: false};
    w.draw = function(ctx, node, width, y, height) {
        const h = Math.max(18, height || 20);
        ctx.save(); ctx.fillStyle = color; ctx.fillRect(12,y+1,Math.max(0,width-24),h-2);
        ctx.font = "12px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillStyle = "#fff";ctx.fillText(this.name,width/2,y+h/2);ctx.restore();
    };
}
// Appearance follows the same approval prerequisites as the existing action.
// An edited frozen prompt is deliberately still eligible for manual approval.
function syncApplyButton(editor) {
    const w = editor.widgets?.find(x => x.name === "Apply approved prompt to Recipe");
    if (!w) return;
    const ready = editor.widgets?.find(x => x.name === "materialized")?.value === true &&
        !!String(editor.widgets?.find(x => x.name === "shot_h3_prompt")?.value ?? "").trim() &&
        (app.graph?._nodes ?? []).some(n => isRecipePromptNode(n) && n.widgets?.some(v => v.name === "prompt_text"));
    if (!w.__directorApplyAppearance) w.__directorApplyAppearance = {draw: w.draw, color: w.options?.color, ready: false};
    const original = w.__directorApplyAppearance;
    if (original.ready === ready) return;
    original.ready = ready;
    if (ready) colorButton(w, "#286c43");
    else {
        w.draw = original.draw;
        if (original.color === undefined) delete w.options.color;
        else w.options.color = original.color;
    }
    editor.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function addActionButton(node, name, callback, color) {
    let w = node.widgets?.find(w => w.name === name);
    if (!w) w = node.addWidget("button", name, null, callback, { serialize: false });
    if (color) colorButton(w,color);
    return w;
}

// Keep DIRECT immediately underneath the materialized switch, instead of
// placing a queue control at the bottom of a long Shot Editor node. The
// button is UI-only: it never becomes a Python input or a saved widget value.
function putWidgetAfter(node, name, predecessor) {
    const widgets = node.widgets;
    if (!Array.isArray(widgets)) return;
    const from = widgets.findIndex(w => w.name === name);
    const before = widgets.findIndex(w => w.name === predecessor);
    if (from < 0 || before < 0 || from === before + 1) return;
    const [widget] = widgets.splice(from, 1);
    const at = widgets.findIndex(w => w.name === predecessor);
    widgets.splice(at + 1, 0, widget);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

// Native ComfyUI supports explicitly-targeted output-node runs. The Shot
// Editor is OUTPUT_NODE=True in the backend, so asking for its ID makes
// ComfyUI evaluate its ancestors without scheduling unrelated H3 outputs.
// Fail closed: never fall back to app.queuePrompt(0, 1) (whole workflow).
async function executeDirectorOnly(editor) {
    if (editor.__directorQueuePending) return false;
    if (typeof app.queuePrompt !== "function") {
        recipeNotice("ComfyUI targeted queue API is unavailable. Run the selected Shot Editor node manually.");
        return false;
    }
    const graph = app.graph;
    if (typeof graph?.getNodeById !== "function" ||
        graph.getNodeById(editor.id) !== editor) {
        recipeNotice("DIRECT supports a Shot Editor on the top-level ComfyUI graph only. Nothing was queued.");
        return false;
    }
    // Do not silently re-analyze or queue an impossible frozen state.
    const incomplete = directorReachable(editor,true).filter(isAnalysisSnapshotNode).find(n =>
        widgetOf(n,"materialized")?.value === true &&
        widgetOf(n,"snapshot_raw_analysis") && widgetOf(n,"snapshot_director_context") && !snapshotComplete(n));
    if (incomplete) {
        recipeNotice("The saved Analysis Snapshot is incomplete. Use Re-analyze, then DIRECT to capture Pass #1 again. No inference was queued.");
        return false;
    }
    // Unfreeze only the Shot Editor. The Analysis Snapshot stays frozen so
    // DIRECT recomposes Pass #2; if the Snapshot is already unfrozen,
    // ComfyUI also evaluates Pass #1 through the normal dependency chain.
    const wasFrozen = editor.widgets?.find(w => w.name === "materialized")?.value === true;
    editor.__directorQueuePending = true;
    if (wasFrozen) {
        setMaterialized(editor, false);
        graph.change?.();
    }
    try {
        const queued = await app.queuePrompt(0, 1, {
            queueNodeIds: [String(editor.id)],
        });
        if (queued === false) {
            if (wasFrozen) setMaterialized(editor, true);
            recipeNotice("ComfyUI did not queue DIRECT. The previous freeze state was restored.");
            return false;
        }
        console.log(`[OBVPM Director] DIRECT queued Shot Editor #${editor.id} only.`);
        return true;
    } catch (error) {
        if (wasFrozen) setMaterialized(editor, true);
        console.warn("[OBVPM Director] DIRECT queue failed", error);
        recipeNotice("DIRECT could not be queued; previous freeze state restored. Check the console.");
        return false;
    } finally {
        editor.__directorQueuePending = false;
    }
}

function isShotStateNode(node) {
    return node?.comfyClass === "H3DirectorShotState"
        || node?.type === "H3DirectorShotState"
        || node?.constructor?.comfyClass === "H3DirectorShotState";
}

// Explicit one-way handoff to a literal Recipe source. This does NOT connect
// Shot Editor to H3: OBVPM 0.5.2 resolves a single persistent text widget at
// queue time, and automatic clip Sync must never overwrite the Director desk.
function isRecipePromptNode(node) {
    return node?.comfyClass === "H3DirectorRecipePrompt"
        || node?.type === "H3DirectorRecipePrompt"
        || node?.constructor?.comfyClass === "H3DirectorRecipePrompt";
}

function recipeNotice(message) {
    if (typeof window !== "undefined" && typeof window.alert === "function") {
        window.alert(message);
    } else {
        console.warn(`[OBVPM Director] ${message}`);
    }
}

function applyApprovedPrompt(editor) {
    const materialized = editor.widgets?.find(w => w.name === "materialized")?.value === true;
    const prompt = editor.widgets?.find(w => w.name === "shot_h3_prompt")?.value;
    if (!materialized || typeof prompt !== "string" || !prompt.trim()) {
        recipeNotice("Freeze/materialize a non-empty Director Shot Editor prompt before applying it to a Recipe.");
        return false;
    }

    const candidates = (app.graph?._nodes ?? []).filter(isRecipePromptNode);
    if (!candidates.length) {
        recipeNotice("Add an H3 Director Recipe Prompt (obvpm) node first. Put it in its own [restore] group.");
        return false;
    }
    let target = candidates[0];
    if (candidates.length > 1) {
        // No implicit cross-shot overwrite when several Recipe nodes exist.
        const ids = candidates.map(n => String(n.id));
        if (typeof window?.prompt !== "function") {
            recipeNotice(`Multiple Recipe nodes (${ids.join(", ")}). Select one explicitly.`);
            return false;
        }
        const selected = window.prompt(
            `Multiple Recipe Prompt nodes exist. Enter the destination node ID: ${ids.join(", ")}`,
            ""
        );
        if (selected == null) return false;
        target = candidates.find(n => String(n.id) === selected.trim());
        if (!target) {
            recipeNotice("Invalid Recipe node ID; nothing was changed.");
            return false;
        }
    }
    const widget = target.widgets?.find(w => w.name === "prompt_text");
    if (!widget) {
        recipeNotice("Recipe node has no prompt_text widget; nothing was changed.");
        return false;
    }
    if (widget.value === prompt) return true;
    if (typeof widget.value === "string" && widget.value.trim()) {
        // The Recipe prompt might be the historical take currently selected
        // by OBVPM Sync. Overwriting it MUST be a deliberate act.
        if (typeof window?.confirm !== "function" || !window.confirm(
            `Replace the existing Recipe Prompt on node #${target.id}?\n\n` +
            "This may currently be the prompt of a selected historical clip. " +
            "The Director workspace itself will not be changed."
        )) return false;
    }
    widget.value = prompt; // byte-for-byte text, including manual edits
    widget.callback?.(widget.value, app.canvas, target, widget);
    const nextTimeline = (app.graph?._nodes ?? []).find(n => timelineReservationState(n)?.selected);
    if (nextTimeline) markPreparedRecipe(target, nextTimeline, timelineReservationState(nextTimeline).key);
    target.setDirtyCanvas?.(true, true);
    app.graph?.change?.();
    app.graph?.setDirtyCanvas?.(true, true);
    console.log(`[OBVPM Director] applied ${prompt.length} chars to Recipe node #${target.id}. ` +
        "Use its prompt output directly for H3. Director workspace unchanged.");
    return true;
}

// rc25b: a Recipe belongs to a selected NEXT RUN, never implicitly to the
// historical clip highlighted immediately before it. OBVPM 0.5.2 owns the
// actual next_draft and [restore] syncing; this observer only clears an
// unmistakably NEW reservation and commits newly composed text to an empty
// reservation. It does not touch OBVPM's private frontend handlers.
const reservationSeen = new WeakMap();
const reservationPending = new WeakMap();
const reservationArmed = new WeakMap();
// Separate from pin handling: only a newly appended ROOT take may advance
// the implicit NEXT RUN. Never interpret an empty/cleared pin as that event.
const rootTrackSeen = new WeakMap();
const rootPending = new WeakMap();

function isDirectorGenerationPin(pin) {
    if (!pin || !["extend", "prepend", "bridge"].includes(pin.role) || !pin.source) {
        return false;
    }
    return pin.role !== "bridge" || !!pin.source2;
}

function timelineReservationState(node) {
    const raw = node.widgets?.find(w => w.name === "sequence")?.value;
    if (typeof raw !== "string" || !raw.trim().startsWith("{")) return null;
    try {
        const doc = JSON.parse(raw);
        if (doc?.obvpm_timeline !== 1) return null;
        // Only source/role define the reservation's semantic identity.
        // The queue can temporarily attach .plan, and a user may adjust
        // window/at/join/length without creating a NEW shot.
        const pin = doc.next ?? null;
        const role = pin?.role ?? "root";
        // OBVPM 0.5.2 can switch between projects/timelines using the SAME
        // node. A project switch is not a newly accepted Root take.
        const projectKey = doc.project?.id
            ? JSON.stringify([doc.project.id, doc.project.timeline ?? null]) : null;
        // V1 is authoritative. Ignore gaps and planned placeholders. Trim,
        // seam and frame-count edits must not change a root reservation ID.
        const video = doc.tracks?.find(t => t?.id === "V1" && t?.kind === "video");
        const videoPaths = (video?.clips ?? []).flatMap(c =>
            typeof c?.path === "string" && c.path.trim() ? [c.path.trim()] : []);
        const identity = {
            role,
            source: pin?.source ?? null,
            source2: pin?.source2 ?? null,
        };
        // A pinless Root has no `next.source`. Anchor its identity to the
        // final actual clip, rather than reusing one key for every Root.
        if (!isDirectorGenerationPin(pin)) {
            identity.root_after = videoPaths.at(-1) ?? null;
            identity.root_clip_count = videoPaths.length;
            identity.project = projectKey;
        }
        return {
            selected: node.properties?.obvpm_tl_next_sel === true,
            key: JSON.stringify(canonical(identity)),
            videoPaths,
            projectKey,
            // A cleared pin is plain root generation, not an instruction
            // to start a new Director shot. Only real operation pins unlock.
            activePin: isDirectorGenerationPin(pin),
            queueInjected: !!pin?.plan,
            draft: doc.next_draft ?? null,
        };
    } catch (_) { return null; }
}

function recipeDraftText(draft, recipe) {
    const values = draft?.values?.[String(recipe.id)];
    return typeof values?.prompt_text === "string" ? values.prompt_text : null;
}

function markPreparedRecipe(recipe, timeline, key) {
    recipe.properties = recipe.properties || {};
    // Only context identity; the actual prompt stays in the normal editable
    // widget, saved/restored by OBVPM next_draft and clip Recipe.
    recipe.properties.director_recipe_prepared_for = {timeline_id: timeline.id, key};
}

function setRecipeText(recipe, value, reason) {
    const widget = recipe.widgets?.find(w => w.name === "prompt_text");
    if (!widget || widget.value === value) return false;
    widget.value = value;
    widget.callback?.(widget.value, app.canvas, recipe, widget);
    recipe.setDirtyCanvas?.(true, true);
    app.graph?.change?.();
    app.graph?.setDirtyCanvas?.(true, true);
    console.log(`[OBVPM Director] Recipe #${recipe.id}: ${reason}`);
    return true;
}

// A new operation changes timeline.next while the purple NEXT RUN is selected.
// Revisiting an existing reservation with its own next_draft must NOT clear it.
// Never clear a historical clip and never assume an unrecognized/missing
// timeline or multiple Recipe nodes can be safely synchronized.
function watchRecipeReservations() {
    const recipes = (app.graph?._nodes ?? []).filter(isRecipePromptNode);
    for (const timeline of app.graph?._nodes ?? []) {
        const current = timelineReservationState(timeline);
        if (!current || current.queueInjected) continue;
        const previous = reservationSeen.get(timeline);
        reservationSeen.set(timeline, {selected: current.selected, key: current.key});
        // A clear/X or toggling off an active Extend means NO pin.
        // Remember the cleared identity so a later re-arm of the SAME clip
        // is recognized, but do not clear Recipe or unlock either gate.
        if (!current.activePin) {
            const oldTimer = reservationPending.get(timeline);
            if (oldTimer) clearTimeout(oldTimer);
            reservationPending.delete(timeline);
            continue;
        }
        if (!previous || !current.selected) continue; // baseline and clip clicks are inert
        const entered = !previous.selected;
        const newOperation = previous.key !== current.key;
        if (!entered && !newOperation) continue;
        const previousTimer = reservationPending.get(timeline);
        if (previousTimer) clearTimeout(previousTimer);
        const timer = setTimeout(() => {
            reservationPending.delete(timeline);
            const settled = timelineReservationState(timeline);
            if (!settled?.selected || !settled.activePin || settled.queueInjected || settled.key !== current.key) return;
            if (recipes.length !== 1) return; // no ambiguous auto-targeting
            const nowRecipes = (app.graph?._nodes ?? []).filter(isRecipePromptNode);
            if (nowRecipes.length !== 1) return;
            const recipe = nowRecipes[0];
            const saved = recipeDraftText(settled.draft, recipe);
            const prepared = recipe.properties?.director_recipe_prepared_for;
            const previousDifferent = prepared?.timeline_id === timeline.id
                && prepared.key !== settled.key;
            // Existing next_draft takes precedence when revisiting the band.
            // An operation changed while ALREADY on purple is definitely new;
            // when arriving from a clip, a known different prepared context
            // or a blank draft is new. An unrecognized nonempty draft (e.g.
            // created before rc25b) is kept rather than destroyed.
            const fresh = entered
                ? (!String(saved ?? "").trim() || previousDifferent)
                : newOperation;
            if (!fresh) {
                reservationArmed.delete(recipe);
                return;
            }
            setRecipeText(recipe, "", "new timeline reservation — old prompt cleared");
            // Reset gates only for this verified purple reservation. In
            // particular, selecting a historical clip must never unfreeze.
            resetMaterializedShotStates("new purple timeline reservation");
            reservationArmed.set(recipe, {timeline, key: current.key});
        }, 750);
        reservationPending.set(timeline, timer);
    }
}

// rc25b.2: OBSERVE the main track after a successful Add to Timeline.
// OBVPM 0.5.2 has no public take-added event; its persisted V1 clip paths
// are a safe, passive indicator for the specific "new Root after last clip"
// workflow. A newly inserted path must EXTEND the existing real-clip list,
// not replace/move/trim/split an existing item. Never act on initial load.
function rootTrackState(node) {
    const parsed = timelineReservationState(node);
    if (parsed) return parsed;
    const raw = node.widgets?.find(w => w.name === "sequence")?.value;
    const pin = node.widgets?.find(w => w.name === "pin_state")?.value;
    // OBVPM's fresh 015 workflow starts with an empty legacy V1 sequence
    // before the first storeDoc() converts it to JSON. Baseline that empty
    // track, so accepting the FIRST Root take also advances correctly.
    // Never guess the contents of a nonempty legacy sequence.
    if (typeof raw !== "string" || raw.trim() || String(pin ?? "").trim()) return null;
    return {
        selected: node.properties?.obvpm_tl_next_sel === true,
        videoPaths: [], projectKey: null, key: "root:empty-legacy", activePin: false,
        queueInjected: false,
    };
}

function appendedRootTake(before, after) {
    if (!Array.isArray(before) || !Array.isArray(after)
        || after.length !== before.length + 1) return false;
    if (before.some((path, i) => path !== after[i])) return false;
    const added = after.at(-1);
    return !!added && !before.includes(added);
}

function watchRootAdvancement() {
    const recipes = (app.graph?._nodes ?? []).filter(isRecipePromptNode);
    for (const timeline of app.graph?._nodes ?? []) {
        const current = rootTrackState(timeline);
        if (!current) continue;
        const previous = rootTrackSeen.get(timeline);
        // The first observation is only a baseline, including after graph
        // reload. A saved/prepared Root may never be reset on graph load.
        rootTrackSeen.set(timeline, {
            paths: current.videoPaths,
            key: current.key,
            activePin: current.activePin,
            projectKey: current.projectKey,
        });
        if (!previous) continue;
        const added = appendedRootTake(previous.paths, current.videoPaths);
        // Clear/disable pin, click a historical clip, change trim, move
        // a clip, restore an existing draft: NONE of these starts a Root.
        if (!added || previous.projectKey !== current.projectKey
            || previous.activePin || current.activePin || !current.selected
            || current.queueInjected || recipes.length !== 1) continue;
        const oldTimer = rootPending.get(timeline);
        if (oldTimer) clearTimeout(oldTimer);
        const rootKey = current.key;
        const addedPath = current.videoPaths.at(-1);
        // Allow OBVPM's synchronous Add and NEXT restore to settle. If the
        // user has navigated elsewhere in the meantime, do not touch it.
        const timer = setTimeout(() => {
            rootPending.delete(timeline);
            const settled = timelineReservationState(timeline);
            if (!settled?.selected || settled.activePin || settled.queueInjected
                || settled.key !== rootKey || settled.videoPaths.at(-1) !== addedPath) return;
            const nowRecipes = (app.graph?._nodes ?? []).filter(isRecipePromptNode);
            if (nowRecipes.length !== 1) return;
            const recipe = nowRecipes[0];
            // The previous Root's prompt is now historical. This NEXT Root
            // starts clean, then autoCommitNewRecipe may prepare it once.
            setRecipeText(recipe, "", "new root after appended timeline take — prompt cleared");
            resetMaterializedShotStates("new root after appended timeline take");
            reservationArmed.set(recipe, {timeline, key: rootKey});
        }, 750);
        rootPending.set(timeline, timer);
    }
}

function autoCommitNewRecipe(editor, state, wasFrozen) {
    if (wasFrozen || state?.materialized !== true) return false;
    const prompt = state?.shot_h3_prompt;
    if (typeof prompt !== "string" || !prompt.trim()) return false;
    const recipes = (app.graph?._nodes ?? []).filter(isRecipePromptNode);
    if (recipes.length !== 1) return false;
    const recipe = recipes[0];
    const armed = reservationArmed.get(recipe);
    if (!armed) return false;
    const active = timelineReservationState(armed.timeline);
    if (!active?.selected || active.key !== armed.key) return false;
    // A hand-edited or already prepared Recipe is authoritative. Never
    // replace it automatically — use the explicit Apply button instead.
    const widget = recipe.widgets?.find(w => w.name === "prompt_text");
    if (!widget || String(widget.value ?? "").trim()) return false;
    const updated = setRecipeText(recipe, prompt,
        `automatically prepared from Shot Editor #${editor.id} (NEXT RUN only)`);
    if (updated) {
        markPreparedRecipe(recipe, armed.timeline, armed.key);
        reservationArmed.delete(recipe);
    }
    return updated;
}

// Explicit project-template reset. Unlike Re-analyze/Recompose or the
// timeline.next unfreeze, this *erases the stored text* as well as the gates.
// Deliberately limited to Director-owned materialized widgets: the user's
// current Request Builder direction, references, model settings and OBVPM
// timeline/sidecars remain untouched.
function clearDirectorMaterializedData() {
    let snapshots = 0;
    let editors = 0;
    for (const node of allDirectorGraphNodes().map(e => e.node)) {
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
                shot_gen2_thinking: "",
                shot_gen2_raw_json: "",
                shot_validation: "",
                materialized: false,
            }, ["shot_direction", "shot_h3_prompt", "shot_analysis",
                "shot_gen2_thinking", "shot_gen2_raw_json", "shot_validation", "materialized"]);
            node.__directorValidationFresh = false;
            editors++;
        }
    }
    for (const node of allDirectorGraphNodes().map(e => e.node)) {
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
    for (const node of allDirectorGraphNodes().map(e => e.node)) {
        if (isShotStateNode(node) && setMaterialized(node, false)) changedEditors++;
        if (isAnalysisSnapshotNode(node) && setMaterialized(node, false)) changedSnapshots++;
    }
    if (changedEditors || changedSnapshots) {
        for (const node of allDirectorGraphNodes().map(e => e.node)) {
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
        pendingReset.delete(node);
        // A cleared pin is NOT a new generation instruction. In Recipe
        // mode, only watchRecipeReservations may unlock the Director:
        // the legacy observer does not understand NEXT selection/drafts.
        if ((app.graph?._nodes ?? []).some(isRecipePromptNode)) continue;
        if (!timelineReservationState(node)?.activePin) continue;

        // Let OBVPM finish +plan / timeline serialization first. By the time
        // timeline.next is committed, the plan snapshot is already being kept;
        // the short debounce also coalesces multi-step UI updates.
        const timer = setTimeout(() => {
            pendingReset.delete(node);
            if (timelineNextFingerprint(node) !== fp) return;
            if ((app.graph?._nodes ?? []).some(isRecipePromptNode)) return;
            if (!timelineReservationState(node)?.activePin) return;
            resetMaterializedShotStates("timeline.next changed (active pin)");
        }, 500);
        pendingReset.set(node, timer);
    }
}

function refreshAnalysis(snapshot) {
    setMaterialized(snapshot,false);
    for (const builder of upstreamRequestBuilders(snapshot)) updateReferenceStatus(builder,"○ Reference roles: waiting for refreshed Pass #1");
    for (const editor of downstreamEditors(snapshot)) { setMaterialized(editor,false); editor.__directorValidationFresh = false; }
    app.graph?.change?.();
}
function widgetOf(node,name) { return node?.widgets?.find(w => w.name === name); }
function writeControl(node,w,value) {
    if (!w || w.value === value) return;
    w.value=value; w.callback?.(value,app.canvas,node,w); node.setDirtyCanvas?.(true,true);
    app.graph?.change?.();
}
function isCore(node) { return !!node?.subgraph && (node.properties?.obvpm_director_core === true || node.subgraph.name === "H3 Director Core (obvpm)"); }
// Fixed-height, two-line readout on the Core. DOM widgets wrap text instead
// of the native single-line string input's ellipsis. Never serialize readouts.
function addCoreReadout(node, name, initial) {
    if (typeof document !== "undefined" && typeof node.addDOMWidget === "function") {
        const row=document.createElement("div"), label=document.createElement("div"), text=document.createElement("div");
        const height=42;
        row.style.cssText="box-sizing:border-box;width:100%;height:42px!important;min-height:42px!important;max-height:42px!important;display:grid;grid-template-columns:minmax(0, 38%) minmax(0,1fr);gap:6px;align-items:center;overflow:hidden;--comfy-widget-min-height:42px;--comfy-widget-max-height:42px;";
        label.textContent=name;
        label.style.cssText="font:12px/15px sans-serif;color:var(--descrip-text,#aaa);padding-left:3px;";
        text.style.cssText="box-sizing:border-box;min-width:0;max-height:36px;line-height:15px;font-size:12px;padding:3px 7px;background:var(--comfy-input-bg,#292929);border-radius:4px;white-space:pre-wrap;overflow-wrap:anywhere;overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;";
        row.append(label,text);
        const w=node.addDOMWidget(name,"director-core-readout",row,{serialize:false,margin:0,getMinHeight:()=>height,getMaxHeight:()=>height,getHeight:()=>height});
        if (w) {
            w.serialize=false; w.__directorReadout={text,value:undefined};
            updateReadout(node,w,initial);
            return w;
        }
    }
    const w=node.addWidget("text",name,initial,null,{serialize:false,readOnly:true});
    if(w) w.disabled=true;
    return w;
}
function updateReadout(node,w,value) {
    if (!w) return;
    const readout=w.__directorReadout;
    if (readout) {
        if (readout.value===value) return;
        readout.value=value;
        readout.text.textContent=String(value??"");
        readout.text.title=String(value??"");
        if(w.name==="Director Status") {
            const state=String(value??"");
            readout.text.style.color=/^PASS(?:\s|$)/.test(state)?"#86c597":/^(?:SAVED )?FAIL(?:\s|$)/.test(state)?"#e99b96":/^(?:SAVED )?WARNING(?:\s|$)/.test(state)?"#ddc077":"";
        }
    } else {
        if (w.value === value) return;
        w.value=value;
    }
    node.setDirtyCanvas?.(true,true);
}
// Read only the outermost saved Analyst JSON object. Mirror the backend's
// mild fence/prose/one redundant closing-brace tolerance, without accepting
// nested fragments or inventing a fallback direction.
function parseSavedAnalyst(raw) {
    let text = String(raw ?? "").trim();
    text = text.replace(/^```(?:json)?\s*\n?/i, "").replace(/\n?```\s*$/, "").trim();
    const start = text.indexOf("{");
    if (start < 0 || /[{}\[\]]/.test(text.slice(0,start))) return null;
    let depth = 0, quoted = false, escaped = false;
    for (let i = start; i < text.length; i++) {
        const ch = text[i];
        if (quoted) {
            if (escaped) escaped = false;
            else if (ch === "\\") escaped = true;
            else if (ch === '"') quoted = false;
            continue;
        }
        if (ch === '"') quoted = true;
        else if (ch === "{") depth++;
        else if (ch === "}" && --depth === 0) {
            const tail = text.slice(i+1).trim();
            if (tail !== "}" && /[{}\[\]]/.test(tail)) return null;
            try { return JSON.parse(text.slice(start,i+1)); } catch (_) { return null; }
        }
    }
    return null;
}
function passOneDirection(snapshot, editor = null) {
    const raw = widgetOf(snapshot,"snapshot_raw_analysis")?.value;
    let analysis = parseSavedAnalyst(raw);
    let normalized = false;
    const frozen = widgetOf(snapshot,"materialized")?.value === true;
    // Saved normalized analysis is a secondary, explicitly labeled source.
    // Never present an older Shot Editor result as a newly pending Pass #1.
    if ((!analysis || !analysis.intent) && frozen && widgetOf(editor,"materialized")?.value === true) {
        analysis = parseSavedAnalyst(widgetOf(editor,"shot_analysis")?.value);
        normalized = !!analysis;
    }
    if (!analysis || !analysis.intent || typeof analysis.intent !== "object") return "";
    const out = [frozen
        ? (normalized ? "Saved Pass #1 · Composer-normalized analysis (raw snapshot unavailable)" : "Captured Pass #1 · Analyst direction (before Composer normalization)")
        : "Previous Pass #1 · refresh pending (not a new analysis)"];
    const fields = (object, keys) => keys.flatMap(([key,label]) => {
        const v = object?.[key];
        return typeof v === "string" && v.trim() ? [`${label}: ${v.trim()}`] : [];
    });
    const section = (title, lines) => { if (lines.length) out.push("",title,...lines); };
    section("Direction",fields(analysis.intent, [["user_action_anchor","User action"],["story_goal","Goal"],["micro_scene_concept","Concept"],["specific_story_beat","Beat"],["dominant_action","Action"],["interpersonal_dynamic","Interaction"],["start_state_assumption","Start"],["behavior_progression","Progression"],["micro_motion_progression","Micro-motion"],["end_state","End"]]));
    for (const track of Array.isArray(analysis.performance_tracks) ? analysis.performance_tracks : []) {
        const lines = fields(track, [["user_owned_action","Action"],["start_state","Start"],["motion_details","Performance"],["response_to","Response"],["timing","Timing"],["end_state","End"]]);
        section(`Performance · ${typeof track?.actor_id === "string" ? track.actor_id : "Actor"}`,lines);
    }
    for (const interaction of Array.isArray(analysis.interaction_dynamics) ? analysis.interaction_dynamics : []) {
        section("Coordination",fields(interaction,[["shared_action","Shared action"],["coordination","Coordination"],["timing_relation","Timing"],["contact_or_spacing","Contact / spacing"]]));
    }
    section("Camera & sound",fields(analysis.intent,[["camera_intent","Camera"],["shot_scale","Scale"],["framing_transition","Framing"],["visibility_notes","Visibility"],["dialogue_plan","Dialogue"],["sound_plan","Sound"]]));
    if (out.length === 1) return "";
    return out.join("\n");
}
function viewPassOneDirection(snapshot, editor = null) {
    const content = passOneDirection(snapshot, editor);
    if (!content) return recipeNotice("No readable Pass #1 direction captured. Run DIRECT with the Analysis Snapshot unfrozen, or inspect the saved analysis inside the Core.");
    viewSavedGen2Trace(snapshot ?? editor,null,"Pass #1 Direction",content);
}
function corePassOneSources(host) {
    const snapshot = graphNodes(host?.subgraph).find(isAnalysisSnapshotNode);
    const editors = directorReachable(host,false).filter(isShotStateNode);
    return { snapshot, editor: editors.length === 1 ? editors[0] : null };
}
function passOnePreview(content) {
    if (!content) return "No analysis captured · run DIRECT";
    const lines = content.split("\n");
    const line = lines.find(l => l.startsWith("Action: ")) ?? lines.find(l => l.startsWith("Beat: ")) ?? lines.find(l => l.startsWith("Progression: ")) ?? lines.find(l => l.startsWith("Concept: ")) ?? lines.find(l => l.startsWith("Goal: ")) ?? lines.find(l => l.includes(": ")) ?? "Direction available";
    return (lines[0].startsWith("Previous") ? "Previous · " : lines[0].startsWith("Saved") ? "Saved · " : "") + line.replace(/^[^:]+: /, "");
}
function attachPassOneReadout(node) {
    if (node.__directorPassOneReadout) return node.__directorPassOneReadout;
    if (typeof document !== "undefined" && typeof node.addDOMWidget === "function") {
        const element = document.createElement("textarea");
        element.readOnly = true; element.spellcheck = false;
        element.value = "No analysis captured · run DIRECT";
        element.style.cssText = "box-sizing:border-box;width:100%;height:240px;min-height:240px;max-height:240px;resize:none;white-space:pre-wrap;overflow:auto;background:var(--comfy-input-bg,#222);color:var(--input-text,#eee);font:12px/1.4 monospace;padding:8px;--comfy-widget-min-height:240px;--comfy-widget-max-height:240px;";
        const w = node.addDOMWidget("Pass #1 Direction","director-pass-one-readout",element,{serialize:false,getMinHeight:()=>240,getMaxHeight:()=>240,getHeight:()=>240});
        w.serialize = false;
        node.__directorPassOneReadout = {widget:w,element};
    } else {
        const w = node.addWidget("text","Pass #1 Direction","No analysis captured · run DIRECT",null,{serialize:false,readOnly:true});
        if (w) w.disabled=true;
        node.__directorPassOneReadout={widget:w};
    }
    return node.__directorPassOneReadout;
}
function updatePassOneReadout(node, content) {
    const r = attachPassOneReadout(node);
    const value = content || "No analysis captured · run DIRECT";
    if (r.element) {
        if (r.element.value !== value) r.element.value = value;
    } else updateReadout(node,r.widget,value);
}
function coreFingerprint(host,snapshot,editor) {
    const builders=upstreamRequestBuilders(snapshot);
    const sources=new Set(builders);
    for (const b of builders) {
        const graph=b.graph??app.graph;
        for (const input of b.inputs??[]) {
            const link=getGraphLink(graph,input.link);
            const sourceId=linkEnd(link,true)[0];
            const source=sourceId==null?null:graph?.getNodeById?.(sourceId);
            if (source) sources.add(source);
        }
    }
    // Include immediate graph-visible inputs (not generated image pixels), plus
    // the model settings and reference links. Never hash captured diagnostics.
    const relevant=[...sources,...graphNodes(host.subgraph).filter(n=>/LlamaCpp/.test(n.type ?? ""))];
    return JSON.stringify(relevant.map(n=>[n.type,n.id,(n.inputs??[]).map(i=>[i.name,i.link]),(n.widgets??[]).filter(w=>!w.name?.includes("status") && w.options?.serialize!==false && w.type!=="button" && w.kind!=="button" && typeof w.value!=="object").map(w=>[w.name,w.value])]));
}
// AUTO-NORMALIZED is evidence of a correction, not proof of validity.
// The validator has already checked the final prompt; never downgrade a FAIL.
function validationOutcome(report) {
    const lines=String(report??"").split(/\r?\n/);
    const has=prefix=>lines.some(l=>new RegExp("^"+prefix+"(?:\\s|$)").test(l));
    const repaired=has("AUTO-NORMALIZED");
    if (has("FAIL")) return {state:"FAIL",repaired};
    if (has("WARNING")) return {state:"WARNING",repaired};
    if (has("PASS")) return {state:"PASS",repaired};
    return {state:"UNKNOWN",repaired};
}
function coreStatus(host,snapshot,editor,compatible) {
    if (!compatible) return "FAIL · missing/incompatible Core nodes or connections — View Status";
    if (!editor) return "WARNING · connect Shot Editor";
    if (widgetOf(snapshot,"materialized")?.value === true && !snapshotComplete(snapshot)) return "FAIL · frozen snapshot incomplete — Re-analyze";
    if (!widgetOf(snapshot,"materialized")?.value || !widgetOf(editor,"materialized")?.value) return "IDLE · DIRECT / analysis pending";
    const validation=String(widgetOf(editor,"shot_validation")?.value ?? "");
    const prompt=String(widgetOf(editor,"shot_h3_prompt")?.value ?? "");
    if (!validation || !prompt) return "IDLE · no validation captured";
    const outcome=validationOutcome(validation);
    if (editor.__directorValidationFresh !== true) {
        if (outcome.state==="FAIL") return "SAVED FAIL · View Status";
        if (outcome.state==="WARNING") return "SAVED WARNING · View Status";
        return "SAVED · run DIRECT to refresh validation";
    }
    if (editor.__directorValidatedPrompt !== prompt) return "WARNING · prompt edited; not revalidated";
    if (outcome.state==="FAIL") return "FAIL · H3 validation — View Status";
    if (outcome.state==="WARNING") return outcome.repaired?"WARNING · normalized; notices remain — View Status":"WARNING · continuity / validation notices — View Status";
    if (outcome.state==="PASS") return outcome.repaired?"PASS · repaired — View Status":"PASS · H3 prompt validation";
    return "WARNING · unrecognized validation report — View Status";
}
function coreCompatibility(host,nodes,snapshot,status,generators) {
    const wired=(n,keys)=>keys.every(key=>n?.inputs?.some(i=>i.name===key && i.link!=null));
    const generatorCompatible=n=>{
        if(n.type==="OllamaImageList_LlamaCppProfiledGenerate") return wired(n,["system","prompt","model_profile","prefill_profile","hardware_profile"]);
        if(!wired(n,["system","prompt","session"])) return false;
        const link=getGraphLink(host.subgraph,n.inputs.find(i=>i.name==="session").link);
        const id=linkEnd(link,true)[0];
        const session=nodes.find(v=>String(v.id)===String(id));
        return ["LlamaCppMtmd_CreateSession","LlamaCppMtmd_CreateRuntimeSession"].includes(session?.type) && wired(session,["model_profile","prefill_profile","hardware_profile"]) && widgetOf(n,"session_unload")?.value===true;
    };
    return !!(snapshot && status && nodes.some(n=>n.type==="H3DirectorResponseValidator") && nodes.some(n=>n.type==="H3DirectorAnalysisCompose") && generators.length===2 && widgetOf(snapshot,"materialized") && host.inputs?.every(i=>i.link!=null) && generators.every(generatorCompatible));
}
function coreDiagnostics(host) {
    const nodes=graphNodes(host.subgraph), snapshot=nodes.find(isAnalysisSnapshotNode);
    const status=nodes.find(n=>n.type==="H3DirectorStatus" || n.comfyClass==="H3DirectorStatus");
    const editors=directorReachable(host,false).filter(isShotStateNode);
    const editor=editors.length===1?editors[0]:null;
    const generators=nodes.filter(n=>["OllamaImageList_LlamaCppProfiledGenerate","LlamaCppMtmd_Generate"].includes(n.type));
    const compatible=coreCompatibility(host,nodes,snapshot,status,generators);
    return {snapshot,status,editors,editor,generators,compatible};
}
function buildCoreStatusReport(host) {
    const {snapshot,editor,editors,compatible}=coreDiagnostics(host);
    const validation=String(widgetOf(editor,"shot_validation")?.value??"");
    const prompt=String(widgetOf(editor,"shot_h3_prompt")?.value??"");
    const snapshotFrozen=widgetOf(snapshot,"materialized")?.value===true;
    const editorFrozen=widgetOf(editor,"materialized")?.value===true;
    const current=snapshotFrozen&&snapshotComplete(snapshot)&&editorFrozen&&editor?.__directorValidationFresh===true&&editor.__directorValidatedPrompt===prompt&&!!prompt.trim();
    const out=["Director Status",coreStatus(host,snapshot,editor,compatible),"", "Core compatibility (basic wiring, not backend version certification): "+(compatible?"PASS":"FAIL — check Core nodes, inputs, sessions and connections"), "Connected Shot Editors: "+editors.length, "Analysis Snapshot: "+(!snapshot?"missing":snapshotFrozen?(snapshotComplete(snapshot)?"materialized":"incomplete frozen state"):"unfrozen / refresh pending"), "Shot Editor: "+(!editor?"not uniquely connected":editorFrozen?"materialized":"unfrozen / composition pending"), "", "H3 validation report · "+(current?"current captured result":"saved / not verified for current inputs and prompt")];
    if (!validation.trim()) out.push("No validation report captured. Run DIRECT to capture the validator result.");
    else {
        const outcome=validationOutcome(validation);
        if(outcome.repaired) out.push(outcome.state==="PASS"?"Normalization applied; final validator checks passed.":outcome.state==="WARNING"?"Normalization applied; advisory warnings remain.":"Normalization applied; remaining findings are not waived.");
        out.push("",validation);
    }
    return out.join("\n");
}
function syncDirectorCore() {
    if (app.configuringGraph) return;
    for (const {node:host} of allDirectorGraphNodes()) {
        if (!isCore(host)) continue;
        const {snapshot,status,editors,editor,generators,compatible}=coreDiagnostics(host);
        if (!host.__directorCoreControls) {
            const controls={}; host.__directorCoreControls=controls;
            for (const [name,index] of [["analysis_seed",0],["editor_seed",1]]) {
                const gen=generators[index]; const seed=widgetOf(gen,"seed");
                if (seed) controls[name]=host.addWidget("number",name,seed.value,v=>writeControl(gen,seed,v),{...(seed.options||{}),serialize:false,step:1,precision:0});
            }
            controls.freeze=host.addWidget("toggle","materialized",!!widgetOf(snapshot,"materialized")?.value,v=>{
                if (!snapshot) return; setMaterialized(snapshot,!!v);
                if (!v) for (const e of directorReachable(host,false).filter(isShotStateNode)) {setMaterialized(e,false);e.__directorValidationFresh=false;}
                app.graph?.change?.();
            },{serialize:false});
            controls.status=addCoreReadout(host,"Director Status","IDLE");
            controls.passOne=addCoreReadout(host,"Pass #1 Direction","No analysis captured · run DIRECT");
            addActionButton(host,"View Pass #1 Direction",()=>{const src=corePassOneSources(host);viewPassOneDirection(src.snapshot,src.editor);});
            addActionButton(host,"View Status",()=>{
                syncDirectorCore();
                viewSavedGen2Trace(host,null,"Director Status",buildCoreStatusReport(host));
            });
            addActionButton(host,"Re-analyze (refresh Pass #1)",()=>{
                if (!snapshot) return;
                refreshAnalysis(snapshot);
                for (const e of directorReachable(host,false).filter(isShotStateNode)) {setMaterialized(e,false);e.__directorValidationFresh=false;}
            },"#8e762e");
            addActionButton(host,"Reset Director Context",requestDirectorContextReset,"#873636");
            host.setDirtyCanvas?.(true,true);
        }
        const c=host.__directorCoreControls;
        updateReadout(host,c.analysis_seed,widgetOf(generators[0],"seed")?.value);
        updateReadout(host,c.editor_seed,widgetOf(generators[1],"seed")?.value);
        updateReadout(host,c.freeze,!!widgetOf(snapshot,"materialized")?.value);
        for (const e of editors) {
            const reset=widgetOf(e,"Reset Director Context (clear saved state)");
            if (reset && !reset.__directorCoreHidden) {
                hideDirectorWidget(reset); reset.__directorCoreHidden=true;
                e.onResize?.(e.size); e.setDirtyCanvas?.(true,true);
            }
        }
        if (editor) {
            if (editor.__directorValidationFresh && snapshot) {
                const fingerprint=coreFingerprint(host,snapshot,editor);
                if (host.__directorObservedEditor !== editor || host.__directorObservedRevision !== editor.__directorCaptureRevision || !host.__directorFingerprint) {
                    host.__directorFingerprint=fingerprint;host.__directorObservedRevision=editor.__directorCaptureRevision;host.__directorObservedEditor=editor;
                } else if (host.__directorFingerprint!==fingerprint) editor.__directorValidationFresh=false;
            } else host.__directorFingerprint=null;
        }
        const text=coreStatus(host,snapshot,editor,compatible);
        updateReadout(host,c.status,text);
        const direction=passOneDirection(snapshot,editor);
        updateReadout(host,c.passOne,passOnePreview(direction));
        if (status) {
            updatePassOneReadout(status,direction);
            updateReadout(status,widgetOf(status,"Status"),text);
            status.__directorReport=String(widgetOf(editor,"shot_validation")?.value ?? "");
        }
    }
}

app.registerExtension({
    name: "obvpm-director.shot-state",

    setup() {
        // Frontend-only observer; no polling of the server and no dependency on
        // private OBVPM implementation details.
        setInterval(() => {
            watchTimelineNext();
            watchRecipeReservations();
            watchRootAdvancement();
            for (const {node} of allDirectorGraphNodes()) if (isShotStateNode(node)) syncApplyButton(node);
            try { syncDirectorCore(); } catch (error) { console.warn("[OBVPM Director] Core UI update failed",error); }
        }, 250);
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "H3DirectorStatus") {
            const created=nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated=function(){
                const result=created?.apply(this,arguments);
                const w=this.addWidget("text","Status","IDLE · awaiting validation",null,{serialize:false,readOnly:true});if(w) w.disabled=true;
                addActionButton(this,"View validation report",()=>viewSavedGen2Trace(this,null,"Director validation",this.__directorReport??""));
                attachPassOneReadout(this);
                addActionButton(this,"View Pass #1 Direction",()=>{
                    const host=allDirectorGraphNodes().find(e=>e.node===this)?.host;
                    if (host && isCore(host)) { const src=corePassOneSources(host); viewPassOneDirection(src.snapshot,src.editor); }
                    else recipeNotice("Pass #1 Direction is available inside a connected Director Core.");
                });
                return result;
            };
            const executed=nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted=function(message){
                executed?.apply(this,arguments);
                const report=message?.director_status?.[0];
                if(typeof report==="string") { this.__directorReport=report; updateReadout(this,widgetOf(this,"Status"),report.split("\n").find(l=>/^(PASS|FAIL|WARNING)/.test(l))??"Validation received"); }
            };
        }
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
            const originalSerialize = nodeType.prototype.onSerialize;
            nodeType.prototype.onSerialize = function(data) {
                const result = originalSerialize?.apply(this,arguments);
                writeSnapshotSerialization(this,data);
                return result;
            };
            const originalConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function(data) {
                const result = originalConfigure?.apply(this,arguments);
                restoreSnapshotSerialization(this,data);
                return result;
            };
            const originalCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const result = originalCreated?.apply(this, arguments);
                addActionButton(this, "Reset Director Context (clear saved state)", requestDirectorContextReset, "#873636");
                addActionButton(this, "Re-analyze (refresh Pass #1)", () => refreshAnalysis(this), "#8e762e");
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
                addActionButton(this, "▶ DIRECT", () => executeDirectorOnly(this), "#286c43");
                putWidgetAfter(this, "▶ DIRECT", "materialized");
                addActionButton(this, "Reset Director Context (clear saved state)",
                    requestDirectorContextReset);
                addActionButton(this, "Apply approved prompt to Recipe", () => {
                    applyApprovedPrompt(this);
                });
                addActionButton(this, "View saved Gen #2 Thinking", () =>
                    viewSavedGen2Trace(this, "shot_gen2_thinking", "Generate #2 Thinking"));
                addActionButton(this, "View saved Gen #2 Raw JSON", () =>
                    viewSavedGen2Trace(this, "shot_gen2_raw_json", "Generate #2 Raw JSON"));
                addActionButton(this, "View / Copy Director Debug Report", () =>
                    viewSavedGen2Trace(this, null, "Director Debug Report",
                        buildDirectorDebugReport(this)));
                addActionButton(this, "Recompose (keep Pass #1)", () => {
                    setMaterialized(this, false);
                    console.log(
                        "[OBVPM Director] Shot Editor unfrozen; Analysis Snapshot remains frozen. " +
                        "Execute the graph to rerun Pass #2."
                    );
                }, "#8e762e");
                applyShotStateWidgetLayout(this);
                syncApplyButton(this);
                return result;
            };

            const originalConfigured = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function() {
                const result = originalConfigured?.apply(this, arguments);
                applyShotStateWidgetLayout(this);
                syncApplyButton(this);
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
                    const wasFrozen = this.widgets?.find(w => w.name === "materialized")?.value === true;
                    applyWidgetValues(this, state, [
                        "shot_direction", "shot_h3_prompt", "shot_analysis",
                        "shot_gen2_thinking", "shot_gen2_raw_json", "shot_validation", "materialized"
                    ]);
                    applyShotStateWidgetLayout(this);
                    this.__directorValidatedPrompt = state.shot_h3_prompt;
                    this.__directorValidationFresh = true;
                    this.__directorCaptureRevision = (this.__directorCaptureRevision ?? 0) + 1;
                    syncApplyButton(this);
                    autoCommitNewRecipe(this, state, wasFrozen);
                    console.log("[OBVPM Director] Shot State materialized; Composer branch is now lazy-blocked.");
                } catch (e) {
                    console.warn("[OBVPM Director] could not materialize shot state widgets", e);
                }
            };
        }
    },
});
