# OBVPM Director v0.6.0

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

Install or update the `h3-prompt-composer/` directory under `ComfyUI/custom_nodes/`, restart ComfyUI, and open the [Recipe example](examples/H3-Director-Recipe-MVP.json). See the [README](README.md) for a guided walkthrough and the [changelog](CHANGELOG.md) for development details.

**Verification:** 120 Python tests and all six frontend regression scripts passed during release preparation. The Director implementation files match the tested rc25b.2 source archive byte for byte.
