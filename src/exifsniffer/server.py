"""FastMCP server: Streamable HTTP transport and ExifSniffer tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from exifsniffer.exif_edit import update_image_exif
from exifsniffer.extract import extract_metadata_list, flatten_to_metadata_list
from exifsniffer.fetch import download_url_to_path
from exifsniffer.local_media import list_image_relative_paths, require_local_media_root
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

GET_LOCAL_MEDIA_SCOPE_DESCRIPTION = (
    "Report whether LOCAL_MEDIA_ROOT is configured for host-scoped media. When set, it is the "
    "absolute directory (usually a Docker bind mount) inside the server filesystem; all other "
    "local media tools accept paths relative to that root with no '..' segments. Returns the same "
    "flat JSON list shape as other tools."
)

LIST_LOCAL_MEDIA_IMAGES_DESCRIPTION = (
    "List image files under LOCAL_MEDIA_ROOT. Parameter relative_directory is relative to that "
    "root (empty string means the root itself). Set recursive true to include subfolders. "
    "Respects max_files (default 500, hard cap 5000). Returns a JSON list of rows with path "
    "local_media.images[i] and value as the relative POSIX path under LOCAL_MEDIA_ROOT."
)

EXTRACT_LOCAL_MEDIA_METADATA_DESCRIPTION = (
    "Like extract_metadata_to_json but the source file lives under LOCAL_MEDIA_ROOT "
    "(source_relative_path is relative to that root). The JSON output is still written under "
    "DATA_DIR via output_json_relative_path. Requires LOCAL_MEDIA_ROOT to be set."
)

UPDATE_LOCAL_MEDIA_EXIF_DESCRIPTION = (
    "Update or remove EXIF tags on a JPEG or WebP file under LOCAL_MEDIA_ROOT (piexif). "
    "image_relative_path is relative to LOCAL_MEDIA_ROOT. set_tags maps IFD names "
    "(0th, Exif, GPS, Interop, 1st) to objects mapping Exif tag names (e.g. Copyright, "
    "ImageDescription) to new values; strings are stored as UTF-8 bytes. For Exif.UserComment "
    "with a string value, Unicode EXIF user comment encoding is applied. remove_tags maps IFD "
    "names to lists of tag names to delete. The file is modified in place on disk. "
    "Other image formats are not supported for writes; use extract for read-only metadata."
)


mcp = FastMCP(
    name="exif-sniffer",
    instructions=(
        "ExifSniffer downloads remote media and extracts EXIF/metadata as a flat JSON list of "
        "path/value entries. When LOCAL_MEDIA_ROOT is set, additional tools read and update EXIF on "
        "files under that host bind-mounted directory using paths relative to that root. "
        "Tools return JSON-compatible lists, not narrative reports."
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


@mcp.tool(name="get_local_media_scope", description=GET_LOCAL_MEDIA_SCOPE_DESCRIPTION)
async def get_local_media_scope() -> list[dict[str, Any]]:
    settings = load_settings()
    raw = settings.local_media_root
    if not raw:
        return flatten_to_metadata_list(
            {"configured": False, "local_media_root": None},
            prefix="local_media",
        )
    root = Path(raw).expanduser().resolve()
    summary = {
        "configured": True,
        "local_media_root": raw,
        "resolved_root": str(root),
        "exists_and_is_dir": root.is_dir(),
    }
    return flatten_to_metadata_list(summary, prefix="local_media")


@mcp.tool(name="list_local_media_images", description=LIST_LOCAL_MEDIA_IMAGES_DESCRIPTION)
async def list_local_media_images(
    relative_directory: Annotated[
        str,
        Field(
            description="Directory relative to LOCAL_MEDIA_ROOT to scan (use '' for the root).",
        ),
    ] = "",
    recursive: Annotated[
        bool,
        Field(description="If true, include images in nested subdirectories."),
    ] = False,
    max_files: Annotated[
        int,
        Field(ge=1, le=5000, description="Maximum number of image paths to return."),
    ] = 500,
) -> list[dict[str, Any]]:
    settings = load_settings()
    root = require_local_media_root(settings)
    rels = list_image_relative_paths(
        root,
        relative_directory,
        recursive=recursive,
        max_files=max_files,
    )
    rows: list[dict[str, Any]] = []
    for i, rel in enumerate(rels):
        rows.append({"path": f"local_media.images[{i}]", "value": rel})
    return rows


@mcp.tool(name="extract_local_media_metadata_to_json", description=EXTRACT_LOCAL_MEDIA_METADATA_DESCRIPTION)
async def extract_local_media_metadata_to_json(
    source_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Path relative to LOCAL_MEDIA_ROOT to an image or video file.",
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
    local_root = require_local_media_root(settings)
    data_root = Path(settings.data_dir)
    src = resolve_under_root(local_root, source_relative_path)
    out = resolve_under_root(data_root, output_json_relative_path)
    rows = extract_metadata_list(src, include_piexif=include_piexif)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return rows


@mcp.tool(name="update_local_media_exif", description=UPDATE_LOCAL_MEDIA_EXIF_DESCRIPTION)
async def update_local_media_exif(
    image_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Path relative to LOCAL_MEDIA_ROOT to a .jpg, .jpeg, or .webp file.",
        ),
    ],
    set_tags: Annotated[
        dict[str, dict[str, Any]] | None,
        Field(
            description=(
                "Map of IFD name to tag map, e.g. {\"0th\": {\"Copyright\": \"2026 Example\"}}. "
                "Omit or pass null for no additions/updates."
            ),
        ),
    ] = None,
    remove_tags: Annotated[
        dict[str, list[str]] | None,
        Field(
            description='Map of IFD name to list of tag names to remove, e.g. {"Exif": ["UserComment"]}. '
            "Omit or pass null for no removals.",
        ),
    ] = None,
) -> list[dict[str, Any]]:
    settings = load_settings()
    local_root = require_local_media_root(settings)
    src = resolve_under_root(local_root, image_relative_path)
    summary = update_image_exif(
        src,
        set_tags=set_tags or {},
        remove_tags=remove_tags or {},
    )
    return flatten_to_metadata_list(summary, prefix="local_media.exif_update")
