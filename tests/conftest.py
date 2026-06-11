"""Shared fixtures for engine tests."""
import os
import sys
import pytest

# Ensure engine/ is importable from the tests/ directory
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE = os.path.normpath(os.path.join(_HERE, '..', 'src', 'legal_text_splitter', 'engine'))
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

# Import engine modules via spec_from_file_location (matching engine's own pattern)
from importlib import util as _iu

_spec_pl = _iu.spec_from_file_location(
    'pipeline_split', os.path.join(_ENGINE, 'pipeline_split.py'))
_mod_pl = _iu.module_from_spec(_spec_pl)
_spec_pl.loader.exec_module(_mod_pl)

_spec_post = _iu.spec_from_file_location(
    '_post_split', os.path.join(_ENGINE, 'post-类型拆分.py'))
_mod_post = _iu.module_from_spec(_spec_post)
_spec_post.loader.exec_module(_mod_post)

_spec_analyze = _iu.spec_from_file_location(
    '_analyze', os.path.join(_ENGINE, 'analyze_split_types.py'))
_mod_analyze = _iu.module_from_spec(_spec_analyze)
_spec_analyze.loader.exec_module(_mod_analyze)


# ---- Expose engine functions as fixtures ----

@pytest.fixture(scope='session')
def clean_html():
    """clean_html: strip HTML tags, normalize entities, dashes, whitespace."""
    return _mod_post.clean_html


@pytest.fixture(scope='session')
def get_ordinal():
    """get_ordinal: extract ordinal number from fragment content."""
    return _mod_post.get_ordinal


@pytest.fixture(scope='session')
def process_text():
    """process_text: full engine pipeline (no DB)."""
    return _mod_pl.process_text


@pytest.fixture(scope='session')
def infer_type_levels():
    """infer_type_levels: compute type → depth mapping from fragments."""
    return _mod_pl.infer_type_levels


@pytest.fixture(scope='session')
def analyze():
    """analyze: detect split types in cleaned text."""
    return _mod_pl.analyze


@pytest.fixture(scope='session')
def type_patterns():
    """The compiled type_patterns list used by get_ordinal and split."""
    return _mod_post.type_patterns
