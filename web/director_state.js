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

app.registerExtension({
    name: "obvpm-director.shot-state",

    setup() {
        // Frontend-only observer; no polling of the server and no dependency on
        // private OBVPM implementation details.
        setInterval(() => {
            watchTimelineNext();
            watchRecipeReservations();
            watchRootAdvancement();
        }, 250);
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
                addActionButton(this, "Apply approved prompt to Recipe", () => {
                    applyApprovedPrompt(this);
                });
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
                    const wasFrozen = this.widgets?.find(w => w.name === "materialized")?.value === true;
                    applyWidgetValues(this, state, [
                        "shot_direction", "shot_h3_prompt", "shot_analysis", "materialized"
                    ]);
                    applyShotStateWidgetLayout(this);
                    autoCommitNewRecipe(this, state, wasFrozen);
                    console.log("[OBVPM Director] Shot State materialized; Composer branch is now lazy-blocked.");
                } catch (e) {
                    console.warn("[OBVPM Director] could not materialize shot state widgets", e);
                }
            };
        }
    },
});
