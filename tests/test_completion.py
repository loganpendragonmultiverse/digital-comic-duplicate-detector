import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from comic_duplicate_detector import core
from comic_duplicate_detector.cli import main


def comic(path):
    with ZipFile(path, "w") as archive:
        archive.writestr("page.png", b"page")
    return path


@pytest.mark.parametrize(
    "value",
    [True, None, "0.5", [], float("nan"), 10**400],
    ids=["bool", "null", "text", "array", "nan", "huge"],
)
def test_threshold_types(value):
    with pytest.raises(core.ScanError, match="threshold"):
        core.scan([], threshold=value)


@pytest.mark.parametrize(
    "value", [True, None, "6", 0.5, 65], ids=["bool", "null", "text", "fraction", "range"]
)
def test_visual_distance_types(tmp_path, value):
    with pytest.raises(core.ScanError, match="visual_distance"):
        core.scan([comic(tmp_path / "one.cbz")], visual_distance=value)


def test_missing_unsupported_empty_inputs_and_directory_errors(tmp_path, monkeypatch):
    with pytest.raises(core.ScanError, match="Missing"):
        core.scan([tmp_path / "missing"])
    unsupported = tmp_path / "page.txt"
    unsupported.write_text("page")
    with pytest.raises(core.ScanError, match="unsupported"):
        core.scan([unsupported])
    with pytest.raises(core.ScanError, match="No supported"):
        core.scan([tmp_path])

    def walk(path, *, onerror):
        onerror(PermissionError("fixture"))
        return iter(())

    monkeypatch.setattr(core.os, "walk", walk)
    with pytest.raises(core.ScanError, match="directory"):
        core.scan([tmp_path])


def test_unsupported_zip_version_is_actionable(tmp_path):
    path = tmp_path / "bad.cbz"
    info = ZipInfo("page.png")
    info.extract_version = 99
    info.create_version = 99
    with ZipFile(path, "w") as archive:
        archive.writestr(info, b"page")
    with pytest.raises(core.ScanError, match="Could not read"):
        core.fingerprint(path)
    assert main([str(path)]) == 2


def test_uncached_source_change_is_refused(tmp_path, monkeypatch):
    source = comic(tmp_path / "one.cbz")
    digest = core._hash_file

    def changed(path):
        value = digest(path)
        with ZipFile(path, "a") as archive:
            archive.writestr("new.png", b"changed")
        return value

    monkeypatch.setattr(core, "_hash_file", changed)
    with pytest.raises(core.ScanError, match="changed"):
        core.scan([source])


@pytest.mark.parametrize(
    "mutation",
    ["count", "warnings", "digest", "pages"],
    ids=["bool-count", "text-warnings", "wrong-digest", "bad-pages"],
)
def test_malformed_cache_entry_rehashed(tmp_path, mutation):
    source = comic(tmp_path / "one.cbz")
    cache = tmp_path / "cache.json"
    core.scan([source], cache=cache)
    data = json.loads(cache.read_text())
    entry = data["entries"][str(source.resolve())]["fingerprint"]
    if mutation == "count":
        entry["page_count"] = True
    elif mutation == "warnings":
        entry["warnings"] = "bad"
    elif mutation == "digest":
        entry["content_sha256"] = "0" * 64
    else:
        entry["page_hashes"] = ["bad"]
    cache.write_text(json.dumps(data))
    assert core.scan([source], cache=cache)["cache_hits"] == 0
    refreshed = json.loads(cache.read_text())["entries"][str(source.resolve())]["fingerprint"]
    assert type(refreshed["page_count"]) is int
    assert (
        refreshed["content_sha256"]
        == hashlib.sha256("\n".join(refreshed["page_hashes"]).encode("ascii")).hexdigest()
    )


def test_boolean_cache_schema_preserved(tmp_path):
    source = comic(tmp_path / "one.cbz")
    cache = tmp_path / "cache.json"
    content = json.dumps({"schema": True, "algorithm": "sha256-pages-v1", "entries": {}})
    cache.write_text(content)
    with pytest.raises(core.ScanError, match="invalid"):
        core.scan([source], cache=cache)
    assert cache.read_text() == content


@pytest.mark.parametrize("dangling", [False, True], ids=["existing", "dangling"])
def test_report_and_cache_links_preserved(tmp_path, dangling):
    source = comic(tmp_path / "one.cbz")
    target = tmp_path / "target.json"
    if not dangling:
        target.write_text("valuable")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert main([str(source), "--output", str(link)]) == 2
    with pytest.raises(core.ScanError, match="ordinary"):
        core.scan([source], cache=link)
    assert link.is_symlink()
    assert target.read_text() == "valuable" if not dangling else not target.exists()


def test_fifo_cache_refused_before_read(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO unavailable")
    source = comic(tmp_path / "one.cbz")
    cache = tmp_path / "cache.json"
    os.mkfifo(cache)
    with pytest.raises(core.ScanError, match="ordinary"):
        core.scan([source], cache=cache)
    assert cache.exists()


def test_report_concurrent_output_preserved(tmp_path, monkeypatch):
    source = comic(tmp_path / "one.cbz")
    output = tmp_path / "report.json"
    original = Path.open

    def raced(path, mode="r", *args, **kwargs):
        if path == output and mode == "x":
            with original(path, "w") as handle:
                handle.write("concurrent")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", raced)
    assert main([str(source), "--output", str(output)]) == 2
    assert output.read_text() == "concurrent"


def test_markdown_path_line_breaks_are_quoted():
    path = "comic" + chr(10) + "# Injected" + chr(96)
    rendered = core.markdown(
        {
            "archives_scanned": 2,
            "matches": [{"kind": "same_pages", "left": path, "right": "other", "similarity": 1.0}],
        }
    )
    assert chr(10) + "# Injected" not in rendered


def test_discovery_resolves_duplicate_aliases(tmp_path):
    source = comic(tmp_path / "one.cbz")
    alias = tmp_path / "alias.cbz"
    try:
        alias.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert core.discover([source, alias, tmp_path]) == [source.resolve()]


def test_visual_source_change_and_decode_error_are_actionable(tmp_path, monkeypatch):
    from comic_duplicate_detector import visual

    source = comic(tmp_path / "one.cbz")

    def changed(path):
        with ZipFile(path, "a") as archive:
            archive.writestr("new.png", b"changed")
        return {"pages": [], "skipped": [], "truncated": False, "archive_page_count": 2}

    monkeypatch.setattr(visual, "page_evidence", changed)
    with pytest.raises(core.ScanError, match="changed"):
        core.scan([source], visual=True)

    def corrupted(path):
        raise core.zipfile.BadZipFile("changed archive")

    monkeypatch.setattr(visual, "page_evidence", corrupted)
    with pytest.raises(core.ScanError, match="visual evidence"):
        core.scan([source], visual=True)


def test_visual_pixel_budget_before_conversion(tmp_path, monkeypatch):
    import io

    from PIL import Image

    from comic_duplicate_detector import visual

    stream = io.BytesIO()
    Image.new("1", (6400, 6400)).save(stream, format="PNG")
    source = tmp_path / "large.cbz"
    with ZipFile(source, "w") as archive:
        archive.writestr("large.png", stream.getvalue())

    def forbidden(*args, **kwargs):
        raise AssertionError("oversized image must not convert")

    monkeypatch.setattr(Image.Image, "convert", forbidden)
    evidence = visual.page_evidence(source)
    assert evidence["pages"] == [] and evidence["skipped"] == ["large.png"]
    html = visual.render_html(
        {
            "matches": [],
            "visual_review": [{"path": str(source), "skipped": ["<large>.png"], "truncated": True}],
        }
    )
    assert "1 skipped pages" in html and "truncated: True" in html
    assert "&lt;large&gt;.png" in html


@pytest.mark.parametrize(
    "limit", [0, True, 0.5, 201], ids=["zero", "bool", "fraction", "over-limit"]
)
def test_visual_limit_validation(tmp_path, limit):
    from comic_duplicate_detector.visual import page_evidence

    with pytest.raises(core.ScanError, match="limit"):
        page_evidence(comic(tmp_path / "one.cbz"), limit=limit)


def test_self_referential_cache_link_is_actionable(tmp_path, capsys):
    source = comic(tmp_path / "one.cbz")
    cache = tmp_path / "cache.json"
    output = tmp_path / "report.json"
    before = source.read_bytes()
    try:
        cache.symlink_to(cache.name)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert main([str(source), "--cache", str(cache), "--output", str(output)]) == 2
    assert "error:" in capsys.readouterr().err
    assert cache.is_symlink() and cache.readlink() == Path(cache.name)
    assert not output.exists() and source.read_bytes() == before


def test_unreadable_discovered_archive_is_not_skipped(tmp_path, monkeypatch):
    source = comic(tmp_path / "one.cbz")
    original = Path.stat

    def inaccessible(path, *args, **kwargs):
        if path == source:
            raise PermissionError("fixture archive")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inaccessible)
    with pytest.raises(core.ScanError, match="discover"):
        core.scan([tmp_path])
