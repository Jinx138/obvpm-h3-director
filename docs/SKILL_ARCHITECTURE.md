# v0.6.6 skill architecture — Creative Freedom & Composer Fidelity

The release is based on the locally tested v0.6.6-dev.2 build. The following measurements compare its prompt texts with v0.6.6-dev.1-cleanup; release metadata changes do not alter the measured instruction texts.

## Design

The universal contract defines **what is binding**, while selected Flavours define the creative competencies used to realize the shot. Explicit user intent, current reference evidence, authoritative dialogue, applicable physical seams and the output formats remain binding. Within these constraints, the Analyst has creative ownership of staging, performance, rhythm, atmosphere and sensory detail. An open request permits a fitting creative scene; an observational request can remain observational. The Composer transports the richness of that analysis into H3 rather than independently redirecting the scene.

The previous assembled prompt sizes are a soft context-budget ceiling, not a length target. Positive instructions take priority. Negative instructions are retained when they protect concrete technical or explicit user constraints. The selected style is a specialization, not a prohibition on techniques associated with other styles.

## Scope and compatibility

- Reworked universal Analyst/Composer instructions, selected genre/style skills, performance settings and operation-specific continuity prose. Existing intimate-style and tone modules are intentionally unchanged in this build.
- Shortened request templates to current data and a concise task; moved operation rules to the corresponding continuity system skill. The assembler remains 54 lines. No change to node I/O, example wiring or model profiles.
- Analysis JSON root keys, nested keys, example types and enum strings are unchanged. Only descriptive field guidance was changed, including explicit permission for inapplicable dramatic or interpersonal fields to be empty/unspecified.
- Dialogue composer skill, dynamic dialogue delivery messages (including the duplicated current-shot system/user contract), speaker resolver, dialogue authority, normalizer, validator, reference reconciliation and optional repair prompt are unchanged. Analyst dialogue wording is compacted and explicitly covers unreferenced/offscreen speakers, narrators and commentators. No additional inference pass.
- The full normalized analysis JSON is still passed to the Composer; no truncation, field filtering or semantic transformation was added.
- The skill-pack version and workspace metadata were advanced to v0.6.6. Manifest checks intentionally require fresh analysis for a new composition. Approved stored prompts remain stored until refreshed by the user.
- Backend-agnostic Core compatibility (GitHub issue #2) remains separate.

## Migration review

See [SKILL_MIGRATION_DEV2.md](../SKILL_MIGRATION_DEV2.md) for the detailed review of removed, consolidated and relocated rules. This documents the change in creative scope as well as what is technically preserved.

## Measured prompt size

Actual selected base-system strings from the existing loader, compared with dev.1-cleanup. All 4 genres × 6 styles × 3 performance settings × 4 tones × 4 operations = 1,152 profile/operation combinations per pass; no custom flavour notes. Counts are whitespace-separated words, not model tokenizer usage. The optional dynamic Composer dialogue system block is unchanged and excluded from this table.

| Pass | Old mean | New mean | Change | Old range | New range |
| --- | ---: | ---: | ---: | ---: | ---: |
| Analyst | 1675.5 | 936.1 | -44.1% | 1508–1837 | 792–1097 |
| Composer | 1472.8 | 840.1 | -43.0% | 1288–1616 | 700–997 |

Every measured base-system combination was smaller than its predecessor. Across the same combinations, the mean number of literal phrases matching `do not`, `never`, `must not` or `avoid` decreased from 18.2 to 0.3 in the Analyst and from 19.3 to 2.2 in the Composer. These are descriptive metrics, not guarantees of freedom or compliance.

Representative user-prompt rendering (four alternating speaker events, same direction, duration and analysis; no actual endpoint frame metadata):

| Operation | Analyst before → after | Composer before → after |
| --- | ---: | ---: |
| New | 207 → 67 | 370 → 320 |
| Extend | 203 → 110 | 399 → 352 |
| Prepend | 192 → 99 | 394 → 347 |
| Bridge | 191 → 98 | 393 → 346 |

For all four Composer request fixtures, the embedded analysis JSON and required output bindings were preserved exactly. These counts do not estimate the variable size of a future live Analyst response.

## Verification

- 227 Python tests executed: 226 passed, 1 skipped; 13 frontend test scripts passed. The four added tests exercise all 2,304 stage/profile/operation selections, schema shape, raw analysis and stable speech contract delivery across all styles, and operation-specific prefixes. They do not measure actual LLM performance.
- Compared schema keys/types/enum strings directly with the dev.1 baseline.
- Compared all 2,304 selected base-system strings and the eight user request fixtures described above.
- No live LLM inference or real ComfyUI/OBVPM reload was run in the automated test environment. Initial local user tests of dev.2 reported two Validator PASS results and richer camera instructions, micro-motion and creative direction. Creative diversity, unwanted invented actions, detail fidelity and actual token consumption need live evaluation. A more open Analyst can produce more detailed or longer analysis; the fixed model context limit still applies.

## Upgrade and further live verification

Install in the unchanged `h3-prompt-composer` folder (backup outside `custom_nodes`), restart ComfyUI and hard-refresh the browser. Run **Re-analyze → DIRECT** once to refresh the old skill manifest. Start with the same four-event dialogue and model/seed settings as before. Compare Gen #1's direction and performance tracks to Gen #2's detailed_description, and inspect speaker IDs and validator status. Then try an open shot and a nonhuman/action shot with voice commentary. Use Recompose for subsequent model comparisons within the new build.
