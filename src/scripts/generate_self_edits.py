#!/usr/bin/env python3
"""
generate_self_edits.py

Deterministic SEAL-MVP self-edit orchestrator with three modes:

1) placeholder (legacy-compatible):
   - Generates placeholder candidate records into --output-jsonl
   - Optional --report-json
   - Keeps old integration path stable

2) generate (SEAL-MVP):
   - Builds full run artifact set under data/self_edits/runs/<run_id>/
       * sources.snapshot.jsonl
       * candidates.jsonl
       * verifications.jsonl
       * accepted.derived.jsonl
       * manifest.json
   - Exports accepted derived training samples to:
       data/training/derived/self_edits.accepted.jsonl
   - Deterministic candidate generation + rule-based verification

3) validate:
   - Validates generated run artifacts and optional export JSONL
   - Fails fast on parse/schema-level errors

Design principles:
- Deterministic behavior (except run_id / timestamps when auto-generated)
- Full audit trail and stable IDs
- No cloud dependency, no model inference
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

# -----------------------------
# Constants
# -----------------------------

DEFAULT_SEED = 1337
DEFAULT_MAX_SOURCES = 50
DEFAULT_CANDIDATES_PER_SOURCE = 1
DEFAULT_EXPORT_ACCEPTED = "data/training/derived/self_edits.accepted.jsonl"
DEFAULT_RUNS_ROOT = "data/self_edits/runs"

KNOWN_WRAPPERS = [
    "kontext:",
    "antwort:",
    "instruction:",
    "### instruction:",
    "### response:",
    "aufgabe:",
    "fokus:",
    "regel:",
]

SECRET_PATTERNS = [
    re.compile(r"(?i)\bapi[_-]?key\b"),
    re.compile(r"(?i)\bsecret\b"),
    re.compile(r"(?i)\btoken\b"),
    re.compile(r"(?i)\bpassword\b"),
    re.compile(r"(?i)\bpasswd\b"),
    re.compile(r"(?i)AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{20,}"),
]

ABSOLUTE_HOST_PATH_PATTERNS = [
    re.compile(r"(?<!\w)/home/"),
    re.compile(r"(?<!\w)/Users/"),
    re.compile(r"(?<!\w)/mnt/"),
    re.compile(r"(?<!\w)/private/"),
    re.compile(r"(?<!\w)/var/"),
]


# -----------------------------
# Data model
# -----------------------------


@dataclasses.dataclass
class SourceSample:
    source_sample_id: str
    line_no: int
    instruction: str
    input: str
    output: str
    source_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class EditCandidate:
    candidate_id: str
    run_id: str
    source_sample_id: str
    candidate_index: int
    strategy: str
    rationale: str
    original_output: str
    proposed_output: str
    audit: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class VerificationRecord:
    verification_id: str
    run_id: str
    candidate_id: str
    source_sample_id: str
    decision: str  # accept|reject|needs_review
    checks: Dict[str, Any]
    reasons: List[str]
    audit: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class DerivedTrainingSample:
    instruction: str
    input: str
    output: str
    provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# -----------------------------
# Helpers
# -----------------------------


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def utc_run_id(prefix: str = "self-edit") -> str:
    return f"{prefix}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def ensure_parent_dir(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


def stable_hash(payload: str, size: int = 12) -> str:
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:size]


def stable_json_dumps(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"JSON line is not an object at {path}:{line_no}")
            yield line_no, obj


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    ensure_parent_dir(path)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(stable_json_dumps(row) + "\n")
            count += 1
    return count


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_wrappers(text: str) -> str:
    out = normalize_newlines(text)
    for w in KNOWN_WRAPPERS:
        out = re.sub(rf"(?im)^\s*{re.escape(w)}\s*", "", out)
    return out


def collapse_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def validate_source_obj(line_no: int, obj: Dict[str, Any]) -> SourceSample:
    for key in ("instruction", "output"):
        if key not in obj:
            raise ValueError(f"Missing required field '{key}' at line {line_no}")
        if not isinstance(obj[key], str):
            raise ValueError(f"Field '{key}' must be string at line {line_no}")

    instruction = obj["instruction"].strip()
    output = obj["output"]
    input_text = obj.get("input", "")
    if not isinstance(input_text, str):
        raise ValueError(f"Field 'input' must be string at line {line_no}")

    if not instruction:
        raise ValueError(f"Field 'instruction' is empty at line {line_no}")

    source_sample_id = (
        obj["id"].strip()
        if isinstance(obj.get("id"), str) and obj["id"].strip()
        else f"line-{line_no}"
    )
    source_hash = stable_hash(
        f"{source_sample_id}|{instruction}|{input_text}|{output}", size=16
    )

    return SourceSample(
        source_sample_id=source_sample_id,
        line_no=line_no,
        instruction=instruction,
        input=input_text,
        output=output,
        source_hash=source_hash,
    )


# -----------------------------
# Candidate generation (deterministic)
# -----------------------------


def strategy_normalize_whitespace(text: str) -> str:
    t = normalize_newlines(text)
    lines = [collapse_ws(x) for x in t.split("\n")]
    return "\n".join(lines).strip()


def strategy_strip_wrappers(text: str) -> str:
    return strip_wrappers(text).strip()


def strategy_first_line_only(text: str) -> str:
    t = strip_wrappers(normalize_newlines(text))
    return t.split("\n", 1)[0].strip()


def strategy_trim_trailing_noise(text: str) -> str:
    t = normalize_newlines(text)
    # cut everything after repeated template markers
    cut_markers = ["###", "Kontext:", "Antwort:", "Instruction:"]
    lower = t.lower()
    cut_pos: Optional[int] = None
    for m in cut_markers:
        idx = lower.find(m.lower())
        if idx != -1 and idx > 0:
            if cut_pos is None or idx < cut_pos:
                cut_pos = idx
    if cut_pos is not None:
        t = t[:cut_pos]
    return collapse_ws(t)


STRATEGIES = [
    ("normalize_whitespace", strategy_normalize_whitespace, "Whitespace normalisiert."),
    ("strip_wrappers", strategy_strip_wrappers, "Bekannte Wrapper entfernt."),
    (
        "first_line_only",
        strategy_first_line_only,
        "Auf die erste relevante Zeile reduziert.",
    ),
    (
        "trim_trailing_noise",
        strategy_trim_trailing_noise,
        "Wiederholungs-/Template-Rauschen abgeschnitten.",
    ),
]


def generate_candidate(
    run_id: str,
    source: SourceSample,
    candidate_index: int,
    seed: int,
) -> EditCandidate:
    # deterministic strategy pick
    selector_seed = stable_hash(
        f"{run_id}|{source.source_sample_id}|{candidate_index}|{seed}", size=16
    )
    selector_int = int(selector_seed, 16)
    strategy_name, strategy_fn, rationale = STRATEGIES[selector_int % len(STRATEGIES)]

    proposed = strategy_fn(source.output)
    if not proposed:
        proposed = source.output.strip()

    candidate_id = f"cand-{stable_hash(f'{run_id}|{source.source_sample_id}|{candidate_index}|{proposed}', size=20)}"

    audit = {
        "event_type": "self_edit_candidate_generated",
        "event_ts": utc_now_iso(),
        "actor_type": "system",
        "actor_id": "generate_self_edits.py",
        "pipeline": "seal-mvp-deterministic-v1",
        "seed": seed,
        "run_id": run_id,
    }

    return EditCandidate(
        candidate_id=candidate_id,
        run_id=run_id,
        source_sample_id=source.source_sample_id,
        candidate_index=candidate_index,
        strategy=strategy_name,
        rationale=rationale,
        original_output=source.output,
        proposed_output=proposed,
        audit=audit,
    )


# -----------------------------
# Verification (deterministic rule-based)
# -----------------------------


def has_secret_signal(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


def has_absolute_host_path_signal(text: str) -> bool:
    return any(p.search(text) for p in ABSOLUTE_HOST_PATH_PATTERNS)


def verify_candidate(candidate: EditCandidate, seed: int) -> VerificationRecord:
    checks: Dict[str, Any] = {}

    checks["schema_required_fields_ok"] = bool(
        candidate.candidate_id
        and candidate.source_sample_id
        and isinstance(candidate.proposed_output, str)
        and isinstance(candidate.original_output, str)
    )
    checks["no_op_diff_ok"] = candidate.proposed_output != candidate.original_output
    checks["no_secret_signal_ok"] = not has_secret_signal(candidate.proposed_output)
    checks["no_absolute_host_path_signal_ok"] = not has_absolute_host_path_signal(
        candidate.proposed_output
    )

    reasons: List[str] = []
    if not checks["schema_required_fields_ok"]:
        reasons.append("schema_required_fields_failed")
    if not checks["no_op_diff_ok"]:
        reasons.append("no_op_candidate")
    if not checks["no_secret_signal_ok"]:
        reasons.append("secret_like_signal_detected")
    if not checks["no_absolute_host_path_signal_ok"]:
        reasons.append("absolute_host_path_signal_detected")

    # Decision logic:
    # - reject: schema/no-op fails
    # - needs_review: policy heuristics fail
    # - accept: all checks pass
    if not checks["schema_required_fields_ok"] or not checks["no_op_diff_ok"]:
        decision = "reject"
    elif (
        not checks["no_secret_signal_ok"]
        or not checks["no_absolute_host_path_signal_ok"]
    ):
        decision = "needs_review"
    else:
        decision = "accept"

    verification_id = f"ver-{stable_hash(f'{candidate.run_id}|{candidate.candidate_id}|{decision}|{seed}', size=20)}"
    audit = {
        "event_type": "self_edit_candidate_verified",
        "event_ts": utc_now_iso(),
        "actor_type": "system",
        "actor_id": "deterministic_rule_verifier",
        "pipeline": "seal-mvp-deterministic-v1",
        "seed": seed,
        "run_id": candidate.run_id,
    }

    return VerificationRecord(
        verification_id=verification_id,
        run_id=candidate.run_id,
        candidate_id=candidate.candidate_id,
        source_sample_id=candidate.source_sample_id,
        decision=decision,
        checks=checks,
        reasons=reasons,
        audit=audit,
    )


# -----------------------------
# Modes
# -----------------------------


def mode_placeholder(args: argparse.Namespace) -> int:
    if not args.output_jsonl:
        raise ValueError("--output-jsonl is required in placeholder mode")

    input_path = Path(args.input_jsonl)
    output_path = Path(args.output_jsonl)

    run_id = args.run_id.strip() if args.run_id else ""
    if not run_id:
        run_id = utc_run_id("self-edit")

    rows: List[Dict[str, Any]] = []
    processed = 0
    max_samples = max(0, int(args.max_samples))

    for line_no, obj in read_jsonl(input_path):
        if max_samples and processed >= max_samples:
            break
        src = validate_source_obj(line_no, obj)

        candidate_id = f"{run_id}-{stable_hash(f'{src.source_sample_id}|{line_no}|placeholder', size=12)}"
        row = {
            "run_id": run_id,
            "source": {
                "example_id": src.source_sample_id,
                "instruction": src.instruction,
                "input": src.input,
            },
            "candidate": {
                "candidate_id": candidate_id,
                "source_example_id": src.source_sample_id,
                "strategy": "noop_identity_placeholder",
                "rationale": "Placeholder candidate for future SEAL loop; no semantic edit applied in MVP.",
                "original_output": src.output,
                "proposed_output": src.output,
                "confidence": 0.10,
                "metadata": {
                    "generator": "generate_self_edits.py",
                    "mode": "placeholder",
                    "timestamp_utc": utc_now_iso(),
                },
            },
            "status": "generated_placeholder",
        }
        rows.append(row)
        processed += 1

    written = write_jsonl(output_path, rows)

    report = {
        "run_id": run_id,
        "mode": "placeholder",
        "input_jsonl": str(input_path.resolve()),
        "output_jsonl": str(output_path.resolve()),
        "processed_examples": processed,
        "written_candidates": written,
        "generator_version": "seal-mvp-placeholder-v2",
        "timestamp_utc": utc_now_iso(),
    }

    if args.report_json:
        report_path = Path(args.report_json)
        ensure_parent_dir(report_path)
        with report_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def resolve_output_dir(args: argparse.Namespace, run_id: str) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    return Path(DEFAULT_RUNS_ROOT) / run_id


def mode_generate(args: argparse.Namespace) -> int:
    input_path = Path(args.input_jsonl)
    run_id = args.run_id.strip() if args.run_id else utc_run_id("self-edit")
    seed = int(args.seed)
    max_sources = max(0, int(args.max_sources))
    candidates_per_source = max(1, int(args.candidates_per_source))

    out_dir = resolve_output_dir(args, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    export_accepted = Path(args.export_accepted or DEFAULT_EXPORT_ACCEPTED)
    export_accepted.parent.mkdir(parents=True, exist_ok=True)

    # Load and validate sources
    sources: List[SourceSample] = []
    for line_no, obj in read_jsonl(input_path):
        sources.append(validate_source_obj(line_no, obj))
        if max_sources and len(sources) >= max_sources:
            break

    # Deterministic order (by line_no already, keep stable)
    # Snapshot
    sources_snapshot_path = out_dir / "sources.snapshot.jsonl"
    write_jsonl(sources_snapshot_path, (s.to_dict() for s in sources))

    # Generate candidates
    candidates: List[EditCandidate] = []
    for src in sources:
        for ci in range(candidates_per_source):
            candidates.append(generate_candidate(run_id, src, ci, seed))
    candidates_path = out_dir / "candidates.jsonl"
    write_jsonl(candidates_path, (c.to_dict() for c in candidates))

    # Verify candidates
    verifications: List[VerificationRecord] = [
        verify_candidate(c, seed) for c in candidates
    ]
    verifications_path = out_dir / "verifications.jsonl"
    write_jsonl(verifications_path, (v.to_dict() for v in verifications))

    # Accepted derived
    source_by_id = {s.source_sample_id: s for s in sources}
    verification_by_candidate = {v.candidate_id: v for v in verifications}
    accepted_derived: List[DerivedTrainingSample] = []
    for c in candidates:
        v = verification_by_candidate[c.candidate_id]
        if v.decision != "accept":
            continue
        src = source_by_id[c.source_sample_id]
        accepted_derived.append(
            DerivedTrainingSample(
                instruction=src.instruction,
                input=src.input,
                output=c.proposed_output,
                provenance={
                    "run_id": run_id,
                    "source_sample_id": src.source_sample_id,
                    "candidate_id": c.candidate_id,
                    "verification_id": v.verification_id,
                    "strategy": c.strategy,
                    "verdict": v.decision,
                },
            )
        )

    accepted_path = out_dir / "accepted.derived.jsonl"
    write_jsonl(accepted_path, (a.to_dict() for a in accepted_derived))
    write_jsonl(export_accepted, (a.to_dict() for a in accepted_derived))

    decision_counts = {"accept": 0, "reject": 0, "needs_review": 0}
    for v in verifications:
        decision_counts[v.decision] = decision_counts.get(v.decision, 0) + 1

    manifest = {
        "run_id": run_id,
        "mode": "generate",
        "created_at_utc": utc_now_iso(),
        "seed": seed,
        "input_jsonl": str(input_path),
        "output_dir": str(out_dir),
        "export_accepted": str(export_accepted),
        "params": {
            "max_sources": max_sources,
            "candidates_per_source": candidates_per_source,
        },
        "artifacts": {
            "sources_snapshot_jsonl": "sources.snapshot.jsonl",
            "candidates_jsonl": "candidates.jsonl",
            "verifications_jsonl": "verifications.jsonl",
            "accepted_derived_jsonl": "accepted.derived.jsonl",
            "manifest_json": "manifest.json",
        },
        "counts": {
            "sources": len(sources),
            "candidates": len(candidates),
            "verifications": len(verifications),
            "accepted_derived": len(accepted_derived),
            "decision_counts": decision_counts,
        },
        "pipeline_version": "seal-mvp-deterministic-v1",
    }

    manifest_path = out_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def _validate_jsonl_required_fields(path: Path, required: List[str]) -> int:
    count = 0
    for line_no, obj in read_jsonl(path):
        count += 1
        missing = [k for k in required if k not in obj]
        if missing:
            raise ValueError(f"{path}:{line_no} missing required fields: {missing}")
    return count


def mode_validate(args: argparse.Namespace) -> int:
    run_dir = Path(args.output_dir) if args.output_dir else None
    if run_dir is None:
        raise ValueError("--output-dir is required in validate mode (run directory)")

    required_files = [
        "sources.snapshot.jsonl",
        "candidates.jsonl",
        "verifications.jsonl",
        "accepted.derived.jsonl",
        "manifest.json",
    ]
    for fn in required_files:
        p = run_dir / fn
        if not p.exists():
            raise FileNotFoundError(f"Missing run artifact: {p}")

    # Validate JSONL files
    n_sources = _validate_jsonl_required_fields(
        run_dir / "sources.snapshot.jsonl",
        [
            "source_sample_id",
            "line_no",
            "instruction",
            "input",
            "output",
            "source_hash",
        ],
    )
    n_candidates = _validate_jsonl_required_fields(
        run_dir / "candidates.jsonl",
        [
            "candidate_id",
            "run_id",
            "source_sample_id",
            "candidate_index",
            "strategy",
            "rationale",
            "original_output",
            "proposed_output",
            "audit",
        ],
    )
    n_verifications = _validate_jsonl_required_fields(
        run_dir / "verifications.jsonl",
        [
            "verification_id",
            "run_id",
            "candidate_id",
            "source_sample_id",
            "decision",
            "checks",
            "reasons",
            "audit",
        ],
    )
    n_accepted = _validate_jsonl_required_fields(
        run_dir / "accepted.derived.jsonl",
        ["instruction", "input", "output", "provenance"],
    )

    # Validate manifest
    manifest_path = run_dir / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    for k in ["run_id", "mode", "created_at_utc", "seed", "artifacts", "counts"]:
        if k not in manifest:
            raise ValueError(f"{manifest_path} missing key: {k}")

    # Optional export validation
    export_path = Path(args.export_accepted or DEFAULT_EXPORT_ACCEPTED)
    export_exists = export_path.exists()
    export_count = 0
    if export_exists:
        export_count = _validate_jsonl_required_fields(
            export_path, ["instruction", "input", "output", "provenance"]
        )

    report = {
        "mode": "validate",
        "run_dir": str(run_dir),
        "validated_at_utc": utc_now_iso(),
        "files_ok": True,
        "counts": {
            "sources_snapshot": n_sources,
            "candidates": n_candidates,
            "verifications": n_verifications,
            "accepted_derived": n_accepted,
            "export_accepted_exists": export_exists,
            "export_accepted_count": export_count,
        },
        "result": "ok",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


# -----------------------------
# CLI
# -----------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Deterministic SEAL-MVP self-edit orchestrator."
    )
    p.add_argument(
        "--mode",
        choices=["placeholder", "generate", "validate"],
        default="placeholder",
        help="placeholder|generate|validate",
    )
    p.add_argument(
        "--input-jsonl",
        required=True,
        help="Input dataset JSONL with instruction/input/output.",
    )
    p.add_argument(
        "--run-id",
        default="",
        help="Optional run identifier. If omitted, timestamp-based run_id is used.",
    )
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--max-samples", type=int, default=0, help="placeholder mode limit")
    p.add_argument("--max-sources", type=int, default=DEFAULT_MAX_SOURCES)
    p.add_argument(
        "--candidates-per-source", type=int, default=DEFAULT_CANDIDATES_PER_SOURCE
    )

    # legacy / placeholder outputs
    p.add_argument(
        "--output-jsonl",
        default="",
        help="Placeholder mode output JSONL (legacy-compatible).",
    )
    p.add_argument(
        "--report-json",
        default="",
        help="Optional report path (placeholder mode).",
    )

    # generate / validate
    p.add_argument(
        "--output-dir",
        default="",
        help="Generate/validate run directory. In generate mode default: data/self_edits/runs/<run_id>.",
    )
    p.add_argument(
        "--export-accepted",
        default=DEFAULT_EXPORT_ACCEPTED,
        help="Export path for accepted derived samples JSONL.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.mode == "placeholder":
            rc = mode_placeholder(args)
        elif args.mode == "generate":
            rc = mode_generate(args)
        elif args.mode == "validate":
            rc = mode_validate(args)
        else:
            raise ValueError(f"Unsupported mode: {args.mode}")
        sys.exit(rc)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
