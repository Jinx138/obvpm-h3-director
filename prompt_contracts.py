"""Render deterministic scene facts and output contracts using external templates."""
import json
import re
from .flavour_skills import render_message
from .speaker_resolution import _delivery_speaker_subject

def _continuity_contract_text(continuity_context, picture_slots=None) -> str:
    """Return stable non-temporal scene facts for continuity prompting."""
    ctx = continuity_context if isinstance(continuity_context, dict) else {}
    available = {int(x) for x in (picture_slots or [])}
    blocks = []
    for role in ("start", "target"):
        ep = ctx.get(role) or {}
        if not ep:
            continue
        label = role.upper()
        scene = ep.get("scene_contract") or {
            "subjects": ep.get("subject_contract") or [],
            "environment_references": [],
            "environment_subjects": [],
        }

        subjects = []
        for item in scene.get("subjects") or []:
            if not isinstance(item, dict):
                continue
            pics = []
            for x in item.get("source_pictures") or []:
                try:
                    pics.append(int(x))
                except Exception:
                    pass
            clean = dict(item)
            clean["source_pictures"] = [x for x in pics if not available or x in available]
            if pics and available and any(x not in available for x in pics):
                clean.pop("definition", None)
            subjects.append(clean)

        env_refs = []
        for item in scene.get("environment_references") or []:
            if not isinstance(item, dict):
                continue
            try:
                pic = int(item.get("picture"))
            except Exception:
                continue
            if available and pic not in available:
                continue
            env_refs.append({"picture": pic, "description": str(item.get("description") or "").strip()})

        env_subjects = []
        for item in scene.get("environment_subjects") or []:
            if not isinstance(item, dict):
                continue
            clean = dict(item)
            pics = []
            for x in item.get("source_pictures") or []:
                try:
                    x = int(x)
                except Exception:
                    continue
                if not available or x in available:
                    pics.append(x)
            clean["source_pictures"] = pics
            env_subjects.append(clean)

        inherited_roles = []
        for item in scene.get("picture_roles") or []:
            if not isinstance(item, dict):
                continue
            try:
                pic = int(item.get("picture"))
            except (TypeError, ValueError):
                continue
            if available and pic not in available:
                continue
            inherited_roles.append({
                "picture": pic,
                "role": str(item.get("role") or "unknown"),
                "label": str(item.get("label") or "")[:120],
            })
        safe = {
            "subjects": subjects,
            "environment_references": env_refs,
            "environment_subjects": env_subjects,
            "picture_roles": inherited_roles,
        }
        from .reference_bindings import endpoint_scene_facts
        blocks.append(render_message('shared', 'endpoint_header', label=label) + json.dumps(endpoint_scene_facts(safe), ensure_ascii=False, indent=2))
    return "\n\n".join(blocks) if blocks else render_message('shared', 'missing_scene_memory')


def _delivery_speech_lines(analysis: dict):
    speech = (analysis.get("intent") or {}).get("speech_request") or {}
    if not speech.get("required"):
        return []
    if str(speech.get("mode") or "").casefold() != "preserve":
        return [render_message('delivery', 'invented_speech')]
    utterances = speech.get("utterances") or []
    if not utterances:
        return [render_message('delivery', 'missing_utterances')]

    lines = [render_message('delivery', 'speech_header')]
    if speech.get("unresolved_collective_speakers"):
        lines.append(render_message("delivery", "unresolved_collective", speakers=", ".join(speech["unresolved_collective_speakers"])))
    if speech.get("unresolved_dialogue_events"):
        lines.append(render_message("delivery", "unresolved_event", events=", ".join(map(str, speech["unresolved_dialogue_events"]))))
    speaker_ids = {}
    for number, entry in enumerate(utterances, 1):
        if isinstance(entry, dict):
            speaker = str(entry.get("speaker") or entry.get("name") or "").strip()
            words = str(entry.get("text") or entry.get("utterance") or "").strip()
        else:
            value = str(entry or "").strip()
            speaker, words = (value.split(":", 1) if ":" in value else ("", value))
            speaker, words = speaker.strip(), words.strip()
        subject = _delivery_speaker_subject(speaker, analysis) if speaker else None
        # Same source gets the same voice ID, even if it speaks again later.
        # Ambiguous/unnamed sources are not assigned a guessed Subject.
        identity = ("subject", subject) if subject is not None else (("name", speaker.casefold()) if speaker else None)
        if identity is not None and identity not in speaker_ids:
            speaker_ids[identity] = len(speaker_ids) + 1
        marker = f"(S{speaker_ids[identity]})" if identity is not None else render_message('delivery', 'unresolved_id')
        source = (render_message('delivery', 'subject_source', subject=subject) if subject is not None else
                  (render_message('delivery', 'unresolved_source', speaker=speaker) if speaker else render_message("delivery", "unspecified_source")))
        lines.append(render_message('delivery', 'event', event_number=number, source=source, speaker_id=marker, quoted_words=json.dumps(words, ensure_ascii=False)))
        if isinstance(entry, dict) and entry.get("shared_line") is not None:
            lines.append(render_message('delivery', 'shared_line', shared_line=entry['shared_line'])
                         + (render_message('delivery', 'shared_simultaneous')
                            if entry.get("delivery") == "simultaneous" else
                            render_message('delivery', 'shared_coordination')))
        if subject is not None:
            language = str(speech.get("language") or "").strip()
            label = language if (re.fullmatch(r"[A-Za-z][A-Za-z -]{1,30}", language) and language.casefold() not in {"auto", "unknown", "none", "unspecified", "language", "actual spoken language"}) else "actual spoken language"
            lines.append(render_message('delivery', 'literal_event', subject=subject, speaker_id=marker, label=label, words=words) +
                         (render_message('delivery', 'language_placeholder') if label == "actual spoken language" else ""))
    lines.append(render_message('delivery', 'speech_omission_rule'))
    lines.append(render_message('delivery', 'speech_final_rule'))
    return lines


def _composer_delivery_contract(analysis_json: str) -> str:
    """Compact, machine-derived final delivery checklist for text-only Pass #2."""
    try:
        analysis = json.loads(analysis_json)
    except (TypeError, ValueError):
        return render_message('delivery', 'fallback')
    if not isinstance(analysis, dict):
        return render_message('delivery', 'fallback')
    reference = analysis.get("reference_contract") or {}
    bindings = reference.get("required_picture_bindings") or []
    requirements = [render_message('delivery', 'reference_header')]
    for item in bindings:
        if not isinstance(item, dict):
            continue
        picture = item.get("picture")
        subjects = item.get("subjects") or []
        role = str(item.get("role") or "").casefold()
        visible = item.get("required_in_shot") is not False
        if subjects:
            for subject in subjects:
                if role == "environment" and not visible:
                    requirements.append(
                        render_message('delivery', 'optional_environment_subject', subject=subject, picture=picture)
                    )
                else:
                    requirements.append(render_message('delivery', 'subject_binding', subject=subject, picture=picture))
                    if role == "environment":
                        requirements.append(
                            render_message('delivery', 'visible_environment_subject', subject=subject)
                        )
        elif role == "character":
            requirements.append(
                render_message('delivery', 'unresolved_character', picture=picture)
            )
        elif role == "environment":
            if visible:
                requirements.append(
                    render_message('delivery', 'visible_environment_picture', picture=picture)
                )
            else:
                requirements.append(
                    render_message('delivery', 'offscreen_picture', picture=picture)
                )
        elif role in {"target_perspective", "end_keyframe"}:
            requirements.append(render_message('delivery', 'target_binding', role=role, picture=picture))
    if reference.get("concrete_keyframe_pictures"):
        requirements.append(render_message('delivery', 'keyframe_present'))
    else:
        requirements.append(render_message('delivery', 'keyframe_absent'))
    requirements.extend(_delivery_speech_lines(analysis))
    return "\n".join("- " + line for line in requirements)
