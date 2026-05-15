"""Results page: summary bar, table, search, export."""
from nicegui import app, ui


def build():
    """Build the results page from data in app.storage.user."""
    result = app.storage.user.get('last_result')
    if not result:
        with ui.column().classes('w-full items-center p-8'):
            ui.label('没有拆分结果，请返回主页重新拆分').classes('text-lg text-grey')
            ui.button('返回主页', on_click=lambda: ui.navigate.to('/'))
        return

    fragments = result.get('fragments', [])
    meta = result.get('meta', {})

    # -- Header --
    with ui.header().classes('bg-primary text-white'):
        with ui.row().classes('w-full items-center justify-between p-2'):
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')) \
                    .props('flat text-white')
                ui.label('拆分结果').classes('text-xl font-bold')
            ui.button('导出 Excel', icon='download', on_click=lambda: _do_export()) \
                .props('flat text-white')

    with ui.column().classes('w-full p-4 gap-4'):
        # -- Summary bar --
        with ui.row().classes('w-full flex-wrap gap-4 items-center bg-grey-1 p-3 rounded-lg'):
            ui.label(f'字符数: {meta.get("char_count", 0):,}').classes('text-sm')
            ui.label(f'片段数: {meta.get("fragment_count", 0):,}').classes('text-sm font-bold')
            ui.label(f'类型: {", ".join(meta.get("all_tags", [])) or "-"}').classes('text-sm')
            ui.label(f'层级: {meta.get("level_chain", "-")}').classes('text-sm')
            ui.label(f'耗时: {meta.get("processing_ms", 0)}ms').classes('text-sm')
            ui.label(f'算法: {meta.get("algorithm", "-")}').classes('text-sm')

        # -- Truncation CSS --
        ui.add_css('''
        .result-table .q-table tbody td {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 0;
            text-align: left;
        }
        .result-table .q-table tbody tr {
            height: 32px;
        }
        ''')

        # -- Table --
        if fragments:
            full_content = {}
            rows = []
            for f in fragments:
                seq = f.get('seq', '')
                content = f.get('content', '')
                full_content[seq] = content
                first_line = content.split('\n')[0].strip() if content else ''
                rows.append({
                    'seq': seq,
                    'content': first_line,
                    'split_type': f.get('split_type') or '-',
                    'index_level': f.get('index_level', '-'),
                    'ordinal': _fmt_ordinal(f.get('ordinal')),
                    # Pass full content to dialog via closure
                })

            table = ui.table(
                columns=[
                    {'name': 'seq', 'label': '序号', 'field': 'seq',
                     'style': 'width:50px;text-align:left'},
                    {'name': 'content', 'label': '内容', 'field': 'content',
                     'style': 'text-align:left'},
                    {'name': 'split_type', 'label': '类型', 'field': 'split_type',
                     'style': 'width:70px;text-align:left'},
                    {'name': 'index_level', 'label': '层级', 'field': 'index_level',
                     'style': 'width:50px;text-align:left'},
                    {'name': 'ordinal', 'label': '序数', 'field': 'ordinal',
                     'style': 'width:70px;text-align:left'},
                ],
                rows=rows, row_key='seq',
            ).classes('w-full result-table')

            # Double-click row → dialog
            async def _row_handler(e):
                row = e.args.get('row', {})
                seq = row.get('seq')
                if seq is None:
                    return
                text = full_content.get(seq, '')
                st = row.get('split_type', '-')
                with ui.dialog() as dialog, ui.card().classes('p-4 max-w-3xl'):
                    ui.label(f'片段 #{seq}').classes('text-lg font-bold')
                    ui.label(f'类型: {st}').classes('text-sm text-grey')
                    ui.separator()
                    ui.markdown(text).classes('whitespace-pre-wrap max-h-96 overflow-auto')
                    with ui.row().classes('justify-end'):
                        ui.button('关闭', on_click=dialog.close)
                dialog.open()

            table.on('rowClick', _row_handler)
        else:
            ui.label('未能拆分出片段').classes('text-grey')


def _fmt_ordinal(ordinal):
    if isinstance(ordinal, list):
        return '.'.join(str(x) for x in ordinal)
    if ordinal is not None:
        return str(ordinal)
    return '-'


def _do_export():
    """Export result data to Excel."""
    result = app.storage.user.get('last_result', {})
    fragments = result.get('fragments', [])

    import io
    try:
        import openpyxl
    except ImportError:
        ui.notify('请安装 openpyxl 以支持导出', type='negative')
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '拆分结果'

    headers = ['序号', '内容', '类型', '层级', '序数']
    for col, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=h)

    for i, frag in enumerate(fragments, start=2):
        ws.cell(row=i, column=1, value=frag.get('seq', ''))
        ws.cell(row=i, column=2, value=frag.get('content', ''))
        ws.cell(row=i, column=3, value=frag.get('split_type', '-'))
        ws.cell(row=i, column=4, value=frag.get('index_level', '-'))
        ws.cell(row=i, column=5, value=_fmt_ordinal(frag.get('ordinal')))

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    ui.download(output.read(), '拆分结果.xlsx')
