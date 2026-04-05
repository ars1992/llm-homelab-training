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
│   └── requirements.txt
├── src/
│   ├── datasets/
│   │   ├── README.md
│   │   └── schemas/
│   │       └── self_edit.schema.json
│   └── scripts/
│       ├── prepare_dataset.py
│       ├── generate_self_edits.py
│       ├── train_lora.py
│       └── eval.py
├── scripts/
│   └── check_gpu.sh
├── configs/
│   ├── base.yaml
│   ├── train_lora_3b_k80.yaml
│   ├── smoke_lora.yaml
│   └── eval.yaml
├── docs/
│   ├── ROADMAP.md
│   ├── SEAL_NOTES.md
│   └── TROUBLESHOOTING_K80.md
├── data/
│   └── README.md
└── .ai/
    ├── CONTEXT.md
    ├── GitGuideline.md
    ├── SyntaxGuideline.md
    ├── ADR-0001-Container-TrainingStack.md
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

Danach bei Bedarf `.env` anpassen (z. B. `CUDA_VISIBLE_DEVICES`, HF Cache Pfade).

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

---

## Datensatzformat (MVP)

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

---

## Artefaktpfade

- LoRA-Adapter: `data/models/<run-id>/`
- Trainingslogs (TensorBoard): `data/logs/<run-id>/`
- Datensätze: `data/datasets/`

`data/` enthält Laufzeitartefakte und soll großteils **nicht versioniert** werden (siehe `.gitignore`).

---

## Workflow-Überblick

1. Datensatz erstellen/validieren (`prepare_dataset.py`, Schema in `src/datasets/schemas/`)
2. Trainingskonfiguration wählen (`configs/train_lora_3b_k80.yaml`)
3. LoRA-Training ausführen (`src/scripts/train_lora.py`)
4. Ergebnisse evaluieren (`src/scripts/eval.py`)
5. Iterativ verbessern (später: Self-Edit-Pipeline via `generate_self_edits.py`)

---

## K80-spezifische Hinweise

- K80 ist VRAM- und throughput-limitiert
- Für stabile Läufe:
  - kleine `batch_size`
  - `gradient_accumulation_steps` erhöhen
  - `seq_len` reduzieren
  - Gradient Checkpointing aktivieren
- Details und bekannte Probleme: `docs/TROUBLESHOOTING_K80.md`

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
- Evaluationsmetriken formalisieren
- SEAL-inspirierte Self-Edit-Loop als kontrollierte Pipeline ergänzen
- Dokumentation in `docs/` und Architekturentscheidungen in `.ai/` fortlaufend pflegen