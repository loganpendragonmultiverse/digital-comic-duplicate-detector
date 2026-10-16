import json
from zipfile import ZipFile

import pytest

from comic_duplicate_detector.cli import main
from comic_duplicate_detector.core import ScanError, _similarity, scan


def cbz(path, pages):
    with ZipFile(path, "w") as archive:
        for i, page in enumerate(pages):
            archive.writestr(f"{i}.png", page)


def test_repetition_order_threshold_and_cache(tmp_path, capsys):
    one, two, three = [tmp_path / f"{name}.cbz" for name in ("one", "two", "three")]
    cbz(one, [b"a", b"a", b"b"])
    cbz(two, [b"a", b"b", b"b"])
    cbz(three, [b"b", b"a", b"a"])
    default = scan([one, two], threshold=0.75)
    assert default["matches"][0]["similarity"] == 1
    assert "page_overlap_mode" not in default
    assert not scan([one, two], threshold=0.75, multiplicity=True)["matches"]
    report = scan([one, two], threshold=0.5, multiplicity=True)
    assert report["matches"][0]["similarity"] == 0.5
    assert report["matches"][0]["kind"] == "likely_duplicate"
    assert scan([one, three], multiplicity=True)["matches"][0]["kind"] == "same_pages"
    cache = tmp_path / "cache.json"
    scan([one, two], cache=cache)
    cached = scan([one, two], cache=cache, multiplicity=True, threshold=0.5)
    assert cached["cache_hits"] == 2
    assert cached["matches"] == report["matches"]
    assert (
        main([str(one), str(two), "--multiplicity", "--threshold", "0.5", "--format", "json"]) == 1
    )
    assert json.loads(capsys.readouterr().out)["page_overlap_mode"] == "multiplicity"


def test_empty_archives_and_invalid_thresholds(tmp_path):
    one, two = tmp_path / "one.cbz", tmp_path / "two.cbz"
    cbz(one, [])
    cbz(two, [])
    assert _similarity((), (), multiplicity=True) == 0
    for threshold in (0, -1, 1.1, float("nan")):
        with pytest.raises(ScanError):
            scan([one, two], multiplicity=True, threshold=threshold)
    report = scan([one, two], multiplicity=True, threshold=1)
    assert all(m["kind"] == "exact_archive" for m in report["matches"])
    assert report["archives"][0]["warnings"]


def test_multiplicity_keeps_visual_labels_separate(tmp_path):
    import io

    from PIL import Image

    stream = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(stream, "PNG")
    one, two = tmp_path / "one.cbz", tmp_path / "two.cbz"
    cbz(one, [stream.getvalue(), stream.getvalue()])
    cbz(two, [stream.getvalue()])
    before = [p.read_bytes() for p in (one, two)]
    report = scan([one, two], multiplicity=True, visual=True, threshold=0.5)
    assert report["matches"][0]["kind"] == "likely_duplicate"
    assert report["visual_matches"][0]["kind"] == "visual_candidate"
    assert before == [p.read_bytes() for p in (one, two)]
