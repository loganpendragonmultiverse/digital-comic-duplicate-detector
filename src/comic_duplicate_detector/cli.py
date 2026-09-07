"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import ScanError, markdown, scan


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="comic-duplicate-detector")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--format", choices=("markdown", "json", "html"), default="markdown")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--rehash", action="store_true")
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--visual-distance", type=int, default=6)
    parser.add_argument("--output", type=Path)
    try:
        args = parser.parse_args(argv)
        if args.output and args.output.exists():
            raise ScanError(f"Output already exists: {args.output}")
        if args.cache and args.output and args.cache.resolve() == args.output.resolve():
            raise ScanError("Cache and report paths must differ")
        result = scan(
            args.paths,
            threshold=args.threshold,
            cache=args.cache,
            rehash=args.rehash,
            visual=args.visual,
            visual_distance=args.visual_distance,
        )
        rendered = (
            json.dumps(result, indent=2) + "\n" if args.format == "json" else markdown(result)
        )
        if args.format == "html":
            from .visual import render_html

            rendered = render_html(result)
        if args.output:
            if args.output.exists():
                raise ScanError(f"Output already exists: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(args.output.resolve())
        else:
            print(rendered, end="")
        return 1 if result["matches"] or result.get("visual_matches") else 0
    except (ScanError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
