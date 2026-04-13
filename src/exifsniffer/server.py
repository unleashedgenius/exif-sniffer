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
from exifsniffer.filesystem_access import (
    fs_create_directory,
    fs_extract_metadata,
    fs_list_files,
    fs_read_file,
    fs_write_file,
    fs_write_metadata,
)
from exifsniffer.local_media import list_image_relative_paths, parse_local_media_root
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

VALIDATE_LOCAL_MEDIA_ROOT_DESCRIPTION = (
    "Check whether local_media_root is usable: must be an absolute path to an existing directory "
    "on the server (e.g. a Docker bind mount visible inside the container). Returns a flat JSON "
    "list with local_media.usable (boolean), local_media.resolved_root, and local_media.error "
    "when unusable."
)

LIST_LOCAL_MEDIA_IMAGES_DESCRIPTION = (
    "List image files under the given local_media_root (absolute directory path). "
    "Parameter relative_directory is relative to that root (empty string means the root itself). "
    "Set recursive true to include subfolders. Respects max_files (default 500, hard cap 5000). "
    "Returns a JSON list of rows with path local_media.images[i] and value as the relative POSIX "
    "path under local_media_root."
)

EXTRACT_LOCAL_MEDIA_METADATA_DESCRIPTION = (
    "Like extract_metadata_to_json but the source file lives under local_media_root "
    "(source_relative_path is relative to that root). The JSON output is still written under "
    "DATA_DIR via output_json_relative_path."
)

LIST_FILES_FS_DESCRIPTION = (
    "List files and subdirectories in the top level of the configured base directory "
    "(environment LOCAL_MEDIA_BASE), matching the LM Studio filesystem-access plugin. "
    "Returns JSON rows; set LOCAL_MEDIA_BASE to an absolute path (same role as plugin "
    "field Base Directory / folderName)."
)

READ_FILE_FS_DESCRIPTION = (
    "Read a UTF-8 text file under LOCAL_MEDIA_BASE. Parameter file_name is relative to that "
    "base with the same naming rules as the LM Studio filesystem-access plugin "
    "(letters, digits, underscore, hyphen, dot, slash; no '..')."
)

WRITE_FILE_FS_DESCRIPTION = (
    "Write or overwrite a UTF-8 text file under LOCAL_MEDIA_BASE, creating parent "
    "subdirectories as needed (LM Studio filesystem-access plugin semantics)."
)

CREATE_DIRECTORY_FS_DESCRIPTION = (
    "Create a subdirectory under LOCAL_MEDIA_BASE (mkdir -p semantics), same idea as the "
    "LM Studio filesystem-access create_directory tool."
)

EXTRACT_METADATA_FS_DESCRIPTION = (
    "Read an image or video under LOCAL_MEDIA_BASE (source_file_name uses the same relative path "
    "rules as read_file). Extract EXIF (Pillow), PNG tEXt/zTXt chunks, or ffprobe JSON for video; "
    "returns the same flat JSON list of {path, value} rows as extract_metadata_to_json. "
    "If output_json_file_name is set, also writes that UTF-8 JSON array under LOCAL_MEDIA_BASE."
)

WRITE_METADATA_FS_DESCRIPTION = (
    "Update or remove EXIF on a .jpg, .jpeg, or .webp file under LOCAL_MEDIA_BASE (file_name relative "
    "path, same rules as write_file). Uses piexif in place. set_tags maps IFD names "
    "(0th, Exif, GPS, Interop, 1st) to {tag_name: value}; remove_tags maps IFD names to lists of "
    "tag names to delete. Omit nulls for no-op sections. Same semantics as update_local_media_exif "
    "but scoped to the configured base directory only."
)

UPDATE_LOCAL_MEDIA_EXIF_DESCRIPTION = (
    "Update or remove EXIF tags on a JPEG or WebP file under local_media_root (piexif). "
    "image_relative_path is relative to that root. set_tags maps IFD names "
    "(0th, Exif, GPS, Interop, 1st) to objects mapping Exif tag names (e.g. Copyright, "
    "ImageDescription) to new values; strings are stored as UTF-8 bytes. For Exif.UserComment "
    "with a string value, Unicode EXIF user comment encoding is applied. remove_tags maps IFD "
    "names to lists of tag names to delete. The file is modified in place on disk. "
    "Other image formats are not supported for writes; use extract for read-only metadata."
)


mcp = FastMCP(
    name="exif-sniffer",
    instructions=(
        "When LOCAL_MEDIA_BASE is set, the server matches the LM Studio taderich73/filesystem-access "
        "plugin: list_files, read_file, write_file, create_directory on one base directory, plus "
        "extract_metadata and write_metadata for image/video metadata on paths under that same base. "
        "All of these tools return JSON arrays of {path, value} rows (not prose). Additional tools "
        "use DATA_DIR or caller-supplied absolute local_media_root for fetch, batch listing, or "
        "mixed layouts."
    ),
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "3000")),
    stateless_http=True,
    streamable_http_path="/mcp",
    json_response=False,
)


def _optional_filesystem_base() -> Path | None:
    settings = load_settings()
    if not settings.local_media_base:
        return None
    return Path(settings.local_media_base)


@mcp.tool(name="list_files", description=LIST_FILES_FS_DESCRIPTION)
async def list_files() -> list[dict[str, Any]]:
    return fs_list_files(_optional_filesystem_base())


@mcp.tool(name="read_file", description=READ_FILE_FS_DESCRIPTION)
async def read_file(
    file_name: Annotated[
        str,
        Field(
            min_length=1,
            description="Relative path under LOCAL_MEDIA_BASE (same rules as LM Studio plugin).",
        ),
    ],
) -> list[dict[str, Any]]:
    return fs_read_file(_optional_filesystem_base(), file_name)


@mcp.tool(name="write_file", description=WRITE_FILE_FS_DESCRIPTION)
async def write_file(
    file_name: Annotated[
        str,
        Field(
            min_length=1,
            description="Relative path under LOCAL_MEDIA_BASE (same rules as LM Studio plugin).",
        ),
    ],
    content: Annotated[str, Field(description="UTF-8 text content for the file.")],
) -> list[dict[str, Any]]:
    return fs_write_file(_optional_filesystem_base(), file_name, content)


@mcp.tool(name="create_directory", description=CREATE_DIRECTORY_FS_DESCRIPTION)
async def create_directory(
    directory_name: Annotated[
        str,
        Field(
            min_length=1,
            description="Directory path relative to LOCAL_MEDIA_BASE.",
        ),
    ],
) -> list[dict[str, Any]]:
    return fs_create_directory(_optional_filesystem_base(), directory_name)


@mcp.tool(name="extract_metadata", description=EXTRACT_METADATA_FS_DESCRIPTION)
async def extract_metadata(
    source_file_name: Annotated[
        str,
        Field(
            min_length=1,
            description="Image or video path relative to LOCAL_MEDIA_BASE (same rules as read_file).",
        ),
    ],
    output_json_file_name: Annotated[
        str | None,
        Field(
            description=(
                "Optional relative path under LOCAL_MEDIA_BASE for a UTF-8 JSON array file "
                "(created/overwritten). Omit or null to skip writing and only return rows."
            ),
        ),
    ] = None,
    include_piexif: Annotated[
        bool,
        Field(
            description="If true, include a piexif section for JPEG (more rows).",
        ),
    ] = False,
) -> list[dict[str, Any]]:
    return fs_extract_metadata(
        _optional_filesystem_base(),
        source_file_name,
        output_json_file_name,
        include_piexif=include_piexif,
    )


@mcp.tool(name="write_metadata", description=WRITE_METADATA_FS_DESCRIPTION)
async def write_metadata(
    file_name: Annotated[
        str,
        Field(
            min_length=1,
            description="Path to .jpg, .jpeg, or .webp relative to LOCAL_MEDIA_BASE.",
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
    return fs_write_metadata(_optional_filesystem_base(), file_name, set_tags, remove_tags)


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


@mcp.tool(name="validate_local_media_root", description=VALIDATE_LOCAL_MEDIA_ROOT_DESCRIPTION)
async def validate_local_media_root(
    local_media_root: Annotated[
        str,
        Field(
            min_length=1,
            description="Absolute path to the directory to validate (e.g. /media/photos).",
        ),
    ],
) -> list[dict[str, Any]]:
    try:
        root = parse_local_media_root(local_media_root)
        summary: dict[str, Any] = {
            "usable": True,
            "resolved_root": str(root),
            "exists_and_is_dir": True,
            "error": None,
        }
    except ValueError as exc:
        summary = {
            "usable": False,
            "resolved_root": None,
            "exists_and_is_dir": False,
            "error": str(exc),
        }
    return flatten_to_metadata_list(summary, prefix="local_media")


@mcp.tool(name="list_local_media_images", description=LIST_LOCAL_MEDIA_IMAGES_DESCRIPTION)
async def list_local_media_images(
    local_media_root: Annotated[
        str,
        Field(
            min_length=1,
            description="Absolute path to the root directory that contains your images.",
        ),
    ],
    relative_directory: Annotated[
        str,
        Field(
            description="Directory relative to local_media_root to scan (use '' for the root).",
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
    root = parse_local_media_root(local_media_root)
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
    local_media_root: Annotated[
        str,
        Field(
            min_length=1,
            description="Absolute path to the root directory that contains your source file.",
        ),
    ],
    source_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Path relative to local_media_root to an image or video file.",
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
    local_root = parse_local_media_root(local_media_root)
    data_root = Path(settings.data_dir)
    src = resolve_under_root(local_root, source_relative_path)
    out = resolve_under_root(data_root, output_json_relative_path)
    rows = extract_metadata_list(src, include_piexif=include_piexif)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return rows


@mcp.tool(name="update_local_media_exif", description=UPDATE_LOCAL_MEDIA_EXIF_DESCRIPTION)
async def update_local_media_exif(
    local_media_root: Annotated[
        str,
        Field(
            min_length=1,
            description="Absolute path to the root directory that contains the image file.",
        ),
    ],
    image_relative_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Path relative to local_media_root to a .jpg, .jpeg, or .webp file.",
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
    local_root = parse_local_media_root(local_media_root)
    src = resolve_under_root(local_root, image_relative_path)
    summary = update_image_exif(
        src,
        set_tags=set_tags or {},
        remove_tags=remove_tags or {},
    )
    return flatten_to_metadata_list(summary, prefix="local_media.exif_update")
