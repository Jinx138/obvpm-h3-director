"""Director-owned reference role interpretation and stable, editable contracts.

Only explicit Picture-number instructions are parsed deterministically. Ordinary
names and narrative referents remain semantic cues for the vision analyst, which
can check them against actual images. No guesswork about image contents here.
"""
import json
import re

VALID_ROLES = {"character", "environment", "object", "style", "storyboard", "end_keyframe", "target_perspective", "unknown"}
ROLE_WORDS = {
    "character": "character", "person": "character", "protagonist": "character",
    "subject": "character", "identity": "character", "actor": "character",
    "location": "environment", "room": "environment", "setting": "environment",
    "environment": "environment", "place": "environment",
    "prop": "object", "object": "object", "item": "object",
    "style": "style", "look": "style", "mood": "style",
    "storyboard": "storyboard", "composition": "storyboard",
    "keyframe": "end_keyframe", "end keyframe": "end_keyframe", "end frame": "end_keyframe", "last frame": "end_keyframe", "final frame": "end_keyframe",
    "target perspective": "target_perspective", "target view": "target_perspective", "target angle": "target_perspective", "target framing": "target_perspective", "target composition": "target_perspective", "end perspective": "target_perspective",
    "frame": "storyboard",
}

# Accept `Picture 1: Alex (character)`, `P2 = living room / location`,
# or `1: Alex — character`. Matching requires a slot number; generic user
# prose MUST NOT be assigned to an arbitrary picture by these heuristics.
LINE_RE = re.compile(r"^\s*(?:(?:picture|pic|p)\s*)?(\d+)\s*[:=\-–]\s*(.+?)\s*$", re.I)
INLINE_RE = re.compile(r"\b(?:picture|pic)\s*(\d+)\s*(?:[:=\-–]|\bis\b|\bshows\b|\bcontains\b)\s*([^\n.;]+)", re.I)
REVERSED_RE = re.compile(r"\b([A-Z][\w\-]*(?:\s+[A-Z][\w\-]*){0,2}?)\s+(?:is\s+in|in|from)\s+(?:picture|pic)\s*(\d+)\b", re.I)


def _slot_value(text):
    value = str(text or "").strip().strip(". ")
    if not value or value.casefold() in {"auto", "automatic", "infer", "?", "none"}:
        return None
    role = "unknown"
    m = re.search(r"\((character|person|protagonist|subject|identity|environment|location|room|setting|object|prop|style|storyboard|frame|keyframe|end keyframe|end frame|last frame|final frame|target perspective|target view|target angle|target framing|target composition|end perspective)\)\s*$", value, re.I)
    if m:
        role = ROLE_WORDS[m.group(1).casefold()]
        value = value[:m.start()].strip(" -–:|/")
    else:
        m = re.search(r"\s*(?:\||/|—|–| - )\s*(character|person|protagonist|subject|identity|environment|location|room|setting|object|prop|style|storyboard|frame|keyframe|end keyframe|end frame|last frame|final frame|target perspective|target view|target angle|target framing|target composition|end perspective)\s*$", value, re.I)
        if m:
            role = ROLE_WORDS[m.group(1).casefold()]
            value = value[:m.start()].strip(" -–:|/")
    if role == "unknown":
        for word in ("target perspective", "target view", "target angle", "target framing", "target composition", "end perspective", "final frame", "last frame", "end frame", "end keyframe", "environment", "location", "room", "setting", "character", "person", "protagonist", "prop", "object", "style", "storyboard"):
            if re.search(r"\b" + re.escape(word) + r"\b", value, re.I):
                role = ROLE_WORDS[word]
                break
    return {"role": role, "label": value[:120]}


def parse_overrides(text, picture_slots, *, direction=False):
    """Only extract explicitly numbered bindings; rejects nonexistent slots."""
    available = {int(x) for x in picture_slots}
    result = {}
    raw = str(text or "")
    for line in raw.splitlines():
        m = LINE_RE.match(line)
        if m and int(m.group(1)) in available:
            val = _slot_value(m.group(2))
            if val:
                result[str(int(m.group(1)))] = val
    if direction:
        for m in INLINE_RE.finditer(raw):
            n = int(m.group(1))
            if n in available and str(n) not in result:
                val = _slot_value(m.group(2))
                if val:
                    result[str(n)] = val
        for m in REVERSED_RE.finditer(raw):
            n = int(m.group(2))
            if n in available and str(n) not in result:
                result[str(n)] = {"role": "character", "label": m.group(1)[:120]}
    return result


def make_reference_brief(direction, roles_text, picture_slots):
    return {
        "user_overrides": parse_overrides(roles_text, picture_slots),
        "direction_bindings": parse_overrides(direction, picture_slots, direction=True),
    }


def _clean_role(value):
    v = str(value or "unknown").casefold().strip()
    if v in VALID_ROLES:
        return v
    return ROLE_WORDS.get(v, "unknown")


def resolve_reference_roles(analysis, context):
    """Merge visual analysis + text-first user hints with explicit authority.

    The analyser identifies unnumbered referents after seeing images. This
    normalization anchors its accepted mappings to the actual connected slots,
    records provenance, and deterministically applies explicit corrections.
    """
    if not isinstance(analysis, dict):
        return []
    ctx = context if isinstance(context, dict) else {}
    slots = sorted({int(x) for x in (ctx.get("picture_slots") or [])})
    brief = ctx.get("reference_roles") or {}
    direct = brief.get("direction_bindings") or {}
    overridden = brief.get("user_overrides") or {}
    existing = {}
    for item in analysis.get("asset_analysis") or []:
        if not isinstance(item, dict):
            continue
        try:
            n = int(item.get("picture"))
        except (TypeError, ValueError):
            continue
        if n in slots:
            existing[n] = item
    out = []
    for n in slots:
        asset = existing.get(n, {})
        role = _clean_role(asset.get("primary_role"))
        raw_label = str(asset.get("label") or "").strip()
        # The analyser may add a name only when grounded in the user text.
        # Free-form image captions cannot establish a person's name.
        label = raw_label if raw_label and raw_label.casefold() in str(ctx.get("direction") or "").casefold() else ""
        source = ("auto: user prompt match" if label else "auto") if role != "unknown" else "unresolved"
        claimed = direct.get(str(n))
        override = overridden.get(str(n))
        if isinstance(claimed, dict):
            label = str(claimed.get("label") or label).strip()[:120]
            role = _clean_role(claimed.get("role")) if claimed.get("role") != "unknown" else role
            source = "user prompt"
        if isinstance(override, dict):
            label = str(override.get("label") or label).strip()[:120]
            role = _clean_role(override.get("role")) if override.get("role") != "unknown" else role
            source = "user override"
        confidence = "confirmed" if source in {"user prompt", "user override"} else (
            "unresolved" if role == "unknown" else "inferred"
        )
        out.append({"picture": n, "role": role, "label": label, "source": source, "confidence": confidence})
        if n in existing:
            existing[n]["primary_role"] = role
            if label:
                existing[n]["label"] = label
        elif source != "unresolved":
            analysis.setdefault("asset_analysis", []).append({
                "picture": n, "primary_role": role, "description": "", "label": label,
                "same_subject_as": None,
            })
        # Keep stable identity names attached to the existing reference-backed
        # subject, without rewriting its visual description/appearance.
        if role == "character" and label:
            for subject in analysis.get("subjects") or []:
                if not isinstance(subject, dict):
                    continue
                if n in _as_int_set(subject.get("source_pictures") or []) and not subject.get("name"):
                    subject["name"] = label
    return out


def _as_int_set(values):
    result = set()
    for v in values:
        try:
            result.add(int(v))
        except (TypeError, ValueError):
            pass
    return result


def enrich_context(analysis_text, context_text):
    """Record resolved roles alongside frozen Pass-1 JSON without changing it."""
    try:
        ctx = json.loads(context_text)
        obj = json.loads(analysis_text)
        if isinstance(ctx, dict) and isinstance(obj, dict):
            ctx["reference_roles_resolved"] = resolve_reference_roles(obj, ctx)
            return json.dumps(ctx, ensure_ascii=False, indent=2)
    except (ValueError, TypeError):
        pass
    return str(context_text or "")


def status_summary(picture_roles):
    chunks = []
    for item in picture_roles or []:
        if not isinstance(item, dict):
            continue
        pic = item.get("picture")
        role = item.get("role") or "unknown"
        label = item.get("label") or ""
        source = item.get("source") or "auto"
        mark = "○" if role == "unknown" else ("◆" if source in {"user prompt", "user override"} else "●")
        display = label or ("Needs label" if role == "unknown" else role.title())
        chunks.append(f"{mark} P{pic} {display} [{role}; {source}]")
    return "  ·  ".join(chunks) if chunks else "○ No picture references"
