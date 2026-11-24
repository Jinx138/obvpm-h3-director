import { app } from "../../scripts/app.js";

// ComfyUI workflow/clipboard validation requires SemVer, not normalized PEP 440.
// Migrate only our own local development metadata; never touch a node's state,
// links, widgets, foreign nodepacks or valid version strings.
const directorNodeTypes = new Set([
    "H3DirectorStatus", "H3DirectorFlavour", "H3DirectorRequestBuilder",
    "H3DirectorVRAMHandoff", "H3DirectorAnalysisSnapshot", "H3DirectorContextReset",
    "H3DirectorAnalysisCompose", "H3DirectorResponseValidator", "H3DirectorShotState",
    "H3DirectorRecipePrompt"
]);
function normalizeDirectorVersion(node) {
    if (!node || ![node.comfyClass, node.type].some(t => directorNodeTypes.has(t))) return;
    const p = node.properties;
    if (!p || (p.cnr_id && p.cnr_id !== "h3-obvpm-director")) return;
    const match = /^0\.6\.4\.dev(11|12|13|14|15|16)$/.exec(p.ver);
    if (match) p.ver = `0.6.4-dev.${match[1]}`;
}
function normalizeDirectorGraph(graph, seen = new Set()) {
    if (!graph || seen.has(graph)) return;
    seen.add(graph);
    for (const node of graph._nodes ?? graph.nodes ?? []) {
        normalizeDirectorVersion(node);
        if (node.subgraph) normalizeDirectorGraph(node.subgraph, seen);
    }
}
app.registerExtension({
    name: "obvpm-director.version-metadata",
    nodeCreated(node) { normalizeDirectorVersion(node); },
    loadedGraphNode(node) { normalizeDirectorVersion(node); },
    afterConfigureGraph() { normalizeDirectorGraph(app.graph); }
});
