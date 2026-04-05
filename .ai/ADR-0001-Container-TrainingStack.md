# ADR-0001: Containerized Training Stack und Version-Pinning-Strategie

- **Datum:** 2026-04-05
- **Status:** Accepted
- **Entscheider:** Projektmaintainer `llm-homelab-training`
- **Geltungsbereich:** Lokale Trainingsumgebung (LoRA/Fine-Tuning, 3B-Modellklasse) auf NVIDIA K80
- **Betroffene Artefakte:** `docker/Dockerfile`, `docker/requirements.txt`, `docker/compose.yaml`, `configs/*`

---

## 1. Kontext

Das Projekt benötigt eine **reproduzierbare lokale Trainingsumgebung** für LoRA/Fine-Tuning ohne Cloud-Abhängigkeit.  
Randbedingungen:

1. Zielhardware ist u. a. **NVIDIA Tesla K80** (ältere GPU-Architektur, begrenzter VRAM, kein praktischer bf16-Standardpfad).
2. Reproduzierbarkeit hat Priorität vor maximaler Performance.
3. Die Umgebung muss interaktiv und iterativ nutzbar sein (Debugging, Training, Evaluation im selben Container-Workflow).
4. Keine Secrets im Repository.
5. Abhängigkeiten müssen deterministisch installierbar sein.

---

## 2. Entscheidung

### 2.1 Container-Base-Image

Wir verwenden als Basis:

- `nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu22.04`

Begründung:

- Die Host-Baseline ist bewusst eingefroren (`NVIDIA Driver 470.256.02`, CUDA Runtime laut `nvidia-smi` `11.4`).
- Für diese Treiberklasse ist ein `cu113`-Stack reproduzierbar kompatibel; `cu118` führte zu CUDA-Initialisierungsfehlern in PyTorch trotz sichtbarer GPU in `nvidia-smi`.
- Der gewählte Stand priorisiert Stabilität auf Tesla K80 (Kepler, sm_37) vor Aktualität.

### 2.2 Python-Dependency-Strategie

Wir verwenden:

- `pip` + `docker/requirements.txt`
- harte Versions-Pins für Kernbibliotheken (z. B. `torch`, `transformers`, `datasets`, `accelerate`, `peft`, `tensorboard`)

Beispielprinzip:

- `torch==1.12.1+cu113` über offiziellen PyTorch CUDA-Index
- keine unkontrollierten Floating-Versionen (`>=` ohne Obergrenze) für Kernkomponenten

### 2.3 Compose-Betriebsmodell

`docker/compose.yaml` stellt einen Service `trainer` bereit mit:

- `working_dir: /workspace`
- Mounts:
  - `../src -> /workspace/src`
  - `../configs -> /workspace/configs`
  - `../data -> /workspace/data`
- GPU-Passthrough (`gpus: all`) plus NVIDIA/CUDA-Umgebungsvariablen
- Default-Command als langlebiger Interaktivmodus (`sleep infinity`)

### 2.4 Optionalkomponenten

`bitsandbytes` wird **nicht** als Standardabhängigkeit erzwungen, sondern nur optional dokumentiert.  
Grund: Kompatibilitätsrisiken auf älterer GPU-/Treiberkombination.

---

### 2.5 Verifizierte Kompatibilitätsentscheidung (K80 / Driver 470)

Im Betrieb wurde folgender Fehler reproduzierbar beobachtet:

- `nvidia-smi` im Container erkennt K80 korrekt,
- PyTorch mit `2.1.2+cu118` meldet jedoch `torch.cuda.is_available() == False`.

Daraus wurde als verbindliche Entscheidung abgeleitet:

1. Downgrade auf `cu113`-kompatiblen Stack (`torch==1.12.1+cu113`).
2. Beibehaltung der eingefrorenen Host-Baseline (kein Treiber-/CUDA-Upgrade).
3. Jede Abweichung nur über Ausnahmefreigabe mit dokumentiertem Rollback-Plan.

## 3. Pinning-Policy (verbindlich)

### 3.1 Was wird gepinnt?

Verbindlich zu pinnen:

1. Base-Image inkl. Tag (`nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04`)
2. Python-Paketversionen in `docker/requirements.txt`
3. Bootstrapping-Tooling (`pip`, `setuptools`, `wheel`) im Dockerfile
4. Trainingsrelevante Defaults in `configs/` (z. B. Precision, Batch, GradAccum, SeqLen)

### 3.2 Was darf variabel bleiben?

1. Laufzeitdaten unter `data/` (Model-Artefakte, Logs, Datasets)
2. Modellname und Dataset-Pfad per CLI/Config-Override
3. Host-spezifische `.env`-Werte (`CUDA_VISIBLE_DEVICES`, lokale Caches)

### 3.3 Änderungsprozess bei Versionsupdates

Ein Update von Base-Image oder Kernpaketen ist nur zulässig mit:

1. dokumentierter Begründung (Kompatibilität, Security, Bugfix)
2. aktualisiertem Hinweis in Doku (`README`, `TROUBLESHOOTING_K80`, ggf. weitere ADR)
3. Smoke-Validierung:
   - Container-Build erfolgreich
   - CUDA in PyTorch verfügbar
   - mindestens ein kurzer Trainingslauf startbar

---

## 4. Begründung (Trade-offs)

### Vorteile

1. **Hohe Reproduzierbarkeit** durch harte Versionierung.
2. **Niedrige Setup-Varianz** zwischen Hosts mit NVIDIA-Stack.
3. **Gute Auditierbarkeit**, da Laufkontext klar aus Image + Requirements + Config rekonstruierbar ist.
4. **Cloud-unabhängig** und lokal kontrollierbar.

### Nachteile

1. Weniger flexibel bei schnellen Upgrades neuer Modell-Stacks.
2. Höherer Pflegeaufwand für explizite Versionserhöhungen.
3. Potenziell geringerer Performance-Fortschritt gegenüber aggressiv aktuellen Stacks.
4. K80 bleibt hardwarebedingt langsam; Stack-Entscheidung löst kein Throughput-Grundproblem.

---

## 5. Konsequenzen

1. Reproduzierbarkeit ist primäres Qualitätskriterium für Infrastrukturänderungen.
2. Neue Features, die Pinning oder K80-Stabilität gefährden, sind nachrangig.
3. Experimente mit optionalen Komponenten (z. B. Quantisierungspakete) erfolgen isoliert und standardmäßig deaktiviert.
4. Fehlerdiagnose priorisiert zunächst **Kompatibilitätsschicht** (Driver/CUDA/PyTorch), dann Hyperparameter.

---

## 6. Alternativen (bewertet)

### A) `python:<version>` als Base-Image + nachträgliche CUDA-Integration

- **Verworfen**, da höhere Komplexität und größere Fehlerfläche bei GPU-Laufzeitkopplung.

### B) Conda-basierter Stack

- **Aktuell nicht gewählt**, da zusätzlicher Layer und größerer Reproduzierungs-/Pflegeaufwand im Zielkontext.

### C) Ungepinntes Latest-Tracking

- **Verworfen**, da nicht auditierbar genug und zu hohe Drift-Risiken.

### D) Alpine-basierter Runtime-Stack (musl)

- **Verworfen**, da CUDA-/PyTorch-Ökosystem für diesen Legacy-K80-Stack primär auf glibc-basierte Distributionen (Ubuntu/Debian) ausgerichtet ist.
- Alpine (musl) erhöht das Risiko für Wheel-/Binary-Inkompatibilitäten, zusätzliche Source-Builds und instabile Reproduzierbarkeit.
- Für den Betriebszweck (K80 + eingefrorene Treiber/CUDA-Baseline) ist ein Ubuntu-basierter CUDA-Stack der robustere, auditierbare Standardpfad.

---

## 7. Security- und Compliance-Hinweise

1. Keine Secrets/Tokens im Repository.
2. `.env` bleibt lokal und wird nicht committed.
3. Modell- und Datensatzlizenzen müssen vor produktiver Nutzung geprüft werden.
4. Trainingsdaten mit potenziell sensitiven Inhalten dürfen nur nach rechtlicher Prüfung verwendet werden.

---

## 8. Verifikation der Entscheidung (Checkliste)

Vor Freigabe eines Stack-Updates:

1. `docker compose` Build erfolgreich
2. GPU im Container sichtbar
3. `torch.cuda.is_available()` liefert `True`
4. Kurzlauf von `train_lora.py` startet ohne Stack-Fehler
5. Logs und Outputs landen in den definierten Pfaden unter `data/`

---

## 9. Gültigkeit und Review

- Diese ADR ist bis auf Widerruf gültig.
- Review-Anlass:
  1. Wechsel der Zielhardware (z. B. von K80 auf neuere Architektur)
  2. notwendige CUDA-/Treiber-Migration
  3. sicherheitsrelevante Änderungen am Base-Image oder Kernabhängigkeiten