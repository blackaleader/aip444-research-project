#!/usr/bin/env python3
"""Offline schema/source validation. Does not load an LLM or an embedding index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_search.benchmark_integrity import ANNOTATION_SET, AnnotationError, GitSource, validate_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--annotation-set", choices=["independent", ANNOTATION_SET], default=ANNOTATION_SET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate_benchmark(ROOT, GitSource(args.repo_path), args.annotation_set)
    except (AnnotationError, KeyError, TypeError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"VALIDATION ERROR: {error}", file=sys.stderr)
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
