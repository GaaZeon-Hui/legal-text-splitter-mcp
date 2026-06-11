"""NiceGUI application entry point.

Registers pages and launches the UI server.
"""
import os
from nicegui import app, ui
from fastapi.staticfiles import StaticFiles


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


app.mount('/static', StaticFiles(directory='static'))

ui.run(
    host='127.0.0.1',
    port=8080,
    title='法规文本拆分系统',
    favicon='📋',
    storage_secret='split-ui-secret-v1',
    reload=False,
    show=os.environ.get('UI_NO_BROWSER', '').lower() != 'true',
)
