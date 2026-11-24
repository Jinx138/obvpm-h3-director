"""Conservative, deterministic consistency checks for image slots and actor references.

These checks never synthesize Picture labels or image descriptions. Vision output
may index a compact image list 1..N despite ComfyUI connecting Picture 3/4;
only an explicit, unique `(Picture N)` label permits moving that description.
"""
import re

_EXPLICIT_SLOT = re.compile(r"\(Picture\s+(\d+)\)\s*$", re.I)


def reconcile_asset_slots(analysis, connected_slots):
    """Retain only connected slots; fix explicitly labeled compact-index errors.

    No inferred positional mapping. If the model's label does not explicitly
    identify its intended real Picture slot, discard the orphan asset rather
    than pretending its visual observations belong to another source.
    """
    available = {int(x) for x in connected_slots}
    assets = analysis.get('asset_analysis') or []
    if not isinstance(assets, list):
        return 0
    actual = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        try:
            num = int(asset['picture'])
        except (KeyError, TypeError, ValueError):
            continue
        if num in available and num not in actual:
            actual[num] = asset
    moved = 0
    # Process only invalid-numbered entries that state their real number
    # explicitly in their own label. Do not remap just because N images arrived.
    proposals = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        try:
            num = int(asset['picture'])
        except (KeyError, TypeError, ValueError):
            continue
        if num in available:
            continue
        label = str(asset.get('label') or '').strip()
        match = _EXPLICIT_SLOT.search(label)
        if not match:
            continue
        target = int(match.group(1))
        if target not in available:
            continue
        proposals.setdefault(target, []).append(asset)

    for target, entries in proposals.items():
        if len(entries) != 1:
            continue
        src = entries[0]
        existing = actual.get(target)
        if existing is not None and str(existing.get('description') or '').strip():
            continue  # Never replace a real description already bound to the slot.
        source_role = str(src.get('primary_role') or 'unknown').casefold()
        current_role = str((existing or {}).get('primary_role') or 'unknown').casefold()
        if existing is not None and current_role not in ('', 'unknown', source_role):
            continue  # Refuse conflicting roles.
        clean_label = _EXPLICIT_SLOT.sub('', str(src.get('label') or '')).strip(' ,;:')
        if existing is None:
            existing = {'picture': target, 'primary_role': source_role,
                        'description': '', 'label': '', 'same_subject_as': None}
            actual[target] = existing
        existing['description'] = str(src.get('description') or '')
        if source_role not in ('', 'unknown'):
            existing['primary_role'] = source_role
        if clean_label:
            existing['label'] = clean_label
        moved += 1
    # Deduplicate by true connected slot, keeping the known slot's entry.
    analysis['asset_analysis'] = [actual[n] for n in sorted(actual)]
    return moved


def sanitize_actor_bindings(analysis):
    """Remove invented or non-reference-backed Subject IDs from actor tracks.

    Actor IDs remain independent of H3 <Subject N> labels. Never guess a new
    reference from prose or an actor's ordering.
    """
    reference = analysis.get('reference_contract') or {}
    valid = set()
    for entry in reference.get('allowed_subjects') or []:
        if not isinstance(entry, dict):
            continue
        try:
            n = int(entry['subject'])
        except (KeyError, ValueError, TypeError):
            continue
        if not isinstance(entry.get('source_pictures'), list) or not entry['source_pictures']:
            continue
        valid.add(n)
    corrected = 0
    for track in analysis.get('performance_tracks') or []:
        if not isinstance(track, dict):
            continue
        raw = track.get('reference_subject')
        if raw is None:
            continue
        if isinstance(raw, bool):
            normalized = None
        else:
            try:
                normalized = int(raw)
            except (ValueError, TypeError):
                normalized = None
        if normalized not in valid:
            track['reference_subject'] = None
            corrected += 1
        elif raw != normalized or type(raw) is not int:
            track['reference_subject'] = normalized
    return corrected
