import zipfile
from pathlib import Path

import pytest

from comic_duplicate_detector.cli import main
from comic_duplicate_detector.core import ScanError, discover, fingerprint, markdown, scan


def comic(path: Path, pages: list[bytes], *, prefix: str = "") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for index, data in enumerate(pages, start=1):
            archive.writestr(f"{prefix}{index:03}.jpg", data)
    return path


def test_same_pages_ignore_archive_names_and_compression(tmp_path: Path) -> None:
    left = comic(tmp_path / "one.cbz", [b"A", b"B"])
    right = comic(tmp_path / "two.cbz", [b"B", b"A"], prefix="pages/")
    result = scan([tmp_path])
    assert result["matches"][0]["kind"] == "same_pages"
    assert fingerprint(left).archive_sha256 != fingerprint(right).archive_sha256


def test_likely_duplicate_threshold(tmp_path: Path) -> None:
    comic(tmp_path / "one.cbz", [b"A", b"B", b"C"])
    comic(tmp_path / "two.cbz", [b"A", b"B", b"D"])
    result = scan([tmp_path], threshold=0.5)
    assert result["matches"][0]["kind"] == "likely_duplicate"


def test_discover_and_empty_archive_warning(tmp_path: Path) -> None:
    comic(tmp_path / "empty.cbz", [])
    assert len(discover([tmp_path])) == 1
    assert fingerprint(tmp_path / "empty.cbz").warnings


def test_invalid_archive_and_threshold(tmp_path: Path) -> None:
    bad = tmp_path / "bad.cbz"
    bad.write_text("bad", encoding="utf-8")
    with pytest.raises(ScanError, match="Could not read"):
        fingerprint(bad)
    with pytest.raises(ScanError, match="threshold"):
        scan([], threshold=0)


def test_markdown_no_matches() -> None:
    assert "No exact" in markdown({"archives_scanned": 0, "matches": []})


def test_cli_json_exit_codes_and_output_guard(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    comic(tmp_path / "one.cbz", [b"A"])
    comic(tmp_path / "two.cbz", [b"A"])
    target = tmp_path / "report.json"
    assert main([str(tmp_path), "--format", "json", "--output", str(target)]) == 1
    assert target.is_file()
    assert main([str(tmp_path), "--output", str(target)]) == 2
    assert "already exists" in capsys.readouterr().err


def test_exact_archive_and_single_file_discovery(tmp_path: Path) -> None:
    first = comic(tmp_path / "one.cbz", [b"A"])
    second = tmp_path / "two.cbz"
    second.write_bytes(first.read_bytes())
    assert discover([first]) == [first.resolve()]
    assert scan([tmp_path])["matches"][0]["kind"] == "exact_archive"


def test_unrelated_archives_and_markdown_match(tmp_path: Path) -> None:
    comic(tmp_path / "one.cbz", [b"A"])
    comic(tmp_path / "two.cbz", [b"B"])
    assert scan([tmp_path])["matches"] == []
    report = {
        "archives_scanned": 2,
        "matches": [{"kind": "same_pages", "left": "one", "right": "two", "similarity": 1.0}],
    }
    assert "100.0%" in markdown(report)


def test_cli_no_matches_and_scan_error(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    comic(tmp_path / "one.cbz", [b"A"])
    assert main([str(tmp_path)]) == 0
    assert "No exact" in capsys.readouterr().out
    bad = tmp_path / "bad.cbz"
    bad.write_text("bad", encoding="utf-8")
    assert main([str(bad)]) == 2
    assert "Could not read" in capsys.readouterr().err
