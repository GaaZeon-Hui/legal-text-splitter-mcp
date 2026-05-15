# 法律法规文本拆分系统 — UI 设计文档

## 概述

为现有的法规文本拆分引擎构建 NiceGUI Web 界面。采用双进程架构：NiceGUI 前端负责输入和展示，FastAPI 服务封装核心分析+拆分流水线。两进程通过 REST/JSON 合约通信。

## 架构：双进程

```
浏览器 → NiceGUI (:8080) → httpx → FastAPI (:8001) → 现有分析模块
```

- **NiceGUI 前端** — 上传/粘贴 → 调 API → 展示结果，不 import 任何分析模块
- **FastAPI 服务** — 薄封装，接收文本 → 调现有 `analyze_scored` / `_protection_config` / `post-类型拆分` → 返回 JSON
- **通信** — `POST /api/split` JSON 入参出参；`GET /health` 健康检查
- **不动现有文件** — 所有新增代码在 `app/` 和 `service/` 目录下，不修改任何现有 .py

## API 合约

### GET /health

```
Response 200:
{
  "status": "ok",
  "version": "1.0.0"
}
```

### POST /api/split

```
Request:
{
  "text": "<原文>",
  "params": {                    // 可选，预留算法参数扩展
    "algorithm": "scored",       // "scored" | "legacy"
    "split_types": null,         // null=自动检测, 或 ["条","章","节"]
    "min_fragment_chars": 10
  }
}

Response 200:
{
  "fragments": [
    {
      "seq": 1,
      "content": "第一条 …",
      "split_type": "条",
      "index_level": 0,
      "ordinal": 1
    }
  ],
  "meta": {
    "char_count": 1234,
    "fragment_count": 15,
    "spine_types": ["条"],
    "all_tags": ["条", "章", "括号"],
    "level_chain": "章→条",
    "processing_ms": 42,
    "algorithm": "scored"
  }
}

Response 422: { "detail": "文本为空或无法解析" }
```

### fragment 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `seq` | int | 片段序号（1-based） |
| `content` | str | 片段完整文本 |
| `split_type` | str\|null | 拆分类型：条/章/节/编/括号/数字点/… |
| `index_level` | int\|null | 层级深度，差分权重法推断 |
| `ordinal` | int \| [int, ...] | 序数值，标量为 int（如 3），点号为数组（如 [6,1,1]） |

### 大数据量约束

- 服务端不翻页，一次返回全量 JSON
- **fragment_count > 10000** 时，服务端返回 422 并提示"文本过大，建议拆分后重试"
- 正常范围（< 10000 条）下，全量传输到前端，由 AG Grid 虚拟滚动承载
- 响应 gzip 压缩以减少传输量

## 页面设计：双页结构

### 主页面 `/`

极简，快速加载。不展示任何结果数据。

- **文件上传区** — 拖拽+点击上传，支持 .txt .docx .xlsx，最大 50MB
- **Excel 列选择** — 上传 .xlsx 后，自动检测第一行表头，弹出下拉让用户选择要读取的文本列。若用户取消/关闭对话框，不上传任何文本，编辑框维持原有内容不变
- **文本编辑框** — 上传/解析后的文本填充到此 textarea，**保持可编辑**，用户可手动修正解析结果。粘贴文本也写入同一个 textarea。上传和粘贴共享此框。**后操作覆盖前内容时，弹出 toast 确认提示**（"当前内容将被替换，是否继续？"），用户确认后才执行覆盖
- **算法参数区** — `<details>` 可折叠，预留给后续扩展
- **拆分按钮** — 文本非空 + 服务在线时激活，Ctrl+Enter 快捷键
- **服务状态灯** — 绿色已连接 / 红色断开，定时轮询 /health（推荐 5 秒间隔）。页面不可见时暂停轮询（`document.visibilityState`），切回可见时立即检测

### 结果页面 `/results`

从主页面跳转而来。数据通过 `app.storage.user['last_result']` 传递（NiceGUI 会话级存储，跨页面存活）。

- **摘要统计栏** — 字符数、片段数、发现类型、层级链、耗时
- **AG Grid 表格** — `ui.aggrid` 虚拟滚动，列：序号、内容、类型、层级、序数。自动列宽，内容列省略长文本
- **行详情** — 点击行弹出 `ui.dialog`，展示该片段完整文本内容
- **搜索** — AG Grid 内置 quickFilter，输入即过滤
- **类型过滤** — AG Grid 列头下拉过滤，按 split_type 筛选
- **导出 Excel** — 下载**当前表格视图**的数据为 .xlsx（即搜索/过滤后的可见行），而非全部片段。导出时沿用 AG Grid 当前排序和过滤状态
- **返回链接** — 回到主页面（不清除 storage）

## 文件解析

| 格式 | 解析方式 | 备注 |
|------|----------|------|
| `.txt` | 直接读取，UTF-8 / GBK 自动检测 | chardet |
| `.docx` | python-docx 提取段落，\n 拼接 | 忽略格式 |
| `.xlsx` | openpyxl 读取用户选择的列 | 上传后弹出列选择下拉，默认选第一列 |
| 粘贴文本 | 写入 textarea | 与上传共享同一个编辑框，后操作覆盖前内容 |

解析流程：上传 → 校验扩展名白名单 → 调解析器（.xlsx 需用户选列）→ 文本填充到 textarea（可编辑）→ 用户确认/修正 → 点拆分 → 文本校验（非空 + < 50MB）→ 发送 /api/split

## 错误处理

| 场景 | UI 表现 |
|------|---------|
| 格式不支持 | 上传区变红 + toast 提示 |
| 文件过大 (>50MB) | 上传区变红 + 提示大小限制 |
| 解析失败 | toast 提示具体原因 |
| 文本为空 | 拆分按钮保持禁用 |
| 服务不可达 | 状态灯变红 + 按钮禁用 + toast |
| 服务返回错误 | 主页 toast 展示错误，不跳转 |
| 请求超时 (30s) | loading 结束 + toast |
| 0 片段结果 | 跳转结果页，显示"未能拆分" |

### UI 状态机

```
IDLE → (文本就绪) → READY → (点击拆分) → LOADING → (成功) → 跳转结果页
  ↑                    ↑                      ↓
  ←←←←←←←←←←←←←←←←←← (失败/超时) ←←←←←←←
  
DISCONNECTED ←→ (服务恢复) → IDLE
```

## 项目文件结构

```
UI SETTING/
├── app/                          # 新增：NiceGUI 前端
│   ├── main.py                   # ui.run() 入口，路由注册，全局状态灯
│   ├── pages/
│   │   ├── index.py              # 主页（上传+列选择+编辑框+参数+拆分）
│   │   └── results.py            # 结果页（摘要+AG Grid+导出）
│   └── components/
│       ├── file_upload.py        # 上传组件（含 .xlsx 列选择对话框）
│       ├── service_client.py     # httpx 客户端封装
│       └── aggrid_table.py       # AG Grid 表格组件（行点击→dialog 详情）
├── service/                      # 新增：FastAPI 服务
│   ├── main.py                   # 服务入口，/health + /api/split
│   └── split_service.py          # 分析+拆分业务封装
├── _protection_config.py         # 不变
├── _type_patterns_config.py      # 不变
├── analyze_scored.py             # 不变
├── analyze_split_types.py        # 不变
├── pipeline_split.py             # 不变
└── post-类型拆分.py              # 不变
```

## 预留扩展位

- **算法参数面板** — `params` 已预留字段，后续加 UI 控件（下拉、滑块）
- **批量处理** — 未来可加 `/batch` 页签，上传 Excel → 逐条调服务 → 批量导出
- **DB 加载** — 服务连接配置区，从数据库按 law_id 拉取文本
- **PySide6 服务替换** — 只要 FastAPI 合约不变，底层服务可任意替换
- **结果编辑** — 表格可加"删除片段"/"合并片段"操作列
