"""Main page: file upload, text editing, parameters, and split trigger."""
import asyncio
from nicegui import app, background_tasks, ui

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

        uploader = FileUpload(on_text_changed=on_text_change)

        # -- Parameters (collapsible) --
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

    # -- Health check (debug: hardcode first, then real) --
    async def _check_health():
        nonlocal service_online
        _status_label.set_text('timer fired')
        service_online = await svc.health()
        if service_online:
            _status_dot.classes(remove='bg-red')
            _status_dot.classes(add='bg-green')
            _status_label.set_text('服务已连接')
        else:
            _status_dot.classes(remove='bg-green')
            _status_dot.classes(add='bg-red')
            _status_label.set_text('服务断开')
        _split_btn.enabled = bool(current_text.strip()) and service_online

    ui.timer(2.0, _check_health)

    # -- Actions --
    def _on_key(e):
        if e.key == 'enter' and e.action == 'keydown' and e.modifiers.get('ctrl'):
            nonlocal current_text
            if current_text.strip() and service_online:
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
