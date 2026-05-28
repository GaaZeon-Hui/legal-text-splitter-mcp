# 恢复丢失修改 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement inline.

**Goal:** 恢复被 git 回退丢失的 6 项引擎修改，逐条修复并同步 4 份副本。

**Architecture:** 每条改动涉及 1-2 个文件，全部 × 4 副本同步。编辑时小心 `_type_patterns_config.py` 中 `\uXXXX` 转义与真中文混存的编码问题。

---

### Task 1: 数字直连中文 `[一-鿿]` → `[一-鿿A-Z]`

**Files:** `_type_patterns_config.py` (4 副本)

- [ ] 在 `_build_type_patterns_cached` 中数字直连中文的 `_digit_pat` 行，把 `[一-鿿]` 换成 `[一-鿿A-Z]`。
- [ ] 同步 4 副本，验证。

---

### Task 2: `LEFT_BRACKETS` 加 `、，`

**Files:** `_type_patterns_config.py` (4 副本)

- [ ] 在 `LEFT_BRACKETS = set(...)` 行末尾 `')` 前插入 `、，` 两个字符。
- [ ] 同步 4 副本，验证 `_bracket_filter` 能拦截左侧有 `、` `，` 的匹配。

---

### Task 3: `_post_match_guard` 加数字点、数字点点

**Files:** `_type_patterns_config.py` (4 副本)

- [ ] `_post_match_guard` 的类型检查行当前为 `if name not in ("数字空格", "数字直连中文"):`
- [ ] 改为 `if name not in ("数字点", "数字点点", "数字直连中文"):`（删除数字空格引用，添加数字点、数字点点）。
- [ ] 同步 4 副本。

---

### Task 4: 条内抑制前置条件 `max_n >= 3`

**Files:** `analyze_split_types.py` (4 副本)

- [ ] 在 `数字点/数字点点在条内抑制` 段落开头，`tiao_positions = []` 之前插入 `tiao_has_spine` 检查。
- [ ] 仅当 `条` 或 `数字条` 的 `max_n >= 3` 时才收集 tiao_positions 用于条内抑制。
- [ ] 同步 4 副本。

---

### Task 5: 数字直连中文无门槛补加 `_dot_only`

**Files:** `analyze_split_types.py` (4 副本)

- [ ] 在 `枚举型强制推荐` 之后、`_p(f"\n  >>> 推荐拆分类型: {all_tags}")` 之前插入数字直连中文补加逻辑。
- [ ] 逻辑：当推荐类型仅限于数字点/数字点点时，数字直连中文 count>0 就无门槛加入 all_tags。
- [ ] 同步 4 副本。

---

### Task 6: 位置 0 split_type 补标

**Files:** `post-类型拆分.py` (4 副本)

- [ ] 在 `split_single_group_with_rollback` 的拆分循环中，`i += 1` 之前加入位置 0 匹配补标逻辑。
- [ ] 当 `find_split_point_for_types` 返回后，检查当前片段内容开头是否匹配当前阶段类型，是则补标 split_type。
- [ ] 同步 4 副本。

---

### 自审

所有改动均验证 4 副本一致，每条改完立即汇报进度。
