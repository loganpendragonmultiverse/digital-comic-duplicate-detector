import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from comic_duplicate_detector.cache import cached_fingerprints
from comic_duplicate_detector.cli import main
from comic_duplicate_detector.core import ScanError, scan
from comic_duplicate_detector.visual import page_evidence, render_html


def archive(path: Path, format: str = "PNG", *, extra: bool = False) -> Path:
    image = Image.new("RGB", (80, 80))
    image.putdata([(x * 3, y * 3, (x + y) % 256) for y in range(80) for x in range(80)])
    stream = io.BytesIO()
    image.save(stream, format=format)
    with zipfile.ZipFile(path, "w") as handle:
        handle.writestr("page." + format.lower(), stream.getvalue())
        if extra:
            handle.writestr("bad.jpg", b"not an image")
    return path


def test_cache_hits_rehash_and_invalidation(tmp_path, monkeypatch) -> None:
    import comic_duplicate_detector.cache as cache_module

    source = archive(tmp_path / "one.cbz")
    cache = tmp_path / "cache.json"
    before = source.read_bytes()
    assert scan([source], cache=cache)["cache_hits"] == 0
    fingerprint = cache_module.fingerprint
    calls = []

    def measured(path):
        calls.append(path)
        return fingerprint(path)

    monkeypatch.setattr(cache_module, "fingerprint", measured)
    assert scan([source], cache=cache)["cache_hits"] == 1 and not calls
    assert scan([source], cache=cache, rehash=True)["cache_hits"] == 0 and len(calls) == 1
    assert source.read_bytes() == before
    archive(source, extra=True)
    assert scan([source], cache=cache)["cache_hits"] == 0
    data = json.loads(cache.read_text())
    data["entries"][str(source.resolve())]["fingerprint"]["page_hashes"] = ["bad"]
    cache.write_text(json.dumps(data))
    assert scan([source], cache=cache)["cache_hits"] == 0
    data = json.loads(cache.read_text())
    data["entries"][str(source.resolve())]["fingerprint"] = {}
    cache.write_text(json.dumps(data))
    assert scan([source], cache=cache)["cache_hits"] == 0


def test_visual_recompression_evidence_is_separate(tmp_path) -> None:
    left, right = archive(tmp_path / "one.cbz"), archive(tmp_path / "two.cbz", "JPEG")
    original = left.read_bytes()
    report = scan([left, right], visual=True)
    assert not report["matches"]
    assert report["visual_matches"][0]["kind"] == "visual_candidate"
    assert report["visual_matches"][0]["overlap"] == 1
    assert "data:image/jpeg;base64," in render_html(report)
    assert left.read_bytes() == original
    assert (
        main(
            [
                str(tmp_path),
                "--visual",
                "--format",
                "html",
                "--output",
                str(tmp_path / "report.html"),
            ]
        )
        == 1
    )


def test_partial_visual_and_invalid_cache(tmp_path, monkeypatch) -> None:
    source = archive(tmp_path / "one.cbz", extra=True)
    assert page_evidence(source)["skipped"] == ["bad.jpg"]
    assert page_evidence(source, limit=1)["truncated"]
    for content in ("not-json", "[]", '{"schema":0}'):
        cache = tmp_path / "cache.json"
        cache.write_text(content)
        with pytest.raises(ScanError, match="invalid"):
            scan([source], cache=cache)
        assert cache.read_text() == content
    with pytest.raises(ScanError, match="dedicated"):
        scan([source], cache=tmp_path / "cache.cbz")
    with pytest.raises(ScanError, match="visual_distance"):
        scan([source], visual_distance=65)
    import comic_duplicate_detector.cache as cache_module

    original_identity = cache_module.identity(source)
    values = iter([original_identity, [0, 0, 0, 0, 0]])
    monkeypatch.setattr(cache_module, "identity", lambda _: next(values))
    with pytest.raises(ScanError, match="changed"):
        cached_fingerprints([source], tmp_path / "fresh.json", False)


def test_output_and_cache_paths_cannot_alias(tmp_path) -> None:
    source = archive(tmp_path / "one.cbz")
    target = tmp_path / "cache.json"
    assert main([str(source), "--cache", str(target), "--output", str(target)]) == 2
