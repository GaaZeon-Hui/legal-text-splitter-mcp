# Legal Text Splitter MCP Server

MCP server for Chinese legal text splitting. Exposes the text splitting engine as MCP tools for AI agents.

## Install

```bash
pip install legal-text-splitter-mcp
```

Or run directly:

```bash
uvx legal-text-splitter-mcp
```

## MCP Tools

### split_text

Split raw legal text into typed fragments. No database required.

Input: `text` (string) — raw legal text, may contain HTML.

### split_by_law_ids

Fetch legal texts from database by law_id, then split each.

Input: `law_ids` (list of strings).

Requires database credentials via environment variables:
- `LEGAL_DB_HOST` (default: localhost)
- `LEGAL_DB_PORT` (default: 3306)
- `LEGAL_DB_USER` (default: root)
- `LEGAL_DB_PASSWORD`
- `LEGAL_DB_NAME` (default: legal_db)

## Configure

Add to your MCP client configuration (e.g., `claude_desktop_config.json`):

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
        "LEGAL_DB_PASSWORD": "...",
        "LEGAL_DB_NAME": "legal_db"
      }
    }
  }
}
```
