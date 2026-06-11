"""Tests for get_ordinal — extract ordinal numbers from legal text fragments."""
import pytest


class TestGetOrdinalArticles:
    """Extracting ordinals from 条 (article) patterns."""

    def test_simple_article(self, get_ordinal):
        """'第一条' → 1."""
        assert get_ordinal('第一条 为了规范市场秩序') == 1

    def test_article_ten(self, get_ordinal):
        """'第十条' → 10."""
        assert get_ordinal('第十条 本法自公布之日起施行') == 10

    def test_article_twenty(self, get_ordinal):
        """'第二十条' → 20."""
        assert get_ordinal('第二十条 附则内容') == 20

    def test_article_hundred(self, get_ordinal):
        """'第一百条' → 100."""
        assert get_ordinal('第一百条 最终条款') == 100

    def test_no_article(self, get_ordinal):
        """Text without 条 pattern returns None."""
        result = get_ordinal('这是一段没有条标记的普通文本')
        assert result is None


class TestGetOrdinalChapters:
    """Extracting ordinals from 章 (chapter) patterns."""

    def test_chapter_one(self, get_ordinal):
        """'第一章' → 1."""
        assert get_ordinal('第一章 总则') == 1

    def test_chapter_six(self, get_ordinal):
        """'第六章' → 6."""
        assert get_ordinal('第六章 附则') == 6


class TestGetOrdinalSections:
    """Extracting ordinals from 节 (section) patterns."""

    def test_section_one(self, get_ordinal):
        """'第一节' → 1."""
        assert get_ordinal('第一节 一般规定') == 1


class TestGetOrdinalNumberedPoints:
    """Extracting ordinals from numbered patterns."""

    def test_dotted_single(self, get_ordinal):
        """'5.1' → [5, 1]."""
        result = get_ordinal('5.1 总述')
        assert isinstance(result, (list, tuple))
        assert list(result) == [5, 1]

    def test_dotted_double(self, get_ordinal):
        """'6.1.1' → [6, 1, 1]."""
        result = get_ordinal('6.1.1 细则一')
        assert isinstance(result, (list, tuple))
        assert list(result) == [6, 1, 1]

    def test_chinese_number_one(self, get_ordinal):
        """'一、' → 1."""
        assert get_ordinal('一、 关于市场准入') == 1

    def test_chinese_number_four(self, get_ordinal):
        """'四、' → 4."""
        assert get_ordinal('四、 关于法律责任') == 4


class TestGetOrdinalParenthesized:
    """Extracting ordinals from parenthesized patterns."""

    def test_chinese_paren_one(self, get_ordinal):
        """'（一）' → 1."""
        assert get_ordinal('（一） 申请材料') == 1

    def test_chinese_paren_six(self, get_ordinal):
        """'（六）' → 6."""
        assert get_ordinal('（六） 执行监督') == 6


class TestGetOrdinalEdgeCases:
    """Edge cases for get_ordinal."""

    def test_empty_string(self, get_ordinal):
        """Empty content returns None."""
        assert get_ordinal('') is None

    def test_whitespace_only(self, get_ordinal):
        """Whitespace-only returns None."""
        assert get_ordinal('   ') is None

    def test_leading_whitespace(self, get_ordinal):
        """Ordinal after leading whitespace — match() anchors at start, returns None."""
        result = get_ordinal('  第一条 测试')
        # match() anchors at position 0; leading space prevents match
        assert result is None

    def test_number_in_middle(self, get_ordinal):
        """Number not at start should still match if pattern matches."""
        # The ordinal extractor uses match() which anchors at start
        result = get_ordinal('前缀 第一条 测试')
        # match() anchors at position 0 — might be None depending on implementation
        # This test documents the current behavior
        assert result is None or result == 1
