# Roadmap — after v0.6.4

These items are deferred, not promised for a particular release.

## Director Context and OBVPM state

- Investigate OBVPM's existing project, timeline, version and restore contracts, including nested subgraph state.
- Target: save and restore the Director's working context (Direction/history, Flavour, seeds, captured analysis, approved prompt and reference bindings) with the corresponding OBVPM timeline/version.
- Define semantics for new/duplicate/switch timeline, save/restore version, and reset; avoid cross-timeline state leakage. Coordinate with OBVPM if an explicit state interface is required. OBVPM remains authoritative for persistence; no parallel Director project manager. Preserve shot-specific Recipe restore independently.

## UI polish

- Match the colored DIRECT, Apply, Re-analyze and Reset buttons to native ComfyUI button widths across resize, canvas modes and subgraphs. The attempted width adjustment did not resolve the live discrepancy and is excluded from v0.6.4.

## Reference authority

- Investigate the outstanding `test_duplicate_analyst_hand_subject_removed` regression. A secondary detail reference explicitly belonging to an existing character should not remain a separate Subject; keep ambiguity safeguards.

## Verification

- Verify snapshot persistence in real ComfyUI save/reload and OBVPM restore scenarios.
- Consider a version-aware backend compatibility check; current status only checks basic wiring and captured validation.

Simultaneous speech timing is outside this roadmap; the Director supplies attributed dialogue, while H3 controls audio realization.
