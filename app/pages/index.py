"""Main page: file upload, text editing, parameters, and split trigger."""
from nicegui import app, ui

from app.components.file_upload import FileUpload
from app.components.service_client import client as svc, ServiceError


def build():
    """Build the main page layout."""
    # -- Per-page state --
    current_text = ''
    service_online = False

    # -- Header --
    with ui.header().classes('bg-primary text-white'):
        with ui.row().classes('w-full items-center justify-between p-2'):
            ui.label('法规文本拆分系统').classes('text-xl font-bold')
            _status_dot = ui.element('span').classes('w-3 h-3 rounded-full')
            _status_label = ui.label('检测中…').classes('text-sm')

    # -- Main content --
    with ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-4'):

        def on_text_change(text):
            nonlocal current_text
            current_text = text
            _split_btn.enabled = bool(text.strip()) and service_online

        current_law_ids = []

        def on_law_ids_changed(law_ids):
            nonlocal current_law_ids
            current_law_ids = law_ids
            _split_btn.enabled = bool(law_ids) and service_online
            _split_btn.props('label=批量拆分')

        uploader = FileUpload(on_text_changed=on_text_change,
                              on_law_ids_changed=on_law_ids_changed)

        # -- Split button --
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

        # -- Loading indicator --
        _spinner = ui.spinner(size='lg').classes('hidden')

    # -- Health poll --
    async def _check_health():
        nonlocal service_online
        service_online = await svc.health()
        if service_online:
            _status_dot.classes(remove='bg-red')
            _status_dot.classes('bg-green')
            _status_label.set_text('服务已连接')
        else:
            _status_dot.classes(remove='bg-green')
            _status_dot.classes('bg-red')
            _status_label.set_text('服务断开')
        _split_btn.enabled = bool(current_text.strip() or current_law_ids) and service_online

    ui.timer(5.0, _check_health)

    # -- Actions --
    def _on_key(e):
        if e.key == 'enter' and e.action == 'keydown' and e.modifiers.get('ctrl'):
            nonlocal current_text
            if current_text.strip() and service_online:
                _do_split()

    async def _do_split():
        nonlocal current_text, current_law_ids
        text = current_text.strip()
        law_ids = current_law_ids

        if not text and not law_ids:
            return

        _split_btn.visible = False
        _spinner.classes(remove='hidden')

        try:
            if law_ids:
                batch_result = await svc.split_by_ids(law_ids)
                from datetime import datetime
                default_name = datetime.now().strftime('%m%d%H%M')
                filename = await _ask_filename(default_name)
                if filename is None:
                    return
                excel_bytes = _build_batch_excel(batch_result)
                ui.download(excel_bytes, f'{filename}.xlsx')
                ui.notify(f'已导出 {len(batch_result["results"])} 条结果', type='positive')
            else:
                result = await svc.split(text)
                app.storage.user['last_result'] = result
                app.storage.user['last_text'] = text
                ui.navigate.to('/results')

        except ServiceError as e:
            ui.notify(str(e), type='negative')
        except Exception as e:
            ui.notify(f'请求失败: {e}', type='negative')
        finally:
            _split_btn.visible = True
            _spinner.classes('hidden')


async def _ask_filename(default_name: str) -> str | None:
    """Show dialog asking for Excel filename."""
    result = {'name': None}

    with ui.dialog() as dialog, ui.card().classes('p-4'):
        ui.label('保存 Excel 文件').classes('text-lg font-bold')
        name_input = ui.input('文件名', value=default_name).classes('w-full')
        with ui.row().classes('gap-2 mt-2'):
            ui.button('确定', on_click=lambda: _set_and_close(name_input.value))
            ui.button('取消', on_click=lambda: dialog.close())

        def _set_and_close(val):
            result['name'] = val
            dialog.close()

    await dialog
    return result['name']


def _build_batch_excel(batch_result: dict) -> bytes:
    """Build Excel from batch results, matching engine _write_excel format."""
    import io
    import openpyxl

    wb = openpyxl.Workbook()

    ws_a = wb.active
    ws_a.title = '拆分类型分析'
    a_headers = ['law_id', '文本长度', '脊椎类型', '脊椎maxN',
                 '附生类型', '附生组数', '全部标签', '最终拆分类型',
                 '拆分片段数', '字符数', '段落数', '错误信息']
    for col, h in enumerate(a_headers, start=1):
        ws_a.cell(row=1, column=col, value=h)

    ws_s = wb.create_sheet('拆分结果')
    s_headers = ['组', '序号', '内容', '保留列', '索引级别']
    for col, h in enumerate(s_headers, start=1):
        ws_s.cell(row=1, column=col, value=h)

    row_a = 2
    row_s = 2
    for r in batch_result['results']:
        lid = r['law_id']
        a = r.get('analysis') or {}
        meta = r.get('meta') or {}
        error = r.get('error', '')

        ws_a.cell(row=row_a, column=1, value=lid)
        ws_a.cell(row=row_a, column=2, value=a.get('char_count', 0))
        ws_a.cell(row=row_a, column=3, value=', '.join(a.get('spine_types', [])))
        ws_a.cell(row=row_a, column=4, value=a.get('max_n', 0))
        ws_a.cell(row=row_a, column=5, value=', '.join(a.get('satellite_types', [])))
        ws_a.cell(row=row_a, column=6, value=a.get('max_gc', 0))
        ws_a.cell(row=row_a, column=7, value=', '.join(a.get('all_tags', [])))
        ws_a.cell(row=row_a, column=8, value=', '.join(meta.get('all_tags', [])))
        ws_a.cell(row=row_a, column=9, value=meta.get('fragment_count', 0))
        ws_a.cell(row=row_a, column=10, value=a.get('char_count', 0))
        ws_a.cell(row=row_a, column=11, value=a.get('para_count', 0))
        ws_a.cell(row=row_a, column=12, value=error)
        row_a += 1

        for frag in r.get('fragments', []):
            ws_s.cell(row=row_s, column=1, value=lid)
            ws_s.cell(row=row_s, column=2, value=frag.get('seq', ''))
            ws_s.cell(row=row_s, column=3, value=frag.get('content', ''))
            ws_s.cell(row=row_s, column=4, value='')
            il = frag.get('index_level')
            ws_s.cell(row=row_s, column=5, value=il if il is not None else '')
            row_s += 1

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()
