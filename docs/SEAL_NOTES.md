# SEAL_NOTES

## Dokumentzweck

Dieses Dokument beschreibt ein **SEAL-inspiriertes** Architektur- und Umsetzungsmodell für `llm-homelab-training`, mit Fokus auf:

- reproduzierbare lokale Ausführung (Container-first)
- deterministische Datenflüsse
- auditierbare Selbstverbesserungszyklen
- K80-kompatible Ressourcenplanung

SEAL wird hier nicht als 1:1-Implementierung verstanden, sondern als Designprinzip:
**Generate -> Critique -> Edit -> Verify -> Curate -> Retrain**.

---

## Ausgangslage und Randbedingungen

1. Zielplattform ist lokal, ohne Cloud-Abhängigkeit.
2. Primäres Trainingsziel ist LoRA/Fine-Tuning eines ~3B Basismodells.
3. Hardware-Limit: NVIDIA K80 (geringe VRAM- und Durchsatzreserven).
4. Reproduzierbarkeit hat Vorrang vor maximaler Geschwindigkeit.
5. Alle Änderungen und Datenherkünfte müssen nachvollziehbar sein.

---

## Begriffsdefinitionen

- Source Sample: Ursprüngliches Trainingsbeispiel im Format `{instruction, input, output}`.
- Candidate Output: Modellantwort auf ein Source Sample.
- Critique: Strukturierte Bewertung eines Candidate Outputs.
- Edit Proposal: Konkrete Änderungsvorschläge inkl. Begründung.
- Verified Edit: Edit Proposal, das definierte Kriterien erfüllt.
- Curation: Auswahl freigegebener Beispiele für den nächsten Trainingszyklus.

---

## Zielarchitektur (fachlich)

### Pipeline-Domänen (strikt getrennt)

1. Inference Domain  
   Erzeugt Candidate Outputs aus Input-Samples.

2. Critique Domain  
   Bewertet Candidate Outputs mittels Regeln/Heuristiken (später optional Judge-Modell).

3. Edit Domain  
   Erzeugt Selbstkorrekturen auf Basis der Critique.

4. Verification Domain  
   Prüft Korrekturen gegen formale Akzeptanzkriterien.

5. Curation Domain  
   Selektiert verwertbare Datensätze für Retraining.

6. Training Domain  
   Trainiert LoRA-Adapter auf kuratierten Daten.

### Orchestrierung

- Jede Pipeline-Instanz hat eine eindeutige `pipeline_run_id`.
- Jeder Schritt erzeugt versionierte Artefakte unter `data/`.
- Jeder Übergang ist als Event im Audit-Log dokumentiert.

---

## Datenobjekte und Identitäten

Pflichtprinzip: Jede Entität hat eine eindeutige ID.

- `sample_id`: ID des Quellsamples
- `candidate_id`: ID einer Modellantwort
- `critique_id`: ID einer Kritikinstanz
- `edit_id`: ID eines Edit-Vorschlags
- `verification_id`: ID einer Verifikationsausführung
- `curation_id`: ID einer Selektionsentscheidung
- `run_id`: ID eines End-to-End Laufs

Empfohlene ID-Konvention: `<entity>-<UTC timestamp>-<short hash>`.

---

## Audit-Trail Mindestanforderungen

Für jeden Eventtyp sind folgende Felder verpflichtend:

- `event_id`
- `event_type`
- `event_ts_utc`
- `pipeline_run_id`
- `actor_type` (`system`, `model`, `human`)
- `actor_id`
- `input_refs` (Liste von IDs/Dateireferenzen)
- `output_refs` (Liste von IDs/Dateireferenzen)
- `status` (`started`, `completed`, `failed`)
- `error_code` (optional)
- `error_message` (optional)

Eventtypen (MVP):

1. `candidate_generation_started/completed/failed`
2. `critique_started/completed/failed`
3. `edit_generation_started/completed/failed`
4. `verification_started/completed/failed`
5. `curation_started/completed/failed`
6. `retrain_started/completed/failed`

---

## Akzeptanzkriterien für Verified Edits (MVP)

Ein Edit gilt als verifiziert, wenn alle Kriterien erfüllt sind:

1. Formatkonsistenz  
   Antwort erfüllt das geforderte Ausgabeschema/Antwortformat.

2. Regelkonformität  
   Keine verbotenen Inhalte, keine offensichtlichen Policy-Verletzungen.

3. Qualitätsverbesserung (mindestens 1 Indikator)  
   Beispiel: höhere Klarheit, geringere Widersprüche, besserer Bezug zur Instruction.

4. Nicht-Regression  
   Edit verschlechtert nicht gegen definierte Baseline-Regeln.

5. Reproduzierbarkeit  
   Verifikation kann mit identischen Inputs wiederholt werden.

---

## Fehlerzustände und deterministische Reaktion

1. Datensatzfehler (`DATA_SCHEMA_INVALID`)  
   Reaktion: Sample überspringen, Fehler in Report/Audit aufnehmen.

2. Inferenzfehler (`INFER_RUNTIME_ERROR`)  
   Reaktion: Retry mit begrenzter Anzahl; bei Fehlschlag Run als `partial_failed`.

3. Critique-Parserfehler (`CRITIQUE_PARSE_ERROR`)  
   Reaktion: Fallback auf regelbasierten Minimal-Critique, markieren.

4. Verifikation Timeout (`VERIFY_TIMEOUT`)  
   Reaktion: Sample als `unverified`, nicht für Retraining nutzen.

5. OOM auf K80 (`GPU_OOM`)  
   Reaktion: Batch/Seq-Länge reduzieren, Checkpointing aktivieren, Schritt erneut.

---

## Staged Implementation Plan

## Stage 0: Baseline stabilisieren

Ziel: Solider, reproduzierbarer LoRA-Basispfad.

Lieferobjekte:
- Trainingsskript stabil (`train_lora.py`)
- Eval-Baseline definiert (`eval.py`)
- Dataset-Validierung aktiv (`prepare_dataset.py`)

Abnahme:
- Ein vollständiger Trainings- und Eval-Lauf ist reproduzierbar.

## Stage 1: Candidate Generation Layer

Ziel: Kandidatenantworten aus Basismodell/Adapter erzeugen.

Lieferobjekte:
- Script: `generate_candidates.py` (neu, später)
- Output: `data/self_edit/candidates/<run_id>.jsonl`
- Audit-Events für Start/Ende/Fehler

Abnahme:
- Für jedes Input-Sample existiert mindestens ein Candidate oder ein Fehlerstatus.

## Stage 2: Critique Layer

Ziel: Strukturierte Kritik mit deterministischen Regeln.

Lieferobjekte:
- Script: `critique_candidates.py` (neu, später)
- Regelset v1 (Länge, Vollständigkeit, Instruction-Bezug, Offensichtliche Fehler)
- Output: `data/self_edit/critiques/<run_id>.jsonl`

Abnahme:
- Jede Critique enthält Scores + Begründungen + Rule IDs.

## Stage 3: Edit Layer

Ziel: Erzeugung konkreter Edit-Vorschläge aus Critique.

Lieferobjekte:
- Erweiterung von `generate_self_edits.py`
- Strukturkonforme Records gemäß `self_edit.schema.json`
- Output: `data/self_edit/edits/<run_id>.jsonl`

Abnahme:
- Jeder Edit referenziert `candidate_id` und `critique_id`.

## Stage 4: Verification Layer

Ziel: Nur verifizierte Edits in den Trainingspool übernehmen.

Lieferobjekte:
- Script: `verify_edits.py` (neu, später)
- Verifikationsreport mit Pass/Fail-Gründen
- Output: `data/self_edit/verified/<run_id>.jsonl`

Abnahme:
- Passrate, Fail-Gründe und Coverage sind im Report ausweisbar.

## Stage 5: Curation + Retraining Loop

Ziel: Kontrollierter Selbstverbesserungszyklus.

Lieferobjekte:
- Script: `curate_for_retrain.py` (neu, später)
- Trainingsdatensatz v2 aus Verified Edits
- Retraining-Lauf mit Vergleich zu Baseline

Abnahme:
- Metrikvergleich dokumentiert: Baseline vs. Self-Edit-Adapter.

---

## Metrikmodell (MVP)

Pflichtmetriken je Lauf:

1. `acceptance_rate`  
   Anteil verifizierter Edits an erzeugten Edits.

2. `regression_rate`  
   Anteil von Edits mit Verifikations-Regression.

3. `format_violation_rate`  
   Anteil von Antworten mit Schema-/Formatverletzungen.

4. `eval_delta_exact_match`  
   Delta Exact-Match gegenüber Baseline-Eval.

5. `eval_delta_token_f1`  
   Delta Token-F1 gegenüber Baseline-Eval.

Metrikartefakte:
- `summary.json` pro Stage
- Aggregation in `data/self_edit/reports/<run_id>/`

---

## Verzeichnislogik für Self-Edit-Artefakte (Vorschlag)

Unter `data/self_edit/`:

- `candidates/`
- `critiques/`
- `edits/`
- `verified/`
- `curated/`
- `reports/`
- `audit/`

Alle Dateien tragen `run_id` im Dateinamen.

---

## K80-spezifische Betriebsrichtlinien

1. Maximal konservative Batchgrößen verwenden.
2. `gradient_accumulation_steps` statt größerer Device-Batches erhöhen.
3. `max_seq_length` initial niedrig halten (zuerst 256/384 testen).
4. Laufzeiten und OOMs im Audit mitschreiben.
5. Bei Instabilität zuerst Determinismus prüfen (Seed, Config-Snapshot, Dataset-Hash).

---

## Security, Compliance, Nachvollziehbarkeit

1. Keine Secrets in Dataset- oder Config-Dateien.
2. Keine ungeprüften personenbezogenen Daten in Trainingssamples.
3. Modell- und Datensatzlizenzen je Run dokumentieren.
4. Jede automatisierte Änderung ist über Audit-Events rückverfolgbar.
5. Outputs für Retraining sind durch IDs und Source-Referenzen vollständig herleitbar.

---

## Offene Punkte (vor produktivem Self-Edit-Loop zu klären)

1. Welches Basismodell ist final für 3B vorgesehen?
2. Welche harten Policy-Regeln gelten für Verifikation?
3. Welche Qualitätsgrenze ist Mindestanforderung für Curation?
4. Wie wird menschliche Freigabe in den Loop integriert (optional gate)?
5. Welche Evaluationssets gelten als verbindliche Regressionstests?

---

## Kurzfazit

Die SEAL-inspirierte Erweiterung soll nicht als unkontrollierter Autopilot umgesetzt werden, sondern als
**formal spezifizierter, auditierbarer und reproduzierbarer Mehrstufenprozess**.
Die Priorität liegt auf stabilen Datenverträgen, eindeutigen IDs, deterministischen Fehlerreaktionen und messbarer Qualitätsentwicklung.