# TROUBLESHOOTING_K80

## Zweck und Scope

Dieses Dokument beschreibt typische Probleme beim LoRA/Fine-Tuning auf **NVIDIA Tesla K80** in der lokalen Container-Umgebung und liefert reproduzierbare Prüf- und Gegenmaßnahmen.

Zielpriorität:

1. **Stabiler Lauf**
2. **Reproduzierbarkeit**
3. **Durchsatzoptimierung**

---

## 1) Typische Hardware-/Runtime-Limits der K80

Die K80 ist eine ältere GPU-Generation (Kepler) mit klaren Grenzen für modernes LLM-Training.

### 1.1 VRAM-Limit / Out-of-Memory (OOM)

**Symptome**
- `CUDA out of memory`
- Prozessabbruch beim Laden des Modells
- Abbruch beim ersten Backward-Pass

**Häufige Ursachen**
- Zu große `max_seq_length`
- Zu hohe `per_device_train_batch_size`
- Zu große LoRA-Konfiguration (`r`, mehr Target-Module)
- Zu viele parallele Worker/Prefetches

**Sofortmaßnahmen (Reihenfolge)**
1. `per_device_train_batch_size = 1`
2. `gradient_accumulation_steps` erhöhen (z. B. 16, 32)
3. `max_seq_length` reduzieren (512 → 384 → 256)
4. `gradient_checkpointing = true`
5. LoRA-Rank reduzieren (`r: 8` statt `16`)
6. Nur notwendige `target_modules` aktiv lassen

---

### 1.2 Langsame Trainingsschritte

**Symptome**
- Sehr hohe `seconds/step`
- GPU-Auslastung niedrig oder stark schwankend

**Häufige Ursachen**
- CPU/Data-Loader bottleneck
- Zu häufiges Logging/Speichern
- Sehr kleine Batch + hoher Overhead pro Step
- Ältere Architektur mit begrenzter Rechenleistung

**Mitigations**
- `dataloader_num_workers` moderat halten (z. B. 2)
- `logging_steps` erhöhen (weniger häufig loggen)
- `save_steps` erhöhen (weniger häufig checkpointen)
- Datensatz vorab bereinigen/normalisieren, I/O minimieren
- Erst Stabilität sichern, danach Performance-Tuning

---

### 1.3 Precision-/Numerik-Probleme (fp16/bf16)

**Symptome**
- `nan`/`inf` im Loss
- Instabile Lernkurve
- Lauf bricht bei Mixed Precision ab

**Wichtig**
- K80 unterstützt in der Praxis typischerweise **fp16**, aber **bf16** nicht sinnvoll nutzbar.

**Mitigations**
- `bf16 = false`
- `fp16 = true` (nur wenn stabil)
- Lernrate senken (z. B. `2e-4` → `1e-4`)
- `max_grad_norm = 1.0` beibehalten
- Bei hartnäckiger Instabilität testweise CPU-Validierung kleiner Samples

---

## 2) Konfigurations-Baselines für K80

Empfohlene konservative Startwerte für MVP-LoRA auf ~3B:

- `per_device_train_batch_size: 1`
- `gradient_accumulation_steps: 16` (oder höher)
- `max_seq_length: 512` (bei OOM auf 384/256)
- `fp16: true`
- `bf16: false`
- `gradient_checkpointing: true`
- `evaluation_strategy: "no"` für erste stabile Trainingsläufe
- `save_steps`: nicht zu klein (z. B. 200+)

---

## 3) Kompatibilität CUDA / PyTorch prüfen

Da K80-Setups stark von Treiber/Runtime abhängen, muss die Kompatibilität explizit verifiziert werden.

### Betriebsregel: eingefrorene, bekannte stabile GPU-Baseline (verbindlich)

Für dieses Projekt gilt eine feste Betriebsbaseline:

- NVIDIA Driver: `470.256.02`
- CUDA Runtime (Host, `nvidia-smi`): `11.4`
- Ziel-GPU: `Tesla K80`

Diese Baseline ist als **stabil freigegeben** und wird **nicht aktualisiert**.  
Änderungen an Treiber/CUDA sind nur per expliziter Ausnahmefreigabe zulässig, da Stabilität und Reproduzierbarkeit priorisiert sind.

### 3.1 Platzhalter-Kompatibilitätsliste (vor produktivem Run konkretisieren)

| Komponente | Erwartungswert (Beispiel) | Status |
|---|---:|---|
| NVIDIA Driver (Host) | Muss zur verwendeten CUDA-Runtime passen | Manuell prüfen |
| CUDA Runtime (Container) | z. B. 11.8 | Manuell prüfen |
| PyTorch Build | CUDA-kompatibler Build (z. B. cu118) | Manuell prüfen |
| GPU-Erkennung | K80 sichtbar im Container | Manuell prüfen |

> Diese Liste ist absichtlich als kontrollierter Platzhalter gehalten. Exakte Werte sollen pro Host dokumentiert werden.

### 3.2 Verifikation im Container (empfohlene Checks)

1. **GPU sichtbar?**
   - `nvidia-smi`
   - Erwartung: K80 wird gelistet.

2. **CUDA in PyTorch aktiv?**
   - `python -c "import torch; print(torch.cuda.is_available())"`
   - Erwartung: `True`

3. **Welche CUDA-Version nutzt PyTorch?**
   - `python -c "import torch; print(torch.version.cuda)"`
   - Erwartung: Wert passend zur Build-Konfiguration.

4. **Wie viele CUDA-Devices sieht PyTorch?**
   - `python -c "import torch; print(torch.cuda.device_count())"`
   - Erwartung: `>= 1` bei aktiver GPU-Zuordnung.

5. **Welche GPU erkennt PyTorch?**
   - `python -c "import torch; print(torch.cuda.get_device_name(0))"`
   - Erwartung: K80-Name.

6. **bf16-Support vorhanden?**
   - `python -c "import torch; print(torch.cuda.is_bf16_supported())"`
   - Erwartung auf K80: typischerweise `False`.

#### Kompatibilitäts-Fix-Hinweis (wichtig)

Falls `nvidia-smi` im Container funktioniert, aber PyTorch trotzdem `torch.cuda.is_available() == False` meldet, liegt häufig ein **Treiber-/CUDA-Build-Mismatch** vor (CUDA-Initialisierung schlägt fehl, obwohl Geräte sichtbar sind).

Typisches Muster:
- `nvidia-smi`: GPU sichtbar
- `torch.cuda.device_count()`: ggf. `>= 1`
- `torch.cuda.is_available()`: `False`
- ggf. Fehler wie „No CUDA GPUs are available“ bei CUDA-Kontextinitialisierung

Reaktion:
1. PyTorch-Build auf zur Host-Baseline passenden CUDA-Build pinnen.
2. Container-CUDA-Basisimage auf kompatible Version ausrichten.
3. Erst nach erfolgreicher CUDA-Initialisierung (`is_available() == True`) Trainingsparameter anpassen.

#### Validierter Ist-Stand (2026-04-05)

Nach Anpassung auf den Legacy-kompatiblen Stack wurde der Container-Check erfolgreich verifiziert:

- `nvidia-smi` im Container: **OK**, 2x `Tesla K80` sichtbar
- `torch_version`: `1.12.1+cu113`
- `torch_cuda_version`: `11.3`
- `torch.cuda.is_available()`: `True`
- `torch.cuda.device_count()`: `1`
- `torch.cuda.get_device_name(0)`: `Tesla K80`
- `compute_capability_0`: `3.7`
- `bf16_supported`: `False` (erwartet auf K80)

Interpretation:
- Der CUDA-Initialisierungspfad für PyTorch ist funktionsfähig.
- Damit ist das frühere Mismatch-Symptom (`nvidia-smi` OK, `is_available=False`) für diese Baseline behoben.
- Der Parser-Warnhinweis zur Compute-Capability-Ausgabe ist für diese geprüfte Ausgabe behoben (`compute_capability_0` wird korrekt erkannt).

#### Smoke-Run Befunde (2026-04-05 bis 2026-04-06)

Im ersten vollständigen `make smoke` Lauf (2026-04-05) wurden drei relevante Probleme beobachtet und anschließend technisch behoben (Dependency-Pinning, Input-Grad-Fix, Fail-Fast-Gates im Makefile).

Im Folge-Run (2026-04-06) wurde `make smoke` erfolgreich abgeschlossen:
- Host-Preflight: erfolgreich (bekannte Host-Warnung zur Compute-Capability blieb bestehen)
- Container-GPU-Check: erfolgreich
- Smoke-Training: erfolgreich, Adapter-Artefakte geschrieben
- Smoke-Eval: erfolgreich, `predictions.jsonl` und `summary.json` vorhanden

1. **Trainingsteil: Dataset/FSSpec-Inkompatibilität**
   - Fehler:
     - `TypeError: can only concatenate tuple (not "str") to tuple`
   - Ort:
     - beim Aufruf von `load_dataset("json", data_files=...)` in `train_lora.py`
   - Einordnung:
     - kein GPU-/CUDA-Problem, sondern eine Python-Abhängigkeits-/Kompatibilitätsfrage im `datasets`/`fsspec`-Pfad.
   - Maßnahme (verbindlich gepinnt):
     - `datasets==2.14.0`
     - `fsspec==2023.6.0`
     - `pyarrow==12.0.1`
   - Zweck der Maßnahme:
     - Vermeidung der beobachteten `TypeError`-Inkompatibilität bei `load_dataset("json", ...)` im Legacy-K80-Stack.

2. **Trainingsteil: Backward-Fehler bei Gradient Checkpointing + LoRA**
   - Fehler:
     - `RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn`
   - Kontext:
     - trat im Smoke-Lauf nach erfolgreichem Dataset-Load während `trainer.train()` auf.
   - Ursache (technisch):
     - bei bestimmten Modell-/Torch-Kombinationen mit aktiviertem `gradient_checkpointing` und LoRA benötigen die Eingaben explizit aktivierte Gradienten.
   - Umgesetzte Abhilfe:
     - in `src/scripts/train_lora.py` wurde für den Checkpointing-Pfad die Aktivierung von Input-Gradienten ergänzt (`enable_input_require_grads()` bzw. Hook-Fallback auf Embeddings).

3. **Eval-Teil: fehlender Adapter nach fehlgeschlagenem Training**
   - Fehler:
     - `ValueError: Can't find 'adapter_config.json' at '/workspace/data/models/<run-id>'`
   - Ursache:
     - der Trainingsschritt ist zuvor fehlgeschlagen, daher wurde kein LoRA-Adapter geschrieben.
   - Folge:
     - Eval konnte den erwarteten Adapterpfad nicht laden.

#### Verbleibende Eval-Caveats nach erfolgreichem Smoke

Auch bei erfolgreichem Smoke bleiben folgende Punkte zu beachten:

1. **Smoke-Metriken sind kein Qualitätsnachweis**
   - Im erfolgreichen Smoke-Run wurden `exact_match_mean` und `token_f1_mean` mit `0.0` protokolliert.
   - Das ist bei extrem kleinem Toy-Dataset und kurzer Trainingsdauer erwartbar und kein Infrastrukturfehler.

2. **Warnung zur Sequenzlänge in Eval**
   - Hinweis: `Asking to truncate to max_length but no maximum length is provided ...`
   - Bewertung: nicht kritisch für den Smoke-Gate, aber für reproduzierbare Real-Evals sollte `max_length`/Prompt-Limits explizit gesetzt werden.

3. **Host-Warnung zur Compute-Capability**
   - Die Host-Prüfung kann weiterhin eine Warnung ausgeben, obwohl K80 korrekt erkannt und Container-CUDA funktionsfähig ist.
   - Für die Freigabe zählt der erfolgreiche Container-Torch-Check (`cuda_available=True`, Device K80, CC 3.7).

#### Validierung: erster kontrollierter Real-Run (2026-04-06)

Der erste kontrollierte Real-Run wurde erfolgreich abgeschlossen und bestätigt die Betriebsfähigkeit des aktuellen K80-Stacks über den Smoke-Umfang hinaus.

Run-Nachweis:
- `run_id`: `real-20260406T092832Z`
- Config: `configs/train_lora_3b_k80_short.yaml`
- Dataset: `data/datasets/train.jsonl`
- Status: `success`

Pflichtartefakte (vorhanden):
- `data/models/real-20260406T092832Z/adapter_config.json`
- `data/models/real-20260406T092832Z/final_metrics.json`
- `data/logs/real-20260406T092832Z/`

Gemeldete Trainingskennzahlen:
- `global_step`: `60`
- `train_loss`: `1.9559472759564718`
- `train_runtime`: `1898.2539s`
- `train_steps_per_second`: `0.032`
- `train_samples_per_second`: `0.506`

Interpretation:
- Der kontrollierte Kurzlauf ist als technisch erfolgreich zu bewerten.
- Die Laufstabilität auf K80 ist für den aktuellen Stack bestätigt.
- Ein längerer Real-Run ist freigegeben, weiterhin unter konservativen K80-Parametern und mit vollständiger Artefaktprüfung.

#### Wichtige Betriebsregel für Smoke-Ergebnisse

Der `Makefile`-Smoke-Workflow ist auf Fail-Fast gehärtet:
- `smoke-train` bricht bei Trainingsfehlern sofort ab.
- Zusätzlich wird das Vorhandensein von `data/models/<run-id>/adapter_config.json` verpflichtend geprüft.
- `smoke-infer` prüft vor Eval erneut das Adapter-Artefakt und nach Eval das Vorhandensein von `data/evals/<run-id>/summary.json`.

Bewertung eines Smoke-Runs:
- Ein Smoke-Run gilt nur dann als **bestanden**, wenn **alle** Kriterien erfüllt sind:
  1. Training ohne Traceback abgeschlossen
  2. Kein Backward-Fehler vom Typ `does not require grad` / fehlende `grad_fn`
  3. Adapter-Artefakte vorhanden (`data/models/<run-id>/adapter_config.json`)
  4. Eval ohne Traceback abgeschlossen
  5. `data/evals/<run-id>/summary.json` vorhanden
- Ein einzelnes Abschluss-Log ohne diese Artefakte ist **nicht** ausreichend als Qualitäts- oder Stabilitätsnachweis.

Wenn einer dieser Checks fehlschlägt, zuerst Treiber/Container-Runtime/PyTorch-Build ausrichten, bevor Trainingsparameter angepasst werden.

---

## 4) Fehlerbilder und deterministische Reaktion

| Fehlerfall | Detektion | Reaktion | Nutzerinfo |
|---|---|---|---|
| CUDA OOM beim Start | Exception beim Model Load | `max_seq_length` senken, Batch=1, ggf. kleineres Base-Modell | „Modell passt nicht in VRAM; Konfigurationsreduktion notwendig.“ |
| CUDA OOM während Backward | Exception im Training Step | `gradient_accumulation_steps` erhöhen, Checkpointing an, LoRA-Rank senken | „Speicherverbrauch pro Step zu hoch; mikro-batching angepasst.“ |
| GPU nicht sichtbar | `nvidia-smi` leer/Fehler | Container-GPU-Passthrough prüfen, Host-Treiber prüfen | „GPU im Container nicht verfügbar; Training auf GPU nicht möglich.“ |
| `torch.cuda.is_available() == False` | Python Check | PyTorch CUDA-Build prüfen, Container Image prüfen | „CUDA in PyTorch nicht aktiv; CPU-Fallback wäre sehr langsam.“ |
| NaN/Inf Loss | Training Logs | Lernrate senken, Daten prüfen, Precision prüfen | „Numerische Instabilität erkannt; konservative Hyperparameter gesetzt.“ |
| Sehr langsame Steps | Logs (sec/step), niedrige GPU-Auslastung | Logging/Checkpoint-Intervall erhöhen, Loader optimieren | „Durchsatz limitiert; Overhead reduziert.“ |

---

## 5) Daten- und Prompt-bezogene Ursachen

Nicht jede Instabilität ist hardwarebedingt.

**Prüfen**
- JSONL sauber (eine Zeile = ein Objekt)
- Pflichtfelder vorhanden: `instruction`, `output`
- Extrem lange Samples filtern/clippen
- Prompt-Template konsistent halten

**Warum relevant**
- Ausreißer in Textlänge verursachen Speicherpeaks
- Inkonsistente Daten erhöhen Loss-Varianz und Instabilität

---

## 6) Minimaler Recovery-Plan bei fehlgeschlagenem Run

1. Letzten Lauf als „failed“ markieren (Run-ID behalten, Logs sichern)
2. Nur **eine** Variable pro Wiederholungsrun ändern
3. Priorisierte Anpassung:
   - `max_seq_length` runter
   - dann `gradient_accumulation_steps` rauf
   - dann Lernrate runter
4. Kurzen Smoke-Run mit wenigen Samples fahren
5. Erst danach vollständigen Lauf starten

Damit bleibt das Tuning nachvollziehbar und auditierbar.

---

## 7) Audit-Checkliste pro Training-Run

Vor jedem Run dokumentieren:

- Run-ID
- Basis-Modellname
- Datensatzpfad + optional Hash
- Relevante Hyperparameter (`batch`, `grad_accum`, `seq_len`, `lr`, `fp16/bf16`)
- Container-Image/Tag
- Treiber-/CUDA-/Torch-Infos aus den Verifikationschecks
- Feste GPU-Baseline: Driver `470.256.02`, CUDA Runtime `11.4`
- Abweichung von der Baseline? (`nein/ja`) inkl. Ausnahmefreigabe-Referenz

Nach jedem Run dokumentieren:

- Erfolg/Fehlerstatus
- Fehlerklasse (OOM, Kompatibilität, Numerik, Daten)
- Dauer, Steps, letzte Metriken
- Nächste geplante Parameteränderung

---

## 8) Kurzfassung: empfohlene Standardreaktionen

- **OOM** → erst `seq_len` runter, dann `grad_accum` rauf
- **Instabiler Loss** → LR runter, `bf16` aus, Daten prüfen
- **GPU nicht verfügbar** → Runtime/Driver/Passthrough zuerst reparieren
- **Zu langsam** → Logging/Checkpointing drosseln, konservativ optimieren

Reproduzierbarkeit hat Vorrang vor aggressiver Optimierung.