import gc
import json
import re

import numpy as np
from .continuity import (
    boundary_frame_index,
    classify_pin_specs,
    decode_frame,
    extract_subject_contract,
    extract_scene_contract,
    recover_director_state,
    resolve_source_path,
)
from .prompt_skill import (
    SKILL_VERSION,
    ANALYST_SYSTEM,
    COMPOSER_SYSTEM,
    REPAIR_SYSTEM,
    analysis_user_prompt,
    composer_user_prompt,
    _delivery_speaker_subject,
)
from .validator import validate_h3_prompt, report
from .speaker_ids import normalize_speaker_ids, _named_subjects
from .dialogue_authority import authoritative_speech_request, enforce_user_dialogue
from .action_fidelity import explicit_pin_roles
from .reference_roles import (
    make_reference_brief, resolve_reference_roles, enrich_context, status_summary,
)
from .contracts import (
    DIRECTOR_CONTEXT_SCHEMA,
    DIRECTOR_CONTEXT_SCHEMA_VERSION,
    ANALYSIS_SCHEMA,
    ANALYSIS_SCHEMA_VERSION,
    SHOT_STATE_SCHEMA,
    SHOT_STATE_SCHEMA_VERSION,
)



def _strip_fence(text):
    s = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, flags=re.I | re.S)
    return m.group(1).strip() if m else s


def _extract_json_tolerant(text):
    """Decode only the OUTERMOST JSON object, never an inner valid fragment.

    Mild model-friendly tolerance: optional code fence or plain introductory /
    trailing prose is accepted. A truncated root, concatenated objects, or
    malformed root always raises rather than silently treating asset_analysis[0]
    or subjects[0] as the complete analysis.
    """
    s = _strip_fence(text)
    start = s.find("{")
    if start < 0:
        raise ValueError("Analysis JSON has no root object")
    before = s[:start].strip()
    if any(ch in before for ch in "{}[]"):
        raise ValueError("Invalid text before the analysis JSON root")
    try:
        obj, end = json.JSONDecoder().raw_decode(s, start)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Incomplete or malformed top-level analysis JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("Analysis JSON root must be an object")
    tail = s[end:].strip()
    if any(ch in tail for ch in "{}[]"):
        raise ValueError("Analysis JSON has trailing structured data; expected one complete object")
    return obj


def _assert_analysis_contract(obj):
    """Pass #1 always returns these root keys, even for an empty scene."""
    if not isinstance(obj, dict):
        raise ValueError("Analysis JSON root must be an object")
    for key, kind in (("asset_analysis", list), ("subjects", list), ("intent", dict)):
        if not isinstance(obj.get(key), kind):
            raise ValueError(f"Analysis JSON is missing the root '{key}' {kind.__name__}; "
                             "a nested object or truncated analysis cannot be composed")
    if "reference_strategy" in obj and not isinstance(obj["reference_strategy"], dict):
        raise ValueError("Analysis JSON root reference_strategy must be an object")
    return obj


def _required_picture_bindings(picture_roles, subjects, intent=None, direction=""):
    """Serialize source-image obligations using connected, accepted picture roles.

    Scene identities are retained, but close-up shots need not force a location
    reference into visible shot prose. Environment references may stay
    Picture-only; they must not become people merely to bind the image.
    """
    by_picture = {}
    for subject in subjects:
        try:
            sid = int(subject["subject"])
        except (KeyError, TypeError, ValueError):
            continue
        for picture in subject.get("source_pictures") or []:
            try:
                by_picture.setdefault(int(picture), []).append(sid)
            except (TypeError, ValueError):
                pass
    intent = intent if isinstance(intent, dict) else {}
    shot_scale = str(intent.get("shot_scale") or "").casefold().replace("-", "_").replace(" ", "_")
    tight_crop = shot_scale in {"close_up", "closeup", "tight_close_up", "extreme_close_up", "macro", "insert", "detail"}
    # Explicitly showing the location overrides the close-up default.
    force_location = bool(re.search(
        r"\b(?:show|include|reveal|establish|display)\b.{0,60}\b(?:room|location|environment|background)\b"
        r"|\b(?:room|location|environment|background)\b.{0,60}\b(?:visible|in frame|in shot)\b",
        direction or "", flags=re.I,
    ))
    # Scene knowledge is never dropped; this marks only the *shot-visible*
    # obligation. A close-up may use the established room for lighting without
    # explicitly citing a room image outside the visible frame.
    requirements = []
    for item in picture_roles:
        picture = int(item["picture"])
        role = str(item.get("role") or "unknown")
        subjects_for_picture = sorted(set(by_picture.get(picture, [])))
        if subjects_for_picture or role in {"environment", "target_perspective", "end_keyframe"}:
            binding = {"picture": picture, "role": role, "subjects": subjects_for_picture}
            if role == "environment" and tight_crop and not force_location:
                binding["required_in_shot"] = False
            requirements.append(binding)
    return requirements



def _cuda_memory_snapshot():
    """Best-effort CUDA memory snapshot for VRAM handoff diagnostics."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda_available": False}
        free_b, total_b = torch.cuda.mem_get_info()
        return {
            "cuda_available": True,
            "free_gib": round(free_b / (1024 ** 3), 3),
            "total_gib": round(total_b / (1024 ** 3), 3),
            "torch_allocated_gib": round(torch.cuda.memory_allocated() / (1024 ** 3), 3),
            "torch_reserved_gib": round(torch.cuda.memory_reserved() / (1024 ** 3), 3),
        }
    except Exception as exc:
        return {"cuda_available": None, "error": str(exc)}


def _free_comfy_vram_for_external_llm():
    """Evict ComfyUI-managed models before an external/local GPU LLM runtime wakes.

    An external LLM runtime runs outside ComfyUI's model manager, so its CUDA allocations cannot
    trigger ComfyUI's normal memory-pressure eviction.  This explicit handoff uses
    ComfyUI's own unload/cache APIs immediately before the first LLM request.
    """
    before = _cuda_memory_snapshot()
    try:
        import comfy.model_management as mm
        mm.unload_all_models()
        gc.collect()
        mm.soft_empty_cache()
        after = _cuda_memory_snapshot()
        result = {
            "requested": True,
            "performed": True,
            "before": before,
            "after": after,
        }
        print(
            "[H3 Prompt Composer] ComfyUI→LLM VRAM handoff: "
            f"free {before.get('free_gib', '?')} GiB -> {after.get('free_gib', '?')} GiB"
        )
        return result
    except Exception as exc:
        after = _cuda_memory_snapshot()
        result = {
            "requested": True,
            "performed": False,
            "before": before,
            "after": after,
            "error": str(exc),
        }
        print(f"[H3 Prompt Composer] WARNING: VRAM handoff failed: {exc}")
        return result



def _pil_to_comfy_tensor(image):
    """Convert a PIL image to one ComfyUI IMAGE tensor [1,H,W,C]."""
    import torch
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _context_load(raw):
    if isinstance(raw, dict):
        return raw
    try:
        obj = json.loads(str(raw or "{}"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


class H3DirectorRequestBuilder:
    """Build the Director analysis request without owning the LLM runtime."""
    CATEGORY = "obvpm/director"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING", "STRING", "STRING", "FLOAT")
    RETURN_NAMES = (
        "system",
        "prompt",
        "llm_images",
        "director_context",
        "current_direction",
        "continuity_info",
        "duration_seconds",
    )
    # llm_images is intentionally a real ComfyUI list so differently-sized
    # references can travel independently to multimodal LLM Generate nodes.
    OUTPUT_IS_LIST = (False, False, True, False, False, False, False)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "direction": ("STRING", {
                    "multiline": True,
                    "default": "the two talk about cars",
                    "tooltip": "Ordinary directing prose. The Director analysis pass derives reference roles, story semantics and H3 intent.",
                }),
                "duration_seconds": ("FLOAT", {
                    "default": 5.2, "min": 1.0, "max": 15.0, "step": 0.1,
                    "tooltip": "Requested H3 duration in seconds. Passed through as FLOAT output; OBVPM Timeline owns frame snapping and overlaps.",
                }),

            },
            "optional": {
                "reference_roles": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": (
                        "Optional picture role/identity corrections; blank = Auto. "
                        "One line per slot, e.g. 'Picture 1: Alex (character)', "
                        "'Picture 2: living room (location)', 'Picture 3: target perspective', "
                        "or 'Picture 4: end keyframe'. "
                        "The user direction is interpreted first; analysis resolves remaining roles visually."
                    ),
                }),
                "pin_specs": ("OBVPM_H3_PINSPECS", {
                    "tooltip": (
                        "Optional OBVPM H3 pin_specs. One before pin = Extend, one after pin = Prepend, "
                        "one before + one after = Bridge. OBVPM still owns execution; the Director only "
                        "uses the endpoints as continuity context."
                    ),
                }),
                "picture_1": ("IMAGE",),
                "picture_2": ("IMAGE",),
                "picture_3": ("IMAGE",),
                "picture_4": ("IMAGE",),
            },
        }

    @staticmethod
    def _load_endpoint(spec, role, llm_images, numbered_picture_count):
        """Decode one Director-only seam frame and recover its materialized state."""
        if spec is None:
            return None, None

        summary = {
            "role": role,
            "place": str(spec.get("place") or ""),
            "take_from": str(spec.get("take_from") or ""),
            "source_path": "",
            "requested_boundary_frame": None,
            "decoded_boundary_frame": None,
            "llm_image_position": None,
            "frame_found": False,
            "prompt_found": False,
            "analysis_found": False,
            "direction_found": False,
            "director_state_source": "",
            "subject_contract_found": False,
            "warnings": [],
        }
        state = {
            "role": role,
            "direction": "",
            "h3_prompt": "",
            "analysis": "",
            "subject_contract": [],
            "scene_contract": {},
        }

        source_path = None
        try:
            source_path = resolve_source_path(spec)
            summary["source_path"] = source_path
            wanted = boundary_frame_index(spec, role=role)
            summary["requested_boundary_frame"] = wanted
            frame, decoded = decode_frame(source_path, wanted)
            llm_images.append(_pil_to_comfy_tensor(frame))
            summary["decoded_boundary_frame"] = decoded
            summary["llm_image_position"] = len(llm_images)  # one-based human-facing position
            summary["frame_found"] = True
        except Exception as exc:
            summary["warnings"].append(f"{role} boundary frame unavailable: {exc}")

        if source_path:
            prior = recover_director_state(source_path)
            state["direction"] = prior.get("direction") or ""
            state["h3_prompt"] = prior.get("h3_prompt") or ""
            state["analysis"] = prior.get("analysis") or ""
            state["subject_contract"] = extract_subject_contract(state["h3_prompt"])
            state["scene_contract"] = extract_scene_contract(
                state["analysis"], state["subject_contract"]
            )
            summary["prompt_found"] = bool(state["h3_prompt"])
            summary["analysis_found"] = bool(state["analysis"])
            summary["direction_found"] = bool(state["direction"])
            summary["director_state_source"] = prior.get("source") or ""
            summary["subject_contract_found"] = bool(state["subject_contract"])
            if not state["h3_prompt"]:
                summary["warnings"].append(
                    f"materialized H3 prompt not found for {role} endpoint"
                )

        if summary["frame_found"]:
            ordinal = int(summary["llm_image_position"])
            if role == "start":
                summary["director_note"] = (
                    f"LLM image #{ordinal} (after {numbered_picture_count} numbered Picture reference(s)) "
                    "is the DIRECTOR-ONLY START continuity frame. It is physical truth for the inherited "
                    "visible seam state and is NOT an H3 <Picture N> reference."
                )
            else:
                summary["director_note"] = (
                    f"LLM image #{ordinal} (after {numbered_picture_count} numbered Picture reference(s)) "
                    "is the DIRECTOR-ONLY TARGET continuity frame. It is physical truth for the required "
                    "arrival state and is NOT an H3 <Picture N> reference."
                )
        else:
            summary["director_note"] = f"{role.capitalize()} continuity endpoint detected, but its boundary frame is unavailable."

        return summary, state

    def build(self, direction, duration_seconds, pin_specs=None,
              picture_1=None, picture_2=None, picture_3=None, picture_4=None,
              reference_roles=""):
        indexed = [(1, picture_1), (2, picture_2), (3, picture_3), (4, picture_4)]
        connected = [(slot, pic) for slot, pic in indexed if pic is not None]
        picture_slots = [slot for slot, _ in connected]
        llm_images = [pic for _, pic in connected]

        classified = classify_pin_specs(pin_specs)
        operation = str(classified.get("operation") or "new")
        continuity = {
            "prompt_policy_version": SKILL_VERSION,
            "operation": operation,
            "pin_count": int(classified.get("pin_count") or 0),
            "start_endpoint": None,
            "target_endpoint": None,
            "warnings": list(classified.get("warnings") or []),
        }

        start_summary, start_state = self._load_endpoint(
            classified.get("start_spec"), "start", llm_images, len(connected)
        )
        target_summary, target_state = self._load_endpoint(
            classified.get("target_spec"), "target", llm_images, len(connected)
        )
        continuity["start_endpoint"] = start_summary
        continuity["target_endpoint"] = target_summary
        for endpoint in (start_summary, target_summary):
            if endpoint:
                continuity["warnings"].extend(endpoint.get("warnings") or [])

        # Internal continuity state retains the materialized endpoint data for provenance.
        # prompt_skill sanitizes the LLM-facing view so temporal prompt/analysis prose
        # cannot leak into continuation choreography.
        continuity_states = {
            "start": start_state or {},
            "target": target_state or {},
        }
        continuity_note_parts = []
        if start_summary:
            continuity_note_parts.append(start_summary.get("director_note") or "")
        if target_summary:
            continuity_note_parts.append(target_summary.get("director_note") or "")
        continuity_note = "\n".join(x for x in continuity_note_parts if x)

        direction = str(direction or "").strip()
        requested_duration = float(duration_seconds)
        reference_brief = make_reference_brief(direction, reference_roles, picture_slots)
        analysis_prompt = analysis_user_prompt(
            direction,
            requested_duration,
            picture_slots,
            operation=operation,
            continuity_context=continuity_states,
            continuity_note=continuity_note,
            reference_brief=reference_brief,
        )

        context = {
            "schema": DIRECTOR_CONTEXT_SCHEMA,
            "schema_version": DIRECTOR_CONTEXT_SCHEMA_VERSION,
            "prompt_policy_version": SKILL_VERSION,
            "direction": direction,
            "authoritative_dialogue": authoritative_speech_request(direction),
            "duration_seconds": requested_duration,
            "picture_slots": picture_slots,
            "reference_roles": reference_brief,
            "operation": operation,
            "continuity_states": continuity_states,
            "continuity_note": continuity_note,
            "continuity": continuity,
        }
        context_json = json.dumps(context, ensure_ascii=False, indent=2)
        continuity_info = json.dumps(continuity, ensure_ascii=False, indent=2)
        return (
            ANALYST_SYSTEM,
            analysis_prompt,
            llm_images,
            context_json,
            direction,
            continuity_info,
            requested_duration,
        )


class H3DirectorVRAMHandoff:
    """Optional visible ComfyUI -> external/local LLM VRAM handoff barrier."""
    CATEGORY = "obvpm/director"
    FUNCTION = "handoff"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("system", "prompt", "diagnostics")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "system": ("STRING", {"forceInput": True}),
                "prompt": ("STRING", {"forceInput": True}),
                "enabled": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Unload ComfyUI-managed models and clear PyTorch CUDA cache immediately before the external/local LLM branch.",
                }),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def handoff(self, system, prompt, enabled=True):
        if bool(enabled):
            info = _free_comfy_vram_for_external_llm()
        else:
            info = {
                "requested": False,
                "performed": False,
                "before": _cuda_memory_snapshot(),
                "after": _cuda_memory_snapshot(),
            }
        return (str(system or ""), str(prompt or ""), json.dumps(info, ensure_ascii=False, indent=2))


class H3DirectorAnalysisSnapshot:
    """Persist Pass #1 and its exact Director context independently of Pass #2.

    Both upstream inputs are LAZY. Once materialized, neither Request Builder,
    VRAM Handoff nor LLM #1 is requested through this node. Re-composition still
    works because the downstream Analysis -> Compose node receives the frozen
    response and the frozen context as ordinary STRING outputs.

    Unlike a second OUTPUT_NODE, this node runs only if a downstream consumer
    actually requests it. That preserves the existing Shot Editor freeze barrier.
    """
    CATEGORY = "obvpm/director"
    FUNCTION = "snapshot"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("raw_analysis", "director_context", "snapshot_status")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "raw_analysis": ("STRING", {"forceInput": True, "multiline": True, "lazy": True}),
                "director_context": ("STRING", {"forceInput": True, "multiline": True, "lazy": True}),
                "materialized": ("BOOLEAN", {
                    "default": False,
                    "tooltip": (
                        "ON: reuse the saved Pass #1 analysis AND matching Director context; "
                        "Generate #1 / VRAM Handoff stay asleep. OFF: capture a fresh Pass #1."
                    ),
                }),
                "snapshot_raw_analysis": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": "Persistent raw vision/semantic response from Generate #1. Editable after freeze.",
                }),
                "snapshot_director_context": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": (
                        "Persistent matching Director Context. Preserved alongside the analysis "
                        "so Pass #2 re-composes the same shot, even when upstream settings change."
                    ),
                }),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Re-evaluate the lazy gate when toggled or edited; an unfrozen upstream
        # change cannot be mistaken for a still-valid frozen snapshot.
        return float("nan")

    @classmethod
    def check_lazy_status(cls, materialized=False, raw_analysis=None,
                          director_context=None, **kwargs):
        if bool(materialized):
            return []
        needed = []
        if raw_analysis is None:
            needed.append("raw_analysis")
        if director_context is None:
            needed.append("director_context")
        return needed

    def snapshot(self, materialized=False, snapshot_raw_analysis="",
                 snapshot_director_context="", raw_analysis=None,
                 director_context=None):
        if bool(materialized):
            analysis = str(snapshot_raw_analysis or "")
            context = str(snapshot_director_context or "")
            if not analysis.strip() or not context.strip():
                raise ValueError(
                    "Analysis Snapshot is frozen but has empty stored analysis/context. "
                    "Turn materialized OFF and execute once to capture Pass #1."
                )
            # Users can edit the stored text. Validate it again at the lazy gate
            # so a malformed frozen snapshot cannot silently poison Pass #2.
            try:
                _assert_analysis_contract(_extract_json_tolerant(analysis))
            except Exception as exc:
                raise ValueError(f"Frozen Analysis Snapshot contains invalid JSON: {exc}") from exc
            return (analysis, context, "FROZEN — Pass #1 bypassed")

        analysis = str(raw_analysis or "").strip()
        context = str(director_context or "").strip()
        if not analysis or not context:
            raise ValueError(
                "Analysis Snapshot requires both Generate #1.response and "
                "Request Builder.director_context when materialized is OFF."
            )
        # Parse immediately, before snapshot capture: never freeze malformed
        # Pass #1 text that would necessarily fail in Analysis -> Compose.
        try:
            parsed = _assert_analysis_contract(_extract_json_tolerant(analysis))
        except Exception as exc:
            raise ValueError(
                "Analysis Snapshot did not materialize because Pass #1 JSON "
                f"is invalid: {exc}"
            ) from exc
        if not _context_load(context):
            raise ValueError("Analysis Snapshot did not materialize: invalid Director Context JSON.")
        context = enrich_context(json.dumps(parsed, ensure_ascii=False), context)

        payload = {
            "materialized": True,
            "snapshot_raw_analysis": analysis,
            "snapshot_director_context": context,
        }
        print(
            "[H3 Director Analysis Snapshot] captured Pass #1: "
            f"analysis={len(analysis)} chars, context={len(context)} chars"
        )
        return {
            "ui": {"director_analysis_snapshot": [json.dumps(payload, ensure_ascii=False)]},
            "result": (analysis, context, "CAPTURED — awaiting UI materialization"),
        }


class H3DirectorContextReset:
    """Optional frontend-only project-template reset control.

    The button in web/director_state.js clears Director materialized widgets in
    the currently open workflow. Backend execution is intentionally a no-op;
    no input connections, generation dependencies, or OBVPM timeline mutation.
    The same action is available directly on Analysis Snapshot / Shot Editor.
    """
    CATEGORY = "obvpm/director"
    FUNCTION = "noop"
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    def noop(self):
        return ()


class H3DirectorAnalysisCompose:
    """Normalize the analysis response and build the final H3 composition request."""
    CATEGORY = "obvpm/director"
    FUNCTION = "compose_request"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = (
        "system",
        "prompt",
        "analysis_json",
        "director_context",
        "analysis_status",
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "raw_analysis": ("STRING", {"forceInput": True, "multiline": True}),
                "director_context": ("STRING", {"forceInput": True, "multiline": True}),
            }
        }

    def compose_request(self, raw_analysis, director_context):
        ctx = _context_load(director_context)
        ctx["authoritative_dialogue"] = authoritative_speech_request(str(ctx.get("direction", "")))
        picture_slots = list(ctx.get("picture_slots") or [])
        status = "PASS"
        try:
            analysis_obj = _assert_analysis_contract(_extract_json_tolerant(raw_analysis))
        except Exception as exc:
            raise ValueError(
                "H3 Director Pass #1 returned malformed analysis JSON. "
                "Pass #2 is text-only and will not run from a fabricated fallback analysis. "
                "Fix/retry the external analysis LLM response. "
                f"Parser error: {exc}"
            ) from exc

        # The external LLM owns the analysis contents; the Director owns the
        # interchange contract and stamps it deterministically.
        analysis_obj["schema"] = ANALYSIS_SCHEMA
        analysis_obj["schema_version"] = ANALYSIS_SCHEMA_VERSION

        # The user's quoted lines are immutable current-interval input, not
        # discretionary Analyst output.  Recover them even if Pass #1 returned
        # mode=preserve with an empty or paraphrased utterances array.
        enforce_user_dialogue(analysis_obj, str(ctx.get("direction", "")))

        # Deterministic H3 reference boundary: <Subject N> is a reference label,
        # not a generic character/viewpoint ID. Keep only Subjects that are
        # actually backed by currently connected numbered Picture references.
        available_picture_set = {int(x) for x in picture_slots}
        allowed_subject_map = {}
        sanitized_subjects = []
        for item in analysis_obj.get("subjects") or []:
            if not isinstance(item, dict):
                continue
            try:
                subject_no = int(item.get("subject"))
            except Exception:
                continue
            source_pictures = []
            for value in item.get("source_pictures") or []:
                try:
                    pic_no = int(value)
                except Exception:
                    continue
                if pic_no in available_picture_set:
                    source_pictures.append(pic_no)
            if not source_pictures:
                continue
            clean = dict(item)
            clean["source_pictures"] = sorted(set(source_pictures))
            sanitized_subjects.append(clean)
            allowed_subject_map.setdefault(subject_no, set()).update(source_pictures)
        analysis_obj["subjects"] = sanitized_subjects

        operation = str(ctx.get("operation", "new")).casefold()
        continuity_states = ctx.get("continuity_states") or {}
        if operation in {"extend", "prepend", "bridge"}:
            start_state = continuity_states.get("start") or {}
            target_state = continuity_states.get("target") or {}
            # Deterministic contract carried into text-only Pass #2.  This is not
            # delegated to Pass #1: endpoint Subject mappings come from the
            # materialized user-authoritative H3 prompts themselves.
            analysis_obj["continuity_contract"] = {
                "operation": operation,
                "contract_mode": "stable_scene_facts_only",
                "current_picture_slots": picture_slots,
                "start_scene": start_state.get("scene_contract") or {
                    "subjects": start_state.get("subject_contract") or [],
                    "environment_references": [],
                    "environment_subjects": [],
                },
                "target_scene": target_state.get("scene_contract") or {
                    "subjects": target_state.get("subject_contract") or [],
                    "environment_references": [],
                    "environment_subjects": [],
                },
            }

            # Existing inherited Subject mappings remain eligible when their
            # referenced Picture slots are still connected for this run.
            for role_key in ("start_scene", "target_scene"):
                scene = analysis_obj["continuity_contract"].get(role_key) or {}
                for item in scene.get("subjects") or []:
                    if not isinstance(item, dict):
                        continue
                    try:
                        subject_no = int(item.get("subject"))
                    except Exception:
                        continue
                    for value in item.get("source_pictures") or []:
                        try:
                            pic_no = int(value)
                        except Exception:
                            continue
                        if pic_no in available_picture_set:
                            allowed_subject_map.setdefault(subject_no, set()).add(pic_no)

        picture_roles = resolve_reference_roles(analysis_obj, ctx)
        ctx["reference_roles_resolved"] = picture_roles

        analysis_obj["reference_contract"] = {
            "picture_roles": picture_roles,
            "allowed_subjects": [
                {"subject": n, "source_pictures": sorted(pics)}
                for n, pics in sorted(allowed_subject_map.items())
                if pics
            ],
            "required_picture_bindings": _required_picture_bindings(
                picture_roles,
                [{"subject": n, "source_pictures": sorted(pics)}
                 for n, pics in sorted(allowed_subject_map.items()) if pics],
                intent=analysis_obj.get("intent") or {},
                direction=str(ctx.get("direction") or ""),
            ),
            "concrete_keyframe_pictures": [
                int(item["picture"]) for item in picture_roles
                if item.get("role") == "end_keyframe"
            ],
            "rule": "POV/viewer/camera-holder semantics do not create a Subject; only reference-backed Subject labels are allowed.",
        }

        # Only extract very specific, user-owned physical-role assertions.
        # Every other movement detail remains the composer's creative freedom.
        analysis_obj["action_contract"] = explicit_pin_roles(
            str(ctx.get("direction") or ""), _named_subjects(analysis_obj)
        )
        analysis_json = json.dumps(analysis_obj, ensure_ascii=False, indent=2)
        # The accepted picture assignments are part of the outgoing Director
        # Context, materialized analysis, and downstream OBVPM Shot State.
        stamped_context = json.dumps(ctx, ensure_ascii=False, indent=2)
        prompt = composer_user_prompt(
            str(ctx.get("direction", "")),
            float(ctx.get("duration_seconds", 5.2)),
            picture_slots,
            analysis_json,
            operation=str(ctx.get("operation", "new")),
            continuity_context=ctx.get("continuity_states") or {},
            continuity_note=str(ctx.get("continuity_note", "")),
        )
        # Small, non-serialized frontend status (also reflected on the Request Builder).
        return {
            "ui": {"director_reference_status": [json.dumps({
                "summary": status_summary(picture_roles),
                "roles": picture_roles,
            }, ensure_ascii=False)]},
            "result": (COMPOSER_SYSTEM, prompt, analysis_json, stamped_context, status),
        }


class H3DirectorResponseValidator:
    """Validate the external LLM response and expose optional repair instructions."""
    CATEGORY = "obvpm/director"
    FUNCTION = "validate"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    # First three intentionally mirror H3DirectorShotState's live input order.
    RETURN_NAMES = (
        "current_direction",
        "h3_prompt",
        "analysis_json",
        "validation",
        "continuity_info",
        "repair_system",
        "repair_prompt",
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "raw_response": ("STRING", {"forceInput": True, "multiline": True}),
                "analysis_json": ("STRING", {"forceInput": True, "multiline": True}),
                "director_context": ("STRING", {"forceInput": True, "multiline": True}),
            }
        }

    def validate(self, raw_response, analysis_json, director_context):
        ctx = _context_load(director_context)
        prompt = str(raw_response or "").strip()
        picture_slots = list(ctx.get("picture_slots") or [])
        try:
            analysis_for_refs = _assert_analysis_contract(_extract_json_tolerant(analysis_json))
        except Exception as exc:
            raise ValueError(f"Response Validator requires a complete Director Analysis: {exc}") from exc
        # Re-assert the user-owned dialogue from Director Context at validation
        # time as well. A manually altered/stale analysis cannot weaken the
        # verbatim requirement or permit an incorrect speaker normalization.
        current_direction = str(ctx.get("direction") or "")
        incoming_speech = (analysis_for_refs.get("intent") or {}).get("speech_request")
        effective_speech = enforce_user_dialogue(analysis_for_refs, current_direction)
        # As with user dialogue, the physical actor/target roles originate in
        # the frozen user Direction, NOT in editable/generated Analysis fields.
        # A stale/manual analysis cannot silently change the user's assignment.
        incoming_actions = analysis_for_refs.get("action_contract")
        effective_actions = explicit_pin_roles(current_direction, _named_subjects(analysis_for_refs))
        if incoming_actions is not None or effective_actions:
            analysis_for_refs["action_contract"] = effective_actions
        # Preserve the original analysis string when no override was needed.
        # Corrected contracts go to the live Shot Editor; materialized user edits
        # remain independently frozen until explicitly recomposed.
        action_contract_changed = (
            (incoming_actions is not None or bool(effective_actions))
            and incoming_actions != effective_actions
        )
        forwarded_analysis_json = (
            json.dumps(analysis_for_refs, ensure_ascii=False, indent=2)
            if incoming_speech != effective_speech or action_contract_changed
            else str(analysis_json or "")
        )
        # Live output only: repair missing *unambiguous* vocal source markers
        # before validation and first-time materialization. Frozen Shot Editor
        # text is returned via its independent lazy gate, never through here.
        prompt, speaker_ids_added = normalize_speaker_ids(prompt, analysis_for_refs)
        allowed_subjects = {
            int(item.get("subject"))
            for item in ((analysis_for_refs.get("reference_contract") or {}).get("allowed_subjects") or [])
            if isinstance(item, dict) and str(item.get("subject", "")).isdigit()
        }
        current_direction = str(ctx.get("direction", "") or "")
        pov_viewer_mode = bool(re.search(r"\bpov\b", current_direction, flags=re.I) and re.search(r"\bviewer\b", current_direction, flags=re.I))
        # The viewer stays first-person/partial by default. Only explicit reveal language
        # disables the plural-visibility guard; ordinary viewer hands/arms do not.
        viewer_full_visibility = bool(re.search(
            r"\bviewer\b.{0,80}\b(?:fully visible|appears in (?:the )?frame|enters (?:the )?frame|face visible|body visible|seen in (?:a )?(?:mirror|reflection)|mirror|reflection|third[- ]person)\b",
            current_direction,
            flags=re.I | re.S,
        ))
        visible_person_subject_count = None
        try:
            visible_person_subject_count = sum(
                1 for item in (analysis_for_refs.get("subjects") or [])
                if isinstance(item, dict) and str(item.get("kind", "")).casefold() == "person"
            )
        except Exception:
            pass

        # The live rc22 delivery resolver already knows unique descriptive
        # speakers (e.g. "the younger man"). Supply the same grounded names to
        # the existing Validator's attribution check; never guess ambiguous
        # or unreferenced subjects. The Validator itself remains unchanged.
        speaker_subject_map = _named_subjects(analysis_for_refs)
        if isinstance(effective_speech, dict):
            for entry in effective_speech.get("utterances") or []:
                if isinstance(entry, dict):
                    speaker = str(entry.get("speaker") or entry.get("name") or "").strip()
                else:
                    value = str(entry or "")
                    speaker = value.split(":", 1)[0].strip() if ":" in value else ""
                if speaker and speaker.casefold() not in speaker_subject_map:
                    grounded = _delivery_speaker_subject(speaker, analysis_for_refs)
                    if grounded is not None:
                        speaker_subject_map[speaker.casefold()] = grounded

        problems = validate_h3_prompt(
            prompt,
            picture_slots,
            allowed_subjects=allowed_subjects,
            pov_viewer_mode=pov_viewer_mode,
            visible_person_subject_count=visible_person_subject_count,
            viewer_full_visibility=viewer_full_visibility,
            required_picture_bindings=(analysis_for_refs.get("reference_contract") or {}).get("required_picture_bindings"),
            picture_roles=(analysis_for_refs.get("reference_contract") or {}).get("picture_roles"),
            expected_speech=(analysis_for_refs.get("intent") or {}).get("speech_request"),
            speaker_subject_map=speaker_subject_map,
            operation=ctx.get("operation", "new"),
            required_actions=effective_actions,
        )

        validation = report(problems)
        if speaker_ids_added:
            validation += (f"\nAUTO-NORMALIZED — inserted {speaker_ids_added} "
                           "unambiguously grounded speaker marker(s); dialogue unchanged.")

        continuity = ctx.get("continuity") or {}
        notices = []
        operation = str(ctx.get("operation", "new")).casefold()
        if operation in {"extend", "prepend", "bridge"}:
            notices.append(f"{operation.upper()} CONTINUITY MODE")
            start_ep = continuity.get("start_endpoint") or {}
            target_ep = continuity.get("target_endpoint") or {}
            if operation in {"extend", "bridge"}:
                if not start_ep.get("frame_found"):
                    notices.append("WARNING — START BOUNDARY FRAME UNAVAILABLE")
                if not start_ep.get("prompt_found"):
                    notices.append("WARNING — START MATERIALIZED H3 PROMPT UNAVAILABLE")
                if not start_ep.get("analysis_found"):
                    notices.append("NOTICE — START DIRECTOR ANALYSIS UNAVAILABLE")
            if operation in {"prepend", "bridge"}:
                if not target_ep.get("frame_found"):
                    notices.append("WARNING — TARGET BOUNDARY FRAME UNAVAILABLE")
                if not target_ep.get("prompt_found"):
                    notices.append("WARNING — TARGET MATERIALIZED H3 PROMPT UNAVAILABLE")
                if not target_ep.get("analysis_found"):
                    notices.append("NOTICE — TARGET DIRECTOR ANALYSIS UNAVAILABLE")
        if notices:
            validation = "\n".join(notices) + "\n" + validation

        if problems:
            # The repair model otherwise sees only the failed output, which may
            # have omitted an entire requested utterance or source reference.
            # Supply only the current authoritative requirements; never send
            # the previous temporal analysis/endpoint history back into a pass.
            repair_authority = {
                "required_picture_bindings": (analysis_for_refs.get("reference_contract") or {}).get("required_picture_bindings") or [],
                "concrete_keyframe_pictures": (analysis_for_refs.get("reference_contract") or {}).get("concrete_keyframe_pictures") or [],
                "speech_request": (analysis_for_refs.get("intent") or {}).get("speech_request") or {},
                "operation": operation,
                "action_contract": analysis_for_refs.get("action_contract") or [],
            }
            repair_prompt = (
                "VALIDATION ERRORS:\n- " + "\n- ".join(problems)
                + "\n\nAUTHORITATIVE OUTPUT REQUIREMENTS:\n"
                + json.dumps(repair_authority, ensure_ascii=False, indent=2)
                + "\n\nPROMPT TO REPAIR:\n" + prompt
            )
            repair_system = REPAIR_SYSTEM
        else:
            repair_system = ""
            repair_prompt = ""

        continuity_info = json.dumps(continuity, ensure_ascii=False, indent=2)
        return (
            str(ctx.get("direction", "")).strip(),
            prompt,
            forwarded_analysis_json,
            validation,
            continuity_info,
            repair_system,
            repair_prompt,
        )



class H3DirectorShotState:
    """Materialized Director shot state for OBVPM Planned Clips.

    The Composer inputs are deliberately lazy. While ``materialized`` is false,
    this node requests the live Composer outputs, returns them, and asks the web
    extension to copy them into the persistent shot_* widgets and flip
    ``materialized`` to true. Once materialized is true, the Composer branch is
    not evaluated at all: the node returns only the stored widget values.

    Put this node inside an OBVPM group whose title contains [restore]. Wire its
    h3_prompt output to the H3 prompt input. This makes the materialized prompt
    part of the actual generation dependency graph and therefore eligible for an
    OBVPM Planned Clip snapshot.
    """
    CATEGORY = "obvpm/director"
    FUNCTION = "store"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("h3_prompt", "direction", "analysis_json")
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "current_direction": ("STRING", {"forceInput": True, "lazy": True}),
                "current_h3_prompt": ("STRING", {"forceInput": True, "lazy": True}),
                "current_analysis": ("STRING", {"forceInput": True, "lazy": True}),
                "materialized": ("BOOLEAN", {
                    "default": False,
                    "tooltip": (
                        "OFF: capture the connected Director outputs on this run. "
                        "After a successful capture the UI flips this ON automatically. "
                        "ON: output the frozen shot_* values without executing the Director/LLM branch."
                    ),
                }),
                "shot_direction": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Frozen direction for THIS planned/generated shot.",
                }),
                "shot_h3_prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Frozen exact H3 prompt for THIS planned/generated shot.",
                }),
                "shot_analysis": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Frozen Director analysis JSON for THIS planned/generated shot.",
                }),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    @classmethod
    def check_lazy_status(cls, materialized=False, current_direction=None,
                          current_h3_prompt=None, current_analysis=None, **kwargs):
        # This is the crucial execution barrier. A restored Planned Clip stores
        # materialized=True, so none of the connected Composer outputs are
        # requested and the external LLM branch stays asleep.
        if bool(materialized):
            return []
        needed = []
        if current_direction is None:
            needed.append("current_direction")
        if current_h3_prompt is None:
            needed.append("current_h3_prompt")
        if current_analysis is None:
            needed.append("current_analysis")
        return needed

    def store(self, materialized=False, shot_direction="", shot_h3_prompt="",
              shot_analysis="", current_direction=None, current_h3_prompt=None,
              current_analysis=None):
        if bool(materialized):
            direction = str(shot_direction or "")
            prompt = str(shot_h3_prompt or "")
            analysis = str(shot_analysis or "")
            return (prompt, direction, analysis)

        # Capture mode: check_lazy_status has requested the three live values.
        direction = str(current_direction or "")
        prompt = str(current_h3_prompt or "")
        analysis = str(current_analysis or "")
        payload = {
            "schema": SHOT_STATE_SCHEMA,
            "schema_version": SHOT_STATE_SCHEMA_VERSION,
            "materialized": True,
            "shot_direction": direction,
            "shot_h3_prompt": prompt,
            "shot_analysis": analysis,
        }
        print(
            "[H3 Director Shot State] materialized Composer result: "
            f"direction={len(direction)} chars, prompt={len(prompt)} chars, analysis={len(analysis)} chars"
        )
        return {
            "ui": {"director_shot_state": [json.dumps(payload, ensure_ascii=False)]},
            "result": (prompt, direction, analysis),
        }


print(f"[H3 Prompt Composer] prompt skill loaded: {SKILL_VERSION}")


NODE_CLASS_MAPPINGS = {
    "H3DirectorRequestBuilder": H3DirectorRequestBuilder,
    "H3DirectorVRAMHandoff": H3DirectorVRAMHandoff,
    "H3DirectorAnalysisSnapshot": H3DirectorAnalysisSnapshot,
    "H3DirectorContextReset": H3DirectorContextReset,
    "H3DirectorAnalysisCompose": H3DirectorAnalysisCompose,
    "H3DirectorResponseValidator": H3DirectorResponseValidator,
    "H3DirectorShotState": H3DirectorShotState,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3DirectorRequestBuilder": "H3 Director Request Builder (obvpm)",
    "H3DirectorVRAMHandoff": "H3 Director VRAM Handoff (obvpm)",
    "H3DirectorAnalysisSnapshot": "H3 Director Analysis Snapshot (obvpm)",
    "H3DirectorContextReset": "H3 Director Reset Context (obvpm)",
    "H3DirectorAnalysisCompose": "H3 Director Analysis → Compose (obvpm)",
    "H3DirectorResponseValidator": "H3 Director Response Validator (obvpm)",
    "H3DirectorShotState": "H3 Director Shot Editor (obvpm)",
}
