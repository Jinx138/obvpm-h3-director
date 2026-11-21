import { app } from "../../scripts/app.js";

// History belongs to its Request Builder inside the ComfyUI workflow JSON.
// No browser-wide storage, timeline/Recipe synchronization, or backend storage.
// Only direction + reference_roles are retained, never image or model data.
const HISTORY_PROPERTY = "director_request_history_v1";
const HISTORY_LIMIT = 100;

function widgetsPair(node) {
    const widget = name => node.widgets?.find(w => w.name === name)?.value;
    return {
        direction: String(widget("direction") ?? ""),
        reference_roles: String(widget("reference_roles") ?? ""),
    };
}

function validPair(item) {
    return item && typeof item === "object" &&
        typeof item.direction === "string" && typeof item.reference_roles === "string";
}

function equalPair(a, b) {
    return !!a && !!b && a.direction === b.direction && a.reference_roles === b.reference_roles;
}

function readEntries(node) {
    const raw = node.properties?.[HISTORY_PROPERTY];
    if (!Array.isArray(raw)) return [];
    return raw.filter(validPair).slice(-HISTORY_LIMIT).map(x => ({
        direction: x.direction, reference_roles: x.reference_roles,
    }));
}

function writeEntries(node, entries) {
    node.properties ??= {};
    // Keep a plain JSON-compatible copy so ComfyUI serializes it with this
    // Request Builder. Nothing is written to localStorage or to OBVPM shot data.
    node.properties[HISTORY_PROPERTY] = entries.slice(-HISTORY_LIMIT).map(x => ({
        direction: x.direction, reference_roles: x.reference_roles,
    }));
    app.graph?.change?.();
    return true;
}

function status(node, message = "") {
    const w = node.widgets?.find(x => x.name === "director_history_status");
    if (!w) return;
    const entries = readEntries(node);
    const state = node.__directorHistory;
    const current = widgetsPair(node);
    const selected = state?.cursor >= 0 ? entries[state.cursor] : null;
    const label = selected
        ? `${state.cursor + 1}/${entries.length}${equalPair(current, selected) ? "" : " · edited"}`
        : `draft · ${entries.length} saved`;
    w.value = `History: ${message || label}`;
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function notice(node, message) {
    status(node, message);
    console.info(`[OBVPM Director] ${message}`);
}

function applyPair(node, pair) {
    if (!validPair(pair)) return;
    const state = node.__directorHistory;
    state.applying = true;
    try {
        for (const key of ["direction", "reference_roles"]) {
            const w = node.widgets?.find(x => x.name === key);
            if (!w) continue;
            w.value = pair[key];
            w.callback?.(w.value, app.canvas, node, w);
        }
    } finally {
        state.applying = false;
    }
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
    app.graph?.change?.();
}

function rememberDraft(node, entries) {
    const state = node.__directorHistory;
    const now = widgetsPair(node);
    if (state.cursor < 0 || !equalPair(now, entries[state.cursor])) {
        state.draft = now;
    }
}

function showIndex(node, entries, index) {
    const state = node.__directorHistory;
    if (index < 0 || index >= entries.length) {
        state.cursor = -1;
        applyPair(node, state.draft ?? widgetsPair(node));
    } else {
        state.cursor = index;
        applyPair(node, entries[index]);
    }
    status(node);
}

function previous(node) {
    const entries = readEntries(node);
    if (!entries.length) return notice(node, "no saved entries");
    rememberDraft(node, entries);
    const cursor = node.__directorHistory.cursor;
    showIndex(node, entries, cursor < 0 ? entries.length - 1 : Math.max(0, cursor - 1));
}

function next(node) {
    const entries = readEntries(node);
    if (!entries.length) return notice(node, "no saved entries");
    const cursor = node.__directorHistory.cursor;
    if (cursor < 0) return notice(node, "already on draft");
    rememberDraft(node, entries);
    showIndex(node, entries, cursor + 1);
}

function recordPair(pair, node, source) {
    if (!validPair(pair) || (!pair.direction.trim() && !pair.reference_roles.trim())) {
        notice(node, "empty direction/roles not saved");
        return false;
    }
    const entries = readEntries(node);
    // Repeated seed runs do not flood the list. An edited old entry becomes
    // a new pair; repeating an existing one promotes it to the newest slot.
    const prior = entries.findIndex(entry => equalPair(entry, pair));
    if (prior >= 0) entries.splice(prior, 1);
    entries.push(pair);
    writeEntries(node, entries);
    const state = node.__directorHistory;
    if (equalPair(widgetsPair(node), pair)) {
        state.cursor = entries.length - 1;
        state.draft = pair;
    } else {
        // The queued run may complete after the user has edited the form.
        // Store the executed inputs without replacing their live draft.
        state.cursor = -1;
        state.draft = widgetsPair(node);
    }
    status(node);
    if (source === "execution") {
        console.info("[OBVPM Director] executed Request Builder pair recorded in workflow");
    }
    return true;
}

function save(node) {
    recordPair(widgetsPair(node), node, "manual");
}

function removeSelected(node) {
    const entries = readEntries(node);
    const state = node.__directorHistory;
    const index = state.cursor;
    if (index < 0 || index >= entries.length) {
        return notice(node, "select a saved entry before Delete");
    }
    if (!equalPair(widgetsPair(node), entries[index])) {
        return notice(node, "unsaved edits: Save or navigate before Delete");
    }
    if (typeof window !== "undefined" && typeof window.confirm === "function" &&
        !window.confirm(`Delete saved Director direction/roles ${index + 1}/${entries.length}?`)) return;
    entries.splice(index, 1);
    writeEntries(node, entries);
    if (entries.length) showIndex(node, entries, Math.min(index, entries.length - 1));
    else showIndex(node, entries, -1);
}

function addHistoryButton(node, name, handler) {
    if (node.widgets?.some(w => w.name === name)) return;
    const w = node.addWidget("button", name, null, () => handler(node), {serialize: false});
    if (w) w.options = {...(w.options || {}), serialize: false};
}

function attachHistory(node) {
    if (node.__directorHistory) return;
    node.__directorHistory = {cursor: -1, draft: widgetsPair(node), applying: false};
    addHistoryButton(node, "History · Save", save);
    addHistoryButton(node, "History · Delete", removeSelected);
    addHistoryButton(node, "History · ◀ Previous", previous);
    addHistoryButton(node, "History · Next ▶", next);
    const label = node.addWidget("text", "director_history_status", "", null,
        {serialize: false, readOnly: true});
    if (label) {
        label.options = {...(label.options || {}), serialize: false, readOnly: true};
        label.disabled = true;
    }
    status(node);
}

app.registerExtension({
    name: "obvpm-director.request-builder-history",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "H3DirectorRequestBuilder") return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const result = created?.apply(this, arguments);
            attachHistory(this);
            return result;
        };
        const configured = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(info) {
            const result = configured?.apply(this, arguments);
            // onConfigure is called once the saved node properties have been
            // restored. Never replace the workflow's current Direction/roles.
            if (this.__directorHistory) {
                this.__directorHistory.cursor = -1;
                this.__directorHistory.draft = widgetsPair(this);
                status(this);
            }
            return result;
        };
        const executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function(message) {
            executed?.apply(this, arguments);
            const raw = message?.director_request_history?.[0] ?? message?.director_request_history;
            if (!raw) return;
            try {
                const pair = typeof raw === "string" ? JSON.parse(raw) : raw;
                recordPair(pair, this, "execution");
            } catch (error) {
                console.warn("[OBVPM Director] invalid executed history payload", error);
            }
        };
    },
});
