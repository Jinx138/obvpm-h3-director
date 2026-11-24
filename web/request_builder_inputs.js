import { app } from "../../scripts/app.js";

// v0.6.4.dev2 LOCAL append-only Picture auto-grow candidate.
// LiteGraph link targets are positional. NEVER reorder or remove an existing
// slot during creation/configure/connection/reload. We alter ONLY the initial
// frontend node definition to start with picture_1; the backend still declares
// picture_1..picture_9. Next picture sockets are appended after connecting the
// currently last numbered socket (the FLOAT widget slot keeps its own index).
// Older saved nodes retain their exact existing socket layout. A separately
// supplied compacted workflow allows one-time, offline migration.
const MAX_PICTURES = 9;
const FIXED_TYPES = Object.freeze({
    pin_specs: "*", audio_in: "AUDIO", video_in: "VIDEO", length: "*",
    hunting: "*", hunt_count: "*",
});
const PICTURE = /^picture_([1-9])$/;

function slotByName(node, name) { return node.inputs?.find(x => x?.name === name); }
function connected(slot) { return slot?.link !== null && slot?.link !== undefined; }
function getLink(graph, id) {
    if (id == null || !graph?.links) return null;
    const links = graph.links;
    if (typeof links.get === "function") {
        return links.get(id) ?? links.get(String(id)) ??
            (Number.isFinite(+id) ? links.get(+id) : null) ?? null;
    }
    return links[id] ?? null;
}
function targetSlot(info) { return Array.isArray(info) ? info[4] : info?.target_slot; }
function sourceId(info) { return Array.isArray(info) ? info[1] : info?.origin_id; }
function sourceSlot(info) { return Array.isArray(info) ? info[2] : info?.origin_slot; }
function linkType(info) { return Array.isArray(info) ? info[5] : info?.type; }
function setTarget(info, index) {
    if (Array.isArray(info)) info[4] = index;
    else if (info) info.target_slot = index;
}
function shouldOwnLink(info, node) {
    if (!info) return false;
    const targetId = Array.isArray(info) ? info[3] : info.target_id;
    return targetId == null || targetId == node.id;
}

// Append-only growth. Loaded nodes keep their saved inputs unchanged, while
// fresh nodes start with picture_1 (frontend definition is pruned on register).
// Preserve sparse historical picture names; never renumber a connected one.
// The last connected picture determines the next free socket, capped at 9.
function ensureNativeSockets(node) {
    if (!Array.isArray(node.inputs) || !node.addInput) return;
    const old = slotByName(node, "total_frames");
    if (old && !slotByName(node, "length")) {
        old.name = "length";
        old.localized_name = "length";
    }
    for (const [name, type] of Object.entries(FIXED_TYPES)) {
        if (!slotByName(node, name)) node.addInput(name, type);
        const slot = slotByName(node, name);
        if (slot) { slot.type = type; slot.localized_name = name; }
    }
    let lastConnectedPicture = 0;
    for (let i = 1; i <= MAX_PICTURES; i++) {
        if (connected(slotByName(node, `picture_${i}`))) lastConnectedPicture = i;
    }
    const required = Math.min(MAX_PICTURES, Math.max(1, lastConnectedPicture + 1));
    for (let i = 1; i <= required; i++) {
        const name = `picture_${i}`;
        if (!slotByName(node, name)) node.addInput(name, "IMAGE");
    }
    for (let i = 1; i <= MAX_PICTURES; i++) {
        const name = `picture_${i}`;
        const slot = slotByName(node, name);
        if (slot) { slot.type = "IMAGE"; slot.localized_name = name; }
    }
    // The FLOAT is a native convertible widget/socket. Do not add, move, or
    // remove it here: ComfyUI owns the widget-input lifecycle.
}

function correctTargets(node, graph) {
    for (let index = 0; index < (node.inputs?.length ?? 0); index++) {
        const slot = node.inputs[index];
        if (!connected(slot)) continue;
        const info = getLink(graph, slot.link);
        if (shouldOwnLink(info, node)) setTarget(info, index);
    }
}

// Only rebind a saved link if the frontend's deserializer reattached the ID
// at a different socket. A snapshot is keyed by name rather than position.
function reconcileSavedNames(node, graph) {
    const saved = node.__directorSavedLinks;
    delete node.__directorSavedLinks;
    if (!Array.isArray(saved)) return;
    for (const {name, link} of saved) {
        const target = slotByName(node, name) ??
            (name === "total_frames" ? slotByName(node, "length") : null);
        const info = getLink(graph, link);
        if (!target || !shouldOwnLink(info, node)) continue;
        if (target.link === link) continue;
        // Preserve other links; do not steal an occupied, distinct socket.
        if (connected(target) && target.link !== link) continue;
        for (const s of node.inputs ?? []) if (s !== target && s?.link === link) s.link = null;
        target.link = link;
    }
}

// A narrow legacy repair for the verified 0.6.2 -> 0.6.3 corruption:
// IMAGE #0 is stored on hunt_count, IMAGE #1 on picture_1, etc. Restrict
// the repair to a contiguous sequence from one origin with ascending output
// slots and with IMAGE link types. Do not guess from names or move real hunt
// diagnostics from other sources. Never shift picture indices blindly.
function repairLegacyImageOffset(node, graph) {
    const hunt = slotByName(node, "hunt_count");
    if (!connected(hunt)) return false;
    const first = getLink(graph, hunt.link);
    if (!first || !shouldOwnLink(first, node) || linkType(first) !== "IMAGE") return false;
    const origin = sourceId(first);
    const firstOut = sourceSlot(first);
    if (origin == null || !Number.isInteger(firstOut)) return false;
    const sequence = [hunt.link];
    for (let i = 1; i < MAX_PICTURES; i++) {
        const slot = slotByName(node, `picture_${i}`);
        if (!connected(slot)) break;
        const info = getLink(graph, slot.link);
        if (!shouldOwnLink(info, node) || linkType(info) !== "IMAGE" ||
            sourceId(info) !== origin || sourceSlot(info) !== firstOut + i) break;
        sequence.push(slot.link);
    }
    // At least the miswired first picture plus one contiguous following
    // picture, and a vacant destination at the end, are necessary evidence.
    if (sequence.length < 2 || sequence.length > MAX_PICTURES) return false;
    const last = slotByName(node, `picture_${sequence.length}`);
    if (!last || connected(last)) return false;
    // All links are known and owned by the same Request Builder.
    hunt.link = null;
    for (let i = 0; i < sequence.length; i++) {
        slotByName(node, `picture_${i + 1}`).link = sequence[i];
    }
    console.warn(`[OBVPM Director] Recovered ${sequence.length} displaced IMAGE links from legacy hunt_count/picture inputs; save the workflow to persist the repair.`);
    return true;
}

function syncSafely(node) {
    if (app.configuringGraph || !node || !Array.isArray(node.inputs)) return;
    ensureNativeSockets(node);
    const graph = node.graph ?? app.graph;
    reconcileSavedNames(node, graph);
    repairLegacyImageOffset(node, graph);
    correctTargets(node, graph);
    node.setDirtyCanvas?.(true, true);
    graph?.setDirtyCanvas?.(true, true);
}

function scheduleSync(node) {
    if (app.configuringGraph || node.__directorInputsSyncPending) return;
    node.__directorInputsSyncPending = true;
    setTimeout(() => {
        node.__directorInputsSyncPending = false;
        if (!app.configuringGraph) syncSafely(node);
    }, 0);
}

function applyDirectionSizing(node) {
    const sizes = [
        {name: "direction", min: 220, max: null, preferred: "67%"},
        {name: "reference_roles", min: 56, max: 96, preferred: "17%"},
    ];
    for (const {name, min, max, preferred} of sizes) {
        const widget = node.widgets?.find(w => w.name === name);
        if (!widget) continue;
        widget.options = widget.options || {};
        widget.options.getHeight = () => preferred;
        widget.options.getMinHeight = () => min;
        if (max !== null) widget.options.getMaxHeight = () => max;
        if (widget.element?.style) {
            widget.element.style.setProperty("--comfy-widget-height", preferred);
            widget.element.style.setProperty("--comfy-widget-min-height", `${min}px`);
            if (max !== null) widget.element.style.setProperty("--comfy-widget-max-height", `${max}px`);
        }
    }
    if (node.__directorLayoutRefreshPending) return;
    node.__directorLayoutRefreshPending = true;
    const refresh = () => {
        node.__directorLayoutRefreshPending = false;
        node.onResize?.(node.size);
        node.setDirtyCanvas?.(true, true);
        app.graph?.setDirtyCanvas?.(true, true);
    };
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(refresh);
    else setTimeout(refresh, 0);
}

function restoreSavedWidgetValues(node, saved) {
    if (!saved || !node.widgets) return;
    const named = saved.widgets_values_named;
    let role, duration;
    if (named && typeof named === "object" &&
        typeof named.reference_roles === "string" &&
        typeof named.duration_seconds === "number") {
        role = named.reference_roles;
        duration = named.duration_seconds;
    } else {
        const values = saved.widgets_values;
        if (!Array.isArray(values) || values.length < 3 ||
            typeof values[1] !== "number" || typeof values[2] !== "string") return;
        role = values[2];
        duration = values[1];
    }
    const rolesWidget = node.widgets.find(w => w.name === "reference_roles");
    const durationWidget = node.widgets.find(w => w.name === "duration_seconds");
    if (rolesWidget) rolesWidget.value = role;
    if (durationWidget) durationWidget.value = duration;
}

app.registerExtension({
    name: "obvpm-director.request-builder-inputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "H3DirectorRequestBuilder") return;
        // The server still accepts all nine optional picture_N arguments.
        // Hide the unused optional definitions ONLY for initial frontend node
        // construction; saved workflows reconstruct their inputs from JSON.
        // This avoids ANY runtime removal (which caused the v0.6.3 drift).
        const optional = nodeData.input?.optional;
        if (optional && typeof optional === "object") {
            for (let i = 2; i <= MAX_PICTURES; i++) {
                delete optional[`picture_${i}`];
            }
        }
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const result = created?.apply(this, arguments);
            applyDirectionSizing(this);
            if (!app.configuringGraph) scheduleSync(this);
            return result;
        };
        const configured = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function() {
            const result = configured?.apply(this, arguments);
            restoreSavedWidgetValues(this, arguments[0]);
            const savedInputs = arguments[0]?.inputs;
            this.__directorSavedLinks = Array.isArray(savedInputs) ?
                savedInputs.filter(x => x?.name && x.link != null)
                           .map(x => ({name: x.name, link: x.link})) : null;
            applyDirectionSizing(this);
            if (!app.configuringGraph) scheduleSync(this);
            return result;
        };
        const changed = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function(type) {
            const result = changed?.apply(this, arguments);
            if (!app.configuringGraph && (type === 1 || type === "input")) scheduleSync(this);
            return result;
        };
    },
    afterConfigureGraph() {
        const seen = new Set();
        function visit(graph) {
            if (!graph || seen.has(graph)) return;
            seen.add(graph);
            for (const node of graph._nodes ?? graph.nodes ?? []) {
                if (node?.type === "H3DirectorRequestBuilder") scheduleSync(node);
                if (node?.subgraph) visit(node.subgraph);
            }
        }
        visit(app.graph);
    },
});
