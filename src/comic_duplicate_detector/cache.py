"""Versioned metadata-invalidated cache; explicit rehash remains available."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .core import Fingerprint, ScanError, fingerprint


def identity(path: Path) -> list[int]:
    info = path.stat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def cached_fingerprints(
    paths: list[Path], cache: Path, rehash: bool
) -> tuple[list[Fingerprint], int]:
    if cache.suffix.lower() != ".json":
        raise ScanError("Cache must use a dedicated .json path")
    data: dict[str, Any] = {"schema": 1, "algorithm": "sha256-pages-v1", "entries": {}}
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or data.get("schema") != 1
                or data.get("algorithm") != "sha256-pages-v1"
                or not isinstance(data.get("entries"), dict)
            ):
                raise ValueError("wrong cache schema")
        except (ValueError, TypeError) as exc:
            raise ScanError("Existing cache is invalid; choose a new dedicated cache path") from exc
    results = []
    hits = 0
    for path in paths:
        key = str(path.resolve())
        before = identity(path)
        entry = data["entries"].get(key)
        result = None
        if not rehash and isinstance(entry, dict) and entry.get("identity") == before:
            try:
                value = entry["fingerprint"]
                result = Fingerprint(
                    path=key,
                    archive_sha256=value["archive_sha256"],
                    content_sha256=value["content_sha256"],
                    page_count=value["page_count"],
                    page_hashes=tuple(value["page_hashes"]),
                    warnings=tuple(value["warnings"]),
                )
                hashes = (result.archive_sha256, result.content_sha256, *result.page_hashes)
                if result.page_count != len(result.page_hashes) or not all(
                    isinstance(item, str)
                    and len(item) == 64
                    and all(c in "0123456789abcdef" for c in item)
                    for item in hashes
                ):
                    result = None
            except (KeyError, TypeError):
                result = None
        if result is None:
            result = fingerprint(path)
        else:
            hits += 1
        if identity(path) != before:
            raise ScanError("Archive changed during scan; retry with stable source files")
        data["entries"][key] = {"identity": before, "fingerprint": result.public()}
        results.append(result)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=cache.parent, suffix=".tmp", delete=False
    ) as handle:
        json.dump(data, handle, indent=2)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, cache)
    finally:
        temporary.unlink(missing_ok=True)
    return results, hits
