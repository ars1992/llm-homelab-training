#!/usr/bin/env python3
"""
merge_datasets.py

Merges multiple JSONL dataset files into a single deduplicated output.
Used for combining vault extraction, exact_extraction samples and runbook samples.

Deduplication strategy: content-level (identical JSON lines are dropped).
Order: sources are processed in the order given; first occurrence wins.

Usage:
    python src/scripts/merge_datasets.py \
        --sources data/datasets/train_vault.jsonl \
                  data/datasets/exact_extraction_samples.jsonl \
                  data/datasets/runbook_samples.jsonl \
        --output data/datasets/train.jsonl \
        --report data/datasets/merge_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def merge_jsonl_sources(
    sources: List[Path],
    output: Path,
    max_samples: Optional[int],
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Read JSONL sources in order, deduplicate by raw line content, write merged output.

    Returns a report dict with per-source stats and totals.
    """
    seen: set = set()
    merged: List[str] = []
    source_stats: List[Dict[str, Any]] = []

    for src in sources:
        if not src.exists():
            print(f"WARN: source not found, skipping: {src}", file=sys.stderr)
            source_stats.append(
                {
                    "path": str(src),
                    "exists": False,
                    "lines_read": 0,
                    "records_added": 0,
                    "duplicates_skipped": 0,
                    "invalid_json_skipped": 0,
                }
            )
            continue

        lines_read = 0
        records_added = 0
        duplicates_skipped = 0
        invalid_json_skipped = 0

        with src.open("r", encoding=encoding) as f:
            for raw in f:
                if max_samples is not None and len(merged) >= max_samples:
                    break

                line = raw.strip()
                if not line:
                    continue

                lines_read += 1

                # Validate JSON before adding
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    invalid_json_skipped += 1
                    print(
                        f"WARN: invalid JSON in {src}, skipping line {lines_read}",
                        file=sys.stderr,
                    )
                    continue

                # Normalise line for deduplication (re-serialise to canonical form)
                canonical = json.dumps(obj, ensure_ascii=False, sort_keys=True)

                if canonical in seen:
                    duplicates_skipped += 1
                    continue

                seen.add(canonical)
                # Write the original (non-sorted) line for readability
                merged.append(line)
                records_added += 1

        print(
            f"INFO: {src.name}: read={lines_read} added={records_added} "
            f"dupes={duplicates_skipped} invalid={invalid_json_skipped}"
        )
        source_stats.append(
            {
                "path": str(src),
                "exists": True,
                "lines_read": lines_read,
                "records_added": records_added,
                "duplicates_skipped": duplicates_skipped,
                "invalid_json_skipped": invalid_json_skipped,
            }
        )

    # Write merged output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding=encoding) as out_f:
        for line in merged:
            out_f.write(line + "\n")

    total = len(merged)
    print(f"INFO: merged total={total} records -> {output}")

    return {
        "output_path": str(output.resolve()),
        "total_records": total,
        "sources": source_stats,
    }


# ---------------------------------------------------------------------------
# Schema validation (lightweight)
# ---------------------------------------------------------------------------


def validate_output_schema(output: Path, encoding: str = "utf-8") -> bool:
    """
    Spot-check first and last record for required fields.
    Returns True if schema appears valid, False otherwise.
    """
    required = {"instruction", "output"}
    lines: List[str] = []
    with output.open("r", encoding=encoding) as f:
        for raw in f:
            line = raw.strip()
            if line:
                lines.append(line)

    if not lines:
        print("WARN: output file is empty", file=sys.stderr)
        return False

    for sample_line in [lines[0], lines[-1]]:
        try:
            obj = json.loads(sample_line)
        except json.JSONDecodeError:
            print("ERROR: output contains invalid JSON lines", file=sys.stderr)
            return False
        missing = required - set(obj.keys())
        if missing:
            print(
                f"ERROR: output record missing required fields: {missing}",
                file=sys.stderr,
            )
            return False
        if not str(obj.get("instruction", "")).strip():
            print("ERROR: 'instruction' is empty in sampled record", file=sys.stderr)
            return False
        if not str(obj.get("output", "")).strip():
            print("ERROR: 'output' is empty in sampled record", file=sys.stderr)
            return False

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Merge multiple JSONL training dataset files into one deduplicated output. "
            "Sources are processed in declaration order; first occurrence wins on duplicates."
        )
    )
    p.add_argument(
        "--sources",
        nargs="+",
        required=True,
        metavar="PATH",
        help="One or more source JSONL files to merge (in priority order).",
    )
    p.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output JSONL path for merged dataset.",
    )
    p.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Maximum output records (0 = unlimited).",
    )
    p.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8).",
    )
    p.add_argument(
        "--report",
        default=None,
        metavar="PATH",
        help="Optional JSON report output path.",
    )
    p.add_argument(
        "--validate-schema",
        action="store_true",
        default=True,
        help="Spot-check output schema after merge (default: True).",
    )
    p.add_argument(
        "--no-validate-schema",
        dest="validate_schema",
        action="store_false",
        help="Skip output schema validation.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    sources = [Path(s) for s in args.sources]
    output = Path(args.output)
    max_samples: Optional[int] = int(args.max_samples) if args.max_samples > 0 else None

    report = merge_jsonl_sources(
        sources=sources,
        output=output,
        max_samples=max_samples,
        encoding=args.encoding,
    )

    if args.validate_schema and output.exists() and report["total_records"] > 0:
        ok = validate_output_schema(output, encoding=args.encoding)
        report["schema_valid"] = ok
        if ok:
            print("OK: schema validation passed")
        else:
            print("ERROR: schema validation failed", file=sys.stderr)
            sys.exit(1)
    else:
        report["schema_valid"] = None

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding=args.encoding) as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"INFO: report written -> {report_path}")

    if report["total_records"] == 0:
        print("WARN: merged output is empty — check source paths", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
