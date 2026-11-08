"""Small, deterministic structural and semantic checks for H3 output.

No inference or silent rewriting is performed here.  Failures are returned to
OBVPM Director's existing optional LLM repair path.
"""
import re
from .action_fidelity import action_role_checks

SECTIONS = [
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
]
LABEL_RE = re.compile(r"<(Subject|Picture|Video|Audio)\s+(\d+)>")
DIALOGUE_RE = re.compile(r"<d>\s*\[([^\]]+)\]\s*(.*?)\s*</d>", re.I | re.S)
SPEAKER_RE = re.compile(r"\(S([1-9]\d*)\)")
SUBJECT_RE = re.compile(r"<Subject\s+(\d+)>")
SUMMARY_PREFIX_RE = re.compile(r"(?im)^summary:\s*\[([^\]\n]+)\]")


def _section_body(text, section):
    """Return one canonical section's body or an empty string."""
    m = re.search(r"(?im)^" + re.escape(section) + r":\s*", text)
    if not m:
        return ""
    next_heading = re.search(r"(?im)^(?:" + "|".join(SECTIONS) + r"):\s*", text[m.end():])
    return text[m.end():m.end() + next_heading.start()] if next_heading else text[m.end():]


def _reference_checks(text, required_picture_bindings):
    problems = []
    definitions = _section_body(text, "subject_definitions")
    detail = _section_body(text, "detailed_description")
    # Check the accepted source mapping, not merely whether some <Picture N>
    # appears somewhere in the prompt.
    for binding in required_picture_bindings or []:
        if not isinstance(binding, dict):
            continue
        try:
            picture = int(binding["picture"])
        except (KeyError, TypeError, ValueError):
            continue
        role = str(binding.get("role") or "unknown").casefold()
        subjects = []
        for raw_subject in binding.get("subjects") or []:
            try:
                subjects.append(int(raw_subject))
            except (TypeError, ValueError):
                continue
        picture_tag = f"<Picture {picture}>"
        required_in_shot = binding.get("required_in_shot", True) is not False
        if subjects:
            for subject in subjects:
                definition = re.search(
                    rf"(?m)^\s*<Subject\s+{subject}>\s+is\s+([^\n]*)", definitions,
                    flags=re.I,
                )
                # Optional offscreen environments need not be explicitly defined.
                if ((required_in_shot or definition is not None)
                        and (not definition or picture_tag not in definition.group(0))):
                    problems.append(
                        f"reference binding missing: <Subject {subject}> must cite {picture_tag} "
                        "in subject_definitions"
                    )
                if role == "environment" and required_in_shot and f"<Subject {subject}>" not in detail:
                    problems.append(
                        f"environment <Subject {subject}> from {picture_tag} is defined "
                        "but not used in detailed_description"
                    )
        elif role in {"environment", "target_perspective", "end_keyframe"} and required_in_shot and picture_tag not in detail:
            problems.append(
                f"{role} reference missing: cite {picture_tag} in detailed_description "
                "to preserve its accepted picture role"
            )
    return problems


def _speech_checks(text, expected_speech=None, speaker_subject_map=None):
    problems = []
    detail = _section_body(text, "detailed_description")
    matches = list(DIALOGUE_RE.finditer(detail))
    raw_opens = len(re.findall(r"<d>", detail, flags=re.I))
    raw_closes = len(re.findall(r"</d>", detail, flags=re.I))
    if raw_opens != len(matches) or raw_closes != len(matches):
        problems.append("noncanonical or unbalanced dialogue: each vocal event needs <d>[Language] words</d>")

    source_to_speaker = {}
    speaker_to_source = {}
    first_seen_ids = []
    previous_end = 0
    event_subjects = []
    for event_number, match in enumerate(matches, 1):
        # The speaker tag for this event must be present *after* the preceding
        # vocal event.  An ID used for event 1 cannot silently label event 2.
        lead = detail[previous_end:match.start()]
        marker = list(SPEAKER_RE.finditer(lead))
        event_subject = None
        if not marker:
            problems.append(f"dialogue event {event_number} has no preceding (Sx) speaker ID")
        else:
            mark = marker[-1]
            speaker_id = int(mark.group(1))
            if speaker_id not in first_seen_ids:
                first_seen_ids.append(speaker_id)
            # Only make a Source->ID assertion when the source label is explicit
            # in the immediate clause preceding the speaker marker.
            preceding_subjects = list(SUBJECT_RE.finditer(lead[:mark.start()]))
            # Canonical explicit attribution is <Subject N> (Sx); when the
            # marker is adjacent, this is a reliable user-speaker binding.
            adjacent = re.search(r"<Subject\s+(\d+)>\s*$", lead[:mark.start()])
            if adjacent:
                event_subject = int(adjacent.group(1))
            elif len(preceding_subjects) == 1:
                event_subject = int(preceding_subjects[0].group(1))
            if preceding_subjects:
                source = int(preceding_subjects[-1].group(1))
                previous = source_to_speaker.setdefault(source, speaker_id)
                if previous != speaker_id:
                    problems.append(
                        f"<Subject {source}> changes speaker ID from (S{previous}) to (S{speaker_id})"
                    )
                other = speaker_to_source.setdefault(speaker_id, source)
                if other != source:
                    problems.append(
                        f"(S{speaker_id}) is assigned to both <Subject {other}> and <Subject {source}>"
                    )
        event_subjects.append(event_subject)
        previous_end = match.end()
    if first_seen_ids != list(range(1, len(first_seen_ids) + 1)):
        problems.append("speaker IDs must be assigned (S1), (S2), ... in first-vocal-event order")

    request = expected_speech if isinstance(expected_speech, dict) else {}
    if request.get("required") and str(request.get("mode", "")).casefold() in {"preserve", "invent"}:
        if not matches:
            problems.append("required speech has no canonical <d>[Language] ...</d> vocal events")
        if str(request.get("mode")).casefold() == "preserve":
            utterances = request.get("utterances") or []
            if not utterances:
                problems.append("required preserved dialogue has no authoritative utterances; cannot validate wording or speaker order")
            expected = []
            for entry in utterances:
                if isinstance(entry, str):
                    expected.append(entry.split(":", 1)[-1].strip() if ":" in entry else entry.strip())
                elif isinstance(entry, dict):
                    expected.append(str(entry.get("text") or entry.get("utterance") or "").strip())
            actual = [m.group(2).strip() for m in matches]
            if expected and expected != actual:
                problems.append("preserved dialogue differs from the user-supplied wording, order, or event count")
            if request.get("authority") == "user_direction" and speaker_subject_map:
                for i, entry in enumerate(utterances[:len(event_subjects)]):
                    name = (str(entry.get("speaker") or entry.get("name") or "").strip()
                            if isinstance(entry, dict)
                            else entry.split(":", 1)[0].strip() if isinstance(entry, str) and ":" in entry
                            else "")
                    expected_subject = speaker_subject_map.get(name.casefold())
                    actual_subject = event_subjects[i]
                    if (expected_subject is not None and actual_subject is not None
                            and int(expected_subject) != int(actual_subject)):
                        problems.append(
                            f"dialogue event {i + 1} attributed to <Subject {actual_subject}> "
                            f"but user-authorized speaker '{name}' is <Subject {expected_subject}>"
                        )
    return problems


def validate_h3_prompt(text: str, available_pictures, allowed_subjects=None,
                       pov_viewer_mode=False, visible_person_subject_count=None,
                       viewer_full_visibility=False, required_picture_bindings=None,
                       expected_speech=None, picture_roles=None, operation=None,
                       speaker_subject_map=None, required_actions=None):
    problems = []
    positions = []
    lower = text.lower()
    for sec in SECTIONS:
        needle = sec + ":"
        p = lower.find(needle)
        if p < 0:
            problems.append(f"missing section: {sec}")
        positions.append(p)

    present_positions = [p for p in positions if p >= 0]
    if present_positions and present_positions != sorted(present_positions):
        problems.append("sections are not in canonical order")

    available_pictures = set(int(x) for x in available_pictures)
    for kind, n_s in LABEL_RE.findall(text):
        if kind == "Picture":
            n = int(n_s)
            if n not in available_pictures:
                problems.append(f"references unavailable <Picture {n}>; connected slots are {sorted(available_pictures)}")

    used_subjects = sorted({int(n) for k, n in LABEL_RE.findall(text) if k == "Subject"})
    if "subject_definitions:" in lower and "summary:" in lower:
        definitions = _section_body(text, "subject_definitions")
        for n in used_subjects:
            if f"<Subject {n}>" not in definitions:
                problems.append(f"<Subject {n}> used but not defined in subject_definitions")

    if allowed_subjects is not None:
        allowed_subjects = {int(x) for x in allowed_subjects}
        for n in used_subjects:
            if n not in allowed_subjects:
                problems.append(
                    f"<Subject {n}> is not reference-backed for this run; POV/viewer roles must remain descriptive unless bound to an allowed reference Subject"
                )

    if pov_viewer_mode and not viewer_full_visibility and visible_person_subject_count == 1:
        plural_visual_patterns = [
            (r"\btwo\s+(?:visible\s+)?figures\b", "two figures"),
            (r"\bboth\s+(?:of\s+their\s+)?faces\b", "both faces"),
            (r"\btheir\s+faces\b", "their faces"),
            (r"\btwo\s+people\b", "two people"),
        ]
        for pattern, label in plural_visual_patterns:
            if re.search(pattern, text, flags=re.I):
                problems.append(
                    f"POV viewer was promoted to a second fully visible person via '{label}'; viewer body-part actions remain first-person/partial unless explicitly revealed"
                )
                break

    if SPEAKER_RE.search(text) and "<d>" not in text:
        problems.append("speaker IDs are present but no <d> dialogue tag was found")
    problems.extend(_speech_checks(text, expected_speech, speaker_subject_map))
    problems.extend(_reference_checks(text, required_picture_bindings))
    problems.extend(action_role_checks(_section_body(text, "detailed_description"), required_actions))

    roles = picture_roles or []
    has_concrete_keyframe = any(
        isinstance(item, dict) and item.get("role") == "end_keyframe"
        and item.get("picture") in available_pictures for item in roles
    )
    summary = SUMMARY_PREFIX_RE.search(text)
    if summary:
        types = {piece.strip().casefold() for piece in summary.group(1).split("+")}
        if "keyframe completion" in types and not has_concrete_keyframe:
            problems.append("task prefix 'keyframe completion' has no connected concrete keyframe picture")
        if str(operation or "new").casefold() in {"extend", "prepend", "bridge"} and "video continuation" not in types:
            problems.append("continuity operation requires 'video continuation' in summary task prefix")
    elif operation is not None:
        problems.append("summary must start with a canonical [task type] prefix")

    extras = re.findall(r"(?mi)^([a-z_ ]{3,40}):\s*$", text)
    extra_names = [x.strip().lower().replace(" ", "_") for x in extras if x.strip().lower().replace(" ", "_") not in SECTIONS]
    if extra_names:
        problems.append("noncanonical top-level section(s): " + ", ".join(sorted(set(extra_names))))
    return problems


def report(problems):
    if not problems:
        return "PASS — six-section structure, reference bindings and speaker checks passed."
    return "FAIL\n- " + "\n- ".join(problems)
