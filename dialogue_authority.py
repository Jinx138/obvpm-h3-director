"""Deterministic, user-owned dialogue authority for the current Director interval.

Only explicit speaker-attributed, quoted speech in the current Direction is
extracted. Stage directions around speech do not become part of the utterance
or speaker label. The Analyst cannot delete, reorder, or rewrite these lines.
"""
import re

# Find speech introductions, not whole lines: a quotation may be preceded by
# an action or followed by more stage direction, or share a line with a reply.
_SPEECH_INTRO = re.compile(
    r"\b(?:says?|said|asks?|asked|replies|reply|replied|responds?|responded|"
    r"answers?|answered|whispers?|whispered|shouts?|shouted|murmurs?|murmured)"
    r"\s*[:,]?\s*(?P<open>[\"“„'‘])",
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
    r"winces|waves|blinks|looking|smiling|turning|nodding|"
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


def extract_user_dialogue(direction):
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
                result.append(f'{speaker}: {words}')
            cursor = close + 1
    return result


def authoritative_speech_request(direction, previous=None):
    """Build a source-of-truth contract, or None when nothing is quoted.

    Only the dialogue itself is user-owned; language can be carried over as a
    *hint* from prior analysis, because extracting language from arbitrary
    dialogue would require fallible classification.
    """
    utterances = extract_user_dialogue(direction)
    if not utterances:
        return None
    previous = previous if isinstance(previous, dict) else {}
    return {
        'mode': 'preserve',
        'required': True,
        'language': str(previous.get('language') or ''),
        'intent': 'Preserve the explicit quoted user dialogue verbatim, with speaker order unchanged.',
        'utterances': utterances,
        'authority': 'user_direction',
    }


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
