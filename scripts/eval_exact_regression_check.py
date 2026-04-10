#!/usr/bin/env python3
"""
eval_exact_regression_check.py

Purpose:
- Lightweight self-check for exact-eval regressions in val_report.json.
- Detects the specific failure mode:
  exact_candidate == expected_contains[0] but pass == false.

Usage examples:
  python scripts/eval_exact_regression_check.py \
    --report data/evals/val-real-20260410T124540Z-20260410T151002Z/val_report.json

  python scripts/eval_exact_regression_check.py \
    --report data/evals/.../val_report.json \
    --cases val-002,val-005,val-013,val-014 \
    --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CASES = ["val-002", "val-005", "val-013", "val-014"]


@dataclass
class CaseCheck:
    case_id: str
    exists: bool
    is_exact: bool
    expected: Optional[str]
    passed: Optional[bool]
    fail_reason: Optional[str]
    exact_candidate: Optional[str]
    normalized_output_preview: Optional[str]
    candidate_equals_expected: bool
    normalized_equals_expected: bool
    suspicious_exact_mismatch: bool
    notes: List[str]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Self-check exact-eval regression behavior in val_report.json."
    )
    p.add_argument(
        "--report",
        required=True,
        help="Path to val_report.json (e.g. data/evals/<run-id>/val_report.json)",
    )
    p.add_argument(
        "--cases",
        default=",".join(DEFAULT_CASES),
        help="Comma-separated case IDs to inspect (default key exact cases).",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Fail if a requested case is missing or not tagged as exact.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary in addition to text output.",
    )
    return p.parse_args()


def load_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Invalid report format: root must be an object")
    if "results" not in data or not isinstance(data["results"], list):
        raise ValueError("Invalid report format: missing list field 'results'")
    return data


def tag_set(tags: Any) -> set:
    if not isinstance(tags, list):
        return set()
    out = set()
    for t in tags:
        if isinstance(t, str):
            x = t.strip().lower()
            if x:
                out.add(x)
    return out


def first_expected(expected_contains: Any) -> Optional[str]:
    if not isinstance(expected_contains, list) or len(expected_contains) == 0:
        return None
    first = expected_contains[0]
    if isinstance(first, str):
        return first
    return None


def evaluate_case(case_id: str, row: Optional[Dict[str, Any]]) -> CaseCheck:
    if row is None:
        return CaseCheck(
            case_id=case_id,
            exists=False,
            is_exact=False,
            expected=None,
            passed=None,
            fail_reason=None,
            exact_candidate=None,
            normalized_output_preview=None,
            candidate_equals_expected=False,
            normalized_equals_expected=False,
            suspicious_exact_mismatch=False,
            notes=["missing_case"],
        )

    tags = tag_set(row.get("tags"))
    is_exact = "exact" in tags
    expected = first_expected(row.get("expected_contains"))
    passed_val = row.get("pass")
    passed = bool(passed_val) if isinstance(passed_val, bool) else None
    fail_reason = (
        row.get("fail_reason") if isinstance(row.get("fail_reason"), str) else None
    )
    exact_candidate = (
        row.get("exact_candidate")
        if isinstance(row.get("exact_candidate"), str)
        else None
    )
    normalized_preview = (
        row.get("normalized_output_preview")
        if isinstance(row.get("normalized_output_preview"), str)
        else None
    )

    candidate_equals_expected = (
        expected is not None
        and exact_candidate is not None
        and exact_candidate == expected
    )
    normalized_equals_expected = (
        expected is not None
        and normalized_preview is not None
        and normalized_preview == expected
    )

    suspicious_exact_mismatch = (
        is_exact
        and passed is False
        and fail_reason == "exact_mismatch"
        and (candidate_equals_expected or normalized_equals_expected)
    )

    notes: List[str] = []
    if not is_exact:
        notes.append("not_exact_tag")
    if expected is None:
        notes.append("missing_expected_contains[0]")
    if passed is None:
        notes.append("missing_or_invalid_pass")
    if suspicious_exact_mismatch:
        notes.append("suspicious_exact_mismatch")

    return CaseCheck(
        case_id=case_id,
        exists=True,
        is_exact=is_exact,
        expected=expected,
        passed=passed,
        fail_reason=fail_reason,
        exact_candidate=exact_candidate,
        normalized_output_preview=normalized_preview,
        candidate_equals_expected=candidate_equals_expected,
        normalized_equals_expected=normalized_equals_expected,
        suspicious_exact_mismatch=suspicious_exact_mismatch,
        notes=notes,
    )


def build_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("id")
        if isinstance(case_id, str) and case_id.strip():
            idx[case_id] = row
    return idx


def print_table(checks: List[CaseCheck]) -> None:
    headers = [
        "case_id",
        "exists",
        "exact",
        "pass",
        "fail_reason",
        "cand==exp",
        "norm==exp",
        "suspicious",
    ]
    rows = []
    for c in checks:
        rows.append(
            [
                c.case_id,
                str(c.exists),
                str(c.is_exact),
                str(c.passed),
                c.fail_reason or "",
                str(c.candidate_equals_expected),
                str(c.normalized_equals_expected),
                str(c.suspicious_exact_mismatch),
            ]
        )

    widths = [len(h) for h in headers]
    for r in rows:
        for i, val in enumerate(r):
            widths[i] = max(widths[i], len(val))

    def fmt(r: List[str]) -> str:
        return " | ".join(val.ljust(widths[i]) for i, val in enumerate(r))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt(r))


def main() -> None:
    args = parse_args()
    report_path = Path(args.report)
    requested_cases = [c.strip() for c in str(args.cases).split(",") if c.strip()]

    report = load_report(report_path)
    rows = report.get("results", [])
    if not isinstance(rows, list):
        raise ValueError("Invalid report format: results must be a list")

    idx = build_index(rows)
    checks = [evaluate_case(case_id, idx.get(case_id)) for case_id in requested_cases]

    print(f"report={report_path}")
    print(f"requested_cases={','.join(requested_cases)}")
    print()
    print_table(checks)
    print()

    suspicious = [c for c in checks if c.suspicious_exact_mismatch]
    missing = [c for c in checks if not c.exists]
    not_exact = [c for c in checks if c.exists and not c.is_exact]

    # Exit policy
    # rc=1 if suspicious mismatch exists.
    # rc=1 in strict mode if missing/not_exact exists.
    rc = 0
    if suspicious:
        rc = 1
        print("RESULT=FAIL")
        print("reason=suspicious_exact_mismatch_detected")
        print("details=" + ",".join(c.case_id for c in suspicious))
    elif args.strict and (missing or not_exact):
        rc = 1
        print("RESULT=FAIL")
        reasons = []
        if missing:
            reasons.append("missing_cases=" + ",".join(c.case_id for c in missing))
        if not_exact:
            reasons.append("not_exact_cases=" + ",".join(c.case_id for c in not_exact))
        print("reason=" + ";".join(reasons))
    else:
        print("RESULT=PASS")
        print("reason=no_suspicious_exact_mismatch")

    if args.json:
        payload = {
            "report": str(report_path),
            "requested_cases": requested_cases,
            "summary": {
                "total": len(checks),
                "suspicious_exact_mismatch": len(suspicious),
                "missing_cases": len(missing),
                "not_exact_cases": len(not_exact),
                "strict": bool(args.strict),
                "result": "FAIL" if rc != 0 else "PASS",
            },
            "checks": [
                {
                    "case_id": c.case_id,
                    "exists": c.exists,
                    "is_exact": c.is_exact,
                    "expected": c.expected,
                    "pass": c.passed,
                    "fail_reason": c.fail_reason,
                    "exact_candidate": c.exact_candidate,
                    "normalized_output_preview": c.normalized_output_preview,
                    "candidate_equals_expected": c.candidate_equals_expected,
                    "normalized_equals_expected": c.normalized_equals_expected,
                    "suspicious_exact_mismatch": c.suspicious_exact_mismatch,
                    "notes": c.notes,
                }
                for c in checks
            ],
        }
        print()
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    sys.exit(rc)


if __name__ == "__main__":
    main()
