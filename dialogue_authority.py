"""Deterministic, user-owned dialogue authority for the current Director interval.

Only explicit speaker-attributed, quoted speech in the current Direction is
extracted. Stage directions around speech do not become part of the utterance
or speaker label. The Analyst cannot delete, reorder, or rewrite these lines.
"""
import re

# Find speech introductions, not whole lines: a quotation may be preceded by
# an action or followed by more stage direction, or share a line with a reply.
from .vocal_cues import AUTHORITY_CUE

_SPEECH_INTRO = re.compile(
    AUTHORITY_CUE
    + r"(?:\s+(?:softly|quietly|gently|warmly|calmly|firmly|urgently|slowly|hesitantly|nervously|aloud|suddenly))*"
    + r"(?:\s+(?:in unison|together|simultaneously|in chorus))?"
    + r"(?:\s+in\s+(?P<language>English|German|French|Spanish|Italian|Portuguese|Dutch|Japanese|Korean|Mandarin|Chinese|Russian|Arabic|Hindi|Polish|Turkish|Swedish))?"
    + r"\s*[:,]?\s*(?P<open>[\"“„'‘])",
    flags=re.I,
)
_PAIRS = {'"': '"', '“': '”', '„': '“', "'": "'", '‘': '’'}

# Deliberately conservative action-cue list. These words separate an initial
# speaker noun phrase from staging ("Aster smiles and replies"). They are
# ordinary English actions, not character names or case-specific roles.
_ACTION_CUE = re.compile(
    r"[,\s]+(?:looks|smiles|turns|nods|glances|leans|grins|laughs|"
    r"reaches|takes|puts|holds|gives|touches|pauses|breathes|sighs|"
    r"frowns|faces|shifts|gestures|steps|walks|sits|stands|kneels|"
    r"winces|waves|blinks|look|smile|turn|nod|glance|lean|grin|laugh|"
    r"reach|take|put|hold|give|touch|pause|breathe|sigh|shift|gesture|"
    r"step|walk|sit|stand|kneel|salute|salutes|raise|raises|clink|clinks|"
    r"looking|smiling|turning|nodding|"
    r"glancing|leaning|grinning|laughing|reaching|pausing)\b"
)
_DELIVERY_ADVERB = re.compile(
    r"(?:\s+(?:softly|quietly|gently|warmly|calmly|firmly|urgently|"
    r"slowly|hesitantly|nervously|aloud|suddenly))+$", flags=re.I,
)
_SPEAKER_LABEL = re.compile(r"[\w][\w .,'’\-]{0,70}")


def _closing_quote(line, start, closer):
    """Locate the corresponding close quote without splitting contractions."""
    for pos in range(start, len(line)):
        if line[pos] != closer:
            continue
        if closer in {"'", '’'} and pos + 1 < len(line) and line[pos + 1].isalnum():
            continue  # apostrophe in 'I'm' or 'don’t', not a closing quote
        return pos
    return -1


def _speaker_from_lead(lead):
    """Keep the attributed actor, not the actor's adjacent stage directions."""
    lead = lead.lstrip(' \t.;,!?')
    # A same-line reply may begin 'and Bryn replies' after a quotation.
    lead = re.sub(r'(?i)^(?:and|then)\s+', '', lead)
    action = _ACTION_CUE.search(lead)
    if action:
        lead = lead[:action.start()]
    else:
        lead = _DELIVERY_ADVERB.sub('', lead)
    speaker = lead.strip(' \t,;')
    # Do not assign authority to unattributed narrative connectors or an
    # unresolved clause that ends in 'and' (unknown staging/action).
    if (not _SPEAKER_LABEL.fullmatch(speaker)
            or re.match(r"(?i)^(?:and|then|while|as|after|before)\b", speaker)
            or re.search(r"(?i)\band$", speaker)):
        return ''
    return speaker


def _extract_dialogue_events(direction):
    """Return speaker-prefixed verbatim quotes, or [] without attribution.

    Speech ordering and words between the user-supplied quotation marks are
    preserved. Only deterministic local attribution is accepted. Unattributed
    quoted narrative is not upgraded into user-authorized speech.
    """
    result = []
    for line in str(direction or '').splitlines():
        cursor = 0
        while intro := _SPEECH_INTRO.search(line, cursor):
            close = _closing_quote(line, intro.end(), _PAIRS[intro['open']])
            if close < 0:
                cursor = intro.end()
                continue
            speaker = _speaker_from_lead(line[cursor:intro.start()])
            words = line[intro.end():close]
            if speaker and words.strip():
                result.append((f'{speaker}: {words}', bool(re.search(
                    r'\b(?:in unison|together|simultaneously|in chorus)\b', intro.group(0), re.I)), intro.group('language')))
            cursor = close + 1
    return result


def extract_user_dialogue(direction):
    """Return verbatim speaker-prefixed dialogue, in user order."""
    return [entry for entry, _, _ in _extract_dialogue_events(direction)]


def authoritative_speech_request(direction, previous=None):
    """Build a source-of-truth contract, or None when nothing is quoted.

    Only the dialogue itself is user-owned; language can be carried over as a
    *hint* from prior analysis, because extracting language from arbitrary
    dialogue would require fallible classification.
    """
    events = _extract_dialogue_events(direction)
    utterances = [entry for entry, _, _ in events]
    if not utterances:
        return None
    previous = previous if isinstance(previous, dict) else {}
    request = {
        'mode': 'preserve',
        'required': True,
        'language': str(previous.get('language') or ''),
        'intent': 'Preserve the explicit quoted user dialogue verbatim, with speaker order unchanged.',
        'utterances': utterances,
        'authority': 'user_direction',
    }
    simultaneous = [n for n, (_, together, _) in enumerate(events, 1) if together]
    if simultaneous:
        request['simultaneous_lines'] = simultaneous
    # An explicit, consistent speech-language instruction overrides the
    # Analyst hint. Do not infer language from surrounding stage directions.
    languages = [language for _, _, language in events]
    if all(languages) and len({language.casefold() for language in languages}) == 1:
        request['language'] = languages[0].capitalize()
        request['language_authority'] = 'user_direction'
    elif any(language and language.casefold() != request['language'].casefold() for language in languages):
        # A single global hint cannot safely represent multilingual events.
        request['language'] = ''
    return request


def enforce_user_dialogue(analysis, direction):
    """Stamp user-supplied quotes over inconsistent Analyst speech_request.

    Returns the effective speech request. Does not touch Analyst planning,
    invented speech authorized by separate instructions, or shot materializations.
    """
    intent = analysis.get('intent') or {}
    if not isinstance(intent, dict):
        raise ValueError('Analysis intent must be an object')
    previous = intent.get('speech_request') or {}
    authority = authoritative_speech_request(direction, previous)
    if authority is not None:
        intent['speech_request'] = authority
        analysis['intent'] = intent
        return authority
    return previous if isinstance(previous, dict) else {}


# Collective speech is still one user-authored quotation, but each grounded
# vocal source needs its own canonical H3 event. Do not turn an arbitrary
# plural description into all available reference Subjects.
_GROUP = re.compile(
    r"^(?:the\s+)?(?:(both)(?:\s+(?:of\s+them|(?:the\s+)?(?:men|women|people|persons|characters|subjects|actors)))?"
    r"|(two|three|four|[2-4])\s+(men|women|people|persons|characters|subjects|actors))$", re.I)
_GROUP_COUNTS = {"two": 2, "three": 3, "four": 4, "2": 2, "3": 3, "4": 4}


def bind_collective_dialogue(analysis, speech):
    """Resolve explicit collective quotes against accepted person identities.

    Called after reference reconciliation, and again at validation from the
    original user direction. Ambiguous referenced groups fail closed rather
    than authorizing speech for an arbitrary bystander. No Subject is created.
    """
    if not isinstance(speech, dict) or speech.get('authority') != 'user_direction':
        return speech
    from .prompt_skill import _delivery_speaker_subject
    from .speaker_ids import _named_subjects
    # Explicit allowed_subjects (including []) is authoritative when present.
    refs = analysis.get('reference_contract') or {}
    allowed = {int(x['subject']) for x in refs.get('allowed_subjects', [])
               if isinstance(x, dict) and str(x.get('subject', '')).isdigit()}
    persons = {}
    for item in analysis.get('subjects') or []:
        if (not isinstance(item, dict) or str(item.get('kind', '')).casefold() != 'person'
                or not str(item.get('subject', '')).isdigit() or not item.get('source_pictures')):
            continue
        sid = int(item['subject'])
        if 'allowed_subjects' in refs and sid not in allowed:
            continue
        description = str(item.get('name', '')) + ' ' + str(item.get('description', ''))
        for asset in analysis.get('asset_analysis') or []:
            if isinstance(asset, dict) and asset.get('picture') in item['source_pictures']:
                description += ' ' + str(asset.get('description', '')) + ' ' + str(asset.get('label', ''))
        persons[sid] = description
    names = _named_subjects(analysis)
    intent = analysis.get('intent') or {}
    plan = str(intent.get('dialogue_plan') or '')
    synchronized = bool(re.search(r'\b(?:in unison|simultaneous(?:ly)?|synchroni[sz]ed|overlapping|together|same time)\b', plan, re.I))
    bound, unresolved = [], []
    for number, entry in enumerate(speech.get('utterances') or [], 1):
        if not isinstance(entry, str) or ':' not in entry:
            bound.append(entry)
            continue
        speaker, words = entry.split(':', 1)
        speaker, words = speaker.strip(), words.strip()
        group = _GROUP.fullmatch(speaker)
        parts = re.split(r'\s+and\s+', speaker, flags=re.I)
        if not group and len(parts) == 1:
            bound.append(entry)
            continue
        ids = []
        if group:
            count = 2 if group[1] else _GROUP_COUNTS[group[2].lower()]
            noun = (group[3] or speaker.split()[-1]).casefold()
            candidates = list(persons)
            # A gendered collective may select a subset, but only with an
            # exact count and positive descriptive evidence.
            if noun in {'men', 'women'}:
                positive = (r'\b(?:man|men|male|father|son|gentleman|boy)\b' if noun == 'men'
                            else r'\b(?:woman|women|female|mother|daughter|lady|girl)\b')
                candidates = [sid for sid in candidates if re.search(positive, persons[sid], re.I)]
            if len(candidates) == count:
                ids = sorted(candidates)
        else:
            for part in parts:
                sid = names.get(part.strip().casefold()) or _delivery_speaker_subject(part, analysis)
                if sid not in persons or sid in ids:
                    ids = []
                    break
                ids.append(sid)
        if ids:
            for sid in ids:
                bound.append({'speaker': f'<Subject {sid}>', 'text': words,
                              'shared_line': number, 'delivery': 'simultaneous' if (synchronized or number in speech.get('simultaneous_lines', [])) else 'shared'})
        else:
            bound.append(entry)  # retain verbatim words even if attribution is ambiguous
            unresolved.append(speaker)
    result = dict(speech, utterances=bound)
    if unresolved:
        result['unresolved_collective_speakers'] = unresolved
    intent['speech_request'] = result
    analysis['intent'] = intent
    return result


def normalize_shared_line_placeholder(prompt, speech, analysis):
    """Expand an explicit, unique, already staged shared-line placeholder.

    Only live single-shot drafts, only one fully grounded simultaneous user
    line, only if the real language is supplied. Do not append speech at an
    invented beat or change existing dialogue, actor order or other prose.
    """
    from .speaker_ids import _detail_span
    text = str(prompt or '')
    if (not isinstance(speech, dict) or speech.get('authority') != 'user_direction'
            or speech.get('mode') != 'preserve' or not speech.get('required')
            or speech.get('unresolved_collective_speakers')):
        return text, 0
    entries = speech.get('utterances') or []
    if len(entries) < 2 or not all(isinstance(e, dict) and e.get('shared_line') is not None
            and e.get('delivery') == 'simultaneous' for e in entries):
        return text, 0
    if any(not isinstance(e.get('text'), str) or not isinstance(e.get('shared_line'), int) for e in entries):
        return text, 0
    if len({e['shared_line'] for e in entries}) != 1 or len({e.get('text') for e in entries}) != 1:
        return text, 0
    words = entries[0].get('text')
    language = str(speech.get('language') or '').strip()
    if not isinstance(words, str) or not words.strip() or re.search(r'[<>\r\n]', words):
        return text, 0
    # Language is never inferred from the surrounding prompt's language.
    if not re.fullmatch(r'[A-Za-z][A-Za-z -]{1,30}', language) or language.casefold() in {'unknown','auto','none','unspecified','actual spoken language','language'}:
        return text, 0
    sources = [re.fullmatch(r'<Subject (\d+)>', str(e.get('speaker') or '')) for e in entries]
    if not all(sources) or len({m.group(1) for m in sources}) != len(sources):
        return text, 0
    span = _detail_span(text)
    if not span:
        return text, 0
    start, end = span
    detail = text[start:end]
    if (len(re.findall(r'\[Shot\s+\d+\]', detail, re.I)) != 1
            or re.search(r'</?d\b|\(S\d+\)', detail, re.I)):
        return text, 0
    if any(m.group(0) not in detail for m in sources):
        return text, 0
    # Do not resolve "they" when a competing visible person could own the
    # cue. The accepted subjects are authoritative, not generated pronouns.
    actor_ids = {int(m.group(1)) for m in sources}
    visible_ids = {int(x) for x in re.findall(r'<Subject (\d+)>', detail)}
    people = {int(s['subject']) for s in (analysis.get('subjects') or [])
              if isinstance(s, dict) and str(s.get('subject', '')).isdigit()
              and str(s.get('kind', '')).casefold() == 'person'}
    if not actor_ids <= people or (people & visible_ids) != actor_ids:
        return text, 0
    if words in detail or '"' in detail or '“' in detail:
        return text, 0
    # The placeholders are explicitly speech, never a generic action or
    # a summary mention. Refuse multiple candidate timing positions.
    shared = list(re.finditer(r'\b(?:they|both(?:\s+(?:men|women|people|actors|characters))?)\s+(?:deliver|speak|say|exclaim)\s+the\s+line\s+(?:simultaneously|in unison|together|in chorus)\b', detail, re.I))
    individual = [list(re.finditer(re.escape(m.group(0)) + r'\s+(?:speaks?|says?|delivers?|exclaims?)\s+the\s+line\b', detail, re.I)) for m in sources]
    if len(shared) == 1 and not any(individual):
        # Only a unique, explicit simultaneous beat. The existing sentence
        # remains intact, and its two literal events are expanded in place.
        match = shared[0]
        literal = ' and '.join(f'{m.group(0)} (S{i}) <d>[{language}] {words}</d>' for i, m in enumerate(sources, 1))
        detail = detail[:match.end()] + ' — ' + literal + ' —' + detail[match.end():]
    elif (not shared and all(len(matches) == 1 for matches in individual)
          and re.search(r"\b(?:simultaneously|in unison|in chorus|at the same time)\b", detail, re.I)):
        positions = [matches[0] for matches in individual]
        if [m.start() for m in positions] != sorted(m.start() for m in positions):
            return text, 0
        for i, match in reversed(list(enumerate(positions, 1))):
            actor = sources[i-1].group(0)
            # Retain vocal verb and subsequent performance prose.
            phrase = re.sub(r'\bthe\s+line\b$', lambda _: f'<d>[{language}] {words}</d>', match.group(0), flags=re.I)
            phrase = actor + f' (S{i})' + phrase[len(actor):]
            detail = detail[:match.start()] + phrase + detail[match.end():]
    else:
        return text, 0
    return text[:start] + detail + text[end:], len(entries)
