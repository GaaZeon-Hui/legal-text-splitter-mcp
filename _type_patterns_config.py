"""
共享拆分类型模式配置 — 供分析引擎和拆分引擎统一调用。

包含中文数字转换、左括号守卫、类型→模式映射工厂函数。
两边各自维护的 build_all_patterns() 和 type_patterns 已合并至此。
"""
from functools import lru_cache
import re

# ==================== 中文数字 ====================
CN_NUM = r"[零一二三四五六七八九十百千万]+"

# 左括号/引号环绕守卫已移至 PRE_MATCH_FILTERS（_bracket_filter），此处清空
_LBR = ""

@lru_cache(maxsize=256)
def cn2int(chn: str) -> int:
    """中文数字字符串 → 整数。"""
    chn = chn.strip().replace('〇', '零')
    if not chn:
        return 0
    num_map = {'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,
               '十':10,'百':100,'千':1000,'万':10000}
    total = section = digit = 0
    for char in chn:
        if char == '万':
            total += (section + digit) * 10000
            section = digit = 0
        elif char == '千':
            section += (digit if digit > 0 else 1) * 1000
            digit = 0
        elif char == '百':
            section += (digit if digit > 0 else 1) * 100
            digit = 0
        elif char == '十':
            section += (digit if digit > 0 else 1) * 10
            digit = 0
        elif char == '零':
            pass
        else:
            digit = num_map.get(char, 0)
    total += section + digit
    return total




# ==================== Helper 工厂函数 ====================

def _cn_pat(pat_template, name):
    """中文序数：如 第一条 → 1。pat_template 中用 {cn} 占位。"""
    pat = _LBR + pat_template.format(cn=f"({CN_NUM})")
    return (name, re.compile(pat), lambda m: cn2int(m.group(1)))

def _digit_pat(pat_str, name):
    """阿拉伯数字：如 1、2 → 1。"""
    return (name, re.compile(_LBR + pat_str), lambda m: int(m.group(1)))

def _dotted_pat(pat_str, name):
    """点号层级：如 1.1 → (1,1)，支持全角点．"""
    pat = _LBR + pat_str
    return (name, re.compile(pat), lambda m: (
        tuple(int(x) for x in m.group(1).replace('．', '.').split('.'))
        if ('.' in m.group(1) or '．' in m.group(1))
        else int(m.group(1))
    ))


# ==================== 类型 → 模式映射 ====================

@lru_cache(maxsize=None)
def _build_type_patterns_cached(types_tuple):
    """
    缓存版核心逻辑 — 入参为 tuple（hashable）。
    types_tuple: 类型名称元组，如 ("条", "章", "节", …)
    """
    results = []
    _LBRACK = set('\u2018\u201c\u300c\u300e\u300a\u3008\uff08[(\u3014\uff62')
    _RBRACK = set('\u2019\u201d\u300d\u300f\u300b\u3009\uff09])\u3015\uff63')
    for t in types_tuple:
        if t == "条":
            results.append(_cn_pat("第{cn}条", "条"))
            _base_tp = results[-1]
            def _tiao_ext(m, _base=_base_tp):
                return _base[2](m)
            results[-1] = (_base_tp[0], _base_tp[1], _tiao_ext)
        elif t == "章":
            results.append(_cn_pat("第{cn}章", "章"))
        elif t == "节":
            results.append(_cn_pat("第{cn}节", "节"))
        elif t == "编":
            results.append(_cn_pat("第{cn}编", "编"))
        elif t == "部分":
            results.append(_cn_pat("第{cn}部分", "部分"))
        elif t == "括号":
            pat = _LBR + r"[（(](\d+|" + CN_NUM + r")[）)]"
            results.append(("括号", re.compile(pat),
                            lambda m: int(m.group(1)) if m.group(1).isdigit()
                            else cn2int(m.group(1))))
        elif t == "中文顿号":
            pat = _LBR + r"(?<!第)(" + CN_NUM + r")[、､](?!第)"
            results.append(("中文顿号", re.compile(pat), lambda m: cn2int(m.group(1))))
        elif t == "数字顿号":
            results.append(_digit_pat(r"(\d+)[、､]", "数字顿号"))
        elif t == "数字空格":
            results.append(_digit_pat(r"(?<![.\d])(\d+)(?!\.\d)[\u3000 ]+", "数字空格"))
            _base_tp = results[-1]
            def _sk_ext(m, _base=_base_tp):
                # \u53f3\u4fa7\u9644\u8fd1\u6709\u53f3\u62ec\u53f7/\u5f15\u53f7\u65f6\u4e0d\u8bc6\u522b
                if m.end() < len(m.string):
                    after = m.string[m.end():].lstrip()[:6]
                    if any(c in _RBRACK for c in after):
                        return None
                # \u540e\u6709\u6761/\u7ae0
                if m.end() < len(m.string):
                    after = m.string[m.end():].lstrip()
                    if after.startswith(("\u6761", "\u7ae0")):
                        return None
                return _base[2](m)
            results[-1] = (_base_tp[0], _base_tp[1], _sk_ext)
        elif t == "数字条":
            results.append(_dotted_pat(r"第(\d+(?:[\.．]\d+)*)条", "数字条"))
        elif t == "数字章":
            results.append(_dotted_pat(r"第(\d+(?:[\.．]\d+)*)章", "数字章"))
        elif t == "数字节":
            results.append(_dotted_pat(r"第(\d+(?:[\.．]\d+)*)节", "数字节"))
        elif t == "数字点":
            pat = _LBR + r"(\d+(?:[\.．]\d+)+)(?!\s*[)\uff09\]\u301d\uff5d\u300d\u300f\u203a\u00bb\u300d])(?=\s|[一-鿿]|[（(《〈\u2018\u201c\u300c\u300e]|$)"
            results.append(("数字点", re.compile(pat),
                            lambda m: tuple(int(x) for x in m.group(1).replace('．', '.').split('.'))
                            if ('.' in m.group(1) or '．' in m.group(1)) else int(m.group(1))))
        elif t == "数字点点":
            pat = _LBR + r"(\d+(?:[\.．]\d+)*)[\.．](?!\s*[)\uff09\]\u301d\uff5d\u300d\u300f\u203a\u00bb\u300d])(?=\s|[一-鿿]|[（(《〈\u2018\u201c\u300c\u300e]|$)"
            results.append(("数字点点", re.compile(pat),
                            lambda m: tuple(int(x) for x in m.group(1).replace('．', '.').split('.'))
                            if ('.' in m.group(1) or '．' in m.group(1)) else int(m.group(1))))
        elif t == "数字直连中文":
            results.append(_digit_pat(r"(?<![.\d])(\d+)(?!\.\d)[\u3000 ]?(?=[一-鿿])", "数字直连中文"))
            _base_tp = results[-1]
            def _szlz_ext(m, _base=_base_tp):
                # \u53f3\u4fa7\u9644\u8fd1\u6709\u53f3\u62ec\u53f7/\u5f15\u53f7\u65f6\u4e0d\u8bc6\u522b
                if m.end() < len(m.string):
                    after = m.string[m.end():].lstrip()[:6]
                    if any(c in _RBRACK for c in after):
                        return None
                # \u540e\u6709\u6761/\u7ae0
                if m.end() < len(m.string):
                    after = m.string[m.end():].lstrip()
                    if after.startswith(("\u6761", "\u7ae0")):
                        return None
                return _base[2](m)
            results[-1] = (_base_tp[0], _base_tp[1], _szlz_ext)
        elif t == "中文是":
            results.append(_cn_pat("{cn}是", "中文是"))
        elif t == "要素数字冒号":
            pat = _LBR + r"要素(\d+)[：:]"
            results.append(("要素数字冒号", re.compile(pat), lambda m: int(m.group(1))))
    return results


def build_type_patterns(types_list):
    """
    根据类型名列表生成 [(name, compiled_pat, extractor), ...]。

    入参接受 list 或 tuple，内部通过 tuple 缓存避免重复编译。
    """
    return list(_build_type_patterns_cached(tuple(types_list)))

# ==================== 共享匹配循环 + 可插拔过滤器 ====================
# iter_matches 遍历 pattern 匹配结果，通过 PRE_MATCH_FILTERS 做前置过滤。
# 新增过滤器只需写一个 filter(name, m) → True(跳过) 的函数，加到 PRE_MATCH_FILTERS。

LEFT_BRACKETS = set('\u2018\u201c\u300c\u300e\u300a\u3008\uff08[(\u3014\uff62')
SKIP_DANZI = set('过见')
SKIP_CIYU = {'超过', '至少'}

def _skip_danzi(name, m):
    """跳过前面（允许空白）有指定单字符集合中字符的匹配。"""
    if m.start() == 0:
        return False
    j = m.start() - 1
    while j >= 0 and m.string[j] in " \t\n\r\u3000\u00a0":
        j -= 1
    return j >= 0 and m.string[j] in SKIP_DANZI
def _skip_ciyu(name, m):
    """跳过前面有指定词语（超过/至少，允许跳过空白）的匹配。"""
    if m.start() > 0:
        # 从匹配位置前一个字符开始向左跳过空白
        j = m.start() - 1
        while j >= 0 and m.string[j] in " \t\n\r\u3000\u00a0":
            j -= 1
        
        # 检查前几个字符是否构成 SKIP_WORDS 中的词语
        for word in SKIP_CIYU:
            word_len = len(word)
            if j >= word_len - 1:   # 确保有足够字符
                # 提取从 j-word_len+1 到 j 的片段（因为 j 指向词语的最后一个字符）
                start_idx = j - word_len + 1
                if m.string[start_idx:j+1] == word:
                    return True
    return False
def _bracket_filter(name, m):
    """\u8df3\u8fc7\u524d\u6709\u5de6\u62ec\u53f7/\u5f15\u53f7\uff08\u8df3\u8fc7\u7a7a\u767d\uff09\u7684\u5339\u914d\u3002"""
    if m.start() > 0:
        j = m.start() - 1
        while j >= 0 and m.string[j] in " \t\n\r\u3000\u00a0":
            j -= 1
        if j >= 0 and m.string[j] in LEFT_BRACKETS:
            return True
    return False


def _tiao_prefix_filter(name, m):
    """\u8df3\u8fc7\u6761\u524d\u6709\u7279\u5b9a\u4e2d\u6587\u7684\u8bef\u5339\u914d\u3002"""
    if name not in ("\u6761", "\u6570\u5b57\u6761"):
        return False
    pre = m.string[:m.start()].rstrip()
    if pre.endswith(("\u5c06","\u4f5c\u4e3a","\u7ed9","\u7684","\u5bf9","\u6309","\u6309\u89c4\u5b9a","\u6309\u89c4\u8303","\u6309\u6807\u51c6","\u6309\u51c6\u5219","\u6309\u8981\u6c42","\u6309\u6cd5\u89c4","\u6309\u89c4\u7ae0","\u6309\u6761\u4f8b")):
        return True
    import re as _re
    if _re.search(r'^\u6309.+\u6cd5$', pre):
        return True
    if ('\u6309\u300a' in pre and pre.endswith('\u300b')) or ('\u6309\uff08' in pre and pre.endswith('\uff09')):
        return True
    return False

def _di_prefix_filter(name, m):
    """\u8df3\u8fc7\u6570\u5b57\u76f4\u8fde\u4e2d\u6587/\u6570\u5b57\u7a7a\u683c\u524d\u6709\u7b2c\u7684\u5339\u914d\u3002"""
    if name not in ("\u6570\u5b57\u76f4\u8fde\u4e2d\u6587", "\u6570\u5b57\u7a7a\u683c", "\u4e2d\u6587\u987f\u53f7"):
        return False
    if m.start() > 0:
        j = m.start() - 1
        while j >= 0 and m.string[j] in " \t\n\r\u3000\u00a0":
            j -= 1
        if j >= 0 and m.string[j] == '\u7b2c':
            return True
    return False

# \u524d\u7f6e\u8fc7\u6ee4\u5668\u5217\u8868\uff1a\u6bcf\u4e2a filter(name, m) \u2192 True \u8868\u793a\u8df3\u8fc7\u8be5\u5339\u914d
PRE_MATCH_FILTERS = [
    _bracket_filter,
    _skip_danzi,
    _skip_ciyu,
    _tiao_prefix_filter,
    _di_prefix_filter,
]

def iter_matches(patterns, text, type_names=None, extra_filters=None):
    """
    遍历 pattern 匹配，应用前置过滤器后 yield。

    patterns: [(name, compiled_pat, extractor), ...]
    text: 被搜索文本
    type_names: 可选，只处理指定类型
    extra_filters: 可选，额外过滤器列表（临时追加，不修改 PRE_MATCH_FILTERS）
    yield: (name, pat, func, match_object)
    """
    filters = PRE_MATCH_FILTERS + (extra_filters or [])
    for name, pat, func in patterns:
        if type_names is not None and name not in type_names:
            continue
        for m in pat.finditer(text):
            if any(f(name, m) for f in filters):
                continue
            yield name, pat, func, m
