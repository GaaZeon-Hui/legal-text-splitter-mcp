# 文书类型拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增"文书类型"拆分类型，识别法规中的《规划》《规定》《意见》《通知》，并在已有守卫规则体系下正常工作。

**Architecture:** 在现有引擎四文件（`_type_patterns_config.py`、`analyze_split_types.py`、`post-类型拆分.py`、`pipeline_split.py`）中加新类型，不修改通用逻辑（`is_plain_text` 保持原样，通用过滤器全保留）。新增 `_genju_guard` 通用过滤器拦截"根据"前缀。所有改动 × 4 份副本同步。

**Tech Stack:** Python 3.12, 现有引擎管线

---

## 文件结构

| 文件 | 职责 | 改动 |
|------|------|------|
| `_type_patterns_config.py` | 模式定义 + 过滤器 | 加文书类型 pattern、`_genju_guard`、`，。`到 `_RGUARD_RBRACK`、文书类型进 `_post_match_guard` |
| `analyze_split_types.py` | SPLIT_TYPES + 分析 + 入围规则 | 加类型到列表、`group_count=count`、≥3 入围 |
| `post-类型拆分.py` | 拆分执行 + 回卷 | 加类型到列表、跳过回卷 |
| `pipeline_split.py` | 管线编排 | `clean_html` 提前到 `analyze` 前 |
| `packaging/` | 桌面版打包 | 不动（已有） |
| `app/` | UI 层 | 不动（已有） |

---

### Task 1: `_type_patterns_config.py` — 加文书类型模式

**Files:**
- Modify: `_type_patterns_config.py` (顶层 + 拆分-打包 + MCP src + MCP dist 共 4 份副本)

- [ ] **Step 1: 在 `_build_type_patterns_cached` 中 数字直连中文 分支后插入文书类型**

找到 `elif t == "数字直连中文":` 分支末尾（`results.append(_digit_pat(...))` 那一行），在其后、`elif t == "中文是":` 之前插入：

```python
        elif t == "文书类型":
            _wslx_seq = [0]
            def _wslx_ext(m, _seq=_wslx_seq):
                _seq[0] += 1
                return _seq[0]
            results.append(("文书类型", re.compile(_LBR + r"《(规划|规定|意见|通知)》"), _wslx_ext))
```

- [ ] **Step 2: 验证模式可编译**

```bash
python -c "from _type_patterns_config import build_type_patterns; pts=build_type_patterns(['文书类型']); print(len(pts), pts[0][0])"
```
Expected: `1 文书类型`

- [ ] **Step 3: Commit**

```bash
git add _type_patterns_config.py
git commit -m "feat: add 文书类型 pattern to _type_patterns_config"
```

---

### Task 2: `_type_patterns_config.py` — 加 `_genju_guard` 过滤器

**Files:**
- Modify: `_type_patterns_config.py` (4 份副本)

- [ ] **Step 1: 在 `_post_match_guard` 返回 `False` 之后、`PRE_MATCH_FILTERS` 之前插入函数**

```python
def _genju_guard(name, m):
    """跳过左侧紧邻'根据'的匹配（跳过空白）。"""
    if m.start() > 0:
        j = m.start() - 1
        while j >= 0 and m.string[j] in " \t\n\r　 ":
            j -= 1
        if j >= 1 and m.string[j-1:j+1] == "根据":
            return True
    return False
```

- [ ] **Step 2: 注册到 PRE_MATCH_FILTERS，放在最前面**

```
PRE_MATCH_FILTERS = [
    _genju_guard,          ← 新增
    _bracket_filter,
    _skip_danzi,
    ...
]
```

- [ ] **Step 3: 验证过滤器生效**

```python
import re
from _type_patterns_config import PRE_MATCH_FILTERS
m = next(re.finditer(r'《通知》', '根据《通知》要求'))
for f in PRE_MATCH_FILTERS:
    if f('文书类型', m):
        print(f'{f.__name__} filtered')
```
Expected: `_genju_guard filtered`

- [ ] **Step 4: Commit**

```bash
git add _type_patterns_config.py
git commit -m "feat: add _genju_guard filter for 根据 prefix"
```

---

### Task 3: `_type_patterns_config.py` — 文书类型加入右守卫 + `，。`

**Files:**
- Modify: `_type_patterns_config.py` (4 份副本)

- [ ] **Step 1: 文书类型加入 `_post_match_guard` 类型检查**

```
if name not in ("数字点", "数字点点", "数字直连中文"):
```
改为：
```
if name not in ("数字点", "数字点点", "数字直连中文", "文书类型"):
```

- [ ] **Step 2: `_RGUARD_RBRACK` 加 `，。`**

```
_RGUARD_RBRACK = set(''”」』》〉）)]〕｣')
```
改为：
```
_RGUARD_RBRACK = set(''”」』》〉）)]〕｣，。')
```

- [ ] **Step 3: Commit**

```bash
git add _type_patterns_config.py
git commit -m "feat: add 文书类型 to _post_match_guard, add ，。to _RGUARD_RBRACK"
```

---

### Task 4: `analyze_split_types.py` — 加入 SPLIT_TYPES + 组数处理 + 入围规则

**Files:**
- Modify: `analyze_split_types.py` (4 份副本)

- [ ] **Step 1: SPLIT_TYPES 加 "文书类型"**

在 `"数字点", "数字点点", "数字直连中文",` 后、`"中文是", "要素数字冒号",` 前插入：
```python
    "文书类型",
```

- [ ] **Step 2: `analyze()` 中给文书类型设 `group_count = count`**

在 `entry["scalar_groups"] = groups_detail` 之后、`# 元组序数分析` 之前插入：

```python
        # 文书类型特殊处理：无序数特征，每个出现即一组
        if name == "文书类型" and entry["count"] > 0:
            entry["group_count"] = entry["count"]
```

- [ ] **Step 3: `print_report()` 中加入围规则**

在 中文顿号 特殊规则之后、`# ---- 定性 ----` 之前插入：

```python
    # 文书类型特殊规则：≥3 个即推荐，count 即组数
    e_wslx = results.get("文书类型")
    if e_wslx and not e_wslx.get("suppressed", False) and e_wslx["count"] >= 3:
        qualifying["文书类型"] = {"max_n": 0, "group_count": e_wslx["count"]}
```

- [ ] **Step 4: 不动 `is_plain_text`** — 保持原始逻辑

- [ ] **Step 5: 验证**

```bash
python -c "
from analyze_split_types import SPLIT_TYPES
print('文书类型' in SPLIT_TYPES)
"
```
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add analyze_split_types.py
git commit -m "feat: add 文书类型 to analyze with group_count and qualifying rule"
```

---

### Task 5: `post-类型拆分.py` — 加入 SPLIT_TYPES + 跳过回卷

**Files:**
- Modify: `post-类型拆分.py` (4 份副本)

- [ ] **Step 1: SPLIT_TYPES 加 "文书类型"**（同 Task 4 Step 1）

- [ ] **Step 2: `global_backward_rollback` 跳过文书类型**

```python
    for tp in split_type_order:
        if tp in SCORED_TYPES:
```
改为：
```python
    for tp in split_type_order:
        if tp in SCORED_TYPES or tp == "文书类型":
```

- [ ] **Step 3: Commit**

```bash
git add post-类型拆分.py
git commit -m "feat: add 文书类型 to post-类型拆分, skip rollback"
```

---

### Task 6: `pipeline_split.py` — `clean_html` 提前

**Files:**
- Modify: `pipeline_split.py` (4 份副本)

- [ ] **Step 1: `process_text` 中清洗提到分析前**

```python
    # 改前
    raw_results = analyze(raw_text)
    ...
    cleaned_text = clean_html(raw_text)
    
    # 改后
    cleaned_text = clean_html(raw_text)
    raw_results = analyze(cleaned_text)
    ...
    # 后续 clean_html 调用删除，直接用 cleaned_text
```

精确替换：将 `# 1. 分析拆分类型` 到 `# 2. 清洗 + 保护 + 拆分` 这一段重新编排。

- [ ] **Step 2: 验证**

```bash
python -c "
from pipeline_split import process_text
r = process_text('《规划》第一章 《规定》第二条 《意见》第三条', law_id='test', quiet=True)
print(r['split_types'])
"
```
Expected: 包含 `文书类型`

- [ ] **Step 3: Commit**

```bash
git add pipeline_split.py
git commit -m "fix: run clean_html before analyze for better pattern matching"
```

---

### Task 7: 全量同步到 4 份副本 + 最终验证

- [ ] **Step 1: 同步文件**

```bash
python -c "
import shutil
src = r'D:\2026_File\2026May\UI SETTING'
dst = [r'...拆分-打包', r'...mcp\src\...\engine', r'...mcp\dist\...\engine']
for f in ['_type_patterns_config.py','analyze_split_types.py','post-类型拆分.py','pipeline_split.py']:
    for d in dst:
        shutil.copy2(f'{src}/{f}', f'{d}/{f}')
print('synced')
"
```

- [ ] **Step 2: 全量验证 — d5bc3be1 测试**

用 `d5bc3be1` 验证完整管线：
```python
r = process_text(text, law_id='d5bc3be1', quiet=True)
assert r['split_types'] == ['文书类型']
assert r['split_count'] == 7  # 1 preamble + 6 《规定》
```

- [ ] **Step 3: 全量验证 — 保护块测试**

验证"根据《规定》"被 `_genju_guard` 拦截、`《规定》）` 被 `_post_match_guard` 拦截、`。 《规定》` 正常存活。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: sync 文书类型 changes to all copies"
```

---

## 自审

**1. Spec 覆盖:** 每个需求都有对应 Task — 模式定义(T1)、`_genju_guard`(T2)、右守卫+逗句号(T3)、分析+入围(T4)、拆分+回卷(T5)、管线顺序(T6)、同步(T7)。

**2. 无占位符:** 所有步骤含完整代码。

**3. 类型一致性:** `entry["group_count"] = entry["count"]` 在 T4 设，T4 入围规则用 `e_wslx["count"]`，一致。
