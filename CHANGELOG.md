## 0.6.0rc23 — 2026-11-07

- **Strictly missing vocal markers:** extend the rc17 live-output speaker-ID normalizer to recognize uniquely referenced descriptive speakers such as "the younger man" / "the older man in the blue shirt", using the same conservative resolver as rc22. An adjacent speech-action cue is required before adding an `(Sx)`; unrelated Subject mentions, offscreen voices, or uncertain attribution are not corrected.
- **Fail closed:** never overwrite an existing conflicting `(Sx)` ID. Reject changed, missing, or reordered user-owned utterances. Do not change dialogue bytes, staging, other H3 prose, materialized/frozen Shot Editor text, or manually edited prompts.
- Supply uniquely grounded descriptive speaker mappings to the existing Validator's attribution check. No third LLM pass, new nodes/ports, OBVPM timeline logic, or changes to Extend/Prepend/Bridge boundaries, references, POV, or materialization behavior.
- Synthetic regression tests include wrong-existing-ID safety, offscreen voices, ambiguous descriptions, mismatched text, and a mixed named/unnamed attribution case. Private diagnostic replays are used locally but excluded from the archive. Live ComfyUI acceptance remains to be checked.

## 0.6.0rc22 — 2026-11-07

- **Composer delivery clarity, text-only Pass #2:** add an explicit, machine-derived ordered list of user-authoritative utterances, including verbatim wording, unique reference-backed `<Subject N>` attributions when deterministically resolvable, and stable first-vocal-source `(Sx)` numbering. Repeated sources reuse an ID; ambiguous names/roles are left unresolved, never assigned to a guessed Subject.
- **Visible environment contract:** require `<Subject N>` (or bare `<Picture N>` for a Picture-only environment) inside `detailed_description` only for shot-visible bindings. Respect rc19 `required_in_shot: false` so offscreen close-up locations are not forced into frame or invented as new Subjects.
- **Prompt priorities:** move the compact, run-specific delivery contract to the end of the composer user request after the directing task and eliminate several redundant system rules. Keep open cinematic decisions and shot-specific motion free where the user/continuity has not fixed them.
- Only Composer request construction and associated tests changed; no output prompt auto-edit, validator relaxation, extra LLM pass, node/socket/UI change, materialization/Freeze behavior change, or OBVPM timing/editing duplication. The automatic timeline/materialization switch remains an unverified separate issue.
- 92 Python tests and 2 frontend tests, including a private deterministic request replay of the observed failed rc21 Extend. Real Qwen compliance improvement requires new live Vanilla tests; a static contract test is not evidence of film continuity.

## 0.6.0rc21 — 2026-11-07

- Fix rc18 deterministic `authoritative_dialogue` extraction when explicit quoted speech follows a stage action (`The younger man looks ... and says`) or has stage direction after the closing quote (`... replies: "..." As he speaks, ...`). Previously the actor label could absorb stage prose and a following utterance could be dropped entirely.
- Accept multiple explicitly attributed quote events on one line, paired typographic quotation marks and apostrophes inside single-quoted contractions. Preserve the exact spoken words and original event order; do not invent speech from unattributed quotations.
- Regression coverage for Request Builder authority, Analysis → Compose normalization, speaker attribution, and unchanged validator H3 output. The actual rc20 11-second Extend composer output revalidates PASS with no prompt edits once the authority contract is corrected.
- No changes to H3 prompt grammar, two-pass LLM architecture, materialized/freeze UI, continuity endpoints, action validator, OBVPM-owned duration/snapping or reference rules. Automatic Timeline → materialization reset remains an unconfirmed separate observation.

## 0.6.0rc20 — 2026-11-07

- Fix rc19 actor/target detection for hand-pin clauses containing intervening object Subjects before the pinning verb (e.g. "S2 holds S1 down, and pins S1's hands"). Do not mistake the object of an earlier verb for the pinning actor.
- Retain fail-closed detection of an extra reversed pin; do not change the reference/visibility requirements or rewrite LLM-generated prose.
- Document the live-confirmed ComfyUI circular-dependency limitation when Request Builder `duration_seconds` is connected to the same Timeline node supplying its `pin_specs`; retain existing ports and FLOAT passthrough for compatibility.
- No changes to materialization, START/TARGET continuity, two-pass generation, dialogue authority, or OBVPM-owned timing/overlap.

## 0.6.0rc19 — 2026-11-07

- Keep the existing Director Request Builder `duration_seconds` FLOAT input and expose a same-value FLOAT output for the OBVPM Timeline. Do not duplicate OBVPM frame snapping or overlap ownership. No new Duration node or timeline-length feedback.
- Separate inherited scene/location knowledge from shot-visible reference obligations. Established locations may remain implicit for close-up crops unless the user explicitly requires a visible location; medium/wide shots retain reference-binding validation.
- Add conservative deterministic `action_contract` for explicit user-owned actor→target hand-pin directives, and reject missing or reversed pins in the H3 detailed description. Do not infer action rules for unrelated choreography or auto-rewrite the prompt.
- Keep two LLM passes, materialized Shot Editor, START/TARGET seam endpoints, POV semantics, dialogue authority and OBVPM timeline ownership unchanged.

# Changelog

## v0.6.0rc18 — 2026-11-07

- **User-owned dialogue contract:** Request Builder records explicitly attributed, quoted speech in its existing frozen Director Context; Analysis → Compose overwrites any missing, reordered, paraphrased or contradictory Analyst `speech_request` with the literal user wording and speaker order. No third inference pass.
- **Validator independent authority:** Re-derive user-supplied lines from the frozen Direction before normalization and validation, including when composed analysis is manually edited or from an older snapshot. Missing IDs are filled only with unambiguous sources; wrong literal dialogue or demonstrably swapped speaker attribution fails. Empty `preserve` utterances cannot silently PASS.
- **Scope constrained:** no changes to materialized/editor text, freeze barriers, OBVPM timeline, node IDs, sockets, reference mapping or POV handling. Existing rc17 external Generate profiles and workflows remain compatible.
- Synthetic regression tests plus private replay against the observed rc17 high-temperature missing-utterances/missing-speaker case; no private user data in release archive.

## v0.6.0rc17 — 2026-11-07

- **Live speaker-ID normalization:** Response Validator inserts missing `(Sx)` markers deterministically beside existing reference-backed `<Subject N>` mentions if the dialogue source is unique. Speaker indices follow vocal-event order, not Subject numbers. Existing correct markers and all user dialogue bytes remain unchanged.
- **Conservative fail-closed behavior:** no auto-correction when user-supplied dialogue is changed, a voice cannot be mapped to a Subject, or an existing speaker ID contradicts event ordering. Environment/POV viewer references never become vocal Subjects.
- **Materialization preserved:** the operation applies only to live Generate #2 text before first-time materialization; frozen Shot Editor text and manual edits remain authoritative. No new LLM, nodes, inputs, or workflow migration.
- Added rc17 regressions including the real rc16 dialogue failure replayed locally (private assets excluded from the public archive).


## v0.6.0rc16 — 2026-11-07

- **Fail-closed analysis JSON:** parse only a complete root object with `asset_analysis`, `subjects`, and `intent`; never salvage an interior object from truncated JSON. Validate both freshly captured and manually edited frozen snapshots, plus Analysis → Compose. Preserve support for JSON code fences and harmless leading/trailing prose.
- **Deterministic picture-source obligations:** normalized `reference_contract` now carries `required_picture_bindings` and `concrete_keyframe_pictures`. The text-only composer receives a concise checklist derived from connected accepted picture roles. Environment references remain valid Picture-only assets; converting a room into an H3 Subject is optional, not required.
- **Reference validation:** check that every tracked Subject cites its actual source Picture in `subject_definitions`; an environment with no Subject must be cited explicitly in `detailed_description`, and an environment Subject must be used there. Also verify active `target_perspective` / `end_keyframe` picture references.
- **Dialogue validation:** require a speaker ID for each canonical `<d>` event, verify consistent IDs for explicit Subject speaker markers, and preserve user-provided utterances verbatim/in order when `mode=preserve`.
- **Summary task type:** reject `keyframe completion` unless an accepted, connected `end_keyframe` reference exists; retain `video continuation` for Extend/Prepend/Bridge.
- **Diagnostics only, no silent H3 prompt mutation:** failed validation populates the existing optional repair-system and repair-prompt outputs, including the authoritative source bindings and user-supplied speech necessary to repair omissions; the Director does not run an LLM or rewrite materialized prompts.
- Expanded Request Builder reference-role tooltip to cover `target_perspective` and `end_keyframe`; retained node IDs, category, materialization behavior, six-section output grammar, backend-independent LLM integration, and OBVPM ownership boundaries.
- Added synthetic regression tests for the observed Vanilla D/E/F failures and regression replays of actual user-supplied outputs locally (not included in the public archive).
- No OBVPM Pro workflow, proprietary implementation, private scene data, model weights or assets included.

## v0.6.0rc15
- Added explicit reference roles `target_perspective` and `end_keyframe`.
- `target_perspective` guides the later/end portion of the shot toward a similar angle/framing/spatial relationship without forcing an exact terminal frame.
- `end_keyframe` remains a hard terminal picture anchor.
- Reference-role parsing accepts intuitive user labels such as `Picture 4: target perspective` or `Picture 4: end keyframe`.

# Changelog

## 0.6.0rc14 — 2026-11-07

- Reference-role prepass: Pass #1 first extracts the user's named subjects/locations from Direction, then visually matches connected Picture slots; uncertain matches stay unassigned. This is within the existing multimodal pass, not a third LLM pass.
- Optional `reference_roles` field in Request Builder for corrections: `Picture 1: Alex (character)`, `Picture 2: living room (location)`. Explicit per-picture user labels override inferred mappings. Existing rc13 workflow nodes remain compatible when the optional field is absent.
- Persist the accepted mappings and provenance in the frozen Analysis Snapshot Director Context, normalized `reference_contract.picture_roles`, the downstream Director Context, and Shot Analysis. Previous scene contracts carry safe names/roles through Extends, not temporal choreography.
- Compact, read-only Picture mapping status in Request Builder and Analysis → Compose: Auto / user-prompt match / user override / unresolved; changes to Direction or overrides invalidate the displayed status pending Re-analyze.
- Director Context and Analysis schemas v4; Shot State schema remains v1. No changes to LLM runtime, OBVPM timeline, freeze semantics, POV, or H3 six-section prompt structure.


## 0.6.0rc13 — 2026-11-06

- Add explicit **Reset Director Context** action on Analysis Snapshot and Shot Editor, plus an optional `H3DirectorContextReset` UI control node under `obvpm/director`.
- A single user-confirmed reset clears all frozen analysis/context and shot editor text fields across the *current workflow* and unlocks both lazy gates; it does not touch Request Builder inputs, references, models, OBVPM timelines, takes or sidecars.
- Keep `Re-analyze`, `Recompose`, automatic `timeline.next` unfreezing, schema, node IDs, and rc11 Prompt/POV/Continuity contracts unchanged. No auto-queue.
- Document `Save As` workflow-template hygiene and warning about pending jobs re-materializing stale results.

## 0.6.0rc12 — 2026-11-05

- Add `H3DirectorAnalysisSnapshot`: a materializable, lazy Pass #1 gate storing raw analysis and the matching Director Context. With analysis frozen, Generate #1 (and VRAM Handoff) is not requested when Generate #2 is recomposed.
- Add `Re-analyze (refresh Pass #1)` frontend action that unfreezes the snapshot and its connected Shot Editor(s); no auto-queueing.
- Rename displayed `H3DirectorShotState` to `H3 Director Shot Editor (obvpm)` without changing the internal node ID, widgets or shot-state schema. Add `Recompose (keep analysis)` action to unfreeze only the final H3 prompt.
- Reset both Analysis Snapshot and Shot Editor when authoritative OBVPM `timeline.next` changes; preserve both freeze states on ordinary reload.
- Leave VRAM Handoff's `IS_CHANGED` behavior, rc11 Prompt Policy, and Extend/Prepend/Bridge/POV logic unchanged.

## 0.6.0rc11 — 2026-11-02

- Keep rc10 POV viewpoint/framing semantics unchanged.
- Treat active `viewer` actions as first-person embodied actions: hands/forearms, breath and contact may enter the shot without creating a second fully visible figure.
- Add narrow Analyst/Composer guidance so viewer body-part actions do not become plural visual staging such as `two figures`, `both faces`, or `their faces`.
- Add a semantic Validator guard for explicit POV+viewer runs with one referenced person, while allowing explicit viewer reveals such as mirror/reflection or a deliberate POV break.

## 0.6.0rc10 — 2026-11-02

- Keep rc9 POV/reference-subject handling unchanged.
- Define POV as viewpoint semantics only, with no implicit shot scale or camera movement.
- Preserve inherited viewing distance/FOV for POV unless the user explicitly requests tighter framing/movement or physical action genuinely changes camera-to-subject distance.
- Prevent subject eye contact with the viewer/camera from being promoted automatically to a close-up.
- Do not infer zoom, push-in or dolly-in from POV alone; body/camera translation follows only explicit/current action or inherited seam motion.

## 0.6.0rc9 — 2026-11-02

- Add a narrow POV/reference-boundary fix without changing rc8 continuity behavior.
- Treat `viewer`/POV/camera-holder as camera or narrative semantics, not as an automatic H3 `<Subject N>`.
- Normalize Pass #1 subjects to reference-backed entries only and stamp a deterministic `reference_contract.allowed_subjects` for Pass #2.
- Permit an existing referenced Subject to own the POV while preventing a second viewpoint-only Subject from being invented.
- Validator now reports any `<Subject N>` that is not reference-backed for the current run.
- Keep rc8 stable-scene continuity, positive-forward prompting, and Shot State layout unchanged.

## 0.6.0rc8 — 2026-11-02

- Keep rc7 generalized Extend/Prepend/Bridge architecture and action-history sanitization.
- Replace the subject-only inherited contract with a stable scene contract: Subject/reference mappings plus structured environment/location facts extracted from prior analysis.
- Continue to exclude prior temporal intent/action/camera/dialogue prose from both LLM passes.
- Simplify continuity prompting back toward the rc4 positive-forward style: seam -> current direction -> new development, with substantially less defensive meta-language.
- Treat established location as persistent scene state; close-up/DOF changes may soften the background without replacing the location with a generic backdrop.
- Narrow creative freedom to details that are both unspecified and unestablished.
- Bump Director Context and Analysis schemas to v3; Shot State remains v1.
- Leave POV policy unchanged pending real-use evidence.

## 0.6.0rc7

- Fix Extend/Prepend/Bridge action replay regression by removing full endpoint H3 prompt, old analysis, and old direction from both LLM-facing continuity requests.
- Continuity LLMs now inherit only the deterministic stable Subject/reference contract; boundary frames remain physical seam truth.
- Added regression invariant: distinctive completed-action text from an endpoint must not appear in Pass #1 or Pass #2 requests.

## 0.6.0rc6 — 2026-11-01

- Correct rc5 continuity over-constraint: materialized endpoint prompts are authoritative for stable facts/Subject mapping, but their action choreography is completed history and must not be replayed.
- Restore the progressive Extend rule: match the START seam once, then immediately advance toward and beyond the user direction when duration permits.
- Treat transient seam state (pose, gaze, blocking, expression, movement, framing) as an initial condition that may evolve continuously rather than as attributes to preserve throughout the extension.
- Keep rc5 generalized Extend/Prepend/Bridge endpoint architecture and stable Subject contract unchanged.

## 0.6.0rc5 — 2026-11-01

Continuity completion pass before public release:

- Generalize OBVPM `pin_specs` interpretation from the former Extend-only special case to continuity endpoints: one `before` pin = Extend, one `after` pin = Prepend, one of each = Bridge.
- Keep OBVPM authoritative for pin execution; the Director only recovers endpoint visual/semantic context.
- Decode Director-only START and TARGET seam frames after the numbered H3 Picture references; never expose them as H3 reference labels.
- Recover materialized Shot State independently from both Bridge endpoints.
- Add a stable inherited Subject contract extracted from materialized `subject_definitions`, preserving Subject numbers and Picture mappings across continuity chains unless current authoritative input changes them.
- Make materialized endpoint H3 prompts authoritative over older endpoint analysis, so manual prompt edits survive into later Extend/Prepend/Bridge planning.
- Add operation-specific analysis/composition rules for Extend, Prepend and Bridge, including endpoint-compatible camera/framing evolution.
- Bump Director Context and Analysis interchange schemas to v2; Shot State remains schema v1.
- Rebalance Shot State multiline widgets to Direction 25% / H3 Prompt 50% / Analysis 25%.

## 0.6.0rc4 — 2026-11-01

Release-scope cleanup and public-contract freeze candidate:

- Remove the legacy all-in-one llama.cpp node/client architecture entirely.
- Remove the legacy Clip State / Restore State node and pre-v0.6 state-recovery fallbacks.
- Keep only the modular two-pass Director core plus materialized Shot State.
- Separate package/prompt-policy versioning from stable interchange schemas.
- Add schema v1 stamps for Director Context, Analysis, and materialized Shot State.
- Make malformed Pass #1 analysis JSON a hard, explicit failure; Pass #2 is text-only and no longer receives a fictitious image fallback.
- Adopt the newer Handbook dialogue-authority contract: concrete invented dialogue/monologue only when explicitly requested/authorized by the user; otherwise plan communicative behavior without quoted wording.
- Keep explicit user requests for invented/preserved speech mandatory through Pass #1, Pass #2 and validation.
- Generalize README/runtime wording from llama.cpp-specific inference to backend-agnostic external LLM Generate nodes.
- Keep Response Validator behavior unchanged for rc4: it reports failures and exposes optional repair prompts; it does not own inference.
- Keep tested materialization and reload behavior unchanged.

## 0.6.0rc3 — 2026-11-01

Prompt/validation hardening from Pro-Director testing:

- Add open-observation / strict-evidence rules for visual reference analysis.
- Explicitly forbid checklist completion and forced categorical choices for ambiguous or non-exclusive visual evidence.
- Separate image-local asset observations from stable subject identity facts.
- Do not infer communicative intent or semantic dialogue from visual appearance alone.
- Add structured `intent.speech_request` metadata (`none|preserve|invent`, required, language, intent, utterances).
- Treat explicit user requests to invent dialogue/monologue/speech as authoritative creative instructions.
- Require Pass #1 to plan concrete spoken wording when invented speech is explicitly requested.
- Require Pass #2 to emit actual canonical `<d>[Language] ...</d>` dialogue instead of merely describing the speech act.
- Validator now fails when analysis marks invented/preserved speech as required but the final H3 prompt contains no canonical dialogue content.
- Keep Response Validator primary outputs ordered `current_direction`, `h3_prompt`, `analysis_json` for straight Shot-State wiring.
- Document Generate #2 as text-only in the recommended modular wiring and note the 16k+ context recommendation from local KV-slot testing.
- Leave materialized Shot State / timeline reset behavior unchanged.

## 0.6.0rc2 — 2026-10-31

UI/integration cleanup for the Pro-Director workflow test:

- Move all Director nodes to `obvpm/director`.
- Remove version numbers from visible node names.
- Add `(obvpm)` to visible node names so Nodes 2.0 text search for `OBVPM` finds them.
- Reorder `H3 Director Response Validator` outputs to match Shot State live inputs:
  `current_direction`, `h3_prompt`, `analysis_json`.
- Reorder Shot State live inputs to the top in the same order.
- Keep `Analysis → Compose` passthrough outputs adjacent and ordered for the Validator.
- Preserve modular external llama.cpp inference and materialized Planned Clip behavior.

## 0.6.0rc1

- Split the former all-in-one llama.cpp Composer into Request Builder, external LLM passes,
  Analysis → Compose, Response Validator, optional VRAM Handoff, and materialized Shot State.
