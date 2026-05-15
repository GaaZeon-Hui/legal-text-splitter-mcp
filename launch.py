"""One-click launcher for the legal document split system.

Starts the FastAPI service, waits for it to be ready, then launches
the NiceGUI UI. Both processes are cleaned up on exit.

Usage:
    python launch.py        # prints progress, opens browser
    python launch.py --no-browser  # don't open browser automatically
"""
import subprocess
import sys
import os
import time
import signal

_PARENT = os.path.dirname(os.path.abspath(__file__))
SERVICE_HOST = '127.0.0.1'
SERVICE_PORT = 8001
UI_PORT = 8080
HEALTH_URL = f'http://{SERVICE_HOST}:{SERVICE_PORT}/health'
SERVICE_STARTUP_TIMEOUT = 15  # seconds

_service_proc = None


def _start_service():
    """Launch the FastAPI service as a subprocess."""
    global _service_proc
    cmd = [sys.executable, '-m', 'uvicorn', 'service.main:app',
           '--host', SERVICE_HOST, '--port', str(SERVICE_PORT)]
    _service_proc = subprocess.Popen(
        cmd,
        cwd=_PARENT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f'启动分析服务 (pid={_service_proc.pid})...', end='', flush=True)


def _wait_for_service(timeout=SERVICE_STARTUP_TIMEOUT):
    """Poll /health until the service responds or timeout expires."""
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(HEALTH_URL, timeout=2)
            if r.status == 200:
                print(' 就绪')
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.3)
        print('.', end='', flush=True)
    print(' 超时')
    return False


def _stop_service():
    """Terminate the service subprocess."""
    global _service_proc
    if _service_proc is None:
        return
    try:
        _service_proc.terminate()
        _service_proc.wait(timeout=5)
        print('分析服务已停止')
    except subprocess.TimeoutExpired:
        _service_proc.kill()
        _service_proc.wait()
        print('分析服务已强制停止')
    except Exception:
        pass


def _cleanup():
    """Cleanup handler — called on normal exit and SIGINT."""
    _stop_service()


def main():
    show_browser = '--no-browser' not in sys.argv

    print('=' * 50)
    print('  法规文本拆分系统')
    print('=' * 50)

    # 1. Start service
    _start_service()

    # 2. Wait for ready
    if not _wait_for_service():
        print('错误: 分析服务启动失败')
        _stop_service()
        sys.exit(1)

    # 3. Register cleanup
    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda sig, frame: (_cleanup(), sys.exit(0)))

    # 4. Suppress browser if requested
    if not show_browser:
        os.environ['UI_NO_BROWSER'] = 'true'

    # 5. Launch UI (ui.run() is called at module level in app/main.py, blocks until quit)
    try:
        print(f'启动界面 http://{SERVICE_HOST}:{UI_PORT}')
        sys.path.insert(0, _PARENT)
        os.chdir(_PARENT)
        import app.main
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup()


if __name__ == '__main__':
    main()
