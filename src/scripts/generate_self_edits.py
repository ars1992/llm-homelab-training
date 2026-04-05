#!/usr/bin/env python3
"""
generate_self_edits.py

MVP/Placeholder für eine zukünftige SEAL-inspirierte Self-Edit-Pipeline.

Zweck:
- Liest ein JSONL-Dataset mit Feldern:
  { "instruction": str, "input": str, "output": str, ... }
- Erzeugt ein "self-edit candidates" JSONL als strukturiertes Placeholder-Format
- Schreibt optional einen kleinen Report (JSON) für Audit/Debug

Wichtig:
- Diese Version führt KEINE modellbasierte Selbstkorrektur durch.
- Sie erzeugt deterministische Platzhalter, damit Datenpfade und Pipeline-Schritte
  früh stabilisiert werden können.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import uuid
from typing import Dict, Iterable, Iterator, List, Tuple


@dataclasses.dataclass
class EditCandidate:
    candidate_id: str
    source_example_id: str
    strategy: str
    rationale: str
    original_output: str
    proposed_output: str
    confidence: float
    metadata: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_example_id": self.source_example_id,
            "strategy": self.strategy,
            "rationale": self.rationale,
            "original_output": self.original_output,
            "proposed_output": self.proposed_output,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate placeholder self-edit candidates from instruction dataset JSONL."
    )
    parser.add_argument(
        "--input-jsonl",
        required=True,
        help="Pfad zur Eingabe-JSONL mit Feldern instruction/input/output.",
    )
    parser.add_argument(
        "--output-jsonl",
        required=True,
        help="Pfad zur Ausgabe-JSONL für Self-Edit-Kandidaten.",
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="Optionaler Pfad für JSON-Report.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optionaler Run-Identifier. Wenn leer, wird ein UUID-basierter run_id erzeugt.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Optionales Limit an Samples (0 = alle).",
    )
    return parser.parse_args()


def ensure_parent_dir(file_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(file_path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def read_jsonl(path: str) -> Iterator[Tuple[int, Dict[str, object]]]:
    with open(path, "r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ungültiges JSON in {path}:{line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"Eintrag in {path}:{line_no} ist kein JSON-Objekt.")
            yield line_no, obj


def validate_example(example: Dict[str, object], line_no: int) -> Dict[str, str]:
    required = ["instruction", "output"]
    for key in required:
        if key not in example:
            raise ValueError(f"Pflichtfeld '{key}' fehlt in Zeile {line_no}.")
        if not isinstance(example[key], str):
            raise ValueError(f"Feld '{key}' muss string sein (Zeile {line_no}).")

    instruction = example.get("instruction", "")
    user_input = example.get("input", "")
    output = example.get("output", "")

    if not isinstance(user_input, str):
        raise ValueError(f"Feld 'input' muss string sein, wenn vorhanden (Zeile {line_no}).")

    return {
        "instruction": instruction,
        "input": user_input,
        "output": output,
    }


def build_source_example_id(line_no: int, example: Dict[str, object]) -> str:
    if "id" in example and isinstance(example["id"], str) and example["id"].strip():
        return example["id"].strip()
    return f"line-{line_no}"


def generate_placeholder_candidate(
    source_example_id: str,
    validated: Dict[str, str],
    run_id: str,
) -> EditCandidate:
    """
    Placeholder-Strategie:
    - proposed_output = original_output (identisch)
    - rationale erklärt, dass dies nur ein Pipeline-Stub ist
    - confidence niedrig gesetzt
    """
    candidate_id = f"{run_id}-{uuid.uuid4().hex[:12]}"
    original_output = validated["output"]

    return EditCandidate(
        candidate_id=candidate_id,
        source_example_id=source_example_id,
        strategy="noop_identity_placeholder",
        rationale=(
            "Placeholder candidate for future SEAL loop; no semantic edit applied in MVP."
        ),
        original_output=original_output,
        proposed_output=original_output,
        confidence=0.10,
        metadata={
            "generator": "generate_self_edits.py",
            "mode": "placeholder",
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


def write_jsonl(path: str, rows: Iterable[Dict[str, object]]) -> int:
    ensure_parent_dir(path)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or f"self-edit-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    max_samples = int(args.max_samples)

    generated: List[Dict[str, object]] = []
    processed = 0

    for line_no, raw_example in read_jsonl(args.input_jsonl):
        if max_samples > 0 and processed >= max_samples:
            break

        validated = validate_example(raw_example, line_no)
        source_example_id = build_source_example_id(line_no, raw_example)
        candidate = generate_placeholder_candidate(source_example_id, validated, run_id)

        generated.append(
            {
                "run_id": run_id,
                "source": {
                    "example_id": source_example_id,
                    "instruction": validated["instruction"],
                    "input": validated["input"],
                },
                "candidate": candidate.to_dict(),
                "status": "generated_placeholder",
            }
        )
        processed += 1

    written = write_jsonl(args.output_jsonl, generated)

    report = {
        "run_id": run_id,
        "input_jsonl": os.path.abspath(args.input_jsonl),
        "output_jsonl": os.path.abspath(args.output_jsonl),
        "processed_examples": processed,
        "written_candidates": written,
        "generator_version": "mvp-placeholder-v1",
        "notes": [
            "No model inference performed.",
            "All proposed_output values equal original_output.",
            "Replace strategy with verifier/editor loop in future SEAL implementation.",
        ],
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    if args.report_json.strip():
        ensure_parent_dir(args.report_json)
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
