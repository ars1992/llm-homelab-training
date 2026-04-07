#!/usr/bin/env python3
"""
eval_val.py

Minimal regression evaluator for val.jsonl records with `expected_contains` checks.

Expected JSONL schema per line:
{
  "id": "val-001",
  "instruction": "...",
  "input": "",
  "expected_contains": ["..."],
  "tags": ["regression"]
}
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    from peft import PeftModel
except Exception:
    PeftModel = None  # Optional at runtime


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id(prefix: str = "eval-val") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def load_yaml(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be an object.")
    return data


def cfg_get(cfg: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = cfg
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def build_prompt(instruction: str, input_text: str) -> str:
    instruction = instruction.strip()
    input_text = (input_text or "").strip()
    if input_text:
        return (
            "### Instruction:\n"
            f"{instruction}\n\n"
            "### Input:\n"
            f"{input_text}\n\n"
            "### Response:\n"
        )
    return f"### Instruction:\n{instruction}\n\n### Response:\n"


def normalize_text(
    s: str, trim_whitespace: bool = True, case_sensitive: bool = False
) -> str:
    out = s
    if trim_whitespace:
        out = " ".join(out.split())
    if not case_sensitive:
        out = out.lower()
    return out


def load_val_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    rows: List[Dict[str, Any]] = []
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
                raise ValueError(f"Row at {path}:{line_no} is not a JSON object")
            required = ["id", "instruction", "input", "expected_contains", "tags"]
            missing = [k for k in required if k not in obj]
            if missing:
                raise ValueError(f"{path}:{line_no} missing required fields: {missing}")
            if not isinstance(obj["id"], str) or not obj["id"].strip():
                raise ValueError(f"{path}:{line_no} invalid id")
            if (
                not isinstance(obj["instruction"], str)
                or not obj["instruction"].strip()
            ):
                raise ValueError(f"{path}:{line_no} invalid instruction")
            if not isinstance(obj["input"], str):
                raise ValueError(f"{path}:{line_no} input must be string")
            if (
                not isinstance(obj["expected_contains"], list)
                or len(obj["expected_contains"]) == 0
            ):
                raise ValueError(
                    f"{path}:{line_no} expected_contains must be non-empty list"
                )
            for token in obj["expected_contains"]:
                if not isinstance(token, str) or not token.strip():
                    raise ValueError(
                        f"{path}:{line_no} expected_contains has invalid token"
                    )
            if not isinstance(obj["tags"], list):
                raise ValueError(f"{path}:{line_no} tags must be list")
            rows.append(obj)
    if not rows:
        raise ValueError(f"No rows loaded from {path}")
    return rows


def load_model_and_tokenizer(
    base_model: str,
    adapter_path: Optional[str],
    device: str = "auto",
) -> Tuple[Any, Any, str]:
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = torch.float16 if torch.cuda.is_available() else None
    device_map = "auto" if device == "auto" else None

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch_dtype,
        device_map=device_map,
    )

    if adapter_path:
        if PeftModel is None:
            raise RuntimeError(
                "PEFT adapter requested but peft is not importable in this environment."
            )
        adapter_dir = Path(adapter_path).resolve()
        if not adapter_dir.exists():
            raise FileNotFoundError(f"Adapter path not found: {adapter_dir}")
        model = PeftModel.from_pretrained(model, str(adapter_dir))

    model.eval()
    runtime_device = str(getattr(model, "device", "cpu"))
    return model, tokenizer, runtime_device


@torch.no_grad()
def generate_one(
    model: Any,
    tokenizer: Any,
    instruction: str,
    input_text: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
) -> str:
    prompt = build_prompt(instruction, input_text)
    inputs = tokenizer(prompt, return_tensors="pt")
    if hasattr(model, "device"):
        dev = model.device
        inputs = {k: v.to(dev) for k, v in inputs.items()}

    gen_kwargs: Dict[str, Any] = {
        "max_new_tokens": int(max_new_tokens),
        "do_sample": bool(do_sample),
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
    }
    if do_sample:
        gen_kwargs["temperature"] = float(max(temperature, 1e-6))
        gen_kwargs["top_p"] = float(top_p)

    outputs = model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs.get("attention_mask"),
        **gen_kwargs,
    )
    prompt_len = int(inputs["input_ids"].shape[1])
    completion_ids = outputs[0][prompt_len:]
    return tokenizer.decode(completion_ids, skip_special_tokens=True).strip()


def evaluate_contains(
    prediction: str,
    expected_contains: List[str],
    case_sensitive: bool,
    trim_whitespace: bool,
) -> Tuple[bool, List[str]]:
    pred_norm = normalize_text(
        prediction,
        trim_whitespace=trim_whitespace,
        case_sensitive=case_sensitive,
    )
    missing: List[str] = []
    for needle in expected_contains:
        needle_norm = normalize_text(
            needle,
            trim_whitespace=trim_whitespace,
            case_sensitive=case_sensitive,
        )
        if needle_norm not in pred_norm:
            missing.append(needle)
    return len(missing) == 0, missing


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate val.jsonl with expected_contains regression checks."
    )
    p.add_argument("--config", type=str, default="configs/datasets/val_regression.yaml")
    p.add_argument("--dataset", type=str, default=None, help="Override dataset path")
    p.add_argument("--base-model", type=str, default="facebook/opt-2.7b")
    p.add_argument("--adapter-path", type=str, default=None)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--output-dir", type=str, default=None)
    p.add_argument("--device", type=str, default="auto", help="auto|cpu|cuda")
    p.add_argument("--max-samples", type=int, default=0, help="0 = all")
    p.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Reserved for compatibility; currently evaluated sample-wise.",
    )
    p.add_argument("--max-new-tokens", type=int, default=None)
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--top-p", type=float, default=None)
    p.add_argument("--do-sample", action="store_true")
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--no-trim-whitespace", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)

    dataset_path = args.dataset or cfg_get(
        cfg, "dataset", "path", default="data/datasets/val.jsonl"
    )
    run_id = args.run_id or utc_run_id("eval-val")
    output_root = args.output_dir or cfg_get(
        cfg, "outputs", "root_dir", default="data/evals"
    )
    output_dir = Path(output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    max_new_tokens = (
        args.max_new_tokens
        if args.max_new_tokens is not None
        else int(cfg_get(cfg, "evaluation", "max_new_tokens", default=96))
    )
    temperature = (
        args.temperature
        if args.temperature is not None
        else float(cfg_get(cfg, "evaluation", "temperature", default=0.0))
    )
    top_p = (
        args.top_p
        if args.top_p is not None
        else float(cfg_get(cfg, "evaluation", "top_p", default=1.0))
    )
    do_sample = bool(
        args.do_sample or cfg_get(cfg, "evaluation", "do_sample", default=False)
    )
    case_sensitive = bool(
        args.case_sensitive
        or cfg_get(cfg, "evaluation", "case_sensitive", default=False)
    )
    trim_whitespace = not bool(args.no_trim_whitespace) and bool(
        cfg_get(cfg, "evaluation", "trim_whitespace", default=True)
    )

    rows = load_val_jsonl(Path(dataset_path))
    if args.max_samples and args.max_samples > 0:
        rows = rows[: args.max_samples]

    model, tokenizer, runtime_device = load_model_and_tokenizer(
        base_model=args.base_model,
        adapter_path=args.adapter_path,
        device=args.device,
    )

    results: List[Dict[str, Any]] = []
    pass_count = 0

    for idx, row in enumerate(rows, start=1):
        pred = generate_one(
            model=model,
            tokenizer=tokenizer,
            instruction=row["instruction"],
            input_text=row["input"],
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
        )
        passed, missing = evaluate_contains(
            prediction=pred,
            expected_contains=row["expected_contains"],
            case_sensitive=case_sensitive,
            trim_whitespace=trim_whitespace,
        )
        if passed:
            pass_count += 1

        results.append(
            {
                "id": row["id"],
                "instruction": row["instruction"],
                "input": row["input"],
                "tags": row.get("tags", []),
                "expected_contains": row["expected_contains"],
                "prediction": pred,
                "pass": passed,
                "missing": missing,
            }
        )
        print(f"[eval-val] {idx}/{len(rows)} id={row['id']} pass={passed}")

    total = len(results)
    pass_rate = (pass_count / total) if total else 0.0

    report = {
        "run": {
            "run_id": run_id,
            "timestamp_utc": utc_now(),
            "dataset_path": str(Path(dataset_path).resolve()),
            "base_model": args.base_model,
            "adapter_path": str(Path(args.adapter_path).resolve())
            if args.adapter_path
            else None,
            "runtime_device": runtime_device,
        },
        "config_effective": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "do_sample": do_sample,
            "case_sensitive": case_sensitive,
            "trim_whitespace": trim_whitespace,
            "batch_size": args.batch_size,
        },
        "summary": {
            "total": total,
            "passed": pass_count,
            "failed": total - pass_count,
            "pass_rate": pass_rate,
        },
        "results": results,
    }

    report_name = cfg_get(cfg, "outputs", "report_filename", default="val_report.json")
    report_path = output_dir / str(report_name)
    preds_path = output_dir / "val_predictions.jsonl"

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with preds_path.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[eval-val] wrote report: {report_path}")
    print(f"[eval-val] wrote predictions: {preds_path}")
    print(f"[eval-val] pass_rate={pass_rate:.4f} ({pass_count}/{total})")


if __name__ == "__main__":
    main()
