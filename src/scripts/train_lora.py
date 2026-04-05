#!/usr/bin/env python3
"""
MVP LoRA training script for instruction datasets in JSONL format.

Expected dataset format (one JSON object per line):
{"instruction": "...", "input": "...", "output": "..."}

- `instruction`: required, non-empty string
- `output`: required, non-empty string
- `input`: optional string (defaults to "")
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import yaml
from datasets import Dataset, load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
    set_seed,
)


# -----------------------------
# Config / defaults
# -----------------------------

DEFAULTS: Dict[str, Any] = {
    "model_name": "facebook/opt-2.7b",
    "dataset_path": "data/datasets/train.jsonl",
    "eval_dataset_path": None,
    "output_root": "data/models",
    "logs_root": "data/logs",
    "run_id": None,
    "run_id_prefix": "lora",
    "seed": 42,
    "max_seq_length": 512,
    "num_train_epochs": 1,
    "learning_rate": 2e-4,
    "weight_decay": 0.0,
    "warmup_ratio": 0.03,
    "lr_scheduler_type": "cosine",
    "train_batch_size": 1,
    "eval_batch_size": 1,
    "gradient_accumulation_steps": 16,
    "logging_steps": 10,
    "save_steps": 200,
    "save_total_limit": 2,
    "evaluation_strategy": "no",  # "no" | "steps" | "epoch"
    "eval_steps": 200,
    "gradient_checkpointing": True,
    "fp16": True,
    "bf16": False,  # K80 does not support bf16
    "max_steps": -1,
    "optim": "adamw_torch",
    "dataloader_num_workers": 0,
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "lora_bias": "none",
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "report_to": ["tensorboard"],
    "logging_first_step": True,
    "save_safetensors": True,
    "overwrite_output_dir": False,
}


@dataclass
class RunPaths:
    run_id: str
    model_dir: Path
    logs_dir: Path


# -----------------------------
# Utility functions
# -----------------------------

def utc_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        obj = yaml.safe_load(f) or {}
    if not isinstance(obj, dict):
        raise ValueError(f"Config must be a YAML object, got: {type(obj)}")
    return obj


def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        out[k] = v
    return out


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _set_if_present(dst: Dict[str, Any], src: Dict[str, Any], src_key: str, dst_key: str) -> None:
    if src_key in src and src[src_key] is not None:
        dst[dst_key] = src[src_key]


def apply_yaml_config(base_cfg: Dict[str, Any], file_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supports both:
    1) flat keys (legacy)
    2) nested keys from configs/train_lora_3b_k80.yaml
    """
    cfg = dict(base_cfg)

    # 1) Flat/legacy override
    cfg = merge_config(cfg, {k: v for k, v in file_cfg.items() if k in cfg})

    # 2) Nested override
    run = _as_dict(file_cfg.get("run"))
    paths = _as_dict(file_cfg.get("paths"))
    model = _as_dict(file_cfg.get("model"))
    data = _as_dict(file_cfg.get("data"))
    lora = _as_dict(file_cfg.get("lora"))
    training = _as_dict(file_cfg.get("training"))

    _set_if_present(cfg, run, "run_id", "run_id")
    _set_if_present(cfg, run, "run_id_prefix", "run_id_prefix")
    _set_if_present(cfg, run, "seed", "seed")

    _set_if_present(cfg, paths, "dataset_jsonl", "dataset_path")
    _set_if_present(cfg, paths, "eval_dataset_jsonl", "eval_dataset_path")
    _set_if_present(cfg, paths, "model_output_root", "output_root")
    _set_if_present(cfg, paths, "log_output_root", "logs_root")

    _set_if_present(cfg, model, "base_model_name", "model_name")

    _set_if_present(cfg, data, "max_seq_length", "max_seq_length")

    _set_if_present(cfg, lora, "r", "lora_r")
    _set_if_present(cfg, lora, "alpha", "lora_alpha")
    _set_if_present(cfg, lora, "dropout", "lora_dropout")
    _set_if_present(cfg, lora, "bias", "lora_bias")
    _set_if_present(cfg, lora, "target_modules", "target_modules")

    _set_if_present(cfg, training, "num_train_epochs", "num_train_epochs")
    _set_if_present(cfg, training, "max_steps", "max_steps")
    _set_if_present(cfg, training, "per_device_train_batch_size", "train_batch_size")
    _set_if_present(cfg, training, "per_device_eval_batch_size", "eval_batch_size")
    _set_if_present(cfg, training, "gradient_accumulation_steps", "gradient_accumulation_steps")
    _set_if_present(cfg, training, "learning_rate", "learning_rate")
    _set_if_present(cfg, training, "weight_decay", "weight_decay")
    _set_if_present(cfg, training, "warmup_ratio", "warmup_ratio")
    _set_if_present(cfg, training, "lr_scheduler_type", "lr_scheduler_type")
    _set_if_present(cfg, training, "logging_steps", "logging_steps")
    _set_if_present(cfg, training, "save_steps", "save_steps")
    _set_if_present(cfg, training, "save_total_limit", "save_total_limit")
    _set_if_present(cfg, training, "evaluation_strategy", "evaluation_strategy")
    _set_if_present(cfg, training, "eval_steps", "eval_steps")
    _set_if_present(cfg, training, "gradient_checkpointing", "gradient_checkpointing")
    _set_if_present(cfg, training, "optim", "optim")
    _set_if_present(cfg, training, "dataloader_num_workers", "dataloader_num_workers")
    _set_if_present(cfg, training, "fp16", "fp16")
    _set_if_present(cfg, training, "bf16", "bf16")
    _set_if_present(cfg, training, "report_to", "report_to")

    # Normalization
    if isinstance(cfg.get("target_modules"), list):
        cfg["target_modules"] = [m for m in cfg["target_modules"] if isinstance(m, str) and m.strip()]

    return cfg


def validate_effective_config(cfg: Dict[str, Any]) -> None:
    int_fields = [
        "seed",
        "max_seq_length",
        "train_batch_size",
        "eval_batch_size",
        "gradient_accumulation_steps",
        "logging_steps",
        "save_steps",
        "save_total_limit",
        "eval_steps",
        "max_steps",
        "dataloader_num_workers",
        "lora_r",
        "lora_alpha",
    ]
    float_fields = [
        "learning_rate",
        "weight_decay",
        "warmup_ratio",
        "lora_dropout",
        "num_train_epochs",
    ]

    for key in int_fields:
        if key in cfg and cfg[key] is not None:
            cfg[key] = int(cfg[key])

    for key in float_fields:
        if key in cfg and cfg[key] is not None:
            cfg[key] = float(cfg[key])

    for key in ("fp16", "bf16", "gradient_checkpointing", "logging_first_step", "save_safetensors"):
        if key in cfg:
            cfg[key] = bool(cfg[key])

    if cfg["max_seq_length"] <= 0:
        raise ValueError("max_seq_length must be > 0")
    if cfg["train_batch_size"] <= 0:
        raise ValueError("train_batch_size must be > 0")
    if cfg["eval_batch_size"] <= 0:
        raise ValueError("eval_batch_size must be > 0")
    if cfg["gradient_accumulation_steps"] <= 0:
        raise ValueError("gradient_accumulation_steps must be > 0")
    if not cfg.get("model_name"):
        raise ValueError("model_name must not be empty")
    if not cfg.get("dataset_path"):
        raise ValueError("dataset_path must not be empty")
    if not isinstance(cfg.get("target_modules"), list) or not cfg["target_modules"]:
        raise ValueError("target_modules must be a non-empty list")


def resolve_run_paths(cfg: Dict[str, Any]) -> RunPaths:
    run_prefix = str(cfg.get("run_id_prefix") or "lora")
    run_id = cfg.get("run_id") or utc_run_id(run_prefix)
    model_dir = Path(cfg["output_root"]) / run_id
    logs_dir = Path(cfg["logs_root"]) / run_id
    model_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(run_id=run_id, model_dir=model_dir, logs_dir=logs_dir)


def validate_dataset_line(obj: Dict[str, Any], line_no: int, src: str) -> None:
    if not isinstance(obj, dict):
        raise ValueError(f"{src}:{line_no} is not a JSON object")
    if "instruction" not in obj or not isinstance(obj["instruction"], str) or not obj["instruction"].strip():
        raise ValueError(f"{src}:{line_no} missing non-empty string field 'instruction'")
    if "output" not in obj or not isinstance(obj["output"], str) or not obj["output"].strip():
        raise ValueError(f"{src}:{line_no} missing non-empty string field 'output'")
    if "input" in obj and not isinstance(obj["input"], str):
        raise ValueError(f"{src}:{line_no} field 'input' must be a string when present")


def sanity_check_jsonl(path: Path, max_lines: int = 1000) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Dataset file does not exist: {path}")
    if path.suffix.lower() != ".jsonl":
        raise ValueError(f"Dataset must be .jsonl file, got: {path}")

    with path.open("r", encoding="utf-8") as f:
        seen = 0
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} invalid JSON ({exc})") from exc
            validate_dataset_line(obj, line_no=line_no, src=str(path))
            seen += 1
            if seen >= max_lines:
                break

    if seen == 0:
        raise ValueError(f"Dataset appears empty (no valid non-empty lines): {path}")


def format_sample(instruction: str, input_text: str, output: str) -> str:
    instruction = instruction.strip()
    input_text = (input_text or "").strip()
    output = output.strip()

    if input_text:
        prompt = (
            "### Instruction:\n"
            f"{instruction}\n\n"
            "### Input:\n"
            f"{input_text}\n\n"
            "### Response:\n"
            f"{output}"
        )
    else:
        prompt = (
            "### Instruction:\n"
            f"{instruction}\n\n"
            "### Response:\n"
            f"{output}"
        )
    return prompt


def tokenize_dataset(
    ds: Dataset,
    tokenizer: AutoTokenizer,
    max_seq_length: int,
) -> Dataset:
    def _map_fn(batch: Dict[str, List[Any]]) -> Dict[str, Any]:
        texts = []
        for instr, inp, out in zip(
            batch["instruction"],
            batch.get("input", [""] * len(batch["instruction"])),
            batch["output"],
        ):
            text = format_sample(instr, inp if inp is not None else "", out)
            texts.append(text)

        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )
        return tokenized

    keep_cols = [c for c in ds.column_names if c in ("instruction", "input", "output")]
    ds = ds.select_columns(keep_cols)
    ds_tok = ds.map(
        _map_fn,
        batched=True,
        remove_columns=keep_cols,
        desc="Tokenizing dataset",
    )
    return ds_tok


def choose_precision(cfg: Dict[str, Any]) -> Dict[str, bool]:
    # K80-compatible default: fp16=True, bf16=False.
    has_cuda = torch.cuda.is_available()
    fp16 = bool(cfg.get("fp16", False))
    bf16 = bool(cfg.get("bf16", False))

    if not has_cuda:
        # On CPU, mixed precision flags should be off.
        return {"fp16": False, "bf16": False}

    # If both true, prefer bf16 only if supported.
    if bf16 and not torch.cuda.is_bf16_supported():
        print("[WARN] bf16 requested but not supported on this GPU. Falling back to fp16.")
        bf16 = False
        fp16 = True

    if bf16 and fp16:
        # Avoid enabling both simultaneously.
        fp16 = False

    return {"fp16": fp16, "bf16": bf16}


def print_trainable_parameters(model: torch.nn.Module) -> None:
    trainable_params = 0
    all_params = 0
    for _, p in model.named_parameters():
        all_params += p.numel()
        if p.requires_grad:
            trainable_params += p.numel()
    ratio = (100 * trainable_params / all_params) if all_params > 0 else 0.0
    print(
        f"Trainable params: {trainable_params:,} | "
        f"All params: {all_params:,} | "
        f"Trainable%: {ratio:.4f}"
    )


# -----------------------------
# Main train logic
# -----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train LoRA adapter on JSONL instruction dataset.")
    p.add_argument("--config", type=str, default="configs/train_lora_3b_k80.yaml")
    p.add_argument("--dataset", type=str, default=None, help="Override dataset_path from config")
    p.add_argument("--eval-dataset", type=str, default=None, help="Override eval_dataset_path from config")
    p.add_argument("--model-name", type=str, default=None, help="Override model_name from config")
    p.add_argument("--run-id", type=str, default=None, help="Optional run id; defaults to UTC timestamp")
    p.add_argument("--max-seq-length", type=int, default=None, help="Override max_seq_length")
    return p.parse_args()


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)

    config_path = Path(args.config)
    if config_path.exists():
        file_cfg = read_yaml(config_path)
        cfg = apply_yaml_config(cfg, file_cfg)
    else:
        print(f"[WARN] Config file not found, using defaults: {config_path}")

    # CLI overrides always win
    if args.dataset:
        cfg["dataset_path"] = args.dataset
    if args.eval_dataset:
        cfg["eval_dataset_path"] = args.eval_dataset
    if args.model_name:
        cfg["model_name"] = args.model_name
    if args.run_id:
        cfg["run_id"] = args.run_id
    if args.max_seq_length is not None:
        cfg["max_seq_length"] = int(args.max_seq_length)

    validate_effective_config(cfg)
    return cfg


def load_json_datasets(train_path: Path, eval_path: Optional[Path]) -> Dict[str, Dataset]:
    data_files: Dict[str, str] = {"train": str(train_path)}
    if eval_path is not None:
        data_files["validation"] = str(eval_path)

    ds_dict = load_dataset("json", data_files=data_files)

    out: Dict[str, Dataset] = {"train": ds_dict["train"]}
    if "validation" in ds_dict:
        out["validation"] = ds_dict["validation"]
    return out


def save_run_metadata(run_paths: RunPaths, cfg: Dict[str, Any]) -> None:
    meta = {
        "run_id": run_paths.run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": cfg,
    }
    meta_path = run_paths.model_dir / "run_metadata.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    cfg = build_config(args)

    # Reproducibility seeds
    seed = int(cfg.get("seed", 42))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    set_seed(seed)

    train_path = Path(cfg["dataset_path"])
    eval_path = Path(cfg["eval_dataset_path"]) if cfg.get("eval_dataset_path") else None

    sanity_check_jsonl(train_path)
    if eval_path is not None:
        sanity_check_jsonl(eval_path)

    run_paths = resolve_run_paths(cfg)
    save_run_metadata(run_paths, cfg)

    print(f"[INFO] Run ID: {run_paths.run_id}")
    print(f"[INFO] Model output dir: {run_paths.model_dir}")
    print(f"[INFO] Logs dir: {run_paths.logs_dir}")
    print(f"[INFO] Base model: {cfg['model_name']}")
    print(f"[INFO] Train dataset: {train_path}")
    if eval_path:
        print(f"[INFO] Eval dataset: {eval_path}")

    # Tokenizer / model
    tokenizer = AutoTokenizer.from_pretrained(cfg["model_name"], use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg["model_name"],
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )

    # Important for some causal LMs with gradient checkpointing
    model.config.use_cache = False

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=int(cfg["lora_r"]),
        lora_alpha=int(cfg["lora_alpha"]),
        lora_dropout=float(cfg["lora_dropout"]),
        bias=str(cfg.get("lora_bias", "none")),
        target_modules=cfg["target_modules"],
    )
    model = get_peft_model(model, lora_cfg)
    print_trainable_parameters(model)

    # Dataset load / tokenize
    raw = load_json_datasets(train_path=train_path, eval_path=eval_path)
    train_ds = tokenize_dataset(
        ds=raw["train"],
        tokenizer=tokenizer,
        max_seq_length=int(cfg["max_seq_length"]),
    )
    eval_ds = None
    if "validation" in raw:
        eval_ds = tokenize_dataset(
            ds=raw["validation"],
            tokenizer=tokenizer,
            max_seq_length=int(cfg["max_seq_length"]),
        )

    precision = choose_precision(cfg)

    training_args = TrainingArguments(
        output_dir=str(run_paths.model_dir),
        overwrite_output_dir=bool(cfg.get("overwrite_output_dir", False)),
        num_train_epochs=float(cfg["num_train_epochs"]),
        max_steps=int(cfg["max_steps"]),
        per_device_train_batch_size=int(cfg["train_batch_size"]),
        per_device_eval_batch_size=int(cfg["eval_batch_size"]),
        gradient_accumulation_steps=int(cfg["gradient_accumulation_steps"]),
        learning_rate=float(cfg["learning_rate"]),
        weight_decay=float(cfg["weight_decay"]),
        warmup_ratio=float(cfg["warmup_ratio"]),
        lr_scheduler_type=str(cfg["lr_scheduler_type"]),
        logging_dir=str(run_paths.logs_dir),
        logging_steps=int(cfg["logging_steps"]),
        logging_first_step=bool(cfg.get("logging_first_step", True)),
        save_steps=int(cfg["save_steps"]),
        save_total_limit=int(cfg["save_total_limit"]),
        evaluation_strategy=str(cfg["evaluation_strategy"]),
        eval_steps=int(cfg["eval_steps"]),
        gradient_checkpointing=bool(cfg["gradient_checkpointing"]),
        fp16=bool(precision["fp16"]),
        bf16=bool(precision["bf16"]),
        report_to=cfg["report_to"],
        optim=str(cfg["optim"]),
        dataloader_num_workers=int(cfg["dataloader_num_workers"]),
        seed=seed,
        save_safetensors=bool(cfg.get("save_safetensors", True)),
    )

    # Trainer automatically handles labels for CausalLM with this collator.
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    trainer.train()

    # Save LoRA adapter + tokenizer + trainer state
    trainer.save_model(str(run_paths.model_dir))
    tokenizer.save_pretrained(str(run_paths.model_dir))
    trainer.save_state()

    # Save final metrics
    metrics = {"run_id": run_paths.run_id, "global_step": trainer.state.global_step}
    metrics_path = run_paths.model_dir / "final_metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("[INFO] Training finished.")
    print(f"[INFO] Adapter saved to: {run_paths.model_dir}")
    print(f"[INFO] TensorBoard logs: {run_paths.logs_dir}")


if __name__ == "__main__":
    main()
