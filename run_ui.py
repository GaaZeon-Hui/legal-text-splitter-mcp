"""Launch the NiceGUI application on port 8080.

Requires the FastAPI service to be running on port 8001.
"""
import sys
import os

_PARENT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PARENT)
os.chdir(_PARENT)

if __name__ == '__main__':
    # Quick health check -- warn if service is not running
    try:
        import httpx
        r = httpx.get('http://127.0.0.1:8001/health', timeout=2.0)
        if r.status_code == 200:
            print('FastAPI 服务已连接 (:8001)')
        else:
            print('警告: 服务响应异常')
    except Exception:
        print('提示: FastAPI 服务未启动，请在另一个终端运行: python run_service.py')

    import app.main
