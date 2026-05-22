"""Thin wrapper around the engine pipeline.

Does NOT process text itself — injects raw text into the engine
and captures output at the engine's processing boundary.
"""
import sys
import os
import time

_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

_ENGINE = os.path.join(_PARENT, '拆分-打包')
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

from importlib import util as _importlib_util

_pipeline_spec = _importlib_util.spec_from_file_location(
    'pipeline_split', os.path.join(_ENGINE, 'pipeline_split.py'))
_pipeline_mod = _importlib_util.module_from_spec(_pipeline_spec)
_pipeline_spec.loader.exec_module(_pipeline_mod)

process_text = _pipeline_mod.process_text
process_single_law = _pipeline_mod.process_single_law
infer_type_levels = _pipeline_mod.infer_type_levels
get_ordinal = _pipeline_mod.get_ordinal
_get_db_connection = _pipeline_mod._get_db_connection

from analyze_split_types import _format_level_chain

MAX_FRAGMENTS = 10000


def split_text(text: str) -> dict:
    """Execute full engine pipeline on raw text.

    Injects text into the engine and captures the result at the boundary.
    The engine handles: analyze → protect → split → restore → infer levels.
    """
    t0 = time.time()

    engine_result = process_text(text)

    if engine_result["error"]:
        raise RuntimeError(engine_result["error"])

    gdata = engine_result["split_results"]
    analysis = engine_result["analysis"]
    processing_ms = int((time.time() - t0) * 1000)

    if len(gdata) > MAX_FRAGMENTS:
        raise ValueError(
            f'文本过大，片段数 {len(gdata)} 超过上限 {MAX_FRAGMENTS}，建议拆分后重试')

    # Build fragments in API format
    fragments = []
    for frag in gdata:
        fragments.append({
            'seq': len(fragments) + 1,
            'content': frag.get('content', ''),
            'split_type': frag.get('split_type'),
            'index_level': frag.get('index_level'),
            'ordinal': get_ordinal(frag.get('content', '')),
            'extra': frag.get('extra', ''),
        })

    # Build meta from analysis report
    level_chain = '-'
    level_count = 0
    all_tags = engine_result.get('split_types', [])
    if all_tags:
        type_levels = infer_type_levels(gdata)
        level_chain, level_count = _format_level_chain(type_levels)

    return {
        'fragments': fragments,
        'meta': {
            'char_count': len(text),
            'fragment_count': len(fragments),
            'spine_types': analysis.get('spine_types', []),
            'all_tags': all_tags,
            'level_chain': level_chain,
            'processing_ms': processing_ms,
            'algorithm': 'engine',
        },
    }


def split_by_ids(law_ids: list[str]) -> dict:
    """Execute engine pipeline for each law_id via process_single_law.

    Opens a DB connection, fetches raw text by law_id,
    and runs the full engine pipeline on each.
    """
    conn = _get_db_connection()
    try:
        results = []
        for law_id in law_ids:
            engine_result = process_single_law(law_id, conn, quiet=True)
            if engine_result['error']:
                results.append({
                    'law_id': law_id,
                    'fragments': [],
                    'meta': {},
                    'analysis': {},
                    'error': engine_result['error'],
                })
                continue

            gdata = engine_result['split_results']
            analysis = engine_result.get('analysis') or {}

            fragments = []
            for frag in gdata:
                fragments.append({
                    'seq': len(fragments) + 1,
                    'content': frag.get('content', ''),
                    'split_type': frag.get('split_type'),
                    'index_level': frag.get('index_level'),
                    'ordinal': get_ordinal(frag.get('content', '')),
                    'extra': frag.get('extra', ''),
                })

            level_chain = '-'
            all_tags = engine_result.get('split_types', [])
            if all_tags:
                type_levels = infer_type_levels(gdata)
                level_chain, _ = _format_level_chain(type_levels)

            results.append({
                'law_id': law_id,
                'fragments': fragments,
                'analysis': analysis,
                'meta': {
                    'char_count': analysis.get('char_count', 0),
                    'fragment_count': len(fragments),
                    'all_tags': all_tags,
                    'level_chain': level_chain,
                },
            })
        return {'results': results}
    finally:
        conn.close()
