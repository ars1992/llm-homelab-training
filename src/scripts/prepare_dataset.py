#!/usr/bin/env python3
"""
prepare_dataset.py

Dataset preparation skeleton for instruction tuning.
Expected input format per JSONL line:

{
  "instruction": "...",   # required, non-empty string
  "input": "...",         # optional string (normalized to "")
  "output": "..."         # required, non-empty string
}

This script validates records and writes a normalized JSONL output.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ValidationIssue:
    line_no: int
    reason: str


@dataclass
class PrepareSummary:
    total_lines: int
    valid_records: int
    invalid_records: int
    issues: List[ValidationIssue]


def _as_clean_string(value: Any) -> Optional[str]:
    """Return stripped string if value is str, else None."""
    if not isinstance(value, str):
        return None
    return value.strip()


def validate_record(
    obj: Dict[str, Any],
    line_no: int,
    allow_empty_input: bool = True,
) -> Tuple[bool, Optional[Dict[str, str]], Optional[str]]:
    """
    Validate and normalize a single record.
    Returns:
      (is_valid, normalized_record, error_reason)
    """
    if not isinstance(obj, dict):
        return False, None, "record must be a JSON object"

    instruction = _as_clean_string(obj.get("instruction"))
    output = _as_clean_string(obj.get("output"))

    if instruction is None or instruction == "":
        return False, None, "'instruction' is required and must be a non-empty string"

    if output is None or output == "":
        return False, None, "'output' is required and must be a non-empty string"

    raw_input = obj.get("input", "")
    normalized_input = _as_clean_string(raw_input)

    if normalized_input is None:
        return False, None, "'input' must be a string when present"

    if not allow_empty_input and normalized_input == "":
        return False, None, "'input' must be non-empty in current validation mode"

    normalized = {
        "instruction": instruction,
        "input": normalized_input,
        "output": output,
    }
    return True, normalized, None


def prepare_dataset(
    input_path: Path,
    output_path: Path,
    strict: bool = False,
    max_samples: Optional[int] = None,
    allow_empty_input: bool = True,
    encoding: str = "utf-8",
) -> PrepareSummary:
    """
    Read input JSONL, validate format, and write normalized JSONL.
    - strict=False: skip invalid records and continue
    - strict=True: fail on first invalid record
    """
    issues: List[ValidationIssue] = []
    normalized_records: List[Dict[str, str]] = []
    total_lines = 0

    with input_path.open("r", encoding=encoding) as f:
        for line_no, raw_line in enumerate(f, start=1):
            if max_samples is not None and len(normalized_records) >= max_samples:
                break

            line = raw_line.strip()
            if line == "":
                # Skip empty lines silently
                continue

            total_lines += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                reason = f"invalid JSON: {exc.msg}"
                issues.append(ValidationIssue(line_no=line_no, reason=reason))
                if strict:
                    raise ValueError(f"Line {line_no}: {reason}") from exc
                continue

            is_valid, normalized, error = validate_record(
                obj=obj,
                line_no=line_no,
                allow_empty_input=allow_empty_input,
            )

            if not is_valid:
                reason = error or "unknown validation error"
                issues.append(ValidationIssue(line_no=line_no, reason=reason))
                if strict:
                    raise ValueError(f"Line {line_no}: {reason}")
                continue

            normalized_records.append(normalized)  # type: ignore[arg-type]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding=encoding) as out:
        for record in normalized_records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    return PrepareSummary(
        total_lines=total_lines,
        valid_records=len(normalized_records),
        invalid_records=len(issues),
        issues=issues,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and validate instruction-tuning dataset (JSONL)."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to source JSONL dataset.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to normalized output JSONL dataset.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on first invalid record instead of skipping invalid rows.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Optional cap for number of valid records to write.",
    )
    parser.add_argument(
        "--disallow-empty-input",
        action="store_true",
        help="Treat empty 'input' as invalid.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    summary = prepare_dataset(
        input_path=input_path,
        output_path=output_path,
        strict=args.strict,
        max_samples=args.max_samples,
        allow_empty_input=not args.disallow_empty_input,
        encoding=args.encoding,
    )

    print("Dataset preparation completed.")
    print(f"Input lines processed: {summary.total_lines}")
    print(f"Valid records written: {summary.valid_records}")
    print(f"Invalid records: {summary.invalid_records}")

    if summary.invalid_records > 0:
        print("\nValidation issues:")
        for issue in summary.issues[:20]:
            print(f"  - line {issue.line_no}: {issue.reason}")
        if len(summary.issues) > 20:
            print(f"  ... and {len(summary.issues) - 20} more")


if __name__ == "__main__":
    main()
