"""FastAPI service for legal document splitting.

Endpoints:
    GET  /health     — health check
    POST /api/split  — analyze + split legal text
"""
import asyncio
import os
import sys

_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from service.split_service import split_text as _split_text

app = FastAPI(title='法规文本拆分服务', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:8080'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


class SplitParams(BaseModel):
    algorithm: str = 'scored'
    split_types: list[str] | None = None
    min_fragment_chars: int = 10


class SplitRequest(BaseModel):
    text: str
    params: SplitParams = Field(default_factory=SplitParams)


@app.get('/health')
async def health():
    return {'status': 'ok', 'version': '1.0.0'}


@app.post('/api/split')
async def api_split(request: SplitRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail='文本为空或无法解析')

    try:
        result = await asyncio.to_thread(
            _split_text, request.text, request.params.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'处理失败: {e}')

    return result


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001)
