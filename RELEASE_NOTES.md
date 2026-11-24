# OBVPM Director v0.6.4

**A new directing engine and a more compact workspace.**

## Highlights

- **Flavour and performance:** select genre, directing style and performance independently. Modular skills guide both analysis and composition, including individual actor performance and interaction dynamics.
- **Continuity and reference fidelity:** improved action ownership, reference reconciliation, prompt formatting and continuity task handling. Exact user-supplied dialogue remains authoritative, including shared lines when individual speakers can be resolved. Deterministic vocal-event normalization restores missing dialogue tags and speaker IDs for unambiguous, verbatim, locally attributed speech.
- **Director Core:** native ComfyUI subgraph containing the two LLM passes, analysis snapshot, validator and status. Inspect a compact Pass #1 Direction preview or open its read-only semantic plan without running another LLM. View Status exposes the full validator report and distinguishes clean passes, successfully normalized passes, warnings and remaining failures. A correctly bound but uncited environment in shot prose is a warning, not a hard failure.
- **Focused Shot Editor:** prompt-only editing surface; green DIRECT, conditional green Apply, yellow Recompose (keep Pass #1). The Core exposes Re-analyze and Reset Director Context.
- **Current llama.cpp example:** separate Native Sessions, Model Profiles and Prefill Profiles, with automatic unloading after both passes. Gen #1 starts at 8192 context; Gen #2 is text-only. Setup hints are included in the Core and README.
- **Workflow robustness:** append-only Picture socket growth, valid SemVer metadata for copy/paste, compact history controls. Existing queue isolation and Recipe interfaces are retained.

## Upgrade

Install/update H3 OBVPM Director, restart ComfyUI and hard-refresh the browser. Open the new [Core Workspace](examples/H3-Director-Core-Workspace.json), configure both sessions and copy the block into your workflow. Older flat examples are superseded; the individual Director nodes remain available. Connect the required Flavour input and reset/re-analyze snapshots from previous skill versions. For OBVPM, keep the literal Recipe Prompt in its separate `[restore]` group.

See the [README](README.md) for the setup guide and known limitations. The Director is independent of the LLM backend and does not distribute any OBVPM Pro workflow, model weights or reference assets. Status reports basic wiring and prompt validation, not a comprehensive backend version check or a video quality guarantee.

## Validation and known limitations

The release package passes 181 of 182 Python regression tests and all 13 frontend test scripts. One known reference-authority case (`test_duplicate_analyst_hand_subject_removed`) remains open: a secondary detail image may retain a duplicate character Subject. Review bindings and validation before approval. Snapshot persistence after actual ComfyUI reload and OBVPM version restore is not fully live-certified. Simultaneous speech remains generation-model dependent. The colored buttons may differ slightly in width from native controls. See [ROADMAP.md](ROADMAP.md).
