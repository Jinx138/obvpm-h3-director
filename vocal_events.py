"""Normalize bounded, user-authorized H3 vocal events as a transaction.

Never invent speech, replace changed wording, move a beat or guess a source.
The legacy marker-only path remains available for already canonical events.
"""
import re
from .speaker_ids import (_detail_span, _speech_entry,
                          _grounded_vocal_cue, normalize_speaker_ids)
from .validator import DIALOGUE_RE, _speech_checks
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
    from .prompt_skill import _delivery_speaker_subject
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
            or not speech.get('required') or speech.get('unresolved_collective_speakers') or not expected):
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
