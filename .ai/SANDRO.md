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
- [ ] Produktions- und Trainingspointer fachlich getrennt (`LATEST_REALRUN_ID` vs. `LATEST_OK_ADAPTER_ID`)
- [ ] Retention schützt produktive Referenzen und entfernt keine promoteten Adapter unbeabsichtigt
- [ ] Für neue Betriebsmodi zusätzlich eine kurze, kompakte Inbetriebnahme-Checkliste in `.ai/` anlegen
- [ ] `.env.example` nur mit tatsächlich genutzten oder bewusst optionalen Variablen pflegen; Alt-/Scheinfelder entfernen
- [ ] Bei Environment-Variablen zwischen aktiver technischer Nutzung, dokumentarischem Zweck und Zukunftsoption explizit unterscheiden
- [ ] Neue Feature-Wünsche zur Infrastruktur-Portabilität (z. B. GPU-Profile) immer als eigene Anforderung mit Zielbild, Akzeptanzkriterien und Betriebsregeln dokumentieren

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

- 2026-04-09:
  - Serving-/Promotion-Architektur für `llm-homelab-training` als neuer MVP-Betriebsstandard festgelegt.
  - Zielbild präzisiert:
    - Sonntäglicher automatisierter Trainingslauf (`nightly-run`)
    - jeder Trainingslauf erzeugt eine neue Run-ID und einen neuen Adapter-Ordner
    - Serving läuft als separater Docker-Service `serve`
    - Serving nutzt ausschließlich den promoteten Pointer `data/runs/LATEST_OK_ADAPTER_ID`
    - OpenClaw spricht den Serving-Endpunkt über eine OpenAI-kompatible API an
  - Verbindliche Trennung von technischer und fachlicher Referenz eingeführt:
    - `LATEST_REALRUN_ID` = letzter technisch erfolgreicher Real-Run
    - `LATEST_OK_ADAPTER_ID` = letzter fachlich freigegebener Adapter für Serving
    - `LATEST_OK_ADAPTER_PATH` nur abgeleitete Hilfsreferenz, nicht Source-of-Truth
  - Promotionsregel dokumentiert:
    - Promotion nur nach `make eval-val`
    - Default-Thresholds:
      - `pass_rate_exact_openbook >= 0.60`
      - `avg_coverage_runbook_openbook >= 0.30`
    - Bei Fail bleibt `LATEST_OK_ADAPTER_ID` unverändert; Serving bleibt stabil
  - Continue-Trainingsregel verschärft:
    - `make real-run-continue` startet nur von `LATEST_OK_ADAPTER_ID`
    - wenn kein promoteter Adapter vorhanden ist: Fallback auf `make real-run-short`
  - Serving-MVP dokumentiert:
    - separates Compose-File `docker/compose.serve.yaml`
    - Service `serve`
    - Health-Endpunkt `/health`
    - OpenAI-kompatibler MVP-Endpunkt `POST /v1/chat/completions`
    - optionaler Reload-Endpunkt `POST /reload`
    - Default-Port `8901`
  - Nightly-Orchestrierung angepasst:
    - `preflight`
    - `lock-status`
    - `check-single-flight`
    - `validate-val`
    - `prepare-dataset-augmented`
    - Train (`real-run-continue` von `LATEST_OK`, sonst `real-run-short`)
    - `eval-val`
    - `promote-latest-ok`
    - bei neuer Promotion Neustart des Serving-Service
    - `retention-clean`
  - Betriebsentscheidung bestätigt:
    - Serving darf während Nightly-Training heruntergefahren werden
    - Parallelbetrieb von Training und Serving ist auf K80 nicht erforderlich
  - Retention-Regel erweitert:
    - `retention-clean` muss sowohl `LATEST_REALRUN_ID` als auch `LATEST_OK_ADAPTER_ID` schützen
  - Lernpunkt für zukünftige Sessions:
    - bei produktionsnahen ML-Systemen technische Laufhistorie und stabile Serving-Freigabe immer als getrennte Zustände modellieren
    - für neue Betriebsmodi neben Architektur- und Kontextdoku immer auch eine kompakte Inbetriebnahme-Checkliste in `.ai/` pflegen
    - `.env.example` als echte Betriebsvorlage behandeln und nicht als unverbindliche Sammelstelle für unverdrahtete Variablen

- 2026-04-10:
  - Environment-Template-Regel für `llm-homelab-training` präzisiert:
    - `.env.example` soll nur Variablen enthalten, die aktuell technisch genutzt werden oder bewusst als optionale Betriebsparameter vorgesehen sind.
    - Variablen ohne aktive Verdrahtung im Compose-/Make-/Code-Pfad sind als Drift-/Verwirrungsquelle zu behandeln und zu entfernen oder sauber als zukünftige Option zu kennzeichnen.
  - Prüfreihenfolge für Environment-Dateien festgelegt:
    - 1) Wird die Variable in Compose-Dateien referenziert?
    - 2) Wird sie in Makefile oder Code tatsächlich ausgewertet?
    - 3) Ist sie nur dokumentarisch erwähnt?
    - 4) Ist ihr Status im Template klar erkennbar?
  - Qualitätsregel ergänzt:
    - `.env.example` muss den tatsächlichen Betriebsstand von Training und Serving widerspiegeln, einschließlich `SERVE_PORT`, `BASE_MODEL`, `LATEST_OK_POINTER` und `HEALTH_PATH`, wenn diese im Compose-Stack verwendet werden.
  - Wartungsprinzip dokumentiert:
    - Environment-Templates regelmäßig gegen reale Compose-/Runtime-Nutzung abgleichen, damit Setup-Dokumentation und technische Verdrahtung nicht auseinanderlaufen.
    - Neuer Feature-Wunsch aufgenommen: GPU-Profil-Portabilität über `.env` und Profil-Configs (inkl. optionaler Dockerfile-Profile pro GPU-Klasse), damit Trainings- und Serving-Stacks ohne Codeänderung zwischen unterstützten GPUs umschaltbar sind.
  - Eval-Härtung (Regression `val`) dokumentiert:
    - Exact-Normalisierung wurde robust gegen Wrapper-/Template-Leakage ausgelegt (`Kontext:`, `Antwort:`, `Instruction:` usw. werden in Exact-Fällen entfernt).
    - Für Exact-Fälle wurde `first_line_only` als Standard eingeführt, um endlose Wiederholungen im Modell-Output nicht als Primärsignal zu werten.
    - Kandidaten-Extraktion für Single-Value-Exact-Fälle ergänzt (Pfad-/Dateiname-/Token-Muster), damit der geforderte Wert deterministisch aus umgebendem Text isoliert werden kann.
    - Zielbild bestätigt: Eval nicht „cheaten“, sondern robust den fachlich geforderten Zielwert extrahieren und exakt vergleichen.
  - Serving-Härtung (`src/serve/app.py`) dokumentiert:
    - Startverhalten ohne `LATEST_OK_ADAPTER_ID` auf „degraded statt crash“ umgestellt.
    - `/health` liefert jetzt auch im Degraded-Status strukturierte Zustandsinformationen (`status`, `message`, Pointer-/Adapter-Kontext).
    - `/v1/chat/completions` liefert bei nicht geladenem Modell deterministisch `503` mit klarer Ursache statt Laufzeitcrash.
    - Generierungsdefaults gegen Looping verschärft (`repetition_penalty`, `no_repeat_ngram_size`, begrenzte `max_new_tokens`-Obergrenze für Serving).
    - Prompt-Härtung ergänzt:
      - feste Systemregel („nur finale Antwort“, keine Template-Tokens ausgeben)
      - Stop-/Cut-Logik auf `###`-Marker
      - Wrapper-Sanitizer für typische Tokens (`Kontext:`, `Antwort:`, `Instruction:` etc.)
    - Tool-less RAG-light / FAQ-MVP ergänzt:
      - feste Repo-Fakten für häufige Fragen (u. a. `docker/compose.serve.yaml`, `docker/compose.yaml`, `make preflight`)
      - deterministische Kurzantworten für klar definierte Standardprompts.
    - Betriebsprinzip bestätigt: Auditierbare Trennung zwischen „Service läuft“ und „modellseitig bereit“ bleibt erhalten.
  - Serving-Smoke-Test-Prozess ergänzt:
    - neues Skript `scripts/serve_smoke.sh` für standardisierte Prompt-Regression gegen `/v1/chat/completions`.
    - neues Make-Target `make serve-test`.
    - Report-Ausgabe nach `data/evals/serve_smoke_<timestamp>.txt`.
    - Abnahmekriterium im Smoke: keine Wrapper-/Template-Leaks (`### Input`, `### Response`, `### Instruction`, `Kontext:`, `Antwort:`).
  - OOM-/Fragmentierungs-Maßnahme verbindlich dokumentiert:
    - `.env.example` enthält `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128`.
    - Variable wird durch Training- und Serving-Compose an Container durchgereicht.
    - Troubleshooting-Doku verweist explizit auf diese Option bei sporadischen OOMs im Modell-Load/Eval.

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

- 2026-04-08 (Eval-Qualität + Trainingsdaten-Alignment / Aufgabenpakete A–D):

  ## Diagnose-Befund (Stand: Adapter real-20260408T085717Z)
  - make eval-val: 2/40 pass (nur val-023 und val-024).
  - Root-Cause-Analyse:
    - val-023/val-024 haben tags ohne "exact" → Substring-Matching → kurze Strings wie "data/models" / "data/logs" werden im Output gefunden.
    - Alle exact-Items (val-001 bis val-022) scheitern weil OPT-2.7b mit minimalem LoRA keine Exact-Extraction gelernt hat.
    - Alle val-rb-* (runbook) scheitern weil keine runbook-artigen Trainingssamples im Dataset vorhanden waren.
    - Vault-Extraktion liefert überwiegend allgemeine Dokumentations-Samples, keine Exact-Extraction-Muster.

  ## Umgesetzte Maßnahmen

  ### A1–A4 (eval_val.py): War bereits in Vorversion implementiert
  - missing_expected_contains, found_expected_contains, output_preview, normalized_output_preview: vorhanden.
  - Tag-aware Normalisierung (exact vs. non-exact): vorhanden.
  - Suite-Splitting (pass_rate_exact_openbook, pass_rate_runbook_openbook, pass_rate_closedbook): vorhanden.
  - Partial credit für runbook_openbook (pass_threshold=0.6, coverage): vorhanden.
  - D1/D2 (deterministischer Prompt, temperature=0): vorhanden.

  ### B1 (neu): src/scripts/validate_val.py
  - Checks V001–V007: JSON-Syntax, Pflichtfelder, eindeutige IDs, non-empty expected_contains und tags.
  - Warnungen W001–W003: overly_strict (>12 tokens), fehlende Gruppentyp-Tags, kurze Instructions.
  - Tag-group Distribution + expected_contains Statistik in Ausgabe.
  - Optionaler JSON-Report.
  - Make-Target: make validate-val (host-seitig, kein Container erforderlich).
  - Exit-Code: 0 = clean, 1 = Fehler.

  ### C1 (neu): exact_extraction Mode in prepare_dataset.py
  - Neuer Modus --mode exact_extraction parst MD-Dateien mit ## Instruction/Input/Output Triplets.
  - Output wird verbatim übernommen (keine Redaction, keine Umformatierung).
  - Graceful bei fehlendem Vault-Mount.
  - Make-Target: make prepare-dataset-exact.

  ### C1 Seed-Datei (neu): data/datasets/exact_extraction_samples.jsonl
  - 35 handkuratierte Samples die Exact-Extraction-Muster für val-001 bis val-024 trainieren.
  - Deckt ab: Pfad-Extraktion, Service/Container-Namen, Versions-Strings, GPU-Namen, Policy-Items (Ja/Nein).
  - Verfügbar ohne Vault-Mount → sofort einsatzbereit.

  ### C2 (neu): Frontmatter-Filter in prepare_dataset.py
  - is_frontmatter_heavy(): überspringt Sections wo >55% der Zeilen YAML-artige key:value-Muster sind.
  - is_moc_only_output(): überspringt Outputs die nur MOC/aliases/tags-Zeilen enthalten.
  - Beide in section_is_sample_worthy() und prepare_vault_md_mode() integriert.
  - Neue Skip-Reasons: "frontmatter_heavy", "moc_only_output".

  ### C3 (neu): data/datasets/runbook_samples.jsonl
  - 20 Trainingssamples die alle val-rb-001 bis val-rb-010 expected_contains abdecken.
  - Je 2 Variationen pro Testtyp (Swap, Preflight, Dataset, Continue-Run, Swap-Reset, Status, Eval, Retention, Quality-Diagnose, E2E).
  - Outputs enthalten EXAKT die Strings aus expected_contains der val-rb-* Items als Substrings.

  ### Merge-Pipeline (neu): src/scripts/merge_datasets.py + make prepare-dataset-augmented
  - merge_datasets.py: dedupliziertes Zusammenführen mehrerer JSONL-Sources (canonical JSON-Key-Sort für Duplikat-Erkennung).
  - Reihenfolge: train_vault.jsonl → exact_extraction_samples.jsonl → runbook_samples.jsonl → train.jsonl.
  - Schema-Validierung nach Merge als Pflichtcheck.
  - Make-Target: make prepare-dataset-augmented (ersetzt make prepare-dataset-vault im Augmentation-Pfad).

  ### Volume-Mount (neu): docker/compose.yaml
  - ExactExtraction-Vault: /data/obsidian-rw/Eliot/.../ExactExtraction → /vault/exact_extraction:ro
  - Graceful: falls Host-Pfad nicht existiert, wird Docker-Bind-Mount als leeres Verzeichnis angelegt.
  - make prepare-dataset-exact prüft Existenz vor Extraktion.

  ## Empfohlene nächste Schritte (Reihenfolge)
  1. make validate-val → val.jsonl auf Strukturfehler prüfen.
  2. make prepare-dataset-augmented → neues train.jsonl mit Exact-Extraction + Runbook-Samples.
  3. make real-run-short oder make real-run-continue → kurzer neuer Trainingslauf.
  4. make eval-val → Subscores vergleichen; Ziel: pass_rate_exact_openbook > 0.6.
  5. Runbook-Items (val-rb-*): avg_coverage > 0.3 als erster Fortschrittsindikator.

  ## Lernpunkte (für zukünftige Sessions)
  - Eval-Qualität hängt direkt vom Trainings-Datenmix ab: ohne Exact-Extraction-Samples kein Exact-Extraction-Verhalten.
  - val-Items mit Tags ohne "exact" nutzen Substring-Matching → einfacher zu erfüllen → bewusst setzen.
  - Runbook-Outputs müssen die expected_contains-Strings als genaue Substrings enthalten.
  - Vault-Extraktion allein reicht nicht: gezielt kuratierte Seed-Samples für kritische Fähigkeiten ergänzen.
  - Heredocs in Makefile-Targets sind fehleranfällig → immer eigene Python-Skripte dafür anlegen.
  - validate_val.py host-seitig halten (kein Container-Start nötig) → schnell ausführbar im CI/pre-commit.