"""Legal text splitting engine — bundled from 拆分-打包/.

Exports the two entry points used by the MCP server.
"""
import os as _os
import sys as _sys

# Engine files use sibling imports (e.g. from _protection_config import ...)
# and spec_from_file_location — the engine directory must be on sys.path.
_ENGINE_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _ENGINE_DIR not in _sys.path:
    _sys.path.insert(0, _ENGINE_DIR)

from .pipeline_split import process_text, process_single_law
