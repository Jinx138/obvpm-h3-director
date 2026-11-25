# OBVPM Director v0.6.5

**Dialogue and continuity reliability update for v0.6.4.**

## Highlights

- **Dialogue authority:** reconcile exact user speech with the Analyst’s structured actor-level speaker plan. Preserve repeated utterances and indirect speaker references when grounded; unresolved speech is reported rather than silently dropped. Distinguish spoken dialogue from quoted visual text using semantic evidence.
- **Vocal event normalization:** repair unambiguous missing speaker IDs, detached postfix IDs and narrowly scoped extra terminal punctuation without changing spoken words or overriding conflicting assignments. Prefer explicit role labels to incidental narrative mentions.
- **Continuity references:** reconcile current Picture ownership against historical shot-local Subject numbers for Extend, Prepend and Bridge. Incompatible bindings are no longer unioned merely because local numbers coincide.
- **Unchanged workspace:** the v0.6.4 Core layout, Flavour controls, Recipe integration, queue behavior and validation severity policy are retained.

## Upgrade

Update the Director, restart ComfyUI and hard-refresh the browser. Use **Re-analyze → DIRECT** to refresh previously materialized analysis and rebuild the dialogue and reference contracts. Existing v0.6.4 Core wiring remains compatible. The bundled [Core Workspace](examples/H3-Director-Core-Workspace.json) has updated version metadata.

## Validation and limitations

Live testing included alternating and repeated speakers during hotfix development, and a successful Extend on the final development baseline introducing a new reference-backed android, two spoken lines and a separate synchronized foreground logo. Broader language, Prepend and Bridge coverage remains primarily automated or pending live verification. The final package passes 216 of 217 Python regression tests and all 13 frontend test scripts. The known duplicate hand-detail Subject regression remains open. Malformed Analyst JSON is rejected; indirect attribution depends on grounded structured Analyst evidence. Simultaneous speech timing and generated video quality remain model-dependent. The Director does not implement a persistent cross-timeline identity store. See [ROADMAP.md](ROADMAP.md) and [README.md](README.md).

No OBVPM Pro workflows or model weights are distributed.
