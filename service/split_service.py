"""Thin wrapper around the existing analysis + split pipeline.

Exposes a single entry point split_text(text, params) -> dict
that the FastAPI endpoint calls directly.
"""
import sys
import os
import time

# Ensure parent directory is on sys.path so existing modules are importable
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from _protection_config import apply_protection_blocks, _restore_placeholders
from _type_patterns_config import build_type_patterns
from analyze_scored import analyze as analyze_scored
from analyze_split_types import analyze as analyze_legacy
from analyze_split_types import print_report, infer_type_levels

# post-类型拆分 uses Chinese filename — import via importlib
from importlib import util as _importlib_util
_post_spec = _importlib_util.spec_from_file_location(
    'post_split', os.path.join(_PARENT, 'post-类型拆分.py'))
_post_mod = _importlib_util.module_from_spec(_post_spec)
_post_spec.loader.exec_module(_post_mod)

clean_html = _post_mod.clean_html
split_plain_by_paragraphs = _post_mod.split_plain_by_paragraphs
split_single_group_with_rollback = _post_mod.split_single_group_with_rollback

# Also need _format_level_chain (defined in analyze_split_types, not exported)
from analyze_split_types import _format_level_chain


_ORDINAL_PATTERN_CACHE = {}

def _extract_ordinal(content, split_type):
    """Extract the ordinal value from a fragment's content based on its split_type.

    Patterns are cached per split_type to avoid rebuilding compiled regex for
    every fragment in large documents (the caller loops over all fragments).
    """
    if not split_type:
        return None
    try:
        if split_type not in _ORDINAL_PATTERN_CACHE:
            _ORDINAL_PATTERN_CACHE[split_type] = build_type_patterns([split_type])
        patterns = _ORDINAL_PATTERN_CACHE[split_type]
        for name, pat, func in patterns:
            m = pat.match(content)
            if m:
                val = func(m)
                if val is not None:
                    return val
        return None
    except (AttributeError, TypeError):
        return None


MAX_FRAGMENTS = 10000


def split_text(text: str, params: dict | None = None) -> dict:
    """Execute full analysis + split pipeline.

    Args:
        text: Raw legal document text (may contain HTML).
        params: Optional algorithm parameters:
            - algorithm: 'scored' (default) | 'legacy'
            - split_types: None (auto-detect) | ['条', '章', ...]
            - min_fragment_chars: 10 (default)

    Returns:
        dict with 'fragments' (list) and 'meta' (dict).
    """
    if params is None:
        params = {}

    algorithm = params.get('algorithm', 'scored')
    split_types_override = params.get('split_types')
    # min_fragment_chars is reserved for future use

    # 1. Clean HTML
    cleaned = clean_html(text)

    # 2. Apply protection blocks
    protected, blocks = apply_protection_blocks(cleaned)

    # 3. Analyze
    if algorithm == 'scored':
        report = analyze_scored(protected)
    else:
        raw_results = analyze_legacy(protected)
        report = print_report(raw_results, protected, quiet=True)

    all_tags = report.get('all_tags', [])
    is_plain = report.get('is_plain', False)

    # Override split types if specified
    if split_types_override is not None:
        all_tags = split_types_override
        is_plain = False

    # 4. Split
    t0 = time.time()

    if is_plain or not all_tags or all_tags == ['纯文本']:
        gdata = [{
            'group': 'input', 'seq': 1,
            'content': protected, 'extra': None,
            'source_id': 0, 'split_type': None,
        }]
    elif '纯文本段落拆分' in all_tags:
        paragraphs = split_plain_by_paragraphs(protected)
        gdata = []
        for i, p in enumerate(paragraphs):
            gdata.append({
                'group': 'input', 'seq': i + 1,
                'content': p, 'extra': None,
                'source_id': 0, 'split_type': None,
            })
        other_types = [t for t in all_tags if t != '纯文本段落拆分']
        if other_types:
            gdata = split_single_group_with_rollback(
                gdata, 'input', split_types_override=other_types, verbose=False)
    else:
        gdata = [{
            'group': 'input', 'seq': 1,
            'content': protected, 'extra': None,
            'source_id': 0, 'split_type': None,
        }]
        gdata = split_single_group_with_rollback(
            gdata, 'input', split_types_override=all_tags, verbose=False)

    processing_ms = int((time.time() - t0) * 1000)

    # 5. Check fragment count
    if len(gdata) > MAX_FRAGMENTS:
        raise ValueError(
            f'文本过大，片段数 {len(gdata)} 超过上限 {MAX_FRAGMENTS}，建议拆分后重试')

    # 6. Restore protection block placeholders
    for frag in gdata:
        frag['content'] = _restore_placeholders(frag['content'], blocks)

    # 7. Infer type index levels
    type_levels = infer_type_levels(gdata)

    # 8. Build fragment list
    fragments = []
    for frag in gdata:
        st = frag.get('split_type')
        ordinal = _extract_ordinal(frag['content'], st)
        fragments.append({
            'seq': len(fragments) + 1,
            'content': frag['content'],
            'split_type': st,
            'index_level': type_levels.get(st),
            'ordinal': ordinal,
        })

    # 9. Build meta
    chain_str, _ = _format_level_chain(type_levels)

    return {
        'fragments': fragments,
        'meta': {
            'char_count': len(text),
            'fragment_count': len(fragments),
            'spine_types': report.get('spine_types', []),
            'all_tags': all_tags,
            'level_chain': chain_str,
            'processing_ms': processing_ms,
            'algorithm': algorithm,
        },
    }
