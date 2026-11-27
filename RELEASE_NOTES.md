# OBVPM Director v0.6.6 — Creative Freedom & Composer Fidelity

A leaner, more expressive Director, based on the locally tested dev.2 build.

## Highlights

- **Creative direction:** delegate staging, cinematography, rhythm, performance and atmosphere to the Analyst wherever user intent leaves room. Replace preventative creative restrictions with focused, positive guidance.
- **Flavour specialization:** selected genre, directing style and performance skills supply relevant expertise without loading unrelated styles. Preserve technical contracts and creative coverage.
- **Composer fidelity:** carry actor-specific motion, reactions, timing and sensory details from the Analyst into the final H3 prompt, rather than flattening or re-directing the performance.
- **External skill architecture:** editable skill files and request templates, a compact prompt assembler, deterministic contract and speaker-resolution modules, and template-aware provenance.
- **Speaker identity:** explicitly distinguish recurring vocal sources from dialogue-event numbering (S1/S2/S1/S2). Existing dialogue authority, normalization and validation remain in place.

## Upgrade

Update the Director, restart ComfyUI and hard-refresh the browser. Run **Re-analyze → DIRECT** to refresh old Analysis Snapshots and skill manifests. Existing workspace wiring, model profiles, node interfaces, Recipe integration and approved stored prompts are retained. The [portable Core Workspace](examples/H3-Director-Core-Workspace.json) has updated version metadata.

## Verification and scope

Across 1,152 profile/operation selections per pass, the dev.2 base system prompts averaged 44% fewer words for the Analyst and 43% fewer for the Composer than dev.1. These measurements exclude dynamic dialogue contracts, analysis JSON and custom Flavour notes; they are not tokenizer measurements or guarantees of inference speed. Initial local user testing reported two Validator PASS results and richer camera instructions, micro-motion and creative direction. Broader live coverage remains ongoing. See [skill architecture](docs/SKILL_ARCHITECTURE.md) and [migration review](SKILL_MIGRATION_DEV2.md).

The Analysis JSON structure and existing reference, dialogue and continuity contracts remain intact. Backend-agnostic Core diagnostics ([issue #2](https://github.com/Jinx138/obvpm-h3-director/issues/2)) remain a separate task. No audio-input branch or additional inference pass is included. Generated video quality and simultaneous speech timing remain model-dependent.

No OBVPM Pro workflows or model weights are distributed.
