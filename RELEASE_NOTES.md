# v0.6.0rc23 — Release candidate

**Release status:** Pre-release. Proven in local ComfyUI testing; not a guarantee of identical behavior with other LLMs or H3 checkpoints.

## Highlights

- Two externally hosted LLM passes: multimodal visual/semantic analysis followed by text-only H3 prompt composition. No built-in provider, inference engine or automatic third repair LLM.
- Explicitly materialized **Analysis Snapshot** and **Shot Editor** with separate **Re-analyze** and **Recompose** controls.
- Continuity support for OBVPM **Extend, Prepend and Bridge** from START/TARGET boundary states, without replaying completed actions.
- Stable reference-based Subject mapping, `viewer`/POV behavior and soft `target_perspective` versus hard `end_keyframe` roles.
- Deterministic preservation of explicitly quoted user dialogue and conservative normalization of missing speaker IDs, with a fail-closed Validator.
- A portable, Director-only ComfyUI example workflow using optional external llama.cpp Generate nodes, with no bundled model paths, pictures or proprietary OBVPM Pro workflow.

## Recommended models — optional

**Qwen3.8-27B GGUF, preferably a suitable non-thinking configuration**, is our practical recommendation based on local testing. No particular finetune, quantization, model path, model runtime, or hardware is required by the Director itself.

- **Generate #1:** vision-capable model plus its corresponding multimodal projector (`mmproj`).
- **Generate #2:** text-only prompt composer; do not connect the reference-image list or require an `mmproj`.
- The included example uses external `ollama-image-list` llama.cpp profile/generation nodes. This is **one integration example**, not an obligatory backend.
- Context size, token budget and GPU offloading depend on local hardware and available models. The example's hardware/profile settings are illustrative.

## Known limitations and validation policy

- The Validator deliberately reports `FAIL` when formally required bindings or speaker IDs are absent, even if the resulting H3 video looks acceptable; **do not assume `PASS` guarantees a good video or `FAIL` proves a bad one**.
- Missing dialogue IDs are auto-inserted only where uniquely grounded. Incorrect IDs, ambiguous speaker attribution and rewritten user dialogue are not auto-fixed.
- A `target_perspective` reference is a soft Director-level camera goal, not a guarantee that the H3 image-conditioning path will weight or time the picture softly. When targeting a substantially different perspective, verify your own generation workflow's image/first-frame wiring.
- Some Continuity workflows require OBVPM to provide actual pin specs and boundary frames. The example JSON is not a replacement for an H3 video-generation workflow.
- Materialized outputs remain user-authoritative; use **Reset Director Context**, **Re-analyze**, and **Recompose** intentionally.

## Installation

See the repository [`README.md`](README.md) for setup, node responsibilities, wiring and compatibility. The release tag for this candidate is `v0.6.0rc23`.

## Distribution boundary

This repository contains the Director's modular public-source code and its illustrative Director-only workflow. It does **not** include Patreon-exclusive OBVPM Pro workflow JSONs, private user scenes, personal reference images, H3 weights or third-party model packages.
