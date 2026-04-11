"""Extract EXIF/metadata from local images (Pillow/piexif) and videos (ffprobe)."""

from __future__ import annotations

import json
import struct
import subprocess
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import piexif
from PIL import Image
from PIL.ExifTags import TAGS

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"})
VIDEO_SUFFIXES = frozenset(
    {
        ".mp4",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
        ".m4v",
        ".wmv",
        ".mpg",
        ".mpeg",
        ".3gp",
    }
)


def _serialize_exif_value(value: object) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()
    if isinstance(value, tuple | list):
        return [_serialize_exif_value(v) for v in value]
    return value


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _decode_png_tEXt_chunk(data: bytes) -> dict[str, str] | None:
    """Parse PNG tEXt chunk payload: keyword (latin-1) + null + text (latin-1)."""
    if b"\x00" not in data:
        return None
    i = data.index(b"\x00")
    keyword = data[:i].decode("latin-1", errors="replace")
    text = data[i + 1 :].decode("latin-1", errors="replace")
    return {"keyword": keyword, "text": text}


def _decode_png_zTXt_chunk(data: bytes) -> dict[str, str] | None:
    """Parse PNG zTXt chunk payload: keyword + null + compression + zlib-compressed text."""
    if b"\x00" not in data:
        return None
    i = data.index(b"\x00")
    keyword = data[:i].decode("latin-1", errors="replace")
    if len(data) < i + 2:
        return None
    comp_method = data[i + 1]
    compressed = data[i + 2 :]
    if comp_method != 0:
        return {
            "keyword": keyword,
            "text": f"<unsupported zTXt compression method {comp_method}>",
        }
    try:
        raw = zlib.decompress(compressed)
        text = raw.decode("latin-1", errors="replace")
    except (zlib.error, ValueError, OSError) as exc:
        return {"keyword": keyword, "text": f"<zlib decompress failed: {exc}>"}
    return {"keyword": keyword, "text": text}


def parse_png_tEXt_and_zTXt(path: Path) -> dict[str, list[dict[str, str]]]:
    """Scan *path* for PNG ``tEXt`` and ``zTXt`` chunks; return lists keyed by chunk type.

    Non-PNG files or invalid signatures yield empty lists. Multiple chunks with the same keyword
    are all preserved in order.
    """
    out: dict[str, list[dict[str, str]]] = {"tEXt": [], "zTXt": []}
    try:
        data = path.read_bytes()
    except OSError:
        return out
    if len(data) < 8 or data[:8] != PNG_SIGNATURE:
        return out

    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        ctype = data[pos + 4 : pos + 8]
        chunk_start = pos + 8
        chunk_end = chunk_start + length
        if chunk_end + 4 > len(data):
            break
        chunk_data = data[chunk_start:chunk_end]
        pos = chunk_end + 4  # skip CRC

        if ctype == b"IEND":
            break
        if ctype == b"tEXt":
            entry = _decode_png_tEXt_chunk(chunk_data)
            if entry:
                out["tEXt"].append(entry)
        elif ctype == b"zTXt":
            entry = _decode_png_zTXt_chunk(chunk_data)
            if entry:
                out["zTXt"].append(entry)

    return out


def _pillow_exif_dict(img: Image.Image) -> dict[str, Any]:
    exif = img.getexif()
    if not exif:
        return {}
    out: dict[str, Any] = {}
    for tag_id, value in exif.items():
        name = TAGS.get(tag_id, str(tag_id))
        out[str(name)] = _serialize_exif_value(value)
    return out


def _piexif_dict(path: Path) -> dict[str, Any] | None:
    try:
        raw = piexif.load(str(path))
    except Exception:
        return None
    out: dict[str, Any] = {}
    for ifd_name, ifd in raw.items():
        if ifd_name == "thumbnail" or ifd is None:
            continue
        if not isinstance(ifd, dict):
            continue
        section: dict[str, Any] = {}
        for tag, val in ifd.items():
            tag_name = (
                piexif.TAGS[ifd_name][tag]["name"]
                if ifd_name in piexif.TAGS and tag in piexif.TAGS[ifd_name]
                else str(tag)
            )
            section[tag_name] = _serialize_exif_value(val)
        out[str(ifd_name)] = section
    return out


def _ffprobe(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"ffprobe failed ({proc.returncode}): {err[:500]}")
    return json.loads(proc.stdout)


def _sniff_kind(path: Path) -> str | None:
    suf = path.suffix.lower()
    if suf in IMAGE_SUFFIXES:
        return "image"
    if suf in VIDEO_SUFFIXES:
        return "video"
    return None


def _guess_media_kind(path: Path) -> str:
    guessed = _sniff_kind(path)
    if guessed:
        return guessed
    try:
        with Image.open(path) as img:
            if img.format:
                return "image"
    except Exception:
        pass
    return "video"


def extract_metadata_document(path: Path, *, include_piexif: bool = False) -> dict[str, Any]:
    """Build normalized metadata document for *path* (nested structure for internal use)."""
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    kind = _guess_media_kind(path)

    now = datetime.now(timezone.utc).isoformat()
    doc: dict[str, Any] = {
        "schema_version": 1,
        "source_path": str(path.resolve()),
        "media_kind": kind,
        "extracted_at": now,
    }

    if kind == "image":
        with Image.open(path) as img:
            image_block: dict[str, Any] = {
                "format": img.format,
                "mode": img.mode,
                "size": list(img.size),
                "exif_pillow": _pillow_exif_dict(img),
            }
            if img.format == "PNG":
                image_block["png_text_chunks"] = parse_png_tEXt_and_zTXt(path)
            doc["image"] = image_block
        if include_piexif and path.suffix.lower() in (".jpg", ".jpeg"):
            doc["piexif"] = _piexif_dict(path)
    else:
        doc["ffprobe"] = _ffprobe(path)

    return doc


def flatten_to_metadata_list(obj: Any, prefix: str = "") -> list[dict[str, Any]]:
    """Flatten nested JSON-like *obj* into a list of ``{path, value}`` rows (leaves only)."""
    rows: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        if not obj:
            rows.append({"path": prefix or "/", "value": {}})
            return rows
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            rows.extend(flatten_to_metadata_list(v, p))
    elif isinstance(obj, list):
        if not obj:
            rows.append({"path": prefix or "/", "value": []})
            return rows
        for i, v in enumerate(obj):
            p = f"{prefix}[{i}]" if prefix else f"[{i}]"
            rows.extend(flatten_to_metadata_list(v, p))
    else:
        rows.append({"path": prefix or "/", "value": obj})
    return rows


def extract_metadata_list(path: Path, *, include_piexif: bool = False) -> list[dict[str, Any]]:
    """Extract metadata from *path* and return a flat JSON-friendly list of ``{path, value}`` entries."""
    doc = extract_metadata_document(path, include_piexif=include_piexif)
    return flatten_to_metadata_list(doc)
