"""NiceGUI application entry point.

Registers pages, starts the health poll timer,
and launches the UI server.
"""
import asyncio
import os
from nicegui import app, ui

from app.components.service_client import client as svc

SERVICE_URL = 'http://127.0.0.1:8001'
HEALTH_POLL_SECONDS = 5.0


# Global service status — read by index.py for the status indicator
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
    pass


@app.get('/api/visibility/visible')
async def visibility_visible():
    global service_online
    service_online = await svc.health()


ui.run(
    host='127.0.0.1',
    port=8080,
    title='法规文本拆分系统',
    favicon='📋',
    storage_secret='split-ui-secret-v1',
    reload=False,
    show=os.environ.get('UI_NO_BROWSER', '').lower() != 'true',
)
