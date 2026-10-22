from itertools import permutations

from comic_duplicate_detector.visual import compare


def evidence(values):
    return {
        "pages": [
            {"name": str(i), "dhash": f"{value:016x}", "thumbnail": ""}
            for i, value in enumerate(values)
        ],
        "archive_page_count": len(values),
        "skipped": [],
        "truncated": False,
    }


def test_maximum_pairing_is_independent_of_page_order():
    for left in permutations([0, 1]):
        for right in permutations([0, 2]):
            result = compare(evidence(left), evidence(right), 1)
            assert len(result["pairs"]) == 2
            assert result["overlap"] == 1
            assert len({p["left"]["name"] for p in result["pairs"]}) == 2
            assert len({p["right"]["name"] for p in result["pairs"]}) == 2


def test_disconnected_and_empty_sets():
    assert not compare(evidence([0]), evidence([3]), 1)["pairs"]
    assert compare(evidence([]), evidence([]), 1)["overlap"] == 0


def test_pair_count_matches_small_exhaustive_oracle():
    import random

    def optimum(left, right, distance):
        if not left:
            return 0
        best = optimum(left[1:], right, distance)
        for j, value in enumerate(right):
            if (left[0] ^ value).bit_count() <= distance:
                best = max(best, 1 + optimum(left[1:], right[:j] + right[j + 1 :], distance))
        return best

    rng = random.Random(20261022)
    for _ in range(100):
        left = [rng.randrange(16) for _ in range(rng.randrange(5))]
        right = [rng.randrange(16) for _ in range(rng.randrange(5))]
        distance = rng.randrange(4)
        assert len(compare(evidence(left), evidence(right), distance)["pairs"]) == optimum(
            left, right, distance
        )


def test_dense_graph_at_existing_visual_page_limit():
    result = compare(evidence([0] * 200), evidence([0] * 200), 0)
    assert len(result["pairs"]) == 200
    assert result["overlap"] == 1


def test_actual_cbz_visual_threshold_and_source_preservation(tmp_path):
    import io
    from zipfile import ZipFile

    from PIL import Image

    from comic_duplicate_detector.core import scan

    def page(value):
        rows = [[0, 20, 40, 60, 80, 100, 120, 140, 160] for _ in range(8)]
        if value == 1:
            rows[7][7], rows[7][8] = 160, 140
        if value == 2:
            rows[7][6], rows[7][7] = 140, 120
        image = Image.new("L", (9, 8))
        image.putdata([pixel for row in rows for pixel in row])
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()

    for index, (left, right) in enumerate((([0, 1], [0, 2]), ([1, 0], [2, 0]))):
        paths = [tmp_path / f"left-{index}.cbz", tmp_path / f"right-{index}.cbz"]
        for path, values in zip(paths, (left, right)):
            with ZipFile(path, "w") as archive:
                for number, value in enumerate(values):
                    archive.writestr(f"{number}.png", page(value))
        before = [path.read_bytes() for path in paths]
        report = scan(paths, threshold=1, visual=True, visual_distance=1)
        assert report["visual_matches"][0]["overlap"] == 1
        assert len(report["visual_matches"][0]["pairs"]) == 2
        assert [path.read_bytes() for path in paths] == before
