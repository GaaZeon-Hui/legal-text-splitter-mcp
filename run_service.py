"""Launch the FastAPI split service on port 8001."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('service.main:app', host='127.0.0.1', port=8001, reload=False)
