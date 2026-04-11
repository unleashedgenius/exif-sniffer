"""Tests for metadata extraction."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from exifsniffer.extract import (
    extract_metadata_document,
    extract_metadata_list,
    flatten_to_metadata_list,
    parse_png_tEXt_and_zTXt,
)


def test_extract_minimal_png(tmp_path: Path) -> None:
    img_path = tmp_path / "t.png"
    Image.new("RGB", (4, 4), color="red").save(img_path, format="PNG")
    doc = extract_metadata_document(img_path)
    assert doc["media_kind"] == "image"
    assert doc["schema_version"] == 1
    assert "image" in doc
    assert doc["image"]["png_text_chunks"] == {"tEXt": [], "zTXt": []}


def test_png_tEXt_and_zTXt_chunks(tmp_path: Path) -> None:
    pnginfo = PngInfo()
    pnginfo.add_text("Title", "hello-tEXt")
    pnginfo.add_text("Comment", "hello-zTXt", zip=True)
    img_path = tmp_path / "meta.png"
    Image.new("RGB", (2, 2), color="white").save(img_path, "PNG", pnginfo=pnginfo)

    chunks = parse_png_tEXt_and_zTXt(img_path)
    assert any(c["keyword"] == "Title" and c["text"] == "hello-tEXt" for c in chunks["tEXt"])
    assert any(c["keyword"] == "Comment" and c["text"] == "hello-zTXt" for c in chunks["zTXt"])

    doc = extract_metadata_document(img_path)
    assert doc["image"]["png_text_chunks"] == chunks


def test_write_json_list_roundtrip(tmp_path: Path) -> None:
    img_path = tmp_path / "t.jpg"
    Image.new("RGB", (8, 8), color="blue").save(img_path, format="JPEG")
    out = tmp_path / "meta.json"
    rows = extract_metadata_list(img_path)
    assert isinstance(rows, list)
    assert all("path" in r and "value" in r for r in rows)
    out.write_text(json.dumps(rows), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    paths = {r["path"] for r in loaded}
    assert "media_kind" in paths
    assert any(p.startswith("image.") for p in paths)


def test_flatten_nested() -> None:
    rows = flatten_to_metadata_list({"a": {"b": 1}, "c": [10, 20]})
    by_path = {r["path"]: r["value"] for r in rows}
    assert by_path["a.b"] == 1
    assert by_path["c[0]"] == 10
    assert by_path["c[1]"] == 20
