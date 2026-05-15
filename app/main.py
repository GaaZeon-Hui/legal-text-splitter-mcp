"""NiceGUI application entry point.

Registers pages and launches the UI server.
"""
import os
from nicegui import ui


@ui.page('/')
def index_page():
    """Main page: upload, text editing, params, split trigger."""
    from app.pages.index import build as _build_index
    _build_index()


@ui.page('/test')
def test_page():
    """Diagnostic: test if ui.timer works at all."""
    label = ui.label('waiting...')
    label2 = ui.label('async: waiting...')

    # Test 1: sync timer
    def _sync_update():
        label.set_text('sync timer works!')
        label.classes('text-green')

    ui.timer(1.0, _sync_update, once=True)

    # Test 2: async timer (if this doesn't work, we know why)
    async def _async_update():
        label2.set_text('async timer works!')
        label2.classes('text-green')

    ui.timer(1.5, _async_update, once=True)


@ui.page('/results')
def results_page():
    """Results page: summary bar, AG Grid table, export."""
    from app.pages.results import build as _build_results
    _build_results()


ui.run(
    host='127.0.0.1',
    port=8080,
    title='法规文本拆分系统',
    favicon='📋',
    storage_secret='split-ui-secret-v1',
    reload=False,
    show=os.environ.get('UI_NO_BROWSER', '').lower() != 'true',
)
