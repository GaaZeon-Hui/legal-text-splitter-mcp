"""Results page: summary bar, AG Grid table, search, export."""
from nicegui import app, ui

from app.components.aggrid_table import build_aggrid


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

        # -- Search bar --
        search_input = ui.input(
            '搜索片段内容',
            placeholder='输入关键词…',
        ).classes('w-64')

        # -- AG Grid --
        grid = build_aggrid(fragments, meta)

        # Wire search to AG Grid quickFilter
        search_input.on('keydown',
            lambda e: grid.call_api_method('setGridOption', 'quickFilterText', e.args.get('value', '')),
            throttle=0.3)


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
