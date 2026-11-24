"""Conservative, evidence-bound H3 syntax normalizer.

Only normalizes bare 'Picture N' mentions INSIDE the matching referenced
Subject definition. Does not add a Subject or fabricate a mapping. Never
alters a quoted dialogue segment, shot prose, or unrelated picture number.
"""
from __future__ import annotations
import re

_SUBJECT_LINE = re.compile(r'(?m)^(?P<lead>\s*<Subject\s+(?P<subject>\d+)>\s+is\s+)(?P<body>[^\n]*)$', re.I)


def normalize_reference_tokens(prompt, required_picture_bindings):
    source = str(prompt or '')
    mappings = {}
    for item in required_picture_bindings or []:
        if not isinstance(item, dict):
            continue
        try:
            pic = int(item['picture'])
        except (KeyError, ValueError, TypeError):
            continue
        for raw in item.get('subjects') or []:
            try:
                subject = int(raw)
            except (ValueError, TypeError):
                continue
            mappings.setdefault(subject, set()).add(pic)
    heading = re.search(r'(?im)^subject_definitions\s*:\s*$', source)
    next_heading = re.search(r'(?im)^summary\s*:', source[heading.end():]) if heading else None
    if not heading or not next_heading:
        return source, 0
    start = heading.end()
    end = start + next_heading.start()
    definitions = source[start:end]
    count = 0

    def sub(match):
        nonlocal count
        subject = int(match.group('subject'))
        expected = mappings.get(subject, set())
        body = match.group('body')
        # Never repair if an existing bracketed label contradicts the required
        # mapping, or if the definition contains an unknown bare Picture number.
        bracketed = {int(x) for x in re.findall(r'<Picture\s+(\d+)>', body)}
        bare = {int(x) for x in re.findall(r'(?<!<)\bPicture\s+(\d+)\b(?!>)', body, flags=re.I)}
        if (bracketed - expected) or (bare - expected):
            return match.group(0)
        for pic in sorted(expected):
            pattern = re.compile(r'(?<!<)\bPicture\s+' + str(pic) + r'\b(?!>)', re.I)
            body, n = pattern.subn(f'<Picture {pic}>', body)
            count += n
        return match.group('lead') + body

    repaired = _SUBJECT_LINE.sub(sub, definitions)
    return source[:start] + repaired + source[end:], count
