"""Assemble LLM request data; instruction wording belongs to flavour_skills."""
import json
from .flavour_skills import render_template, render_message, _read
from .speaker_resolution import _delivery_speaker_subject  # compatibility import
from .prompt_contracts import (
    _continuity_contract_text, _delivery_speech_lines, _composer_delivery_contract,
)

SKILL_VERSION = "0.6.6-creative-fidelity"
REPAIR_SYSTEM = _read("repair_system.txt")


def analysis_user_prompt(direction: str, duration: float, picture_slots,
                         operation: str = "new", continuity_context=None,
                         continuity_note: str = "", reference_brief=None) -> str:
    slots = ", ".join(f"Picture {n}" for n in picture_slots) if picture_slots else "none"
    operation = str(operation or "new").casefold()
    brief = reference_brief if isinstance(reference_brief, dict) else {}
    role_notes = json.dumps(brief, ensure_ascii=False) if brief else "{}"
    role_instruction = (
        render_template('reference_role_prepass', role_notes=role_notes)
    )
    if operation in {"extend", "prepend", "bridge"}:
        scene_memory = _continuity_contract_text(continuity_context, picture_slots)
        note = continuity_note.strip() or render_message('analyst', 'missing_endpoint_note')
        if operation == "extend":
            task = render_message('analyst', 'extend')
        elif operation == "prepend":
            task = render_message('analyst', 'prepend')
        else:
            task = render_message('analyst', 'bridge')
        return render_template('analyst_continuity', operation=operation, direction=direction.strip(), role_instruction=role_instruction, duration=duration, slots=slots, note=note, scene_memory=scene_memory, task=task)

    return render_template('analyst_new', direction=direction.strip(), role_instruction=role_instruction, duration=duration, slots=slots)


def composer_user_prompt(direction: str, duration: float, picture_slots, analysis_json: str,
                         operation: str = "new", continuity_context=None,
                         continuity_note: str = "", reference_brief=None) -> str:
    slots = ", ".join(f"Picture {n}" for n in picture_slots) if picture_slots else "none"
    delivery = _composer_delivery_contract(analysis_json)
    operation = str(operation or "new").casefold()
    if operation in {"extend", "prepend", "bridge"}:
        scene_memory = _continuity_contract_text(continuity_context, picture_slots)
        note = continuity_note.strip() or render_message('composer', 'missing_endpoint_note')
        if operation == "extend":
            task = render_message('composer', 'extend')
        elif operation == "prepend":
            task = render_message('composer', 'prepend')
        else:
            task = render_message('composer', 'bridge')
        return render_template('composer_continuity', operation=operation, direction=direction.strip(), duration=duration, slots=slots, note=note, scene_memory=scene_memory, analysis_json=analysis_json, task=task, delivery=delivery)

    return render_template('composer_new', direction=direction.strip(), duration=duration, slots=slots, analysis_json=analysis_json, delivery=delivery)
