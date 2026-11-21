# OBVPM Director v0.6.3

**21 November 2026 · Portable workflow and Request Builder compatibility**

This small follow-up release promotes the live-tested `v0.6.3.dev1` build. It focuses on easier integration into vanilla H3 Ref2VA workflows and stable input wiring. No new Director generation logic, prompt-policy changes, or changes to native OBVPM Hunt are included.

## Changes

- **Connectable `duration_seconds`:** The Request Builder offers a FLOAT input and its editable widget. Connect a duration from a vanilla H3 workflow or leave it unconnected and type seconds directly. If an OBVPM Timeline `length` frame count is connected, `length` remains authoritative at **24 fps**.
- **Stable fixed sockets:** `pin_specs`, `audio_in`, `video_in`, `length`, `duration_seconds`, `hunting`, and `hunt_count` stay before the dynamic `picture_1`–`picture_9` inputs. Dynamic image connections no longer shift previously connected timeline inputs. Frontend link reconciliation handles older layouts and newer LiteGraph LinkMap representations, including subgraphs.
- **Tooltips:** Clarify timing precedence, the distinction between Hunt diagnostics and Hunt control, and the conservative 1 MP Generate #1 vision-image cap.
- **Portable example:** The recommended file is now **[`H3-Director-Portable-Workspace.json`](examples/H3-Director-Portable-Workspace.json)** (no MVP/FRESH suffix), with a coherent Director layout, seed 42 on both Generate nodes, both materialization states initially off, and a shared llama.cpp Prefill Profile (`n_batch=1024`, `n_ubatch=0`). Set the models and projector to match your local setup. If memory is limited, try `n_batch=512`.

## Compatibility and scope

The Director is still backend-agnostic and supports use as a **standalone directing layer**: connect its approved H3 prompt to a vanilla H3 Ref2VA prompt input. With OBVPM Timeline, retain the independent Recipe Prompt group for timeline/Recipe restore. No OBVPM Pro/Patreon workflow is bundled.

**Validation:** 134 Python tests and 10 frontend regression scripts passed for the local test build, followed by successful live use with four picture references and correctly retained timeline links. DIRECT, workflow-local prompt history, 1 MP vision scaling, materialization, and the v0.6.2 queue-isolation safeguard remain unchanged. This is intended as a stability update, not the start of a new feature series.

---

# OBVPM Director v0.6.2

**21 November 2026 · Shot iteration, vision scaling and targeted queue safety**

This update promotes the live-tested `v0.6.2.dev3` code to the public release, retaining the Director's independent two-pass architecture and OBVPM Recipe integration.

## Highlights

- **▶ DIRECT:** One-click targeted execution from **H3 Director Shot Editor (obvpm)**, directly below `materialized`. It releases the Shot Editor's freeze when necessary, preserves a separately frozen Analysis Snapshot, and asks ComfyUI to execute only that editor's dependency branch. A frontend submission guard preserves `partial_execution_targets` through the standard ComfyUI queue path, limits the targeted submission to one job, and quietly drops synchronous duplicate submissions instead of displaying an error modal. **Native Full Run and OBVPM Seed Hunt remain unchanged.**
- **Workflow-local Direction / reference-role history:** Save, Delete, Previous, Next, and automatic capture on execution. The history is stored in the Request Builder's serialized workflow properties, so **save the workflow** to persist changes. Existing dev2/dev3 history entries use the same key and remain compatible.
- **Automatic 1 MP vision scaling:** The Request Builder downscales individual reference images for the first, vision-capable LLM pass only. Aspect ratios are retained; images are never upscaled; empty Picture sockets are skipped. Original references for H3 generation are untouched. Includes START/TARGET continuity frames.
- **Optional `hunting` / `hunt_count` inputs:** OBVPM Unbundle status/diagnostics available without changing actual Hunt settings.
- **Dynamic Picture socket stability:** Retains the `length` and sparse Picture reload fix, tested with optional hunt diagnostics.
- **llama.cpp examples:** Both portable example workflows now ship one shared Prefill Profile, `Custom`, with `n_batch=1024`, `n_ubatch=0`, `image_min_tokens=0`, `image_max_tokens=0`. This is a performance-oriented example configuration **not tied to 32 GB VRAM**. Use `n_batch=512` when resource constraints or hardware favor it. GGUF and `mmproj` remain user-selected.

## Usage and caveats

1. Install/update **H3 OBVPM Director** (`h3-obvpm-director`) from ComfyUI Manager after the manual Registry publication, or clone this repository once into `ComfyUI/custom_nodes/` as `h3-prompt-composer`. **Remove duplicate Director installations** before restarting ComfyUI.
2. Install a compatible VLM + text Generate backend separately, open [the Recipe example](examples/H3-Director-Portable-Workspace.json), and select your local models.
3. Analyze and materialize an approved shot with ▶ DIRECT; keep the Analysis Snapshot frozen when varying only the composer. For OBVPM Seed Hunt, use the materialized Recipe prompt as the video-generation source.
4. A diagnostic/output node wired **directly** to a Generate node can force that LLM to execute despite the saved Snapshot/Editor state. Disconnect direct LLM diagnostics before a full Hunt run.

The queue safety feature operates in the **standard browser ComfyUI queue submission path**. It does not intercept arbitrary backend-initiated jobs or independently queued API requests. It does not disable OBVPM Hunt. The Director still intentionally rejects invalid/malformed LLM JSON instead of silently modifying its meaning; tune `n_ctx`, output limits, and model settings for demanding analysis prompts.

**Verification:** 130 Python tests and nine frontend regression scripts passed for the dev3 code baseline during local development; targeted queue isolation and duplicate suppression were additionally confirmed in a live ComfyUI / OBVPM workflow. Public examples remain Director-only and contain no Patreon-exclusive OBVPM Pro workflow.

---

# OBVPM Director v0.6.1

**Version 0.6.1 · 21 November 2026 · ComfyUI llama.cpp compatibility update**

This maintenance release makes the two bundled example workflows compatible with recent versions of the external **ComfyUI-llama-multimodal** nodepack. The OBVPM Director implementation itself remains the same as the tested v0.6.0 release.

## Changes in v0.6.1

- Both `H3-Director-Recipe-MVP.json` (recommended) and `H3-Director-Analysis-Freeze-Recompose.json` now use the current `[llama.cpp] Hardware Runtime Profile` node and connect a required `[llama.cpp] Prefill Profile` to both Generate passes.
- The shared Prefill Profile uses `Custom` with `n_batch=512`, `n_ubatch=0`, `image_min_tokens=0`, and `image_max_tokens=0`. Zero values disable the optional overrides, retaining backend defaults for those controls.
- The README explains the current llama.cpp nodes, model selection, ComfyUI Manager installation, and GGUF / `mmproj` placement.

**Scope:** No changes to Director Python, JavaScript, prompt skills, analysis contract, validator, timeline integration, Recipe behavior, or workflow-local state. The experimental v0.6.1-dev2 UI features are not included. This release does not claim to fix occasional malformed JSON produced by external inference models.

## Install / update

Install or update **H3 OBVPM Director** (`h3-obvpm-director`) to **0.6.1** using ComfyUI Manager after the Registry publication, restart ComfyUI, and open the current [Recipe example](examples/H3-Director-Portable-Workspace.json). The external llama.cpp nodepack is a separate installation and must also be available. Select GGUF model and matching `mmproj` in the Generate nodes. See [README](README.md).

---

# Previous release: OBVPM Director v0.6.0

**Version 0.6.0 · 15 November 2026 · Based on the extensively live-tested rc25b.2 build**

This release brings a more practical shot-planning and prompt-preservation workflow to **MiniMax H3 Ref2VA in ComfyUI**, with dedicated Recipe integration for **OBVPM Timeline 0.5.2**.

## Highlights

- **Editable Recipe Prompt.** `H3 Director Recipe Prompt (obvpm)` holds the literal prompt used for video generation. OBVPM saves and restores this text through the dedicated `Director Prompt [restore]` group, while the main Director Workspace stays focused on your current shot.
- **Automatic preparation for new shots.** Fresh Extend, Prepend, and Bridge reservations prepare the Director for the next shot. After successful materialization, a new prompt can populate an empty Recipe field automatically. Manual **Apply approved prompt to Recipe** remains available for deliberate updates.
- **Root advancement.** A new Root take appended at the end of the video track can prepare the next Root shot, using the timeline's new tail-media information.
- **More flexible inputs.** Up to nine dynamically displayed picture references, optional media inputs, an expanded Direction editor, and frame-length integration with OBVPM Timeline 0.5.2.
- **Proven two-pass directing.** Vision-grounded analysis, text-based H3 composition, verbatim user dialogue, continuity reasoning, reference attribution, validator feedback, and independent analysis/shot materialization.
- **Updated workflow and documentation.** The new `H3-Director-Recipe-MVP.json` demonstrates the separate Director Workspace and Recipe Prompt groups, accompanied by real ComfyUI screenshots.

## Working with Recipes

1. Select a fresh **NEXT RUN** in OBVPM, or prepare a standalone Director shot.
2. Run the Director to analyze the references and materialize an approved H3 prompt.
3. Review the Recipe Prompt. A fresh, empty Recipe may be filled automatically; use **Apply approved prompt to Recipe** to replace it deliberately.
4. Queue H3 generation with the Recipe Prompt connected directly to the H3 conditioning prompt input.

**The current workflow uses two queue steps:** first the Director, then H3 generation. This ensures the approved literal prompt is available when OBVPM captures the take's Recipe.

## Setup and compatibility

- **ComfyUI:** Python 3.10+.
- **LLM interfaces:** vision-capable Generate #1 and text-based Generate #2. The included example uses external `ollama-image-list` llama.cpp nodes; configure your preferred models, matching VLM projector (`mmproj`) where applicable, and hardware settings.
- **OBVPM:** Recipe and timeline behavior developed for OBVPM Timeline 0.5.2.
- **Continuity:** Extend, Prepend, and Bridge read START/TARGET context supplied by OBVPM.
- **Root detection:** automatically reacts to newly observed tail video paths on the Root track. Manually appended new files can trigger the same observation.
- **Recipe behavior:** the automatic transfer fills an empty Recipe for a fresh unique reservation and a single Recipe Prompt node; existing text is preserved until explicitly replaced.
- **Validation:** PASS confirms structural and semantic contracts. Final visual results depend on the H3 model and its conditioning settings.

Install or update the `h3-prompt-composer/` directory under `ComfyUI/custom_nodes/`, restart ComfyUI, and open the [Recipe example](examples/H3-Director-Portable-Workspace.json). See the [README](README.md) for a guided walkthrough and the [changelog](CHANGELOG.md) for development details.

**Verification:** 120 Python tests and all six frontend regression scripts passed during release preparation. The Director implementation files match the tested rc25b.2 source archive byte for byte.
