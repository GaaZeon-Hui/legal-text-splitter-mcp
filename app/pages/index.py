"""Main page: file upload, text editing, parameters, and split trigger."""
from nicegui import app, ui

from app.components.file_upload import FileUpload
from app.components.service_client import client as svc, ServiceError


def build():
    """Build the main page layout."""
    # -- State --
    current_text = ''

    # -- Header --
    with ui.header().classes('bg-primary text-white'):
        with ui.row().classes('w-full items-center justify-between p-2'):
            ui.label('法规文本拆分系统').classes('text-xl font-bold')
            _status_dot = ui.element('span').classes('w-3 h-3 rounded-full')
            _status_label = ui.label('检测中…').classes('text-sm')

            # Update status from module-level service_online
            ui.timer(1.0, lambda: _update_status(_status_dot, _status_label))

    # -- Main content --
    with ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-4'):

        def on_text_change(text):
            nonlocal current_text
            current_text = text
            _split_btn.enabled = bool(text.strip()) and _get_service_online()

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

        # -- Loading indicator (hidden by default) --
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
