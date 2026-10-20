"""Read-only CBZ content fingerprinting and comparison."""

from __future__ import annotations

import hashlib
import json
import lzma
import math
import os
import stat
import string
import zipfile
import zlib
from collections import Counter
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

    def failed(error: OSError) -> None:
        raise ScanError(f"Could not inspect directory: {error}") from error

    try:
        for candidate in paths:
            resolved = candidate.resolve()
            metadata = resolved.stat()
            if stat.S_ISDIR(metadata.st_mode):
                for directory, _directories, files in os.walk(resolved, onerror=failed):
                    for name in files:
                        path = Path(directory) / name
                        if path.suffix.lower() in {".cbz", ".zip"}:
                            metadata = path.stat()
                            if stat.S_ISREG(metadata.st_mode):
                                found.add(path.resolve(strict=True))
            elif stat.S_ISREG(metadata.st_mode) and resolved.suffix.lower() in {".cbz", ".zip"}:
                found.add(resolved)
            else:
                raise ScanError(f"Missing or unsupported input: {candidate}")
    except FileNotFoundError as exc:
        raise ScanError(f"Missing input: {exc.filename}") from exc
    except (OSError, RuntimeError) as exc:
        raise ScanError(f"Could not discover archives: {exc}") from exc
    return sorted(found, key=lambda path: (str(path).casefold(), str(path)))


def _identity(path: Path) -> tuple[int, int, int, int, int]:
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def fingerprint(path: Path) -> Fingerprint:
    try:
        before = _identity(path)
        archive_hash = _hash_file(path)
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
                    page_digest = hashlib.sha256()
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        page_digest.update(chunk)
                    pages.append(page_digest.hexdigest())
            if not pages:
                warnings.append("No supported image pages found.")
        if _identity(path) != before:
            raise ScanError("Archive changed during scan; retry with stable source files")
    except (
        OSError,
        EOFError,
        UnicodeError,
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
        zlib.error,
        lzma.LZMAError,
    ) as exc:
        raise ScanError(f"Could not read archive {path}: {exc}") from exc
    ordered = tuple(sorted(pages))
    digest = hashlib.sha256("\n".join(ordered).encode("ascii")).hexdigest()
    return Fingerprint(
        str(path.resolve()), archive_hash, digest, len(pages), ordered, tuple(warnings)
    )


def scan(
    paths: Iterable[Path],
    *,
    threshold: float = 0.9,
    cache: Path | None = None,
    rehash: bool = False,
    visual: bool = False,
    visual_distance: int = 6,
    multiplicity: bool = False,
) -> dict[str, Any]:
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not 0 < threshold <= 1
        or not math.isfinite(threshold)
    ):
        raise ScanError("threshold must be greater than 0 and at most 1.")
    archives = discover(paths)
    if not archives:
        raise ScanError("No supported CBZ/ZIP archives found")
    if type(visual_distance) is not int or not 0 <= visual_distance <= 64:
        raise ScanError("visual_distance must be between 0 and 64")
    identities = {path: _identity(path) for path in archives}
    hits = 0
    if cache:
        from .cache import cached_fingerprints

        fingerprints, hits = cached_fingerprints(archives, cache, rehash)
    else:
        fingerprints = [fingerprint(path) for path in archives]
    matches = []
    for index, left in enumerate(fingerprints):
        for right in fingerprints[index + 1 :]:
            similarity = _similarity(left.page_hashes, right.page_hashes, multiplicity=multiplicity)
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
    report = {
        "archives_scanned": len(fingerprints),
        "threshold": threshold,
        "matches": matches,
        "archives": [item.public() for item in fingerprints],
        "cache_hits": hits,
        "cache_note": "Metadata cache is an optimization, not proof against deliberate metadata/cache tampering; use --rehash for fresh fingerprints.",
    }
    if multiplicity:
        report["page_overlap_mode"] = "multiplicity"
    if visual:
        from .visual import compare, page_evidence

        try:
            pages = [page_evidence(path) for path in archives]
        except (
            OSError,
            EOFError,
            RuntimeError,
            NotImplementedError,
            UnicodeError,
            zipfile.BadZipFile,
            zlib.error,
            lzma.LZMAError,
        ) as exc:
            raise ScanError(f"Could not read visual evidence: {exc}") from exc
        candidates = []
        for i, left_pages in enumerate(pages):
            for j in range(i + 1, len(pages)):
                candidate = compare(left_pages, pages[j], visual_distance)
                if candidate["pairs"] and candidate["overlap"] >= threshold:
                    candidates.append(
                        {**candidate, "left": str(archives[i]), "right": str(archives[j])}
                    )
        report["visual_matches"] = candidates
        report["visual_review"] = [
            {"path": str(path), "skipped": evidence["skipped"], "truncated": evidence["truncated"]}
            for path, evidence in zip(archives, pages)
        ]
    if any(_identity(path) != identities[path] for path in archives):
        raise ScanError("Archive changed during scan; retry with stable source files")
    return report


def _literal_path(path: str) -> str:
    return "".join(
        f"&#{ord(char)};" if char in string.punctuation else char
        for char in json.dumps(path, ensure_ascii=False)
    )


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Digital comic duplicate report",
        "",
        f"Archives scanned: **{report['archives_scanned']}**",
        f"Matches: **{len(report['matches'])}**",
        "",
    ]
    if report.get("page_overlap_mode"):
        lines.append("Page overlap: multiplicity-aware Jaccard (order ignored).")
    if not report["matches"]:
        lines.append("No exact or likely duplicates met the threshold.")
    for match in report["matches"]:
        lines.extend(
            [
                f"## {match['kind'].replace('_', ' ').title()}",
                "",
                f"- {_literal_path(match['left'])}",
                f"- {_literal_path(match['right'])}",
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


def _similarity(
    left: tuple[str, ...], right: tuple[str, ...], *, multiplicity: bool = False
) -> float:
    if multiplicity:
        left_counts, right_counts = Counter(left), Counter(right)
        union_count = sum((left_counts | right_counts).values())
        return sum((left_counts & right_counts).values()) / union_count if union_count else 0.0
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0
