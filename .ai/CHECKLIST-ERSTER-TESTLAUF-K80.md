# CHECKLISTE ERSTER TESTLAUF K80

## Dokumentkontrolle
- Status: Verbindlich
- Version: 1.0
- Datum: 2026-04-05
- Geltungsbereich: `llm-homelab-training` auf Host mit NVIDIA Tesla K80
- Priorität: Reproduzierbarkeit und Stabilität vor Performance

---

## 1) Kritische Betriebsregel (No-Update-Policy)

Vor jedem Lauf bestätigen:

- [ ] NVIDIA Driver bleibt auf `470.256.02`
- [ ] CUDA Runtime (Host, `nvidia-smi`) bleibt auf `11.4`
- [ ] Keine Treiber-/CUDA-Updates ohne explizite Ausnahmefreigabe inkl. Rollback-Plan
- [ ] Abweichungen werden als No-Go behandelt

---

## 2) Preflight Host (Pflicht-Gate)

### 2.1 In Projekt wechseln
- [ ] `cd /opt/projects/llm-homelab-training`

### 2.2 Grundprüfung
- [ ] `make preflight`
- [ ] Keine harten Fehler im Output

### 2.3 Host-GPU Prüfung
- [ ] `./scripts/check_gpu.sh --host-only --compose-file docker/compose.yaml --service trainer`
- [ ] `nvidia-smi` funktioniert
- [ ] Tesla K80 wird erkannt
- [ ] Warnungen dokumentieren, harte Fehler sofort stoppen

**No-Go Bedingungen**
- [ ] Host-GPU nicht sichtbar
- [ ] Docker/Compose nicht verfügbar
- [ ] Pflichtdateien fehlen

---

## 3) Container Runtime + GPU (Pflicht-Gate)

### 3.1 Build und Start
- [ ] `make build`
- [ ] `make up`

### 3.2 Container-GPU
- [ ] `make check-gpu-container`
- [ ] Torch meldet CUDA verfügbar
- [ ] GPU-Device im Container sichtbar

**No-Go Bedingungen**
- [ ] Container sieht keine GPU
- [ ] Torch CUDA unavailable
- [ ] Runtime-Mismatch/Compose-Fehler

---

## 4) Datenprüfung vor Training

### 4.1 Standard-LoRA Daten
- [ ] `data/datasets/train.jsonl` vorhanden
- [ ] `data/datasets/val.jsonl` vorhanden
- [ ] Format je Zeile: `{"instruction":"...","input":"...","output":"..."}`
- [ ] Pflichtfelder `instruction` und `output` nicht leer

### 4.2 Optional normalisieren
- [ ] `python src/scripts/prepare_dataset.py --input data/datasets/train.jsonl --output data/datasets/train.normalized.jsonl`

### 4.3 Self-Edit Daten (optional für spätere Phase)
- [ ] `data/datasets/self_edit_train.jsonl` vorhanden
- [ ] `data/datasets/self_edit_val.jsonl` vorhanden
- [ ] Auditfelder vorhanden (`event_id`, `event_ts`, `actor_type`, `pipeline`, `base_model`)

---

## 5) Smoke-Run (Pflicht vor erstem Real-Run)

### 5.1 Smoke starten
- [ ] `make smoke`

### 5.2 Smoke-Artefakte prüfen
- [ ] `data/runs/smoke/report.txt` existiert
- [ ] `data/models/smoke-*` erzeugt
- [ ] `data/evals/smoke-*` erzeugt
- [ ] Kein harter Fehler im Ablauf

**No-Go Bedingungen**
- [ ] Smoke bricht vor Training/Eval ab
- [ ] OOM bereits im Smoke-Minimallauf
- [ ] Keine Artefakte erzeugt

---

## 6) Erster kurzer Real-Run (kontrolliert)

### 6.1 Konservative Konfiguration prüfen
- [ ] Config: `configs/train_lora_3b_k80.yaml`
- [ ] `per_device_train_batch_size = 1`
- [ ] `fp16 = true`, `bf16 = false`
- [ ] `gradient_checkpointing = true`
- [ ] `max_seq_length` konservativ (bei OOM: 512 -> 384 -> 256)

### 6.2 Training starten
- [ ] `python src/scripts/train_lora.py --config configs/train_lora_3b_k80.yaml --dataset data/datasets/train.jsonl`

### 6.3 Ergebnis prüfen
- [ ] Adapter unter `data/models/<run-id>/`
- [ ] Logs unter `data/logs/<run-id>/`
- [ ] Keine wiederholten OOM-/CUDA-Abbrüche

---

## 7) Mini-Evaluation (Pflicht nach erstem Run)

- [ ] `python src/scripts/eval.py --dataset data/datasets/val.jsonl --base-model facebook/opt-2.7b --adapter-path data/models/<run-id> --output-dir data/evals/<run-id>`
- [ ] `predictions.jsonl` vorhanden
- [ ] `summary.json` vorhanden
- [ ] Ergebnisse plausibel (kein leerer Output-Stream)

---

## 8) Reaktionsregeln bei Fehlern

- [ ] Pro Wiederholungsrun nur **einen** Parameter ändern
- [ ] OOM-Reihenfolge strikt einhalten:
  1. `max_seq_length` senken
  2. danach `gradient_accumulation_steps` erhöhen
  3. erst danach weitere Hyperparameter prüfen
- [ ] Treiber/CUDA nicht anfassen
- [ ] Fehlerklasse dokumentieren (GPU, Daten, Runtime, Modellzugriff)

---

## 9) Häufigste Startfehler (Prävention)

- [ ] Zu aggressive Sequenzlänge/Batchsize auf K80
- [ ] CUDA/Driver/Torch-Mismatch ignoriert
- [ ] JSONL-Schema driftet (fehlende/leere Pflichtfelder)
- [ ] Fehlende Run-Disziplin (kein sauberer run_id Bezug)
- [ ] Zu früher Start der Self-Edit-Orchestrierung vor stabiler Baseline

---

## 10) Run-Protokoll (auszufüllen)

- Datum/Zeit (UTC): __________________
- Operator: __________________
- Host: __________________
- Driver/CUDA bestätigt (470.256.02 / 11.4): [ ] Ja  [ ] Nein
- Commit-Stand: __________________
- Base Model: __________________
- Dataset: __________________
- Config: __________________
- Run-ID: __________________
- Ergebnis: [ ] success  [ ] failed
- Fehlerklasse (falls failed): __________________
- Nächste Maßnahme: __________________
- Freigabe für längeren Lauf: [ ] Ja  [ ] Nein