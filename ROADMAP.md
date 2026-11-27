# Roadmap — after v0.6.6

Development priorities and longer-term work. Items without a tested implementation are not release promises.

## v0.6.6 — creative direction and skill architecture

v0.6.6 incorporates the tested dev.2 prompt architecture; further live verification continues.

- **dev.1 — included in v0.6.6:** externalize static LLM instructions and request templates, separate deterministic contract and speaker-resolution logic from the prompt assembler, and clarify stable speaker identities for returning speakers.
- **dev.2 — included in v0.6.6, promising initial live feedback:** reduce universal instructions to authority, format, identity and fidelity; delegate cinematic choices to selected flavours. Initial user testing reports two Validator PASS results and richer camera instructions, micro-motion and creative direction. Broader live coverage remains open.
- Preserve creative coverage while removing redundant instructions. Audit restrictions against observed failures, use positive guidance where possible, and treat the previous assembled context size as a soft budget rather than a hard limit. Genre, directing style, performance and tone should contribute their own relevant expertise without leaking into unrelated flavours.
- Continue targeted flavour refinement only where live results reveal a need. Preserve the separation of Analyst direction and Composer delivery; verify that actor-specific motion, timing, cinematography, reactions and sensory detail survive Pass #2.
- Keep dialogue syntax, speaker identity and current machine-derived dialogue contracts available across all genres, including offscreen voices, narrators and commentators. Verify alternating and returning speakers (S1/S2/S1/S2) in live inference; consider guarded ID renumbering or contract deduplication only if results justify it.
- Inspect actual assembled system/user prompts, selected skill manifests and model token usage. Review Analysis JSON field overlap and applicability separately, with explicit snapshot/schema compatibility checks before any interface changes.
- Retain the v0.6.6 baseline until a later change demonstrates a concrete benefit.

## Core backend compatibility

- [Issue #2](https://github.com/Jinx138/obvpm-h3-director/issues/2): replace llama.cpp-only compatibility assumptions with checks of the two-pass data flow and Director interfaces. Distinguish an unknown backend from genuinely broken wiring and from H3 prompt validation.
- Audit backend assumptions in generator discovery, exposed seed controls and model-setting fingerprints. Keep backend-specific checks separate and verify both the reference llama.cpp workflow and an alternative Ollama configuration where available.
- Preserve DIRECT, Re-analyze, Recompose, freeze/materialization and the external inference-node architecture. No additional inference pass is part of this compatibility task.

## Director Context and OBVPM state

- Investigate OBVPM's existing project, timeline, version and restore contracts, including nested subgraph state.
- Target: save and restore the Director's working context (Direction/history, Flavour, seeds, captured analysis, approved prompt and reference bindings) with the corresponding OBVPM timeline/version.
- Define semantics for new/duplicate/switch timeline, save/restore version, and reset; avoid cross-timeline state leakage. Coordinate with OBVPM if an explicit state interface is required. OBVPM remains authoritative for persistence; no parallel Director project manager. Preserve shot-specific Recipe restore independently.

## UI polish

- Indicate stale captured analysis when the current Direction or other relevant inputs differ from the frozen snapshot; do not silently unfreeze it.

- Match the colored DIRECT, Apply, Re-analyze and Reset buttons to native ComfyUI button widths across resize, canvas modes and subgraphs. The attempted width adjustment did not resolve the live discrepancy and is excluded from v0.6.4.

## Verification

- Broaden live regression coverage for multilingual dialogue, alternating speakers, Prepend, Bridge, POV and diverse flavours (including nonhuman/observational scenes). Observe Analyst JSON stability, Composer fidelity, creative diversity and runtime/context usage.
- Prefer focused regression tests for observed failures over preventative creative restrictions. Compare the same frozen analysis when evaluating Composer models.
- Before release: check the portable Core Workspace, packaging and manual Comfy Registry publication workflow; distribute no OBVPM Pro workflows or model weights.

- Verify snapshot persistence in real ComfyUI save/reload and OBVPM restore scenarios.
- Keep backend version certification separate from the structural compatibility check; no blanket certification of external inference integrations.

Simultaneous speech timing is outside this roadmap; the Director supplies attributed dialogue, while H3 controls audio realization.
