"""FastMCP server: Streamable HTTP transport and ExifSniffer tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from exifsniffer.extract import extract_metadata_list, flatten_to_metadata_list
from exifsniffer.fetch import download_url_to_path
from exifsniffer.paths import resolve_under_root
from exifsniffer.settings import load_settings

FETCH_REMOTE_MEDIA_DESCRIPTION = (
    "Download an image or video from an HTTP(S) URL and save it under the server data directory "
    "(DATA_DIR, default /data). Use this first when the user provides a web URL and you need a "
    "local file path for metadata extraction. Validates the URL, blocks SSRF to private/reserved "
    "networks (unless FETCH_ALLOW_PRIVATE_HOSTS is set), follows redirects up to FETCH_MAX_REDIRECTS, "
    "and enforces MAX_DOWNLOAD_BYTES. Parameter destination_relative_path must be relative to "
    "DATA_DIR with no '..' segments (e.g. incoming/photo.jpg). Returns a JSON array (list) of "
    "metadata rows: each item is an object with string keys path and value describing the download "
    "result (saved_path, final_url, bytes_written, etc.)."
)

EXTRACT_METADATA_DESCRIPTION = (
    "Read a local image or video file under DATA_DIR, extract EXIF (Pillow), PNG tEXt and zTXt "
    "text chunks (keyword/text pairs under image.png_text_chunks), or container metadata (ffprobe "
    "JSON for video), and write a JSON file that is a single array of objects. Each array element "
    "has path (dot/bracket path into the extracted tree) and value (string, number, or nested "
    "JSON-serializable data for leaves). The tool response is the same array. Use include_piexif "
    "true for extra JPEG piexif sections. Output file is UTF-8 JSON array format."
)


mcp = FastMCP(
    name="exif-sniffer",
    instructions=(
        "ExifSniffer downloads remote media and extracts EXIF/metadata as a flat JSON list of "
        "path/value entries. Tools return JSON-compatible lists, not narrative reports."
    ),
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "3000")),
    stateless_http=True,
    streamable_http_path="/mcp",
    json_response=False,
)


@mcp.tool(name="fetch_remote_media", description=FETCH_REMOTE_MEDIA_DESCRIPTION)
async def fetch_remote_media(
    url: Annotated[
        str,
        Field(
            min_length=8,
            description="Absolute http(s) URL of an image or video to download.",
        ),
    ],
    destination_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Relative path under DATA_DIR where the file will be written (e.g. incoming/file.jpg).",
        ),
    ],
) -> list[dict[str, Any]]:
    settings = load_settings()
    root = Path(settings.data_dir)
    dest = resolve_under_root(root, destination_relative_path)
    meta = await download_url_to_path(url, dest, settings)
    summary: dict[str, Any] = {
        "saved_path": str(dest),
        **meta,
    }
    return flatten_to_metadata_list(summary, prefix="fetch")


@mcp.tool(name="extract_metadata_to_json", description=EXTRACT_METADATA_DESCRIPTION)
async def extract_metadata_to_json(
    source_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Relative path under DATA_DIR to an image or video file.",
        ),
    ],
    output_json_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Relative path under DATA_DIR for the output .json file (created/overwritten).",
        ),
    ],
    include_piexif: Annotated[
        bool,
        Field(
            description="If true, include a piexif section for JPEG (more rows).",
        ),
    ] = False,
) -> list[dict[str, Any]]:
    settings = load_settings()
    root = Path(settings.data_dir)
    src = resolve_under_root(root, source_relative_path)
    out = resolve_under_root(root, output_json_relative_path)
    rows = extract_metadata_list(src, include_piexif=include_piexif)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return rows
