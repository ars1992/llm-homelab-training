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
- Host-freundlicher Laufmodus für schwere Schritte (CPU/I/O priorisiert, E2E bleibt lauffähig)

## Ordner-Overview
- `docker/`  
  Container-Stack (`Dockerfile`, `compose.yaml`, `compose.serve.yaml`, gepinnte Dependencies)
- `src/scripts/`  
  Trainings-, Datenvorbereitungs-, Self-Edit- und Eval-Skripte
- `src/datasets/schemas/`  
  Schemata für strukturierte Datensätze (u. a. Self-Edit)
- `configs/`  
  Laufkonfigurationen (Basis, K80-LoRA, Evaluation)
- `configs/datasets/`  
  Dataset-spezifische Konfigurationen (u. a. Regression-Eval für `val.jsonl`)
- `docs/`  
  Roadmap, K80-Troubleshooting, SEAL-Notizen, Backup-Policy
- `scripts/`  
  Betriebsnahe Prüfscripte (u. a. `check_gpu.sh` für Preflight)
- `Makefile`  
  Standardisierte Targets für Preflight, Smoke, Training, Eval, Promotion, Serving, Retention, Recovery (`swap-reset`) und Betrieb
- `data/`  
  Lokale, nicht versionierte Artefakte: Datensätze, Modelle, Logs
- `.ai/`  
  Architektur-/Kontextdokumente, Betriebsleitlinien und Guidelines

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

6. Standardpfad (host-freundlich, empfohlen):
`make real-run-short` oder `make real-run-continue`

Hinweis zu Continue-Priorität und Stabilitäts-Gates:
- `make real-run-continue` verwendet als Startpunkt ausschließlich den aktuell promoteten Adapter aus `data/runs/LATEST_OK_ADAPTER_ID`.
- Falls kein promoteter Adapter vorhanden ist oder der referenzierte Adapter ungültig ist, greift ein deterministischer Fallback auf `make real-run-short`.
- Vor Heavy-Steps greifen Single-Flight und Swap-Gates:
  - Single-Flight-Lock (`data/runs/LOCK`) verhindert parallele Train/Eval-Läufe.
  - Swap-Gate prüft `MemAvailable` und `SwapFree` vor Training/Eval.

7. Optional direkter Container-Start (nur bei gezieltem Debugging):
`docker compose -f docker/compose.yaml exec trainer bash`
`python src/scripts/train_lora.py --config configs/train_lora_3b_k80.yaml --dataset data/datasets/train.jsonl`

8. Logs ansehen (TensorBoard):
`tensorboard --logdir data/logs --host 0.0.0.0 --port 6006`

9. Status/Audit prüfen und optional stoppen:
`make run-status`
`make eval-val`
`make down`

## Output-Konventionen
- LoRA-Adapter: `data/models/<run-id>/`
- Trainingslogs: `data/logs/<run-id>/`
- Smoke-Run Status/Metadaten: `data/runs/smoke/report.txt`
- Smoke-Eval-Artefakte: `data/evals/smoke-*/`
- Letzter technischer Real-Run Pointer: `data/runs/LATEST_REALRUN_ID`
- Letzter fachlich freigegebener Adapter Pointer: `data/runs/LATEST_OK_ADAPTER_ID`
- Optional abgeleiteter Adapter-Pfad: `data/runs/LATEST_OK_ADAPTER_PATH`
- Letzte Promotionsentscheidung: `data/runs/LATEST_PROMOTION_SUMMARY.json`

## Hinweise zu K80
- Kleine Batchgrößen verwenden
- `max_seq_length` konservativ halten (Default: `384`, bei weiterem Speicher-/Swap-Druck auf `256`)
- `gradient_accumulation_steps` erhöht halten (Default-Pfad: `24`)
- Tokenisierung/Loader konservativ parallelisieren (`num_proc=1`, kleine Worker-Zahlen)
- Schwere Schritte über host-freundlichen Laufmodus ausführen (`scripts/run_nice.sh` via Make-Targets)

### Swap-Thrash Mitigation (verbindliche Reihenfolge)
1. Sequenzlänge reduzieren (`512 -> 384 -> 256`)
2. Danach `gradient_accumulation_steps` erhöhen/anpassen (`16 -> 24/32`) für stabileres Signal
3. Tokenisierungs-Parallelität niedrig halten (`num_proc=1`)
4. Erst danach weitere Hyperparameter ändern

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
  - Regression-Eval ergänzt:
    - Committed Regression-Set: `data/datasets/val.jsonl` (Schema mit `expected_contains`)
    - Dataset-Config: `configs/datasets/val_regression.yaml`
    - Eval-Skript: `src/scripts/eval_val.py`
    - Make-Target: `make eval-val`
    - Berichtspfad: `data/evals/<run-id>/val_report.json`
  - Nächster Gate-Status:
    - Ein längerer Real-Run ist freigegeben, weiterhin unter konservativen K80-Parametern und mit vollständiger Run-ID-/Artefaktprüfung.

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

## Regression-Eval Standard (committed)
- Val-Set im Repo: `data/datasets/val.jsonl`
- Eval-Konfiguration: `configs/datasets/val_regression.yaml`
- Ausführung:
  1. `make real-run-short` (falls kein aktueller Adapter vorliegt)
  2. `make eval-val`
- Ergebnisprüfung:
  - `val_report.json` vorhanden
  - Passrate und Fail-Cases im Report nachvollziehbar
  - Bei niedriger Passrate: gezielte Datensatz-/Prompt-Verbesserung statt Infrastrukturänderung

## Serving-Architektur (MVP, getrennt vom Training)
- Serving läuft als separater Docker-Compose-Stack über `docker/compose.serve.yaml`.
- Service-Name: `serve`
- Standard-Port: `8901`
- Health-Endpunkt: `/health`
- Inferenz-Endpunkt: `POST /v1/chat/completions`
- Optionaler Reload-Endpunkt: `POST /reload`
- Serving liest beim Start den freigegebenen Adapter aus `data/runs/LATEST_OK_ADAPTER_ID`.
- Aus dem Pointer wird deterministisch `data/models/<run-id>` abgeleitet.
- Serving nutzt **nicht** automatisch den letzten technischen Real-Run, sondern ausschließlich den zuletzt evaluierten und promoteten Adapter.
- Betriebsregel: Serving darf für den Nightly-Trainingszeitraum gestoppt bzw. neu gestartet werden; Parallelbetrieb mit Training ist für den MVP nicht erforderlich.

### Serving-Make-Targets
- `make serve-up`
- `make serve-down`
- `make serve-logs`
- `make serve-health`
- `make serve-reload`

### OpenClaw-Anbindung
- OpenClaw spricht den Serving-Service über die OpenAI-kompatible API an.
- Erwarteter Betriebsmodus: stabile Nutzung gegen den aktuell promoteten Adapter, keine direkte Kopplung an den Trainingscontainer.

## Promotion- und Pointer-Disziplin (verbindlich)
- Jeder Trainingslauf schreibt eine neue `run_id` und erzeugt einen neuen Adapter-Ordner.
- `LATEST_REALRUN_ID` dokumentiert den letzten technisch erfolgreichen Real-Run.
- `LATEST_OK_ADAPTER_ID` dokumentiert den letzten fachlich freigegebenen Adapter für Serving.
- Promotion erfolgt nur nach erfolgreicher Regression-Eval.
- Wenn eine Promotion fehlschlägt oder die Schwellenwerte nicht erreicht werden, bleibt `LATEST_OK_ADAPTER_ID` unverändert.
- Folge: Serving bleibt stabil, auch wenn der neueste Trainingslauf fachlich nicht ausreichend ist.

### Aktuelle Start-Schwellenwerte für Promotion
- `pass_rate_exact_openbook >= 0.60`
- `avg_coverage_runbook_openbook >= 0.30`

### Audit-Artefakte der Promotion
- Referenzierter Kandidat: `data/runs/LATEST_REALRUN_ID`
- Letzter Eval-Run Pointer: `data/runs/LATEST_EVAL_RUN_ID`
- Promotionszusammenfassung: `data/runs/LATEST_PROMOTION_SUMMARY.json`

## Nightly-Run Zielablauf (Sonntag, MVP)
Verbindliche Reihenfolge:
1. `make preflight`
2. `make lock-status`
3. `make check-single-flight`
4. `make validate-val`
5. `make prepare-dataset-augmented`
6. Trainingsstart:
   - `make real-run-continue`, wenn `LATEST_OK_ADAPTER_ID` auf einen gültigen Adapter zeigt
   - sonst `make real-run-short`
7. `make eval-val`
8. `make promote-latest-ok`
9. Wenn ein neuer Adapter promotet wurde:
   - Serving wird neu gestartet
10. `make retention-clean`

### Nightly-Betriebsregeln
- Es wird nie ein bestehender Adapter-Ordner überschrieben.
- Continue-Training erfolgt ausschließlich vom letzten promoteten Adapter.
- Promotion ist von Eval-Erfolg abhängig.
- Serving wird nur bei neuer Promotion aktualisiert.
- Retention muss mindestens `LATEST_REALRUN_ID` und `LATEST_OK_ADAPTER_ID` schützen.

## Vault-Dataset-Generierung (15 Dokumentation)
- Quelle (Host): `/mnt/qnap/Obsidian_Vaults/Work/0 Seeds/15 Dokumentation/`
- Mount im Container (read-only): `/vault/15_Dokumentation`
- Workflow:
  1. `make up`
  2. `make prepare-dataset-vault`
- Betriebsmodus:
  - Ausführung host-freundlich über `scripts/run_nice.sh` (nice/ionice)
  - Vor/Nachlauf-Quickfacts werden protokolliert (Zeit, Uptime, Mem/Swap, Disk)
- Zielartefakte:
  - Trainingsdataset: `data/datasets/train.jsonl`
  - Laufbericht: `data/datasets/prepare_report.json`

### Acceptance Checks (verbindlich)
- `data/datasets/train.jsonl` wird erzeugt und ist UTF-8 JSONL (eine Zeile = ein JSON-Objekt)
- Schema pro Zeile: `{"instruction":"...","input":"...","output":"..."}`
- Determinismus:
  - Dateireihenfolge sortiert
  - reproduzierbare Extraktionslogik ohne LLM
- Secret-Redaction aktiv:
  - keine Treffer auf Schlüsselwörter wie `TOKEN`, `API_KEY`, `SECRET`, `PASSWORD`, `BEGIN PRIVATE KEY`, `OPENAI`, `PAPERLESS_TOKEN`, `HF_TOKEN`
- Laufstatistik im Report enthalten:
  - Anzahl `.md` Dateien gefunden/gescannt
  - Anzahl Sections gescannt
  - Anzahl Samples geschrieben
  - Top-Skip-Gründe

## Host-freundlicher Laufmodus (neu, Betriebsstandard)
- Schwere Make-Targets laufen prioritätsgesenkt, um Host-Bedienbarkeit zu erhalten:
  - `prepare-dataset-vault`
  - `real-run-short`
  - `real-run-continue`
  - `prepare-dataset` / `smoke-train` / `eval-val` (ebenfalls priorisiert)
- Optionaler CPU-Cap verfügbar: `make limit-cpu` (Container-Update auf feste CPU-Obergrenze)
- Optionales Host-Recovery-Target verfügbar: `make swap-reset`
  - Guard: nur ausführen, wenn `MemAvailable` ausreichend hoch ist (Schwellwertprüfung), sonst Warnung und Skip.
- Memory-Pressure wird als Warnsignal geführt (nicht blockierend), OOM-Diagnostik erfolgt best-effort bei Fehlern.

## Single-Flight Lock + Swap-Gates (neu)
- Single-Flight-Lock:
  - Lockfile: `data/runs/LOCK`
  - Verhalten: Wenn Lock aktiv ist, brechen `real-run-short`, `real-run-continue`, `eval-val` und `nightly-run` mit `already_running` ab.
  - Betriebsziele: keine parallelen Heavy-Runs, weniger RAM-/Swap-Spitzen.
- Swap-Gates:
  - Vor Training (`real-run-*`): Prüfung von `MemAvailable` und `SwapFree`; bei kritischem Zustand wird zunächst `swap-reset` versucht, danach Abbruch falls weiterhin kritisch.
  - Vor Eval (`eval-val`): gleiche Prüfung; bei weiterhin kritischem Zustand wird Eval übersprungen (non-blocking Policy bleibt erhalten).
- Lock-Operations:
  - Status prüfen: `make lock-status`
  - Manuelle Recovery bei stale Lock: `make lock-clear` (nur bewusst und kontrolliert verwenden).

## Retention- und Run-Pointer-Disziplin (neu)
- `retention-clean` schützt die in `data/runs/LATEST_REALRUN_ID` referenzierte Run-ID vor versehentlichem Prune (insb. `data/models` und `data/logs`).
- Nach Retention wird der Pointer validiert:
  - zeigt `LATEST_REALRUN_ID` auf keinen vorhandenen Adapter mehr, wird automatisch auf den neuesten verfügbaren gültigen Adapter (`adapter_config.json` vorhanden) repariert.
- Ziel: `make run-status` und `make eval-val` bleiben auch nach Retention lauffähig.

## Notfall-Runbook bei anhaltendem Speicher-/Swap-Druck
1. Nicht-kritische Services stoppen (z. B. TensorBoard/Serving), um RAM und I/O zu entlasten.
2. `swap-reset` nur bei ausreichendem `MemAvailable` ausführen.
3. Falls Druck dauerhaft hoch bleibt: Swap temporär vergrößern und anschließend Trainingsprofil weiter entschärfen (`max_seq_length`, Parallelität, Workload).
4. Grundsatz: Swap ist Stabilitäts-Puffer, keine Dauerlösung für regulären Betrieb.

## Nächster Ausbauschritt
Self-Edit-Workflow (SEAL-inspiriert) über `src/scripts/generate_self_edits.py` und `src/datasets/schemas/self_edit.schema.json` schrittweise produktionsnah ausbauen.