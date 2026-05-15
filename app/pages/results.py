"""Results page: summary bar, table rendered by pretext (JS) for clean typography."""
import json
from nicegui import app, ui


FONT_STACK = (
    '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", '
    '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'
)


def build():
    result = app.storage.user.get('last_result')
    if not result:
        with ui.column().classes('w-full items-center p-8'):
            ui.label('没有拆分结果，请返回主页重新拆分').classes('text-lg text-grey')
            ui.button('返回主页', on_click=lambda: ui.navigate.to('/'))
        return

    fragments = result.get('fragments', [])
    meta = result.get('meta', {})

    with ui.header().classes('bg-primary text-white'):
        with ui.row().classes('w-full items-center justify-between p-2'):
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')) \
                    .props('flat text-white')
                ui.label('拆分结果').classes('text-xl font-bold')
            ui.button('导出 Excel', icon='download', on_click=lambda: _do_export()) \
                .props('flat text-white')

    with ui.column().classes('w-full p-4 gap-4'):
        with ui.row().classes('w-full flex-wrap gap-4 items-center bg-grey-1 p-3 rounded-lg'):
            ui.label(f'字符数: {meta.get("char_count", 0):,}').classes('text-sm')
            ui.label(f'片段数: {meta.get("fragment_count", 0):,}').classes('text-sm font-bold')
            ui.label(f'类型: {", ".join(meta.get("all_tags", [])) or "-"}').classes('text-sm')
            ui.label(f'层级: {meta.get("level_chain", "-")}').classes('text-sm')
            ui.label(f'耗时: {meta.get("processing_ms", 0)}ms').classes('text-sm')
            ui.label(f'算法: {meta.get("algorithm", "-")}').classes('text-sm')

        if fragments:
            _build_pretext_table(fragments)
        else:
            ui.label('未能拆分出片段').classes('text-grey')


def _build_pretext_table(fragments):
    rows_js = []
    detail_map = {}
    for f in fragments:
        seq = f.get('seq', '')
        content = f.get('content', '')
        st = f.get('split_type') or '-'
        il = f.get('index_level')
        il_str = str(il) if il is not None else '-'
        ord_val = _fmt_ordinal(f.get('ordinal'))
        rows_js.append([seq, content, st, il_str, ord_val])
        detail_map[str(seq)] = {'s': seq, 't': st, 'c': content}

    rows_json = json.dumps(rows_js, ensure_ascii=False)
    detail_json = json.dumps(detail_map, ensure_ascii=False)
    font_stack = FONT_STACK

    html = (
        '<div id="pt-root" style="width:100%;overflow:hidden"></div>'
        '<link rel="stylesheet"'
        ' href="https://fonts.googleapis.com/css2?family=Inter:400,500,600&display=swap">'
        '<style>'
        f'.pt{{width:100%;border-collapse:collapse;table-layout:fixed;'
        f'font-family:{font_stack};font-size:15px;line-height:1.55;'
        f'-webkit-font-smoothing:antialiased;color:#1a1a1a}}'
        '.pt th{padding:0 0 10px 0;text-align:left;font-weight:500;font-size:12px;'
        'color:#999;border-bottom:1px solid #e0e0e0}'
        '.pt td{padding:10px 0;text-align:left;border-bottom:1px solid #f2f2f2;'
        'overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'
        '.pt tbody tr{cursor:pointer}'
        '.pt tbody tr:hover td{color:#000}'
        '.pt-s{width:36px;padding-left:4px!important}'
        '.pt-t{width:64px}.pt-l{width:40px}.pt-o{width:76px}'
        '</style>'
        '<script type="module">'
        f'const ROWS = {rows_json};'
        f'const DETAIL = {detail_json};'
        f'const FONT = "15px {font_stack}";'
        'function esc(s){var t=document.createElement("span");t.textContent=String(s);return t.innerHTML}'
        'function _truncIdx(mod,text,font,mw){'
        '  var lo=0,hi=text.length;var p=mod.prepare,l=mod.layout;'
        '  while(lo<hi){var mid=Math.ceil((lo+hi)/2);'
        '    if(l(p(text.substring(0,mid),font),mw,23).height<=23)lo=mid;else hi=mid-1}'
        '  return lo}'
        'async function init(){'
        '  var mod=null;'
        '  try{mod=await import("/static/pretext-layout.js")}catch(e){console.warn("pretext:",e)}'
        '  var root=document.getElementById("pt-root");if(!root)return;'
        '  var cw=root.clientWidth-36-64-40-76-28;'
        '  var engine=null;'
        '  if(mod&&cw>=80){'
        '    var plan=[];'
        '    for(var i=0;i<ROWS.length;i++){'
        '      plan.push({idx:i,prep:mod.prepare(String(ROWS[i][1]),FONT)})}'
        '    engine={mod:mod,plan:plan}}'
        '  render(root,cw,engine)}'
        'function render(root,cw,engine){'
        '  var h="<table class=\\"pt\\"><thead><tr>"'
        '    +"<th class=\\"pt-s\\">#</th><th>内容</th>"'
        '    +"<th class=\\"pt-t\\">类型</th><th class=\\"pt-l\\">层级</th>"'
        '    +"<th class=\\"pt-o\\">序数</th></tr></thead><tbody>";'
        '  for(var i=0;i<ROWS.length;i++){'
        '    var r=ROWS[i];var display;'
        '    if(engine){'
        '      var pi=engine.plan[i];'
        '      var lr=engine.mod.layout(pi.prep,cw,23);'
        '      if(lr.lineCount<=1&&lr.height<=23){display=r[1]}'
        '      else{var f=String(r[1]).split("\\n")[0];'
        '        display=f.substring(0,_truncIdx(engine.mod,f,FONT,cw))+"…"}}'
        '    else{display=String(r[1]).split("\\n")[0]||""}'
        '    h+="<tr data-seq=\\""+esc(String(r[0]))+"\\">"'
        '      +"<td class=\\"pt-s\\">"+esc(r[0])+"</td>"'
        '      +"<td>"+esc(display)+"</td>"'
        '      +"<td class=\\"pt-t\\">"+esc(r[2])+"</td>"'
        '      +"<td class=\\"pt-l\\">"+esc(r[3])+"</td>"'
        '      +"<td class=\\"pt-o\\">"+esc(r[4])+"</td>"'
        '      +"</tr>"'
        '  }'
        '  h+="</tbody></table>";'
        '  root.innerHTML=h;'
        '  root.querySelector("tbody").addEventListener("click",function(e){'
        '    var tr=e.target.closest("tr");if(!tr)return;'
        '    var d=DETAIL[tr.dataset.seq];if(d)window.__pd=d})}'
        'init();'
        '</script>'
    )

    ui.html(html).classes('w-full')

    async def _check_click():
        try:
            raw = await ui.run_javascript(
                'var x=__pd;__pd=null;return x ? JSON.stringify(x) : null',
                timeout=0.3)
        except Exception:
            raw = None
        if raw:
            data = json.loads(raw)
            with ui.dialog() as dialog, ui.card().classes('p-4 max-w-3xl'):
                ui.label(f'片段 #{data.get("s","?")}').classes('text-lg font-bold')
                ui.label(f'类型: {data.get("t","-")}').classes('text-sm text-grey')
                ui.separator()
                ui.markdown(data.get('c', '')).classes('whitespace-pre-wrap max-h-96 overflow-auto')
                with ui.row().classes('justify-end'):
                    ui.button('关闭', on_click=dialog.close)
            dialog.open()

    ui.timer(0.3, _check_click)


def _fmt_ordinal(ordinal):
    if isinstance(ordinal, list):
        return '.'.join(str(x) for x in ordinal)
    if ordinal is not None:
        return str(ordinal)
    return '-'


def _do_export():
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
    for col, h in enumerate(['序号', '内容', '类型', '层级', '序数'], start=1):
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
