# Testing

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`. CI also audits dependencies and runs the supported OS/Python matrix.

## 1.1.0 reviewed improvements

Cache unchanged archive hashes and add opt-in visual comparison with paired page thumbnails and overlap evidence.

Install the optional visual extra with `pip install 'digital-comic-duplicate-detector[visual]'`. The versioned cache checks file identity, size and nanosecond modification/change timestamps; `--rehash` bypasses it. Metadata is not protection against a deliberately forged cache. Visual comparison uses perceptual dHash distance (`--visual-distance`, default 6), one-to-one page pairing and overlap relative to full archive page counts. It is a review aid, not proof of duplicate content. Visual previews are bounded to 200 pages per archive and flag truncation; image decoding has size limits. Exact and visual groups remain distinct. Reports may contain private page thumbnails. Archives are never modified or deleted; invalid existing caches and existing report outputs are refused.

Validation: formatting, lint, types and all 13 regression tests pass locally. Protected remote CI and release verification remain required.

## 1.2.0: Page multiplicity

The opt-in `--multiplicity` flag compares page-hash counts with multiset Jaccard: sum of minimum counts divided by sum of maximum counts. For A,A,B versus A,B,B the score is 0.5; the default set score remains 1. Page order is ignored in both modes. Exact archive and same-pages labels retain their meanings; visual evidence remains separate. Existing caches contain repeated hashes and work in either mode. Empty page collections have zero overlap, though byte-identical empty archives can still be exact archive matches. Reports never select a preferred copy or delete archives.

```bash
comic-duplicate-detector ./comics --multiplicity --threshold 0.8 --format json
```
