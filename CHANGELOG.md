# Changelog

## 2.0.1 - 2026-10-22

- Replace greedy visual page matching with bounded maximum-cardinality matching so local choices cannot hide valid overlap pairs.
- Preserve exact-byte and multiplicity comparisons, partial-coverage warnings and the read-only archive boundary.
- Add all-order counterexample and empty/disconnected regression cases.

## 2.0.0 — 2026-10-20

- Require Python 3.11 or newer and Pillow 13.0.0 or newer (below 14); the fixed dependency no longer supports Python 3.10.
- Retain every existing test/assertion, 90% coverage and all three operating systems; test Python 3.11 and 3.14 in six full native cells.
- Retain prior scanning and report improvements. Old published releases remain unchanged.


### Repository ownership correction

- Correct CODEOWNERS to the verified maintainer user with repository write access.
- Add an exact-commit GitHub ownership gate that rejects unknown owners, organization/user confusion, missing access and API failures.
- Preserve the published 1.2.1 release; it contained an invalid ownership entry and is superseded by this maintenance release.

## 1.2.1 — 2026-10-20

- Make missing inputs and unreadable directories actionable.
- Stream page hashes and check source stability in cached, uncached and visual scans.
- Validate cached fingerprint types/content identity and refuse linked/nonregular cache files.
- Create reports exclusively and correct visual report typography.
- Run promised typing/dependency checks and install the four authority documents.

## 1.2.0 - 2026-10-16

- Added opt-in multiplicity-aware page overlap while preserving default set comparison and separate visual evidence.
- Added synthetic regression tests for boundaries, aggregation and unchanged inputs.


## 1.1.0 - 2026-09-07

- Cache unchanged archive hashes and add opt-in visual comparison with paired page thumbnails and overlap evidence.
- Added regression coverage for the audited behavior and invalid inputs.

## [1.0.0] - 2026-07-26

- Initial read-only CBZ discovery, archive/page hashing, exact and threshold matches, safety limits, Markdown/JSON reports, and automated tests.

[1.0.0]: https://github.com/loganpendragonmultiverse/digital-comic-duplicate-detector/releases/tag/v1.0.0
