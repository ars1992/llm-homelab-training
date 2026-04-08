#!/usr/bin/env python3
"""
validate_val.py

Structural and quality validator for val.jsonl.

Checks (verbindlich):
  V001  Jede Zeile ist valides JSON
  V002  Jede Zeile ist ein JSON-Objekt
  V003  Pflichtfelder vorhanden: id, instruction, input, expected_contains, tags
  V004  IDs sind eindeutig (keine Duplikate)
  V005  expected_contains ist eine nicht-leere Liste
  V006  tags ist eine nicht-leere Liste
  V007  Alle expected_contains-Einträge sind nicht-leere Strings

Warnungen (advisory, blockieren nicht):
  W001  expected_contains enthält mehr als MAX_STRICT_TOKENS Einträge (sehr streng)
  W002  tags enthalten keinen bekannten Gruppentyp (exact|runbook|closedbook|openbook)
  W003  instruction kürzer als MIN_INSTRUCTION_LEN Zeichen

Exit codes:
  0  Keine Fehler (Warnungen sind OK)
  1  Mindestens ein V-Check fehlgeschlagen
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Set

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: List[str] = ["id", "instruction", "input", "expected_contains", "tags"]
KNOWN_GROUP_TAGS: Set[str] = {
    "exact",
    "runbook",
    "closedbook",
    "openbook",
    "closedbook_policy",
}
MAX_STRICT_TOKENS: int = 12
MIN_INSTRUCTION_LEN: int = 10


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationError:
    line_no: int
    item_id: Optional[str]
    check: str
    message: str


@dataclass
class ValidationWarning:
    line_no: int
    item_id: Optional[str]
    check: str
    message: str


@dataclass
class ValidationReport:
    dataset_path: str
    total_lines: int = 0
    blank_lines: int = 0
    items_parsed: int = 0
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def passed(self) -> bool:
        return self.error_count == 0


# ---------------------------------------------------------------------------
# Per-item validation
# ---------------------------------------------------------------------------


def validate_item(
    obj: Any,
    line_no: int,
    seen_ids: Set[str],
    max_strict_tokens: int,
    min_instruction_len: int,
) -> tuple[List[ValidationError], List[ValidationWarning]]:
    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []

    # V002 — must be a dict
    if not isinstance(obj, dict):
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=None,
                check="V002",
                message=f"Row is not a JSON object, got {type(obj).__name__}",
            )
        )
        return errors, warnings

    # Extract id for context (may be missing/invalid)
    raw_id = obj.get("id")
    item_id: Optional[str] = (
        str(raw_id).strip() if isinstance(raw_id, str) and str(raw_id).strip() else None
    )

    # V003 — required fields
    missing = [k for k in REQUIRED_FIELDS if k not in obj]
    if missing:
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=item_id,
                check="V003",
                message=f"Missing required fields: {missing}",
            )
        )
        # Cannot validate further without required fields
        return errors, warnings

    # V003 continued — id must be non-empty string
    if not isinstance(obj["id"], str) or not obj["id"].strip():
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=None,
                check="V003",
                message="Field 'id' must be a non-empty string",
            )
        )
    else:
        item_id = obj["id"].strip()

        # V004 — uniqueness
        if item_id in seen_ids:
            errors.append(
                ValidationError(
                    line_no=line_no,
                    item_id=item_id,
                    check="V004",
                    message=f"Duplicate id detected: '{item_id}'",
                )
            )
        else:
            seen_ids.add(item_id)

    # V003 — instruction must be non-empty string
    if not isinstance(obj["instruction"], str) or not obj["instruction"].strip():
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=item_id,
                check="V003",
                message="Field 'instruction' must be a non-empty string",
            )
        )
    else:
        # W003 — instruction length
        if len(obj["instruction"].strip()) < min_instruction_len:
            warnings.append(
                ValidationWarning(
                    line_no=line_no,
                    item_id=item_id,
                    check="W003",
                    message=(
                        f"instruction is very short ({len(obj['instruction'].strip())} chars, "
                        f"min recommended: {min_instruction_len})"
                    ),
                )
            )

    # V003 — input must be string (empty is allowed)
    if not isinstance(obj["input"], str):
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=item_id,
                check="V003",
                message="Field 'input' must be a string",
            )
        )

    # V005 — expected_contains must be non-empty list
    ec = obj["expected_contains"]
    if not isinstance(ec, list) or len(ec) == 0:
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=item_id,
                check="V005",
                message="Field 'expected_contains' must be a non-empty list",
            )
        )
    else:
        # V007 — all entries must be non-empty strings
        for i, token in enumerate(ec):
            if not isinstance(token, str) or not token.strip():
                errors.append(
                    ValidationError(
                        line_no=line_no,
                        item_id=item_id,
                        check="V007",
                        message=f"expected_contains[{i}] is not a non-empty string: {token!r}",
                    )
                )

        # W001 — too many expected_contains tokens (may be overly strict)
        if len(ec) > max_strict_tokens:
            warnings.append(
                ValidationWarning(
                    line_no=line_no,
                    item_id=item_id,
                    check="W001",
                    message=(
                        f"expected_contains has {len(ec)} tokens "
                        f"(threshold: {max_strict_tokens}) — may be overly strict for pass/fail"
                    ),
                )
            )

    # V006 — tags must be non-empty list
    tags = obj["tags"]
    if not isinstance(tags, list) or len(tags) == 0:
        errors.append(
            ValidationError(
                line_no=line_no,
                item_id=item_id,
                check="V006",
                message="Field 'tags' must be a non-empty list",
            )
        )
    else:
        # W002 — no known group tag
        tag_set = {str(t).strip().lower() for t in tags if isinstance(t, str)}
        if not tag_set.intersection(KNOWN_GROUP_TAGS):
            warnings.append(
                ValidationWarning(
                    line_no=line_no,
                    item_id=item_id,
                    check="W002",
                    message=(
                        f"tags contain no known group identifier "
                        f"({sorted(KNOWN_GROUP_TAGS)}). "
                        f"Got: {sorted(tag_set)}"
                    ),
                )
            )

    return errors, warnings


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------


def validate_val_jsonl(
    path: Path,
    max_strict_tokens: int = MAX_STRICT_TOKENS,
    min_instruction_len: int = MIN_INSTRUCTION_LEN,
) -> ValidationReport:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    report = ValidationReport(dataset_path=str(path.resolve()))
    seen_ids: Set[str] = set()

    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            report.total_lines += 1
            line = raw.strip()
            if not line:
                report.blank_lines += 1
                continue

            # V001 — valid JSON
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                report.errors.append(
                    ValidationError(
                        line_no=line_no,
                        item_id=None,
                        check="V001",
                        message=f"Invalid JSON: {exc.msg} (col {exc.colno})",
                    )
                )
                continue

            report.items_parsed += 1
            item_errors, item_warnings = validate_item(
                obj=obj,
                line_no=line_no,
                seen_ids=seen_ids,
                max_strict_tokens=max_strict_tokens,
                min_instruction_len=min_instruction_len,
            )
            report.errors.extend(item_errors)
            report.warnings.extend(item_warnings)

    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(report: ValidationReport, verbose: bool = False) -> None:
    print(f"[validate-val] dataset: {report.dataset_path}")
    print(
        f"[validate-val] lines={report.total_lines}  blank={report.blank_lines}  items={report.items_parsed}"
    )
    print(
        f"[validate-val] errors={report.error_count}  warnings={report.warning_count}"
    )

    if report.errors:
        print("\nERRORS (V-checks):")
        for e in report.errors:
            id_info = f"id={e.item_id!r}" if e.item_id else "id=<unknown>"
            print(f"  [{e.check}] line={e.line_no} {id_info} — {e.message}")

    if report.warnings and verbose:
        print("\nWARNINGS (advisory):")
        for w in report.warnings:
            id_info = f"id={w.item_id!r}" if w.item_id else "id=<unknown>"
            print(f"  [{w.check}] line={w.line_no} {id_info} — {w.message}")
    elif report.warnings and not verbose:
        print(f"\n{report.warning_count} warning(s) — use --verbose to list them")

    # Tag-group summary
    _print_tag_summary(report.dataset_path)

    if report.passed:
        print("\nRESULT: OK — all V-checks passed")
    else:
        print(f"\nRESULT: FAIL — {report.error_count} error(s) found")


def _print_tag_summary(dataset_path: str) -> None:
    """Re-scan file to print tag-group distribution."""
    from collections import Counter

    tag_groups: Counter = Counter()
    strict_counts: List[int] = []

    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue

                tags = obj.get("tags", [])
                if not isinstance(tags, list):
                    continue
                tag_set = {str(t).strip().lower() for t in tags}

                group = "ungrouped"
                if "openbook" in tag_set and "exact" in tag_set:
                    group = "exact_openbook"
                elif "openbook" in tag_set and "runbook" in tag_set:
                    group = "runbook_openbook"
                elif "closedbook" in tag_set or "closedbook_policy" in tag_set:
                    group = "closedbook"
                elif "openbook" in tag_set:
                    group = "openbook_other"
                tag_groups[group] += 1

                ec = obj.get("expected_contains", [])
                if isinstance(ec, list):
                    strict_counts.append(len(ec))

        if tag_groups:
            print("\nTag-group distribution:")
            for grp, cnt in sorted(tag_groups.items(), key=lambda x: -x[1]):
                print(f"  {grp}: {cnt}")

        if strict_counts:
            avg = sum(strict_counts) / len(strict_counts)
            max_ec = max(strict_counts)
            overly_strict = sum(1 for c in strict_counts if c > MAX_STRICT_TOKENS)
            print(
                f"\nexpected_contains stats: avg={avg:.1f}  max={max_ec}  overly_strict(>{MAX_STRICT_TOKENS})={overly_strict}"
            )
    except Exception:
        pass


def write_json_report(report: ValidationReport, path: Path) -> None:
    payload = {
        "dataset_path": report.dataset_path,
        "total_lines": report.total_lines,
        "blank_lines": report.blank_lines,
        "items_parsed": report.items_parsed,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "passed": report.passed,
        "errors": [
            {
                "line_no": e.line_no,
                "item_id": e.item_id,
                "check": e.check,
                "message": e.message,
            }
            for e in report.errors
        ],
        "warnings": [
            {
                "line_no": w.line_no,
                "item_id": w.item_id,
                "check": w.check,
                "message": w.message,
            }
            for w in report.warnings
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[validate-val] JSON report written: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Validate val.jsonl for structural integrity and quality."
    )
    p.add_argument(
        "--dataset",
        type=str,
        default="data/datasets/val.jsonl",
        help="Path to val.jsonl (default: data/datasets/val.jsonl)",
    )
    p.add_argument(
        "--max-strict-tokens",
        type=int,
        default=MAX_STRICT_TOKENS,
        help=f"W001 threshold: items with more expected_contains tokens get a warning (default: {MAX_STRICT_TOKENS})",
    )
    p.add_argument(
        "--min-instruction-len",
        type=int,
        default=MIN_INSTRUCTION_LEN,
        help=f"W003 threshold: minimum instruction length in chars (default: {MIN_INSTRUCTION_LEN})",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print warnings in addition to errors",
    )
    p.add_argument(
        "--report",
        type=str,
        default=None,
        help="Optional path to write JSON report",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on any warning as well (not just errors)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset)

    try:
        report = validate_val_jsonl(
            path=dataset_path,
            max_strict_tokens=args.max_strict_tokens,
            min_instruction_len=args.min_instruction_len,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print_report(report, verbose=args.verbose)

    if args.report:
        write_json_report(report, Path(args.report))

    if args.strict and report.warning_count > 0:
        sys.exit(1)

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
