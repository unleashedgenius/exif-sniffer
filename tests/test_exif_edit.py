"""Tests for in-place EXIF updates (JPEG/WebP)."""

from __future__ import annotations

import piexif
import pytest
from PIL import Image

from exifsniffer.exif_edit import update_image_exif
from exifsniffer.extract import extract_metadata_document


def test_update_jpeg_copyright_roundtrip(tmp_path) -> None:
    img_path = tmp_path / "x.jpg"
    Image.new("RGB", (4, 4), color="blue").save(img_path, format="JPEG")
    summary = update_image_exif(
        img_path,
        set_tags={"0th": {"Copyright": "ACME"}},
        remove_tags={},
    )
    assert summary["tags_updated"]
    doc = extract_metadata_document(img_path)
    assert doc["image"]["exif_pillow"].get("Copyright") == "ACME"


def test_remove_exif_tag(tmp_path) -> None:
    img_path = tmp_path / "y.jpg"
    Image.new("RGB", (2, 2), color="red").save(img_path, format="JPEG")
    update_image_exif(img_path, set_tags={"0th": {"Copyright": "X"}}, remove_tags={})
    update_image_exif(img_path, set_tags={}, remove_tags={"0th": ["Copyright"]})
    raw = piexif.load(str(img_path))
    assert piexif.ImageIFD.Copyright not in raw["0th"]


def test_no_op_does_not_crash(tmp_path) -> None:
    img_path = tmp_path / "z.jpg"
    Image.new("RGB", (2, 2), color="green").save(img_path, format="JPEG")
    summary = update_image_exif(img_path, set_tags={}, remove_tags={})
    assert summary.get("unchanged") is True


def test_no_op_on_unsupported_suffix_raises(tmp_path) -> None:
    png_path = tmp_path / "n.png"
    Image.new("RGB", (2, 2), color="black").save(png_path, format="PNG")
    with pytest.raises(ValueError, match="EXIF write is only supported"):
        update_image_exif(png_path, set_tags={}, remove_tags={})


def test_webp_inserts_exif_when_missing(tmp_path) -> None:
    img_path = tmp_path / "w.webp"
    Image.new("RGB", (2, 2), color="white").save(img_path, "WEBP")
    update_image_exif(img_path, set_tags={"0th": {"Copyright": "WEBP"}}, remove_tags={})
    assert piexif.load(str(img_path))["0th"].get(piexif.ImageIFD.Copyright) == b"WEBP"
