# CONTEXT

## Projektziel
`llm-homelab-training` stellt eine lokal reproduzierbare Container-Trainingsumgebung für LoRA/Fine-Tuning eines ca. 3B-Basismodells auf NVIDIA K80 bereit.  
Der aktuelle Fokus ist ein stabiler MVP-Trainingspfad; darauf aufbauend folgt eine SEAL-inspirierte Self-Edit-Pipeline.

## Leitprinzipien
- Lokal-only Betrieb (keine Cloud-Abhängigkeit)
- Reproduzierbarkeit vor Performance-Optimierung
- Konfigurationsgetriebene Ausführung
- Trennung von Code, Konfiguration und Laufzeitartefakten
- Keine Secrets im Repository

## Ordner-Overview
- `docker/`  
  Container-Stack (`Dockerfile`, `compose.yaml`, gepinnte Dependencies)
- `src/scripts/`  
  Trainings-, Datenvorbereitungs-, Self-Edit- und Eval-Skripte
- `src/datasets/schemas/`  
  Schemata für strukturierte Datensätze (u. a. Self-Edit)
- `configs/`  
  Laufkonfigurationen (Basis, K80-LoRA, Evaluation)
- `docs/`  
  Roadmap, K80-Troubleshooting, SEAL-Notizen, Backup-Policy
- `scripts/`  
  Betriebsnahe Prüfscripte (u. a. `check_gpu.sh` für Preflight)
- `Makefile`  
  Standardisierte Targets für Preflight, Smoke, Training und Betrieb
- `data/`  
  Lokale, nicht versionierte Artefakte: Datensätze, Modelle, Logs
- `.ai/`  
  Architektur-/Kontextdokumente und Guidelines

## Datenformat (MVP Training)
Erwartetes JSONL pro Zeile:
`{"instruction":"...", "input":"...", "output":"..."}`

Pflicht:
- `instruction` (string, nicht leer)
- `output` (string, nicht leer)

Optional:
- `input` (string, leer erlaubt)

## How to run (lokal)

### Standard-Preflight (empfohlen vor jedem Lauf)

1. `.env` anlegen:
`cp .env.example .env`

2. Host-Preflight prüfen:
`make preflight`

3. Container bauen und starten:
`make build`
`make up`

4. Container-GPU prüfen:
`make check-gpu-container`

### Smoke-Run (schneller End-to-End Check)

5. Vollständigen Smoke-Workflow starten:
`make smoke`

Der Smoke-Workflow führt deterministisch aus:
- GPU-Checks (Host + Container)
- Build/Start
- Tiny-Dataset-Erzeugung
- Kurz-Training
- Kurz-Evaluation
- Smoke-Report unter `data/runs/smoke/report.txt`

### Manueller Trainingslauf (MVP)

6. In den Trainer-Container:
`docker compose -f docker/compose.yaml exec trainer bash`

7. Training starten:
`python src/scripts/train_lora.py --config configs/train_lora_3b_k80.yaml --dataset data/datasets/train.jsonl`

8. Logs ansehen (TensorBoard):
`tensorboard --logdir data/logs --host 0.0.0.0 --port 6006`

9. Optional stoppen:
`make down`

## Output-Konventionen
- LoRA-Adapter: `data/models/<run-id>/`
- Trainingslogs: `data/logs/<run-id>/`
- Smoke-Run Status/Metadaten: `data/runs/smoke/report.txt`
- Smoke-Eval-Artefakte: `data/evals/smoke-*/`

## Hinweise zu K80
- Kleine Batchgrößen verwenden
- Gradient Accumulation erhöhen
- `max_seq_length` konservativ halten
- Bei OOM zuerst Sequenzlänge reduzieren, dann weitere Parameter anpassen

## Meilensteinstatus (aktuell)
- Container CUDA Validierung erfolgreich abgeschlossen:
  - `nvidia-smi` im Container erkennt Tesla K80 korrekt
  - PyTorch CUDA ist verfügbar (`torch.cuda.is_available() == true`)
  - Verifizierter Runtime-Stand: `torch 1.12.1+cu113`, `CUDA 11.3`, `compute capability 3.7`

- Smoke-Run erfolgreich abgeschlossen:
  - `SMOKE_RUN_ID=smoke-20260406T092145Z`
  - Host-Preflight erfolgreich (Driver `470.256.02`, CUDA Runtime `11.4`, 2x Tesla K80 erkannt)
  - Container-GPU-Check erfolgreich (`cuda_available=true`, `compute_capability_0=3.7`)
  - Smoke-Training erfolgreich:
    - Adapter geschrieben nach `data/models/smoke-20260406T092145Z/`
    - Logs geschrieben nach `data/logs/smoke-20260406T092145Z/`
  - Smoke-Eval erfolgreich:
    - Predictions: `data/evals/smoke-20260406T092145Z/predictions.jsonl`
    - Summary: `data/evals/smoke-20260406T092145Z/summary.json`
  - Smoke-Report geschrieben: `data/runs/smoke/report.txt`

- Gate-Entscheidung:
  - Erster kurzer Real-Trainingslauf wurde erfolgreich abgeschlossen.
  - Validierter Run:
    - `run_id`: `real-20260406T092832Z`
    - Adapter-Artefakt vorhanden: `data/models/real-20260406T092832Z/adapter_config.json`
    - Finale Metrikdatei vorhanden: `data/models/real-20260406T092832Z/final_metrics.json`
    - `global_step`: `60`
  - Trainingsmetriken (Kurzlauf):
    - `train_loss`: `1.9559472759564718`
    - `train_runtime`: `1898.2539s`
    - `train_steps_per_second`: `0.032`
    - `train_samples_per_second`: `0.506`
  - Nächster Gate-Status:
    - Ein längerer Real-Run ist freigegeben, weiterhin mit konservativen K80-Parametern und vollständiger Run-ID-/Artefaktprüfung.

## Erstes Real-Run Protokoll (verbindlich)

### Ziel
Ein kontrollierter Kurzlauf auf realem Dataset zur Validierung von Stabilität, Artefaktpfaden und Laufdisziplin vor längeren Trainingsläufen.

### Ausführung (Reihenfolge)
1. `make preflight`
2. `make up`
3. `make check-gpu-container`
4. `make real-run-short`
5. `make run-status`

### Verwendete Konfiguration
- `configs/train_lora_3b_k80_short.yaml`
- Dataset: `data/datasets/train.jsonl`
- Run-ID wird automatisch gesetzt und in `data/runs/LATEST_REALRUN_ID` gespeichert.

### Erwartete Pflichtartefakte pro erfolgreichem Real-Run
- `data/models/<run-id>/adapter_config.json`
- `data/models/<run-id>/run_metadata.json`
- `data/models/<run-id>/final_metrics.json`
- `data/logs/<run-id>/` (TensorBoard-kompatible Logs)

### Abbruch-/No-Go Kriterien
- Training-Traceback
- fehlendes `adapter_config.json`
- fehlendes `final_metrics.json` bei abgeschlossen gemeldetem Lauf
- GPU-Fehler im Container-Check (`cuda_available=false`)

### Nachbereitung (Audit)
Nach jedem Real-Run dokumentieren:
- `run_id`
- UTC-Zeitstempel
- Commit-Stand
- verwendete Config + Dataset
- Ergebnisstatus (`success`/`failed`)
- Fehlerklasse und nächste Maßnahme (falls `failed`)

### Aktueller Nachweis (zuletzt erfolgreicher kontrollierter Real-Run)
- `run_id`: `real-20260406T092832Z`
- Config: `configs/train_lora_3b_k80_short.yaml`
- Dataset: `data/datasets/train.jsonl`
- Status: `success`
- Pflichtartefakte:
  - `data/models/real-20260406T092832Z/adapter_config.json`
  - `data/models/real-20260406T092832Z/final_metrics.json`
  - `data/logs/real-20260406T092832Z/`

## Ad-hoc Modellfrage Test (2026-04-06)

- Testfrage (Prompt): `Beantworte kurz und präzise: was weist du über eliot`
- Ausführung: Eval mit Adapter `data/models/real-20260406T092832Z`
- Ergebnisartefakte:
  - `data/evals/ask-eliot-real-20260406T092832Z/predictions.jsonl`
  - `data/evals/ask-eliot-real-20260406T092832Z/summary.json`
- Beobachtetes Antwortmuster:
  - Antwort enthält Wiederholungen und Prompt-Leakage (`### Response:` wiederholt im Output).
  - Inhaltliche Qualität ist für diese Frage unpräzise und nicht faktenorientiert.
- Interpretation:
  - Pipeline technisch erfolgreich (Inferenz + Artefaktschreibung), aber Antwortqualität für offene Wissensfragen ist im aktuellen Kurzlauf nicht ausreichend.
- Folgeaktion:
  1. Eval-Prompts um klare Antwortgrenzen erweitern (Länge/Format/Stop-Kriterien).
  2. Val-Set um offene Wissensfragen ergänzen und mit festen Qualitätskriterien evaluieren.

## Nächster Ausbauschritt
Self-Edit-Workflow (SEAL-inspiriert) über `src/scripts/generate_self_edits.py` und `src/datasets/schemas/self_edit.schema.json` schrittweise produktionsnah ausbauen.