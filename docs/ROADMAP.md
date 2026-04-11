# ROADMAP — llm-homelab-training

## Zweck und Scope

Dieser Roadmap-Plan definiert die stufenweise Umsetzung einer reproduzierbaren lokalen Training-Umgebung für LoRA/Fine-Tuning (3B Klasse) auf NVIDIA K80 sowie den späteren Ausbau um eine SEAL-inspirierte Self-Edit-Pipeline.

**Leitprinzipien:**
- Reproduzierbarkeit vor Feature-Umfang
- Lokal/offline-fähig (keine Cloud-Abhängigkeit)
- Auditierbarkeit aller Läufe (Konfiguration, Datenstand, Outputs)
- Deterministische Verzeichnis- und Artefaktstruktur

---

## Phase 0 — Fundament und Betriebsfähigkeit (MVP-Setup)

### Ziel
Containerisierte, lokal startbare Trainingsumgebung mit reproduzierbarem Dependency-Stack.

### Lieferobjekte
- `docker/Dockerfile` mit gepinnten Kernabhängigkeiten
- `docker/compose.yaml` mit GPU-Passthrough und Mount-Logik
- `.env.example` ohne Secrets
- `README.md` Quickstart und Ausführungspfade
- Basisverzeichnisstruktur (`src/`, `configs/`, `docs/`, `.ai/`, `data/`)

### Akzeptanzkriterien
1. `docker compose -f docker/compose.yaml up -d --build` läuft ohne manuelle Nacharbeit.
2. Container startet interaktiv (`sleep infinity`/Shell) und sieht gemountete Pfade unter `/workspace`.
3. GPU ist im Container sichtbar (z. B. per `torch.cuda.is_available()` im Python-Check).
4. Keine Secrets im Repository; `.env` bleibt lokal.

### Risiken
- CUDA/Driver-Mismatch auf Host
- Unterschiedliche Docker/NVIDIA-Toolkit-Versionen

---

## Phase 1 — Datenpipeline und Formatdisziplin

### Ziel
Validierbarer, stabiler Dateneingang für Training und spätere Self-Edit-Erweiterungen.

### Lieferobjekte
- `src/scripts/prepare_dataset.py` (Formatprüfung/Normalisierung)
- Datensatzdokumentation in `src/datasets/README.md`
- JSON-Schema für Self-Edit (`src/datasets/schemas/self_edit.schema.json`)
- Konventionen für JSONL (`instruction`, `input`, `output`)

### Akzeptanzkriterien
1. Ungültige JSONL-Zeilen werden deterministisch erkannt und protokolliert.
2. Ausgabeformat ist konsistent und trainierbar (eine Zeile = ein Sample).
3. Pflichtfelder werden strikt validiert (`instruction`, `output` nicht leer).
4. Schema-Datei ist für spätere Self-Edit-Objekte nutzbar.

### Risiken
- Inhomogene Rohdatenqualität
- Zu lange Samples für K80-VRAM-Budget

---

## Phase 2 — LoRA-Training auf K80 (MVP-Trainingslauf)

### Ziel
Erster reproduzierbarer LoRA-Trainingslauf eines 3B-Basismodells mit stabilen K80-Parametern.

### Lieferobjekte
- `src/scripts/train_lora.py` (MVP)
- `configs/train_lora_3b_k80.yaml` (batch klein, grad accumulation, fp16, checkpointing)
- Laufartefaktpfade:
  - `data/models/<run-id>/`
  - `data/logs/<run-id>/`

### Akzeptanzkriterien
1. Training startet mit CLI + Konfig ohne Codeänderung.
2. Adapter-Artefakte werden unter `data/models/<run-id>/` gespeichert.
3. TensorBoard-kompatible Logs entstehen unter `data/logs/<run-id>/`.
4. Laufmetadaten (run-id, config snapshot, timestamps) sind nachvollziehbar.
5. Konfiguration ist auf K80 realistisch (kein bf16-Zwang, OOM-robuste Defaults).

### Risiken
- OOM bei Sequenzlänge/Batches
- Langsame Iterationszeiten auf K80

---

## Phase 3 — Evaluation und Baseline-Vergleich

### Ziel
Standardisierte Bewertung von Base vs. LoRA-Adapterläufen.

### Lieferobjekte
- `src/scripts/eval.py` (MVP-Evaluation)
- `configs/eval.yaml`
- Ergebnisartefakte (z. B. `predictions.jsonl`, `summary.json`) unter `data/evals/<run-id>/`

### Akzeptanzkriterien
1. Evaluationslauf ist per CLI reproduzierbar.
2. Metriken und Rohvorhersagen werden getrennt gespeichert.
3. Mindestens ein Baseline-Vergleich (Base-Modell vs. Adapter) ist dokumentiert.
4. Fehlerfälle pro Sample werden protokolliert, ohne den Gesamtlauf unnötig zu stoppen (konfigurierbar).

### Risiken
- Vergleichbarkeit leidet bei nicht fixierten Prompts/Seeds
- Metriken decken Fachqualität nur teilweise ab

---

## Phase 4 — Betriebsstabilität, Troubleshooting, Audit

### Ziel
Wiederholbare Abläufe und kontrollierbares Fehlermanagement für längere Trainingszyklen.

### Lieferobjekte
- `docs/TROUBLESHOOTING_K80.md`
- Auditable Run-Konventionen (run-id, Dataset-Hash, Config-Snapshot)
- Standard-Prozeduren für OOM/Instabilität/Kompatibilitätsprobleme

### Akzeptanzkriterien
1. Häufige K80-Probleme sind mit konkreten Gegenmaßnahmen dokumentiert.
2. Jeder Trainingslauf besitzt eindeutig zuordenbare Run-ID und Artefaktpfade.
3. CUDA/PyTorch-Kompatibilität ist verifizierbar und dokumentiert.
4. Reproduktionsschritte eines abgeschlossenen Laufs sind in ≤ 10 Minuten auffindbar.

### Risiken
- Divergenz zwischen Dokumentation und tatsächlicher Konfiguration
- Fehlende Disziplin bei Run-Protokollierung

---

## Phase 5 — SEAL-MVP Self-Edit Pipeline (Accepted / umgesetzt)

### Ziel
Deterministische, auditierbare Self-Edit-Pipeline als reproduzierbarer Erweiterungspfad des Trainingssystems.

### Umgesetzter Stand (Ist)
- `src/scripts/generate_self_edits.py` als stabiler Entry-Point mit Modi:
  - `--mode placeholder` (kompatibler Legacy-Pfad)
  - `--mode generate` (deterministischer Self-Edit-Loop)
  - `--mode validate` (fail-fast Artefakt-/JSONL-Validierung)
- Verbindliche Run-Artefakte unter:
  - `data/self_edits/runs/<run_id>/sources.snapshot.jsonl`
  - `data/self_edits/runs/<run_id>/candidates.jsonl`
  - `data/self_edits/runs/<run_id>/verifications.jsonl`
  - `data/self_edits/runs/<run_id>/accepted.derived.jsonl`
  - `data/self_edits/runs/<run_id>/manifest.json`
- Stabiler Exportpfad:
  - `data/training/derived/self_edits.accepted.jsonl`
- Makefile-Integration:
  - `make self-edits-generate`
  - `make self-edits-validate`
  - `make self-edits` als Alias auf `self-edits-generate`
- Deterministische Verifikation:
  - Entscheidungen `accept | reject | needs_review`
  - regelbasierte Checks (Pflichtfelder, No-op/Diff, einfache Policy-Heuristiken)

### Abnahme (erfüllt)
1. Run-Artefakte + Manifest werden pro Run konsistent erzeugt.
2. Accepted-Export ist vorhanden und als JSONL validierbar.
3. Provenance-Felder in Accepted-Samples sind vorhanden (candidate/source/verification refs).
4. Validate-Modus schlägt bei Strukturfehlern deterministisch fehl.

### Risiken (verbleibend)
- Qualitätsgrenze durch rein regelbasierten Verifier (ohne semantischen Judge).
- Zusätzlicher Storage- und Retention-Bedarf für `data/self_edits/runs/`.

### Next-Phase Backlog (Phase 5.x)
1. Human-Review-Queue für `needs_review` inkl. Freigabe-/Ablehnungsworkflow.
2. Optionaler zweiter Verifier (LLM-Judge) als explizit aktivierbarer Modus.
3. Merge-Strategie für Derived Samples im Training feinjustieren:
   - Cap/Weighting/Sampling pro Laufprofil
   - Dedupe- und Prioritätsregeln dokumentieren
4. Qualitätsmetriken für Self-Edit-Wirkung verbindlich machen:
   - Einfluss auf `eval-val`-Teilmetriken
   - Delta-Reporting je Run
5. Retention-Regeln für Self-Edit-Artefakte formalisieren (Schutz kritischer Runs/Manifeste).

---

## Phase 6 — Qualitätssicherung und Release-Reife (v1.0 lokal)

### Ziel
Stabiler, dokumentierter Stand für wiederkehrenden lokalen Einsatz.

### Lieferobjekte
- Release-Checkliste (Setup, Training, Eval, Artefakte, Doku)
- Versionierte ADRs in `.ai/`
- Minimaler Regressionstest für Kernpfade (Smoke-Tests)

### Akzeptanzkriterien
1. Neuaufbau auf sauberem Host ist reproduzierbar.
2. Mindestens ein dokumentierter End-to-End-Lauf (Prepare → Train → Eval) ist erfolgreich.
3. Abweichungen/Annahmen sind in den Dokumenten explizit vermerkt.
4. Roadmap-Punkte Phase 0–4 sind als „erfüllt“ markiert und belegt.

### Risiken
- Technische Schulden aus schnellen MVP-Entscheidungen
- Unzureichende Testabdeckung bei Änderungen

---

## Meilensteinübersicht (Kurzform)

| Meilenstein | Inhalt | Exit-Kriterium |
|---|---|---|
| M0 | Container-Stack bereit | Trainer-Container mit GPU läuft stabil |
| M1 | Datenformat stabil | JSONL-Validierung und Normalisierung vorhanden |
| M2 | Erstes LoRA-Training | Adapter + Logs mit Run-ID gespeichert |
| M3 | Evaluation aktiv | Vergleichbare Metrik-Reports erzeugt |
| M4 | Audit/Troubleshooting | Reproduktion + Fehlerbehandlung dokumentiert |
| M5 | Self-Edit Inkrement 1 | Schema-konforme Edit-Kette mit Audit-Feldern |
| M6 | v1.0 lokal | End-to-End reproduzierbar, releasefähig |

---

## Abhängigkeiten und Annahmen

### Annahmen
- Host erfüllt CUDA-/Treiberanforderungen für gewählten Container-Stack.
- Verwendetes 3B-Basismodell ist lizenz- und zugriffsseitig verfügbar.
- Trainingsdaten dürfen rechtlich für Fine-Tuning genutzt werden.

### Offene Punkte
1. Finales Basismodell für den „Default“-Pfad (OPT 2.7B vs. Alternative).
2. Verbindliche Evaluationsmetriken für Domänenqualität.
3. Entscheidung, ob und wann Quantisierung (`bitsandbytes`) produktiv genutzt wird.
4. Governance-Regeln für Acceptance/Reject in Self-Edit-Schleifen.

---

## Definition of Done (projektweit)

Ein Roadmap-Abschnitt gilt als abgeschlossen, wenn:
1. Lieferobjekte im Repo vorhanden sind,
2. Akzeptanzkriterien praktisch verifiziert wurden,
3. Run-Artefakte und Konfiguration nachvollziehbar abgelegt sind,
4. bekannte Risiken/Restunsicherheiten dokumentiert wurden.