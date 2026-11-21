import { app } from "../../scripts/app.js";

// v0.6.3 dev: preserve the fixed backend picture_1..picture_9 contract,
// but keep FIXED socket indices stable before those dynamic image inputs.
// Older workflow link IDs and sparse/noncontiguous pictures must survive
// migration and repeated configure without any link stealing.
const MAX_PICTURES = 9;
const INPUT_ORDER = [
    "pin_specs", "audio_in", "video_in",
    "length", "duration_seconds", "hunting", "hunt_count",
    ...Array.from({ length: MAX_PICTURES }, (_, i) => `picture_${i + 1}`),
];
const PICTURE_RE = /^picture_([1-9])$/;

function byName(node, name) {
    return node.inputs?.find(input => input?.name === name);
}

function isConnected(input) {
    return input?.link !== null && input?.link !== undefined;
}

function addInputIfMissing(node, name, type) {
    if (!byName(node, name)) node.addInput?.(name, type);
}

// Modern LiteGraph uses a LinkMap/Map; older builds use a plain object.
// Resolving both matters: otherwise a reorder appears visually correct but
// target_slot keeps the old picture index and the next connection steals it.
function getLink(graph, id) {
    const links = graph?.links;
    if (!links || id == null) return null;
    if (typeof links.get === "function") {
        return links.get(id) ?? links.get(String(id)) ??
            (Number.isFinite(Number(id)) ? links.get(Number(id)) : null) ?? null;
    }
    return links[id] ?? null;
}

function reorderSlotsWithoutDroppingLinks(node) {
    const slots = node.inputs;
    if (!Array.isArray(slots)) return;
    const order = name => {
        const i = INPUT_ORDER.indexOf(name);
        return i < 0 ? INPUT_ORDER.length : i;
    };
    const sorted = [...slots].sort((a, b) => order(a.name) - order(b.name));
    if (!sorted.every((slot, i) => slot === slots[i])) {
        slots.splice(0, slots.length, ...sorted);
    }
    // A link's target_slot is positional, not keyed by input name. Repair it
    // after insertion/sorting, including the old 4-picture saved workflows.
    // Both modern link objects and older LiteGraph array links are supported.
    for (let i = 0; i < slots.length; i++) {
        const slot = slots[i];
        if (!isConnected(slot)) continue;
        const link = getLink(node.graph, slot.link) ?? getLink(app.graph, slot.link);
        if (Array.isArray(link)) link[4] = i;
        else if (link) link.target_slot = i;
    }
}

// v0.6.2 made duration_seconds widget-only and retired older FLOAT sockets.
// v0.6.3 RESTORES its connectable socket: preserve existing duration links.
// New ComfyUI defines this as a standard required FLOAT/widget pair, while
// old workflow JSONs may lack the input entirely; add it if absent after load.
function ensureDurationSocket(node) {
    addInputIfMissing(node, "duration_seconds", "FLOAT");
    const socket = byName(node, "duration_seconds");
    if (socket) {
        socket.type = "FLOAT";
        socket.localized_name = "duration_seconds";
    }
}

// UI4 exposed the timeline frame input as total_frames. Preserve its link
// when upgrading saved workflows while giving the socket the name of the
// OBVPM Unbundle output: length.
function migrateLegacyLengthSocket(node) {
    const old = byName(node, "total_frames");
    if (!old) return;
    const current = byName(node, "length");
    if (!current) {
        old.name = "length";
        old.localized_name = "length";
        return;
    }
    if (isConnected(old)) {
        if (isConnected(current)) {
            console.warn("[OBVPM Director] length and total_frames both wired; retaining both until resolved");
            return;
        }
        current.link = old.link;
        old.link = null;
    }
    const index = node.inputs.indexOf(old);
    if (index >= 0) node.removeInput(index);
}

function syncPictureInputs(node) {
    if (app.configuringGraph) return; // Never mutate slots during link restore.
    if (!Array.isArray(node.inputs) || !node.addInput || !node.removeInput) return;
    // Only post-configure: never mutate saved socket indices during restore.
    migrateLegacyLengthSocket(node);
    ensureDurationSocket(node);
    // Old workflows may have slots 2..4 (or even 9) connected while earlier
    // inputs are empty. Keep all connections and the highest connected index.
    let highestConnected = 0;
    for (const slot of node.inputs) {
        const match = PICTURE_RE.exec(slot?.name ?? "");
        if (match && isConnected(slot)) highestConnected = Math.max(highestConnected, +match[1]);
    }
    const visible = Math.min(MAX_PICTURES, Math.max(1, highestConnected + 1));
    // Remove only trailing, unconnected picture slots. Never remove a slot
    // with a link ID, including during a saved-workflow restore.
    for (let i = MAX_PICTURES; i > visible; i--) {
        const index = node.inputs.findIndex(slot => slot.name === `picture_${i}`);
        if (index >= 0 && !isConnected(node.inputs[index])) node.removeInput(index);
    }
    for (let i = 1; i <= visible; i++) addInputIfMissing(node, `picture_${i}`, "IMAGE");
    // Newly introduced media inputs are reserved, but kept visible and typed.
    addInputIfMissing(node, "pin_specs", "*");
    // Existing saved workflows serialize slot types: widen older pin_specs
    // sockets as well, otherwise the new backend wildcard is still blocked
    // by the loaded frontend's OBVPM_H3_PINSPECS slot type.
    const pinInput = byName(node, "pin_specs");
    if (pinInput) pinInput.type = "*";
    addInputIfMissing(node, "audio_in", "AUDIO");
    addInputIfMissing(node, "video_in", "VIDEO");
    // OBVPM Timeline Unbundle `length`: integer frame count, wildcard
    // transport type. This is the authoritative duration when connected.
    addInputIfMissing(node, "length", "*");
    const lengthInput = byName(node, "length");
    if (lengthInput) {
        lengthInput.type = "*";
        lengthInput.localized_name = "length";
    }
    // Stable OBVPM diagnostics stay BEFORE the growing picture socket family.
    // After each mutation, repair positional link target_slot by semantic name.
    addInputIfMissing(node, "hunting", "*");
    addInputIfMissing(node, "hunt_count", "*");
    for (const name of ["hunting", "hunt_count"]) {
        const input = byName(node, name);
        if (input) { input.type = "*"; input.localized_name = name; }
    }
    reorderSlotsWithoutDroppingLinks(node);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

// UI2: establish actual *constraints* in ComfyUI's layout engine, not only
// preferred percentage heights. In some frontend builds a getHeight("68%")
// preference alone leaves both multiline widgets equally tall.
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
            if (max !== null) {
                widget.element.style.setProperty("--comfy-widget-max-height", `${max}px`);
            }
        }
    }
    // Rerun layout *after* the widget constraints are attached. Without
    // this, ComfyUI can retain the equal-height layout from node creation.
    // Do not change node dimensions or any stored values here.
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

// Before rc24-ui1 the serialized widget array was: direction, duration,
// reference_roles. The native UI order is now: direction, reference_roles,
// duration. Accept old saves without swapping the numeric duration and the
// role text. Current saves use the named values when available.
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

// Deferring until the current graph mutation finishes avoids changing slot
// indices during LiteGraph's onConnectionsChange dispatch and before the
// saved graph's link map has been fully configured.
function scheduleSync(node) {
    if (app.configuringGraph) return;
    if (node.__directorInputsSyncPending) return;
    node.__directorInputsSyncPending = true;
    setTimeout(() => {
        node.__directorInputsSyncPending = false;
        syncPictureInputs(node);
    }, 0);
}

app.registerExtension({
    name: "obvpm-director.request-builder-inputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "H3DirectorRequestBuilder") return;
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
            // ComfyUI restores link target_slot by INDEX. On graph load the
            // snapshot records which LINK was attached to which named socket.
            // Reconcile only once the entire graph has finished configuring.
            const savedInputs = arguments[0]?.inputs;
            this.__directorSavedLinks = Array.isArray(savedInputs)
                ? savedInputs.filter(x => x?.name && x.link != null)
                             .map(x => ({ name: x.name, link: x.link }))
                : null;
            applyDirectionSizing(this);
            if (!app.configuringGraph) scheduleSync(this);
            return result;
        };
        const connectionsChanged = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function(type, index, connected, link, slot) {
            const result = connectionsChanged?.apply(this, arguments);
            if (!app.configuringGraph && (type === 1 || type === "input")) scheduleSync(this);
            return result;
        };
    },
    afterConfigureGraph() {
        // A separate post-configure phase is essential: removing/reordering
        // sockets inside onConfigure/onConnectionsChange races the frontend's
        // link reconstruction and leads to cumulative picture-link drift.
        // Walk nested subgraphs as well as the root. A saved Director inside
        // a subgraph must receive the same semantic link repair on reload.
        const seen = new Set();
        function visit(graph) {
            if (!graph || seen.has(graph)) return;
            seen.add(graph);
            const nodes = graph._nodes ?? graph.nodes ?? [];
            for (const node of nodes) {
                if (node?.type === "H3DirectorRequestBuilder") {
                    if (Array.isArray(node.__directorSavedLinks)) {
                        const mapping = node.__directorSavedLinks;
                        delete node.__directorSavedLinks;
                        for (const {name, link: id} of mapping) {
                            const slot = byName(node, name) ??
                                (name === "total_frames" ? byName(node, "length") : null);
                            const info = getLink(node.graph ?? graph, id);
                            if (!slot || !info) continue;
                            // Recover semantic endpoint by saved INPUT NAME,
                            // regardless of its old positional target_slot.
                            for (const candidate of node.inputs ?? []) {
                                if (candidate !== slot && candidate?.link === id) candidate.link = null;
                            }
                            slot.link = id;
                        }
                    }
                    scheduleSync(node);
                }
                if (node?.subgraph) visit(node.subgraph);
            }
        }
        visit(app.graph);
    },
});
