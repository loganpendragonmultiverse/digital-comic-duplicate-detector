"""Opt-in perceptual evidence. No archive extraction or deletion."""

from __future__ import annotations

import base64
import io
import zipfile
from html import escape
from pathlib import Path
from typing import Any

from .core import IMAGE_SUFFIXES, MAX_ENTRY_BYTES, ScanError


def page_evidence(path: Path, limit: int = 200) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ScanError("Visual comparison requires the optional [visual] dependency.") from exc
    pages = []
    skipped = []
    with zipfile.ZipFile(path) as archive:
        candidates = [
            info
            for info in archive.infolist()
            if not info.is_dir() and Path(info.filename).suffix.lower() in IMAGE_SUFFIXES
        ]
        for info in candidates[:limit]:
            if info.file_size > MAX_ENTRY_BYTES:
                raise ScanError("Visual page exceeds the safety limit")
            try:
                with Image.open(io.BytesIO(archive.read(info))) as original:
                    if original.width * original.height > 40_000_000:
                        skipped.append(info.filename)
                        continue
                    gray = original.convert("L").resize((9, 8))
                    pixels = list(gray.getdata())
                    value = 0
                    for y in range(8):
                        for x in range(8):
                            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
                    thumb = original.convert("RGB")
                    thumb.thumbnail((120, 160))
                    stream = io.BytesIO()
                    thumb.save(stream, format="JPEG", quality=65)
                    pages.append(
                        {
                            "name": info.filename,
                            "dhash": f"{value:016x}",
                            "thumbnail": base64.b64encode(stream.getvalue()).decode("ascii"),
                        }
                    )
            except (OSError, ValueError, Image.DecompressionBombError):
                skipped.append(info.filename)
    return {
        "pages": pages,
        "skipped": skipped,
        "truncated": len(candidates) > limit,
        "archive_page_count": len(candidates),
    }


def compare(left: dict[str, Any], right: dict[str, Any], distance: int) -> dict[str, Any]:
    available = set(range(len(right["pages"])))
    pairs = []
    for page in left["pages"]:
        choices = sorted(
            ((int(page["dhash"], 16) ^ int(right["pages"][j]["dhash"], 16)).bit_count(), j)
            for j in available
        )
        if choices and choices[0][0] <= distance:
            difference, j = choices[0]
            available.remove(j)
            pairs.append({"left": page, "right": right["pages"][j], "distance": difference})
    denominator = max(left["archive_page_count"], right["archive_page_count"])
    return {
        "kind": "visual_candidate",
        "overlap": len(pairs) / denominator if denominator else 0,
        "pairs": pairs,
        "partial": bool(
            left["skipped"] or right["skipped"] or left["truncated"] or right["truncated"]
        ),
    }


def render_html(report: dict[str, Any]) -> str:
    body = [
        "<h1>Comic duplicate evidence</h1><p>Visual similarity is a review aid, not exact equality. Nothing is deleted.</p>"
    ]
    for match in report["matches"]:
        body.append(
            f"<section><h2>{escape(match['kind'])}</h2><p>{escape(match['left'])}<br>{escape(match['right'])}</p></section>"
        )
    for match in report.get("visual_matches", []):
        body.append(
            f"<section><h2>Visual candidate Â· {match['overlap']:.0%} page overlap</h2><p>{escape(match['left'])}<br>{escape(match['right'])}</p>"
        )
        if match["partial"]:
            body.append(
                "<p>Partial comparison: some pages were skipped or exceeded the configured limit.</p>"
            )
        for pair in match["pairs"]:
            body.append('<div class="pair">')
            for side in ("left", "right"):
                page = pair[side]
                body.append(
                    f'<figure><img alt="Page comparison thumbnail" src="data:image/jpeg;base64,{page["thumbnail"]}"><figcaption>{escape(page["name"])}</figcaption></figure>'
                )
            body.append(f"<p>Hash distance: {pair['distance']}</p></div>")
        body.append("</section>")
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Comic duplicate evidence</title><style>body{font:17px system-ui;max-width:1000px;margin:auto;padding:22px;background:#f4f1e9;color:#243743}section{background:white;padding:18px;border:1px solid #b9c9cc;border-radius:12px;margin:18px 0;overflow-wrap:anywhere}.pair{display:flex;flex-wrap:wrap;gap:16px}figure{margin:8px;max-width:140px}img{max-width:100%}</style>'
        + "".join(body)
        + "</html>"
    )
