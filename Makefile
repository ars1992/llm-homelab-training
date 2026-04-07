# Makefile for llm-homelab-training
# Purpose:
# - operational lifecycle targets for container workflow
# - reproducible smoke workflow (GPU checks -> build/up -> tiny train -> tiny infer -> report)

.DEFAULT_GOAL := help

PROJECT_NAME := llm-homelab-training
COMPOSE_FILE := docker/compose.yaml
COMPOSE := docker compose -f $(COMPOSE_FILE)
SERVICE := trainer
BASE_MODEL := facebook/opt-2.7b

SMOKE_DATASET := data/datasets/smoke_train.jsonl
SMOKE_STATE_DIR := data/runs/smoke
SMOKE_RUN_ID_FILE := $(SMOKE_STATE_DIR)/LATEST_RUN_ID
SMOKE_REPORT := $(SMOKE_STATE_DIR)/report.txt

REALRUN_CONFIG := configs/train_lora_3b_k80_short.yaml
REALRUN_DATASET := data/datasets/train.jsonl
RUN_STATE_DIR := data/runs
LATEST_REALRUN_ID_FILE := $(RUN_STATE_DIR)/LATEST_REALRUN_ID

VAL_REG_CONFIG := configs/datasets/val_regression.yaml
VAL_REG_DATASET := data/datasets/val.jsonl
VAL_REG_OUTPUT_ROOT := data/evals

VAULT_DOCS_ROOT := /vault/15_Dokumentation
VAULT_PREPARE_OUTPUT := data/datasets/train.jsonl
VAULT_PREPARE_REPORT := data/datasets/prepare_report.json

.PHONY: help \
	preflight check-docker check-gpu-host check-gpu-container check-paths gpu-info \
	build up down restart ps logs shell \
	ensure-data-dirs \
	train eval eval-val prepare-dataset prepare-dataset-vault self-edits tensorboard \
	real-run-short run-status \
	smoke smoke-dataset smoke-train smoke-infer smoke-report \
	clean-smoke clean-data

help:
	@echo "Targets:"
	@echo "  preflight        - Verify local prerequisites (docker, gpu, paths)"
	@echo "  build            - Build trainer image"
	@echo "  up               - Start trainer container in background"
	@echo "  down             - Stop/remove trainer container"
	@echo "  restart          - Restart trainer container"
	@echo "  ps               - Show compose service status"
	@echo "  logs             - Tail service logs"
	@echo "  shell            - Open shell inside trainer container"
	@echo "  gpu-info         - Show nvidia-smi inside container"
	@echo "  ensure-data-dirs - Create expected local data directories"
	@echo "  train            - Start LoRA training using default config"
	@echo "  eval             - Run eval script on dataset"
	@echo "  eval-val         - Run deterministic expected_contains regression checks"
	@echo "  prepare-dataset  - Validate/normalize dataset JSONL"
	@echo "  prepare-dataset-vault - Build train.jsonl from /vault/15_Dokumentation markdown files"
	@echo "  self-edits       - Generate placeholder self-edit candidates"
	@echo "  tensorboard      - Start tensorboard in container (port 6006)"
	@echo "  real-run-short   - Start first controlled K80 real-run with short config"
	@echo "  run-status       - Show latest real-run id and artifact status"
	@echo "  smoke            - End-to-end smoke workflow (check/build/up/train/infer/report)"
	@echo "  clean-smoke      - Remove smoke outputs"
	@echo "  clean-data       - Remove generated datasets/evals/logs/models (keeps data/README.md)"

preflight: check-docker check-gpu-host check-paths ensure-data-dirs

check-docker:
	@command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found in PATH"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose plugin not available"; exit 1; }
	@echo "OK: docker + compose available"

check-gpu-host:
	@./scripts/check_gpu.sh --host-only --compose-file $(COMPOSE_FILE) --service $(SERVICE)

check-paths:
	@test -f $(COMPOSE_FILE) || { echo "ERROR: missing $(COMPOSE_FILE)"; exit 1; }
	@test -f docker/Dockerfile || { echo "ERROR: missing docker/Dockerfile"; exit 1; }
	@test -f configs/train_lora_3b_k80.yaml || { echo "ERROR: missing configs/train_lora_3b_k80.yaml"; exit 1; }
	@test -f src/scripts/train_lora.py || { echo "ERROR: missing src/scripts/train_lora.py"; exit 1; }
	@echo "OK: required project files present"

ensure-data-dirs:
	@mkdir -p data/datasets data/models data/logs data/evals $(SMOKE_STATE_DIR)
	@echo "OK: ensured data directories"

build: check-docker check-paths
	@$(COMPOSE) build

up: ensure-data-dirs
	@$(COMPOSE) up -d

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

eval-val: up
	@set -e; \
	if [ ! -f $(LATEST_REALRUN_ID_FILE) ]; then \
		echo "ERROR: missing $(LATEST_REALRUN_ID_FILE). Run 'make real-run-short' first."; \
		exit 1; \
	fi; \
	RUN_ID=$$(cat $(LATEST_REALRUN_ID_FILE)); \
	ADAPTER_PATH=data/models/$$RUN_ID; \
	EVAL_RUN_ID=val-$$RUN_ID-$$(date -u +%Y%m%dT%H%M%SZ); \
	echo "EVAL_VAL_RUN_ID=$$EVAL_RUN_ID"; \
	$(COMPOSE) exec -T $(SERVICE) python src/scripts/eval_val.py \
		--config $(VAL_REG_CONFIG) \
		--dataset $(VAL_REG_DATASET) \
		--base-model $(BASE_MODEL) \
		--adapter-path $$ADAPTER_PATH \
		--run-id $$EVAL_RUN_ID \
		--output-dir $(VAL_REG_OUTPUT_ROOT); \
	test -f $(VAL_REG_OUTPUT_ROOT)/$$EVAL_RUN_ID/val_report.json || { echo "ERROR: missing val_report.json for $$EVAL_RUN_ID"; exit 1; }; \
	echo "OK: eval-val finished for $$EVAL_RUN_ID"

prepare-dataset: up
	@$(COMPOSE) exec $(SERVICE) python src/scripts/prepare_dataset.py \
		--input data/datasets/raw.jsonl \
		--output data/datasets/train.jsonl

prepare-dataset-vault: up
	@$(COMPOSE) exec -T $(SERVICE) python src/scripts/prepare_dataset.py \
		--mode vault_md \
		--vault-root $(VAULT_DOCS_ROOT) \
		--output $(VAULT_PREPARE_OUTPUT) \
		--max-files 500 \
		--max-samples 5000 \
		--redact-secrets true \
		--report $(VAULT_PREPARE_REPORT)

self-edits: up
	@$(COMPOSE) exec $(SERVICE) python src/scripts/generate_self_edits.py \
		--input-jsonl data/datasets/train.jsonl \
		--output-jsonl data/datasets/self_edits.jsonl \
		--report-json data/datasets/self_edits.report.json

tensorboard: up
	@$(COMPOSE) exec $(SERVICE) tensorboard --logdir data/logs --host 0.0.0.0 --port 6006

real-run-short: preflight up check-gpu-container
	@set -e; \
	RUN_ID=real-$$(date -u +%Y%m%dT%H%M%SZ); \
	mkdir -p $(RUN_STATE_DIR); \
	echo "$$RUN_ID" > $(LATEST_REALRUN_ID_FILE); \
	echo "REAL_RUN_ID=$$RUN_ID"; \
	$(COMPOSE) exec $(SERVICE) python src/scripts/train_lora.py \
		--config $(REALRUN_CONFIG) \
		--dataset $(REALRUN_DATASET) \
		--run-id $$RUN_ID; \
	test -f data/models/$$RUN_ID/adapter_config.json || { echo "ERROR: missing adapter_config.json for $$RUN_ID"; exit 1; }; \
	echo "OK: real-run-short finished for $$RUN_ID"

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

smoke: preflight build up check-gpu-container smoke-dataset smoke-train smoke-infer smoke-report
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
	$(COMPOSE) exec $(SERVICE) python src/scripts/train_lora.py \
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
	$(COMPOSE) exec $(SERVICE) python src/scripts/eval.py \
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

clean-smoke:
	@rm -f $(SMOKE_DATASET) $(SMOKE_RUN_ID_FILE) $(SMOKE_REPORT)
	@rm -rf data/evals/smoke-* data/models/smoke-* data/logs/smoke-*
	@echo "OK: smoke artifacts removed"

clean-data:
	@find data -mindepth 1 -maxdepth 1 ! -name README.md -exec rm -rf {} +
	@mkdir -p data/datasets data/models data/logs data/evals $(SMOKE_STATE_DIR)
	@echo "OK: cleaned generated data artifacts (kept data/README.md)"
