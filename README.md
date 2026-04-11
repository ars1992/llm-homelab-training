# llm-homelab-training

Reproduzierbare lokale Container-Umgebung für LLM-Training (LoRA/Fine-Tuning) auf NVIDIA K80 mit Fokus auf **stabilem Workflow**, **Version-Pinning** und späterer Erweiterung um eine **SEAL-inspirierte Self-Edit-Pipeline**.

## Ziele

- Lokales, cloudfreies Training im Container
- Reproduzierbare Abhängigkeiten (Python + ML-Stack)
- MVP-Trainingspipeline für LoRA auf einem 3B-Basismodell
- Saubere Trennung zwischen Code (`src/`), Konfiguration (`configs/`) und Laufzeitartefakten (`data/`)

## Projektstruktur

```text
.
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── Makefile
├── docker/
│   ├── Dockerfile
│   ├── compose.yaml
│   ├── compose.serve.yaml
│   └── requirements.txt
├── src/
│   ├── datasets/
│   │   ├── README.md
│   │   └── schemas/
│   │       └── self_edit.schema.json
│   ├── scripts/
│   │   ├── prepare_dataset.py
│   │   ├── generate_runbook_samples.py
│   │   ├── generate_self_edits.py
│   │   ├── train_lora.py
│   │   ├── eval.py
│   │   ├── eval_val.py
│   │   └── validate_val.py
│   └── serve/
│       └── app.py
├── scripts/
│   ├── check_gpu.sh
│   ├── run_nice.sh
│   └── serve_smoke.sh
├── configs/
│   ├── base.yaml
│   ├── train_lora_3b_k80.yaml
│   ├── train_lora_3b_k80_short.yaml
│   ├── smoke_lora.yaml
│   ├── eval.yaml
│   └── datasets/
│       └── val_regression.yaml
├── docs/
│   ├── ROADMAP.md
│   ├── SEAL_NOTES.md
│   ├── TROUBLESHOOTING_K80.md
│   └── BACKUP_POLICY.md
├── data/
│   └── README.md
└── .ai/
    ├── CONTEXT.md
    ├── GitGuideline.md
    ├── SyntaxGuideline.md
    ├── ADR-0001-Container-TrainingStack.md
    ├── ADR-0002-TrainingData-In-Repo.md
    ├── ADR-0003: SEAL-MVP (Self-Edit Loop) als deterministische, auditierbare Pipeline-Erweiterung.md
    ├── CHECKLIST-SERVE-PROMOTION-MVP.md
    ├── TASK-ZED-0001-Fix-Permissions-Data-Mount.md
    └── SANDRO.md
```

---

## Voraussetzungen

- Docker + Docker Compose Plugin
- NVIDIA-Treiber auf Host installiert
- NVIDIA Container Toolkit korrekt eingerichtet
- Zugriff auf mindestens eine CUDA-fähige GPU (Ziel: K80)
- Optional: Hugging Face Token (für gated Modelle), **nicht ins Repo committen**

---

## Quickstart

### 1) Repo klonen und wechseln

Empfohlener Code-Pfad (Source-of-Truth): `/opt/projects/llm-homelab-training`  
(`opt/containers` nur für Runtime-Stacks, nicht für Code als Primärablage).

```bash
mkdir -p /opt/projects
cd /opt/projects
git clone <DEIN-REPO-URL> llm-homelab-training
cd llm-homelab-training
```

### 2) Beispiel-Umgebungsvariablen kopieren

```bash
cp .env.example .env
```

Danach bei Bedarf `.env` anpassen.

Wichtige lokale Overrides:

- `CUDA_VISIBLE_DEVICES` / `NVIDIA_VISIBLE_DEVICES`
- Cache-Pfade (`HF_HOME`, `HF_DATASETS_CACHE`, `TRANSFORMERS_CACHE`)
- `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128` (Fragmentierungsmitigation)
- **UID/GID-Mapping gegen root-owned Artefakte**:
  - `USERMAP_UID` und `USERMAP_GID`
  - Werte auf Host prüfen mit `id -u` und `id -g`
- **Trainer-Cache-Bind-Mount muss aktiv sein**:
  - `docker/compose.yaml` mountet `../.cache:/workspace/.cache`
  - verhindert `PermissionError` beim Schreiben von Hugging-Face-Artefakten unter `/workspace/.cache/huggingface/...`

### 3) Container bauen und starten

```bash
docker compose -f docker/compose.yaml up -d --build
```

### 4) In den Trainer-Container wechseln

```bash
docker compose -f docker/compose.yaml exec trainer bash
```

### 5) Training starten (MVP)

Im Container:

```bash
python src/scripts/train_lora.py \
  --config configs/train_lora_3b_k80.yaml \
  --dataset data/datasets/train.jsonl
```

### 6) TensorBoard Logs prüfen

Im Container:

```bash
tensorboard --logdir data/logs --host 0.0.0.0 --port 6006
```

Auf Host (wenn Port gemappt): `http://localhost:6006`

### 7) Preflight + Smoke-Workflow (empfohlen vor langen Runs)

Auf Host:

```bash
make preflight
make smoke
```

Der Smoke-Workflow führt fail-fast aus:
1. Host-GPU-Checks
2. Container-Build/Start
3. Container-GPU-Checks
4. Mini-Training
5. Mini-Eval/Infer
6. Smoke-Report unter `data/runs/smoke/report.txt`

### 8) Augmented Dataset bauen (Vault + Exact + Runbook + optional Self-Edits)

```bash
make prepare-dataset-augmented
```

Ablauf:

1. Vault-Extraktion nach `data/datasets/train_vault.jsonl`
2. Exact-Extraction Samples
3. deterministische Runbook-Generierung (`runbook_samples.jsonl`)
4. optional capped Self-Edit-Export (`SELF_EDITS_MERGE_ENABLE`, `SELF_EDITS_MERGE_CAP`)
5. deduplizierter Merge nach `data/datasets/train.jsonl`

### 9) Regression-Eval auf `val.jsonl`

```bash
make eval-val
```

Ergebnisartefakte:
- `data/evals/<run-id>/val_report.json`
- `data/evals/<run-id>/val_predictions.jsonl`

### 10) SEAL-MVP Self-Edits (deterministisch, auditierbar)

```bash
make self-edits-generate
make self-edits-validate
```

Run-Artefakte:
- `data/self_edits/runs/<run_id>/sources.snapshot.jsonl`
- `data/self_edits/runs/<run_id>/candidates.jsonl`
- `data/self_edits/runs/<run_id>/verifications.jsonl`
- `data/self_edits/runs/<run_id>/accepted.derived.jsonl`
- `data/self_edits/runs/<run_id>/manifest.json`

Stabiler Exportpfad:
- `data/training/derived/self_edits.accepted.jsonl`

### 11) Serving (gehärtet, OpenAI-kompatibel)

```bash
make serve-up
make serve-health
make serve-test
```

Merkmale:
- Startet auch ohne `LATEST_OK` im Degraded-Status statt Crash
- `/v1/chat/completions` liefert bei nicht bereitem Modell deterministisch `503`
- Antwort-Sanitizer + anti-loop defaults aktiv
- `make serve-test` schreibt Smoke-Report nach `data/evals/serve_smoke_<ts>.txt`

### 12) Retention sicher ausführen

```bash
make retention-clean
```

Betriebsverhalten:
- Retention schützt den Run aus `data/runs/LATEST_REALRUN_ID` vor dem Pruning.
- Promotete Adapter (`LATEST_OK_ADAPTER_ID`) bleiben geschützt.
- Falls `LATEST_REALRUN_ID` auf einen fehlenden Adapter zeigt, wird der Pointer auf den neuesten vorhandenen Adapter-Run repariert.

### 13) Swap nach schwerem Lauf zurücksetzen (Host)

```bash
make swap-reset
```

Betriebsverhalten:
- `swap-reset` wird nur ausgeführt, wenn `MemAvailable` auf dem Host größer als ca. 6 GB ist.
- Bei zu wenig verfügbarem RAM wird der Schritt mit Warnung übersprungen.

### 14) Single-Flight Lock + Swap-Gates (Stabilität)

```bash
make lock-status
make real-run-continue
make eval-val
```

Betriebsverhalten:
- Es darf immer nur ein schwerer Lauf gleichzeitig aktiv sein (Single-Flight über `data/runs/LOCK`).
- Wenn ein Lock aktiv ist, brechen `real-run-*`, `eval-val` und `nightly-run` mit klarer Meldung ab (`already_running`).
- Vor Training und Eval greifen Swap-Gates:
  - Training: bei kritischem Speicher-/Swap-Zustand wird abgebrochen.
  - Eval: bei kritischem Zustand wird der Lauf übersprungen (non-blocking Policy bleibt erhalten).

Recovery:
- Lock prüfen: `make lock-status`
- Lock nur bei eindeutigem Stale-Zustand entfernen: `make lock-clear`

---

## Datensatzformate

### A) Training (`data/datasets/train.jsonl`)

`train_lora.py` erwartet JSONL mit je einem Objekt pro Zeile:

```json
{"instruction":"...", "input":"...", "output":"..."}
```

Hinweise:
- `instruction` ist Pflicht
- `output` ist Pflicht
- `input` kann leer sein (`""`)
- Encoding: UTF-8
- Eine Zeile = ein Trainingsbeispiel

### B) Regression-Validation (`data/datasets/val.jsonl`)

`eval_val.py` erwartet JSONL im folgenden Schema:

```json
{"id":"val-001","instruction":"...","input":"","expected_contains":["..."],"tags":["regression"]}
```

Hinweise:
- `expected_contains` enthält 1–3 kurze Substrings
- Prüfung erfolgt substring-basiert (`pass/fail`)
- Dieses Schema ist für Regression-Eval gedacht, nicht als direktes `output`-Trainingslabel

---

## Artefaktpfade

- LoRA-Adapter: `data/models/<run-id>/`
- Trainingslogs (TensorBoard): `data/logs/<run-id>/`
- Datensätze: `data/datasets/`
- Regression-Reports: `data/evals/<run-id>/val_report.json`
- Serving-Smoke-Reports: `data/evals/serve_smoke_<ts>.txt`
- Self-Edit-Run-Artefakte: `data/self_edits/runs/<run_id>/...`
- Self-Edit-Export (accepted): `data/training/derived/self_edits.accepted.jsonl`
- Self-Edit-Run-Pointer: `data/runs/LATEST_SELF_EDIT_RUN_ID`

`data/` enthält Laufzeitartefakte und soll großteils **nicht versioniert** werden (siehe `.gitignore`).

---

## Workflow-Überblick

1. Datensatzquellen vorbereiten (`prepare_dataset.py`, optional `prepare-dataset-augmented`)
2. Runbook-Samples deterministisch generieren (`make runbook-samples-generate`)
3. Optional Self-Edits generieren/validieren (`make self-edits-generate`, `make self-edits-validate`)
4. Trainingskonfiguration wählen (`configs/train_lora_3b_k80.yaml` oder `configs/train_lora_3b_k80_short.yaml`)
5. Single-Flight prüfen (`make check-single-flight` bzw. indirekt über Lauf-Targets)
6. LoRA-Training ausführen (`make real-run-short` oder `make real-run-continue`)
7. Swap-Gates vor schweren Schritten beachten (Train = abort bei kritisch, Eval = skip bei kritisch)
8. Regression-Eval ausführen (`make eval-val`, non-blocking)
9. Promotion prüfen (`make promote-latest-ok`) und Serving nur bei neuer Promotion umschalten
10. Serving testen (`make serve-test`)
11. Retention ausführen (`make retention-clean`) mit Schutz von `LATEST_REALRUN_ID` und `LATEST_OK_ADAPTER_ID`

---

## K80-spezifische Hinweise

- K80 ist VRAM- und throughput-limitiert
- Für stabile Läufe:
  - kleine `batch_size`
  - `gradient_accumulation_steps` erhöhen
  - `seq_len` reduzieren
  - Gradient Checkpointing aktivieren

### Swap-Thrash Mitigation (Quickstart, verbindliche Reihenfolge)

Wenn der Host während Dataset-Prep oder Training unbedienbar wird, gilt folgende Reihenfolge:

1. **`max_seq_length` zuerst reduzieren** (wichtigster Hebel):
   - Standardpfad: `512 -> 384`
   - Bei weiterem Swap-Druck: `384 -> 256`
2. **`gradient_accumulation_steps` erhöhen**, um bei kürzerer Sequenzlänge ein stabiles Trainingssignal zu halten
   (z. B. `16 -> 24` oder `32`).
3. **Tokenisierungs-Parallelität niedrig halten** (`num_proc: 1`, kleine `dataloader_num_workers`), um RAM-Peaks zu vermeiden.
4. **Schwere Targets mit niedriger Priorität ausführen** (host-freundlicher Laufmodus über `run_nice`).
5. **Mem/Swap vor und nach Lauf prüfen**:
   - `free -h`
   - `grep -E 'MemAvailable|SwapTotal|SwapFree' /proc/meminfo`
   - `df -h /`

Hinweis:
- Diese Maßnahmen priorisieren Host-Stabilität und Bedienbarkeit.
- Der Lauf kann dadurch langsamer werden; das ist erwartetes Verhalten.

Notfall-Runbook (wenn Host trotz Maßnahmen unresponsiv wird):
1. Nicht-kritische Dienste stoppen (z. B. TensorBoard/Serving), um RAM/I/O zu entlasten.
2. Swap-Status prüfen und nur bei ausreichendem RAM `make swap-reset` ausführen.
3. Falls Druck dauerhaft hoch bleibt: Swap temporär vergrößern und danach Ursache im Trainingsprofil beheben.
4. Zielzustand ist stabiler RAM-Betrieb; Swap ist nur Notfallpuffer, keine Dauerlösung.

### Verbindliche Legacy-GPU Baseline (frozen)

Für dieses Projekt ist eine feste, stabile GPU-Software-Baseline definiert:

- NVIDIA Driver (Host): `470.256.02`
- CUDA Runtime laut `nvidia-smi`: `11.4`
- Ziel-GPU: `Tesla K80`

Betriebsregel:
- Treiber/CUDA werden **nicht** aktualisiert.
- Änderungen sind nur per expliziter Ausnahmefreigabe mit Risikoanalyse und Rollback-Plan zulässig.

### Permissions / Ownership-Betriebsregel

Um root-owned Artefakte unter `data/` zu vermeiden, läuft der Trainer-Container mit Host-UID/GID-Mapping:

- Compose: `user: "${USERMAP_UID:-1000}:${USERMAP_GID:-1000}"`
- `.env`: `USERMAP_UID`, `USERMAP_GID` korrekt auf Host setzen (`id -u`, `id -g`)
- Zusätzlich muss der HF-Cache hostseitig gemountet sein:
  - `../.cache:/workspace/.cache`
  - sonst kann es bei Modell-/Tokenizer-Downloads zu `PermissionError` unter `/workspace/.cache/huggingface/...` kommen
- Nach Änderung immer neu erstellen:
  - `docker compose -f docker/compose.yaml down`
  - `docker compose -f docker/compose.yaml up -d --build`

Basisimage-Entscheidung (Ubuntu statt Alpine):
- Für CUDA-/PyTorch-Workloads auf K80 nutzen wir Ubuntu-basierte NVIDIA-Images.
- Grund: Höhere Kompatibilität mit glibc-basierten CUDA/PyTorch-Wheels und reproduzierbarere Installation von `transformers`/`peft`-Abhängigkeiten.
- Alpine (musl) ist für diesen Stack bewusst ausgeschlossen, da es häufiger zu Build-/Kompatibilitätsproblemen führt.

Referenzen:
- K80 Troubleshooting: `docs/TROUBLESHOOTING_K80.md`
- GPU Datenblatt: `.ai/GPU-DATENBLATT-K80-HOMELAB.md`
- Erste-Testlauf-Checkliste: `.ai/CHECKLIST-ERSTER-TESTLAUF-K80.md`

---

## Reproduzierbarkeit

- Version-Pinning im Container-Stack
- Feste Konfigurationsdateien unter `configs/`
- Laufzeitartefakte getrennt von Source Code
- Keine Secrets im Repository
- GPU-Preconditions als fail-fast Check (`scripts/check_gpu.sh`, `make preflight`)

---

## Backup-Strategie (empfohlen)

Formale Richtlinie: `docs/BACKUP_POLICY.md`

Trennung für robuste Sicherung:
- **Code (Source-of-Truth):** `/opt/projects/llm-homelab-training`
- **Runtime-Artefakte:** `data/` (nicht ins Git, selektiv sichern)
- **`/opt/containers`:** nur Runtime-Ort, nicht Primärablage für Projektcode

Backup-Empfehlung:
1. **Täglich sichern**
   - Repository-Inhalt (inkl. Doku, Configs, Skripte)
   - Run-Metadaten (Konfiguration, Run-ID, Metrik-Summary)
   - wichtige Adapter-Artefakte (`best`/`final`)
2. **Wöchentlich sichern**
   - sekundäre Logs/Reports
3. **Ausschließen**
   - große Caches (`.cache`, HF caches)
   - unnötige Zwischencheckpoints, sofern reproduzierbar

Restore-Drills (regelmäßig):
- Code-only Rebuild
- Restore eines einzelnen Runs (Metadaten + Adapter)
- Kritischer Partial-Restore (`data/`-Verlust simulieren)

---

## Sicherheit / Compliance

- Keine API Keys in Git
- `.env` lokal halten
- Bei externen Modellquellen Lizenzbedingungen prüfen
- Trainingsdaten auf Datenschutz/Urheberrecht prüfen

---

## Nächste Schritte

- Basisdatensatz + Validierung robust machen

## Externe Referenzen (Vault)

- ADR: `ADR_Trainingsdaten_im_llm-homelab-training_repo_2026-04-06`
- Blueprint: `Dokumentation_Projektplan_TrainingData_Blueprint_2026-04-06`
- Checklist: `Dokumentation_Dataset_Quality_Checklist_Eval_Gates_2026-04-06`
- Evaluationsmetriken formalisieren
- SEAL-inspirierte Self-Edit-Loop als kontrollierte Pipeline ergänzen
- Dokumentation in `docs/` und Architekturentscheidungen in `.ai/` fortlaufend pflegen