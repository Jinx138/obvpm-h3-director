"""Resolve speaker identities against the Director reference/actor contract."""
import re

def _delivery_speaker_subject(speaker: str, analysis: dict):
    """Resolve a speaker description only when ONE referenced person fits.

    Explicit names and Subject labels win. Descriptive phrases such as
    'the younger person' may match a unique visual description, but generic
    labels and tied matches remain unresolved. This is guidance to Pass #2,
    not a rewrite of its output or the Validator's safety checks.
    """
    from .speaker_ids import _named_subjects, _subject_label_candidates

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
    reference_contract = analysis.get("reference_contract") or {}
    permitted = reference_contract.get("allowed_subjects") or []
    if "allowed_subjects" in reference_contract:
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
    # An explicitly numbered user Picture is stronger than a fuzzy role name.
    # Only one accepted, non-environment Subject may own that picture.
    picture = re.search(r"\b(?:in|from)\s+<?Picture\s+(\d+)>?$", speaker, re.I)
    if picture:
        owners = {n for n, entry in subjects if str(picture[1]) in
                  {str(p) for p in entry.get("source_pictures") or []}}
        return next(iter(owners)) if len(owners) == 1 else None
    # The Analyst already identifies actors and connects them to Subjects.
    # Use exact actor IDs, never incidental words in a performance narrative.
    key = lambda value: re.sub(r"[\s_-]+", " ", str(value or "").strip().casefold())
    actor_matches = {int(t["reference_subject"]) for t in analysis.get("performance_tracks") or []
                     if isinstance(t, dict) and str(t.get("reference_subject", "")).isdigit()
                     and int(t["reference_subject"]) in allowed and t.get("actor_id")
                     and key(t["actor_id"]) == key(speaker)}
    named = _named_subjects(analysis).get(speaker.casefold())
    if named in allowed:
        actor_matches.add(named)
    if actor_matches:
        return next(iter(actor_matches)) if len(actor_matches) == 1 else None

    # Require ALL descriptive anchor words and a unique match. Common role
    # nouns and grammatical glue are not identity-discriminating anchors.
    generic = {
        "the", "a", "an", "and", "or", "in", "of", "on", "at", "to", "from",
        "with", "by", "his", "her", "their", "our", "my", "your", "this", "that",
        "man", "woman", "person", "people", "figure", "character", "subject",
        "speaker", "voice", "guy", "girl", "boy", "shirt", "jacket", "wearing",
    }
    words = lambda t: set(re.findall(r"[^\W_]+", str(t or "").casefold()))
    # In a person label, "the younger one" is an elliptical role, not an
    # identity named One. Match the age descriptor, and keep uniqueness.
    age_role = re.fullmatch(r"(?:the\s+)?(?:old|older|young|younger)\s+(?:one|man|woman|person)", speaker, re.I)
    if age_role:
        generic.add("one")
        # Identity labels are self-attributions, unlike descriptive prose
        # which can mention other actors. Canonicalize only bounded age-role
        # labels, not arbitrary words from descriptions or stage direction.
        def role_key(label):
            match = re.fullmatch(r"(?:the\s+)?(old|older|young|younger)\s+(one|man|woman|person)",
                                 re.sub(r"[_-]+", " ", label).strip(), re.I)
            if not match:
                return None
            age, kind = match.groups()
            return ({"old": "older", "young": "younger"}.get(age.casefold(), age.casefold()), kind.casefold())
        wanted_age, wanted_kind = role_key(speaker)
        explicit_roles = {}
        for label, ids in _subject_label_candidates(analysis).items():
            role = role_key(label)
            if role:
                for sid in ids & allowed:
                    explicit_roles.setdefault(sid, set()).add(role)
        matched = {sid for sid, roles in explicit_roles.items()
                   if any(age == wanted_age and (wanted_kind in {"one", "person"} or kind == wanted_kind)
                          for age, kind in roles)}
        if matched:
            if len(matched) != 1:
                return None
            sid = next(iter(matched))
            if any(age != wanted_age for age, _ in explicit_roles[sid]):
                return None  # Conflicting explicit self-labels are not evidence.
            return sid
    def age_alias(tokens):
        return {{"old": "older", "young": "younger"}.get(token, token) for token in tokens}
    anchors = words(speaker) - generic
    if age_role:
        anchors = age_alias(anchors)
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
        evidence = words(description)
        if age_role:
            evidence = age_alias(evidence)
        if anchors <= evidence:
            matches.append(number)
    return matches[0] if len(matches) == 1 else None
