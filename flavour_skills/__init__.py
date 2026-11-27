"""Select staged system skills and render external request templates."""
import hashlib
import json
from pathlib import Path

FLAVOUR_SCHEMA = 'obvpm.director.flavour'
FLAVOUR_VERSION = 1
GENRES = ('auto', 'contemporary', 'science_fiction', 'fantasy')
STYLES = ('general', 'drama_emotional', 'action_kinetic', 'casual_comedy',
          'dreamlike', 'adult_nsfw')
PERFORMANCE = ('adaptive', 'restrained', 'expressive')
INTIMACY_TONES = ('adaptive', 'tender', 'playful', 'passionate')
SKILL_PACK_VERSION = '0.6.6-creative-fidelity'
_DIR = Path(__file__).resolve().parent


def make_profile(genre, directing_style, performance='adaptive',
                 intimacy_tone='adaptive', flavour_notes=''):
    profile = {
        'schema': FLAVOUR_SCHEMA,
        'schema_version': FLAVOUR_VERSION,
        'genre': str(genre),
        'directing_style': str(directing_style),
        'performance': str(performance),
        'intimacy_tone': str(intimacy_tone),
        'flavour_notes': str(flavour_notes or '').strip(),
    }
    if profile['genre'] not in GENRES:
        raise ValueError(f"Unknown Director genre: {profile['genre']!r}")
    if profile['directing_style'] not in STYLES:
        raise ValueError(f"Unknown Director directing style: {profile['directing_style']!r}")
    if profile['performance'] not in PERFORMANCE:
        raise ValueError(f"Unknown performance setting: {profile['performance']!r}")
    if profile['intimacy_tone'] not in INTIMACY_TONES:
        raise ValueError(f"Unknown intimacy tone: {profile['intimacy_tone']!r}")
    if len(profile['flavour_notes']) > 2000:
        raise ValueError('Flavour notes must be 2000 characters or fewer.')
    return profile


def parse_profile(raw):
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError('Director Flavour input is not valid JSON.') from exc
    if not isinstance(obj, dict) or obj.get('schema') != FLAVOUR_SCHEMA:
        raise ValueError('Director Flavour requires a connected H3 Director Flavour node.')
    if obj.get('schema_version') != FLAVOUR_VERSION:
        raise ValueError('Director Flavour schema version mismatch.')
    return make_profile(
        obj.get('genre'), obj.get('directing_style'),
        obj.get('performance', 'adaptive'), obj.get('intimacy_tone', 'adaptive'),
        obj.get('flavour_notes', ''),
    )


def _read(relative):
    path = _DIR / relative
    if not path.is_file():
        raise FileNotFoundError(f'Missing Director skill: {path}')
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        raise ValueError(f'Empty Director skill: {path}')
    return text


def render_template(name, **values):
    """Render a repository-owned template; inserted values are never reparsed."""
    return (_DIR / 'templates' / f'{name}.txt').read_text(encoding='utf-8').format(**values)


def render_message(group, key, **values):
    messages = json.loads((_DIR / 'templates' / f'{group}.json').read_text(encoding='utf-8'))
    return messages[key].format(**values)


def template_manifest(stage, operation='new'):
    """Hash the selected request template sources, separately from system text."""
    continuity = operation in ('extend', 'prepend', 'bridge')
    names = [f'templates/{stage}_{"continuity" if continuity else "new"}.txt', 'templates/shared.json']
    if stage == 'analyst':
        names.append('templates/reference_role_prepass.txt')
    else:
        names.append('templates/delivery.json')
    if continuity:
        names.append(f'templates/{stage}.json')
    entries = [{ 'name': name, 'sha256': hashlib.sha256((_DIR / name).read_bytes()).hexdigest()} for name in names]
    return {'sha256': hashlib.sha256(json.dumps(entries, sort_keys=True).encode('utf-8')).hexdigest(), 'modules': entries}


def _sections(profile, stage, operation='new'):
    profile = parse_profile(profile)
    if stage not in ('analyst', 'composer'):
        raise ValueError(f'Unknown Director pass {stage!r}')
    operation = str(operation or 'new').casefold()
    if operation not in ('new', 'extend', 'prepend', 'bridge', 'continue', 'edit', 'unspecified'):
        raise ValueError(f'Unknown Director operation {operation!r}')
    parts = [
        (f'system_{stage}.txt', _read(f'system_{stage}.txt')),
        (f'core_{stage}.txt', _read(f'core_{stage}.txt')),
        (f'genres/{profile["genre"]}_{stage}.txt',
         _read(f'genres/{profile["genre"]}_{stage}.txt')),
        (f'styles/{profile["directing_style"]}_{stage}.txt',
         _read(f'styles/{profile["directing_style"]}_{stage}.txt')),
    ]
    if operation in ('extend', 'prepend', 'bridge'):
        parts.append((f'continuity_{stage}.txt', _read(f'continuity_{stage}.txt')))
    if stage == 'composer':
        parts.insert(1, ('dialogue/composer.txt', _read('dialogue/composer.txt')))
    perf = profile['performance']
    if perf != 'adaptive':
        relative = f'performance/{perf}.txt'
        parts.append((relative, _read(relative)))
    if profile['directing_style'] == 'adult_nsfw' and profile['intimacy_tone'] != 'adaptive':
        relative = f'tones/{profile["intimacy_tone"]}.txt'
        parts.append((relative, _read(relative)))
    if profile['flavour_notes']:
        parts.append(('flavour_notes', render_template('flavour_notes', notes=profile['flavour_notes'])))
    return parts


def compose_system(profile, stage, operation='new'):
    """Return JUST the selected staged system prompt; no legacy base."""
    return '\n\n'.join(content for _, content in _sections(profile, stage, operation))


def manifest(profile, stage, operation='new'):
    """Selected base system and template provenance (not final dynamic payload/token count)."""
    selected = _sections(profile, stage, operation)
    payload = '\n\n'.join(content for _, content in selected)
    return {
        'architecture': 'external-skill-templates-v1',
        'skill_pack_version': SKILL_PACK_VERSION,
        'stage': stage,
        'operation': str(operation or 'new').casefold(),
        'sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest(),
        'chars': len(payload),
        'words': len(payload.split()),
        'modules': [{'name': name, 'chars': len(content)} for name, content in selected],
        'request_templates': template_manifest(stage, str(operation or 'new').casefold()),
    }
