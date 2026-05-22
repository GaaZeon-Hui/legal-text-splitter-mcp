"""MCP server for legal text splitting.

Exposes two tools:
    split_text        — split raw legal text into fragments (no DB needed)
    split_by_law_ids  — fetch text from DB by law_id, then split each
"""
import asyncio
import os
import sys
import time

from mcp.server.fastmcp import FastMCP

# Ensure engine/ can be imported when running via entry point
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from legal_text_splitter.engine.pipeline_split import (
    process_text,
    process_single_law,
    _get_db_connection,
    infer_type_levels,
    get_ordinal,
)

MAX_FRAGMENTS = 10000

mcp = FastMCP("legal-text-splitter")


def _format_result(engine_result: dict, char_count: int, elapsed_ms: int) -> dict:
    """Convert engine result dict to MCP tool output format."""
    gdata = engine_result["split_results"]

    fragments = []
    for frag in gdata:
        fragments.append({
            "seq": len(fragments) + 1,
            "content": frag.get("content", ""),
            "split_type": frag.get("split_type"),
            "index_level": frag.get("index_level"),
            "ordinal": get_ordinal(frag.get("content", "")),
            "extra": frag.get("extra", ""),
        })

    all_tags = engine_result.get("split_types", [])
    level_chain = "-"
    if all_tags:
        try:
            type_levels = infer_type_levels(gdata)
            chains = [f"{t}({lv})" for t, lv in type_levels.items()]
            level_chain = " > ".join(chains) if chains else "-"
        except Exception:
            pass

    return {
        "fragments": fragments,
        "meta": {
            "char_count": char_count,
            "fragment_count": len(fragments),
            "all_tags": all_tags,
            "level_chain": level_chain,
            "processing_ms": elapsed_ms,
        },
    }


@mcp.tool()
async def split_text(text: str) -> dict:
    """Split Chinese legal text into typed fragments.

    Accepts raw text (may contain HTML), runs the full engine pipeline:
    clean_html -> analyze -> split -> infer levels -> get ordinals.

    Returns fragments with sequence numbers, split types, index levels,
    and ordinals. No database connection required.
    """
    if not text or not text.strip():
        return {"error": "text is empty"}

    t0 = time.time()
    loop = asyncio.get_running_loop()

    def _run():
        result = process_text(text)
        if result["error"]:
            raise RuntimeError(result["error"])
        gdata = result["split_results"]
        if len(gdata) > MAX_FRAGMENTS:
            raise ValueError(
                f"Text too large: {len(gdata)} fragments exceeds limit of {MAX_FRAGMENTS}")
        return result

    try:
        engine_result = await loop.run_in_executor(None, _run)
        elapsed = int((time.time() - t0) * 1000)
        return _format_result(engine_result, len(text), elapsed)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def split_by_law_ids(law_ids: list[str]) -> dict:
    """Split legal texts fetched from database by law_id.

    Opens a DB connection (configured via LEGAL_DB_* env vars),
    fetches raw text for each law_id, and runs the full engine pipeline on each.
    """
    if not law_ids:
        return {"error": "law_ids is empty"}

    loop = asyncio.get_running_loop()

    def _run():
        conn = _get_db_connection()
        try:
            results = []
            for law_id in law_ids:
                engine_result = process_single_law(law_id, conn, quiet=True)
                if engine_result["error"]:
                    results.append({
                        "law_id": law_id,
                        "fragments": [],
                        "meta": {},
                        "error": engine_result["error"],
                    })
                    continue

                gdata = engine_result["split_results"]
                analysis = engine_result.get("analysis") or {}

                fragments = []
                for frag in gdata:
                    fragments.append({
                        "seq": len(fragments) + 1,
                        "content": frag.get("content", ""),
                        "split_type": frag.get("split_type"),
                        "index_level": frag.get("index_level"),
                        "ordinal": get_ordinal(frag.get("content", "")),
                        "extra": frag.get("extra", ""),
                    })

                all_tags = engine_result.get("split_types", [])
                level_chain = "-"
                if all_tags:
                    try:
                        type_levels = infer_type_levels(gdata)
                        chains = [f"{t}({lv})" for t, lv in type_levels.items()]
                        level_chain = " > ".join(chains) if chains else "-"
                    except Exception:
                        pass

                results.append({
                    "law_id": law_id,
                    "fragments": fragments,
                    "meta": {
                        "char_count": analysis.get("char_count", 0),
                        "fragment_count": len(fragments),
                        "all_tags": all_tags,
                        "level_chain": level_chain,
                    },
                })
            return {"results": results}
        finally:
            conn.close()

    try:
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        return {"error": str(e)}


async def main():
    """Entry point for `uvx legal-text-splitter-mcp`."""
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
