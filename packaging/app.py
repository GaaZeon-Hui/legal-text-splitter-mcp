"""Desktop app entry point.

Runs the FastAPI service in a daemon thread, then opens a native
desktop window (pywebview) instead of a browser tab.

Usage:
    python packaging/app.py
"""
import sys
import os
import time
import threading
import asyncio
import signal
import atexit

if getattr(sys, 'frozen', False):
    _PARENT = sys._MEIPASS
else:
    _PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
SERVICE_HOST = '127.0.0.1'
SERVICE_PORT = 8001
HEALTH_URL = f'http://{SERVICE_HOST}:{SERVICE_PORT}/health'

_server = None


def _run_service():
    """Run the FastAPI service in a daemon thread with explicit event loop."""
    global _server
    if _PARENT not in sys.path:
        sys.path.insert(0, _PARENT)
    os.chdir(_PARENT)
    import uvicorn

    config = uvicorn.Config('service.main:app', host=SERVICE_HOST,
                            port=SERVICE_PORT, log_level='warning')
    _server = uvicorn.Server(config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_server.serve())


def _stop_service():
    """Signal the service to stop gracefully."""
    global _server
    if _server is not None:
        _server.should_exit = True


def _wait_for_service(timeout=15):
    import urllib.request, urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(HEALTH_URL, timeout=2)
            if r.status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.3)
    return False


def main():
    _svc_thread = threading.Thread(target=_run_service, daemon=False)
    _svc_thread.start()

    if not _wait_for_service():
        print('Service failed to start')
        sys.exit(1)

    def _shutdown():
        _stop_service()
        _svc_thread.join(timeout=3)

    atexit.register(_shutdown)
    signal.signal(signal.SIGINT, lambda s, f: (_shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda s, f: (_shutdown(), sys.exit(0)))

    # Launch NiceGUI in native desktop window
    from nicegui import ui, app as nice_app

    @ui.page('/')
    def index_page():
        from app.pages.index import build as _build_index
        _build_index()

    @ui.page('/results')
    def results_page():
        from app.pages.results import build as _build_results
        _build_results()

    import fastapi.staticfiles
    nice_app.mount('/static',
                   fastapi.staticfiles.StaticFiles(
                       directory=os.path.join(_PARENT, 'static')))

    nice_app.on_shutdown(_shutdown)

    ui.run(
        host=SERVICE_HOST,
        port=8080,
        title='法规文本拆分系统',
        favicon='📋',
        storage_secret='split-ui-secret-v1',
        reload=False,
        show=False,
        native=True,
        window_size=(1200, 800),
    )


if __name__ == '__main__':
    main()
