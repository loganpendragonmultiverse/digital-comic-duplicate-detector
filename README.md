# Digital Comic Duplicate Detector

[![CI](https://github.com/loganpendragonmultiverse/digital-comic-duplicate-detector/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/digital-comic-duplicate-detector/actions/workflows/ci.yml)

Digital Comic Duplicate Detector finds exact and likely duplicate CBZ comics without extracting, renaming, or modifying them. It hashes the archive and each supported image page, so copies can still match when filenames, folder layout, ZIP metadata, compression, or page order differ.

## Three-minute start

Requires Python 3.11 or newer.

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

## More open-source projects

This project is part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/).

## Version 1.1.0: reviewed improvements

Cache unchanged archive hashes and add opt-in visual comparison with paired page thumbnails and overlap evidence.

```bash
comic-duplicate-detector ./comics --cache hashes.json --visual --format html --output review.html
```

Install the optional visual extra with `pip install 'digital-comic-duplicate-detector[visual]'`. The versioned cache checks file identity, size and nanosecond modification/change timestamps; `--rehash` bypasses it. Metadata is not protection against a deliberately forged cache. Visual comparison uses perceptual dHash distance (`--visual-distance`, default 6), one-to-one page pairing and overlap relative to full archive page counts. It is a review aid, not proof of duplicate content. Visual previews are bounded to 200 pages per archive and flag truncation; image decoding has size limits. Exact and visual groups remain distinct. Reports may contain private page thumbnails. Archives are never modified or deleted; invalid existing caches and existing report outputs are refused.

## 1.2.0: Page multiplicity

The opt-in `--multiplicity` flag compares page-hash counts with multiset Jaccard: sum of minimum counts divided by sum of maximum counts. For A,A,B versus A,B,B the score is 0.5; the default set score remains 1. Page order is ignored in both modes. Exact archive and same-pages labels retain their meanings; visual evidence remains separate. Existing caches contain repeated hashes and work in either mode. Empty page collections have zero overlap, though byte-identical empty archives can still be exact archive matches. Reports never select a preferred copy or delete archives.

```bash
comic-duplicate-detector ./comics --multiplicity --threshold 0.8 --format json
```

## 1.2.1 completion and verification

Missing/unsupported input roots and directories without CBZ/ZIP files are errors,
not clean zero-scan results. Directory traversal errors are actionable. Nested directory
symbolic links are not traversed; source file links are resolved and duplicate
resolved input paths are scanned once.

Archive/page hashes stream, and file identity is checked before and after the
scan, including visual evidence. Keep sources stable: this detects ordinary
changes but is not a filesystem snapshot or protection against deliberate tampering.
Unsupported ZIP headers/compression errors produce actionable scan errors.

Cache headers and cached fingerprint types/content digests are checked; malformed
entries are recalculated. Cache files must be ordinary non-symlink JSON files.
The cache remains a trusted local optimization; use --rehash for fresh proof.
Report output uses exclusive creation and refuses existing/dangling symbolic
links. Accidental concurrent output creation is preserved; hostile concurrent
filesystem changes are outside the guarantee.

CI retains the full native matrix and 90% coverage, and now runs strict mypy plus
a dependency-audit job. Both packages install all four authority documents under
share/doc/digital-comic-duplicate-detector. Before release, test each fresh installed
package outside the checkout, verify import provenance and document hashes, and
exercise real JSON/Markdown/HTML CLI, cached/uncached/multiplicity/visual paths.
Exact tag-workflow artifacts require the same acceptance and independent review.

Visual HTML includes skipped/truncated scan coverage even without a candidate pair. Markdown filenames are rendered as literal evidence rather than report markup.

Filesystem canonicalization failures, including a looping cache link, are actionable CLI errors. Discovery explicitly checks supported archive metadata and refuses unreadable entries instead of silently reporting a completed subset.

## 2.0.0: verified repository ownership

This maintenance release corrects the inherited CODEOWNERS entry to the verified
maintainer user. Version 1.2.1 remains published with its original invalid entry;
use 2.0.0 for the corrected repository materials. Comic scanning behavior is unchanged.

The `codeowners` CI job validates the exact workflow commit against GitHub: the
catch-all entry must name `@LoganPendragonmulti`, resolve to user ID 6430701,
have repository write access, and produce no GitHub CODEOWNERS errors. API or
identity failures fail the job. Existing native tests, coverage, typing, dependency
audit and CodeQL checks remain required. Release acceptance repeats ownership
validation at the exact annotated tag commit. The ownership gate uses the existing workflow
token and existing read-only workflow permissions. It changes no repository access
or protection settings. The separately authorized Python 3.11 migration replaces the three required
Python 3.10 check contexts with their Python 3.11 counterparts. This context
migration is distinct from the read-only ownership gate; the six native matrix
cells and all other protections remain in place.

## 2.0.0 compatibility change

Python 3.11 or newer is required. Pillow 13.0.0 supplies the upstream security
fixes and no longer supports Python 3.10; this project requires Pillow>=13.0.0,<14
for image processing. Python 3.10 users must upgrade their interpreter before
installing this supported release. Previous published releases remain unchanged
and are not represented as receiving these dependency fixes.

The six full native CI cells use Ubuntu, Windows and macOS with Python 3.11 and
3.14. All existing tests/assertions and the 90% coverage threshold remain, along
with formatting, lint, strict typing, dependency audit, builds and CodeQL.
No test skips, advisory waivers or repurposed Python 3.10 job names are introduced.
