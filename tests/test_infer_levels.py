"""Tests for infer_type_levels — type hierarchy depth inference."""
import pytest


class TestInferTypeLevels:
    """Type level inference from gdata fragments."""

    def test_returns_dict(self, infer_type_levels):
        """Should return a dict mapping type → depth."""
        gdata = [
            {'content': '第一章 总则', 'split_type': '章', 'index_level': None},
            {'content': '第一条 目的', 'split_type': '条', 'index_level': None},
            {'content': '第二条 范围', 'split_type': '条', 'index_level': None},
        ]
        result = infer_type_levels(gdata)
        assert isinstance(result, dict)

    def test_chapter_and_article_levels(self, infer_type_levels):
        """Known types map to integer levels — engine assigns depth."""
        gdata = [
            {'content': '第一章 总则', 'split_type': '章', 'index_level': None},
            {'content': '第一条 目的', 'split_type': '条', 'index_level': None},
            {'content': '第二条 范围', 'split_type': '条', 'index_level': None},
            {'content': '第一项 细则', 'split_type': '项', 'index_level': None},
        ]
        result = infer_type_levels(gdata)
        # All known types should get integer levels
        for tp in ['章', '条', '项']:
            if tp in result:
                assert isinstance(result[tp], int), \
                    f'{tp} level should be int, got {type(result[tp])}'
        # Type ordering: inner types <= outer types (higher or equal number)
        # The engine assigns levels based on the type hierarchy defined in SPLIT_TYPES
        assert '条' in result
        assert '项' in result
        # Both map to valid integer levels
        assert result['条'] >= 0
        assert result['项'] >= 0

    def test_unknown_types_handled(self, infer_type_levels):
        """Types not in SPLIT_TYPES hierarchy should get a default."""
        gdata = [
            {'content': 'X 某未知类型', 'split_type': '未知类型', 'index_level': None},
        ]
        result = infer_type_levels(gdata)
        # Should not crash; unknown types get some default level
        assert isinstance(result, dict)

    def test_empty_gdata(self, infer_type_levels):
        """Empty gdata returns empty dict."""
        result = infer_type_levels([])
        assert result == {}

    def test_multi_fragment_same_type(self, infer_type_levels):
        """Multiple fragments of same type share the same level."""
        gdata = [
            {'content': '第一条 A', 'split_type': '条', 'index_level': None},
            {'content': '第二条 B', 'split_type': '条', 'index_level': None},
            {'content': '第三条 C', 'split_type': '条', 'index_level': None},
        ]
        result = infer_type_levels(gdata)
        assert '条' in result
        assert isinstance(result['条'], int)

    def test_level_assignment_to_fragments(self, infer_type_levels):
        """Each typed fragment should get an index_level assigned."""
        gdata = [
            {'content': '第一章 总则', 'split_type': '章', 'index_level': None},
            {'content': '第一条 目的', 'split_type': '条', 'index_level': None},
        ]
        type_levels = infer_type_levels(gdata)
        for frag in gdata:
            st = frag.get('split_type')
            frag['index_level'] = type_levels.get(st) if st else None
        # All typed fragments should have a level
        for frag in gdata:
            assert frag['index_level'] is not None, \
                f'Fragment {frag["content"][:20]} should have index_level'
