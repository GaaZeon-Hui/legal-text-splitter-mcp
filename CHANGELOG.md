# 法规文本拆分系统 — 维护文档

> 最后更新：2026-05-18

---

## 1. 项目文件地图

```
UI SETTING/
│
├── ═══════════════ 入口 & 启动 ═══════════════
│
├── launch.py                    ← 一键启动（双击/命令行）─ 自动启服务 → 等就绪 → 开 UI
├── run_service.py               ← 单独启动 FastAPI 服务 :8001
├── run_ui.py                    ← 单独启动 NiceGUI UI :8080
│
├── ═══════════════ UI 前端 app/ ═══════════════
│
├── app/
│   ├── main.py                  ← NiceGUI 入口：路由注册 / + /results，静态文件挂载
│   ├── pages/
│   │   ├── index.py             ← 主页：上传+编辑+参数+拆分按钮+健康轮询
│   │   └── results.py           ← 结果页：摘要栏+表格+导出
│   └── components/
│       ├── service_client.py    ← HTTP 客户端：调 /health 和 /api/split
│       ├── file_upload.py       ← 上传组件：解析 txt/docx/xlsx + 列选择 + 覆盖确认
│       └── aggrid_table.py      ← [备用] AG Grid 表格组件（当前版本未使用）
│
├── ═══════════════ 服务端 service/ ═══════════════
│
├── service/
│   ├── main.py                  ← FastAPI 服务入口：GET /health, POST /api/split
│   └── split_service.py         ← 编排层：调用引擎 → 组装 JSON → 唯一的外部适配层
│
├── ═══════════════ 核心引擎（不可修改） ═══════════════
│
├── analyze_scored.py            ← 打分式拆分类型分析（默认算法）
├── analyze_split_types.py       ← 规则式拆分类型分析（legacy 算法）
├── post-类型拆分.py             ← 拆分执行引擎（切分+回卷+过渡切分）
├── _protection_config.py        ← 保护块：日期/电话/公文号→占位符
├── _type_patterns_config.py     ← 类型模式：中文数字转换+正则工厂+匹配迭代
├── pipeline_split.py            ← [保留] 原 DB→Excel 批处理流水线（UI 未用）
│
├── ═══════════════ 静态资源 static/ ═══════════════
│
├── static/
│   ├── table-renderer.js        ← 结果表格 JS 渲染器（pretext + fallback）
│   ├── pretext-layout.js        ← pretext 主模块（文本测量）
│   ├── pretext-rich-inline.js   ← pretext 富文本模块
│   ├── analysis.js              ← pretext 依赖
│   ├── bidi.js                  ← pretext 依赖（双向文本）
│   ├── line-break.js            ← pretext 依赖（换行）
│   ├── line-text.js             ← pretext 依赖（行文本）
│   ├── measurement.js           ← pretext 依赖（测量）
│   └── generated/
│       └── bidi-data.js         ← pretext 生成数据
│
├── ═══════════════ 文档 ═══════════════
│
├── CHANGELOG.md                 ← 本文件：维护文档
├── docs/superpowers/specs/2026-05-15-split-ui-design.md  ← 设计文档
├── docs/superpowers/plans/2026-05-15-split-ui-plan.md    ← 实现计划
├── NICEGUI.md                   ← NiceGUI 框架参考
│
├── ═══════════════ 废弃 ═══════════════
│
└── UI.py.bak                    ← 旧占位文件
```

---

## 2. 接口合约

### 2.A 外部合约：不能动

#### `split_service.py → 结果页`

split_service.py 的 `split_text()` 返回给外部的 JSON 结构是**唯一不可变的合约**。结果页和导出功能都依赖它。

```
split_text(text, params) -> dict
{
    "fragments": [
        {
            "seq":         int,          ← 片段序号（1-based）
            "content":     str,          ← 片段完整文本
            "split_type":  str|null,     ← 拆分类型：条/章/节/编/括号/数字点/…
            "index_level": int|null,     ← 层级深度（差分权重法推断，0=最外层）
            "ordinal":     int|[int]     ← 序数：标量如 3，点号如 [6,1,1]
        },
        ...
    ],
    "meta": {
        "char_count":     int,           ← 原文字符数
        "fragment_count": int,           ← 片段总数
        "spine_types":    [str],         ← 脊椎类型列表（如 ["条"]）
        "all_tags":       [str],         ← 所有检测到的拆分类型
        "level_chain":    str,           ← 层级链（如 "章→条"）
        "processing_ms":  int,           ← 处理耗时（毫秒）
        "algorithm":      str,           ← 使用的算法（"scored" | "legacy"）
    }
}
```

**依赖此合约的文件：**
- `app/pages/results.py` — `_build_pretext_table()` 和 `_do_export()` 都读这个结构
- `static/table-renderer.js` — `ROWS` 和 `DETAIL` 从这个结构生成

#### HTTP API 合约：不能动

```
GET /health
→ 200 {"status": "ok", "version": "1.0.0"}

POST /api/split
← {"text": "…", "params": {"algorithm": "scored", "split_types": null, "min_fragment_chars": 10}}
→ 200 {fragments, meta}
→ 422 {"detail": "…"}            ← 空文本或超10000片段
→ 500 {"detail": "处理失败: …"}    ← 意外错误
```

**依赖此合约的文件：**
- `app/components/service_client.py` — `ServiceClient.split()` / `health()`
- `launch.py` — 启动前轮询 `/health`
- `app/pages/index.py` — 健康检查定时器调 `svc.health()`

---

### 2.B 内部合约：可以改，改完同步 split_service.py

#### `analyze() → dict`（分析报告）

**调用方：** `service/split_service.py`  
**提供方：** `analyze_scored.py`（默认）或 `analyze_split_types.py`（legacy）

```
analyze(text: str) -> dict
{
    "all_tags":         [str],   ← 推荐的所有拆分类型
    "spine_types":      [str],   ← 脊椎类型（序列最长、最可靠）
    "satellite_types":  [str],   ← 附生类型
    "is_plain":         bool,    ← 未检测到任何类型时为 True
    "max_n":            int,     ← 最大连续递增长度
    "max_gc":           int,     ← 最大组数
}
```

#### `split_single_group_with_rollback() → [gdata]`（拆分执行）

**调用方：** `service/split_service.py`  
**提供方：** `post-类型拆分.py`

```
split_single_group_with_rollback(
    group_data: [dict],               ← 输入片段列表
    group_name: str,                  ← 组名（"input"）
    split_types_override: [str]|None, ← 用哪些类型切分
    verbose: bool                     ← 是否打印日志
) -> [dict]                           ← 输出片段列表

gdata 结构（每个片段）:
{
    "group":      str,            ← 组名
    "seq":        int,            ← 序号（在过程中会重新编号）
    "content":    str,            ← 片段文本
    "extra":      str|null,       ← 回卷标记（如 "回卷5;括回7"）
    "source_id":  int,            ← 来源索引
    "split_type": str|null,       ← 拆分类型
    "uid":        int,            ← 唯一 ID（回卷追踪用）
    "parent":     int|null,       ← 父片段 uid
    "parent_seq": int,            ← 父序号
}
```

#### `apply_protection_blocks() → (str, list)`（保护块）

**调用方：** `service/split_service.py`  
**提供方：** `_protection_config.py`

```
apply_protection_blocks(text: str) -> (protected_text: str, blocks: [str])
```

**注意：** `analyze_scored.py` 内部也调了 `apply_protection_blocks`。所以保护块在流水线中被调了两次——一次在 scored 分析内部，一次在 split_service 开头。第二次因为已保护的文本不再匹配 pattern，实际上是安全的。

#### `clean_html()` → str

**调用方：** `service/split_service.py`  
**提供方：** `post-类型拆分.py`

```
clean_html(text: str) -> str
```
去除 HTML 标签，标准化空白符。

#### `infer_type_levels()` → dict

**调用方：** `service/split_service.py`  
**提供方：** `analyze_split_types.py`

```
infer_type_levels(sequence: [dict]|[str]) -> {类型名: 层级int}
```
差分权重法：分析片段出现顺序和包裹关系，推断类型间的层级索引。0=最外层。

#### `_restore_placeholders()` → str

**调用方：** `service/split_service.py`  
**提供方：** `_protection_config.py`

```
_restore_placeholders(text: str, blocks: [str]) -> str
```
把 `___PB_XXX_N___` 占位符替换回 blocks 里的原始文本。

---

## 3. 数据流向图

```
┌─────────────────────────────────────────────────────────────────┐
│                        外部合约（不可变）                          │
│                                                                 │
│  GET /health        →  {"status": "ok"}                         │
│  POST /api/split    ←  {text, params}                           │
│                     →  {fragments: [{seq,content,...}],         │
│                         meta: {char_count,fragment_count,...}}   │
│                                                                 │
│  消费者: launch.py, index.py, service_client.py, results.py       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                  service/split_service.py                       │
│                     （唯一的编排 + 适配层）                          │
│                                                                 │
│  split_text(text, params) -> {fragments, meta}                  │
│    │                                                            │
│    ├─ [1] clean_html(text)                     → str            │
│    │     └─ post-类型拆分.py                                     │
│    │                                                            │
│    ├─ [2] apply_protection_blocks(text)        → (str, list)    │
│    │     └─ _protection_config.py                               │
│    │                                                            │
│    ├─ [3] analyze(protected)                   → dict(report)   │
│    │     ├─ analyze_scored.py (默认)                             │
│    │     │   ├─ apply_protection_blocks()                        │
│    │     │   ├─ build_type_patterns()         ← _type_patterns  │
│    │     │   └─ score_ordinals()                                 │
│    │     └─ analyze_split_types.py (legacy)                     │
│    │         ├─ apply_protection_blocks()                        │
│    │         └─ print_report()                                    │
│    │                                                            │
│    ├─ [4] split_single_group_with_rollback()  → [gdata]         │
│    │     └─ post-类型拆分.py                                     │
│    │         ├─ find_split_point_for_types()                     │
│    │         ├─ global_backward_rollback()                       │
│    │         └─ split_empty_prefix_transitions()                 │
│    │                                                            │
│    ├─ [5] _restore_placeholders(per frag)     → str             │
│    │     └─ _protection_config.py                               │
│    │                                                            │
│    ├─ [6] infer_type_levels(gdata)            → dict{type:level}│
│    │     └─ analyze_split_types.py                               │
│    │                                                            │
│    ├─ [7] _extract_ordinal(content, type)     → int|[int]       │
│    │     └─ _type_patterns_config.py                             │
│    │                                                            │
│    └─ [8] 打包 → {fragments, meta}                               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                        内部合约（可改）                             │
│                                                                 │
│  以上 7 个被调函数的签名/返回值，只要在 split_service.py 里适配，    │
│  对外部零影响。                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. UI 组件关系

```
app/main.py （入口）
  │
  ├── @ui.page('/')
  │     └── app/pages/index.py:build()
  │           ├── FileUpload(on_text_changed)    ← file_upload.py
  │           │     └── 解析 txt/docx/xlsx → 填入共享 textarea
  │           ├── 算法参数 (ui.expansion)
  │           └── 拆分按钮 → svc.split()         ← service_client.py
  │                 ├── 成功 → app.storage.user['last_result'] = result
  │                 └── ui.navigate.to('/results')
  │
  ├── @ui.page('/results')
  │     └── app/pages/results.py:build()
  │           ├── app.storage.user['last_result']  ← 读数据
  │           ├── 摘要栏（meta 统计信息）
  │           ├── ui.add_head_html → CSS 样式
  │           ├── ui.run_javascript → window.__ROWS / __DETAIL
  │           ├── 加载 static/table-renderer.js（模块脚本）
  │           ├── 轮询 window.__pd → 弹详情对话框
  │           └── 导出 Excel → openpyxl
  │
  └── app.mount('/static', StaticFiles(directory='static'))
```

---

## 5. NiceGUI CSS 排版规则（牢记）

在结果页中我们使用原始 HTML `<table>`（不是 `ui.table`），Quasar 全局样式会覆盖自定义 CSS。

**必须遵循三重防御：**

1. **注入方式** — 用 `ui.add_head_html('<style>...</style>')`，不要用 `ui.html()` 放 `<style>`
2. **选择器** — 所有选择器加 `#pt-root` 前缀提高特异性
3. **关键属性** — `text-align`、`vertical-align`、`border`、`font-weight`、`width` 全部加 `!important`
4. **列宽** — 同时用 `<colgroup>` + CSS `nth-child` 双重锁定

```css
#pt-root .pt-t { table-layout: fixed !important; }
#pt-root .pt-c1 { text-align: center !important; font-weight: 700 !important; }
#pt-root .pt-t th:nth-child(1), #pt-root .pt-t td:nth-child(1) { width: 52px !important; }
```

（详见 `app/pages/results.py` 中 `_build_pretext_table()` 的 `add_head_html` 部分）

---

## 6. 版本历史

| 日期 | 里程碑 |
|------|--------|
| 2026-05-15 | 完成设计文档和实现计划 |
| 2026-05-15 | Task 1-10：service + UI 全部组件实现 |
| 2026-05-15 | 健康轮询修复（timer 放进页面而非 startup） |
| 2026-05-15 | 表格迭代：ui.table → pretext → 原始 HTML + add_head_html |
| 2026-05-18 | CSS 三重防御方案落地（#pt-root + !important + nth-child） |
| 2026-05-18 | 列宽固定 + 居中对齐 + 框线 全部生效 |
