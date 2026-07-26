# Digital Comic Duplicate Detector

[![CI](https://github.com/loganpendragonmultiverse/digital-comic-duplicate-detector/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/digital-comic-duplicate-detector/actions/workflows/ci.yml)

Digital Comic Duplicate Detector finds exact and likely duplicate CBZ comics without extracting, renaming, or modifying them. It hashes the archive and each supported image page, so copies can still match when filenames, folder layout, ZIP metadata, compression, or page order differ.

## Three-minute start

Requires Python 3.10 or newer.

```bash
python -m pip install .
comic-duplicate-detector "D:\\Comics"
comic-duplicate-detector collection-a collection-b --threshold 0.85 --format json --output duplicates.json
```

Exit code `0` means no matches, `1` means matches were found, and `2` means the scan failed. Reports distinguish byte-identical archives, archives with the same page set, and likely duplicates meeting the page-hash Jaccard threshold.

## Safety and privacy

The scan is read-only and local. Archives are streamed in memory one page at a time and are never extracted. Entry count, individual-page size, and total uncompressed-size limits reduce decompression-bomb risk. There is no telemetry, network request, AI service, or central comic database.

## Limitations

- Version 1 supports CBZ/ZIP archives. CBR and CB7 need format-specific readers and are not claimed.
- Exact page hashes detect identical image bytes, not resized, recompressed, cropped, or visually similar scans.
- Page order is deliberately ignored for content identity; inspect reported pairs before deleting anything.
- A result is evidence for review, not authorization to remove files. The tool never deletes.

## Development and maintenance

Run `python -m pip install -e ".[dev]"`, then `ruff format --check .`, `ruff check .`, `pytest`, and `python -m build`. Contributions go through reviewed pull requests. Version 1.0.0 is feature-complete for safe CBZ byte-content comparison.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md). Licensed under the [MIT License](LICENSE).
