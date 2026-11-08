import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from PIL import Image

SIDECAR_SUFFIX = ".mctx.safetensors"
STATE_NODE_CLASSES = {"H3DirectorShotState"}


def _specs(pin_specs):
    if isinstance(pin_specs, dict):
        return [pin_specs]
    return [spec for spec in list(pin_specs or []) if isinstance(spec, dict)]


def classify_pin_specs(pin_specs) -> Dict[str, Any]:
    """Classify OBVPM H3 pin specs as Director continuity endpoints.

    OBVPM owns the pin execution.  The Director only interprets the semantic
    relationship:
      * one ``before`` pin            -> extend / inherited start endpoint
      * one ``after`` pin             -> prepend / inherited target endpoint
      * one ``before`` + one ``after`` -> bridge / two authoritative endpoints

    Unsupported/duplicate placement specs are reported instead of guessed.
    """
    specs = _specs(pin_specs)
    before = [s for s in specs if str(s.get("place") or "").casefold() == "before"]
    after = [s for s in specs if str(s.get("place") or "").casefold() == "after"]
    other = [
        s for s in specs
        if str(s.get("place") or "").casefold() not in {"before", "after"}
    ]
    warnings = []

    if other:
        warnings.append(
            f"{len(other)} pin spec(s) use unsupported placement(s); Director only interprets before/after endpoints"
        )
    if len(before) > 1:
        warnings.append("multiple before pins supplied; Director will not guess a start endpoint")
    if len(after) > 1:
        warnings.append("multiple after pins supplied; Director will not guess a target endpoint")

    start = before[0] if len(before) == 1 else None
    target = after[0] if len(after) == 1 else None

    if start is not None and target is not None and not other and len(specs) == 2:
        operation = "bridge"
    elif start is not None and target is None and not other and len(specs) == 1:
        operation = "extend"
    elif start is None and target is not None and not other and len(specs) == 1:
        operation = "prepend"
    elif not specs:
        operation = "new"
    else:
        operation = "new"
        warnings.append("pin stack could not be mapped unambiguously to new/extend/prepend/bridge")

    return {
        "operation": operation,
        "start_spec": start,
        "target_spec": target,
        "pin_count": len(specs),
        "warnings": warnings,
    }



def _output_root():
    import folder_paths
    return os.path.abspath(folder_paths.get_output_directory())


def resolve_source_path(spec: Dict[str, Any]) -> str:
    candidate = spec.get("source_path")
    if not candidate:
        source = spec.get("source") or {}
        candidate = source.get("clip") if isinstance(source, dict) else None
    if not candidate:
        raise ValueError("continuity pin has no source_path/source.clip")

    root = _output_root()
    raw = str(candidate)
    path = os.path.abspath(raw if os.path.isabs(raw) else os.path.join(root, raw))
    try:
        inside = path != root and os.path.commonpath([root, path]) == root
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f"continuity source escapes ComfyUI output folder: {raw}")
    if not os.path.isfile(path):
        raise ValueError(f"continuity source clip does not exist: {path}")
    return path


def boundary_frame_index(spec: Dict[str, Any], role: Optional[str] = None) -> int:
    """Return the display-order frame at the generated-content seam.

    A start/before pin hands *into* generated content, so its final pinned frame
    is the authoritative start boundary.  A target/after pin is what generated
    content must hand *into*, so its first pinned frame is the authoritative
    target boundary.
    """
    if role is None:
        role = "target" if str(spec.get("place") or "").casefold() == "after" else "start"
    role = str(role).casefold()

    start = int(spec.get("source_start", 0) or 0)
    frames = int(spec.get("source_frames", 0) or 0)
    if role == "target":
        return max(0, start)
    if frames > 0:
        return max(0, start + frames - 1)

    source = spec.get("source") or {}
    meta = source.get("meta") if isinstance(source, dict) else None
    if isinstance(meta, dict):
        delivered = int(meta.get("delivered_frames", 0) or 0)
        if delivered > 0:
            return delivered - 1
    return -1


def decode_frame(path: str, frame_index: int) -> Tuple[Image.Image, int]:
    import av
    wanted = int(frame_index)
    last = None
    last_i = -1
    with av.open(path) as container:
        stream = container.streams.video[0]
        for i, frame in enumerate(container.decode(stream)):
            last = frame
            last_i = i
            if wanted >= 0 and i == wanted:
                return frame.to_image().convert("RGB"), i
    if last is None:
        raise ValueError(f"No decodable video frame in {path}")
    return last.to_image().convert("RGB"), last_i


def _sidecar_path(video_path: str) -> str:
    base, _ = os.path.splitext(video_path)
    return base + SIDECAR_SUFFIX


def _read_blob(path: str, name: str):
    from safetensors import safe_open
    with safe_open(path, framework="pt", device="cpu") as f:
        if name not in f.keys():
            return None
        raw = bytes(f.get_tensor(name).cpu().numpy().tobytes())
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _coerce_analysis(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return ""


def _state_from_node_dict(node: dict) -> Optional[dict]:
    """Read only the current materialized H3DirectorShotState contract."""
    node_type = node.get("type") or node.get("class_type")
    if node_type not in STATE_NODE_CLASSES:
        return None

    named = node.get("widgets_values_named")
    if isinstance(named, dict):
        direction = str(named.get("shot_direction") or "").strip()
        prompt = str(named.get("shot_h3_prompt") or "").strip()
        analysis = _coerce_analysis(named.get("shot_analysis"))
        if direction or prompt or analysis:
            return {
                "direction": direction,
                "h3_prompt": prompt,
                "analysis": analysis,
                "source": "workflow_shot_state_node",
            }

    values = node.get("widgets_values")
    if isinstance(values, list) and len(values) >= 4:
        # Current positional widget order: materialized, shot_direction,
        # shot_h3_prompt, shot_analysis. Linked current_* inputs are sockets.
        direction = str(values[1] or "").strip()
        prompt = str(values[2] or "").strip()
        analysis = _coerce_analysis(values[3])
        if direction or prompt or analysis:
            return {
                "direction": direction,
                "h3_prompt": prompt,
                "analysis": analysis,
                "source": "workflow_shot_state_node_positional",
            }

    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        direction = str(inputs.get("shot_direction") or "").strip()
        prompt = str(inputs.get("shot_h3_prompt") or "").strip()
        analysis = _coerce_analysis(inputs.get("shot_analysis"))
        if direction or prompt or analysis:
            return {
                "direction": direction,
                "h3_prompt": prompt,
                "analysis": analysis,
                "source": "prompt_shot_state_node",
            }
    return None


def _walk_find_state(obj) -> Optional[dict]:
    if isinstance(obj, dict):
        hit = _state_from_node_dict(obj)
        if hit:
            return hit
        # API-format prompt: {node_id: {class_type, inputs}}
        for value in obj.values():
            hit = _walk_find_state(value)
            if hit:
                return hit
    elif isinstance(obj, list):
        for value in obj:
            hit = _walk_find_state(value)
            if hit:
                return hit
    return None


def recover_director_state(video_path: str) -> dict:
    """Recover current materialized Director state from an OBVPM sidecar snapshot."""
    result = {"direction": "", "h3_prompt": "", "analysis": "", "source": "not_found"}
    sidecar = _sidecar_path(video_path)
    if not os.path.isfile(sidecar):
        result["source"] = "no_sidecar"
        return result

    for blob_name in ("workflow", "prompt"):
        try:
            obj = _read_blob(sidecar, blob_name)
        except Exception:
            continue
        hit = _walk_find_state(obj)
        if hit:
            hit["source"] = f"sidecar_blob:{blob_name}:{hit['source']}"
            return hit
    return result


def extract_subject_contract(h3_prompt: str) -> list:
    """Extract stable Subject definitions from a materialized six-section prompt.

    Extract only the stable Subject/reference portion of the materialized prompt.
    Temporal prompt prose is intentionally not exposed to later LLM passes, because
    it can cause completed action choreography to be replayed during continuation.
    """
    text = str(h3_prompt or "")
    m = re.search(
        r"subject_definitions\s*:\s*(.*?)(?=\n\s*summary\s*:|\Z)",
        text,
        flags=re.I | re.S,
    )
    if not m:
        return []

    out = []
    for raw_line in m.group(1).splitlines():
        line = raw_line.strip()
        hit = re.match(r"^<Subject\s+(\d+)>\s+is\s+(.+?)\s*$", line, flags=re.I)
        if not hit:
            continue
        subject = int(hit.group(1))
        pictures = sorted({int(x) for x in re.findall(r"<Picture\s+(\d+)>", line, flags=re.I)})
        out.append({
            "subject": subject,
            "definition": line,
            "source_pictures": pictures,
        })
    return out


def extract_scene_contract(analysis_text: str, subject_contract=None) -> dict:
    """Extract only non-temporal scene facts that are safe to inherit.

    The previous analysis contains both useful continuity facts and temporal
    choreography. Only asset/Subject records that describe environment/location
    identity are inherited here. Intent/action/camera/dialogue fields are never
    copied into this contract.
    """
    contract = {
        "subjects": list(subject_contract or []),
        "environment_references": [],
        "environment_subjects": [],
        "picture_roles": [],
    }
    raw = str(analysis_text or "").strip()
    if not raw:
        return contract
    try:
        obj = json.loads(raw)
    except Exception:
        return contract
    if not isinstance(obj, dict):
        return contract

    # Names and roles accepted in the previous generation survive as stable
    # semantic scene facts. This is NOT an event/action timeline.
    for item in ((obj.get("reference_contract") or {}).get("picture_roles") or []):
        if not isinstance(item, dict):
            continue
        try:
            pic = int(item.get("picture"))
        except (TypeError, ValueError):
            continue
        role = str(item.get("role") or "unknown")
        if role in {"character", "environment", "object", "style", "storyboard", "end_keyframe", "target_perspective"}:
            contract["picture_roles"].append({
                "picture": pic, "role": role,
                "label": str(item.get("label") or "")[:120],
                "source": str(item.get("source") or "auto"),
            })

    for item in obj.get("asset_analysis") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("primary_role") or "").casefold() != "environment":
            continue
        try:
            picture = int(item.get("picture"))
        except Exception:
            continue
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        contract["environment_references"].append({
            "picture": picture,
            "description": description,
        })

    for item in obj.get("subjects") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "").casefold() != "environment":
            continue
        try:
            subject = int(item.get("subject"))
        except Exception:
            continue
        pics = []
        for value in item.get("source_pictures") or []:
            try:
                pics.append(int(value))
            except Exception:
                pass
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        contract["environment_subjects"].append({
            "subject": subject,
            "source_pictures": sorted(set(pics)),
            "description": description,
        })

    return contract

