import json

# H3-DIRECTOR-ACTING-EXPRESSION-DEV7
# H3-DIRECTOR-FLAVOUR-DEV8
# H3-DIRECTOR-SKILL-ISOLATION-DEV9
# H3-DIRECTOR-ACTION-OWNED-DEV10
# H3-DIRECTOR-INDIVIDUAL-TRACKS-DEV10C
import re

SKILL_VERSION = "0.6.4.dev10e-continuity-performance-contract"





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
        blocks.append(f"{label} STABLE SCENE FACTS:\n" + json.dumps(safe, ensure_ascii=False, indent=2))
    return "\n\n".join(blocks) if blocks else "[No inherited stable scene facts available.]"


def analysis_user_prompt(direction: str, duration: float, picture_slots,
                         operation: str = "new", continuity_context=None,
                         continuity_note: str = "", reference_brief=None) -> str:
    slots = ", ".join(f"Picture {n}" for n in picture_slots) if picture_slots else "none"
    operation = str(operation or "new").casefold()
    brief = reference_brief if isinstance(reference_brief, dict) else {}
    role_notes = json.dumps(brief, ensure_ascii=False) if brief else "{}"
    role_instruction = (
        "REFERENCE ROLE PREPASS (before visual interpretation):\n"
        "Read the user's direction for character and location names first. "
        "Match those referents to the actual numbered images when visually justified. "
        "Apply explicit numbered user labels below; leave ambiguous matches unresolved. "
        "Multiple detail references of the same character are complementary, "
        "not new identities. Current connected Pictures and current user roles "
        "override incompatible inherited descriptions even when slot numbers are reused.\n"
        f"USER PICTURE LABELS: {role_notes}\n"
    )
    if operation in {"extend", "prepend", "bridge"}:
        scene_memory = _continuity_contract_text(continuity_context, picture_slots)
        note = continuity_note.strip() or "Continuity endpoint frame metadata unavailable."
        if operation == "extend":
            task = "Continue the user-defined or inherited action directly from START; use remaining time for its physically continuous performance, without replay or a new unrelated event."
        elif operation == "prepend":
            task = "Direct the user-defined action and its micro-movements chronologically toward the physical TARGET state."
        else:
            task = "Direct one continuous within-action physical and expressive progression from START to TARGET."
        return f"""OPERATION:
{operation}

CURRENT USER DIRECTION:
{direction.strip()}

{role_instruction}
AVAILABLE DURATION: {duration:.2f} seconds
CURRENT H3 REFERENCE IMAGE SLOTS: {slots}

DIRECTOR-ONLY ENDPOINT IMAGE STATUS / ORDER:
{note}

INHERITED STABLE SCENE MEMORY:
{scene_memory}

TASK:
{task}
The endpoint frame establishes the physical seam. Keep the established subjects and location active while planning the new interval. Earlier completed actions are history. Current numbered reference images remain authoritative visual evidence. When a current picture serves as a target_perspective, preserve it as a soft end-goal rather than a hard final-frame match. Return the required JSON only."""

    return f"""USER DIRECTION:
{direction.strip()}

{role_instruction}
AVAILABLE DURATION: {duration:.2f} seconds
CONNECTED REFERENCE IMAGE SLOTS: {slots}.

Identify the action, participants, roles and spatial state established by the current user Direction and references. Keep that action authoritative; do not invent a new story or extra event just to create a micro-scene. Direct its camera-visible performance over the available seconds: micro-movement, expressive facial and bodily details, timing, contact, reciprocal reactions and a continuable physical end state. Only when the user explicitly requests invention may you choose an additional small compatible event. If the user explicitly requests invented speech, supply actual words in speech_request/utterances; otherwise do not invent spoken wording. Different seeds may vary HOW the same user-owned action is performed, not WHAT action occurs. Return the required JSON only."""


def _delivery_speaker_subject(speaker: str, analysis: dict):
    """Resolve a speaker description only when ONE referenced person fits.

    Explicit names and Subject labels win. Descriptive phrases such as
    'the younger person' may match a unique visual description, but generic
    labels and tied matches remain unresolved. This is guidance to Pass #2,
    not a rewrite of its output or the Validator's safety checks.
    """
    from .speaker_ids import _named_subjects

    subjects = []
    for entry in analysis.get("subjects") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("kind") or "").casefold() in {"environment", "location"}:
            continue
        try:
            number = int(entry["subject"])
        except (KeyError, TypeError, ValueError):
            continue
        subjects.append((number, entry))
    allowed = {number for number, _ in subjects}
    # A reference-backed Subject is required even for delivery guidance.
    permitted = ((analysis.get("reference_contract") or {}).get("allowed_subjects") or [])
    if permitted:
        grounded = set()
        for entry in permitted:
            if isinstance(entry, dict):
                try:
                    grounded.add(int(entry["subject"]))
                except (KeyError, TypeError, ValueError):
                    continue
        allowed &= grounded
        subjects = [(number, entry) for number, entry in subjects if number in allowed]
    speaker = str(speaker or "").strip()
    explicit = re.fullmatch(r"<Subject\s+(\d+)>", speaker, flags=re.I)
    if explicit:
        number = int(explicit.group(1))
        return number if number in allowed else None
    named = _named_subjects(analysis).get(speaker.casefold())
    if named in allowed:
        return named

    # Require ALL descriptive anchor words and a unique match. Common role
    # nouns and grammatical glue are not identity-discriminating anchors.
    generic = {
        "the", "a", "an", "and", "or", "in", "of", "on", "at", "to", "from",
        "with", "by", "his", "her", "their", "our", "my", "your", "this", "that",
        "man", "woman", "person", "people", "figure", "character", "subject",
        "speaker", "voice", "guy", "girl", "boy", "shirt", "jacket", "wearing",
    }
    words = lambda t: set(re.findall(r"[^\W_]+", str(t or "").casefold()))
    anchors = words(speaker) - generic
    if not anchors:
        return None
    matches = []
    for number, entry in subjects:
        description = str(entry.get("description") or "") + " " + str(entry.get("name") or "")
        for asset in analysis.get("asset_analysis") or []:
            if not isinstance(asset, dict):
                continue
            if asset.get("picture") in (entry.get("source_pictures") or []):
                description += " " + str(asset.get("description") or "")
                description += " " + str(asset.get("label") or "")
        if anchors <= words(description):
            matches.append(number)
    return matches[0] if len(matches) == 1 else None


def _delivery_speech_lines(analysis: dict):
    speech = (analysis.get("intent") or {}).get("speech_request") or {}
    if not speech.get("required"):
        return []
    if str(speech.get("mode") or "").casefold() != "preserve":
        return ["Explicitly requested invented speech: compose the spoken words; "
                "label each vocal event with the source's stable (Sx) ID."]
    utterances = speech.get("utterances") or []
    if not utterances:
        return ["Preserved dialogue requested but no authoritative utterances supplied; "
                "do not invent text to fill this gap."]

    lines = ["Authoritative user dialogue, in playback order (verbatim words):"]
    if speech.get("unresolved_collective_speakers"):
        lines.append("UNRESOLVED collective speaker attribution: " + ", ".join(speech["unresolved_collective_speakers"]) + ". Preserve the words; do not guess a reference binding.")
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
        marker = f"(S{speaker_ids[identity]})" if identity is not None else "(Sx: identify source from scene)"
        source = (f"<Subject {subject}>" if subject is not None else
                  (f"speaker '{speaker}' (Subject unresolved)" if speaker else "speaker not specified"))
        lines.append(f"Event {number}: {source} {marker} — exact spoken words: {json.dumps(words, ensure_ascii=False)}")
        if isinstance(entry, dict) and entry.get("shared_line") is not None:
            lines.append(f"  Shared line {entry['shared_line']}: this actor speaks the complete words. "
                         + ("Deliver in unison with the other actors of this shared line, not as a reply."
                            if entry.get("delivery") == "simultaneous" else
                            "Preserve the user/Analyst coordination with the other actors of this shared line."))
        if isinstance(entry, dict) and entry.get("shared_line") is not None and subject is not None:
            language = str(speech.get("language") or "").strip()
            label = language if re.fullmatch(r"[A-Za-z][A-Za-z -]{1,30}", language) else "actual spoken language"
            lines.append(f"  Required literal shot event: <Subject {subject}> {marker} says, <d>[{label}] {words}</d>" +
                         (" (replace the language placeholder with the real language)." if label == "actual spoken language" else ""))
    lines.append("Never replace a spoken event with 'speaks the line' or a description of speaking. "
                 "Shared simultaneous events must each have a tag and distinct source ID, without implying a sequential exchange.")
    lines.append("Emit EVERY event once and in order as a separate <d>[Language] words</d>; "
                 "put every event in detailed_description, at its actual speech beat, with its specified Subject and (Sx). "
                 "The summary never satisfies this contract; keep the quoted words byte-for-byte.")
    return lines


def _composer_delivery_contract(analysis_json: str) -> str:
    """Compact, machine-derived final delivery checklist for text-only Pass #2."""
    try:
        analysis = json.loads(analysis_json)
    except (TypeError, ValueError):
        return "Use the normalized reference_contract and canonical per-event speaker IDs."
    if not isinstance(analysis, dict):
        return "Use the normalized reference_contract and canonical per-event speaker IDs."
    reference = analysis.get("reference_contract") or {}
    bindings = reference.get("required_picture_bindings") or []
    requirements = ["Reference bindings:"]
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
                        f"Optional offscreen environment <Subject {subject}> / <Picture {picture}>: "
                        "do not force a detailed_description citation or wider framing; "
                        "if defined, preserve the correct Picture binding."
                    )
                else:
                    requirements.append(f"<Subject {subject}> definition cites <Picture {picture}>.")
                    if role == "environment":
                        requirements.append(
                            f"Visible environment: cite <Subject {subject}> in detailed_description."
                        )
        elif role == "character":
            requirements.append(
                f"UNRESOLVED character reference <Picture {picture}>: do not silently discard it; "
                "the user must identify the existing Subject owner (or re-analyze)."
            )
        elif role == "environment":
            if visible:
                requirements.append(
                    f"detailed_description cites <Picture {picture}> as the visible environment (no Subject)."
                )
            else:
                requirements.append(
                    f"Offscreen <Picture {picture}> is scene memory, not a required visible citation."
                )
        elif role in {"target_perspective", "end_keyframe"}:
            requirements.append(f"Include the accepted {role} <Picture {picture}> in detailed_description.")
    if reference.get("concrete_keyframe_pictures"):
        requirements.append("A concrete end keyframe is present; use task types accordingly.")
    else:
        requirements.append("No end keyframe: omit 'keyframe completion' from task prefix.")
    requirements.extend(_delivery_speech_lines(analysis))
    return "\n".join("- " + line for line in requirements)


def composer_user_prompt(direction: str, duration: float, picture_slots, analysis_json: str,
                         operation: str = "new", continuity_context=None,
                         continuity_note: str = "", reference_brief=None) -> str:
    slots = ", ".join(f"Picture {n}" for n in picture_slots) if picture_slots else "none"
    delivery = _composer_delivery_contract(analysis_json)
    operation = str(operation or "new").casefold()
    if operation in {"extend", "prepend", "bridge"}:
        scene_memory = _continuity_contract_text(continuity_context, picture_slots)
        note = continuity_note.strip() or "Continuity endpoint metadata unavailable."
        if operation == "extend":
            task = "Write the next interval directly from START, maintaining the specified ongoing action while detailing its visible changes and reciprocal performance."
        elif operation == "prepend":
            task = "Write the preceding interval of the user-owned action, with physically continuous performance arriving at TARGET."
        else:
            task = "Write one continuous, physically coherent performance of the specified action from START to TARGET."
        return f"""OPERATION:
{operation}

CURRENT USER DIRECTION:
{direction.strip()}

AVAILABLE DURATION: {duration:.2f} seconds
CURRENT H3 PICTURE SLOTS: {slots}

DIRECTOR-ONLY ENDPOINT STATUS:
{note}

INHERITED STABLE SCENE MEMORY:
{scene_memory}

INTERNAL REFERENCE + DIRECTOR ANALYSIS:
{analysis_json}

TASK:
{task}
Keep established subjects and location coherent from the physical seam; previous completed actions remain history. Endpoint frames remain Director-only. Target perspectives are soft composition guides; end keyframes are hard terminal anchors.

REQUIRED OUTPUT BINDINGS:
(machine-derived; apply before stylistic choices)
{delivery}"""

    return f"""USER DIRECTION:
{direction.strip()}

AVAILABLE DURATION: {duration:.2f} seconds
AVAILABLE PICTURE SLOTS: {slots}.

INTERNAL REFERENCE + DIRECTOR ANALYSIS:
{analysis_json}

TASK:
Write the final six-section MiniMax H3 full-reference prompt. Preserve the user/inherited action, actors, targets, duration and blocking in the analysis. Expand its behavior_progression and micro_motion_progression into concrete, camera-visible, physically plausible acting THROUGHOUT the same action, without inventing a separate event. Target perspectives are soft composition guides; end keyframes are hard terminal anchors. Only invent concrete dialogue when explicitly authorized.

REQUIRED OUTPUT BINDINGS:
(machine-derived; apply before stylistic choices)
{delivery}"""

REPAIR_SYSTEM = r'''
You repair a MiniMax H3 full-reference prompt that failed the existing format/reference validation.
Preserve the creative content, micro-scene, staging, dialogue meaning, visibility discipline, and intended shot. Fix only formal H3 syntax/reference problems that are explicitly identified.
Return only the corrected final prompt with exactly these six sections in this order:
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:

Canonical syntax reminders:
- Subject definitions use `<Subject N> is ...`, one plain line each; no Markdown bullets and no `<Subject N>:` definition form.
- A POV/viewer/camera-holder role does not create a `<Subject N>` unless it is already bound to a real reference asset in the analysis reference_contract. Remove invented viewpoint-only Subject definitions and their retention lines.
- In POV, viewer hands/forearms or other first-person body parts may enter frame while the viewer remains off-camera as a full person. Repair accidental plural framing (`two figures`, `both faces`, `their faces`) when only one complete on-screen person is intended.
- Use exact `<Picture N>` tokens, never `(see Picture N)`.
- retention_analysis uses one line per defined reference label and only fixed relationship markers.
- detailed_description contains `[Shot 1]`; later shots use timestamps only for actual cuts.
- Actual vocal sources use stable `(S1)`, `(S2)`, ... assigned by order of vocal events.
- Repair every reported missing `<Picture N>` binding by citing that exact picture in its Source Subject definition, or inside the shot for an environment without a Subject. Keep the current camera/framing; do not replicate a panoramic reference viewpoint.
- Remove `keyframe completion` from the task prefix unless the accepted reference contract includes a concrete end keyframe.
- Canonical spoken-event form: `<Subject 2> (S1) whispers, <d>[English] Welcome home.</d>`
- The `<d>` content contains spoken words only; do not place Subject labels, speaker headers, colons, or screenplay formatting inside it.
- Never leave spoken dialogue as ordinary quoted prose outside `<d>`.
- When no audience-only music is present, write `N/A`.
Do not invent unavailable reference labels.
Do not add commentary or markdown fences.
'''.strip()
