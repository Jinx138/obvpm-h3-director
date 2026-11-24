"""Deterministic reference identity reconciliation for OBVPM Director.

This module only joins picture references to already reference-backed subjects.
It never invents Subject IDs, image content, or a new identity. Explicit user
Picture roles are authoritative; ambiguous detail ownership stays unresolved.
"""
import re

_DETAIL_TERMS = re.compile(
    r"\b(?:detail|close[ -]?up|macro|insert|hands?|fingers?|fingernails?|nails?|"
    r"arms?|forearms?|eyes?|face|facial|feet|shoes?|hair|outfit|clothing|"
    r"jewell?ery|tattoo|ring|back|side[ -]?view|texture|crop|portrait|"
    r"h[aä]nde?|finger|gesicht|augen|f[uü]ße?|kleidung|schmuck|nahaufnahme|"
    r"ausschnitt)\b", re.I,
)
_PICTURE_HINT = re.compile(r"\b(?:picture|pic|bild)\s*[#:]?\s*(\d+)\b", re.I)
_SUBJECT_HINT = re.compile(r"<Subject\s+(\d+)>|\bsubject\s*[#:]?\s*(\d+)\b", re.I)
_LEADING_DETAIL = re.compile(
    r"^(?:the\s+)?(?:close[ -]?up|macro|insert|detail(?:s)?|hands?|fingers?|"
    r"fingernails?|nails?|arms?|forearms?|eyes?|face|facial|feet|shoes?|"
    r"hair|outfit|clothing|jewell?ery|tattoo|ring|back|side[ -]?view|"
    r"texture|crop|portrait|h[aä]nde?|finger|gesicht|augen|f[uü]ße?|"
    r"kleidung|schmuck|nahaufnahme|ausschnitt)\s+"
    r"(?:of|from|for|belonging\s+to|von|des|der|zu)?\s*",
    re.I,
)
_TRAILING_DETAIL = re.compile(
    r"\s+(?:'s\s+)?(?:hands?|fingers?|fingernails?|nails?|arms?|forearms?|"
    r"eyes?|face|hair|feet|shoes?|outfit|clothing|tattoo|ring|detail(?:s)?|"
    r"close[ -]?up|macro|crop|portrait|back|side[ -]?view|"
    r"h[aä]nde?|finger|gesicht|augen|f[uü]ße?|kleidung|nahaufnahme)"
    r"(?:\s+(?:close[ -]?up|detail|macro|crop|view))?\s*$", re.I,
)


def _int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _numbers(raw):
    if not isinstance(raw, (tuple, list, set)):
        return []
    return sorted({n for value in raw if (n := _int(value)) is not None})


def _norm(label):
    return re.sub(r"\s+", " ", str(label or "").strip().casefold()).strip(" .,:;-/")


def _owner_hints(label):
    """Return possible explicit owner labels from an explicitly marked detail.

    A generic 'hands close-up' is NOT proof of ownership. Names, Picture N,
    or Subject N must identify exactly one existing reference-backed subject.
    """
    label = str(label or "").strip()
    if not _DETAIL_TERMS.search(label):
        return set()
    options = {_norm(label)}
    tail = _LEADING_DETAIL.sub("", label).strip(" -—,:;/")
    if tail and tail != label:
        options.add(_norm(tail))
    trimmed = _TRAILING_DETAIL.sub("", label).strip(" -—,:;/")
    if trimmed and trimmed != label:
        options.add(_norm(trimmed))
    possessive = re.match(r"^(.+?)['’]s\s+", label, flags=re.I)
    if possessive:
        options.add(_norm(possessive.group(1)))
    return {x for x in options if x}


def reconcile_subject_references(analysis, context, picture_roles):
    """Attach additional references to existing Subjects when ownership is clear.

    In-place on analysis; invoke AFTER role resolution but BEFORE allowed_subjects
    and required_picture_bindings are assembled. Returns diagnostic strings.
    """
    slots = {_int(p) for p in (context.get("picture_slots") or [])}
    slots.discard(None)
    subjects = [x for x in (analysis.get("subjects") or []) if isinstance(x, dict)]
    roles = { _int(x.get("picture")): x for x in picture_roles if isinstance(x, dict) }
    assets = {
        _int(x.get("picture")): x
        for x in (analysis.get("asset_analysis") or []) if isinstance(x, dict)
    }
    issues = []

    def mapping():
        pic_to_subjects = {}
        subject_by_id = {}
        for subj in subjects:
            sid = _int(subj.get("subject"))
            if sid is None:
                continue
            subject_by_id[sid] = subj
            for pic in _numbers(subj.get("source_pictures")):
                if pic in slots:
                    pic_to_subjects.setdefault(pic, set()).add(sid)
        return pic_to_subjects, subject_by_id

    # Strongest evidence first: user-marked detail relationship, followed by
    # an unambiguous analyst-provided same_subject_as (Picture number).
    for pic in sorted(slots):
        role_entry = roles.get(pic) or {}
        if role_entry.get("role") != "character":
            continue
        pic_to_subjects, by_id = mapping()
        label = str(role_entry.get("label") or "")
        source = str(role_entry.get("source") or "")
        named = {}
        for subject_id, subj in by_id.items():
            labels = [subj.get("name")]
            for main_pic in _numbers(subj.get("source_pictures")):
                if main_pic == pic:
                    continue
                labels.append((roles.get(main_pic) or {}).get("label"))
                labels.append((assets.get(main_pic) or {}).get("label"))
            for name in labels:
                normalized = _norm(name)
                if normalized:
                    named.setdefault(normalized, set()).add(subject_id)

        desired = set()
        # Explicit 'hands of Picture 1' / 'detail of <Subject 3>'.
        if source in {"user override", "user prompt"} and _DETAIL_TERMS.search(label):
            for p in _PICTURE_HINT.findall(label):
                desired.update(pic_to_subjects.get(int(p), set()))
            for match in _SUBJECT_HINT.findall(label):
                sid = _int(match[0] or match[1])
                if sid in by_id:
                    desired.add(sid)
            for hint in _owner_hints(label):
                desired.update(named.get(hint, set()))
        # Explicitly repeating an already bound person's exact label is safe,
        # but a bare label from auto vision is NOT an authoritative join.
        if source in {"user override", "user prompt"} and not _DETAIL_TERMS.search(label):
            desired.update(named.get(_norm(label), set()))
        if not desired:
            prior = (assets.get(pic) or {}).get("same_subject_as")
            if isinstance(prior, str):
                hit = _PICTURE_HINT.fullmatch(prior.strip())
                prior = int(hit.group(1)) if hit else _int(prior)
            else:
                prior = _int(prior)
            if prior is not None and prior != pic:
                desired.update(pic_to_subjects.get(prior, set()))

        if len(desired) > 1:
            issues.append(f"Picture {pic}: ambiguous multi-reference owner {sorted(desired)}; no automatic merge")
            continue
        if not desired:
            continue
        owner = next(iter(desired))
        main = by_id.get(owner)
        if main is None:
            continue
        conflicting = pic_to_subjects.get(pic, set()) - {owner}
        if conflicting:
            # Drop ONLY reference-only duplicate Subjects that would become
            # source-less after moving this picture. Never rewrite a subject
            # that is backed by another unrelated image.
            unsafe = [sid for sid in conflicting if
                      len(set(_numbers(by_id[sid].get("source_pictures"))) - {pic}) > 0]
            if unsafe:
                issues.append(f"Picture {pic}: conflicting independent Subject(s) {unsafe}; kept unchanged")
                continue
            for sid in conflicting:
                duplicate = by_id[sid]
                duplicate["source_pictures"] = [p for p in _numbers(duplicate.get("source_pictures")) if p != pic]
                if duplicate in subjects and not duplicate["source_pictures"]:
                    subjects.remove(duplicate)
        main["source_pictures"] = sorted(set(_numbers(main.get("source_pictures"))) | {pic})

    # Keep the current Subject IDs and their descriptions; no new Subject is
    # invented solely from a picture-label claim. Unresolved references will
    # be surfaced by required_picture_bindings + Validator instead.
    analysis["subjects"] = subjects
    return issues
