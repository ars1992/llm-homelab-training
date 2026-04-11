# Makefile for llm-homelab-training
# Purpose:
# - operational lifecycle targets for container workflow
# - reproducible E2E workflow: preflight -> dataset -> train -> eval -> retention
# - default training strategy: continue from latest OK adapter with fallback to fresh short run
#
# Reminder (Paperless references):
# - LoRA (Doc 1848): default path in this MVP
# - SEAL (Doc 1723): later, not part of nightly MVP
# - Watermarking (Doc 1853): later, when sharing adapters
# - Seal-Tools (Doc 1846): later, when tool-use tuning starts

.DEFAULT_GOAL := help

PROJECT_NAME := llm-homelab-training
COMPOSE_FILE := docker/compose.yaml
COMPOSE := docker compose -f $(COMPOSE_FILE)
SERVICE := trainer
BASE_MODEL := facebook/opt-2.7b
NIGHTLY_CONFIG := configs/nightly.yaml
# Hilfsfunktion: liest einen Wert aus NIGHTLY_CONFIG via scripts/cfg.py
# Verwendung: $(call cfg,dotted.key)
cfg = $(shell python3 scripts/cfg.py $(NIGHTLY_CONFIG) $(1))

SMOKE_DATASET := data/datasets/smoke_train.jsonl
SMOKE_STATE_DIR := data/runs/smoke
SMOKE_RUN_ID_FILE := $(SMOKE_STATE_DIR)/LATEST_RUN_ID
SMOKE_REPORT := $(SMOKE_STATE_DIR)/report.txt

REALRUN_CONFIG := configs/train_lora_3b_k80_short.yaml
REALRUN_DATASET := data/datasets/train.jsonl
RUN_STATE_DIR := data/runs
LATEST_REALRUN_ID_FILE := $(RUN_STATE_DIR)/LATEST_REALRUN_ID
LATEST_OK_ADAPTER_ID_FILE := $(RUN_STATE_DIR)/LATEST_OK_ADAPTER_ID
LATEST_OK_ADAPTER_PATH_FILE := $(RUN_STATE_DIR)/LATEST_OK_ADAPTER_PATH
LATEST_PROMOTION_SUMMARY_FILE := $(RUN_STATE_DIR)/LATEST_PROMOTION_SUMMARY.json

VAL_REG_CONFIG := configs/datasets/val_regression.yaml
VAL_REG_DATASET := data/datasets/val.jsonl
VAL_REG_OUTPUT_ROOT := data/evals
PROMOTE_MIN_PASS_RATE_EXACT_OPENBOOK := $(call cfg,promotion.pass_rate_exact_openbook_min)
PROMOTE_MIN_AVG_COVERAGE_RUNBOOK_OPENBOOK := $(call cfg,promotion.avg_coverage_runbook_openbook_min)
SERVE_COMPOSE_FILE := docker/compose.serve.yaml
SERVE_COMPOSE := docker compose -f $(SERVE_COMPOSE_FILE)
SERVE_PORT ?= 8901
SERVE_HEALTH_PATH ?= /health
SERVE_NAME := serve
SERVE_SMOKE_OUTPUT_DIR := data/evals

VAULT_DOCS_ROOT := /vault/15_Dokumentation
VAULT_PREPARE_OUTPUT := data/datasets/train.jsonl
VAULT_PREPARE_REPORT := data/datasets/prepare_report.json

RETENTION_KEEP := $(call cfg,retention.keep)
NIGHTLY_APPLY_CPU_LIMIT := $(call cfg,nightly.apply_cpu_limit)

# Supplemental dataset paths (augmentation for C1/C3)
EXACT_EXTRACTION_VAULT := /vault/exact_extraction
EXACT_EXTRACTION_OUTPUT := data/datasets/exact_extraction_samples.jsonl
EXACT_EXTRACTION_REPORT := data/datasets/exact_extraction_report.json
RUNBOOK_SAMPLES := data/datasets/runbook_samples.jsonl
RUNBOOK_SAMPLES_REPORT := data/datasets/runbook_samples.report.json
VAL_VALIDATE_REPORT := data/datasets/val_validate_report.json

SELF_EDITS_RUNS_ROOT := data/self_edits/runs
SELF_EDITS_EXPORT_ACCEPTED := data/training/derived/self_edits.accepted.jsonl
SELF_EDITS_MAX_SOURCES := $(call cfg,self_edits.max_sources)
SELF_EDITS_CANDIDATES_PER_SOURCE := $(call cfg,self_edits.candidates_per_source)
SELF_EDITS_SEED := $(call cfg,self_edits.seed)
SELF_EDITS_VALIDATE_RUN_ID ?=
SELF_EDITS_MERGE_ENABLE := $(call cfg,self_edits.merge_enable)
SELF_EDITS_MERGE_CAP := $(call cfg,self_edits.merge_cap)
SELF_EDITS_MERGE_CAPPED := data/training/derived/self_edits.accepted.capped.jsonl

RUN_LOCK_FILE := $(RUN_STATE_DIR)/LOCK
SWAP_GATE_SWAPFREE_MIN_KB := $(call cfg,swap_gate.swapfree_min_kb)
SWAP_GATE_MEM_MIN_KB := $(call cfg,swap_gate.mem_min_kb)

.PHONY: help \
	preflight check-docker check-gpu-host check-gpu-container check-paths gpu-info \
	build up limit-cpu swap-reset check-single-flight lock-status lock-clear swap-gate-train swap-gate-eval down restart ps logs shell \
	ensure-data-dirs \
	train eval eval-val validate-val prepare-dataset prepare-dataset-vault \
	prepare-dataset-exact runbook-samples-generate prepare-dataset-augmented \
	self-edits self-edits-generate self-edits-validate tensorboard \
	real-run-short real-run-continue run-status nightly-run promote-latest-ok \
	serve-up serve-down serve-logs serve-health serve-reload serve-test \
	smoke smoke-dataset smoke-train smoke-infer smoke-report \
	retention-clean clean-smoke clean-data reset-runtime

help:
	@echo "Targets:"
	@echo "  preflight                  - Verify local prerequisites (docker, gpu, paths)"
	@echo "  build                      - Build trainer image"
	@echo "  up                         - Start trainer container in background"
	@echo "  limit-cpu                  - Optional: apply docker CPU cap (cpus=6) to trainer container"
	@echo "  swap-reset                 - Reset host swap when MemAvailable > ~6GB (sudo swapoff/swapon)"
	@echo "  check-single-flight        - Abort if another train/eval workflow is already running"
	@echo "  lock-status                - Show current lock file state"
	@echo "  lock-clear                 - Remove lock file (manual recovery only)"
	@echo "  swap-gate-train            - Swap gate for training (tries swap-reset, aborts on low SwapFree)"
	@echo "  swap-gate-eval             - Swap gate for eval (tries swap-reset, exits 2 if still low)"
	@echo "  down                       - Stop/remove trainer container"
	@echo "  restart                    - Restart trainer container"
	@echo "  ps                         - Show compose service status"
	@echo "  logs                       - Tail service logs"
	@echo "  shell                      - Open shell inside trainer container"
	@echo "  gpu-info                   - Show nvidia-smi inside container"
	@echo "  ensure-data-dirs           - Create expected local data directories"
	@echo "  train                      - Start LoRA training using default config"
	@echo "  eval                       - Run eval script on dataset"
	@echo "  eval-val                   - Run expected_contains regression checks (non-blocking, RC=0)"
	@echo "  validate-val               - Validate val.jsonl for structural integrity (host-side, no container)"
	@echo "  prepare-dataset            - Validate/normalize dataset JSONL"
	@echo "  prepare-dataset-vault      - Build train.jsonl from /vault/15_Dokumentation markdown files"
	@echo "  prepare-dataset-exact      - Extract exact_extraction samples from /vault/exact_extraction MD files"
	@echo "  prepare-dataset-augmented  - Vault dataset + append exact_extraction + runbook samples -> train.jsonl"
	@echo "  runbook-samples-generate   - Generate deterministic runbook_samples.jsonl from val-rb-* cases"
	@echo "  self-edits                 - Backward-compatible alias to self-edits-generate"
	@echo "  self-edits-generate        - Run deterministic SEAL-MVP generation and export accepted derived samples"
	@echo "  self-edits-validate        - Validate SEAL-MVP run artifacts (set SELF_EDITS_VALIDATE_RUN_ID=<run_id>)"
	@echo "  (augmented merge)          - Uses capped self-edits export ($(SELF_EDITS_MERGE_CAP)) with priority before vault/runbook"
	@echo "  tensorboard                - Start tensorboard in container (port 6006)"
	@echo "  real-run-short             - Fresh short run (new adapter from base model)"
	@echo "  real-run-continue          - Continue from latest OK adapter; fallback to fresh short run"
	@echo "  run-status                 - Show latest real-run id and artifact status"
	@echo "  promote-latest-ok          - Promote latest real run to LATEST_OK pointer if eval thresholds pass"
	@echo "  nightly-run                - preflight -> validate-val -> prepare-dataset-augmented -> train -> eval -> promote -> serve restart -> retention-clean"
	@echo "  serve-up                   - Start serving stack (OpenAI-compatible API) on configured port"
	@echo "  serve-down                 - Stop serving stack"
	@echo "  serve-logs                 - Tail serving logs"
	@echo "  serve-health               - Query serving health endpoint"
	@echo "  serve-reload               - Reload serving model from LATEST_OK pointer"
	@echo "  serve-test                 - Run standardized serving smoke prompts and write report to data/evals"
	@echo "  smoke                      - End-to-end smoke workflow (check/build/up/train/infer/report)"
	@echo "  retention-clean            - Keep only latest N run-like dirs in models/logs/evals (default N=3)"
	@echo "  clean-smoke                - Remove smoke outputs"
	@echo "  clean-data                 - Remove generated datasets/evals/logs/models and reset runtime pointers"
	@echo "  reset-runtime              - Stop serving/training containers and reset runtime state for fresh E2E tests"

preflight: check-docker check-gpu-host check-paths ensure-data-dirs

check-docker:
	@command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found in PATH"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose plugin not available"; exit 1; }
	@echo "OK: docker + compose available"

check-gpu-host:
	@./scripts/check_gpu.sh --host-only --compose-file $(COMPOSE_FILE) --service $(SERVICE)

check-paths:
	@test -f $(COMPOSE_FILE) || { echo "ERROR: missing $(COMPOSE_FILE)"; exit 1; }
	@test -f $(SERVE_COMPOSE_FILE) || { echo "ERROR: missing $(SERVE_COMPOSE_FILE)"; exit 1; }
	@test -f docker/Dockerfile || { echo "ERROR: missing docker/Dockerfile"; exit 1; }
	@test -f configs/train_lora_3b_k80.yaml || { echo "ERROR: missing configs/train_lora_3b_k80.yaml"; exit 1; }
	@test -f src/scripts/train_lora.py || { echo "ERROR: missing src/scripts/train_lora.py"; exit 1; }
	@test -f src/serve/app.py || { echo "ERROR: missing src/serve/app.py"; exit 1; }
	@echo "OK: required project files present"

ensure-data-dirs:
	@mkdir -p data/datasets data/models data/logs data/evals $(SMOKE_STATE_DIR) $(RUN_STATE_DIR) .cache .cache/huggingface .cache/huggingface/datasets .cache/huggingface/transformers
	@touch $(LATEST_OK_ADAPTER_ID_FILE)
	@if [ ! -f $(LATEST_OK_ADAPTER_PATH_FILE) ]; then echo "data/models/<run-id>" > $(LATEST_OK_ADAPTER_PATH_FILE); fi
	@echo "OK: ensured data directories"

build: check-docker check-paths
	@echo "##############"
	@echo "### STEP build: trainer image build"
	@echo "##############"
	@$(COMPOSE) build

up: ensure-data-dirs
	@echo "##############"
	@echo "### STEP up: trainer stack start"
	@echo "##############"
	@$(COMPOSE) up -d

limit-cpu: up
	@docker update --cpus=6 llm-homelab-trainer >/dev/null
	@echo "OK: applied CPU limit (cpus=6) to llm-homelab-trainer"

swap-reset:
	@set -e; \
	if [ ! -r /proc/meminfo ]; then \
		echo "WARN: /proc/meminfo not available on this host. swap-reset skipped."; \
		exit 0; \
	fi; \
	MEM_AVAIL_KB=$$(awk '/MemAvailable:/ {print $$2}' /proc/meminfo); \
	THRESHOLD_KB=6000000; \
	echo "INFO: MemAvailable_kB=$$MEM_AVAIL_KB threshold_kB=$$THRESHOLD_KB"; \
	if [ "$$MEM_AVAIL_KB" -gt "$$THRESHOLD_KB" ]; then \
		echo "INFO: resetting swap (swapoff/swapon)"; \
		sudo swapoff -a && sudo swapon -a; \
		echo "OK: swap reset completed"; \
	else \
		echo "WARN: MemAvailable too low for safe swap reset. Skipping."; \
	fi

check-single-flight:
	@set -e; \
	if [ -f $(RUN_LOCK_FILE) ]; then \
		echo "ERROR: already_running lock_file=$(RUN_LOCK_FILE)"; \
		cat $(RUN_LOCK_FILE) 2>/dev/null || true; \
		exit 1; \
	fi; \
	echo "OK: no active lock"

lock-status:
	@set -e; \
	if [ -f $(RUN_LOCK_FILE) ]; then \
		echo "LOCK=active file=$(RUN_LOCK_FILE)"; \
		cat $(RUN_LOCK_FILE) 2>/dev/null || true; \
	else \
		echo "LOCK=none"; \
	fi

lock-clear:
	@rm -f $(RUN_LOCK_FILE)
	@echo "OK: lock cleared ($(RUN_LOCK_FILE))"

swap-gate-train:
	@set -e; \
	if [ ! -r /proc/meminfo ]; then \
		echo "WARN: /proc/meminfo unavailable; skipping swap gate (train)"; \
		exit 0; \
	fi; \
	MEM_AVAIL_KB=$$(awk '/MemAvailable:/ {print $$2}' /proc/meminfo); \
	SWAP_FREE_KB=$$(awk '/SwapFree:/ {print $$2}' /proc/meminfo); \
	echo "INFO: swap-gate-train MemAvailable_kB=$$MEM_AVAIL_KB SwapFree_kB=$$SWAP_FREE_KB"; \
	if [ "$$MEM_AVAIL_KB" -lt "$(SWAP_GATE_MEM_MIN_KB)" ]; then \
		echo "ERROR: swap_gated train aborted (MemAvailable below threshold)"; \
		exit 1; \
	fi; \
	if [ "$$SWAP_FREE_KB" -lt "$(SWAP_GATE_SWAPFREE_MIN_KB)" ]; then \
		echo "WARN: low SwapFree before train; attempting swap-reset"; \
		$(MAKE) swap-reset; \
		MEM_AVAIL_KB=$$(awk '/MemAvailable:/ {print $$2}' /proc/meminfo); \
		SWAP_FREE_KB=$$(awk '/SwapFree:/ {print $$2}' /proc/meminfo); \
		echo "INFO: swap-gate-train post-reset MemAvailable_kB=$$MEM_AVAIL_KB SwapFree_kB=$$SWAP_FREE_KB"; \
		if [ "$$MEM_AVAIL_KB" -lt "$(SWAP_GATE_MEM_MIN_KB)" ]; then \
			echo "ERROR: swap_gated train aborted (MemAvailable below threshold after reset)"; \
			exit 1; \
		fi; \
		if [ "$$SWAP_FREE_KB" -lt "$(SWAP_GATE_SWAPFREE_MIN_KB)" ]; then \
			echo "ERROR: swap_gated train aborted (SwapFree still low)"; \
			exit 1; \
		fi; \
	fi; \
	echo "OK: swap-gate-train passed"

swap-gate-eval:
	@set -e; \
	if [ ! -r /proc/meminfo ]; then \
		echo "WARN: /proc/meminfo unavailable; skipping swap gate (eval)"; \
		exit 0; \
	fi; \
	MEM_AVAIL_KB=$$(awk '/MemAvailable:/ {print $$2}' /proc/meminfo); \
	SWAP_FREE_KB=$$(awk '/SwapFree:/ {print $$2}' /proc/meminfo); \
	echo "INFO: swap-gate-eval MemAvailable_kB=$$MEM_AVAIL_KB SwapFree_kB=$$SWAP_FREE_KB"; \
	if [ "$$MEM_AVAIL_KB" -lt "$(SWAP_GATE_MEM_MIN_KB)" ]; then \
		echo "WARN: swap_gated eval skipped (MemAvailable below threshold)"; \
		exit 2; \
	fi; \
	if [ "$$SWAP_FREE_KB" -lt "$(SWAP_GATE_SWAPFREE_MIN_KB)" ]; then \
		echo "WARN: low SwapFree before eval; attempting swap-reset"; \
		$(MAKE) swap-reset; \
		MEM_AVAIL_KB=$$(awk '/MemAvailable:/ {print $$2}' /proc/meminfo); \
		SWAP_FREE_KB=$$(awk '/SwapFree:/ {print $$2}' /proc/meminfo); \
		echo "INFO: swap-gate-eval post-reset MemAvailable_kB=$$MEM_AVAIL_KB SwapFree_kB=$$SWAP_FREE_KB"; \
		if [ "$$MEM_AVAIL_KB" -lt "$(SWAP_GATE_MEM_MIN_KB)" ]; then \
			echo "WARN: swap_gated eval skipped (MemAvailable below threshold after reset)"; \
			exit 2; \
		fi; \
		if [ "$$SWAP_FREE_KB" -lt "$(SWAP_GATE_SWAPFREE_MIN_KB)" ]; then \
			echo "WARN: swap_gated eval skipped (SwapFree still low)"; \
			exit 2; \
		fi; \
	fi; \
	echo "OK: swap-gate-eval passed"

check-gpu-container: up
	@./scripts/check_gpu.sh --container-only --compose-file $(COMPOSE_FILE) --service $(SERVICE)

down:
	@$(COMPOSE) down

restart:
	@$(COMPOSE) restart

ps:
	@$(COMPOSE) ps

logs:
	@$(COMPOSE) logs -f $(SERVICE)

shell:
	@$(COMPOSE) exec $(SERVICE) bash

gpu-info:
	@$(COMPOSE) exec $(SERVICE) nvidia-smi

train: up
	@$(COMPOSE) exec $(SERVICE) python src/scripts/train_lora.py \
		--config configs/train_lora_3b_k80.yaml \
		--dataset data/datasets/train.jsonl

eval: up
	@$(COMPOSE) exec $(SERVICE) python src/scripts/eval.py \
		--dataset data/datasets/val.jsonl \
		--base-model $(BASE_MODEL) \
		--output-dir data/evals/manual-eval

# Non-blocking by policy: writes report if possible, but never fails E2E.
eval-val: up
	@echo "##############"
	@echo "### STEP eval-val: regression evaluation"
	@echo "##############"
	@set +e; \
	if [ -f $(RUN_LOCK_FILE) ]; then \
		echo "ERROR: already_running lock_file=$(RUN_LOCK_FILE)"; \
		cat $(RUN_LOCK_FILE) 2>/dev/null || true; \
		exit 1; \
	fi; \
	if [ ! -f $(LATEST_REALRUN_ID_FILE) ]; then \
		echo "WARN: missing $(LATEST_REALRUN_ID_FILE). Skipping eval-val."; \
		exit 0; \
	fi; \
	RUN_ID=$$(cat $(LATEST_REALRUN_ID_FILE)); \
	ADAPTER_PATH=data/models/$$RUN_ID; \
	if [ ! -f $$ADAPTER_PATH/adapter_config.json ]; then \
		echo "WARN: missing adapter at $$ADAPTER_PATH. Skipping eval-val."; \
		exit 0; \
	fi; \
	$(MAKE) swap-gate-eval; \
	GATE_RC=$$?; \
	if [ $$GATE_RC -eq 2 ]; then \
		echo "WARN: eval-val skipped by swap gate."; \
		exit 0; \
	fi; \
	if [ $$GATE_RC -ne 0 ]; then \
		echo "WARN: eval-val swap gate failed (RC=$$GATE_RC). Skipping."; \
		exit 0; \
	fi; \
	printf 'pid=%s\nstart_ts=%s\ncommand=%s\n' "$$$$" "$$(date -u +%Y-%m-%dT%H:%M:%SZ)" "eval-val" > $(RUN_LOCK_FILE); \
	trap 'rm -f $(RUN_LOCK_FILE)' EXIT INT TERM; \
	EVAL_RUN_ID=val-$$RUN_ID-$$(date -u +%Y%m%dT%H%M%SZ); \
	echo "EVAL_VAL_RUN_ID=$$EVAL_RUN_ID"; \
	echo "$$EVAL_RUN_ID" > $(RUN_STATE_DIR)/LATEST_EVAL_RUN_ID; \
	./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/eval_val.py \
		--config $(VAL_REG_CONFIG) \
		--dataset $(VAL_REG_DATASET) \
		--base-model $(BASE_MODEL) \
		--adapter-path $$ADAPTER_PATH \
		--run-id $$EVAL_RUN_ID \
		--output-dir $(VAL_REG_OUTPUT_ROOT); \
	RC=$$?; \
	rm -f $(RUN_LOCK_FILE); \
	trap - EXIT INT TERM; \
	if [ $$RC -ne 0 ]; then \
		echo "WARN: eval-val returned non-zero (RC=$$RC). Continuing by policy."; \
		exit 0; \
	fi; \
	if [ ! -f $(VAL_REG_OUTPUT_ROOT)/$$EVAL_RUN_ID/val_report.json ]; then \
		echo "WARN: missing val_report.json for $$EVAL_RUN_ID. Continuing by policy."; \
		exit 0; \
	fi; \
	echo "OK: eval-val finished for $$EVAL_RUN_ID"; \
	exit 0

prepare-dataset: up
	@./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/prepare_dataset.py \
		--input data/datasets/raw.jsonl \
		--output data/datasets/train.jsonl

prepare-dataset-vault: up
	@./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/prepare_dataset.py \
		--mode vault_md \
		--vault-root $(VAULT_DOCS_ROOT) \
		--output $(VAULT_PREPARE_OUTPUT) \
		--max-files 500 \
		--max-samples 5000 \
		--redact-secrets true \
		--report $(VAULT_PREPARE_REPORT)

# B1: Validate val.jsonl structural integrity (host-side, no container required).
# Exit 0 = clean; Exit 1 = structural errors found. src/scripts/validate_val.py
validate-val:
	@python3 src/scripts/validate_val.py \
		--dataset $(VAL_REG_DATASET) \
		--verbose \
		--report $(VAL_VALIDATE_REPORT)

# C2: Deterministic runbook sample generation from val-rb-* cases.
# Host-side by design for reproducibility against committed val.jsonl.
runbook-samples-generate:
	@python3 src/scripts/generate_runbook_samples.py \
		--val-jsonl $(VAL_REG_DATASET) \
		--output-jsonl $(RUNBOOK_SAMPLES) \
		--variants-per-case $(call cfg,runbook.variants_per_case) \
		--seed $(call cfg,runbook.seed) \
		--report-json $(RUNBOOK_SAMPLES_REPORT)

# C1: Extract exact_extraction samples from MD triplets (## Instruction/Input/Output).
# Graceful: skips with WARN if /vault/exact_extraction is not mounted.
prepare-dataset-exact: up
	@set -e; \
	if $(COMPOSE) exec -T $(SERVICE) test -d $(EXACT_EXTRACTION_VAULT) 2>/dev/null; then \
		echo "INFO: ExactExtraction vault found at $(EXACT_EXTRACTION_VAULT) — extracting samples"; \
		./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/prepare_dataset.py \
			--mode exact_extraction \
			--vault-root $(EXACT_EXTRACTION_VAULT) \
			--output $(EXACT_EXTRACTION_OUTPUT) \
			--max-files 500 \
			--max-samples 1000 \
			--report $(EXACT_EXTRACTION_REPORT); \
	else \
		echo "WARN: ExactExtraction vault not mounted at $(EXACT_EXTRACTION_VAULT). Skipping extraction."; \
		echo "INFO: Seed file $(EXACT_EXTRACTION_OUTPUT) will be used if it exists (checked during augment step)."; \
	fi

# C1+C2+C3+C4: Augmented dataset build:
#   1. Vault markdown extraction -> data/datasets/train_vault.jsonl
#   2. Exact extraction samples from MD triplets (if vault mounted, else seed file used)
#   3. Deterministic runbook sample generation -> data/datasets/runbook_samples.jsonl
#   4. Deterministic capped self-edits export -> data/training/derived/self_edits.accepted.capped.jsonl
#   5. Merge self-edits(capped, prioritized) + vault + exact_extraction + runbook -> train.jsonl (deduplicated)
# Use this instead of prepare-dataset-vault when supplemental samples should be included.
prepare-dataset-augmented: up
	@echo "##############"
	@echo "### STEP prepare-dataset-augmented: build merged train dataset"
	@echo "##############"
	@set -e; \
	echo "INFO: Step 1/5 — Vault markdown extraction -> train_vault.jsonl"; \
	./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/prepare_dataset.py \
		--mode vault_md \
		--vault-root $(VAULT_DOCS_ROOT) \
		--output data/datasets/train_vault.jsonl \
		--max-files 500 \
		--max-samples 4000 \
		--redact-secrets true \
		--report data/datasets/prepare_vault_report.json; \
	echo "INFO: Step 2/5 — Exact extraction samples (vault or seed)"; \
	$(MAKE) prepare-dataset-exact; \
	echo "INFO: Step 3/5 — Generate deterministic runbook samples"; \
	$(MAKE) runbook-samples-generate; \
	echo "INFO: Step 4/5 — Prepare deterministic capped self-edits export (cap=$(SELF_EDITS_MERGE_CAP), enable=$(SELF_EDITS_MERGE_ENABLE))"; \
	mkdir -p data/training/derived; \
	: > $(SELF_EDITS_MERGE_CAPPED); \
	if [ "$(SELF_EDITS_MERGE_ENABLE)" = "1" ] && [ -f $(SELF_EDITS_EXPORT_ACCEPTED) ]; then \
		python3 -c "from pathlib import Path; src=Path('$(SELF_EDITS_EXPORT_ACCEPTED)'); dst=Path('$(SELF_EDITS_MERGE_CAPPED)'); cap=int('$(SELF_EDITS_MERGE_CAP)'); lines=[ln for ln in src.read_text(encoding='utf-8').splitlines() if ln.strip()]; dst.write_text('\n'.join(lines[:cap]) + ('\n' if lines[:cap] else ''), encoding='utf-8')"; \
		echo "INFO: self-edits capped export prepared -> $(SELF_EDITS_MERGE_CAPPED)"; \
	else \
		echo "INFO: self-edits merge disabled or export missing; using empty $(SELF_EDITS_MERGE_CAPPED)"; \
	fi; \
	echo "INFO: Step 5/5 — Merging all sources with deterministic priority weighting -> train.jsonl"; \
	./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/merge_datasets.py \
		--sources \
			$(SELF_EDITS_MERGE_CAPPED) \
			data/datasets/train_vault.jsonl \
			$(EXACT_EXTRACTION_OUTPUT) \
			$(RUNBOOK_SAMPLES) \
		--output $(VAULT_PREPARE_OUTPUT) \
		--max-samples 5000 \
		--report data/datasets/merge_report.json \
		--validate-schema; \
	echo "OK: prepare-dataset-augmented completed -> $(VAULT_PREPARE_OUTPUT)"

self-edits: self-edits-generate

self-edits-generate: up
	@echo "##############"
	@echo "### STEP self-edits-generate: deterministic SEAL-MVP generation"
	@echo "##############"
	@set -e; \
	RUN_ID=self-edit-$$(date -u +%Y%m%dT%H%M%SZ); \
	OUTPUT_DIR=$(SELF_EDITS_RUNS_ROOT)/$$RUN_ID; \
	echo "SELF_EDIT_RUN_ID=$$RUN_ID"; \
	$(COMPOSE) exec -T $(SERVICE) python src/scripts/generate_self_edits.py \
		--mode generate \
		--input-jsonl data/datasets/train.jsonl \
		--output-dir $$OUTPUT_DIR \
		--export-accepted $(SELF_EDITS_EXPORT_ACCEPTED) \
		--max-sources $(SELF_EDITS_MAX_SOURCES) \
		--candidates-per-source $(SELF_EDITS_CANDIDATES_PER_SOURCE) \
		--seed $(SELF_EDITS_SEED); \
	$(COMPOSE) exec -T $(SERVICE) python src/scripts/generate_self_edits.py \
		--mode validate \
		--input-jsonl data/datasets/train.jsonl \
		--output-dir $$OUTPUT_DIR \
		--export-accepted $(SELF_EDITS_EXPORT_ACCEPTED); \
	echo "$$RUN_ID" > $(RUN_STATE_DIR)/LATEST_SELF_EDIT_RUN_ID; \
	echo "OK: self-edits-generate completed run_id=$$RUN_ID"

self-edits-validate: up
	@set -e; \
	if [ -z "$(SELF_EDITS_VALIDATE_RUN_ID)" ]; then \
		if [ -f $(RUN_STATE_DIR)/LATEST_SELF_EDIT_RUN_ID ]; then \
			RUN_ID=$$(cat $(RUN_STATE_DIR)/LATEST_SELF_EDIT_RUN_ID); \
		else \
			echo "ERROR: no run id specified. Set SELF_EDITS_VALIDATE_RUN_ID=<run_id> or run make self-edits-generate first."; \
			exit 1; \
		fi; \
	else \
		RUN_ID="$(SELF_EDITS_VALIDATE_RUN_ID)"; \
	fi; \
	OUTPUT_DIR=$(SELF_EDITS_RUNS_ROOT)/$$RUN_ID; \
	echo "SELF_EDIT_VALIDATE_RUN_ID=$$RUN_ID"; \
	$(COMPOSE) exec -T $(SERVICE) python src/scripts/generate_self_edits.py \
		--mode validate \
		--input-jsonl data/datasets/train.jsonl \
		--output-dir $$OUTPUT_DIR \
		--export-accepted $(SELF_EDITS_EXPORT_ACCEPTED)

tensorboard: up
	@$(COMPOSE) exec $(SERVICE) tensorboard --logdir data/logs --host 0.0.0.0 --port 6006

# Fresh short run (from base model).
real-run-short: preflight up check-gpu-container check-single-flight
	@echo "##############"
	@echo "### STEP real-run-short: fresh training run"
	@echo "##############"
	@set -e; \
	$(MAKE) swap-gate-train; \
	printf 'pid=%s\nstart_ts=%s\ncommand=%s\n' "$$$$" "$$(date -u +%Y-%m-%dT%H:%M:%SZ)" "real-run-short" > $(RUN_LOCK_FILE); \
	trap 'rm -f $(RUN_LOCK_FILE)' EXIT INT TERM; \
	RUN_ID=real-$$(date -u +%Y%m%dT%H%M%SZ); \
	echo "REAL_RUN_ID=$$RUN_ID (fresh)"; \
	./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/train_lora.py \
		--config $(REALRUN_CONFIG) \
		--dataset $(REALRUN_DATASET) \
		--run-id $$RUN_ID; \
	test -f data/models/$$RUN_ID/adapter_config.json || { echo "ERROR: missing adapter_config.json for $$RUN_ID"; exit 1; }; \
	echo "$$RUN_ID" > $(LATEST_REALRUN_ID_FILE); \
	rm -f $(RUN_LOCK_FILE); \
	trap - EXIT INT TERM; \
	echo "OK: real-run-short finished for $$RUN_ID"

# Default mode: continue from latest promoted OK adapter, fallback to fresh short run.
real-run-continue: preflight up check-gpu-container check-single-flight
	@echo "##############"
	@echo "### STEP real-run-continue: continue training from promoted adapter"
	@echo "##############"
	@set -e; \
	$(MAKE) swap-gate-train; \
	printf 'pid=%s\nstart_ts=%s\ncommand=%s\n' "$$$$" "$$(date -u +%Y-%m-%dT%H:%M:%SZ)" "real-run-continue" > $(RUN_LOCK_FILE); \
	trap 'rm -f $(RUN_LOCK_FILE)' EXIT INT TERM; \
	PREV_RUN_ID=""; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then \
		CANDIDATE=$$(cat $(LATEST_OK_ADAPTER_ID_FILE)); \
		if [ -n "$$CANDIDATE" ] && [ -f data/models/$$CANDIDATE/adapter_config.json ]; then \
			PREV_RUN_ID="$$CANDIDATE"; \
		fi; \
	fi; \
	if [ -z "$$PREV_RUN_ID" ]; then \
		echo "WARN: no promoted OK adapter found. Fallback -> real-run-short"; \
		rm -f $(RUN_LOCK_FILE); \
		trap - EXIT INT TERM; \
		$(MAKE) real-run-short; \
		exit 0; \
	fi; \
	if ! $(COMPOSE) exec -T $(SERVICE) python src/scripts/train_lora.py --help 2>/dev/null | grep -q -- "--adapter-path"; then \
		echo "WARN: train_lora.py has no --adapter-path support. Fallback -> real-run-short"; \
		rm -f $(RUN_LOCK_FILE); \
		trap - EXIT INT TERM; \
		$(MAKE) real-run-short; \
		exit 0; \
	fi; \
	RUN_ID=real-$$(date -u +%Y%m%dT%H%M%SZ); \
	echo "REAL_RUN_ID=$$RUN_ID (continue from $$PREV_RUN_ID)"; \
	./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/train_lora.py \
		--config $(REALRUN_CONFIG) \
		--dataset $(REALRUN_DATASET) \
		--adapter-path data/models/$$PREV_RUN_ID \
		--run-id $$RUN_ID; \
	test -f data/models/$$RUN_ID/adapter_config.json || { echo "ERROR: missing adapter_config.json for $$RUN_ID"; exit 1; }; \
	echo "$$RUN_ID" > $(LATEST_REALRUN_ID_FILE); \
	rm -f $(RUN_LOCK_FILE); \
	trap - EXIT INT TERM; \
	echo "OK: real-run-continue finished for $$RUN_ID"

run-status:
	@set -e; \
	if [ ! -f $(LATEST_REALRUN_ID_FILE) ]; then \
		echo "ERROR: missing $(LATEST_REALRUN_ID_FILE). Run 'make real-run-short' first."; \
		exit 1; \
	fi; \
	RUN_ID=$$(cat $(LATEST_REALRUN_ID_FILE)); \
	echo "LATEST_REAL_RUN_ID=$$RUN_ID"; \
	echo "model_dir=data/models/$$RUN_ID"; \
	echo "log_dir=data/logs/$$RUN_ID"; \
	test -f data/models/$$RUN_ID/adapter_config.json && echo "adapter_config.json: OK" || { echo "adapter_config.json: MISSING"; exit 1; }; \
	if [ -f data/models/$$RUN_ID/final_metrics.json ]; then \
		echo "final_metrics.json:"; \
		cat data/models/$$RUN_ID/final_metrics.json; \
	else \
		echo "final_metrics.json: not found (training may have failed early)"; \
	fi

promote-latest-ok:
	@echo "##############"
	@echo "### STEP promote-latest-ok: evaluate promotion decision"
	@echo "##############"
	@echo ""
	@set -e; \
	if [ ! -f $(LATEST_REALRUN_ID_FILE) ]; then \
		echo "WARN: missing $(LATEST_REALRUN_ID_FILE). Promotion skipped."; \
		exit 0; \
	fi; \
	RUN_ID=$$(cat $(LATEST_REALRUN_ID_FILE)); \
	if [ -z "$$RUN_ID" ]; then \
		echo "WARN: empty latest real run id. Promotion skipped."; \
		exit 0; \
	fi; \
	EVAL_RUN_ID=""; \
	if [ -f $(RUN_STATE_DIR)/LATEST_EVAL_RUN_ID ]; then \
		CANDIDATE_EVAL_ID=$$(cat $(RUN_STATE_DIR)/LATEST_EVAL_RUN_ID); \
		if [ -f $(VAL_REG_OUTPUT_ROOT)/$$CANDIDATE_EVAL_ID/val_report.json ]; then \
			case "$$CANDIDATE_EVAL_ID" in \
				val-$$RUN_ID-*) EVAL_RUN_ID="$$CANDIDATE_EVAL_ID" ;; \
			esac; \
		fi; \
	fi; \
	if [ -z "$$EVAL_RUN_ID" ]; then \
		EVAL_RUN_ID=$$(find $(VAL_REG_OUTPUT_ROOT) -mindepth 1 -maxdepth 1 -type d -name "val-$$RUN_ID-*" -print 2>/dev/null | sed 's#^$(VAL_REG_OUTPUT_ROOT)/##' | sort -r | head -n 1); \
	fi; \
	if [ -z "$$EVAL_RUN_ID" ]; then \
		echo "WARN: no eval run found for $$RUN_ID. Promotion skipped."; \
		exit 0; \
	fi; \
	REPORT_PATH=$(VAL_REG_OUTPUT_ROOT)/$$EVAL_RUN_ID/val_report.json; \
	if [ ! -f $$REPORT_PATH ]; then \
		echo "WARN: missing $$REPORT_PATH. Promotion skipped."; \
		exit 0; \
	fi; \
	PROMOTE_RESULT=$$(python3 -c "import json; p='$$REPORT_PATH'; data=json.load(open(p,'r',encoding='utf-8')); s=data.get('summary',{}); pass_exact=float(s.get('pass_rate_exact_openbook',0.0)); cov_runbook=float(s.get('avg_coverage_runbook_openbook',0.0)); pass_ok=pass_exact >= float('$(PROMOTE_MIN_PASS_RATE_EXACT_OPENBOOK)'); cov_ok=cov_runbook >= float('$(PROMOTE_MIN_AVG_COVERAGE_RUNBOOK_OPENBOOK)'); ok=(pass_ok and cov_ok); print('PROMOTE' if ok else 'KEEP'); print(pass_exact); print(cov_runbook); print('1' if pass_ok else '0'); print('1' if cov_ok else '0')"); \
	DECISION=$$(printf '%s\n' "$$PROMOTE_RESULT" | sed -n '1p'); \
	PASS_EXACT=$$(printf '%s\n' "$$PROMOTE_RESULT" | sed -n '2p'); \
	COVERAGE_RUNBOOK=$$(printf '%s\n' "$$PROMOTE_RESULT" | sed -n '3p'); \
	PASS_EXACT_OK=$$(printf '%s\n' "$$PROMOTE_RESULT" | sed -n '4p'); \
	COVERAGE_RUNBOOK_OK=$$(printf '%s\n' "$$PROMOTE_RESULT" | sed -n '5p'); \
	PREV_OK_ID=""; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then PREV_OK_ID=$$(cat $(LATEST_OK_ADAPTER_ID_FILE)); fi; \
	if [ "$$DECISION" = "PROMOTE" ]; then \
		echo "$$RUN_ID" > $(LATEST_OK_ADAPTER_ID_FILE); \
		echo "data/models/$$RUN_ID" > $(LATEST_OK_ADAPTER_PATH_FILE); \
		python3 -c "import json; data={'run_id':'$$RUN_ID','eval_run_id':'$$EVAL_RUN_ID','decision':'promoted','previous_ok_run_id':'$$PREV_OK_ID','new_ok_run_id':'$$RUN_ID','thresholds':{'pass_rate_exact_openbook_min':float('$(PROMOTE_MIN_PASS_RATE_EXACT_OPENBOOK)'),'avg_coverage_runbook_openbook_min':float('$(PROMOTE_MIN_AVG_COVERAGE_RUNBOOK_OPENBOOK)')},'observed':{'pass_rate_exact_openbook':float('$$PASS_EXACT'),'avg_coverage_runbook_openbook':float('$$COVERAGE_RUNBOOK')}}; open('$(LATEST_PROMOTION_SUMMARY_FILE)','w',encoding='utf-8').write(json.dumps(data,ensure_ascii=False,indent=2))"; \
		echo "PROMOTED: $$RUN_ID"; \
	else \
		python3 -c "import json; data={'run_id':'$$RUN_ID','eval_run_id':'$$EVAL_RUN_ID','decision':'kept_previous','previous_ok_run_id':'$$PREV_OK_ID','new_ok_run_id':'$$PREV_OK_ID','thresholds':{'pass_rate_exact_openbook_min':float('$(PROMOTE_MIN_PASS_RATE_EXACT_OPENBOOK)'),'avg_coverage_runbook_openbook_min':float('$(PROMOTE_MIN_AVG_COVERAGE_RUNBOOK_OPENBOOK)')},'observed':{'pass_rate_exact_openbook':float('$$PASS_EXACT'),'avg_coverage_runbook_openbook':float('$$COVERAGE_RUNBOOK')}}; open('$(LATEST_PROMOTION_SUMMARY_FILE)','w',encoding='utf-8').write(json.dumps(data,ensure_ascii=False,indent=2))"; \
		echo "KEPT_PREVIOUS_OK: $$PREV_OK_ID (candidate $$RUN_ID below thresholds)"; \
	fi; \
	echo ""; \
	echo "PROMOTION REPORT"; \
	echo "  run_id: $$RUN_ID"; \
	echo "  eval_run_id: $$EVAL_RUN_ID"; \
	echo "  decision: $$DECISION"; \
	echo "  exact_openbook pass_rate IST=$$PASS_EXACT SOLL>=$(PROMOTE_MIN_PASS_RATE_EXACT_OPENBOOK) ok=$$PASS_EXACT_OK"; \
	echo "  runbook_openbook avg_coverage IST=$$COVERAGE_RUNBOOK SOLL>=$(PROMOTE_MIN_AVG_COVERAGE_RUNBOOK_OPENBOOK) ok=$$COVERAGE_RUNBOOK_OK"; \
	echo "  previous_ok_run_id: $$PREV_OK_ID"; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then \
		echo "  new_ok_run_id: $$(cat $(LATEST_OK_ADAPTER_ID_FILE))"; \
	fi; \
	echo ""

serve-up:
	@echo "##############"
	@echo "### STEP serve-up: serving stack build/start"
	@echo "##############"
	@$(SERVE_COMPOSE) up -d --build

serve-down:
	@$(SERVE_COMPOSE) down

serve-logs:
	@$(SERVE_COMPOSE) logs -f $(SERVE_NAME)

serve-health:
	@echo "##############"
	@echo "### STEP serve-health: query serving health endpoint"
	@echo "##############"
	@curl -fsS http://127.0.0.1:$(SERVE_PORT)$(SERVE_HEALTH_PATH)

serve-reload:
	@curl -fsS -X POST http://127.0.0.1:$(SERVE_PORT)/reload

serve-test:
	@echo "##############"
	@echo "### STEP serve-test: standardized serving smoke prompts"
	@echo "##############"
	@OUT_DIR=$(SERVE_SMOKE_OUTPUT_DIR) bash ./scripts/serve_smoke.sh

# Orchestrator:
# 1) preflight
# 2) lock-status
# 3) validate-val
# 4) self-edits-generate (wenn self_edits.generate_in_nightly=true in configs/nightly.yaml)
# 5) prepare-dataset-augmented
# 6) continue from LATEST_OK, else fresh short run
# 7) eval-val
# 8) promote-latest-ok
# 9) restart serve only if promoted
# 10) retention-clean
nightly-run: preflight validate-val check-single-flight
	@echo "##############"
	@echo "### STEP nightly-run: full automated pipeline"
	@echo "##############"
	@echo ""
	@set -e; \
	$(MAKE) lock-status; \
	$(MAKE) swap-gate-eval; \
	SELF_EDITS_NIGHTLY=$$(python3 scripts/cfg.py $(NIGHTLY_CONFIG) self_edits.generate_in_nightly); \
	if [ "$$SELF_EDITS_NIGHTLY" = "True" ] || [ "$$SELF_EDITS_NIGHTLY" = "true" ] || [ "$$SELF_EDITS_NIGHTLY" = "1" ]; then \
		echo "INFO: nightly-run self-edits-generate (self_edits.generate_in_nightly=true)"; \
		$(MAKE) self-edits-generate; \
	else \
		echo "INFO: nightly-run self-edits-generate uebersprungen (self_edits.generate_in_nightly=false)"; \
	fi; \
	$(MAKE) prepare-dataset-augmented; \
	if [ "$(NIGHTLY_APPLY_CPU_LIMIT)" = "1" ]; then \
		$(MAKE) limit-cpu; \
	else \
		echo "INFO: nightly-run CPU cap skipped (set NIGHTLY_APPLY_CPU_LIMIT=1 to enable)"; \
	fi; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ] && [ -n "$$(cat $(LATEST_OK_ADAPTER_ID_FILE))" ] && [ -f data/models/$$(cat $(LATEST_OK_ADAPTER_ID_FILE))/adapter_config.json ]; then \
		echo "INFO: nightly-run start mode=continue from promoted adapter"; \
		$(MAKE) real-run-continue; \
	else \
		echo "INFO: nightly-run start mode=fresh-short (no promoted adapter available)"; \
		$(MAKE) real-run-short; \
	fi; \
	$(MAKE) swap-gate-eval; \
	$(MAKE) eval-val; \
	PREV_OK_ID=""; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then PREV_OK_ID=$$(cat $(LATEST_OK_ADAPTER_ID_FILE)); fi; \
	$(MAKE) promote-latest-ok; \
	NEW_OK_ID=""; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then NEW_OK_ID=$$(cat $(LATEST_OK_ADAPTER_ID_FILE)); fi; \
	if [ -n "$$NEW_OK_ID" ] && [ "$$NEW_OK_ID" != "$$PREV_OK_ID" ]; then \
		echo "INFO: promoted adapter changed ($$PREV_OK_ID -> $$NEW_OK_ID); restarting serve"; \
		$(MAKE) serve-down || true; \
		$(MAKE) serve-up; \
	else \
		echo "INFO: no new promotion applied; serving remains unchanged"; \
	fi; \
	$(MAKE) retention-clean; \
	echo "OK: nightly-run completed"

smoke: preflight build up check-gpu-container smoke-dataset smoke-train smoke-infer smoke-report
	@echo "##############"
	@echo "### STEP smoke: end-to-end smoke workflow completed"
	@echo "##############"
	@echo "OK: smoke workflow completed"

smoke-dataset: ensure-data-dirs
	@printf '%s\n' \
'{"instruction":"Antworte mit exakt einem Wort: OK","input":"","output":"OK"}' \
> $(SMOKE_DATASET)
	@echo "OK: wrote $(SMOKE_DATASET)"

smoke-train: up smoke-dataset
	@set -e; \
	RUN_ID=smoke-$$(date -u +%Y%m%dT%H%M%SZ); \
	echo "$$RUN_ID" > $(SMOKE_RUN_ID_FILE); \
	echo "SMOKE_RUN_ID=$$RUN_ID"; \
	./scripts/run_nice.sh $(COMPOSE) exec -T $(SERVICE) python src/scripts/train_lora.py \
		--config configs/smoke_lora.yaml \
		--dataset $(SMOKE_DATASET) \
		--run-id $$RUN_ID; \
	test -f data/models/$$RUN_ID/adapter_config.json || { echo "ERROR: missing adapter_config.json for $$RUN_ID"; exit 1; }; \
	echo "OK: smoke train finished for $$RUN_ID"

smoke-infer: up
	@test -f $(SMOKE_RUN_ID_FILE) || { echo "ERROR: missing $(SMOKE_RUN_ID_FILE) (run smoke-train first)"; exit 1; }
	@set -e; \
	RUN_ID=$$(cat $(SMOKE_RUN_ID_FILE)); \
	echo "SMOKE_RUN_ID=$$RUN_ID"; \
	test -f data/models/$$RUN_ID/adapter_config.json || { echo "ERROR: missing adapter_config.json for $$RUN_ID (training did not produce adapter artifacts)"; exit 1; }; \
	$(COMPOSE) exec -T $(SERVICE) python src/scripts/eval.py \
		--dataset $(SMOKE_DATASET) \
		--base-model $(BASE_MODEL) \
		--adapter-path data/models/$$RUN_ID \
		--output-dir data/evals/$$RUN_ID \
		--max-samples 1 \
		--max-new-tokens 16 \
		--batch-size 1; \
	test -f data/evals/$$RUN_ID/summary.json || { echo "ERROR: missing eval summary for $$RUN_ID"; exit 1; }; \
	echo "OK: smoke infer finished for $$RUN_ID"

smoke-report:
	@test -f $(SMOKE_RUN_ID_FILE) || { echo "ERROR: missing $(SMOKE_RUN_ID_FILE)"; exit 1; }
	@RUN_ID=$$(cat $(SMOKE_RUN_ID_FILE)); \
	GIT_SHA=$$(git rev-parse --short HEAD 2>/dev/null || echo "unknown"); \
	TS=$$(date -u +%Y-%m-%dT%H:%M:%SZ); \
	mkdir -p $(SMOKE_STATE_DIR); \
	{ \
		echo "project=$(PROJECT_NAME)"; \
		echo "timestamp_utc=$$TS"; \
		echo "run_id=$$RUN_ID"; \
		echo "git_sha=$$GIT_SHA"; \
		echo "base_model=$(BASE_MODEL)"; \
		echo "dataset=$(SMOKE_DATASET)"; \
		echo "model_dir=data/models/$$RUN_ID"; \
		echo "eval_dir=data/evals/$$RUN_ID"; \
	} > $(SMOKE_REPORT); \
	echo "OK: wrote $(SMOKE_REPORT)"

# Keeps latest N run-like directories in models/logs/evals.
# Never touches HF caches (outside these paths).
# Protects LATEST_REALRUN_ID and LATEST_OK_ADAPTER_ID from pruning and repairs stale pointers afterwards.
retention-clean:
	@set -e; \
	KEEP=$(RETENTION_KEEP); \
	PROTECT_REAL_ID=""; \
	PROTECT_OK_ID=""; \
	if [ -f $(LATEST_REALRUN_ID_FILE) ]; then \
		PROTECT_REAL_ID=$$(cat $(LATEST_REALRUN_ID_FILE)); \
	fi; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then \
		PROTECT_OK_ID=$$(cat $(LATEST_OK_ADAPTER_ID_FILE)); \
	fi; \
	echo "INFO: retention keep=$$KEEP protect_real_id=$$PROTECT_REAL_ID protect_ok_id=$$PROTECT_OK_ID"; \
	for ROOT in data/models data/logs data/evals; do \
		[ -d $$ROOT ] || { echo "INFO: skip missing $$ROOT"; continue; }; \
		CANDIDATES=$$(find $$ROOT -mindepth 1 -maxdepth 1 -type d -print | sed "s#^$$ROOT/##" | grep -E ".*-[0-9]{8}T[0-9]{6}Z$$" | sort -r); \
		if [ -n "$$PROTECT_REAL_ID" ]; then \
			CANDIDATES=$$(printf '%s\n' "$$CANDIDATES" | grep -v -x "$$PROTECT_REAL_ID" || true); \
		fi; \
		if [ -n "$$PROTECT_OK_ID" ]; then \
			CANDIDATES=$$(printf '%s\n' "$$CANDIDATES" | grep -v -x "$$PROTECT_OK_ID" || true); \
		fi; \
		COUNT=$$(printf '%s\n' "$$CANDIDATES" | sed '/^$$/d' | wc -l | tr -d ' '); \
		if [ "$$COUNT" -le "$$KEEP" ]; then \
			echo "INFO: $$ROOT nothing to prune ($$COUNT <= $$KEEP)"; \
			continue; \
		fi; \
		PRUNE=$$(printf '%s\n' "$$CANDIDATES" | tail -n +$$((KEEP+1))); \
		printf '%s\n' "$$PRUNE" | while IFS= read -r NAME; do \
			[ -n "$$NAME" ] || continue; \
			rm -rf "$$ROOT/$$NAME"; \
			echo "PRUNED: $$ROOT/$$NAME"; \
		done; \
	done; \
	if [ -f $(LATEST_REALRUN_ID_FILE) ]; then \
		CURRENT_ID=$$(cat $(LATEST_REALRUN_ID_FILE)); \
		if [ -n "$$CURRENT_ID" ] && [ ! -f data/models/$$CURRENT_ID/adapter_config.json ]; then \
			NEW_ID=$$(find data/models -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sed 's#^data/models/##' | grep -E '^real-[0-9]{8}T[0-9]{6}Z$$' | sort -r | while IFS= read -r RID; do [ -f data/models/$$RID/adapter_config.json ] && { echo "$$RID"; break; }; done); \
			if [ -z "$$NEW_ID" ]; then \
				NEW_ID=$$(find data/models -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sed 's#^data/models/##' | sort -r | while IFS= read -r RID; do [ -f data/models/$$RID/adapter_config.json ] && { echo "$$RID"; break; }; done); \
			fi; \
			if [ -n "$$NEW_ID" ]; then \
				echo "$$NEW_ID" > $(LATEST_REALRUN_ID_FILE); \
				echo "INFO: repaired $(LATEST_REALRUN_ID_FILE) -> $$NEW_ID"; \
			else \
				echo "WARN: no adapter found to repair $(LATEST_REALRUN_ID_FILE)"; \
			fi; \
		fi; \
	fi; \
	if [ -f $(LATEST_OK_ADAPTER_ID_FILE) ]; then \
		CURRENT_OK_ID=$$(cat $(LATEST_OK_ADAPTER_ID_FILE)); \
		if [ -n "$$CURRENT_OK_ID" ] && [ ! -f data/models/$$CURRENT_OK_ID/adapter_config.json ]; then \
			echo "WARN: promoted adapter missing after retention; clearing LATEST_OK pointer"; \
			: > $(LATEST_OK_ADAPTER_ID_FILE); \
			echo "data/models/<run-id>" > $(LATEST_OK_ADAPTER_PATH_FILE); \
		fi; \
	fi; \
	echo "OK: retention-clean done"

clean-smoke:
	@rm -rf data/models/smoke-* data/evals/smoke-* data/logs/smoke-* $(SMOKE_STATE_DIR)
	@mkdir -p $(SMOKE_STATE_DIR)
	@echo "OK: smoke artifacts removed"

clean-data:
	@find data -mindepth 1 -maxdepth 1 ! -name README.md -exec rm -rf {} +
	@mkdir -p data/datasets data/models data/logs data/evals $(SMOKE_STATE_DIR) $(RUN_STATE_DIR) .cache .cache/huggingface .cache/huggingface/datasets .cache/huggingface/transformers
	@touch $(LATEST_OK_ADAPTER_ID_FILE)
	@echo "data/models/<run-id>" > $(LATEST_OK_ADAPTER_PATH_FILE)
	@echo "OK: data artifacts removed and runtime pointers reset"
	@rm -f $(LATEST_REALRUN_ID_FILE) $(RUN_STATE_DIR)/LATEST_EVAL_RUN_ID $(LATEST_PROMOTION_SUMMARY_FILE) $(RUN_LOCK_FILE)
	@echo "OK: cleaned generated data artifacts and reset runtime pointers (kept data/README.md)"

reset-runtime:
	@echo "##############"
	@echo "### STEP reset-runtime: stop stacks and reset runtime state"
	@echo "##############"
	@set -e; \
	echo "INFO: stopping serving stack (if running)"; \
	$(SERVE_COMPOSE) down || true; \
	echo "INFO: stopping training stack (if running)"; \
	$(COMPOSE) down || true; \
	echo "INFO: clearing runtime state for fresh E2E run"; \
	$(MAKE) clean-data; \
	echo "OK: runtime reset completed"
