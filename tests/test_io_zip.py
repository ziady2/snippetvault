import io
import zipfile

import pytest

from snippetbox import io_zip
from snippetbox.errors import IOFormatError
from snippetbox.snippet import Snippet


def test_export_to_bytes_returns_zip(python_snippet):
    data = io_zip.export_to_bytes([python_snippet])
    assert data[:2] == b"PK"


def test_export_includes_manifest(python_snippet):
    data = io_zip.export_to_bytes([python_snippet])
    zf = zipfile.ZipFile(io.BytesIO(data))
    assert "manifest.json" in zf.namelist()


def test_export_includes_body_file(python_snippet):
    data = io_zip.export_to_bytes([python_snippet])
    zf = zipfile.ZipFile(io.BytesIO(data))
    body_files = [n for n in zf.namelist() if n.startswith("snippets/")]
    assert body_files


def test_round_trip(python_snippet):
    data = io_zip.export_to_bytes([python_snippet])
    back = io_zip.import_from_bytes(data)
    assert len(back) == 1
    assert back[0].body == python_snippet.body


def test_round_trip_with_dup_filename():
    a = Snippet(title="Same Slug", body="A", language="python")
    b = Snippet(title="Same Slug", body="B", language="python")
    a.slug = "same-slug"
    b.slug = "same-slug"
    data = io_zip.export_to_bytes([a, b])
    back = io_zip.import_from_bytes(data)
    assert len(back) == 2


def test_import_bad_zip_raises():
    with pytest.raises(IOFormatError):
        io_zip.import_from_bytes(b"not a zip file at all")


def test_import_zip_without_manifest():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", "content")
    out = io_zip.import_from_bytes(buf.getvalue())
    assert len(out) == 1
    assert "content" in out[0].body


def test_import_zip_filters_unsafe_names():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../etc/passwd", "x")
        zf.writestr("ok.txt", "ok")
    out = io_zip.import_from_bytes(buf.getvalue())
    assert all("../" not in s.title for s in out)


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.zip"
    io_zip.export_to_file([python_snippet], target)
    back = io_zip.import_from_file(target)
    assert len(back) == 1


def test_import_missing_file(tmp_path):
    with pytest.raises(IOFormatError):
        io_zip.import_from_file(tmp_path / "missing.zip")


def test_import_zip_bad_manifest():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", "not json")
    with pytest.raises(IOFormatError):
        io_zip.import_from_bytes(buf.getvalue())


def test_list_entries(python_snippet):
    data = io_zip.export_to_bytes([python_snippet])
    entries = io_zip.list_entries(data)
    assert "manifest.json" in entries


def test_list_entries_bad_zip():
    with pytest.raises(IOFormatError):
        io_zip.list_entries(b"nope")
