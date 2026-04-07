# SANDRO.md — Projektübergreifendes Arbeitsgedächtnis

## Zweck
Dieses Dokument speichert projektübergreifende Arbeitsprinzipien, Entscheidungen und Zusammenarbeitserfahrungen.
Ziel ist, über mehrere Sessions konsistent, schneller und auditierbar zu arbeiten.

---

## Nutzerprofil (persistente Präferenzen)

- Rolle/Erwartung: IT-Projektplaner- und Architektursicht statt reiner Feature-Implementierung.
- Fokus: Enterprise-Software, Datenmanagement, Compliance, Security, Auditierbarkeit.
- Denkweise: Systemisch, formal, nachvollziehbar, dokumentationsorientiert.
- Prioritäten:
  1. Reproduzierbarkeit
  2. Lokaler Betrieb ohne Cloud-Zwang
  3. Saubere Strukturierung (Domänentrennung, IDs, Fehlerzustände, Audit-Trail)
- Kommunikationsstil:
  - präzise, ohne Marketing-Sprache
  - keine Floskeln, keine Emojis
  - Annahmen und Unsicherheiten explizit benennen

---

## Verbindliche Arbeitsweise (für zukünftige Sessions)

1. Immer mit kurzer, präziser Checkliste starten (3–7 Punkte).
2. Danach klare, nummerierte Schritte in logischer Reihenfolge.
3. Fehlende Informationen explizit als Annahme/Offene Frage markieren.
4. Jede Entität mit eindeutiger ID denken.
5. Jede Aktion auditierbar modellieren.
6. Fehler- und Sonderfälle deterministisch definieren.
7. Fachliche Domänen strikt trennen.

---

## Bisher bestätigte Qualitätskriterien

- „Commit-ready“ bedeutet:
  - Struktur vorhanden
  - Konfigurationen nachvollziehbar
  - Dokumentation konsistent
  - keine Secrets
- Doku ist Teil des Systems (nicht optional).
- Reproduzierbarkeit ist wichtiger als „fancy features“.

---

## Projektkontext-Memory

### Projekt: `llm-homelab-training`
- Ziel: reproduzierbare Container-Trainingsumgebung (LoRA/Fine-Tuning, 3B-Klasse) auf NVIDIA K80.
- Späterer Ausbau: SEAL-inspirierte Self-Edit-Pipeline.
- Betriebsmodus: lokal, ohne Cloud-Abhängigkeit.
- Wichtige Leitlinie: K80-Limits früh berücksichtigen (VRAM, Throughput, Precision-Kompatibilität).

---

## Was gut funktioniert hat

- Frühe Strukturierung in:
  - `docker/`, `src/`, `configs/`, `docs/`, `.ai/`
- Frühes Festlegen von:
  - Datenformat
  - Artefaktpfaden
  - Troubleshooting-Konzept
- Architekturentscheidungen in ADR-Form dokumentieren.

---

## Verbesserungsbedarf / Watchouts

- Bei YAML-Configs auf konsistente Key-Strukturen achten (flat vs. nested).
- Kompatibilitätsannahmen (CUDA/PyTorch/Driver) immer verifizieren, nicht implizit voraussetzen.
- Bei MVP-Skripten früh Validierung + klare Fehlermeldungen einbauen.
- Keine impliziten Betriebsannahmen (z. B. GPU-Sichtbarkeit im Container) ohne Check-Kommandos.

---

## Standard-Check vor Abschluss einer Aufgabe

- [ ] Zielbild und Scope klar definiert
- [ ] Dateistruktur vollständig
- [ ] Konfigurationen und Skripte konsistent
- [ ] Fehlerfälle dokumentiert
- [ ] Audit-/Nachvollziehbarkeit berücksichtigt
- [ ] Offene Fragen explizit gelistet
- [ ] Keine Secrets oder lokale Artefakte im Repo

---

## Offene-Fragen-Template (für neue Projekte)

1. Fachliche Zielprozesse und Grenzen?
2. Welche Entitäten + IDs sind verpflichtend?
3. Welche Events müssen auditierbar sein?
4. Welche Fehlerzustände sind fachlich kritisch?
5. Welche Reproduzierbarkeitsanforderungen sind „must-have“?
6. Welche regulatorischen/Compliance-Rahmen gelten?

---

## Änderungslog

- 2026-04-05:
  - Erstfassung als projektübergreifendes Gedächtnis angelegt.
  - Nutzerpräferenzen, Arbeitsprinzipien und Qualitätskriterien dokumentiert.
  - Kontext zu `llm-homelab-training` aufgenommen.
  - Eliot-Review zur Backup-Strategie ausgewertet und als Entscheidungsnotiz übernommen:
    - Bewertung Verzeichnisstrategie: „teilweise“, mit Ergänzungen „passt“.
    - Code-Source-of-truth unter `opt/projects/llm-homelab-training` bestätigt.
    - `opt/containers` nur als Runtime-Ort, nicht als alleinige Quelle für Compose/Env/Secrets.
    - Auditierbare Run-Metadaten als kleine, gesondert sicherbare Klasse priorisiert.
    - Artefakte in Klassen aufgeteilt:
      - Klasse 1: kritische, kleinere Outputs (finale/beste Adapter, Summarys) täglich sichern.
      - Klasse 2: nützliche, mittelgroße Logs regelmäßig sichern.
      - Klasse 3: große, ersetzbare Checkpoints/Caches standardmäßig nicht voll sichern.
    - Restore-Drills als Pflichtprozess aufgenommen:
      - Code-only-Rebuild
      - Audit-Restore eines konkreten Run-ID
      - Full-critical-Restore
      - monatlicher Dependency-Drift-Check

- 2026-04-05 (Eliot First-Run Empfehlungen):
  - Reifegrad-Einschätzung:
    - Solides MVP mit End-to-End-Bausteinen (Build/Run -> Daten -> Train -> Eval -> Ops/Doku).
    - Ops-Reife über Basisniveau durch `Makefile`, Preflight/Smoke, GPU-Checks und gepinnte Abhängigkeiten.
    - Weiterhin MVP, bis K80-Stabilität über mehrere echte Läufe verifiziert ist.
  - Sicherster erster Testlauf auf K80 (Reihenfolge):
    - 1) Host/Stack prüfen (`check_gpu.sh`, `make preflight`)
    - 2) Container minimal starten und CUDA-Verfügbarkeit in Python prüfen
    - 3) Dataset-Smoke mit kleinem Slice (Format/Encoding/Felder prüfen)
    - 4) Kurz-Training mit `smoke_lora.yaml` (wenige Steps, deterministisch)
    - 5) Mini-Eval auf kleinem `val`-Subset
    - 6) Erst danach kurzer Real-Run mit `train_lora_3b_k80.yaml`, dann Voll-Run
    - 7) Self-Edit erst nach stabiler Baseline aktivieren
  - Häufigste Fehler zu Beginn vermeiden:
    - OOM durch zu aggressive `seq_len`/Batch/Precision-Konfiguration
    - CUDA/Driver/Torch-Mismatch im Container
    - Schema-Drift in JSONL-Daten (fehlende Felder, leere Inhalte, kaputte Encodings)
    - Fehlende Run-Disziplin (keine Run-ID, keine Config-/Commit-Zuordnung)
    - Zu frühes Parallel-Debugging von Baseline-Training und Self-Edit-Loop
  - Kritische Betriebsfestlegung GPU-Stack (frozen baseline, verbindlich):
    - NVIDIA Driver (Host): `470.256.02`
    - CUDA Runtime laut `nvidia-smi`: `11.4`
    - No-Update-Policy: Keine Updates von NVIDIA-Treiber oder CUDA durchführen, da dies die letzte stabile Version für den Betrieb ist.
    - Änderungen an Driver/CUDA nur per expliziter Ausnahmeentscheidung mit dokumentiertem Rollback-Plan.
  - Hinweis zum aktuellen Preflight-Warnsignal:
    - Warnung zu Compute Capability (`below minimum 3.7`) trotz K80-Bestand kann aus Check-Parsing resultieren.
    - Bis zur technischen Klärung gilt: tatsächliche GPU-Identität über `nvidia-smi -L` und Container-Torch-Checks priorisieren.
  - Root-Cause dokumentiert (CUDA-Sichtbarkeit im Container):
    - Symptom: `nvidia-smi` im Container sieht K80, aber `torch.cuda.is_available() == False` (teils `device_count` inkonsistent).
    - Ursache: Container-/Wheel-Stack war auf `cu118` (`torch==2.1.2+cu118`) bei Host Driver `470.256.02` + K80; diese Kombination ist nicht kompatibel.
    - Einordnung: NVML-Pfad kann funktionieren (`nvidia-smi`), während CUDA-Context-Initialisierung für PyTorch fehlschlägt.
  - Remediation dokumentiert (ohne Driver/CUDA-Hostupdate):
    - Base-Image auf `nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu22.04` abgesenkt.
    - Python-Stack auf K80-/Driver-470-kompatible Versionen gepinnt:
      - `torch==1.12.1+cu113`
      - `torchvision==0.13.1+cu113`
      - `torchaudio==0.12.1`
      - `transformers==4.31.0`
      - `accelerate==0.21.0`
      - `peft==0.5.0`
      - `datasets==2.14.0`
    - GPU-Check korrigiert: `cuda_device_count` wird jetzt unabhängig von `is_available` ausgegeben (bessere Diagnose).
  - Verbindliche Verifikationsreihenfolge nach Änderung:
    - `make build`
    - `make up`
    - `make check-gpu-container`
    - optional `make smoke` vor erstem längeren Trainingslauf
  - Ablagehinweis korrigiert:
    - Externe Vault-Pfade sind für dieses Projekt außer Scope.
    - Betriebsrelevante Baseline-Dokumentation bleibt im Projekt-Repository.
  - Alpine-Rationale dokumentiert:
    - Für CUDA-/PyTorch-/Transformers-Workloads auf K80 wird Ubuntu/Debian-Basis verwendet, nicht Alpine.
    - Grund: bessere Kompatibilität im glibc-/CUDA-Ökosystem; Alpine (musl) erhöht Build-/Runtime-Risiken bei ML-Wheels.
  - CUDA-Image-Tag-Auflösung dokumentiert:
    - Fehlerursache beim Build war ein nicht existierender Tag mit `ubuntu22.04` für CUDA `11.3.1`.
    - Verifizierter gültiger Tag: `nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04`.
    - Entscheidungsregel: Bei Legacy-K80 immer Tag-Existenz vor Stack-Änderungen verifizieren und Baseline anschließend fixieren.
  - Smoke-Run Incident dokumentiert (Run-ID: `smoke-20260405T165115Z`):
    - Host- und Container-GPU-Checks vollständig erfolgreich (`torch.cuda.is_available() == true`, `compute_capability_0 == 3.7`).
    - Build und Modell-Download erfolgreich (OPT-2.7B geladen, LoRA-Trainable Params korrekt angezeigt).
    - Trainingsskript schlug beim Dataset-Load fehl:
      - Fehler: `TypeError: can only concatenate tuple (not "str") to tuple`
      - Ort: `load_dataset("json", data_files=...)` in `train_lora.py`
      - Wahrscheinlicher Zusammenhang: Abhängigkeitsinkompatibilität im `datasets`/`fsspec` Stack für die gewählten Legacy-Pins.
    - Folgefehler in Eval:
      - `adapter_config.json` nicht gefunden unter `data/models/smoke-...`
      - Ursache: Training brach vor Adapter-Save ab.
    - Prozesslücke identifiziert:
      - `make smoke` meldete trotz Train/Eval-Fehler „completed“.
      - Schlussfolgerung: Smoke-Targets müssen bei Fehlern hart abbrechen (`set -e`/saubere Exit-Code-Propagation), damit keine False-Green Ergebnisse entstehen.
  - Follow-up Aktionen (verbindlich):
    - Versionsmatrix `datasets`/`fsspec`/`pyarrow` für torch-1.12-kompatiblen Stack verifizieren und fix pinnen.
    - `train_lora.py` um robustes Exception-Handling + klare Fehlerklassifikation beim Dataset-Load ergänzen.
    - `Makefile` Smoke-Targets so anpassen, dass Train/Eval-Fehler den Lauf sofort als failed markieren.
    - Erst nach erfolgreichem Smoke ohne Fehler in den ersten kurzen Real-Run wechseln.
  - PEFT-Metadaten-Constraint dokumentiert (Torch 1.12 Kompatibilität):
    - Verifiziert: `peft` Versionen `0.1.0` bis `0.4.0` deklarieren in den Paket-Metadaten `torch>=1.13.0`.
    - Konsequenz: Mit `torch==1.12.1+cu113` ist eine normale pip-Auflösung mit PEFT nicht möglich (`ResolutionImpossible`).
    - Verbindliche K80-kompatible Basis-Pins (ohne automatische PEFT-Abhängigkeitsauflösung):
      - `torch==1.12.1+cu113`
      - `transformers==4.30.2`
      - `accelerate==0.20.3`
    - Workaround (Ausnahmeverfahren): `peft` nur per `--no-deps` installieren, nachdem der Basis-Stack fix installiert wurde.
    - Zusatzregel zum Workaround:
      - Nach `--no-deps` ist ein verpflichtender Import-/Runtime-Sanity-Check durchzuführen.
      - Der Lauf muss als „Dependency-Override“ im Run-Metadatenblock markiert werden (inkl. PEFT-Version, Commit, UTC-Zeit).
      - Bei Import-/Runtime-Fehler gilt: Workaround verwerfen und PEFT für diesen Stack deaktivieren.
    - Zusätzliche Stabilitätsregel:
      - `torchvision` und `torchaudio` bleiben aus dem Standard-Stack entfernt, da für den textbasierten LoRA-Workflow nicht erforderlich und konfliktanfällig.
    - Betriebsfolge nach Dependency-Änderungen:
      - `make build` -> `make up` -> `make check-gpu-container` -> `make smoke` (verpflichtend) vor Real-Run.
  - Smoke-Run erfolgreich verifiziert (Run-ID: `smoke-20260406T092145Z`):
    - Host- und Container-Gates bestanden:
      - Host: Driver `470.256.02`, CUDA Runtime `11.4`, 2x Tesla K80 sichtbar
      - Container: `torch 1.12.1+cu113`, `torch.cuda.is_available()==true`, `compute_capability_0==3.7`
    - Trainingspfad erfolgreich:
      - LoRA Smoke-Training abgeschlossen (`5/5` Steps)
      - Train-Metrik: `train_loss=3.8740`, `train_runtime=8.2295s`, `train_steps_per_second=0.608`
      - Adapter-Artefakte wurden unter `data/models/smoke-20260406T092145Z` geschrieben
    - Eval-Pfad erfolgreich:
      - Runtime-Device: `cuda:0`
      - Eval-Artefakte vorhanden:
        - `data/evals/smoke-20260406T092145Z/predictions.jsonl`
        - `data/evals/smoke-20260406T092145Z/summary.json`
      - Smoke-Metriken (ein Sample):
        - `exact_match_mean=0.0`
        - `token_f1_mean=0.0`
        - `prediction_chars_mean=43.0`
        - `reference_chars_mean=2.0`
    - Betriebsimplikation:
      - Smoke-Gate ist als bestanden zu werten (kein False-Green, Train+Eval+Artefaktchecks erfüllt).
      - Nächster freigegebener Schritt: erster kurzer Real-Trainingslauf mit `configs/train_lora_3b_k80.yaml`.
      - Hinweis zur Interpretation: Smoke-Metriken dienen primär als Pipeline-Sanity-Check, nicht als Qualitätsbenchmark.
  - Kompatibilitätsfix dokumentiert (Smoke-Run `smoke-20260405T165115Z`):
    - GPU-Stack erfolgreich validiert:
      - `torch 1.12.1+cu113`
      - `torch.cuda.is_available() == true`
      - `compute capability 3.7` auf Tesla K80
    - Trainingsblocker identifiziert:
      - `TypeError: can only concatenate tuple (not "str") to tuple` beim `datasets` JSON-Load.
    - Abhilfe für Legacy-Stack gesetzt:
      - `fsspec==2023.6.0`
      - `pyarrow==12.0.1`
    - Zusätzlicher Trainingsblocker identifiziert:
      - `RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn` während `trainer.train()`.
    - Root Cause (technisch):
      - Bei aktivem `gradient_checkpointing` in Kombination mit LoRA waren Input-Gradienten nicht explizit aktiviert.
    - Remediation umgesetzt:
      - In `train_lora.py` wird bei aktiviertem Checkpointing `enable_input_require_grads()` genutzt.
      - Fallback über Forward-Hook auf Embeddings gesetzt, falls die Methode am Modell nicht vorhanden ist.
  - Smoke-Gate-Härtung umgesetzt:
    - `smoke-train` bricht jetzt hart ab, wenn `adapter_config.json` fehlt.
    - `smoke-infer` prüft Adapter-Artefakte vor Eval und verlangt `summary.json` als Erfolgsnachweis.
    - Prozessregel: `make smoke` gilt nur als bestanden, wenn Train + Eval + Artefaktchecks ohne Fehler durchlaufen.
  - Erster kontrollierter Real-Run erfolgreich abgeschlossen:
    - `run_id`: `real-20260406T092832Z`
    - Config: `configs/train_lora_3b_k80_short.yaml`
    - Dataset: `data/datasets/train.jsonl`
    - Ergebnis: `success`
    - Pflichtartefakte vorhanden:
      - `data/models/real-20260406T092832Z/adapter_config.json`
      - `data/models/real-20260406T092832Z/final_metrics.json`
      - `data/logs/real-20260406T092832Z/`
    - Trainingsmetriken:
      - `global_step=60`
      - `train_loss=1.9559472759564718`
      - `train_runtime=1898.2539s`
      - `train_steps_per_second=0.032`
      - `train_samples_per_second=0.506`
  - Ad-hoc Inference-Test dokumentiert (Prompt-Test auf trainiertem Adapter):
    - Testfrage: `Beantworte kurz und präzise: was weist du über eliot`
    - Ausführungspfad:
      - Dataset: `data/datasets/ask_eliot.jsonl`
      - Adapter: `data/models/real-20260406T092832Z`
      - Output: `data/evals/ask-eliot-real-20260406T092832Z/predictions.jsonl`
    - Beobachtetes Modellverhalten:
      - Antwort wurde generiert, Inference-Pipeline funktioniert technisch.
      - Inhalt war repetitiv und enthielt wiederholte `### Response:`-Segmente.
      - Sprachqualität war reduziert (`... für eine kurze Probleme`), Präzisionsvorgabe wurde nur teilweise erfüllt.
      - Eval-Kennzahlen (`exact_match_mean=0.0`, `token_f1_mean=0.0`) sind für diesen Test nicht als Qualitätsmaß geeignet, da `reference=placeholder`.
    - Interpretation:
      - Infrastruktur und Adapter-Ladepfad sind bestätigt funktionsfähig.
      - Antwortqualität für freie Q&A-Prompts ist mit aktuellem kleinem Datensatz noch begrenzt.
  - Empfohlener nächster Schritt:
    - Längeren Real-Run freigeben (gleiche Baseline, konservative K80-Parameter), danach standardisierte Eval auf `data/datasets/val.jsonl` durchführen und Ergebnisse gegen den Kurzlauf vergleichen.
    - Für Q&A-Qualität gezielt zusätzliche Trainingssamples mit kurzen, nicht-repetitiven Antworten ergänzen und Prompt-/Stop-Format in der Inferenz prüfen.
  - Erster Real-Run (kontrolliert) als Standardverfahren festgelegt:
    - Ziel: reproduzierbarer Kurzlauf auf realem Datensatz vor längeren Trainingsläufen.
    - Verbindliche Reihenfolge:
      - 1) `make preflight`
      - 2) `make up`
      - 3) `make check-gpu-container`
      - 4) `make real-run-short`
      - 5) `make run-status`
    - Konfiguration:
      - `configs/train_lora_3b_k80_short.yaml`
      - konservative K80-Parameter (`batch=1`, `fp16=true`, `bf16=false`, `gradient_checkpointing=true`)
    - Gate-Kriterien für „Real-Run bestanden“:
      - Training ohne Traceback abgeschlossen
      - `data/models/<run-id>/adapter_config.json` vorhanden
      - Logs unter `data/logs/<run-id>/` vorhanden
      - `run-status` meldet Adapter-Artefakte erfolgreich
    - No-Go-Kriterien:
      - CUDA-/GPU-Check nicht grün
      - fehlende Adapter-Artefakte nach Training
      - wiederkehrende OOM-/Runtime-Fehler ohne dokumentierte Einzeländerung
    - Prozessregel:
      - Pro Wiederholungslauf nur eine Parameteränderung und vollständige Dokumentation mit `run_id`.

- 2026-04-07 (Host-freundlicher Laufmodus / Soft-Limits):
  - Zielbild aktualisiert:
    - Schwere Schritte (`prepare-dataset-vault`, `real-run-short`, `real-run-continue`) sollen den Host weniger belasten, E2E aber unverändert lauffähig bleiben.
  - Umgesetzte Betriebsmaßnahme:
    - Wrapper `scripts/run_nice.sh` eingeführt und ausführbar gemacht.
    - Wrapper nutzt weiche Priorisierung:
      - CPU: `nice -n 10`
      - I/O: `ionice -c2 -n7` (wenn verfügbar)
    - Wrapper protokolliert vor/nach dem Lauf:
      - UTC-Zeitstempel
      - Uptime
      - Speicher-Schnappschuss
      - Disk-Schnappschuss (`/`)
  - Memory-Pressure-Warnung (nicht-blockierend):
    - Schwelle `MemAvailable < 1536MB` erzeugt Warnung, aber keinen harten Abbruch.
  - Fehlerdiagnostik bei Fehlschlag:
    - Best-effort OOM-Dump aus Kernel-Logs (`oom|out of memory|killed process`) wird ausgegeben.
  - Makefile-Workflow angepasst:
    - `prepare-dataset-vault` läuft über `./scripts/run_nice.sh ...`
    - `real-run-short` läuft über `./scripts/run_nice.sh ...`
    - `real-run-continue` läuft über `./scripts/run_nice.sh ...`
    - Optionales Target `limit-cpu` ergänzt (`docker update --cpus=6 llm-homelab-trainer`)
    - `nightly-run` kann CPU-Cap optional aktivieren über `NIGHTLY_APPLY_CPU_LIMIT=1`
  - Audit-Hinweis:
    - Änderung ist Betriebs-/Stabilitätsmaßnahme (Host-Responsiveness), keine Qualitätsoptimierung des Modells.
    - E2E-Prinzip bleibt unverändert: `preflight -> dataset -> train -> eval -> retention`.

- 2026-04-07 (Swap-Thrash Mitigation / SeqLen-First, verbindliche Reihenfolge):
  - Zielbild:
    - Training und Dataset-Preparation sollen Host-Bedienbarkeit priorisieren (kein Swap-Thrash), auch wenn Läufe langsamer werden.
  - Verbindliche Reihenfolge bei Speicher-/Swap-Druck:
    - 1) `max_seq_length` zuerst reduzieren (`512 -> 384`, bei Bedarf `384 -> 256`).
    - 2) Danach `gradient_accumulation_steps` erhöhen (z. B. `16 -> 24/32`) zur Stabilisierung des Trainingssignals.
    - 3) Tokenisierungs-Parallelität niedrig halten (`num_proc=1`) und kleine Tokenize-Batches verwenden, um RAM-Peaks zu reduzieren.
  - Umgesetzte technische Maßnahmen:
    - `configs/train_lora_3b_k80.yaml`: `max_seq_length=384`, `gradient_accumulation_steps=24`, `data.num_proc=1`, `dataloader_num_workers=1`.
    - `configs/train_lora_3b_k80_short.yaml`: `gradient_accumulation_steps=24` (bei konservativem `max_seq_length=384`).
    - `src/scripts/train_lora.py`: Tokenisierung konfigurierbar über `tokenization_num_proc` und `tokenization_batch_size` (RAM-Peak-Minderung).
  - Observability-Anforderung:
    - Vor-/Nachlauf-Snapshots verpflichtend mit Fokus auf `MemAvailable`, `SwapTotal`, `SwapFree` plus `free -h` und `df -h /`.
  - Prozessregel:
    - Erst wenn SeqLen-/Tokenisierungshebel ausgereizt sind, weitere Optimierungen prüfen.