# GPU-DATENBLATT-K80-HOMELAB

## Dokumentmetadaten
- **Status:** Verbindlich
- **Version:** 1.0
- **Datum:** 2026-04-05
- **Projekt:** `llm-homelab-training`
- **Scope:** Lokaler Betrieb auf NVIDIA Tesla K80
- **Owner:** Sandro

---

## 1) Verbindliche Betriebsregel (Frozen Baseline)

### No-Update-Policy (kritisch)
Für diesen Host und dieses Projekt gilt:

1. **Keine Updates** von NVIDIA-Treiber.
2. **Keine Updates** der CUDA-Baseline.
3. Änderungen sind nur per **expliziter Ausnahmefreigabe** zulässig (inkl. Risikoanalyse + Rollback-Plan).

### Freigegebene stabile Baseline
- **NVIDIA Driver (Host):** `470.256.02`
- **CUDA Runtime laut `nvidia-smi`:** `11.4`
- **GPU-Modell:** `Tesla K80`

Begründung:
- Diese Kombination ist als letzte stabile Version für den Betrieb freigegeben.
- Reproduzierbarkeit und Stabilität haben Vorrang vor Upgrades.

---

## 2) Inventory / Hardware-Identität

| Feld | Wert |
|---|---|
| Hostname | `ars1992-docker` |
| GPU Typ | NVIDIA Tesla K80 |
| Anzahl erkannter GPUs | 2 |
| VRAM pro GPU | 11441 MiB |
| Ziel-Compute-Capability | 3.7 |

Hinweis:
- Bei Warnungen zur Compute Capability ist die tatsächliche Identität immer gegen `nvidia-smi -L` und Container-Torch-Checks zu verifizieren.

---

## 3) Runtime- und Container-Baseline

| Feld | Wert |
|---|---|
| Source-of-Truth Projektpfad | `/opt/projects/llm-homelab-training` |
| Container-Orchestrierung | Docker Compose |
| Preflight-Check | `make preflight` |
| Host-GPU-Check | `./scripts/check_gpu.sh --host-only --compose-file docker/compose.yaml --service trainer` |
| Container-GPU-Check | `make check-gpu-container` |

---

## 4) K80 Betriebsgrenzen (Trainingsstart)

| Bereich | Vorgabe |
|---|---|
| Precision | `fp16=true`, `bf16=false` |
| Start Batch Size | `per_device_train_batch_size=1` |
| Sequenzlänge | konservativ starten (`512`, bei OOM auf `384/256`) |
| Gradient Checkpointing | aktiv |
| Priorität | Stabilität/Reproduzierbarkeit vor Durchsatz |

Standardreaktion bei OOM:
1. `max_seq_length` reduzieren
2. `gradient_accumulation_steps` erhöhen
3. erst danach weitere Parameter ändern

---

## 5) Pflicht-Gates vor längeren Runs

Vor jedem produktiven Lauf müssen alle Punkte erfüllt sein:

- [ ] `make preflight` erfolgreich
- [ ] `make check-gpu-container` erfolgreich
- [ ] optional `make smoke` erfolgreich
- [ ] Baseline unverändert (`Driver=470.256.02`, `CUDA Runtime=11.4`)

No-Go:
- GPU nicht sichtbar im Container
- Torch meldet `cuda.is_available() = False`
- Abweichung von Baseline ohne Ausnahmefreigabe

---

## 6) Monitoring & Fehlerindikatoren

Während des Betriebs beobachten:
- CUDA OOM
- `nan`/`inf` im Loss
- stark schwankende oder extrem langsame Steps
- GPU/Device plötzlich nicht mehr verfügbar

Bei Auffälligkeiten:
1. Lauf stoppen
2. Status + Fehlertyp dokumentieren
3. nur **einen** Parameter pro Retry ändern

---

## 7) Change-Control (Ausnahmeverfahren)

Änderungen an Treiber/CUDA nur mit vollständig dokumentierter Freigabe:

1. Änderungsgrund
2. Risikoanalyse
3. Rollback-Plan
4. Wartungsfenster
5. Post-Change Smoke-Test erfolgreich
6. kurzer Trainings- und Eval-Lauf erfolgreich

Ohne diese 6 Punkte: **Änderung unzulässig**.

---

## 8) Auditpflicht pro Lauf

Pflichtfelder im Run-Protokoll:
- `run_id`
- Datum/Zeit (UTC)
- Commit-Stand
- genutzte Config
- Dataset + (wenn möglich) Hash
- Base Model + Adapter
- Ergebnis (`success/failed`)
- Fehlerklasse (falls fehlgeschlagen)
- Baseline-Abgleich (`unchanged` / `deviation` + Freigabereferenz)

---

## 9) Verweise

- Projekt-Troubleshooting: `docs/TROUBLESHOOTING_K80.md`
- Backup-Policy: `docs/BACKUP_POLICY.md`
- Erste-Testlauf-Checkliste: `.ai/CHECKLIST-ERSTER-TESTLAUF-K80.md`

---

## 10) Freigabevermerk

Diese Datei ist verbindliche Betriebsgrundlage für GPU-relevante Entscheidungen im Projekt `llm-homelab-training`.
Abweichungen sind nur über das Ausnahmeverfahren zulässig.