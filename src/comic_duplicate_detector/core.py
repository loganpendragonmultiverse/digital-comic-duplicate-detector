"""Read-only CBZ content fingerprinting and comparison."""

from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}
MAX_ENTRY_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_ENTRIES = 5000


class ScanError(ValueError):
    """Raised when an archive is unsafe or unreadable."""


@dataclass(frozen=True)
class Fingerprint:
    path: str
    archive_sha256: str
    content_sha256: str
    page_count: int
    page_hashes: tuple[str, ...]
    warnings: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["page_hashes"] = list(self.page_hashes)
        payload["warnings"] = list(self.warnings)
        return payload


def discover(paths: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for candidate in paths:
        resolved = candidate.resolve()
        if resolved.is_dir():
            found.update(
                path for path in resolved.rglob("*") if path.suffix.lower() in {".cbz", ".zip"}
            )
        elif resolved.is_file() and resolved.suffix.lower() in {".cbz", ".zip"}:
            found.add(resolved)
    return sorted(found, key=lambda path: str(path).casefold())


def fingerprint(path: Path) -> Fingerprint:
    archive_hash = _hash_file(path)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ScanError(f"Archive has more than {MAX_ENTRIES} entries: {path}")
            if sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
                raise ScanError(f"Archive expands beyond the safety limit: {path}")
            pages = []
            warnings = []
            for info in infos:
                if info.is_dir() or Path(info.filename).suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                if info.file_size > MAX_ENTRY_BYTES:
                    raise ScanError(f"Archive page exceeds the safety limit: {info.filename}")
                with archive.open(info) as handle:
                    pages.append(hashlib.sha256(handle.read()).hexdigest())
            if not pages:
                warnings.append("No supported image pages found.")
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ScanError(f"Could not read archive {path}: {exc}") from exc
    ordered = tuple(sorted(pages))
    digest = hashlib.sha256("\n".join(ordered).encode("ascii")).hexdigest()
    return Fingerprint(
        str(path.resolve()), archive_hash, digest, len(pages), ordered, tuple(warnings)
    )


def scan(paths: Iterable[Path], *, threshold: float = 0.9) -> dict[str, Any]:
    if not 0 < threshold <= 1:
        raise ScanError("threshold must be greater than 0 and at most 1.")
    archives = discover(paths)
    fingerprints = [fingerprint(path) for path in archives]
    matches = []
    for index, left in enumerate(fingerprints):
        for right in fingerprints[index + 1 :]:
            similarity = _similarity(left.page_hashes, right.page_hashes)
            if left.archive_sha256 == right.archive_sha256:
                kind = "exact_archive"
            elif left.content_sha256 == right.content_sha256 and left.page_count:
                kind = "same_pages"
            elif similarity >= threshold and similarity > 0:
                kind = "likely_duplicate"
            else:
                continue
            matches.append(
                {
                    "left": left.path,
                    "right": right.path,
                    "kind": kind,
                    "similarity": round(similarity, 6),
                }
            )
    return {
        "archives_scanned": len(fingerprints),
        "threshold": threshold,
        "matches": matches,
        "archives": [item.public() for item in fingerprints],
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Digital comic duplicate report",
        "",
        f"Archives scanned: **{report['archives_scanned']}**",
        f"Matches: **{len(report['matches'])}**",
        "",
    ]
    if not report["matches"]:
        lines.append("No exact or likely duplicates met the threshold.")
    for match in report["matches"]:
        lines.extend(
            [
                f"## {match['kind'].replace('_', ' ').title()}",
                "",
                f"- `{match['left']}`",
                f"- `{match['right']}`",
                f"- Page-hash similarity: {match['similarity']:.1%}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0
