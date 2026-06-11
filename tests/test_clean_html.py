"""Tests for clean_html — HTML tag stripping, entity decoding, dash normalization."""
import pytest
import sys
import os

# conftest.py handles engine setup; import the test constants
from tests.constants import (
    LEGAL_TEXT_HTML,
    LEGAL_TEXT_DASH_ORDINALS,
)


class TestCleanHtmlBasic:
    """Basic HTML cleaning — tags, entities, whitespace."""

    def test_strips_html_tags(self, clean_html):
        """All HTML tags should be removed."""
        result = clean_html('<p>第一条 测试内容。</p>')
        assert '<p>' not in result
        assert '</p>' not in result
        assert result == '第一条 测试内容。'

    def test_decodes_nbsp(self, clean_html):
        """&nbsp; becomes a regular space."""
        result = clean_html('第一条&nbsp;测试&nbsp;内容')
        assert '&nbsp;' not in result
        assert '第一条 测试 内容' in result

    def test_decodes_amp(self, clean_html):
        """&amp; becomes &."""
        result = clean_html('A &amp; B')
        assert '&amp;' not in result
        assert 'A & B' in result

    def test_decodes_lt_gt(self, clean_html):
        """&lt; and &gt; become < and >."""
        result = clean_html('X &lt; Y &gt; Z')
        assert '&lt;' not in result
        assert '&gt;' not in result
        assert 'X < Y > Z' in result

    def test_full_html_document(self, clean_html):
        """Full HTML document should yield clean text."""
        result = clean_html(LEGAL_TEXT_HTML)
        assert '<html>' not in result
        assert '<body>' not in result
        assert '<p>' not in result
        assert '&nbsp;' not in result
        assert '&lt;' not in result
        assert '反垄断法' in result

    def test_normalizes_whitespace(self, clean_html):
        """Multiple spaces/newlines collapse to single space."""
        result = clean_html('第一条  多个空格\n\n换行\t\t制表符')
        assert '   ' not in result
        assert '\n\n' not in result
        assert '\t\t' not in result

    def test_strips_leading_trailing_space(self, clean_html):
        """Leading and trailing whitespace stripped."""
        result = clean_html('  第一条 测试  ')
        assert result == '第一条 测试'


class TestCleanHtmlDashNormalization:
    """Dash ordinal normalization — database convention fix."""

    # Chinese em-dash patterns
    @pytest.mark.parametrize('input_text,expected', [
        ('-、 经营许可', '一、 经营许可'),
        ('—、 监督管理', '一、 监督管理'),
        ('（-） 申请材料', '（一） 申请材料'),
        ('（—） 审批流程', '（一） 审批流程'),
        ('(-) 公示信息', '(一) 公示信息'),
        ('(—) 复议程序', '(一) 复议程序'),
    ])
    def test_dash_to_one(self, clean_html, input_text, expected):
        """Dash ordinals (-、, —、, （-）, etc.) become 一、 patterns."""
        result = clean_html(input_text)
        assert expected in result

    def test_full_dash_text(self, clean_html):
        """Complete dash ordinal text should be fully normalized."""
        result = clean_html(LEGAL_TEXT_DASH_ORDINALS)
        # All dash variants should be gone
        assert '-、' not in result
        assert '—、' not in result
        assert '（-）' not in result
        assert '（—）' not in result
        assert '(-)' not in result
        assert '(—)' not in result
        # Should have normalized versions
        assert '一、' in result
        assert '（一）' in result
        assert '(一)' in result

    def test_normal_dash_not_affected(self, clean_html):
        """Regular hyphens in text should NOT be normalised."""
        result = clean_html('合同双方——甲方和乙方——应遵守本协议')
        # Text-level em dashes between words should remain
        assert '甲方' in result
        assert '乙方' in result
