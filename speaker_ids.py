"""Conservative, deterministic live-output normalization for H3 vocal markers.

Resolve exact, authorized dialogue to uniquely reference-backed people.
Only vocal IDs are edited, and only in live output before materialization.
Never change words, stage direction, other prose or user-edited frozen shots.
"""
from collections import defaultdict
import re

from .validator import DIALOGUE_RE, SPEAKER_RE, SUBJECT_RE, SECTIONS

# An actor attribution is more than an incidental Subject mention. This small
# syntactic gate protects against e.g. "S1 watches S2 ask" being normalized as
# S1's speech. Ambiguity fails closed and remains visible in Validator output.
_VOCAL_CUE = re.compile(
    r"\b(?:says?|said|asks?|asked|replies|reply|replied|responds?|responded|"
    r"answers?|answered|speaks?|spoke|whispers?|whispered|murmurs?|murmured|"
    r"shouts?|shouted|adds?|added|calls?|called|exclaims?|exclaimed|"
    r"mutters?|muttered|sings?|sang|hums?|hummed)\b", re.I
)
_OBJECT_PREP = re.compile(
    r"\b(?:to|toward|towards|at|with|for|of|about|from|beside|behind|near|"
    r"next\s+to|alongside|on|over|under)\s*$", re.I
)


def _grounded_vocal_cue(lead, occurrence, source):
    """Require an immediate, compatible vocal attribution for named authority.

    Keep broad reference resolution out of the staging rewrite. A competing
    Subject acting nearer the speaking verb, or a new sentence after the
    intended speaker mention, makes the local attribution uncertain.
    """
    tail = lead[occurrence.end():]
    cues = list(_VOCAL_CUE.finditer(tail))
    if not cues:
        return False
    cue = cues[-1]
    between = tail[:cue.start()]
    if re.search(r"[.!?]\s+(?=[A-Z<])", between):
        return False
    for other in SUBJECT_RE.finditer(between):
        if int(other.group(1)) == source:
            continue
        if not _OBJECT_PREP.search(between[:other.start()]):
            return False
    return True


def _detail_span(text):
    match = re.search(r"(?im)^detailed_description:\s*", text)
    if match is None:
        return None
    start = match.end()
    next_heading = re.search(
        r"(?im)^(?:" + "|".join(re.escape(s) for s in SECTIONS) + r"):\s*",
        text[start:],
    )
    return (start, start + next_heading.start() if next_heading else len(text))


def _named_subjects(analysis):
    """Resolve explicit Analyst/role labels to unique, non-environment Subjects."""
    candidates = defaultdict(set)
    subjects = analysis.get("subjects") or []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        try:
            number = int(subject["subject"])
        except (KeyError, TypeError, ValueError):
            continue
        if str(subject.get("kind") or "").casefold() in {"environment", "location"}:
            continue
        labels = []
        if subject.get("name"):
            labels.append(str(subject["name"]))
        description = str(subject.get("description") or "")
        named_description = re.match(r"^([^:\n]{1,60}):\s+", description)
        if named_description:
            labels.append(named_description.group(1))
        try:
            pictures = {int(p) for p in (subject.get("source_pictures") or [])}
        except (TypeError, ValueError):
            pictures = set()
        for asset in (analysis.get("asset_analysis") or []):
            if not isinstance(asset, dict):
                continue
            if str(asset.get("primary_role") or "").casefold() != "character":
                continue
            try:
                if int(asset.get("picture")) in pictures and asset.get("label"):
                    labels.append(str(asset["label"]))
            except (ValueError, TypeError):
                continue
        for role in ((analysis.get("reference_contract") or {}).get("picture_roles") or []):
            if not isinstance(role, dict) or str(role.get("role") or "").casefold() != "character":
                continue
            try:
                if int(role.get("picture")) in pictures and role.get("label"):
                    labels.append(str(role["label"]))
            except (ValueError, TypeError):
                continue
        for label in labels:
            key = label.strip().casefold()
            if key:
                candidates[key].add(number)
    return {key: next(iter(ids)) for key, ids in candidates.items() if len(ids) == 1}


def _speech_entry(entry):
    """Extract (explicit speaker, actual words) without guessing speakers."""
    if isinstance(entry, dict):
        name = str(entry.get("speaker") or entry.get("name") or "").strip()
        content = str(entry.get("text") or entry.get("utterance") or "").strip()
        return name, content
    if isinstance(entry, str) and ":" in entry:
        speaker, words = entry.split(":", 1)
        return speaker.strip(), words.strip()
    return "", str(entry or "").strip()


def normalize_speaker_ids(h3_prompt, analysis):
    """Return (prompt, added_count), inserting missing markers only when safe.

    A verbatim user utterance with a uniquely resolved, reference-backed
    speaker is the strongest authority. Otherwise exactly one person Subject
    must occur before the event. IDs follow first-vocal-event order, not
    Subject numbers. Never overwrite a pre-existing contradictory marker;
    leave it for the Validator, to preserve rc17 fail-closed behavior.
    """
    text = str(h3_prompt or "")
    if not isinstance(analysis, dict):
        return text, 0
    span = _detail_span(text)
    if span is None:
        return text, 0
    start, end = span
    detail = text[start:end]
    events = list(DIALOGUE_RE.finditer(detail))
    if not events:
        return text, 0

    speech = (analysis.get("intent") or {}).get("speech_request") or {}
    is_preserve = str(speech.get("mode") or "").casefold() == "preserve"
    provided = speech.get("utterances") or []
    if is_preserve:
        # A model that changed or dropped a user's words must NOT be made to
        # look correct by a merely syntactic normalization.
        if len(provided) != len(events):
            return text, 0
        expected = [_speech_entry(item) for item in provided]
        if [words for _, words in expected] != [m.group(2).strip() for m in events]:
            return text, 0
    else:
        expected = []

    allowed = {
        int(item.get("subject")) for item in analysis.get("subjects") or []
        if isinstance(item, dict) and str(item.get("subject", "")).isdigit()
        and str(item.get("kind") or "").casefold() not in {"environment", "location"}
    }
    names = _named_subjects(analysis)
    # Reuse rc22's conservative phrase -> Subject mapping. This resolves
    # "the younger man" when asset descriptions make it unique, but never a
    # generic/tied label or an offscreen person lacking a reference binding.
    from .prompt_skill import _delivery_speaker_subject
    sources = []
    positions = []
    previous_end = 0
    for i, event in enumerate(events):
        lead = detail[previous_end:event.start()]
        explicit_name = expected[i][0] if is_preserve else ""
        if explicit_name:
            source = names.get(explicit_name.casefold())
            if source is None:
                source = _delivery_speaker_subject(explicit_name, analysis)
            if source is None:
                return text, 0  # An unmapped/offscreen speaker is not a Subject.
        else:
            candidates = {int(num) for num in SUBJECT_RE.findall(lead)} & allowed
            if len(candidates) != 1:
                return text, 0
            source = next(iter(candidates))
        if source not in allowed:
            return text, 0
        source_re = re.compile(rf"<Subject\s+{source}>")
        occurrences = list(source_re.finditer(lead))
        if not occurrences:
            return text, 0  # Never invent a new Subject mention or alter prose.
        if explicit_name and not _grounded_vocal_cue(lead, occurrences[-1], source):
            return text, 0  # Speaker role in the actual prose is not grounded.
        sources.append(source)
        positions.append(start + previous_end + occurrences[-1].end())
        previous_end = event.end()

    # Determine the canonical speaker numbering from actual authorized events.
    assigned = {}
    expected_ids = []
    for source in sources:
        if source not in assigned:
            assigned[source] = len(assigned) + 1
        expected_ids.append(assigned[source])

    edits = []
    previous_end = 0
    for i, event in enumerate(events):
        lead = detail[previous_end:event.start()]
        explicit_name = expected[i][0] if is_preserve else ""
        markers = list(SPEAKER_RE.finditer(lead))
        if markers:
            if len(markers) != 1:
                return text, 0
            marker = markers[0]
            # Do not conceal model-provided conflicting IDs. A valid marker
            # still must belong to the authorized Subject, not a bystander.
            adjacent = re.search(
                rf"<Subject\s+{sources[i]}>\s*$", lead[:marker.start()]
            )
            if ((explicit_name and not adjacent)
                    or int(marker.group(1)) != expected_ids[i]):
                return text, 0
        else:
            edits.append((positions[i], f" (S{expected_ids[i]})"))
        previous_end = event.end()

    if not edits:
        return text, 0
    for position, insertion in reversed(edits):
        text = text[:position] + insertion + text[position:]
    return text, len(edits)
