# 中文法规条款拆分MCP

这是目前市场上独一无二的、面向 MCP 生态的中文法律文本拆分工具，极大简化法律 AI 应用的构建流程~

目前忘记上传测试用例了，但是相信我，北大法宝随便拉一条出来都可以轻松给他按条款切成燥子。输出Excel表中自带每一条拆分条款对应索引级别，方便各位可自行构建索引目录~

## 功能

| 工具 | 说明 | 需要数据库 |
|------|------|-----------|
| `split_text` | 将原始法规文本拆分为带类型的片段 | 否 |
| `split_by_law_ids` | 按 law_id 从数据库拉取文本后拆分 | 是 |

## 安装

### 从 Git 安装（推荐）

```bash
git clone <https://github.com/GaaZeon-Hui/legal-text-splitter-mcp.git>
cd legal-text-splitter-mcp
pip install -e .
```



## 配置 MCP 客户端

将以下配置添加到 MCP 客户端配置文件中：

### Claude Desktop / Claude Code

配置文件位置：
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Claude Code**: 项目根目录 `.mcp.json` 或全局 `~/.claude/.mcp.json`

```json
{
  "mcpServers": {
    "legal-splitter": {
      "command": "uvx",
      "args": ["legal-text-splitter-mcp"],
      "env": {
        "LEGAL_DB_HOST": "your_host",
        "LEGAL_DB_PORT": "8001",
        "LEGAL_DB_USER": "root",
        "LEGAL_DB_PASSWORD": "your_password",
        "LEGAL_DB_NAME": "legal_db"
      }
    }
  }
}
```

> **注意**：如果只使用 `split_text` 工具（不需要数据库），可以省略 `env` 中的所有 DB 配置。

### 从本地路径安装时

使用本地路径：

```json
{
  "mcpServers": {
    "legal-splitter": {
      "command": "uvx",
      "args": ["--from", "D:/path/to/legal-text-splitter-mcp", "legal-text-splitter-mcp"],
      "env": {
        "LEGAL_DB_HOST": "your_host",
        "LEGAL_DB_PORT": "8001",
        "LEGAL_DB_USER": "root",
        "LEGAL_DB_PASSWORD": "your_password",
        "LEGAL_DB_NAME": "legal_db"
      }
    }
  }
}
```

### Cursor

在 Cursor 设置中找到 MCP 配置，添加上方 JSON 配置。

## 工具详解

### split_text

拆分原始法规文本。无需数据库，直接传入文本即可。

**输入参数：**
- `text` (string) — 原始法规文本，可包含 HTML 标签

**返回示例：**

```json
{
  "fragments": [
    {
      "seq": 1,
      "content": "第一条 为了规范...",
      "split_type": "条",
      "index_level": 0,
      "ordinal": 1,
      "extra": ""
    }
  ],
  "meta": {
    "char_count": 1520,
    "fragment_count": 12,
    "all_tags": ["条", "款"],
    "level_chain": "条(0) > 款(1)",
    "processing_ms": 45
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `seq` | int | 片段序号（从 1 开始） |
| `content` | str | 片段文本内容 |
| `split_type` | str/null | 拆分类型，如"条"/"章"/"款"/"数字点"等 |
| `index_level` | int/null | 层级深度，0=最外层 |
| `ordinal` | int/list/null | 序数值，如 3 表示第三条，[6,1,1] 表示第六章第一节第一项 |
| `extra` | str | 附加信息（回卷标记等） |
| `meta.char_count` | int | 原始文本字符数 |
| `meta.fragment_count` | int | 拆分后的片段总数 |
| `meta.all_tags` | list | 本次拆分涉及的所有类型 |
| `meta.level_chain` | str | 层级链，如 "章(0) > 条(1) > 款(2)" |
| `meta.processing_ms` | int | 处理耗时（毫秒） |

### split_by_law_ids

按 law_id 列表从数据库批量拉取法规文本并拆分。

**输入参数：**
- `law_ids` (string 列表) — 法律 ID 列表

**需要的环境变量：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LEGAL_DB_HOST` | localhost | 数据库地址 |
| `LEGAL_DB_PORT` | 3306 | 数据库端口 |
| `LEGAL_DB_USER` | root | 数据库用户名 |
| `LEGAL_DB_PASSWORD` | (空) | 数据库密码 |
| `LEGAL_DB_NAME` | legal_db | 数据库名 |

## 引擎管线

文本经过的处理流程：

```
原始文本（可含 HTML）
  → clean_html（清洗 HTML 标签）
  → analyze（规则式分析，识别拆分类型）
  → split_single_group_with_rollback（拆分 + 回卷）
  → infer_type_levels（推断层级深度）
  → get_ordinal（提取序数）
  → 输出带类型的片段列表
```

## 开发

```bash
# 克隆项目
git clone <仓库地址>
cd legal-text-splitter-mcp

# 开发模式安装
pip install -e .

# 验证导入
python -c "from legal_text_splitter.engine import process_text; print('OK')"

# 测试拆分
python -c "
from legal_text_splitter.engine import process_text
result = process_text('<p>第一条 测试。</p><p>第二条 内容。</p>')
print(f'{len(result[\"split_results\"])} 个片段')
"
```

## 依赖

- Python >= 3.10
- mcp >= 1.0.0
- openpyxl
- pymysql

## 许可

## License
MIT License. See [LICENSE](LICENSE) file for details.