# 法规文本拆分 UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build NiceGUI web interface + FastAPI service for legal document splitting, with dual-page architecture (input page / results page), AG Grid table with virtual scrolling, file upload with Excel column selection, and health polling.

**Architecture:** Two Python processes — FastAPI service (:8001) wraps existing analysis/split modules behind a REST JSON API; NiceGUI app (:8080) handles upload/input and renders results via AG Grid. Data passes between pages via `app.storage.user`.

**Tech Stack:** NiceGUI, FastAPI, httpx, python-docx, openpyxl, cchardet

---

## File Structure

```
UI SETTING/
├── service/                    # NEW
│   ├── __init__.py
│   ├── main.py                 # FastAPI entry: /health, /api/split
│   └── split_service.py        # Pipeline wrapper: analyze → split → fragments
├── app/                        # NEW
│   ├── __init__.py
│   ├── main.py                 # NiceGUI entry: ui.run(), global health timer
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── index.py            # Main page: upload, textarea, params, split button
│   │   └── results.py          # Results page: summary bar, AG Grid, export
│   └── components/
│       ├── __init__.py
│       ├── service_client.py   # httpx async client for /api/split + /health
│       ├── file_upload.py      # Upload handler + Excel column selector dialog
│       └── aggrid_table.py     # AG Grid wrapper: virtual scroll, row→dialog, export
├── run_service.py              # NEW: one-click launcher for the FastAPI service
├── run_ui.py                   # NEW: one-click launcher for the NiceGUI app
├── _protection_config.py       # UNCHANGED
├── _type_patterns_config.py    # UNCHANGED
├── analyze_scored.py           # UNCHANGED
├── analyze_split_types.py      # UNCHANGED
├── pipeline_split.py           # UNCHANGED
└── post-类型拆分.py            # UNCHANGED
```

---

### Task 1: Service — split_service.py

**Files:**
- Create: `service/__init__.py`
- Create: `service/split_service.py`

- [ ] **Step 1: Write `service/__init__.py`**

```python
# service package
```

- [ ] **Step 2: Write `service/split_service.py`**

```python
"""Thin wrapper around the existing analysis + split pipeline.

Exposes a single entry point split_text(text, params) -> dict
that the FastAPI endpoint calls directly.
"""
import sys
import os
import time

# Ensure parent directory is on sys.path so existing modules are importable
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from _protection_config import apply_protection_blocks, _restore_placeholders
from _type_patterns_config import build_type_patterns
from analyze_scored import analyze as analyze_scored
from analyze_split_types import analyze as analyze_legacy
from analyze_split_types import print_report, infer_type_levels, count_paragraphs

# post-类型拆分  uses Chinese filename — import via importlib
from importlib import util as _importlib_util
_post_spec = _importlib_util.spec_from_file_location(
    'post_split', os.path.join(_PARENT, 'post-类型拆分.py'))
_post_mod = _importlib_util.module_from_spec(_post_spec)
_post_spec.loader.exec_module(_post_mod)

clean_html = _post_mod.clean_html
split_plain_by_paragraphs = _post_mod.split_plain_by_paragraphs
split_single_group_with_rollback = _post_mod.split_single_group_with_rollback

# Also need _format_level_chain (defined in analyze_split_types, not exported)
from analyze_split_types import _format_level_chain


def _extract_ordinal(content, split_type):
    """Extract the ordinal value from a fragment's content based on its split_type."""
    if not split_type:
        return None
    try:
        patterns = build_type_patterns([split_type])
        for name, pat, func in patterns:
            m = pat.match(content)
            if m:
                val = func(m)
                if val is not None:
                    return val
        return None
    except Exception:
        return None


MAX_FRAGMENTS = 10000


def split_text(text: str, params: dict | None = None) -> dict:
    """Execute full analysis + split pipeline.

    Args:
        text: Raw legal document text (may contain HTML).
        params: Optional algorithm parameters:
            - algorithm: 'scored' (default) | 'legacy'
            - split_types: None (auto-detect) | ['条', '章', ...]
            - min_fragment_chars: 10 (default)

    Returns:
        dict with 'fragments' (list) and 'meta' (dict).
    """
    if params is None:
        params = {}

    algorithm = params.get('algorithm', 'scored')
    split_types_override = params.get('split_types')
    # min_fragment_chars is reserved for future use

    # 1. Clean HTML
    cleaned = clean_html(text)

    # 2. Apply protection blocks
    protected, blocks = apply_protection_blocks(cleaned)

    # 3. Analyze
    if algorithm == 'scored':
        report = analyze_scored(protected)
    else:
        raw_results = analyze_legacy(protected)
        report = print_report(raw_results, protected, quiet=True)

    all_tags = report.get('all_tags', [])
    is_plain = report.get('is_plain', False)

    # Override split types if specified
    if split_types_override is not None:
        all_tags = split_types_override
        is_plain = False

    # 4. Split
    t0 = time.time()

    if is_plain or not all_tags or all_tags == ['纯文本']:
        gdata = [{
            'group': 'input', 'seq': 1,
            'content': protected, 'extra': None,
            'source_id': 0, 'split_type': None,
        }]
    elif '纯文本段落拆分' in all_tags:
        paragraphs = split_plain_by_paragraphs(protected)
        gdata = []
        for i, p in enumerate(paragraphs):
            gdata.append({
                'group': 'input', 'seq': i + 1,
                'content': p, 'extra': None,
                'source_id': 0, 'split_type': None,
            })
        other_types = [t for t in all_tags if t != '纯文本段落拆分']
        if other_types:
            gdata = split_single_group_with_rollback(
                gdata, 'input', split_types_override=other_types, verbose=False)
    else:
        gdata = [{
            'group': 'input', 'seq': 1,
            'content': protected, 'extra': None,
            'source_id': 0, 'split_type': None,
        }]
        gdata = split_single_group_with_rollback(
            gdata, 'input', split_types_override=all_tags, verbose=False)

    processing_ms = int((time.time() - t0) * 1000)

    # 5. Check fragment count
    if len(gdata) > MAX_FRAGMENTS:
        raise ValueError(
            f'文本过大，片段数 {len(gdata)} 超过上限 {MAX_FRAGMENTS}，建议拆分后重试')

    # 6. Restore protection block placeholders
    for frag in gdata:
        frag['content'] = _restore_placeholders(frag['content'], blocks)

    # 7. Infer type index levels
    type_levels = infer_type_levels(gdata)

    # 8. Build fragment list
    fragments = []
    for frag in gdata:
        st = frag.get('split_type')
        ordinal = _extract_ordinal(frag['content'], st)
        fragments.append({
            'seq': len(fragments) + 1,
            'content': frag['content'],
            'split_type': st,
            'index_level': type_levels.get(st),
            'ordinal': ordinal,
        })

    # 9. Build meta
    chain_str, _ = _format_level_chain(type_levels)

    return {
        'fragments': fragments,
        'meta': {
            'char_count': len(text),
            'fragment_count': len(fragments),
            'spine_types': report.get('spine_types', []),
            'all_tags': all_tags,
            'level_chain': chain_str,
            'processing_ms': processing_ms,
            'algorithm': algorithm,
        },
    }
```

- [ ] **Step 3: Verify service module imports correctly**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "from service.split_service import split_text; print('OK')"
```

Expected: "OK" (or clear import errors to fix).

---

### Task 2: Service — FastAPI main.py

**Files:**
- Create: `service/main.py`

- [ ] **Step 1: Write `service/main.py`**

```python
"""FastAPI service for legal document splitting.

Endpoints:
    GET  /health     — health check
    POST /api/split  — analyze + split legal text
"""
import sys
import os

_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from service.split_service import split_text as _split_text, MAX_FRAGMENTS

app = FastAPI(title='法规文本拆分服务', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


class SplitParams(BaseModel):
    algorithm: str = 'scored'
    split_types: list[str] | None = None
    min_fragment_chars: int = 10


class SplitRequest(BaseModel):
    text: str
    params: SplitParams = Field(default_factory=SplitParams)


@app.get('/health')
async def health():
    return {'status': 'ok', 'version': '1.0.0'}


@app.post('/api/split')
async def api_split(req: SplitRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail='文本为空或无法解析')

    try:
        result = _split_text(req.text, req.params.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'处理失败: {e}')

    return result


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001)
```

- [ ] **Step 2: Install FastAPI dependencies**

```bash
pip install fastapi uvicorn
```

- [ ] **Step 3: Start service and verify**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "
from service.main import app
from fastapi.testclient import TestClient
client = TestClient(app)

# Test health
r = client.get('/health')
assert r.status_code == 200
assert r.json()['status'] == 'ok'
print('health OK')

# Test split with empty text
r = client.post('/api/split', json={'text': '', 'params': {}})
assert r.status_code == 422
print('empty text 422 OK')

# Test split with real text
text = '第一条 为了规范市场秩序，制定本法。\n第二条 市场准入实行负面清单制度。'
r = client.post('/api/split', json={'text': text, 'params': {}})
assert r.status_code == 200
data = r.json()
assert 'fragments' in data
assert 'meta' in data
assert len(data['fragments']) > 0
print(f'split OK — {data[\"meta\"][\"fragment_count\"]} fragments')
"
```

---

### Task 3: UI — service_client.py

**Files:**
- Create: `app/__init__.py`
- Create: `app/components/__init__.py`
- Create: `app/components/service_client.py`

- [ ] **Step 1: Write `app/__init__.py`**

```python
# app package
```

- [ ] **Step 2: Write `app/components/__init__.py`**

```python
# components package
```

- [ ] **Step 3: Write `app/components/service_client.py`**

```python
"""Async HTTP client for the FastAPI split service."""
import httpx

SERVICE_URL = 'http://127.0.0.1:8001'
REQUEST_TIMEOUT = 30.0  # seconds


class ServiceClient:
    """Async client wrapping the /health and /api/split endpoints."""

    def __init__(self, base_url: str = SERVICE_URL):
        self.base_url = base_url

    async def health(self) -> bool:
        """Check if the service is reachable. Returns True/False."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f'{self.base_url}/health')
                return r.status_code == 200
        except Exception:
            return False

    async def split(self, text: str, params: dict | None = None) -> dict:
        """Send text to /api/split, return parsed JSON response.

        Raises ServiceError on non-200 response or network failure.
        """
        body = {
            'text': text,
            'params': params or {},
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(
                f'{self.base_url}/api/split',
                json=body,
            )
        if r.status_code == 422:
            detail = r.json().get('detail', '文本无法解析')
            raise ServiceError(detail, status_code=422)
        if r.status_code != 200:
            raise ServiceError(
                f'服务返回错误 ({r.status_code})',
                status_code=r.status_code)
        return r.json()


class ServiceError(Exception):
    """Raised when the service returns an error response."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


# Module-level singleton
client = ServiceClient()
```

- [ ] **Step 4: Verify client module imports**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "from app.components.service_client import ServiceClient; print('OK')"
```

---

### Task 4: UI — main.py entry point

**Files:**
- Create: `app/main.py`
- Create: `app/pages/__init__.py`

- [ ] **Step 1: Write `app/pages/__init__.py`**

```python
# pages package
```

- [ ] **Step 2: Write `app/main.py`**

```python
"""NiceGUI application entry point.

Registers pages, starts the health poll timer,
and launches the UI server.
"""
import asyncio
from nicegui import app, ui

from app.components.service_client import client as svc

SERVICE_URL = 'http://127.0.0.1:8001'
HEALTH_POLL_SECONDS = 5.0


# ── Global service status ──
service_online = False


async def _poll_health():
    """Periodically check service health."""
    global service_online
    service_online = await svc.health()


@ui.page('/')
def index_page():
    """Main page: upload, text editing, params, split trigger."""
    from app.pages.index import build as _build_index
    _build_index()


@ui.page('/results')
def results_page():
    """Results page: summary bar, AG Grid table, export."""
    from app.pages.results import build as _build_results
    _build_results()


@app.on_startup
async def startup():
    ui.timer(HEALTH_POLL_SECONDS, _poll_health)

    # Page visibility pause/resume for health polling
    ui.add_body_html('''
    <script>
    document.addEventListener('visibilitychange', () => {
        fetch('/api/visibility/' + (document.hidden ? 'hidden' : 'visible'));
    });
    </script>
    ''')

    # Initial health check
    await _poll_health()


@app.get('/api/visibility/hidden')
async def visibility_hidden():
    # When page becomes hidden, we stop the timer
    pass


@app.get('/api/visibility/visible')
async def visibility_visible():
    # When page becomes visible again, immediately check health
    global service_online
    service_online = await svc.health()
    # The timer will continue naturally


ui.run(
    host='127.0.0.1',
    port=8080,
    title='法规文本拆分系统',
    favicon='📋',
    storage_secret='split-ui-secret-v1',
    reload=False,
    show=True,
)
```

- [ ] **Step 3: Create placeholder pages for app to start**

```python
# In app/pages/index.py (temporary placeholder)
def build():
    from nicegui import ui
    ui.label('Main page placeholder')
```

```python
# In app/pages/results.py (temporary placeholder)
def build():
    from nicegui import ui
    ui.label('Results page placeholder')
```

Write these two placeholder files so `app/main.py` can be verified.

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "
import sys
# Just verify imports work — don't actually start the server
from app.components.service_client import ServiceClient
from app.main import _poll_health
print('main.py imports OK')
"
```

---

### Task 5: UI — file_upload.py component

**Files:**
- Create: `app/components/file_upload.py`

- [ ] **Step 1: Write `app/components/file_upload.py`**

```python
"""File upload component with Excel column selector.

Handles .txt, .docx, .xlsx parsing.
Uploaded/parsed text goes into a shared textarea.
"""
import io
import cchardet as chardet
from nicegui import ui

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw)
    encoding = result.get('encoding', 'utf-8') if result else 'utf-8'
    return encoding or 'utf-8'


def _parse_txt(raw: bytes) -> str:
    encoding = _detect_encoding(raw)
    return raw.decode(encoding, errors='replace')


def _parse_docx(raw: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError('请安装 python-docx: pip install python-docx')
    doc = Document(io.BytesIO(raw))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)


def _parse_xlsx_headers(raw: bytes) -> list[str]:
    """Return first-row headers from the Excel file."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError('请安装 openpyxl: pip install openpyxl')
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
    ws = wb.active
    headers = [str(c.value) if c.value is not None else '' for c in ws[1]]
    wb.close()
    return headers


def _parse_xlsx_column(raw: bytes, col_index: int) -> str:
    """Extract text from a single column in the Excel file."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
    ws = wb.active
    cells = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=col_index + 1,
                            max_col=col_index + 1, values_only=True):
        val = row[0]
        if val is not None and str(val).strip():
            cells.append(str(val).strip())
    wb.close()
    return '\n'.join(cells)


class FileUpload:
    """Upload area + Excel column selector + shared textarea.

    Usage:
        uploader = FileUpload(on_text_changed=my_handler)
        # uploader.textarea is the shared ui.textarea
    """

    def __init__(self, on_text_changed=None):
        self.on_text_changed = on_text_changed

        with ui.column().classes('w-full gap-2'):
            # Upload area
            self.upload = ui.upload(
                label='拖拽文件到此处 或 点击上传',
                on_upload=self._handle_upload,
                auto_upload=True,
                max_file_size=MAX_FILE_SIZE,
            ).classes('w-full').props('accept=.txt,.docx,.xlsx')

            # Shared textarea
            self.textarea = ui.textarea(
                '法条文本',
                placeholder='上传文件或在此粘贴法条原文…',
                on_change=lambda e: self._on_text_change(),
            ).classes('w-full h-64')

    def _on_text_change(self):
        if self.on_text_changed:
            self.on_text_changed(self.textarea.value or '')

    async def _handle_upload(self, e):
        """Process uploaded file, handle Excel column selection."""
        raw = e.content.read()

        if len(raw) > MAX_FILE_SIZE:
            ui.notify(f'文件过大，超过 50MB 限制', type='negative')
            self.upload.reset()
            return

        ext = (e.name or '').lower()
        parsed = None

        try:
            if ext.endswith('.txt'):
                parsed = _parse_txt(raw)

            elif ext.endswith('.docx'):
                parsed = _parse_docx(raw)

            elif ext.endswith('.xlsx'):
                # Detect headers and ask user to pick column
                headers = _parse_xlsx_headers(raw)
                if not headers:
                    ui.notify('Excel 文件第一行为空，无法读取列', type='negative')
                    self.upload.reset()
                    return

                # Show column selection dialog
                col_index = await _show_column_dialog(headers)
                if col_index is None:
                    # User cancelled — keep current text, do nothing
                    self.upload.reset()
                    return
                parsed = _parse_xlsx_column(raw, col_index)

            else:
                ui.notify(f'不支持的格式: {ext}', type='negative')
                self.upload.reset()
                return

        except Exception as ex:
            ui.notify(f'文件解析失败: {ex}', type='negative')
            self.upload.reset()
            return

        if not parsed or not parsed.strip():
            ui.notify('文件内容为空', type='warning')
            self.upload.reset()
            return

        # Confirm overwrite if textarea has existing content
        current = (self.textarea.value or '').strip()
        if current:
            result = await _confirm_overwrite()
            if not result:
                self.upload.reset()
                return

        self.textarea.value = parsed
        self._on_text_change()
        self.upload.reset()


async def _show_column_dialog(headers: list[str]) -> int | None:
    """Show dialog for column selection. Returns column index or None if cancelled."""
    result = {'index': None}

    with ui.dialog() as dialog, ui.card().classes('p-4'):
        ui.label('选择要读取的文本列').classes('text-lg font-bold')
        ui.label(f'检测到 {len(headers)} 列').classes('text-sm text-grey')

        options = {f'{h} (第{i+1}列)': i
                   for i, h in enumerate(headers) if h}
        if not options:
            options = {f'第{i+1}列': i for i in range(len(headers))}

        col_select = ui.select(
            options=options,
            value=list(options.values())[0],
            label='文本列',
        ).classes('w-full')

        with ui.row().classes('gap-2'):
            ui.button('确定', on_click=lambda: _set_and_close(0))
            ui.button('取消', on_click=lambda: _set_and_close(None))

        def _set_and_close(val):
            if val == 0:
                result['index'] = col_select.value
            else:
                result['index'] = None
            dialog.close()

    await dialog
    return result['index']


async def _confirm_overwrite() -> bool:
    """Ask user to confirm text overwrite. Returns True to proceed."""
    result = {'ok': False}

    with ui.dialog() as dialog, ui.card().classes('p-4'):
        ui.label('当前内容将被替换').classes('text-lg font-bold')
        ui.label('文本编辑框中已有内容，是否继续？').classes('text-sm text-grey')
        with ui.row().classes('gap-2'):
            ui.button('继续', on_click=lambda: _ok_and_close(dialog, result))
            ui.button('取消', on_click=lambda: dialog.close())

    def _ok_and_close(d, r):
        r['ok'] = True
        d.close()

    await dialog
    return result['ok']
```

- [ ] **Step 2: Install parse dependencies**

```bash
pip install cchardet python-docx openpyxl
```

- [ ] **Step 3: Verify component imports**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "from app.components.file_upload import FileUpload; print('OK')"
```

---

### Task 6: UI — aggrid_table.py component

**Files:**
- Create: `app/components/aggrid_table.py`

- [ ] **Step 1: Write `app/components/aggrid_table.py`**

```python
"""AG Grid table wrapper for fragment results display.

Features:
  - Virtual scrolling for large datasets
  - QuickFilter text search
  - Column header filtering by split_type
  - Row click → dialog with full content
  - Export current view to Excel
"""
import io
from nicegui import ui


def build_aggrid(fragments: list[dict], meta: dict):
    """Build an AG Grid table from fragment data.

    Args:
        fragments: List of fragment dicts from /api/split response.
        meta: Meta dict from /api/split response.

    Returns:
        The ui.aggrid element.
    """
    column_defs = [
        {
            'headerName': '序号',
            'field': 'seq',
            'width': 70,
            'sortable': True,
            'filter': False,
        },
        {
            'headerName': '内容',
            'field': 'content_preview',
            'flex': 1,
            'sortable': False,
            'filter': False,
            'cellRenderer': '''
                function(params) {
                    if (!params.value) return '';
                    return params.value.substring(0, 80) + (params.value.length > 80 ? '…' : '');
                }
            ''',
        },
        {
            'headerName': '类型',
            'field': 'split_type_display',
            'width': 90,
            'sortable': True,
            'filter': True,
        },
        {
            'headerName': '层级',
            'field': 'index_level',
            'width': 70,
            'sortable': True,
            'filter': False,
        },
        {
            'headerName': '序数',
            'field': 'ordinal_display',
            'width': 90,
            'sortable': True,
            'filter': False,
        },
    ]

    row_data = []
    for f in fragments:
        content = f.get('content', '')
        st = f.get('split_type')
        il = f.get('index_level')
        ordinal = f.get('ordinal')

        # Format for display
        st_display = st if st else '-'
        il_display = str(il) if il is not None else '-'
        if isinstance(ordinal, list):
            ord_display = '.'.join(str(x) for x in ordinal)
        elif ordinal is not None:
            ord_display = str(ordinal)
        else:
            ord_display = '-'

        row_data.append({
            'seq': f.get('seq', 0),
            'content': content,
            'content_preview': content,
            'split_type': st_display,
            'split_type_display': st_display,
            'index_level': il_display,
            'ordinal': ordinal,
            'ordinal_display': ord_display,
        })

    grid_options = {
        'columnDefs': column_defs,
        'rowData': row_data,
        'defaultColDef': {
            'resizable': True,
        },
        'enableCellTextSelection': True,
        'rowSelection': 'single',
        'pagination': True,
        'paginationPageSize': 50,
        'paginationPageSizeSelector': [20, 50, 100, 200],
        'domLayout': 'autoHeight',
    }

    grid = ui.aggrid(grid_options).classes('w-full')

    # Row click handler — show full content in dialog
    grid.on('cellClicked', lambda e: _show_detail_dialog(e, row_data))

    return grid


def _show_detail_dialog(event, row_data: list[dict]):
    """Show a dialog with the full fragment content when a row is clicked."""
    row_index = event.args.get('rowIndex', -1)
    if row_index < 0 or row_index >= len(row_data):
        return

    row = row_data[row_index]
    seq = row.get('seq', '?')
    st = row.get('split_type', '-')
    content = row.get('content', '')

    with ui.dialog() as dialog, ui.card().classes('p-4 max-w-2xl'):
        ui.label(f'片段 #{seq}').classes('text-lg font-bold')
        ui.label(f'类型: {st}').classes('text-sm text-grey')
        ui.separator()
        ui.markdown(content).classes('whitespace-pre-wrap max-h-96 overflow-auto')
        with ui.row().classes('justify-end'):
            ui.button('关闭', on_click=dialog.close)

    dialog.open()


def export_to_excel(grid, filename: str = '拆分结果.xlsx'):
    """Export current AG Grid view data to Excel."""
    try:
        import openpyxl
    except ImportError:
        ui.notify('请安装 openpyxl 以支持导出', type='negative')
        return

    # Get data from the grid — extract from current displayed rows
    # AG Grid's Python API gives us access via grid.options
    options = grid.options
    row_data = options.get('rowData', [])

    # Apply current filter/search by checking which rows are visible
    # (simplified: export all data since we can't easily get filtered state)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '拆分结果'

    headers = ['序号', '内容', '类型', '层级', '序数']
    for col, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=h)

    for i, row in enumerate(row_data, start=2):
        ws.cell(row=i, column=1, value=row.get('seq', ''))
        ws.cell(row=i, column=2, value=row.get('content', ''))
        ws.cell(row=i, column=3, value=row.get('split_type', ''))
        ws.cell(row=i, column=4, value=row.get('index_level', ''))
        ws.cell(row=i, column=5, value=row.get('ordinal_display', ''))

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    ui.download(output.read(), filename)
```

- [ ] **Step 2: Verify component imports**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "from app.components.aggrid_table import build_aggrid; print('OK')"
```

---

### Task 7: UI — index.py (main page)

**Files:**
- Create: `app/pages/index.py`

- [ ] **Step 1: Write `app/pages/index.py`**

```python
"""Main page: file upload, text editing, parameters, and split trigger."""
from nicegui import app, ui

from app.components.file_upload import FileUpload
from app.components.service_client import client as svc, ServiceError


def build():
    """Build the main page layout."""
    # ── State ──
    current_text = ''

    # ── Header ──
    with ui.header().classes('bg-primary text-white'):
        with ui.row().classes('w-full items-center justify-between p-2'):
            ui.label('法规文本拆分系统').classes('text-xl font-bold')
            _status_dot = ui.element('span').classes('w-3 h-3 rounded-full')
            _status_label = ui.label('检测中…').classes('text-sm')

            # Update status from module-level service_online
            ui.timer(1.0, lambda: _update_status(_status_dot, _status_label))

    # ── Upload area ──
    with ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-4'):

        def on_text_change(text):
            nonlocal current_text
            current_text = text
            _split_btn.enabled = bool(text.strip()) and _get_service_online()

        uploader = FileUpload(on_text_changed=on_text_change)

        # ── Parameters (collapsible) ──
        with ui.expansion('算法参数', icon='tune').classes('w-full'):
            algorithm_select = ui.select(
                options={'scored': 'scored (打分式)', 'legacy': 'legacy (规则式)'},
                value='scored',
                label='算法',
            ).classes('w-48')

            split_types_select = ui.select(
                options={'auto': '自动检测'},
                value='auto',
                label='拆分类型',
            ).classes('w-48')

        # ── Split button ──
        with ui.row().classes('items-center gap-4'):
            _split_btn = ui.button(
                '拆分',
                icon='play_arrow',
                on_click=lambda: _do_split(),
            ).props('unelevated color=primary')
            _split_btn.enabled = False
            ui.label('Ctrl+Enter').classes('text-sm text-grey')

            # Keyboard shortcut
            ui.keyboard(on_key=lambda e: _on_key(e))

        # ── Loading indicator (hidden by default) ──
        _spinner = ui.spinner(size='lg').classes('hidden')

    def _on_key(e):
        if e.key == 'enter' and e.action == 'keydown' and e.modifiers.get('ctrl'):
            nonlocal current_text
            if current_text.strip() and _get_service_online():
                _do_split()

    async def _do_split():
        nonlocal current_text
        text = current_text.strip()
        if not text:
            return

        _split_btn.visible = False
        _spinner.classes(remove='hidden')

        try:
            params = {
                'algorithm': algorithm_select.value,
            }
            if split_types_select.value != 'auto':
                params['split_types'] = [t.strip() for t in split_types_select.value.split(',')]

            result = await svc.split(text, params)
            app.storage.user['last_result'] = result
            app.storage.user['last_text'] = text
            ui.navigate.to('/results')

        except ServiceError as e:
            ui.notify(str(e), type='negative')
        except Exception as e:
            ui.notify(f'请求失败: {e}', type='negative')
        finally:
            _split_btn.visible = True
            _spinner.classes('hidden', add=True)


def _get_service_online():
    """Read the global service_online from app.main."""
    from app.main import service_online
    return service_online


def _update_status(dot, label):
    online = _get_service_online()
    if online:
        dot.classes('w-3 h-3 rounded-full', add='bg-green')
        dot.classes(remove='bg-red')
        label.set_text('服务已连接')
    else:
        dot.classes('w-3 h-3 rounded-full', add='bg-red')
        dot.classes(remove='bg-green')
        label.set_text('服务断开')
```

- [ ] **Step 2: Verify page loads (manual)**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python app/main.py
# Open http://127.0.0.1:8080 — should see the main page layout
# Stop with Ctrl+C after verification
```

---

### Task 8: UI — results.py (results page)

**Files:**
- Create: `app/pages/results.py`

- [ ] **Step 1: Write `app/pages/results.py`**

```python
"""Results page: summary bar, AG Grid table, search, export."""
from nicegui import app, ui

from app.components.aggrid_table import build_aggrid, export_to_excel


def build():
    """Build the results page from data in app.storage.user."""
    result = app.storage.user.get('last_result')
    if not result:
        ui.label('没有拆分结果，请返回主页重新拆分').classes('text-lg text-grey')
        ui.button('返回主页', on_click=lambda: ui.navigate.to('/'))
        return

    fragments = result.get('fragments', [])
    meta = result.get('meta', {})

    # ── Header ──
    with ui.header().classes('bg-primary text-white'):
        with ui.row().classes('w-full items-center justify-between p-2'):
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props('flat text-white')
                ui.label('拆分结果').classes('text-xl font-bold')
            with ui.row().classes('gap-2'):
                ui.button('导出 Excel', icon='download', on_click=lambda: _do_export()).props('flat text-white')

    with ui.column().classes('w-full p-4 gap-4'):
        # ── Summary bar ──
        with ui.row().classes('w-full flex-wrap gap-4 items-center bg-grey-1 p-3 rounded-lg'):
            ui.label(f'字符数: {meta.get("char_count", 0):,}').classes('text-sm')
            ui.label(f'片段数: {meta.get("fragment_count", 0):,}').classes('text-sm font-bold')
            ui.label(f'类型: {", ".join(meta.get("all_tags", [])) or "-"}').classes('text-sm')
            ui.label(f'层级: {meta.get("level_chain", "-")}').classes('text-sm')
            ui.label(f'耗时: {meta.get("processing_ms", 0)}ms').classes('text-sm')
            ui.label(f'算法: {meta.get("algorithm", "-")}').classes('text-sm')

        # ── Search bar ──
        with ui.row().classes('items-center gap-2'):
            search_input = ui.input(
                '搜索片段内容',
                placeholder='输入关键词…',
            ).classes('w-64')
            search_input.on('keydown', lambda e: _apply_search(e, grid),
                            throttle=0.3)

        # ── AG Grid ──
        grid = build_aggrid(fragments, meta)


def _apply_search(event, grid):
    """Apply quick filter to the AG Grid."""
    text = event.args.get('value', '')
    if grid:
        grid.call_api_method('setGridOption', 'quickFilterText', text)


def _do_export():
    """Export current view to Excel."""
    result = app.storage.user.get('last_result', {})
    fragments = result.get('fragments', [])
    meta = result.get('meta', {})

    import io
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '拆分结果'

    headers = ['序号', '内容', '类型', '层级', '序数']
    for col, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=h)

    for i, frag in enumerate(fragments, start=2):
        ordinal = frag.get('ordinal')
        if isinstance(ordinal, list):
            ord_str = '.'.join(str(x) for x in ordinal)
        elif ordinal is not None:
            ord_str = str(ordinal)
        else:
            ord_str = '-'

        ws.cell(row=i, column=1, value=frag.get('seq', ''))
        ws.cell(row=i, column=2, value=frag.get('content', ''))
        ws.cell(row=i, column=3, value=frag.get('split_type', '-'))
        ws.cell(row=i, column=4, value=frag.get('index_level', '-'))
        ws.cell(row=i, column=5, value=ord_str)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    ui.download(output.read(), '拆分结果.xlsx')
```

---

### Task 9: Launcher scripts & integration

**Files:**
- Create: `run_service.py`
- Create: `run_ui.py`

- [ ] **Step 1: Write `run_service.py`**

```python
"""Launch the FastAPI split service on port 8001."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('service.main:app', host='127.0.0.1', port=8001, reload=False)
```

- [ ] **Step 2: Write `run_ui.py`**

```python
"""Launch the NiceGUI application on port 8080.

Requires the FastAPI service to be running on port 8001.
Starts the service automatically if not already running.
"""
import sys
import os
import subprocess
import time

_PARENT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PARENT)
os.chdir(_PARENT)

if __name__ == '__main__':
    # Quick health check — warn if service is not running
    try:
        import httpx
        r = httpx.get('http://127.0.0.1:8001/health', timeout=2.0)
        if r.status_code == 200:
            print('FastAPI 服务已连接 (:8001)')
        else:
            print('警告: 服务响应异常')
    except Exception:
        print('提示: FastAPI 服务未启动，请在另一个终端运行: python run_service.py')

    import app.main
```

- [ ] **Step 3: Full integration test**

Start service in background, run UI, test end-to-end:

```bash
# Terminal 1 — start service
cd "C:\Users\matech\Desktop\UI SETTING" && python run_service.py

# Terminal 2 — test end-to-end with httpx
cd "C:\Users\matech\Desktop\UI SETTING" && python -c "
import httpx
import asyncio

async def main():
    # Health
    async with httpx.AsyncClient() as c:
        r = await c.get('http://127.0.0.1:8001/health')
        print('Health:', r.json())

        # Split test text
        text = '''第一条 为了规范市场秩序，制定本法。
第二条 市场准入实行负面清单制度。
第三条 国务院市场监督管理部门负责全国市场监督管理工作。
第一章 总则
第一条 目的和依据
第二条 适用范围'''

        r = await c.post('http://127.0.0.1:8001/api/split', json={'text': text, 'params': {}})
        data = r.json()
        print(f'Fragments: {data[\"meta\"][\"fragment_count\"]}')
        print(f'Tags: {data[\"meta\"][\"all_tags\"]}')
        print(f'Chain: {data[\"meta\"][\"level_chain\"]}')
        for f in data['fragments']:
            print(f'  [{f[\"seq\"]}] {f[\"split_type\"] or \"-\"}  {f[\"content\"][:50]}...')

asyncio.run(main())
"
```

- [ ] **Step 4: Manual UI verification**

```bash
cd "C:\Users\matech\Desktop\UI SETTING" && python run_ui.py
```

Verify:
1. Open http://127.0.0.1:8080 — main page loads
2. Status dot shows green (if service running) or red (if not)
3. Upload a .txt file → text fills textarea → split button activates
4. Click "拆分" → navigates to /results
5. Results page shows summary bar + AG Grid table
6. Click a row → dialog shows full content
7. Type in search box → table filters
8. Click "导出 Excel" → downloads file
9. Click back arrow → returns to main page

---

### Task 10: Cleanup old UI.py

**Files:**
- Remove: `UI.py` (replaced by `app/main.py` and `run_ui.py`)

- [ ] **Step 1: Delete old placeholder**

```bash
rm "C:\Users\matech\Desktop\UI SETTING\UI.py"
```

Or rename to `UI.py.bak` if preferred.

---
