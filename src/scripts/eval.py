#!/usr/bin/env python3
"""
eval.py

Scaffold for local evaluation of LoRA runs.

Supported dataset format (JSONL, one object per line):
{"instruction": "...", "input": "...", "output": "..."}

Usage examples:
  python src/scripts/eval.py \
    --config configs/eval.yaml \
    --dataset data/datasets/val.jsonl \
    --base-model facebook/opt-2.7b \
    --adapter-path data/models/run-123 \
    --output-dir data/evals/run-123

  python src/scripts/eval.py \
    --dataset data/datasets/val.jsonl \
    --base-model facebook/opt-2.7b \
    --max-samples 100
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


# ----------------------------
# Data structures
# ----------------------------

@dataclass
class EvalExample:
    instruction: str
    input: str
    output: str
    sample_id: str


@dataclass
class EvalResultRow:
    sample_id: str
    instruction: str
    input: str
    reference: str
    prediction: str
    exact_match: float
    token_f1: float
    prediction_chars: int
    reference_chars: int


# ----------------------------
# Utility functions
# ----------------------------

def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping/object.")
    return data


def merge_config(cli: argparse.Namespace, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    CLI overrides config.
    """
    out = dict(cfg)

    cli_map = {
        "dataset": cli.dataset,
        "base_model": cli.base_model,
        "adapter_path": cli.adapter_path,
        "output_dir": cli.output_dir,
        "max_samples": cli.max_samples,
        "batch_size": cli.batch_size,
        "max_new_tokens": cli.max_new_tokens,
        "temperature": cli.temperature,
        "top_p": cli.top_p,
        "do_sample": cli.do_sample,
        "device": cli.device,
        "seed": cli.seed,
    }

    for k, v in cli_map.items():
        if v is not None:
            out[k] = v

    # defaults
    out.setdefault("output_dir", "data/evals/default-run")
    out.setdefault("batch_size", 1)
    out.setdefault("max_new_tokens", 256)
    out.setdefault("temperature", 0.0)
    out.setdefault("top_p", 1.0)
    out.setdefault("do_sample", False)
    out.setdefault("device", "auto")
    out.setdefault("seed", 42)
    out.setdefault("max_samples", 0)
    return out


def set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def simple_tokenize(s: str) -> List[str]:
    # deterministic lightweight tokenizer for simple metric baseline
    s = normalize_text(s)
    if not s:
        return []
    return re.findall(r"\w+|[^\w\s]", s, flags=re.UNICODE)


def token_f1(pred: str, ref: str) -> float:
    pred_toks = simple_tokenize(pred)
    ref_toks = simple_tokenize(ref)
    if not pred_toks and not ref_toks:
        return 1.0
    if not pred_toks or not ref_toks:
        return 0.0

    ref_counts: Dict[str, int] = {}
    for t in ref_toks:
        ref_counts[t] = ref_counts.get(t, 0) + 1

    overlap = 0
    for t in pred_toks:
        c = ref_counts.get(t, 0)
        if c > 0:
            overlap += 1
            ref_counts[t] = c - 1

    precision = overlap / max(len(pred_toks), 1)
    recall = overlap / max(len(ref_toks), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def exact_match(pred: str, ref: str) -> float:
    return 1.0 if normalize_text(pred) == normalize_text(ref) else 0.0


def build_prompt(instruction: str, user_input: str) -> str:
    """
    Keep this aligned with training prompt conventions.
    """
    instruction = instruction.strip()
    user_input = user_input.strip()

    if user_input:
        return (
            "### Instruction:\n"
            f"{instruction}\n\n"
            "### Input:\n"
            f"{user_input}\n\n"
            "### Response:\n"
        )
    return (
        "### Instruction:\n"
        f"{instruction}\n\n"
        "### Response:\n"
    )


def read_jsonl_dataset(path: str, max_samples: int = 0) -> List[EvalExample]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    examples: List[EvalExample] = []
    with p.open("r", encoding="utf-8") as f:
        for line_idx, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_idx}: {exc}") from exc

            if not isinstance(obj, dict):
                raise ValueError(f"Line {line_idx} must be a JSON object.")

            instruction = obj.get("instruction", "")
            output = obj.get("output", "")
            user_input = obj.get("input", "")

            if not isinstance(instruction, str) or not instruction.strip():
                raise ValueError(f"Line {line_idx}: 'instruction' must be non-empty string.")
            if not isinstance(output, str) or not output.strip():
                raise ValueError(f"Line {line_idx}: 'output' must be non-empty string.")
            if not isinstance(user_input, str):
                raise ValueError(f"Line {line_idx}: 'input' must be string when present.")

            sample_id = obj.get("id")
            if not isinstance(sample_id, str) or not sample_id.strip():
                sample_id = f"line-{line_idx}"

            examples.append(
                EvalExample(
                    instruction=instruction.strip(),
                    input=user_input.strip(),
                    output=output.strip(),
                    sample_id=sample_id,
                )
            )

            if max_samples > 0 and len(examples) >= max_samples:
                break

    if not examples:
        raise ValueError("Dataset is empty after parsing.")
    return examples


def resolve_torch_dtype(device: str) -> Optional[torch.dtype]:
    # On K80, bf16 is typically not available.
    if device.startswith("cuda") or (device == "auto" and torch.cuda.is_available()):
        return torch.float16
    return None


def load_model_and_tokenizer(
    base_model: str,
    adapter_path: Optional[str],
    device: str = "auto",
) -> Tuple[Any, Any, str]:
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = resolve_torch_dtype(device)
    device_map = "auto" if device == "auto" else None

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch_dtype,
        device_map=device_map,
    )

    if adapter_path:
        adapter_path_resolved = str(Path(adapter_path).resolve())
        if not Path(adapter_path_resolved).exists():
            raise FileNotFoundError(f"Adapter path not found: {adapter_path_resolved}")
        model = PeftModel.from_pretrained(model, adapter_path_resolved)

    model.eval()

    runtime_device = "cpu"
    if hasattr(model, "device"):
        runtime_device = str(model.device)

    return model, tokenizer, runtime_device


def chunked(items: List[EvalExample], n: int) -> Iterable[List[EvalExample]]:
    n = max(1, n)
    for i in range(0, len(items), n):
        yield items[i:i + n]


@torch.no_grad()
def predict_batch(
    model: Any,
    tokenizer: Any,
    batch: List[EvalExample],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
) -> List[str]:
    prompts = [build_prompt(x.instruction, x.input) for x in batch]
    inputs = tokenizer(
        prompts,
        return_tensors="pt",
        padding=True,
        truncation=True,
    )

    # move tensors to model device (works for single-device case)
    if hasattr(model, "device"):
        dev = model.device
        inputs = {k: v.to(dev) for k, v in inputs.items()}

    gen_kwargs = dict(
        max_new_tokens=max_new_tokens,
        do_sample=do_sample,
        temperature=max(temperature, 1e-6) if do_sample else None,
        top_p=top_p if do_sample else None,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
    )
    # remove None values
    gen_kwargs = {k: v for k, v in gen_kwargs.items() if v is not None}

    outputs = model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        **gen_kwargs,
    )

    decoded: List[str] = []
    input_lens = (inputs["attention_mask"].sum(dim=1)).tolist()

    for i in range(len(batch)):
        full = outputs[i]
        prompt_len = int(input_lens[i])
        completion_ids = full[prompt_len:]
        text = tokenizer.decode(completion_ids, skip_special_tokens=True).strip()
        decoded.append(text)

    return decoded


def evaluate(
    model: Any,
    tokenizer: Any,
    examples: List[EvalExample],
    batch_size: int,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
) -> Tuple[List[EvalResultRow], Dict[str, Any]]:
    rows: List[EvalResultRow] = []
    total = len(examples)

    for idx, batch in enumerate(chunked(examples, batch_size), start=1):
        preds = predict_batch(
            model=model,
            tokenizer=tokenizer,
            batch=batch,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
        )

        for ex, pred in zip(batch, preds):
            em = exact_match(pred, ex.output)
            f1 = token_f1(pred, ex.output)
            rows.append(
                EvalResultRow(
                    sample_id=ex.sample_id,
                    instruction=ex.instruction,
                    input=ex.input,
                    reference=ex.output,
                    prediction=pred,
                    exact_match=em,
                    token_f1=f1,
                    prediction_chars=len(pred),
                    reference_chars=len(ex.output),
                )
            )

        print(f"[eval] processed batch {idx}, samples {min(idx * batch_size, total)}/{total}")

    exact_matches = [r.exact_match for r in rows]
    token_f1s = [r.token_f1 for r in rows]
    pred_lengths = [r.prediction_chars for r in rows]
    ref_lengths = [r.reference_chars for r in rows]

    summary = {
        "samples": len(rows),
        "metrics": {
            "exact_match_mean": float(statistics.mean(exact_matches)) if rows else 0.0,
            "token_f1_mean": float(statistics.mean(token_f1s)) if rows else 0.0,
            "prediction_chars_mean": float(statistics.mean(pred_lengths)) if rows else 0.0,
            "reference_chars_mean": float(statistics.mean(ref_lengths)) if rows else 0.0,
        },
        "distribution": {
            "exact_match_sum": float(sum(exact_matches)),
            "token_f1_min": float(min(token_f1s)) if rows else 0.0,
            "token_f1_max": float(max(token_f1s)) if rows else 0.0,
            "token_f1_std": float(statistics.pstdev(token_f1s)) if len(token_f1s) > 1 else 0.0,
        },
    }
    return rows, summary


def save_outputs(output_dir: str, rows: List[EvalResultRow], report: Dict[str, Any]) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pred_path = out / "predictions.jsonl"
    summary_path = out / "summary.json"

    with pred_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[eval] wrote predictions: {pred_path}")
    print(f"[eval] wrote summary:     {summary_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate local base/LoRA model on JSONL dataset.")
    p.add_argument("--config", type=str, default=None, help="Path to YAML config.")
    p.add_argument("--dataset", type=str, default=None, help="Path to JSONL eval dataset.")
    p.add_argument("--base-model", type=str, default=None, help="HF model id/path.")
    p.add_argument("--adapter-path", type=str, default=None, help="LoRA adapter directory.")
    p.add_argument("--output-dir", type=str, default=None, help="Output dir for eval artifacts.")
    p.add_argument("--max-samples", type=int, default=None, help="Max number of samples (0 = all).")
    p.add_argument("--batch-size", type=int, default=None, help="Eval batch size.")
    p.add_argument("--max-new-tokens", type=int, default=None, help="Generation max_new_tokens.")
    p.add_argument("--temperature", type=float, default=None, help="Sampling temperature.")
    p.add_argument("--top-p", type=float, default=None, help="Sampling top-p.")
    p.add_argument("--do-sample", action="store_true", help="Enable sampling generation.")
    p.add_argument("--device", type=str, default=None, help="Device override: auto/cpu/cuda.")
    p.add_argument("--seed", type=int, default=None, help="Random seed.")
    return p.parse_args()


def validate_required(cfg: Dict[str, Any]) -> None:
    required = ["dataset", "base_model", "output_dir"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Missing required settings: {', '.join(missing)}")


def main() -> None:
    args = parse_args()
    file_cfg = load_yaml(args.config)
    cfg = merge_config(args, file_cfg)
    validate_required(cfg)

    dataset_path = str(cfg["dataset"])
    base_model = str(cfg["base_model"])
    adapter_path = str(cfg["adapter_path"]) if cfg.get("adapter_path") else None
    output_dir = str(cfg["output_dir"])
    max_samples = int(cfg.get("max_samples", 0))
    batch_size = int(cfg.get("batch_size", 1))
    max_new_tokens = int(cfg.get("max_new_tokens", 256))
    temperature = float(cfg.get("temperature", 0.0))
    top_p = float(cfg.get("top_p", 1.0))
    do_sample = bool(cfg.get("do_sample", False))
    device = str(cfg.get("device", "auto"))
    seed = int(cfg.get("seed", 42))

    set_seed(seed)

    print("[eval] loading dataset...")
    examples = read_jsonl_dataset(dataset_path, max_samples=max_samples)
    print(f"[eval] dataset samples: {len(examples)}")

    print("[eval] loading model/tokenizer...")
    model, tokenizer, runtime_device = load_model_and_tokenizer(
        base_model=base_model,
        adapter_path=adapter_path,
        device=device,
    )
    print(f"[eval] runtime device: {runtime_device}")

    print("[eval] running evaluation...")
    rows, summary = evaluate(
        model=model,
        tokenizer=tokenizer,
        examples=examples,
        batch_size=batch_size,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        do_sample=do_sample,
    )

    report = {
        "run": {
            "timestamp_utc": utc_now_rfc3339(),
            "dataset": str(Path(dataset_path).resolve()),
            "base_model": base_model,
            "adapter_path": str(Path(adapter_path).resolve()) if adapter_path else None,
            "output_dir": str(Path(output_dir).resolve()),
            "device": runtime_device,
            "seed": seed,
        },
        "config_effective": {
            "max_samples": max_samples,
            "batch_size": batch_size,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "do_sample": do_sample,
        },
        "summary": summary,
    }

    save_outputs(output_dir=output_dir, rows=rows, report=report)

    print("[eval] done.")
    print(json.dumps(report["summary"]["metrics"], indent=2))


if __name__ == "__main__":
    main()
