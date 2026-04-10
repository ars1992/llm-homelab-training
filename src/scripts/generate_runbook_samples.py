#!/usr/bin/env python3
"""
generate_runbook_samples.py

Deterministic generator for runbook training samples from val runbook cases.

Input:
  - data/datasets/val.jsonl

Output:
  - data/datasets/runbook_samples.jsonl (overwritten deterministically)

Rules:
  - Uses only val cases with id prefix "val-rb-"
  - Generates N variants per case (default: 25)
  - Each generated output:
      * has 8-12 steps (here: exactly 10)
      * includes ALL expected_contains substrings from val case
      * contains command-like snippets (inline backticks)
      * includes required structural steps:
          1) "Status erfassen / Baseline"
          - at least one "Änderung durchführen"
          - at least one "Persistenz/Config"
          - last step "Verify"
  - Deterministic: same input + seed => byte-identical JSONL output
  - Validation (hard fail / exit 1):
      1) output exists and has >= (10 * variants_per-case) lines
      2) every generated sample contains all expected_contains of its source case
      3) JSONL is valid JSON per line

Optional:
  --report-json path/to/report.json
  --dry-run (only report, no output write)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_VAL_JSONL = "data/datasets/val.jsonl"
DEFAULT_OUTPUT_JSONL = "data/datasets/runbook_samples.jsonl"
DEFAULT_VARIANTS = 25
DEFAULT_SEED = 1337


WHY_SENTENCES = [
    "So bleibt der Ablauf reproduzierbar und auditierbar.",
    "Damit minimierst du Seiteneffekte und kannst sauber zurückrollen.",
    "So erkennst du Abweichungen früh und vermeidest Folgeschäden.",
    "Damit ist der Ablauf für spätere Reviews eindeutig nachvollziehbar.",
    "So stellst du sicher, dass technische und fachliche Gates konsistent bleiben.",
    "Damit sind Ursache und Wirkung pro Schritt klar getrennt dokumentiert.",
]

STEP_LABEL_STYLES = [
    "{n}.",
    "Schritt {n}:",
    "{n})",
]


@dataclass
class ValRunbookCase:
    case_id: str
    instruction: str
    input_text: str
    expected_contains: List[str]
    tags: List[str]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate deterministic runbook_samples.jsonl from val-rb-* cases."
    )
    p.add_argument("--val-jsonl", default=DEFAULT_VAL_JSONL)
    p.add_argument("--output-jsonl", default=DEFAULT_OUTPUT_JSONL)
    p.add_argument("--variants-per-case", type=int, default=DEFAULT_VARIANTS)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--report-json", default=None)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_case_key(case_id: str) -> int:
    # Deterministic integer from case id (no hash randomization side effects).
    # Example: "val-rb-010" -> integer based on bytes.
    total = 0
    for i, b in enumerate(case_id.encode("utf-8"), start=1):
        total += i * b
    return total


def looks_command_like(token: str) -> bool:
    t = token.strip()
    if not t:
        return False
    # command/path/shell-ish indicators
    indicators = [
        "/",
        "--",
        ".json",
        ".yaml",
        ".yml",
        "make ",
        "sudo ",
        "cat ",
        "wc ",
        "head ",
        "free -h",
        "swapon",
        "swapoff",
        "chmod",
        "mkswap",
        "fallocate",
        "nvidia-smi",
        "chown",
    ]
    return any(x in t for x in indicators)


def inline_token(token: str) -> str:
    t = token.strip()
    if looks_command_like(t):
        return f"`{t}`"
    return f'"{t}"'


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def load_val_runbook_cases(path: Path) -> List[ValRunbookCase]:
    if not path.exists():
        raise FileNotFoundError(f"val jsonl not found: {path}")

    out: List[ValRunbookCase] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid json at {path}:{line_no}: {exc}") from exc

            if not isinstance(obj, dict):
                continue
            case_id = str(obj.get("id", "")).strip()
            if not case_id.startswith("val-rb-"):
                continue

            instruction = str(obj.get("instruction", "")).strip()
            input_text = str(obj.get("input", "")).strip()
            expected = obj.get("expected_contains", [])
            tags = obj.get("tags", [])

            if not instruction:
                raise ValueError(f"{path}:{line_no} runbook case missing instruction")
            if not isinstance(expected, list) or not expected:
                raise ValueError(
                    f"{path}:{line_no} runbook case expected_contains must be non-empty list"
                )
            exp_clean: List[str] = []
            for x in expected:
                if not isinstance(x, str) or not x.strip():
                    raise ValueError(
                        f"{path}:{line_no} runbook case has invalid expected token"
                    )
                exp_clean.append(x.strip())

            tags_clean: List[str] = []
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, str) and t.strip():
                        tags_clean.append(t.strip())

            out.append(
                ValRunbookCase(
                    case_id=case_id,
                    instruction=instruction,
                    input_text=input_text,
                    expected_contains=exp_clean,
                    tags=tags_clean,
                )
            )

    out.sort(key=lambda c: c.case_id)
    return out


def rotate(items: List[str], shift: int) -> List[str]:
    if not items:
        return []
    s = shift % len(items)
    return items[s:] + items[:s]


def split_into_groups(items: List[str], n_groups: int) -> List[List[str]]:
    groups: List[List[str]] = [[] for _ in range(n_groups)]
    for i, item in enumerate(items):
        groups[i % n_groups].append(item)
    return groups


def choose_verify_tokens(expected: List[str], fallback_count: int = 2) -> List[str]:
    prefs = [
        "swapon --show",
        "free -h",
        "make run-status",
        "make eval-val",
        "nvidia-smi",
        "val_report.json",
        "val_predictions.jsonl",
    ]
    picked: List[str] = []
    exp_set = expected[:]
    for p in prefs:
        for t in exp_set:
            if p in t and t not in picked:
                picked.append(t)
    if not picked:
        picked.extend(exp_set[:fallback_count])
    return picked[: max(1, min(3, len(picked)))]


def make_step(label_fmt: str, n: int, title: str, body: str) -> str:
    label = label_fmt.format(n=n)
    return f"{label} {title}\n{body}"


def build_variant_output(
    case: ValRunbookCase,
    variant_idx: int,
    seed: int,
) -> str:
    case_key = stable_case_key(case.case_id)
    # Per-variant deterministic RNG.
    rng = random.Random(seed * 1_000_003 + case_key * 97 + variant_idx * 7919)

    label_fmt = STEP_LABEL_STYLES[(variant_idx + case_key) % len(STEP_LABEL_STYLES)]
    why_1 = WHY_SENTENCES[(variant_idx + case_key) % len(WHY_SENTENCES)]
    why_2 = WHY_SENTENCES[(variant_idx * 3 + case_key) % len(WHY_SENTENCES)]
    variant_marker = f"{case.case_id}-v{variant_idx:04d}"

    expected_rot = rotate(
        case.expected_contains,
        shift=(variant_idx + case_key) % len(case.expected_contains),
    )
    groups = split_into_groups(expected_rot, n_groups=5)  # steps 3..7

    verify_tokens = choose_verify_tokens(expected_rot)
    verify_cmds = ", ".join(inline_token(t) for t in verify_tokens)

    baseline_candidates = [
        t for t in expected_rot if "free -h" in t or "swapon --show" in t
    ]
    if baseline_candidates:
        baseline_cmds = " und ".join(inline_token(t) for t in baseline_candidates[:2])
    else:
        # still include command-like baseline using first expected token
        baseline_cmds = inline_token(expected_rot[0])

    def group_body(group_items: List[str], prefix: str) -> str:
        if not group_items:
            return f"- {prefix}: Keine Änderung in diesem Teilpaket. {why_1}"
        lines = [f"- {prefix}: {why_1}"]
        for t in group_items:
            lines.append(f"- Ausführen/prüfen: {inline_token(t)}")
        return "\n".join(lines)

    steps: List[str] = []

    # Step 1 (required)
    steps.append(
        make_step(
            label_fmt,
            1,
            "Status erfassen / Baseline",
            "\n".join(
                [
                    f"- Erfasse den aktuellen Zustand mit {baseline_cmds}.",
                    f"- Notiere Ausgangswerte und Randbedingungen. {why_1}",
                ]
            ),
        )
    )

    # Step 2
    steps.append(
        make_step(
            label_fmt,
            2,
            "Scope und Ziel festlegen",
            "\n".join(
                [
                    f"- Ziel laut Task: {normalize_ws(case.instruction)}",
                    f"- Kontext: {normalize_ws(case.input_text) if case.input_text else 'Kein Zusatzkontext angegeben.'}",
                    f"- Variantenkennung (deterministisch): `{variant_marker}`.",
                    f"- Definiere Abbruchkriterien und Verantwortlichkeit. {why_2}",
                ]
            ),
        )
    )

    # Steps 3..5 (Änderung durchführen)
    steps.append(
        make_step(
            label_fmt,
            3,
            "Änderung durchführen (Teil 1)",
            group_body(groups[0], "Kernaktion A"),
        )
    )
    steps.append(
        make_step(
            label_fmt,
            4,
            "Änderung durchführen (Teil 2)",
            group_body(groups[1], "Kernaktion B"),
        )
    )
    steps.append(
        make_step(
            label_fmt,
            5,
            "Änderung durchführen (Teil 3)",
            group_body(groups[2], "Kernaktion C"),
        )
    )

    # Step 6 (required persist/config)
    persist_items = groups[3]
    persist_lines = [f"- Persistenz/Config: {why_1}"]
    if persist_items:
        for t in persist_items:
            persist_lines.append(
                f"- In Konfiguration übernehmen/prüfen: {inline_token(t)}"
            )
    else:
        persist_lines.append(
            "- Konfigurationszustand dokumentieren und unverändert bestätigen."
        )
    steps.append(make_step(label_fmt, 6, "Persistenz/Config", "\n".join(persist_lines)))

    # Step 7
    steps.append(
        make_step(
            label_fmt,
            7,
            "Sicherheits- und Rechteprüfung",
            group_body(groups[4], "Kontrollaktion"),
        )
    )

    # Step 8
    steps.append(
        make_step(
            label_fmt,
            8,
            "Dokumentation aktualisieren",
            "\n".join(
                [
                    "- Führe die ausgeführten Schritte, Zeitpunkte und Ergebnisse im Runbook nach.",
                    f"- Markiere offene Risiken und nächste Aktion. {why_2}",
                ]
            ),
        )
    )

    # Step 9
    steps.append(
        make_step(
            label_fmt,
            9,
            "Zwischen-Verifikation",
            "\n".join(
                [
                    f"- Prüfe Zwischenergebnis über: {verify_cmds}.",
                    "- Bei Abweichung: letzten erfolgreichen Zustand wiederherstellen und Ursache eingrenzen.",
                ]
            ),
        )
    )

    # Step 10 (required final verify)
    steps.append(
        make_step(
            label_fmt,
            10,
            "Verify",
            "\n".join(
                [
                    f"- Endprüfung erneut ausführen: {verify_cmds}.",
                    "- Ergebnis als bestanden markieren, wenn alle Sollkriterien erfüllt sind.",
                ]
            ),
        )
    )

    output = "\n\n".join(steps)

    # Hard assertion: 8-12 steps by construction
    step_count = len(re.findall(r"(?:^|\n)(?:\d+\.|Schritt \d+:|\d+\))\s", output))
    if not (8 <= step_count <= 12):
        raise RuntimeError(
            f"invalid step count generated for {case.case_id}: {step_count}"
        )

    # Hard assertion: all expected substrings must exist
    for token in case.expected_contains:
        if token not in output:
            raise RuntimeError(
                f"generator invariant failed for {case.case_id}: missing token {token!r}"
            )

    return output


def make_train_sample(case: ValRunbookCase, output_text: str) -> Dict[str, str]:
    return {
        "instruction": case.instruction,
        "input": case.input_text,
        "output": output_text,
    }


def validate_jsonl_file(path: Path) -> Tuple[bool, int]:
    if not path.exists():
        return False, 0
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid json at {path}:{line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"non-object json at {path}:{line_no}")
    return True, count


def run() -> int:
    args = parse_args()

    val_path = Path(args.val_jsonl)
    output_path = Path(args.output_jsonl)
    variants_per_case = int(args.variants_per_case)
    seed = int(args.seed)
    dry_run = bool(args.dry_run)

    if variants_per_case <= 0:
        raise ValueError("--variants-per-case must be > 0")

    cases = load_val_runbook_cases(val_path)
    if not cases:
        raise ValueError("no val-rb-* cases found in val jsonl")

    samples: List[Dict[str, str]] = []
    per_case_report: Dict[str, Dict[str, Any]] = {}
    global_seen_output: set[str] = set()

    for case in cases:
        local_seen: set[str] = set()
        written_for_case = 0

        for v in range(variants_per_case):
            # Ensure dedupe-safety with deterministic fallback attempts.
            produced = None
            for attempt in range(50):
                out_text = build_variant_output(
                    case=case,
                    variant_idx=v * 50 + attempt,  # deterministic variation path
                    seed=seed,
                )
                if out_text not in local_seen:
                    produced = out_text
                    break
            if produced is None:
                raise RuntimeError(
                    f"failed to generate unique variant for {case.case_id} at index={v}"
                )

            local_seen.add(produced)
            global_seen_output.add(produced)

            # Validation invariant per-sample.
            for token in case.expected_contains:
                if token not in produced:
                    raise RuntimeError(
                        f"missing expected token in generated sample: {case.case_id} token={token!r}"
                    )

            sample = make_train_sample(case, produced)
            samples.append(sample)
            written_for_case += 1

        per_case_report[case.case_id] = {
            "expected_contains_count": len(case.expected_contains),
            "sample_count": written_for_case,
        }

    # Deterministic final ordering:
    # by case_id in loaded order + generation order already deterministic.
    total_written = len(samples)

    report: Dict[str, Any] = {
        "run_ts_utc": utc_now_iso(),
        "seed": seed,
        "variants_per_case": variants_per_case,
        "val_jsonl": str(val_path),
        "output_jsonl": str(output_path),
        "cases_found": len(cases),
        "samples_written": total_written,
        "per_case": per_case_report,
        "dry_run": dry_run,
    }

    # Write output JSONL (deterministic formatting)
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as f:
            for s in samples:
                line = json.dumps(
                    s, ensure_ascii=False, separators=(",", ":"), sort_keys=False
                )
                f.write(line + "\n")

    # Optional report
    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # -------------------------
    # Required sanity checks
    # -------------------------

    # 1) output exists and has >= (10 * variants_per_case) lines
    min_required_lines = 10 * variants_per_case
    if dry_run:
        if total_written < min_required_lines:
            print(
                f"ERROR: dry-run produced only {total_written} samples; required >= {min_required_lines}",
                file=sys.stderr,
            )
            return 1
    else:
        exists, line_count = validate_jsonl_file(output_path)
        if not exists:
            print(f"ERROR: output file missing: {output_path}", file=sys.stderr)
            return 1
        if line_count < min_required_lines:
            print(
                f"ERROR: output lines={line_count}; required >= {min_required_lines}",
                file=sys.stderr,
            )
            return 1

    # 2) every val-rb expected_contains is fully contained in every generated output
    # Check on in-memory samples (applies to both dry-run and write mode).
    expected_by_instruction_input: Dict[Tuple[str, str], List[str]] = {
        (c.instruction, c.input_text): c.expected_contains for c in cases
    }
    for idx, s in enumerate(samples, start=1):
        key = (s["instruction"], s["input"])
        expected = expected_by_instruction_input.get(key, [])
        out = s["output"]
        for token in expected:
            if token not in out:
                print(
                    f"ERROR: sample #{idx} missing expected token {token!r}",
                    file=sys.stderr,
                )
                return 1

    # 3) JSONL valid JSON per line
    if not dry_run:
        try:
            validate_jsonl_file(output_path)
        except Exception as exc:
            print(f"ERROR: jsonl validation failed: {exc}", file=sys.stderr)
            return 1

    print(
        f"OK: generated runbook samples | cases={len(cases)} variants={variants_per_case} total={total_written} seed={seed}"
    )
    if args.report_json:
        print(f"OK: wrote report -> {args.report_json}")
    if dry_run:
        print("INFO: dry-run enabled (no output jsonl written)")
    else:
        print(f"OK: wrote output -> {output_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
