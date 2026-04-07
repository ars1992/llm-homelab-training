#!/usr/bin/env python3
"""
prepare_dataset.py

Dataset preparation utility with two modes:

1) jsonl (default)
   Validate/normalize existing instruction-tuning JSONL:
   {"instruction":"...", "input":"...", "output":"..."}

2) vault_md
   Deterministically extract training samples from Markdown files under a vault root.
   Output schema is always:
   {"instruction":"...", "input":"...", "output":"..."}

Vault extraction rules (MVP):
- Parse sections by headings (#, ##, ###, ...)
- A section is sample-worthy if:
  a) it contains a fenced code block with language in {bash, sh, yaml, json}
  OR
  b) it contains >= 3 bullet lines
- For each sample-worthy section create exactly one sample:
  - instruction: fixed runbook-assistant instruction (German, deterministic)
  - input: source_path + section_title + section_body
  - output:
      * all target code blocks + directly adjacent step bullets
      * if no target code blocks exist: bullet list only
- Optional secret redaction on input/output content.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------
# Constants
# -----------------------------

ALLOWED_CODE_LANGS = {"bash", "sh", "yaml", "json"}

FIXED_INSTRUCTION = (
    "Du bist ein Homelab-Runbook-Assistent. "
    "Antworte auf Deutsch in klaren, nachvollziehbaren Schritten ohne Halluzinationen. "
    "Wenn Informationen fehlen, stelle präzise Rückfragen. "
    "Fokus: Docker, Compose, NVIDIA K80 Betrieb und reproduzierbare Abläufe."
)


# -----------------------------
# Data classes
# -----------------------------


@dataclass
class ValidationIssue:
    line_no: int
    reason: str


@dataclass
class PrepareSummary:
    mode: str
    total_input_records: int
    valid_records: int
    invalid_records: int
    issues: List[ValidationIssue]
    files_found: int = 0
    files_scanned: int = 0
    sections_scanned: int = 0
    samples_written: int = 0
    skip_reasons: Optional[Dict[str, int]] = None


@dataclass
class MarkdownSection:
    title: str
    lines: List[str]


@dataclass
class CodeBlock:
    language: str
    start_line: int
    end_line: int
    content_lines: List[str]


# -----------------------------
# Shared helpers
# -----------------------------


def _as_clean_string(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value.strip()


def parse_bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def write_jsonl(
    records: List[Dict[str, str]], output_path: Path, encoding: str = "utf-8"
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding=encoding) as out:
        for rec in records:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")


def summarize_and_print(summary: PrepareSummary) -> None:
    print("Dataset preparation completed.")
    print(f"Mode: {summary.mode}")
    print(f"Valid records written: {summary.valid_records}")
    print(f"Invalid records: {summary.invalid_records}")

    if summary.mode == "jsonl":
        print(f"Input lines processed: {summary.total_input_records}")
    else:
        print(f"Markdown files found: {summary.files_found}")
        print(f"Markdown files scanned: {summary.files_scanned}")
        print(f"Sections scanned: {summary.sections_scanned}")
        print(f"Samples written: {summary.samples_written}")
        if summary.skip_reasons:
            print("\nTop skip reasons:")
            for reason, cnt in sorted(
                summary.skip_reasons.items(), key=lambda x: (-x[1], x[0])
            )[:10]:
                print(f"  - {reason}: {cnt}")

    if summary.invalid_records > 0 and summary.issues:
        print("\nValidation issues:")
        for issue in summary.issues[:20]:
            print(f"  - line {issue.line_no}: {issue.reason}")
        if len(summary.issues) > 20:
            print(f"  ... and {len(summary.issues) - 20} more")


def write_report(
    report_path: Optional[Path], payload: Dict[str, Any], encoding: str = "utf-8"
) -> None:
    if report_path is None:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding=encoding) as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# -----------------------------
# JSONL mode
# -----------------------------


def validate_record(
    obj: Dict[str, Any],
    line_no: int,
    allow_empty_input: bool = True,
) -> Tuple[bool, Optional[Dict[str, str]], Optional[str]]:
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


def prepare_jsonl_mode(
    input_path: Path,
    output_path: Path,
    strict: bool = False,
    max_samples: Optional[int] = None,
    allow_empty_input: bool = True,
    encoding: str = "utf-8",
) -> PrepareSummary:
    issues: List[ValidationIssue] = []
    normalized_records: List[Dict[str, str]] = []
    total_lines = 0

    with input_path.open("r", encoding=encoding) as f:
        for line_no, raw_line in enumerate(f, start=1):
            if max_samples is not None and len(normalized_records) >= max_samples:
                break

            line = raw_line.strip()
            if line == "":
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

    write_jsonl(normalized_records, output_path=output_path, encoding=encoding)

    return PrepareSummary(
        mode="jsonl",
        total_input_records=total_lines,
        valid_records=len(normalized_records),
        invalid_records=len(issues),
        issues=issues,
    )


# -----------------------------
# Vault markdown mode
# -----------------------------


def redact_secrets(text: str) -> str:
    """
    Remove potentially sensitive content without inserting marker tokens.
    Strategy:
    - drop full lines containing sensitive keywords
    - remove secret-like key/value assignments from remaining lines
    - remove long token-like substrings (base64/hex)
    """
    if not text:
        return text

    keyword_line = re.compile(
        r"(?i)("
        r"token|api[_-]?key|secret|password|begin private key|openai|paperless[_-]?token|hf[_-]?token"
        r")"
    )
    assignment = re.compile(
        r"(?i)\b("
        r"token|api[_-]?key|secret|password|pass|hf[_-]?token|paperless[_-]?token"
        r")\b\s*[:=]\s*([^\s\"']{6,}|\"[^\"]{6,}\"|'[^']{6,}')"
    )
    long_base64 = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")
    long_hex = re.compile(r"\b[a-fA-F0-9]{32,}\b")

    cleaned_lines: List[str] = []
    for line in text.splitlines():
        if keyword_line.search(line):
            continue

        line = assignment.sub("", line)
        line = long_base64.sub("", line)
        line = long_hex.sub("", line)
        line = re.sub(r"\s{2,}", " ", line).strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def is_heading_line(line: str) -> bool:
    return re.match(r"^\s*#{1,6}\s+\S", line) is not None


def heading_title(line: str) -> str:
    return re.sub(r"^\s*#{1,6}\s*", "", line).strip()


def split_markdown_sections(lines: List[str]) -> List[MarkdownSection]:
    """
    Split markdown text by headings.
    Includes a root section for content before first heading.
    """
    sections: List[MarkdownSection] = []
    current_title = "(root)"
    current_lines: List[str] = []

    for line in lines:
        if is_heading_line(line):
            # flush previous section
            sections.append(MarkdownSection(title=current_title, lines=current_lines))
            current_title = heading_title(line) or "(untitled)"
            current_lines = []
        else:
            current_lines.append(line)

    sections.append(MarkdownSection(title=current_title, lines=current_lines))
    # keep deterministic order, including empty sections; caller can filter
    return sections


def parse_codeblocks(section_lines: List[str]) -> List[CodeBlock]:
    codeblocks: List[CodeBlock] = []
    in_block = False
    block_lang = ""
    block_start = -1
    block_lines: List[str] = []

    for idx, line in enumerate(section_lines):
        m = re.match(r"^\s*```([A-Za-z0-9_-]+)?\s*$", line)
        if m and not in_block:
            in_block = True
            block_lang = (m.group(1) or "").strip().lower()
            block_start = idx
            block_lines = []
            continue
        if m and in_block:
            # closing fence
            codeblocks.append(
                CodeBlock(
                    language=block_lang,
                    start_line=block_start,
                    end_line=idx,
                    content_lines=block_lines[:],
                )
            )
            in_block = False
            block_lang = ""
            block_start = -1
            block_lines = []
            continue

        if in_block:
            block_lines.append(line)

    # unclosed code fence: ignore to stay conservative
    return codeblocks


def is_bullet_line(line: str) -> bool:
    return re.match(r"^\s*([-*]|\d+\.)\s+\S", line) is not None


def bullet_lines(lines: List[str]) -> List[str]:
    return [ln for ln in lines if is_bullet_line(ln)]


def gather_adjacent_bullets(lines: List[str], start: int, end: int) -> List[str]:
    """
    Gather directly adjacent bullet lines around a code block:
    - contiguous bullet lines immediately above
    - contiguous bullet lines immediately below
    Stops at first non-bullet line in each direction.
    """
    out: List[str] = []

    # above
    i = start - 1
    above_reversed: List[str] = []
    while i >= 0 and is_bullet_line(lines[i]):
        above_reversed.append(lines[i])
        i -= 1
    out.extend(reversed(above_reversed))

    # below
    j = end + 1
    while j < len(lines) and is_bullet_line(lines[j]):
        out.append(lines[j])
        j += 1

    return out


def has_target_codeblock(codeblocks: List[CodeBlock]) -> bool:
    for cb in codeblocks:
        if cb.language in ALLOWED_CODE_LANGS:
            return True
    return False


def section_is_sample_worthy(section: MarkdownSection) -> Tuple[bool, str]:
    lines = section.lines
    if not lines:
        return False, "empty_section"

    cbs = parse_codeblocks(lines)
    if has_target_codeblock(cbs):
        return True, "has_target_codeblock"

    bullets = bullet_lines(lines)
    if len(bullets) >= 3:
        return True, "has_3plus_bullets"

    return False, "no_target_signals"


def build_output_from_section(section: MarkdownSection) -> Tuple[Optional[str], str]:
    """
    Build output using strict extraction policy:
    - target code blocks + directly adjacent step bullets
    - if no target code blocks: only bullet list
    """
    lines = section.lines
    cbs = parse_codeblocks(lines)

    parts: List[str] = []
    seen_bullets = set()

    target_cb_found = False
    for cb in cbs:
        if cb.language not in ALLOWED_CODE_LANGS:
            continue
        target_cb_found = True

        # add adjacent bullets (above+below contiguous)
        adj = gather_adjacent_bullets(lines, cb.start_line, cb.end_line)
        for b in adj:
            key = b.strip()
            if key not in seen_bullets:
                parts.append(b.rstrip())
                seen_bullets.add(key)

        # add fenced code block
        parts.append(f"```{cb.language}")
        parts.extend([ln.rstrip() for ln in cb.content_lines])
        parts.append("```")

    if target_cb_found:
        text = "\n".join(p for p in parts if p is not None).strip()
        if text:
            return text, "code_and_adjacent_bullets"
        return None, "empty_extraction_after_code"

    # no target codeblocks: use bullets only
    bl = bullet_lines(lines)
    if not bl:
        return None, "no_extractable_bullets"
    text = "\n".join(b.rstrip() for b in bl).strip()
    if not text:
        return None, "empty_bullets"
    return text, "bullets_only"


def build_input_context(source_path: Path, section: MarkdownSection) -> str:
    body = "\n".join(section.lines).strip()
    return (
        f"source_path: {source_path.as_posix()}\n"
        f"section_title: {section.title}\n"
        f"section_body:\n"
        f"{body}"
    ).strip()


def iter_markdown_files(vault_root: Path, max_files: Optional[int]) -> List[Path]:
    files = sorted(
        [p for p in vault_root.rglob("*.md") if p.is_file()], key=lambda p: p.as_posix()
    )
    if max_files is not None and max_files >= 0:
        return files[:max_files]
    return files


def prepare_vault_md_mode(
    vault_root: Path,
    output_path: Path,
    max_files: Optional[int],
    max_samples: Optional[int],
    redact: bool,
    encoding: str = "utf-8",
) -> PrepareSummary:
    if not vault_root.exists():
        raise FileNotFoundError(f"Vault root does not exist: {vault_root}")
    if not vault_root.is_dir():
        raise NotADirectoryError(f"Vault root is not a directory: {vault_root}")

    md_files = iter_markdown_files(vault_root=vault_root, max_files=max_files)
    skip_reasons = collections.Counter()
    records: List[Dict[str, str]] = []

    files_scanned = 0
    sections_scanned = 0

    for md_path in md_files:
        if max_samples is not None and len(records) >= max_samples:
            break

        files_scanned += 1
        rel_path = md_path.relative_to(vault_root)

        try:
            raw = md_path.read_text(encoding=encoding, errors="replace")
        except Exception:
            skip_reasons["file_read_error"] += 1
            continue

        lines = raw.splitlines()
        sections = split_markdown_sections(lines)

        for sec in sections:
            if max_samples is not None and len(records) >= max_samples:
                break

            sections_scanned += 1
            worthy, reason = section_is_sample_worthy(sec)
            if not worthy:
                skip_reasons[reason] += 1
                continue

            output_text, out_reason = build_output_from_section(sec)
            if not output_text:
                skip_reasons[out_reason] += 1
                continue

            input_text = build_input_context(source_path=rel_path, section=sec)

            if redact:
                input_text = redact_secrets(input_text)
                output_text = redact_secrets(output_text)

            # Basic non-empty post-redaction checks
            if not input_text.strip():
                skip_reasons["empty_input_after_redaction"] += 1
                continue
            if not output_text.strip():
                skip_reasons["empty_output_after_redaction"] += 1
                continue

            rec = {
                "instruction": FIXED_INSTRUCTION,
                "input": input_text,
                "output": output_text,
            }
            records.append(rec)

    write_jsonl(records, output_path=output_path, encoding=encoding)

    return PrepareSummary(
        mode="vault_md",
        total_input_records=sections_scanned,
        valid_records=len(records),
        invalid_records=0,
        issues=[],
        files_found=len(md_files),
        files_scanned=files_scanned,
        sections_scanned=sections_scanned,
        samples_written=len(records),
        skip_reasons=dict(skip_reasons),
    )


# -----------------------------
# CLI
# -----------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare training dataset from JSONL or markdown vault sections."
    )

    parser.add_argument(
        "--mode",
        choices=["jsonl", "vault_md"],
        default="jsonl",
        help="Preparation mode: jsonl (validate/normalize) or vault_md (extract from markdown vault).",
    )

    # jsonl mode args
    parser.add_argument(
        "--input",
        default=None,
        help="Path to source JSONL dataset (required in mode=jsonl).",
    )

    # shared required output
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSONL dataset.",
    )

    # jsonl mode options
    parser.add_argument(
        "--strict",
        action="store_true",
        help="In jsonl mode: fail on first invalid record.",
    )
    parser.add_argument(
        "--disallow-empty-input",
        action="store_true",
        help="In jsonl mode: treat empty 'input' as invalid.",
    )

    # vault mode options
    parser.add_argument(
        "--vault-root",
        default=None,
        help="In vault_md mode: root folder containing markdown documentation files.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=500,
        help="In vault_md mode: max markdown files to scan deterministically.",
    )
    parser.add_argument(
        "--redact-secrets",
        default="true",
        help="In vault_md mode: true/false for regex-based secret redaction.",
    )

    # shared options
    parser.add_argument(
        "--max-samples",
        type=int,
        default=5000,
        help="Maximum number of output samples (all modes).",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8).",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional JSON report output path.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_path = Path(args.output)
    report_path = Path(args.report) if args.report else None
    max_samples = int(args.max_samples) if args.max_samples is not None else None

    if args.mode == "jsonl":
        if not args.input:
            raise ValueError("--input is required in --mode jsonl")
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")

        summary = prepare_jsonl_mode(
            input_path=input_path,
            output_path=output_path,
            strict=bool(args.strict),
            max_samples=max_samples,
            allow_empty_input=not bool(args.disallow_empty_input),
            encoding=args.encoding,
        )

    elif args.mode == "vault_md":
        if not args.vault_root:
            raise ValueError("--vault-root is required in --mode vault_md")

        vault_root = Path(args.vault_root)
        summary = prepare_vault_md_mode(
            vault_root=vault_root,
            output_path=output_path,
            max_files=args.max_files,
            max_samples=max_samples,
            redact=parse_bool_like(args.redact_secrets),
            encoding=args.encoding,
        )
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")

    summarize_and_print(summary)

    report_payload = {
        "mode": summary.mode,
        "total_input_records": summary.total_input_records,
        "valid_records": summary.valid_records,
        "invalid_records": summary.invalid_records,
        "files_found": summary.files_found,
        "files_scanned": summary.files_scanned,
        "sections_scanned": summary.sections_scanned,
        "samples_written": summary.samples_written,
        "skip_reasons": summary.skip_reasons or {},
        "issues": [{"line_no": i.line_no, "reason": i.reason} for i in summary.issues],
    }
    write_report(
        report_path=report_path, payload=report_payload, encoding=args.encoding
    )


if __name__ == "__main__":
    main()
