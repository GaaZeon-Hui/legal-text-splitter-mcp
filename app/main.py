"""NiceGUI application entry point.

Registers pages, starts the health poll timer,
and launches the UI server.
"""
import asyncio
import os
from nicegui import app, background_tasks, ui

from app.components.service_client import client as svc

SERVICE_URL = 'http://127.0.0.1:8001'
HEALTH_POLL_SECONDS = 5.0

# Global service status — read by index.py for the status indicator
service_online = False


async def _health_poll_loop():
    """Background task that polls /health periodically."""
    global service_online
    while True:
        service_online = await svc.health()
        await asyncio.sleep(HEALTH_POLL_SECONDS)


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
    # Initial health check (fire-and-forget, won't block page loads)
    background_tasks.create(_health_poll_loop(), name='health-poll')


ui.run(
    host='127.0.0.1',
    port=8080,
    title='法规文本拆分系统',
    favicon='📋',
    storage_secret='split-ui-secret-v1',
    reload=False,
    show=os.environ.get('UI_NO_BROWSER', '').lower() != 'true',
)
