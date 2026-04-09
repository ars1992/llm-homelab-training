#!/bin/sh
# reset_runtime_state.sh
#
# Zweck:
# - Sauberer Reset lokaler Laufzeit-Artefakte für einen neuen End-to-End-Test
# - Cron-sicherer Cleanup ohne Änderung von Repository-Code oder versionierten Seeds
#
# Verhalten:
# - stoppt optional den Serving-Stack
# - entfernt nicht versionierte Runtime-Artefakte unter data/
# - setzt Run-/Promotion-Pointer deterministisch zurück
# - lässt committed Referenzdaten und Dokumentation unberührt
#
# Nutzung:
#   sh scripts/reset_runtime_state.sh
#   sh scripts/reset_runtime_state.sh --with-serve-down
#   sh scripts/reset_runtime_state.sh --full
#
# Modus:
# - Standard:
#   - entfernt Modelle, Logs, Evals, generierte Train-Datasets und Run-State
#   - behält versionierte Referenzdaten wie val.jsonl, runbook_samples.jsonl,
#     exact_extraction_samples.jsonl und data/README.md
# - --full:
#   - entfernt zusätzlich weitere generierte Datensatz-Artefakte unter data/datasets/
#   - committed Referenzdateien werden weiterhin nicht gelöscht
#
# Exit Codes:
# - 0: Erfolg
# - 1: Projektstruktur ungültig / Vorbedingungen fehlen

set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DATA_DIR="${PROJECT_ROOT}/data"
RUNS_DIR="${DATA_DIR}/runs"
DATASETS_DIR="${DATA_DIR}/datasets"
MODELS_DIR="${DATA_DIR}/models"
LOGS_DIR="${DATA_DIR}/logs"
EVALS_DIR="${DATA_DIR}/evals"

WITH_SERVE_DOWN=0
FULL_RESET=0

for arg in "$@"; do
  case "$arg" in
    --with-serve-down)
      WITH_SERVE_DOWN=1
      ;;
    --full)
      FULL_RESET=1
      ;;
    -h|--help)
      cat <<'EOF'
reset_runtime_state.sh

Verwendung:
  sh scripts/reset_runtime_state.sh [--with-serve-down] [--full]

Optionen:
  --with-serve-down   Stoppt den Serving-Stack vor dem Reset.
  --full              Entfernt zusätzlich generierte Datensatz-Artefakte.
  -h, --help          Zeigt diese Hilfe.

Reset-Umfang (Standard):
  - data/models/*
  - data/logs/*
  - data/evals/*
  - data/runs/* (mit sauberem Wiederaufbau der Pointer-Dateien)
  - generierte Trainings-/Merge-/Report-Dateien unter data/datasets/

Nicht gelöscht werden:
  - data/README.md
  - data/datasets/val.jsonl
  - data/datasets/runbook_samples.jsonl
  - data/datasets/exact_extraction_samples.jsonl
  - data/datasets/.gitkeep
EOF
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

require_dir() {
  if [ ! -d "$1" ]; then
    echo "ERROR: required directory missing: $1" >&2
    exit 1
  fi
}

safe_rm_children() {
  target_dir="$1"
  if [ -d "$target_dir" ]; then
    find "$target_dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  fi
}

reset_runs_state() {
  mkdir -p "$RUNS_DIR" "$RUNS_DIR/smoke"

  rm -f \
    "$RUNS_DIR/LATEST_REALRUN_ID" \
    "$RUNS_DIR/LATEST_OK_ADAPTER_ID" \
    "$RUNS_DIR/LATEST_OK_ADAPTER_PATH" \
    "$RUNS_DIR/LATEST_PROMOTION_SUMMARY.json" \
    "$RUNS_DIR/LATEST_EVAL_RUN_ID" \
    "$RUNS_DIR/LOCK"

  : > "$RUNS_DIR/LATEST_OK_ADAPTER_ID"
  printf '%s\n' 'data/models/<run-id>' > "$RUNS_DIR/LATEST_OK_ADAPTER_PATH"
}

reset_datasets_standard() {
  mkdir -p "$DATASETS_DIR"

  # Nur generierte, nicht referenzielle Artefakte entfernen.
  rm -f \
    "$DATASETS_DIR/train.jsonl" \
    "$DATASETS_DIR/train.normalized.jsonl" \
    "$DATASETS_DIR/train_vault.jsonl" \
    "$DATASETS_DIR/raw.jsonl" \
    "$DATASETS_DIR/prepare_report.json" \
    "$DATASETS_DIR/prepare_vault_report.json" \
    "$DATASETS_DIR/exact_extraction_report.json" \
    "$DATASETS_DIR/merge_report.json" \
    "$DATASETS_DIR/val_validate_report.json" \
    "$DATASETS_DIR/self_edits.jsonl" \
    "$DATASETS_DIR/self_edits.report.json"
}

reset_datasets_full() {
  reset_datasets_standard

  # Zusätzliche generierte Datensatzreste entfernen, aber committed Referenzen schützen.
  find "$DATASETS_DIR" -mindepth 1 -maxdepth 1 \
    ! -name 'README.md' \
    ! -name '.gitkeep' \
    ! -name 'val.jsonl' \
    ! -name 'runbook_samples.jsonl' \
    ! -name 'exact_extraction_samples.jsonl' \
    -exec rm -rf {} +
}

stop_serve_if_requested() {
  if [ "$WITH_SERVE_DOWN" -ne 1 ]; then
    return 0
  fi

  echo "INFO: stopping serving stack"
  if command -v docker >/dev/null 2>&1; then
    docker compose -f "${PROJECT_ROOT}/docker/compose.serve.yaml" down >/dev/null 2>&1 || true
  else
    echo "WARN: docker not found; serve stack not stopped" >&2
  fi
}

main() {
  require_dir "$PROJECT_ROOT"
  require_dir "$DATA_DIR"
  require_dir "$DATASETS_DIR"

  echo "INFO: project_root=$PROJECT_ROOT"
  echo "INFO: mode=$( [ "$FULL_RESET" -eq 1 ] && printf '%s' 'full' || printf '%s' 'standard' )"
  echo "INFO: with_serve_down=$WITH_SERVE_DOWN"

  stop_serve_if_requested

  echo "INFO: clearing models, logs, evals"
  safe_rm_children "$MODELS_DIR"
  safe_rm_children "$LOGS_DIR"
  safe_rm_children "$EVALS_DIR"

  echo "INFO: resetting run state"
  safe_rm_children "$RUNS_DIR"
  reset_runs_state

  echo "INFO: resetting datasets"
  if [ "$FULL_RESET" -eq 1 ]; then
    reset_datasets_full
  else
    reset_datasets_standard
  fi

  mkdir -p "$MODELS_DIR" "$LOGS_DIR" "$EVALS_DIR" "$RUNS_DIR/smoke"

  echo "OK: runtime state reset complete"
  echo "INFO: preserved reference files:"
  echo "  - data/README.md"
  echo "  - data/datasets/val.jsonl"
  echo "  - data/datasets/runbook_samples.jsonl"
  echo "  - data/datasets/exact_extraction_samples.jsonl"
  echo "  - data/datasets/.gitkeep"
  echo "INFO: next recommended steps:"
  echo "  1. make build"
  echo "  2. make up"
  echo "  3. make smoke"
  echo "  4. make serve-up (erst nach gültiger Promotion)"
}

main "$@"
