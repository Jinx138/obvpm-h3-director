"""Explicit neutral Flavour fixture for pre-v0.6.4 contract tests."""
NEUTRAL_FLAVOUR = {'schema': 'obvpm.director.flavour', 'schema_version': 1, 'genre': 'auto', 'directing_style': 'general', 'performance': 'adaptive', 'intimacy_tone': 'adaptive', 'flavour_notes': ''}

import importlib.util
from pathlib import Path
_spec = importlib.util.spec_from_file_location('director_test_flavour', Path(__file__).resolve().parents[1]/'flavour_skills'/'__init__.py')
_skills = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_skills)

def neutral_manifests(operation='new'):
    return {stage: _skills.manifest(NEUTRAL_FLAVOUR, stage, operation) for stage in ('analyst','composer')}
