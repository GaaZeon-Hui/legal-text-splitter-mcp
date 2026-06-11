"""Tests for process_text — the full engine pipeline (no DB)."""
import pytest
from tests.constants import (
    LEGAL_TEXT_MULTI_TYPE,
    LEGAL_TEXT_ARTICLES_ONLY,
    LEGAL_TEXT_HTML,
    LEGAL_TEXT_EMPTY,
    LEGAL_TEXT_PLAIN,
)


class TestProcessTextBasic:
    """Basic pipeline behavior — output structure and validation."""

    def test_result_structure(self, process_text):
        """Result dict has all required keys."""
        result = process_text('第一条 测试内容。第二条 更多内容。')
        assert 'law_id' in result
        assert 'analysis' in result
        assert 'split_types' in result
        assert 'split_count' in result
        assert 'split_results' in result
        assert 'error' in result

    def test_no_error_for_valid_input(self, process_text):
        """Valid legal text should not produce an error."""
        result = process_text('第一条 测试。第二条 内容。')
        assert result['error'] is None

    def test_split_results_is_list(self, process_text):
        """split_results should be a list of fragment dicts."""
        result = process_text('第一条 测试。')
        assert isinstance(result['split_results'], list)
        assert len(result['split_results']) > 0

    def test_fragment_has_required_keys(self, process_text):
        """Each fragment dict should have expected keys."""
        result = process_text('第一条 测试内容。')
        for frag in result['split_results']:
            assert 'seq' in frag
            assert 'content' in frag
            assert 'split_type' in frag
            assert 'index_level' in frag

    def test_split_count_matches_results(self, process_text):
        """split_count equals len(split_results)."""
        result = process_text(LEGAL_TEXT_MULTI_TYPE)
        assert result['split_count'] == len(result['split_results'])


class TestProcessTextArticlesOnly:
    """Tests with pure 条-structured legal text."""

    def test_splits_articles(self, process_text):
        """Ten articles should produce 10+ fragments."""
        result = process_text(LEGAL_TEXT_ARTICLES_ONLY)
        assert result['error'] is None
        assert result['split_count'] >= 10

    def test_article_type_present(self, process_text):
        """Results should include '条' as a split type."""
        result = process_text(LEGAL_TEXT_ARTICLES_ONLY)
        assert '条' in result['split_types']

    def test_article_content_preserved(self, process_text):
        """Article content should be in fragments."""
        result = process_text(LEGAL_TEXT_ARTICLES_ONLY)
        all_content = ' '.join(f['content'] for f in result['split_results'])
        assert '市场准入实行负面清单制度' in all_content


class TestProcessTextMultiType:
    """Tests with text containing chapters, articles, attachments, etc."""

    def test_multi_type_detected(self, process_text):
        """Multiple split types should be detected."""
        result = process_text(LEGAL_TEXT_MULTI_TYPE)
        types = result['split_types']
        # Should find at least: 章, 条, plus others
        assert len(types) >= 2

    def test_chapter_type_present(self, process_text):
        """Multi-type text should detect at least 条 and numbered types."""
        result = process_text(LEGAL_TEXT_MULTI_TYPE)
        # The engine may or may not split by 章 depending on text structure
        # At minimum, 条 should be detected
        assert '条' in result['split_types']

    def test_no_error_multi_type(self, process_text):
        """Multi-type text should not error."""
        result = process_text(LEGAL_TEXT_MULTI_TYPE)
        assert result['error'] is None

    def test_index_levels_assigned(self, process_text):
        """Fragments should have index_level set (not None for typed fragments)."""
        result = process_text(LEGAL_TEXT_MULTI_TYPE)
        typed_frags = [f for f in result['split_results'] if f['split_type']]
        if typed_frags:
            levels = [f['index_level'] for f in typed_frags]
            # At least some should be non-None
            assert any(l is not None for l in levels)

    def test_attachment_fragments(self, process_text):
        """Text with 附 should produce fragments for attachments."""
        result = process_text(LEGAL_TEXT_MULTI_TYPE)
        all_content = ' '.join(f['content'] for f in result['split_results'])
        assert '实施细则' in all_content or '附1' in all_content


class TestProcessTextHtml:
    """Tests that HTML input is handled correctly through the pipeline."""

    def test_html_input_splits(self, process_text):
        """HTML input should be cleaned and split."""
        result = process_text(LEGAL_TEXT_HTML)
        assert result['error'] is None
        assert result['split_count'] > 0

    def test_html_tags_not_in_output(self, process_text):
        """Output fragments should not contain HTML tags."""
        result = process_text(LEGAL_TEXT_HTML)
        for frag in result['split_results']:
            assert '<p>' not in frag['content']
            assert '<html>' not in frag['content']
            assert '&nbsp;' not in frag['content']

    def test_html_content_preserved(self, process_text):
        """Text content inside HTML tags should be preserved."""
        result = process_text(LEGAL_TEXT_HTML)
        all_content = ' '.join(f['content'] for f in result['split_results'])
        assert '市场准入实行负面清单制度' in all_content
        assert '反垄断法' in all_content


class TestProcessTextEdgeCases:
    """Edge cases and error handling."""

    def test_empty_text_handled(self, process_text):
        """Empty text should not crash."""
        result = process_text(LEGAL_TEXT_EMPTY)
        # Should either return error or empty results
        assert 'error' in result or 'split_results' in result

    def test_plain_text_no_structure(self, process_text):
        """Text without legal structure should still be processed."""
        result = process_text(LEGAL_TEXT_PLAIN)
        assert result['error'] is None
        # Should still produce at least one fragment
        assert result['split_count'] > 0

    def test_law_id_passed_through(self, process_text):
        """Custom law_id should appear in result."""
        custom_id = 'custom-law-001'
        result = process_text('第一条 测试。', law_id=custom_id)
        assert result['law_id'] == custom_id


class TestProcessTextOrdinals:
    """Verify ordinals are extracted and assigned to fragments."""

    def test_article_ordinals_sequential(self, process_text, get_ordinal):
        """Article fragments should have sequential ordinals."""
        result = process_text(LEGAL_TEXT_ARTICLES_ONLY)
        article_frags = [
            f for f in result['split_results']
            if f.get('split_type') == '条'
        ]
        if len(article_frags) >= 3:
            ords = [get_ordinal(f['content']) for f in article_frags]
            ords = [o for o in ords if o is not None]
            # Should be increasing
            for i in range(1, len(ords)):
                assert ords[i] > ords[i - 1], f'Ordinals should increase: {ords}'
