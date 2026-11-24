"""dev10e: Narrow, deterministic H3 formatting repairs at validation delivery.

Source of truth is Director Context operation plus verified, connected Picture
bindings. These functions do not write story, change speech, invent references,
or touch materialized Editor values. The original strict Validator runs afterward.
"""
from __future__ import annotations
import re

_CANONICAL_SECTIONS = (
    'subject_definitions', 'summary', 'retention_analysis',
    'detailed_description', 'overall_soundscape', 'non_diegetic_music',
)
_HEADING = re.compile(r'(?im)^(' + '|'.join(_CANONICAL_SECTIONS) + r'):[ \t]*\r?$')
_PREFIX = re.compile(r'^\[([^\]\r\n]+)\]')
_ALLOWED_TASKS = {
    'video continuation', 'reference generation', 'keyframe completion',
    'video editing', 'audio reuse', 'audio reference',
}
_VALID_RETENTION = '(?:fully_preserved|partially_preserved|attribute_transfer|weak_reference)'
_RETENTION_SHORT = re.compile(
    rf'(?m)^(?P<indent>[ \t]*)(?P<subject><Subject\s+(?P<num>\d+)>):'
    rf'(?P<rest>[ \t]*{_VALID_RETENTION}(?:\b|\s)[^\r\n]*)$',
    re.I,
)


def _range_of_section(text, section):
    """Locate the body of a unique exact-heading section; never guess."""
    matches = list(_HEADING.finditer(text))
    current = [i for i, m in enumerate(matches) if m.group(1).lower() == section]
    if len(current) != 1:
        return None
    idx = current[0]
    if idx + 1 < len(matches):
        return matches[idx].end(), matches[idx+1].start()
    return matches[idx].end(), len(text)


def _connected_reference_guidance(picture_slots, bindings):
    try:
        connected = {int(n) for n in (picture_slots or []) if not isinstance(n, bool)}
    except (TypeError, ValueError):
        return False
    for binding in bindings or []:
        if not isinstance(binding, dict):
            continue
        try:
            picture = int(binding['picture'])
        except (KeyError, ValueError, TypeError):
            continue
        # Only current reference sources for a character, location, or object.
        # A soft target perspective or director-only START frame never qualifies.
        if picture in connected and str(binding.get('role') or '').casefold() in {
            'character', 'environment', 'object',
        }:
            return True
    return False


def normalize_continuity_task_prefix(prompt, operation, connected_picture_slots,
                                     required_picture_bindings):
    """Fix a malformed/missing continuation prefix only when op is authoritative.

    All other types present in a known bracket are retained. Never silently
    overwrite an unknown task type. Does not change new / edit / unspecified.
    """
    src = str(prompt or '')
    if str(operation or '').strip().casefold() not in {'extend', 'prepend', 'bridge'}:
        return src, 0
    span = _range_of_section(src, 'summary')
    if span is None:
        return src, 0
    start, end = span
    body = src[start:end]
    leading = re.match(r'^[ \t\r\n]*', body).group(0)
    rest = body[len(leading):]
    # A malformed initial bracket could encode other semantics; fail closed.
    if rest.startswith('[') and not _PREFIX.match(rest):
        return src, 0
    m = _PREFIX.match(rest)
    types = []
    if m:
        pieces = re.split(r'\s*\+\s*', m.group(1))
        # Accept a common malformed comma variant if EVERY term is recognized.
        if len(pieces) == 1 and ',' in pieces[0]:
            pieces = [s.strip() for s in pieces[0].split(',')]
        pieces = [s.strip().casefold() for s in pieces]
        if not pieces or any(s not in _ALLOWED_TASKS for s in pieces):
            return src, 0
        types = pieces
        rest = rest[m.end():]
    requires_reference = _connected_reference_guidance(
        connected_picture_slots, required_picture_bindings,
    )
    # Put the operation first, and required reference guidance second; preserve
    # any additional already-declared task types and their relative ordering.
    final = ['video continuation']
    if requires_reference or 'reference generation' in types:
        final.append('reference generation')
    final += [t for t in types if t not in final]
    normalized = '[' + ' + '.join(final) + ']'
    # Remove only an immediately duplicated prose keyword from the known bug:
    #   [reference generation] video continuation. [actual content]
    if re.match(r'^[ \t]*video continuation(?=\s|[.,;:]|$)', rest, re.I):
        rest = re.sub(r'^[ \t]*video continuation(?:[ \t]*[.;:])?[ \t]*', ' ', rest,
                      count=1, flags=re.I)
    if rest and not rest[0].isspace():
        rest = ' ' + rest
    candidate = leading + normalized + rest
    if candidate == body:
        return src, 0
    return src[:start] + candidate + src[end:], 1


def normalize_single_shot_retention(prompt):
    """Add the canonical appearance marker ONLY for a visibly grounded Shot 1.

    No multi-shot rewrites, no invented Subject numbers or picture references.
    Existing canonical lines remain unchanged.
    """
    src = str(prompt or '')
    retention_span = _range_of_section(src, 'retention_analysis')
    detail_span = _range_of_section(src, 'detailed_description')
    if retention_span is None or detail_span is None:
        return src, 0
    detail = src[detail_span[0]:detail_span[1]]
    shot_ids = re.findall(r'\[Shot\s+(\d+)\]', detail, re.I)
    if not shot_ids or set(shot_ids) != {'1'} or len(shot_ids) != 1:
        return src, 0
    start, end = retention_span
    segment = src[start:end]
    count = 0

    def sub(match):
        nonlocal count
        n = int(match.group('num'))
        # The visible Shot 1 needs an explicit, exact reference for this actor.
        if not re.search(r'<Subject\s+' + str(n) + r'>', detail, flags=re.I):
            return match.group(0)
        count += 1
        return (match.group('indent') + match.group('subject')
                + ' (appears in [Shot 1]):' + match.group('rest'))

    new = _RETENTION_SHORT.sub(sub, segment)
    if not count:
        return src, 0
    return src[:start] + new + src[end:], count
