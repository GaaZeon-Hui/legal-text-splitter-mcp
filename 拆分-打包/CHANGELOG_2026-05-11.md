# 项目修改日志 — 2026-05-12

> 供其他项目 agent 同步修改使用。所有路径相对于项目根目录 `C:\Users\matech\Desktop\拆分`。

---

## 零、本轮会话 — 2026-05-12

### 0.1 split_type 标注修复（post-类型拆分.py）

修复两处 `cur["split_type"]` 未赋值的 BUG（影响回卷决策）：

**瞬间 A**（split 循环 `elif` 分支）：当 `find_split_point_for_types` 因模式匹配在内容开头（position 0、`pre.strip()==""`）而返回 `None` 时，新增 `elif cur.get("split_type") is None:` 分支，用 `pat.match`（从头匹配）识别并打标。

**瞬间 B**（split 循环 `if res:` 分支）：拆分发生后 `cur["content"] = pre`，新增对 pre 是否以当前阶段模式开头的 `pat.match` 检查，匹配才设 `cur["split_type"]`。

两处判定逻辑统一：只在该行内容确实以当前 stage 的类型模式开头时打标，否则保持 `None`。

### 0.2 数字直连中文/数字空格顺序修复

在 `split_single_group_with_rollback` 的拆分循环中，数字直连中文/数字空格阶段开头增加跳过逻辑：如果当前行已经被前面阶段（数字点/数字点点/其他类型）打标，则跳过不处理。

**原因**：数字直连中文的 `\d+(?=[一-鿿])` 模式是贪婪捕获型，会匹配结构化序号（如 "2 术语和定义" 中的 "2"）中的裸数字，将已由数字点正确拆分的行再次切碎。

**改法**（post-类型拆分.py，拆分循环入口处）：
```python
if stage_type in ("数字直连中文", "数字空格") and cur.get("split_type") is not None:
    i += 1
    continue
```

**影响**：数字点/数字点点拆完的行保持完整，数字直连中文/数字空格只对未被打标的"余料"内容生效。

### 0.3 保护块：新增 4 个模式

在 `post-类型拆分.py` 和 `analyze_split_types.py` 同步新增：

| 变量名 | 正则 | 用途 |
|--------|------|------|
| `FIGURE_PATTERN` | `r'图\s*\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?'` | 图+编号，如 `图1` `图2` `图3-1` |
| `PART_X_PATTERN` | `r'\d+\s*部分'` | 数字+部分，如 `1部分` `2部分` |
| `KILOGRAM_PATTERN` | `r'\d+(?:\.\d+)?\s*千克'` | 数字+千克，如 `5千克` `10.5千克` |
| `TON_PATTERN` | `r'\d+(?:\.\d+)?\s*吨'` | 数字+吨，如 `3吨` `100吨` |

新增位置：文件顶部的图案定义区（`MIN2_PATTERN` / `MIN_PATTERN` 之后）+ 各自的替换调用（`_apply_protection_blocks` return 之前）。`_restore_placeholders` 泛匹配 `___PB_\w+_(\d+)___` 自动覆盖，无需改动。

---

## 一、analyze_split_types.py（核心分析引擎）

### 1.1 保护块：新增 10 个模式（文件顶部，约第 120-160 行）

在 `PAREN_RANGE_PATTERN` 之后新增以下模式定义：

| 变量名 | 正则 | 用途 |
|--------|------|------|
| `TABLE_X_PATTERN` | `r'(?<!\d)\d+\s*表'` | 数字+表，如 `1表` `2表` |
| `X_TABLE_PATTERN` | `r'表\s*\d+'` | 表+数字，如 `表1` `表2` |
| `TONGYI_PATTERN` | `r'统一'` | 防止 `统一、` 中 `一、` 被误识别为中文顿号 |
| `HEYI_PATTERN` | `r'合一'` | 防止 `合一、` 中 `一、` 被误识别为中文顿号 |
| `MM_PATTERN` | `r'\d+(?:\.\d+)?\s*mm'` | 数字+毫米单位，如 `5mm` `10.5mm` |

在 `SHORT_YEAR_PATTERN` 之后新增：

| 变量名 | 正则 | 用途 |
|--------|------|------|
| `YEAR_RANGE_PATTERN` | `r'(?<!\d)(?:19[7-9]\d\|20[01]\d\|202[0-7])(?!\d)'` | 1970-2027 裸年份数字 |
| `NUM_HAO_PATTERN` | `r'(?<!\d)\d+\s*号'` | x号，如 `1号` `10号` |

在 `MONTH_DAY_PATTERN` 之后新增：

| 变量名 | 正则 | 用途 |
|--------|------|------|
| `MONTH_PATTERN` | `r'(?<!\d)(?:1[0-2]\|[1-9])\s*月'` | 1-12月，如 `1月` `12月` |
| `QUARTER_PATTERN` | `r'(?<!\d)[1-4]\s*季度'` | 1-4季度，如 `1季度` `4季度` |

### 1.2 保护块：apply_protection_blocks() 新增 10 段替换逻辑

在 `apply_protection_blocks()` 函数体内，**按以下顺序**插入替换代码。

**插入点 1** — 在 `SHORT_YEAR_PATTERN` 替换之后、`PERCENT_PATTERN` 之前：

```python
    # 1970-2027 年份数字 → ___PB_YR_N___
    def _yr_repl(m):
        blocks.append(m.group(0))
        return f"___PB_YR_{len(blocks)}___"
    text = YEAR_RANGE_PATTERN.sub(_yr_repl, text)

    # x号 → ___PB_HAO_N___
    def _hao_repl(m):
        blocks.append(m.group(0))
        return f"___PB_HAO_{len(blocks)}___"
    text = NUM_HAO_PATTERN.sub(_hao_repl, text)
```

**插入点 2** — 在 `MONTH_DAY_PATTERN` 替换之后、`RANGE_PATTERN` 之前：

```python
    # 1-12月 → ___PB_MO_N___
    def _mo_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MO_{len(blocks)}___"
    text = MONTH_PATTERN.sub(_mo_repl, text)

    # 1-4季度 → ___PB_QT_N___
    def _qt_repl(m):
        blocks.append(m.group(0))
        return f"___PB_QT_{len(blocks)}___"
    text = QUARTER_PATTERN.sub(_qt_repl, text)
```

**插入点 3** — 在 `PAREN_RANGE_PATTERN` 替换之后、`return text` 之前：

```python
    # x表 → ___PB_TX_N___
    def _tx_repl(m):
        blocks.append(m.group(0))
        return f"___PB_TX_{len(blocks)}___"
    text = TABLE_X_PATTERN.sub(_tx_repl, text)

    # 表x → ___PB_XT_N___
    def _xt_repl(m):
        blocks.append(m.group(0))
        return f"___PB_XT_{len(blocks)}___"
    text = X_TABLE_PATTERN.sub(_xt_repl, text)

    # 统一 → ___PB_TY_N___
    def _ty_repl(m):
        blocks.append(m.group(0))
        return f"___PB_TY_{len(blocks)}___"
    text = TONGYI_PATTERN.sub(_ty_repl, text)

    # 合一 → ___PB_HY_N___
    def _hy_repl(m):
        blocks.append(m.group(0))
        return f"___PB_HY_{len(blocks)}___"
    text = HEYI_PATTERN.sub(_hy_repl, text)

    # 数字mm → ___PB_MM_N___
    def _mm_repl(m):
        blocks.append(m.group(0))
        return f"___PB_MM_{len(blocks)}___"
    text = MM_PATTERN.sub(_mm_repl, text)
```

### 1.3 analyze()：match 存储扩展为 4 元组

`analyze()` 函数中，match 收集从 `(text, start, val)` 改为 `(text, start, end, val)`：

```python
# 原：
matches.append((m.group(), m.start(), val))
# 改：
matches.append((m.group(), m.start(), m.end(), val))
```

entry 字典新增 `"positions"` 字段：

```python
entry = {
    "count": len(matches),
    "ordinals": [v for _, _, _, v in matches],   # 解包改为 4 元组
    "positions": [(s, e) for _, s, e, _ in matches],  # 新增
    ...
}
```

### 1.4 find_logical_groups()：内部阈值 3→2

```python
# 原：
if n >= 3 and n > best_n:
# 改：
if n >= 2 and n > best_n:
```

### 1.5 count_group_restarts()：内部阈值 3→2

```python
# 原：
if n >= 3:
    groups.append((1, n))
# 改：
if n >= 2:
    groups.append((1, n))
```

### 1.6 analyze()：新增 3 条抑制规则

在 `analyze()` 函数尾部 `return results` 之前，按顺序插入以下三段抑制逻辑。

**① 数字点/数字点点在条内抑制** — 在原有「交错抑制」之后：

```python
    # ---- 数字点/数字点点在条内抑制 ----
    # 若数字点/数字点点的大部分匹配落在条/数字条的区间内，
    # 说明它们只是条内的子编号，不应作为独立拆分类型。
    tiao_positions = []
    for tname in ["条", "数字条"]:
        tiao_positions.extend(results[tname].get("positions", []))
    if tiao_positions:
        tiao_positions.sort(key=lambda x: x[0])
        tiao_spans = []
        for i in range(len(tiao_positions) - 1):
            tiao_spans.append((tiao_positions[i][0], tiao_positions[i+1][0]))
        tiao_spans.append((tiao_positions[-1][0], len(text)))

        for check_name in ["数字点", "数字点点"]:
            entry = results.get(check_name)
            if not entry or entry["count"] == 0:
                continue
            positions = entry.get("positions", [])
            if not positions:
                continue
            inside_count = 0
            for ps, pe in positions:
                for ts, te in tiao_spans:
                    if ts <= ps < te:
                        inside_count += 1
                        break
            if inside_count > 0 and inside_count / len(positions) > 0.5:
                entry["suppressed"] = True
                entry["suppress_reason"] = "条内抑制"
```

**② 数字顿号包容抑制** — 在①之后：

```python
    # ---- 数字顿号包容抑制 ----
    dunhao_entry = results.get("数字顿号")
    if dunhao_entry and dunhao_entry["count"] > 0:
        dh_positions = dunhao_entry.get("positions", [])
        if dh_positions:
            PARENT_ORDER = ["中文顿号", "条", "括号", "数字点", "数字点点"]
            for parent_name in PARENT_ORDER:
                parent_entry = results.get(parent_name)
                if not parent_entry or parent_entry["count"] < 2:
                    continue
                parent_positions = parent_entry.get("positions", [])
                if not parent_positions:
                    continue
                parent_positions.sort(key=lambda x: x[0])
                parent_spans = []
                for i in range(len(parent_positions) - 1):
                    parent_spans.append((parent_positions[i][0], parent_positions[i+1][0]))
                parent_spans.append((parent_positions[-1][0], len(text)))

                inside_count = 0
                for ps, pe in dh_positions:
                    for ts, te in parent_spans:
                        if ts <= ps < te:
                            inside_count += 1
                            break
                if inside_count > 0 and inside_count / len(dh_positions) > 0.5:
                    dunhao_entry["suppressed"] = True
                    dunhao_entry["suppress_reason"] = f"包容抑制({parent_name})"
                    break
```

**③ 条包裹抑制** — 在②之后、`return results` 之前：

```python
    # ---- 条包裹抑制 ----
    tiao_entry = results.get("条")
    if tiao_entry and tiao_entry["count"] > 0 and tiao_entry["max_n"] <= 4:
        tiao_positions_list = tiao_entry.get("positions", [])
        if tiao_positions_list:
            PARENT_ORDER_TIAO = ["中文顿号", "括号", "数字点", "数字点点"]
            for parent_name in PARENT_ORDER_TIAO:
                parent_entry = results.get(parent_name)
                if not parent_entry or parent_entry["count"] < 2:
                    continue
                parent_positions = parent_entry.get("positions", [])
                if not parent_positions:
                    continue
                parent_positions.sort(key=lambda x: x[0])
                parent_spans = []
                for i in range(len(parent_positions) - 1):
                    parent_spans.append((parent_positions[i][0], parent_positions[i+1][0]))
                parent_spans.append((parent_positions[-1][0], len(text)))

                inside_count = 0
                for ps, pe in tiao_positions_list:
                    for ts, te in parent_spans:
                        if ts <= ps < te:
                            inside_count += 1
                            break
                if inside_count > 0 and inside_count / len(tiao_positions_list) > 0.5:
                    tiao_entry["suppressed"] = True
                    tiao_entry["suppress_reason"] = f"条包裹抑制({parent_name})"
                    break
```

### 1.7 print_report()：中文顿号放宽规则

在 qualifying 循环之后、`# ---- 定性 ----` 注释之前插入：

```python
    # 中文顿号特殊规则：max_n >= 2 即可推荐（放宽 gc/max_n 门槛）
    if "中文顿号" not in qualifying:
        e = results["中文顿号"]
        if (not e.get("suppressed", False)
            and e["count"] >= 3
            and e["max_n"] >= 2):
            qualifying["中文顿号"] = {"max_n": e["max_n"], "group_count": e["group_count"]}
```

### 1.8 print_report()：括号回退推荐位

在「规则B」括号碎片化抑制之后、「枚举型强制推荐」之前插入：

```python
    # ---- 括号回退推荐位 ----
    if "括号" in suppressed_override:
        dot_suppressed = any(
            results[t].get("suppressed", False) and results[t].get("suppress_reason") == "条内抑制"
            for t in ["数字点", "数字点点"]
        )
        if dot_suppressed:
            all_tags = sorted(set(all_tags) | {"括号"})
            suppressed_override.remove("括号")
```

### 1.9 batch_process()：同步两处逻辑

**中文顿号放宽** — 在 batch qualifying 循环之后、`if qualifying:` 之前插入：

```python
            # 中文顿号特殊规则：max_n >= 2 即可推荐
            if "中文顿号" not in qualifying:
                e = raw_results["中文顿号"]
                if (not e.get("suppressed", False)
                    and e["count"] >= 3
                    and e["max_n"] >= 2):
                    qualifying["中文顿号"] = {"max_n": e["max_n"], "group_count": e["group_count"]}
```

**括号回退** — 在 batch 的括号碎片化抑制代码块中，将原：

```python
        if "括号" in tags:
            for parent_tp in ["条", "数字条"]:
                ...
                if parent_gc > 0 and kuo_gc >= parent_gc * 3 and kuo_mn <= 4:
                    tags.remove("括号")
                    break
```

改为（增加 `kuo_suppressed` 标记和回退逻辑）：

```python
        kuo_suppressed = False
        if "括号" in tags:
            for parent_tp in ["条", "数字条"]:
                ...
                if parent_gc > 0 and kuo_gc >= parent_gc * 3 and kuo_mn <= 4:
                    tags.remove("括号")
                    kuo_suppressed = True
                    break
        # 括号回退推荐位
        if kuo_suppressed:
            dot_suppressed = any(
                raw[t].get("suppressed", False) and raw[t].get("suppress_reason") == "条内抑制"
                for t in ["数字点", "数字点点"]
            )
            if dot_suppressed:
                tags.append("括号")
                tags.sort()
```

---

## 二、post-类型拆分.py（拆分引擎 v1）

`_apply_protection_blocks()` 函数需要**完全同步** 1.1 和 1.2 的新增保护块。

### 2.1 新增模式定义（文件顶部，约第 52 行之后）

在 `PAREN_RANGE_PATTERN` 之后追加：

```python
TABLE_X_PATTERN = re.compile(r'(?<!\d)\d+\s*表')
X_TABLE_PATTERN = re.compile(r'表\s*\d+')
TONGYI_PATTERN = re.compile(r'统一')
HEYI_PATTERN = re.compile(r'合一')
MM_PATTERN = re.compile(r'\d+(?:\.\d+)?\s*mm')
```

在 `SHORT_YEAR_PATTERN` 之后追加：

```python
YEAR_RANGE_PATTERN = re.compile(r'(?<!\d)(?:19[7-9]\d|20[01]\d|202[0-7])(?!\d)')
NUM_HAO_PATTERN = re.compile(r'(?<!\d)\d+\s*号')
```

在 `MONTH_DAY_PATTERN` 之后追加：

```python
MONTH_PATTERN = re.compile(r'(?<!\d)(?:1[0-2]|[1-9])\s*月')
QUARTER_PATTERN = re.compile(r'(?<!\d)[1-4]\s*季度')
```

### 2.2 新增替换逻辑（在 _apply_protection_blocks 函数内）

三处插入点与 1.2 完全相同——在 `_sy_repl` 块之后、`_md_repl` 块之后、`_pr_repl` 块之后插入对应的替换函数。

---

## 三、post-类型拆分-v2.py（拆分引擎 v2）

与第二章完全相同的同步操作。两个文件中的 `_apply_protection_blocks()` 各自独立，需分别修改。

---

## 四、拆分策略（文档）

新增/修改以下章节：

| 章节 | 内容 |
|------|------|
| 一、保护块表 | 新增第 9a(1-12月)、9b(1-4季度)、15(x表)、16(表x)、17(统一)、18(合一)、19(数字mm)、20(年份范围)、21(x号) 行 |
| 二-B | 数字点/数字点点在条内抑制（新增章节） |
| 二-C | 数字顿号包容抑制（新增章节） |
| 二-D | 条包裹抑制（新增章节） |
| 三-A | 中文顿号放宽门槛 max_n≥2（新增小节） |
| 五、规则C | 括号回退推荐位（新增小节） |

---

## 五、修改汇总表

| 文件 | 改动项 |
|------|--------|
| `analyze_split_types.py` | 保护块模式 +10、替换逻辑 +10、match 4元组扩展、阈值 3→2 (2处)、抑制规则 +3、中文顿号放宽 (print_report + batch)、括号回退 (print_report + batch) |
| `post-类型拆分.py` | 保护块模式 +10、替换逻辑 +10 |
| `post-类型拆分-v2.py` | 保护块模式 +10、替换逻辑 +10 |
| `拆分策略` | 保护块表 +9行、新增章节 4 个、新增小节 2 个 |

---

## 六、保护块完整清单（按应用顺序）

| 序号 | 占位符 | 匹配内容 | 示例 |
|------|--------|----------|------|
| 1 | `___PB_DATE_N___` | 完整日期 | `2020年1月1日` |
| 2 | `___PB_DOC_N___` | 公文号 | `国发〔2016〕78号` |
| 3 | `___PB_PHONE_N___` | 电话号码 | `010-12345678` |
| 4 | `___PB_CONTACT_N___` | 联系方式块 | `一、联系方式...` |
| 5 | `___PB_YEAR_N___` | 裸年份+年 | `2020年` |
| 6 | `___PB_SY_N___` | 短年份(单数字+年) | `1年` `5年` |
| 7 | `___PB_YR_N___` | 1970-2027 裸年份 | `2020` `1998` |
| 8 | `___PB_HAO_N___` | x号 | `1号` `10号` |
| 9 | `___PB_PCT_N___` | 百分/千分号 | `28%` `7.5‰` |
| 10 | `___PB_FRAC_N___` | 数学分号 | `18/10万` |
| 11 | `___PB_UNIT_N___` | 数量+单位 | `10万` `50米` |
| 12 | `___PB_MD_N___` | 月日日期 | `4月30日` |
| 13 | `___PB_MO_N___` | 1-12月 | `1月` `12月` |
| 14 | `___PB_QT_N___` | 1-4季度 | `1季度` `4季度` |
| 15 | `___PB_RANGE_N___` | 数字+至 | `1至` `2至` |
| 16 | `___PB_ITEM_N___` | 数字+项 | `2项` `3项` |
| 17 | `___PB_MIN_N___` | 数字+分 | `30分` `5分` |
| 18 | `___PB_PR_N___` | 右括号+至/项 | `）至` `）项` |
| 19 | `___PB_TX_N___` | x表 | `1表` `2表` |
| 20 | `___PB_XT_N___` | 表x | `表1` `表2` |
| 21 | `___PB_TY_N___` | 统一 | `统一` |
| 22 | `___PB_HY_N___` | 合一 | `合一` |
| 23 | `___PB_MM_N___` | 数字mm | `5mm` `10.5mm` |


---

## 一、本轮会话 — 2026-05-13 · 流水线审视修复

### 1.1 score_ords.py 内嵌消除（analyze_scored.py）

`analyze_scored.py` 中 `score_ords` 模块的两个遗留导入（`parse`, `rel`）内嵌到本地，`score_ords.py` 备份为 `score_ords.bak`，全项目零引用。

**涉及文件**：`analyze_scored.py`（内嵌 `_parse_ord` + `_rel`）、`score_ords.py` → `score_ords.bak`

### 1.2 find_logical_groups 返回类型修复（analyze_split_types.py）

`find_logical_groups` 空列表早期返回 `0, 0, []`（3-tuple），正常路径返回 `int`。改为统一返回 `int`，修复 docstring。

**涉及文件**：`analyze_split_types.py:97`

### 1.3 --test 模式可达性修复（pipeline_split.py）

`--test` 分支在 if-elif-else 链之外且 preceded by `sys.exit(0)`，完全不可达。改为 `elif "--test": _run_test()`，提取 `_run_test()` 为独立函数，删除孤儿死代码块。同时清理 `else` 块中未使用的 `test_text` 变量。

**涉及文件**：`pipeline_split.py`（新增 `_run_test()` 函数；`--test` 进入 if-elif 链）

### 1.4 _run_single 去重（pipeline_split.py）

`_run_single` 与 `process_single_law` 有约 80% 重复逻辑（DB→分析→清洗→保护→拆分→还原→Excel）。重构为 `_run_single` 委托 `process_single_law(law_id, conn, quiet=False)`，仅保留终端输出和 Excel 写入。同时补齐 `_run_single` 缺失的 `infer_type_levels` 调用（原 `process_single_law` 有此步骤）。

**涉及文件**：`pipeline_split.py`（`process_single_law` 新增 `quiet=True` 参数；`_run_single` 从 70 行缩至 30 行）

### 1.5 lazy import 异常保护（post-类型拆分.py）

两处 `from analyze_scored import score_ordinals` 无 try-except。若导入失败会导致流水线中途崩溃。添加 try-except ImportError 保护，导入失败时回退为全部保留（`kept = [True] * len(ords)`），不标记任何行移除。

**涉及文件**：`post-类型拆分.py:305, 896`

---

## 二、2026-05-15 — 共享参数文件 + 代码重排 + 组标记系统

### 2.0 共享参数文件重构

| 新建文件 | 内容 |
|----------|------|
| `_protection_config.py` | 75 个保护块 pattern + `apply_protection_blocks()` + `_restore_placeholders()` |
| `_type_patterns_config.py` | 17 种拆分类型 regex/extractor + `build_type_patterns()` + `iter_matches()` + `PRE_MATCH_FILTERS` + `PATH_B_TYPES` |

### 2.1 保护块差异合并

| 分叉项 | 选定版 | 理由 |
|--------|--------|------|
| `MINUTE_PATTERN` 排除"分类" | B版`(?!类)` | 防止"分类"中的"分"被误吞 |
| `YEAR_RANGE_PATTERN` | A版 1949-2030 | 覆盖建国至今 |
| `MIN2_PATTERN`(`\d+min`) | B版 | 补全"10min"匹配 |

### 2.2 拆分类型规则差异合并

| 分叉项 | 选定版 | 说明 |
|--------|--------|------|
| 括号 | A版（全角+半角） | 匹配 `(1)` 和 `（1）` |
| 数字顿号 | A版（全角+半角） | 匹配 `1､` 和 `1、` |
| 数字条/章/节点号 | A版 `[\.．]` | 匹配 `第1．1条` |
| 数字点 `_LBR` 守卫 | B版（有守卫） | 减少括号内误报 |
| 数字点全角点 | A版 `[\.．]` | 匹配全角点版本 |
| 数字点点 `_LBR` 守卫 | B版（有守卫） | 同数字点 |
| 要素数字冒号 `_LBR` 守卫 | B版（有守卫） | 统一守卫 |
| `_dotted` 提取器 | 合并版 | A全角替换 + B空值保护 |

### 2.3 过滤机制重构

前置检查全部移至 `PRE_MATCH_FILTERS`：

| 过滤器 | 规则 |
|--------|------|
| `_bracket_filter` | 前有左括号/引号（跳过空白）→ 跳过 |
| `_jian_filter` | 前有"见" → 跳过 |
| `_tiao_prefix_filter` | 条前有"将/作为/给/的/对/按…/按《》/按xx法" → 跳过 |
| `_di_prefix_filter` | 数字直连中文/空格前有"第" → 跳过 |

后置检查保留在 extractor：后有右括号/引号、后有"条""章"。

### 2.4 匹配循环统一

`iter_matches(patterns, text, type_names=None, extra_filters=None)` — 三引擎统一使用，含可插拔过滤器机制。

### 2.5 文件重排

`analyze_split_types.py` / `post-类型拆分.py` 按区域重排：导入→配置→核心入口→辅助函数→I/O。

### 2.6 batch_process 简化

`batch_process(law_ids, output_file=None)` → 去掉自有的 qualifying 判断，改为调 `print_report(results, text, quiet=True)`。

### 2.7 组标记系统

- `compute_group_marks(ords, min_stay)` — 纯函数
- `_mark_group_types(results)` — analyze() 末尾调用
- `_absorb_marked_seqs(group_data, marked_seqs)` — 共享吸收函数
- `_path_b_secondary_rollback(...)` — 在拆分引擎的括号二次回卷之后运行
- `PATH_B_TYPES` — 常量提到 `_type_patterns_config`

### 2.8 括号抑制规则合并 + >=6 解除机制

两条抑制规则合并为统一循环，新增 `max_n >= 6` 时解除抑制的逻辑。

### 2.9 修理的 Bug

| Bug | 修复 |
|-----|------|
| `_LBR` 中 `\u898b` 应为 `\u89c1` | 繁体"見"→简体"见"，见前缀守卫恢复生效 |
| `_simulate_type_sequence` 残留 `build_all_patterns()` | 改为 `build_type_patterns()` |
| `batch_process` 和 `analyze()` 未解包 `apply_protection_blocks` 返回值 | 加 `, _` |
| `_tiao_prefix_filter` 中 `^按.+$` 应为 `^按.+法$` | 修正正则 |
| 括号回退推荐位条件笔误 | 同步修正 |

### 2.10 废弃代码清理

| 删除内容 | 涉及文件 |
|----------|----------|
| 内联保护块（75 pattern + apply + restore） | `analyze_split_types.py` / `post-类型拆分.py` |
| 内联 type patterns（17种 + build_all_patterns） | 同上 |
| `if False:` 死代码 | `analyze_split_types.py` |
| `ALL_SPLIT_TYPES` → 统一 `SPLIT_TYPES` | 全部文件 |
| 未使用导入（CN_NUM, cn2int, OrderedDict） | `analyze_split_types` / `post-类型拆分` / `analyze_scored` |
| 三处独立 LEFT_BRACKETS + 循环守卫 | 同上 |
| 过时注释 | `analyze_split_types.py` |
