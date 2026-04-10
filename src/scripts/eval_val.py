#!/usr/bin/env python3
"""
eval_val.py

Enhanced regression evaluator for val.jsonl with:
- per-item fail diagnostics
- configurable normalization modes
- tag-based subscores
- partial credit for runbook items

Expected JSONL schema per line:
{
  "id": "val-001",
  "instruction": "...",
  "input": "",
  "expected_contains": ["..."],
  "tags": ["regression", "openbook", "exact"]
}
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    from peft import PeftModel
except Exception:
    PeftModel = None  # Optional at runtime


# -----------------------------
# Time / config helpers
# -----------------------------


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


# -----------------------------
# Prompting
# -----------------------------


def build_prompt(
    instruction: str, input_text: str, tags: Optional[List[str]] = None
) -> str:
    """
    Tag-aware prompt hardening:
    - exact: answer with value only
    - runbook: answer in numbered steps
    """
    tag_set = normalized_tag_set(tags)

    instruction = instruction.strip()
    input_text = (input_text or "").strip()

    if "exact" in tag_set:
        policy = "Regel: Antworte nur mit dem exakten Wert. Keine Einleitung, keine Erklärung."
    elif "runbook" in tag_set:
        policy = (
            "Regel: Antworte auf Deutsch in nummerierten Schritten "
            "(8-12 Schritte), präzise und ohne Fülltext."
        )
    else:
        policy = "Regel: Antworte präzise und knapp auf Deutsch."

    if input_text:
        return (
            f"{policy}\n\n"
            f"Aufgabe:\n{instruction}\n\n"
            f"Kontext:\n{input_text}\n\n"
            "Antwort:\n"
        )

    return f"{policy}\n\nAufgabe:\n{instruction}\n\nAntwort:\n"


# -----------------------------
# Normalization / matching
# -----------------------------


def normalized_tag_set(tags: Optional[List[str]]) -> Set[str]:
    return {t.strip().lower() for t in (tags or []) if isinstance(t, str) and t.strip()}


def unify_newlines(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


EXACT_WRAPPERS = [
    "kontext:",
    "antwort:",
    "instruction:",
    "### instruction:",
    "### response:",
    "aufgabe:",
    "fokus:",
    "regel:",
]


def strip_known_wrappers_exact(s: str) -> str:
    t = unify_newlines(s or "")
    for wrapper in EXACT_WRAPPERS:
        t = re.sub(rf"(?im)^\s*{re.escape(wrapper)}\s*", "", t)
    return t


def strip_surrounding_wrappers(s: str) -> str:
    """
    Removes surrounding backticks and quotes repeatedly:
    `foo` -> foo
    "foo" -> foo
    'foo' -> foo
    """
    out = s.strip()
    changed = True
    while changed and len(out) >= 2:
        changed = False
        pairs = [("`", "`"), ('"', '"'), ("'", "'")]
        for left, right in pairs:
            if out.startswith(left) and out.endswith(right) and len(out) >= 2:
                out = out[1:-1].strip()
                changed = True
    return out


def normalize_text(
    s: str,
    trim_whitespace: bool = True,
    case_sensitive: bool = False,
    strip_wrappers: bool = False,
) -> str:
    out = unify_newlines(s)
    if strip_wrappers:
        out = strip_surrounding_wrappers(out)
    if trim_whitespace:
        out = " ".join(out.split())
    if not case_sensitive:
        out = out.lower()
    return out


def normalize_exact_text(
    s: str,
    trim_whitespace: bool = True,
    case_sensitive: bool = True,
    strip_wrappers: bool = False,
    first_line_only: bool = True,
) -> str:
    out = unify_newlines(s or "")
    out = strip_known_wrappers_exact(out)  # always enabled for exact normalization
    if strip_wrappers:
        out = strip_surrounding_wrappers(out)
    out = re.sub(r"[ \t]+", " ", out)
    if first_line_only:
        out = out.split("\n", 1)[0]
    if trim_whitespace:
        out = out.strip()
    if not case_sensitive:
        out = out.lower()
    return out


def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def extract_candidate_for_exact(output: str, expected: str) -> Optional[str]:
    o = output or ""
    e = expected or ""
    if not e:
        return None

    if "/" in e:
        candidates = re.findall(r"/[^\s'\"`]+(?:\s[^\s:'\"`]+)*", o)
        cleaned = [c.strip().rstrip(".,;:") for c in candidates if c and c.strip()]
        for c in cleaned:
            if c == e:
                return c
        containing = [c for c in cleaned if e in c]
        if containing:
            containing.sort(key=len, reverse=True)
            return containing[0]
        if cleaned:
            cleaned.sort(key=lambda c: (_common_prefix_len(c, e), len(c)), reverse=True)
            return cleaned[0]
        return None

    if "." in e:
        m = re.search(rf"\b{re.escape(e)}\b", o)
        if m:
            return m.group(0)

    m = re.search(rf"\b{re.escape(e)}\b", o)
    if m:
        return m.group(0)

    return None


def preview_text(s: str, max_chars: int) -> str:
    s = s or ""
    if max_chars <= 0:
        return ""
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "..."


# -----------------------------
# Dataset load
# -----------------------------


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
            if not isinstance(obj["tags"], list):
                raise ValueError(f"{path}:{line_no} tags must be list")

            for token in obj["expected_contains"]:
                if not isinstance(token, str) or not token.strip():
                    raise ValueError(
                        f"{path}:{line_no} expected_contains has invalid token"
                    )

            rows.append(obj)

    if not rows:
        raise ValueError(f"No rows loaded from {path}")
    return rows


# -----------------------------
# Model / inference
# -----------------------------


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
    tags: Optional[List[str]],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
) -> str:
    prompt = build_prompt(instruction, input_text, tags=tags)
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


# -----------------------------
# Evaluation logic
# -----------------------------


def evaluate_item(
    prediction: str,
    expected_contains: List[str],
    tags: Optional[List[str]],
    non_exact_case_sensitive: bool,
    non_exact_trim_whitespace: bool,
    non_exact_strip_wrappers: bool,
    exact_case_sensitive: bool,
    exact_trim_whitespace: bool,
    exact_strip_wrappers: bool,
    exact_first_line_only: bool,
    runbook_pass_threshold: float,
    no_prompt_echo_tag: str = "no_prompt_echo",
) -> Dict[str, Any]:
    tag_set = normalized_tag_set(tags)
    is_exact = "exact" in tag_set
    is_runbook = "runbook" in tag_set

    # optional anti-echo guard
    if no_prompt_echo_tag.strip().lower() in tag_set:
        pred_lower = prediction.lower()
        prompt_markers = ["instruction:", "input:", "###", "aufgabe:", "antwort:"]
        if any(marker in pred_lower for marker in prompt_markers):
            return {
                "pass": False,
                "coverage": 0.0,
                "hits": 0,
                "total_expected": len(expected_contains),
                "found_expected_contains": [],
                "missing_expected_contains": expected_contains[:],
                "fail_reason": "prompt_echo_detected",
                "exact_candidate": None,
            }

    if is_exact:
        pred_norm = normalize_exact_text(
            prediction,
            trim_whitespace=exact_trim_whitespace,
            case_sensitive=exact_case_sensitive,
            strip_wrappers=exact_strip_wrappers,
            first_line_only=exact_first_line_only,
        )
        exp_norm_pairs = [
            (
                original,
                normalize_exact_text(
                    original,
                    trim_whitespace=exact_trim_whitespace,
                    case_sensitive=exact_case_sensitive,
                    strip_wrappers=exact_strip_wrappers,
                    first_line_only=exact_first_line_only,
                ),
            )
            for original in expected_contains
        ]

        # exact mode with candidate extraction:
        # normalize output, extract best candidate for each expected token, then exact compare.
        exact_found: List[str] = []
        best_candidate: Optional[str] = None
        for original, nrm in exp_norm_pairs:
            candidate = extract_candidate_for_exact(pred_norm, nrm) or pred_norm
            candidate_norm = normalize_exact_text(
                candidate,
                trim_whitespace=exact_trim_whitespace,
                case_sensitive=exact_case_sensitive,
                strip_wrappers=exact_strip_wrappers,
                first_line_only=exact_first_line_only,
            )
            if candidate_norm == nrm:
                exact_found.append(original)
                best_candidate = candidate
                break

        missing = [] if exact_found else expected_contains[:]
        passed = len(exact_found) > 0
        coverage = 1.0 if passed else 0.0
        fail_reason = None if passed else "exact_mismatch"

        return {
            "pass": passed,
            "coverage": coverage,
            "hits": 1 if passed else 0,
            "total_expected": len(expected_contains),
            "found_expected_contains": exact_found,
            "missing_expected_contains": missing,
            "fail_reason": fail_reason,
            "exact_candidate": best_candidate if passed else pred_norm,
        }

    # non-exact (substring coverage)
    pred_norm = normalize_text(
        prediction,
        trim_whitespace=non_exact_trim_whitespace,
        case_sensitive=non_exact_case_sensitive,
        strip_wrappers=non_exact_strip_wrappers,
    )
    exp_norm_pairs = [
        (
            original,
            normalize_text(
                original,
                trim_whitespace=non_exact_trim_whitespace,
                case_sensitive=non_exact_case_sensitive,
                strip_wrappers=non_exact_strip_wrappers,
            ),
        )
        for original in expected_contains
    ]

    found: List[str] = []
    missing: List[str] = []
    for original, nrm in exp_norm_pairs:
        if nrm and nrm in pred_norm:
            found.append(original)
        else:
            missing.append(original)

    total_expected = len(expected_contains)
    hits = len(found)
    coverage = (hits / total_expected) if total_expected > 0 else 0.0

    if is_runbook:
        passed = coverage >= float(runbook_pass_threshold)
        fail_reason = None if passed else "runbook_coverage_below_threshold"
    else:
        passed = hits == total_expected
        fail_reason = None if passed else "missing_expected_contains"

    return {
        "pass": passed,
        "coverage": coverage,
        "hits": hits,
        "total_expected": total_expected,
        "found_expected_contains": found,
        "missing_expected_contains": missing,
        "fail_reason": fail_reason,
        "exact_candidate": None,
    }


def group_name_for_tags(tags: List[str]) -> Optional[str]:
    t = normalized_tag_set(tags)
    if "openbook" in t and "exact" in t:
        return "exact_openbook"
    if "openbook" in t and "runbook" in t:
        return "runbook_openbook"
    if "closedbook" in t or "closedbook_policy" in t:
        return "closedbook"
    return None


# -----------------------------
# CLI
# -----------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Enhanced evaluator for val.jsonl with diagnostics and subscores."
    )
    p.add_argument("--config", type=str, default="configs/datasets/val_regression.yaml")
    p.add_argument("--dataset", type=str, default=None, help="Override dataset path")
    p.add_argument("--base-model", type=str, default="facebook/opt-2.7b")
    p.add_argument("--adapter-path", type=str, default=None)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--output-dir", type=str, default=None)
    p.add_argument("--device", type=str, default="auto", help="auto|cpu|cuda")
    p.add_argument("--max-samples", type=int, default=0, help="0 = all")
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--max-new-tokens", type=int, default=None)
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--top-p", type=float, default=None)
    p.add_argument("--do-sample", action="store_true")
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--no-trim-whitespace", action="store_true")
    return p.parse_args()


# -----------------------------
# Main
# -----------------------------


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

    # generation
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

    # normalization defaults (legacy-compatible with previous config keys)
    default_case_sensitive = bool(
        args.case_sensitive
        or cfg_get(cfg, "evaluation", "case_sensitive", default=False)
    )
    default_trim = not bool(args.no_trim_whitespace) and bool(
        cfg_get(cfg, "evaluation", "trim_whitespace", default=True)
    )

    # exact mode remains strict
    exact_case_sensitive = bool(
        cfg_get(cfg, "evaluation", "exact", "case_sensitive", default=True)
    )
    exact_trim_whitespace = bool(
        cfg_get(cfg, "evaluation", "exact", "trim_whitespace", default=True)
    )
    exact_strip_wrappers = bool(
        cfg_get(cfg, "evaluation", "exact", "strip_wrappers", default=False)
    )
    exact_first_line_only = bool(
        cfg_get(cfg, "evaluation", "exact", "first_line_only", default=True)
    )

    # non-exact mode can normalize more aggressively
    non_exact_case_sensitive = bool(
        cfg_get(
            cfg,
            "evaluation",
            "non_exact",
            "case_sensitive",
            default=default_case_sensitive,
        )
    )
    non_exact_trim_whitespace = bool(
        cfg_get(cfg, "evaluation", "non_exact", "trim_whitespace", default=default_trim)
    )
    non_exact_strip_wrappers = bool(
        cfg_get(cfg, "evaluation", "non_exact", "strip_wrappers", default=True)
    )

    runbook_pass_threshold = float(
        cfg_get(cfg, "evaluation", "runbook", "pass_threshold", default=0.6)
    )
    output_preview_chars = int(
        cfg_get(cfg, "evaluation", "debug", "output_preview_chars", default=200)
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
    coverage_sum = 0.0

    group_totals: Dict[str, int] = {
        "exact_openbook": 0,
        "runbook_openbook": 0,
        "closedbook": 0,
    }
    group_passed: Dict[str, int] = {
        "exact_openbook": 0,
        "runbook_openbook": 0,
        "closedbook": 0,
    }
    group_coverage_sum: Dict[str, float] = {
        "exact_openbook": 0.0,
        "runbook_openbook": 0.0,
        "closedbook": 0.0,
    }

    for idx, row in enumerate(rows, start=1):
        tags = row.get("tags", [])
        prediction = generate_one(
            model=model,
            tokenizer=tokenizer,
            instruction=row["instruction"],
            input_text=row["input"],
            tags=tags,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
        )

        verdict = evaluate_item(
            prediction=prediction,
            expected_contains=row["expected_contains"],
            tags=tags,
            non_exact_case_sensitive=non_exact_case_sensitive,
            non_exact_trim_whitespace=non_exact_trim_whitespace,
            non_exact_strip_wrappers=non_exact_strip_wrappers,
            exact_case_sensitive=exact_case_sensitive,
            exact_trim_whitespace=exact_trim_whitespace,
            exact_strip_wrappers=exact_strip_wrappers,
            exact_first_line_only=exact_first_line_only,
            runbook_pass_threshold=runbook_pass_threshold,
        )

        passed = bool(verdict["pass"])
        coverage = float(verdict["coverage"])

        if passed:
            pass_count += 1
        coverage_sum += coverage

        group = group_name_for_tags(tags)
        if group is not None:
            group_totals[group] += 1
            group_coverage_sum[group] += coverage
            if passed:
                group_passed[group] += 1

        if "exact" in normalized_tag_set(tags):
            normalized_preview = normalize_exact_text(
                prediction,
                trim_whitespace=exact_trim_whitespace,
                case_sensitive=exact_case_sensitive,
                strip_wrappers=exact_strip_wrappers,
                first_line_only=exact_first_line_only,
            )
        else:
            normalized_preview = normalize_text(
                prediction,
                trim_whitespace=non_exact_trim_whitespace,
                case_sensitive=non_exact_case_sensitive,
                strip_wrappers=non_exact_strip_wrappers,
            )

        result_row = {
            "id": row["id"],
            "instruction": row["instruction"],
            "input": row["input"],
            "tags": tags,
            "expected_contains": row["expected_contains"],
            "prediction": prediction,
            "pass": passed,
            "coverage": coverage,
            "hits": verdict["hits"],
            "total_expected": verdict["total_expected"],
            "found_expected_contains": verdict["found_expected_contains"],
            "missing_expected_contains": verdict["missing_expected_contains"],
            "fail_reason": verdict["fail_reason"],
            "exact_candidate": verdict.get("exact_candidate"),
            "output_preview": preview_text(prediction, output_preview_chars),
            "normalized_output_preview": preview_text(
                normalized_preview, output_preview_chars
            ),
        }
        results.append(result_row)

        print(
            f"[eval-val] {idx}/{len(rows)} id={row['id']} "
            f"pass={passed} coverage={coverage:.3f}"
        )

    total = len(results)
    pass_rate = (pass_count / total) if total else 0.0
    avg_coverage = (coverage_sum / total) if total else 0.0

    def _safe_rate(passed_n: int, total_n: int) -> float:
        return (passed_n / total_n) if total_n else 0.0

    def _safe_avg(sum_cov: float, total_n: int) -> float:
        return (sum_cov / total_n) if total_n else 0.0

    summary = {
        "total": total,
        "passed": pass_count,
        "failed": total - pass_count,
        "pass_rate": pass_rate,
        "avg_coverage": avg_coverage,
        "n_cases_exact_openbook": group_totals["exact_openbook"],
        "n_cases_runbook_openbook": group_totals["runbook_openbook"],
        "n_cases_closedbook": group_totals["closedbook"],
        "pass_rate_exact_openbook": _safe_rate(
            group_passed["exact_openbook"], group_totals["exact_openbook"]
        ),
        "pass_rate_runbook_openbook": _safe_rate(
            group_passed["runbook_openbook"], group_totals["runbook_openbook"]
        ),
        "pass_rate_closedbook": _safe_rate(
            group_passed["closedbook"], group_totals["closedbook"]
        ),
        "avg_coverage_exact_openbook": _safe_avg(
            group_coverage_sum["exact_openbook"], group_totals["exact_openbook"]
        ),
        "avg_coverage_runbook_openbook": _safe_avg(
            group_coverage_sum["runbook_openbook"], group_totals["runbook_openbook"]
        ),
        "avg_coverage_closedbook": _safe_avg(
            group_coverage_sum["closedbook"], group_totals["closedbook"]
        ),
    }

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
            "batch_size": args.batch_size,
            "normalization": {
                "exact": {
                    "case_sensitive": exact_case_sensitive,
                    "trim_whitespace": exact_trim_whitespace,
                    "strip_wrappers": exact_strip_wrappers,
                    "first_line_only": exact_first_line_only,
                    "always_strip_known_wrappers": True,
                },
                "non_exact": {
                    "case_sensitive": non_exact_case_sensitive,
                    "trim_whitespace": non_exact_trim_whitespace,
                    "strip_wrappers": non_exact_strip_wrappers,
                },
            },
            "runbook_pass_threshold": runbook_pass_threshold,
            "output_preview_chars": output_preview_chars,
        },
        "summary": summary,
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
    print(
        "[eval-val] "
        f"pass_rate={pass_rate:.4f} ({pass_count}/{total}) "
        f"avg_coverage={avg_coverage:.4f}"
    )


if __name__ == "__main__":
    main()
