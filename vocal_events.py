"""Normalize bounded, user-authorized H3 vocal events as a transaction.

Never invent speech, replace changed wording, move a beat or guess a source.
The legacy marker-only path remains available for already canonical events.
"""
import re
from .speaker_ids import (_detail_span, _speech_entry,
                          _grounded_vocal_cue, normalize_speaker_ids)
from .validator import DIALOGUE_RE, SPEAKER_RE, SUBJECT_RE, _speech_checks
from .vocal_cues import VOCAL_CUE

# Only delimited spans are eligible; no search-and-replace of arbitrary prose.
_EVENT = re.compile(
    r'<d>\s*(?:\[(?P<lang>[^\]\r\n]+)\]\s*)?(?P<tag>[^<>]*?)\s*</d>'
    r'|"(?P<double>[^"\r\n]+)"|“(?P<curly>[^”\r\n]+)”|„(?P<low>[^“\r\n]+)“'
    r"|(?<!\w)'(?P<single>(?:[^'\r\n]|(?<=\w)'(?=\w))+)'(?!\w)"
    r'|‘(?P<singlecurly>(?:[^’\r\n]|(?<=\w)’(?=\w))+)’', re.I)
_LANGUAGE = re.compile(r'[A-Za-z][A-Za-z -]{1,30}')
_UNKNOWN = {'unknown', 'auto', 'none', 'unspecified', 'language', 'actual spoken language'}


def _source(name, analysis):
    from .speaker_resolution import _delivery_speaker_subject
    result = _delivery_speaker_subject(name, analysis)
    if result is None:
        return None
    refs = analysis.get('reference_contract') or {}
    if 'allowed_subjects' in refs and result not in {
        int(x['subject']) for x in refs['allowed_subjects']
        if isinstance(x, dict) and str(x.get('subject', '')).isdigit()
    }:
        return None
    if not any(isinstance(x, dict) and str(x.get('subject')) == str(result)
               and str(x.get('kind', '')).casefold() == 'person' and x.get('source_pictures')
               for x in analysis.get('subjects') or []):
        return None
    return result


# A Composer may emit the spoken lines as a detached list with trailing IDs.
# A suffix is not the prefix of the next line. Only repair a fully bounded
# block, never move dialogue across action or shot boundaries.
_POSTFIX_LINE = re.compile(r"[ \t]*(<d>[^\r\n]*?</d>)[ \t]+\(S([1-9]\d*)\)[ \t]*", re.I)


def normalize_detached_postfix_events(prompt, analysis):
    """Canonicalize a single-shot detached postfix block using user authority.

    Keep every original dialogue tag byte-identical. A unique reference-backed
    actor, existing staging mention, exact event count/words/order and matching
    existing IDs are required. No mixed inline or cross-shot repair.
    """
    text = str(prompt or '')
    span = _detail_span(text)
    if not span or not isinstance(analysis, dict):
        return text, 0
    start, end = span
    detail = text[start:end]
    speech = (analysis.get('intent') or {}).get('speech_request') or {}
    if (speech.get('authority') != 'user_direction' or speech.get('mode') != 'preserve'
            or not speech.get('required') or speech.get('unresolved_collective_speakers') or speech.get('unresolved_dialogue_events')):
        return text, 0
    expected = [_speech_entry(x) for x in speech.get('utterances') or []]
    events = list(DIALOGUE_RE.finditer(detail))
    if not expected or len(events) != len(expected):
        return text, 0
    if len(re.findall(r'<d>', detail, re.I)) != len(events) or len(re.findall(r'</d>', detail, re.I)) != len(events):
        return text, 0
    if [m.group(2).strip() for m in events] != [words for _, words in expected]:
        return text, 0
    if len(re.findall(r'\[Shot\s+\d+\]', detail, re.I)) != 1:
        return text, 0
    block_start = detail.rfind('\n', 0, events[0].start()) + 1
    if not block_start:
        return text, 0
    staging = detail[:block_start]
    if SPEAKER_RE.search(staging):
        return text, 0
    sources = [_source(name, analysis) for name, _ in expected]
    if None in sources or not set(sources) <= {int(n) for n in SUBJECT_RE.findall(staging)}:
        return text, 0
    lines = detail[block_start:].splitlines(keepends=True)
    assignments = {}
    rendered = []
    count = 0
    for line in lines:
        if not line.strip():
            rendered.append(line)
            continue
        if count >= len(events):
            return text, 0
        content = line.rstrip('\r\n')
        m = _POSTFIX_LINE.fullmatch(content)
        if not m or m.group(1) != events[count].group(0):
            return text, 0
        source = sources[count]
        speaker = assignments.setdefault(source, len(assignments) + 1)
        if int(m.group(2)) != speaker:
            return text, 0
        indent = re.match(r'[ \t]*', content).group(0)
        rendered.append(f'{indent}<Subject {source}> (S{speaker}) {m.group(1)}' + line[len(content):])
        count += 1
    if count != len(events):
        return text, 0
    fixed = text[:start] + staging + ''.join(rendered) + text[end:]
    mapping = {name.casefold(): source for (name, _), source in zip(expected, sources)}
    if _speech_checks(fixed, speech, mapping):
        return text, 0
    return fixed, count


def normalize_authorized_terminal_punctuation(prompt, analysis):
    """Restore only a single added terminal punctuation mark in inline speech.

    The exact user quote remains authoritative. Require equal event counts,
    unique reference-backed speakers, explicit canonical attribution or local
    vocal cues, and a successful full speech check after previewing the
    existing marker normalizer.
    No lexical changes, punctuation substitutions, or reordering.
    """
    text = str(prompt or '')
    span = _detail_span(text)
    if not span or not isinstance(analysis, dict):
        return text, 0
    speech = (analysis.get('intent') or {}).get('speech_request') or {}
    if (speech.get('authority') != 'user_direction' or speech.get('mode') != 'preserve'
            or not speech.get('required') or speech.get('unresolved_collective_speakers') or speech.get('unresolved_dialogue_events')):
        return text, 0
    start, end = span
    detail = text[start:end]
    events = list(DIALOGUE_RE.finditer(detail))
    expected = [_speech_entry(x) for x in speech.get('utterances') or []]
    if not events or len(events) != len(expected):
        return text, 0
    if len(re.findall(r'<d>', detail, re.I)) != len(events) or len(re.findall(r'</d>', detail, re.I)) != len(events):
        return text, 0
    sources = [_source(name, analysis) for name, _ in expected]
    if None in sources:
        return text, 0
    edits = []
    previous = 0
    for event, (_, words), source in zip(events, expected, sources):
        lead = detail[previous:event.start()]
        previous = event.end()
        occurrences = list(re.finditer(rf'<Subject\s+{source}>', lead))
        if not occurrences:
            return text, 0
        # An already canonical <Subject N> (Sx) is explicit attribution.
        # Do not require a second, vocabulary-dependent proof of speech for
        # an event which already has a canonical dialogue tag and marker.
        # The full speech check below verifies the actual ID sequence and
        # actor binding; missing markers still need a grounded delivery cue.
        markers = list(SPEAKER_RE.finditer(lead))
        if markers:
            if len(markers) != 1:
                return text, 0
            marker = markers[0]
            if not re.search(rf'<Subject\s+{source}>\s*$', lead[:marker.start()]):
                return text, 0
            tail = lead[marker.end():]
            if SUBJECT_RE.search(tail) or re.search(r'[.!?]\s+(?=[A-Z<])', tail):
                # Preserve the existing cue-based path for explicit object
                # mentions, but never infer new attribution from a marker.
                if not _grounded_vocal_cue(lead, occurrences[-1], source):
                    return text, 0
        elif not _grounded_vocal_cue(lead, occurrences[-1], source):
            return text, 0
        actual = event.group(2).strip()
        if actual == words:
            continue
        if not words or not words[-1].isalnum() or actual not in {words + '.', words + '!'}:
            return text, 0
        # Delete just the extra character; keep surrounding tag formatting.
        position = event.start(2) + len(event.group(2).rstrip()) - 1
        edits.append(position)
    if not edits:
        return text, 0
    for position in reversed(edits):
        detail = detail[:position] + detail[position + 1:]
    draft = text[:start] + detail + text[end:]
    preview, _ = normalize_speaker_ids(draft, analysis)
    mapping = {name.casefold(): source for (name, _), source in zip(expected, sources)}
    if _speech_checks(preview, speech, mapping):
        return text, 0
    return draft, len(edits)


def normalize_vocal_events(prompt, analysis):
    """Return (prompt, tags_added, ids_added); new tag repairs are all-or-nothing.

    A repaired event must have exactly matching, already written words at a
    locally grounded delivery cue. Missing language may be filled from the
    speech contract. Unbalanced tags and arbitrary omitted words stay errors.
    """
    text = str(prompt or '')
    span = _detail_span(text)
    if not span or not isinstance(analysis, dict):
        return text, 0, 0
    start, end = span
    detail = text[start:end]
    speech = (analysis.get('intent') or {}).get('speech_request') or {}
    # Preserve existing supported behavior for already well-formed tags.
    opens = len(re.findall(r'<d>', detail, re.I))
    closes = len(re.findall(r'</d>', detail, re.I))
    canonical = list(DIALOGUE_RE.finditer(detail))
    expected = [_speech_entry(x) for x in speech.get('utterances') or []]
    if opens == closes == len(canonical) and (speech.get('mode') != 'preserve' or
            [m.group(2).strip() for m in canonical] == [words for _, words in expected]):
        fixed, ids = normalize_speaker_ids(text, analysis)
        return fixed, 0, ids
    if (speech.get('authority') != 'user_direction' or speech.get('mode') != 'preserve'
            or not speech.get('required') or speech.get('unresolved_collective_speakers') or speech.get('unresolved_dialogue_events') or not expected):
        return text, 0, 0
    language = str(speech.get('language') or '').strip()
    if not _LANGUAGE.fullmatch(language) or language.casefold() in _UNKNOWN:
        return text, 0, 0
    sources = [_source(name, analysis) for name, _ in expected]
    if None in sources:
        return text, 0, 0
    candidates = list(_EVENT.finditer(detail))
    if sum(m['tag'] is not None for m in candidates) != opens or opens != closes:
        return text, 0, 0
    # Conservatively refuse extra quotes: they could be signs, props, or other dialogue.
    if len(candidates) != len(expected):
        return text, 0, 0
    previous = 0
    edits = []
    for m, (_, words), source in zip(candidates, expected, sources):
        actual = next((m[k] for k in ('tag','double','curly','low','single','singlecurly') if m[k] is not None), '')
        if not words or re.search(r'[<>\r\n]', words) or actual.strip() != words:
            return text, 0, 0
        lead = detail[previous:m.start()]
        previous = m.end()
        occurrences = list(re.finditer(rf'<Subject\s+{source}>', lead))
        if not occurrences or not _grounded_vocal_cue(lead, occurrences[-1], source):
            return text, 0, 0
        tail = lead[occurrences[-1].end():]
        # Do not turn reported, hypothetical, or explicitly negated speech into sound.
        if re.search(r'\b(?:not|never|without|pretends?|imagines?|considers?|plans?|about to|watches|listens)\b', tail, re.I):
            return text, 0, 0
        if m['lang'] is not None:
            if m['lang'].strip().casefold() != language.casefold():
                return text, 0, 0
            continue
        if m['tag'] is None:
            # Bare quoted words must be introduced by an actual delivery cue
            # immediately followed by a punctuation/whitespace boundary.
            if not re.search(r'(?:' + VOCAL_CUE.pattern + r')(?:\s+(?:softly|quietly|aloud|gently|warmly|slowly|firmly|urgently|in\s+' + re.escape(language) + r'))*\s*[:,]?\s*$', tail, re.I):
                return text, 0, 0
        edits.append((m.start(), m.end(), f'<d>[{language}] {words}</d>'))
    if not edits:
        return text, 0, 0
    for a,b,replacement in reversed(edits):
        detail = detail[:a] + replacement + detail[b:]
    draft = text[:start] + detail + text[end:]
    fixed, ids = normalize_speaker_ids(draft, analysis)
    mapping = {name.casefold(): source for (name, _), source in zip(expected, sources)}
    if _speech_checks(fixed, speech, mapping):
        return text, 0, 0
    return fixed, len(edits), ids
