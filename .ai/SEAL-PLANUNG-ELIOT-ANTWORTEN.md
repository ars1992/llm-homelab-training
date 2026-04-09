# SEAL-PLANUNG-ELIOT-ANTWORTEN

## Dokumentkontrolle
- Status: Arbeitsstand / Planungsgrundlage
- Version: 1.0
- Datum: 2026-04-10
- Quelle: Antworten von Eliot auf die SEAL-Planungsfragen
- Geltungsbereich: `llm-homelab-training`, zukünftiger Ausbau von `src/scripts/generate_self_edits.py`

---

## Zweck

Dieses Dokument hält die von Eliot gelieferten Planungsantworten für den nächsten Ausbau des Projekts in Richtung einer SEAL-inspirierten Self-Edit-Pipeline fest.

Ziel ist eine nachvollziehbare, auditierbare und technisch umsetzbare Grundlage für den Umbau von:

- `src/scripts/generate_self_edits.py`

Wichtig:
- Der aktuelle Codezustand ist weiterhin ein Placeholder.
- Dieses Dokument beschreibt die geplante fachliche Zielstruktur, nicht den bereits umgesetzten Ist-Zustand.

---

## Ausgangslage

Das Skript `src/scripts/generate_self_edits.py` ist derzeit ein technischer Placeholder mit folgendem Verhalten:

- Einlesen eines JSONL-Datasets
- Validierung von Basisfeldern
- Erzeugung deterministischer Placeholder-Kandidaten
- Schreiben von JSONL- und Report-Artefakten
- keine echte modellbasierte Edit-Generierung
- keine Verifikation
- keine Akzeptanzentscheidung
- keine Rückführung akzeptierter Edits in Trainingsdaten

Damit ist das Skript aktuell nur geeignet für:

- Pfadstabilisierung
- Formatvalidierung
- frühe Pipeline-Vorbereitung
- Audit- und Report-Struktur

---

## 1. Zielprozess des SEAL-Loops

Von Eliot empfohlener End-to-End-Ablauf:

1. Input:
   - Basis-Trainingsinstanz, z. B. Prompt/Response oder strukturiertes Trainingssample
   - zusätzlich ein Zielkriterium, z. B. „Improve X“

2. Kandidaterzeugung:
   - Erzeuge `N` Self-Edit-Kandidaten
   - jeder Kandidat enthält:
     - Edit-Anweisung
     - erwartete Änderung
     - optional eine Begründung

3. Normalisierung:
   - Canonicalize / trim
   - deterministische Serialisierung
   - Dubletten entfernen

4. Verifikation:
   - jeden Kandidaten gegen definierte MVP-Regeln prüfen
   - Ergebnis vollständig protokollieren

5. Auswahl:
   - akzeptierte Kandidaten bewerten und ranken
   - mögliche Kriterien:
     - Score
     - Risk
     - Coverage
   - Top-`k` auswählen

6. Rückführung:
   - für jeden akzeptierten Kandidaten ein abgeleitetes Trainingssample erzeugen
   - Quelle und abgeleitetes Sample getrennt speichern
   - vollständige Auditspur erhalten

7. Export:
   - auditierbares Gesamtartefakt schreiben
   - zusätzlich nur akzeptierte Samples für den Trainingspfad exportieren

8. Optionaler Folge-Loop:
   - Reject-Gründe aggregieren
   - daraus nächste Kandidaterzeugung steuern

### Offene Entscheidung
Ob automatisches Re-Prompting bereits im MVP enthalten sein soll, ist noch nicht entschieden.

---

## 2. Fachliches Datenmodell

### Minimale Entitäten

#### A) `SourceSample`
Repräsentiert das ursprüngliche Trainings- oder Eingabebeispiel.

Pflichtfelder:
- `id`
- `content`

Auditfelder:
- `created_at`
- `source_path` oder `source_ref`
- `content_hash`
- `schema_version`

Bedeutung:
- stabile Quelle für alle abgeleiteten Edit-Kandidaten

---

#### B) `EditCandidate`
Repräsentiert einen erzeugten Self-Edit-Vorschlag.

Pflichtfelder:
- `id`
- `source_sample_id`
- `edit_spec`

Auditfelder:
- `created_at`
- `generator`
- `generator_params`
- `prompt_ref` (falls LLM-basiert)
- `candidate_hash`
- `parent_run_id`

Bedeutung:
- einzelner Änderungsvorschlag auf Basis eines `SourceSample`

---

#### C) `VerificationRun`
Repräsentiert das Prüfergebnis für einen Kandidaten.

Pflichtfelder:
- `id`
- `candidate_id`
- `verifier_type`
- `verdict`

Auditfelder:
- `created_at`
- `verifier_version`
- `checks`
- `score` (optional)
- `confidence` (optional)
- `notes`
- `evidence_ref`

Mögliche Werte für `verdict`:
- `accept`
- `reject`
- `needs_review`

Bedeutung:
- nachvollziehbare Entscheidungsebene zwischen Kandidat und Trainingsrückführung

---

#### D) `DerivedTrainingSample`
Repräsentiert ein akzeptiertes, aus einem Kandidaten abgeleitetes Trainingsbeispiel.

Pflichtfelder:
- `id`
- `candidate_id`
- `source_sample_id`
- `jsonl_record`

Auditfelder:
- `created_at`
- `export_path`
- `record_hash`
- `format_version`
- `provenance`

Bedeutung:
- tatsächlich in den Trainingspfad rückführbares Sample

---

#### E) `SelfEditRun`
Diese Entität wurde von Eliot nicht separat ausgeformt, ist aber aus Projektsicht sinnvoll.

Pflichtfelder:
- `run_id`
- `status`
- `config_ref`

Auditfelder:
- `created_at`
- `manifest_path`
- `candidate_count`
- `accepted_count`
- `rejected_count`
- `needs_review_count`
- `hashes`

Bedeutung:
- Klammer über alle Artefakte eines Self-Edit-Laufs

---

## 3. Relationen

Verbindliche minimale Relationen:

- `SourceSample 1 --- N EditCandidate`
- `EditCandidate 1 --- N VerificationRun`
- `EditCandidate 0 --- 1 DerivedTrainingSample`

Abgeleitete Regel:
- Ein `DerivedTrainingSample` darf nur existieren, wenn mindestens ein akzeptierendes Verifikationsergebnis vorliegt.

---

## 4. Pflichtfelder / Auditfelder nach Entität

### `SourceSample`
Pflicht:
- `id`
- `content`

Audit:
- `created_at`
- `source_path`
- `source_ref`
- `content_hash`
- `schema_version`

### `EditCandidate`
Pflicht:
- `id`
- `source_sample_id`
- `edit_spec`

Audit:
- `created_at`
- `generator`
- `generator_params`
- `prompt_ref`
- `candidate_hash`
- `parent_run_id`

### `VerificationRun`
Pflicht:
- `id`
- `candidate_id`
- `verifier_type`
- `verdict`

Audit:
- `created_at`
- `verifier_version`
- `checks`
- `score`
- `confidence`
- `notes`
- `evidence_ref`

### `DerivedTrainingSample`
Pflicht:
- `id`
- `candidate_id`
- `source_sample_id`
- `jsonl_record`

Audit:
- `created_at`
- `export_path`
- `record_hash`
- `format_version`
- `provenance`

### `SelfEditRun`
Pflicht:
- `run_id`
- `status`
- `config_ref`

Audit:
- `created_at`
- `manifest_path`
- `counts`
- `hashes`
- `generator_version`

---

## 5. Akzeptanzlogik

### Grundsatz
Für den MVP soll ein **deterministischer, regelbasierter Verifier** verwendet werden.

### Ziel
Keine modellabhängige oder schwer reproduzierbare Entscheidung im ersten Ausbauschritt.

### Accept-Regel
Ein Kandidat darf nur akzeptiert werden, wenn:

1. `edit_spec` nicht leer und formal gültig ist
2. keine harte Invariante verletzt wird
3. ein echter Unterschied zur Quelle vorliegt
4. alle verbindlichen Checks erfolgreich sind

Zusatzregel:
- `diff != 0` ist Pflicht
- reine No-op-Kandidaten dürfen nicht akzeptiert werden

### Reject-Regel
Ein Kandidat wird verworfen, wenn:

- `edit_spec` leer oder ungültig ist
- Schema-/Format-/Policy-Invariante verletzt wird
- das abgeleitete Sample identisch zur Quelle ist
- zentrale technische Checks fehlschlagen

### Needs-Review-Regel
Ein Kandidat wird nicht automatisch exportiert, wenn:

- die Checks widersprüchlich sind
- die Confidence unter einem noch festzulegenden Threshold liegt

### MVP-Verifier
Empfohlen:
- deterministische Regeln
- Schema-Checks
- Diff-Checks
- einfache Heuristiken

### Offene Entscheidung
Ein optionaler zweiter Verifier, z. B. LLM-Judge, ist ausdrücklich **nicht MVP-Standard** und nur spätere Ausbaustufe.

---

## 6. Integration in die Trainingspipeline

Von Eliot vorgeschlagene Zielstruktur:

### Quelle
- `data/source/train.jsonl`
- oder bestehender Trainingsquellenpfad

Bedeutung:
- read-only im Self-Edit-Loop

### Self-Edit-Audit-Artefakte
Unter:
- `data/self_edits/runs/<run_id>/`

Geplante Inhalte:
- `sources.snapshot.jsonl`
- `candidates.jsonl`
- `verifications.jsonl`
- `accepted.derived.jsonl`
- `manifest.json`

### Trainings-Export
Unter:
- `data/training/derived/self_edits.accepted.jsonl`

Bedeutung:
- nur akzeptierte Self-Edits
- klar getrennt von der ursprünglichen Quelle

---

## 7. Trennung Quelle vs. abgeleitetes Trainingssample

Diese Trennung ist verbindlich einzuhalten:

### Quelle
- bleibt unverändert
- ist die fachliche Ursprungsreferenz

### Abgeleitetes Sample
- entsteht nur aus akzeptiertem Kandidaten
- enthält vollständige Provenance

Empfohlene Provenance-Felder:
- `source_sample_id`
- `candidate_id`
- `verification_run_ids`

Ziel:
- nachvollziehbar machen, wie ein Trainingssample entstanden ist
- spätere Reproduzierbarkeit und Auditierbarkeit sichern

---

## 8. Fehler- und Sonderfälle

### Leerer Kandidat
Behandlung:
- Kandidat speichern
- `VerificationRun = reject`
- Grund: `EMPTY_CANDIDATE`
- kein `DerivedTrainingSample`

### Identischer Output / No-op
Behandlung:
- `reject`
- Grund: `NO_OP`
- Nachweis über:
  - identischen Hash
  - leeren Diff
  - gleiche serialisierte Struktur

### Widersprüchliche Verifikation
Behandlung:
- `needs_review`
- nicht in `accepted` exportieren
- im `manifest` als Konflikt zählen

### Offene Entscheidung
Ob `needs_review` zusätzlich in eine separate Human-Review-Queue exportiert wird, ist noch nicht entschieden.

### Niedrige Confidence
Behandlung:
- `needs_review` oder `reject`

### Offene Entscheidung
Threshold und Mapping von Confidence zu `needs_review` oder `reject` sind noch nicht final festgelegt.

### Kaputtes JSONL
Behandlung:
- Export-Datei fail-fast behandeln
- fehlerhafte Zeilen in `*_errors.jsonl` schreiben mit:
  - `line_number`
  - `raw`
  - `parse_error`

Ziel:
- Run bleibt auditierbar
- Trainingsexport wird bei beschädigten Eingaben kontrolliert abgebrochen

---

## 9. Abgrenzung zum aktuellen Placeholder

### Was bestehen bleiben soll
- Dateipfad und Skriptname:
  - `src/scripts/generate_self_edits.py`
- CLI-Rolle als Einstiegspunkt für Self-Edit-Generierung
- Grundstruktur:
  - Einlesen
  - Validierung
  - Run-ID
  - Ausgabe von Artefakten
  - Report-/Audit-Logik

### Was ersetzt oder erweitert werden muss
Der aktuelle Placeholder-Body muss erweitert oder ersetzt werden um:

1. Laden strukturierter `SourceSample`
2. echte Kandidaterzeugung
3. Verifikation
4. Export aller Self-Edit-Artefakte
5. Export akzeptierter Trainingssamples
6. Manifest- und Hashing-Logik

### Placeholder parallel behalten
Ja.

Empfohlen:
- `--mode placeholder`
- oder `--dry-run`

In diesem Modus:
- Dummy-Kandidaten erzeugen
- vollständige Auditstruktur schreiben
- kein echter Trainingsexport

### Offene Entscheidung
Ob der Placeholder-Modus Standard bleibt oder nur noch als Testmodus dient, ist noch nicht entschieden.

---

## 10. Konsequenzen für `generate_self_edits.py`

### Kurzbewertung
Das bestehende Skript ist weiterhin relevant, aber nicht als fertige Implementierung.

### Fachliche Zielrolle
`generate_self_edits.py` wird künftig:
- Entry-Point
- Self-Edit-Orchestrator
- Audit-Artefakt-Exporter

### Nicht mehr ausreichend
Die aktuelle Placeholder-Logik allein reicht nicht für:
- fachlich valide Edit-Erzeugung
- Verifikation
- Akzeptanzentscheidung
- Trainingsintegration

---

## 11. Offene Entscheidungen

Die folgenden Punkte sind laut Eliot noch nicht abschließend entschieden und müssen vor Umsetzung fachlich bestätigt werden:

1. Automatisches Re-Prompting im Loop
2. Human-Review-Queue für `needs_review`
3. Threshold-Mapping für Confidence
4. Standardverhalten des Placeholder-Modus
5. konkrete Zielpfade im bestehenden Repo, falls von Eliots Vorschlag abgewichen werden soll

---

## 12. Empfohlener nächster Umsetzungsschritt

Vor einem Code-Umbau sollten als nächstes spezifiziert werden:

1. endgültige Zielpfade im Repo
2. finales JSON-Schema für:
   - `SourceSample`
   - `EditCandidate`
   - `VerificationRun`
   - `DerivedTrainingSample`
3. deterministische MVP-Checks für den Verifier
4. Exportformat für akzeptierte Trainingssamples
5. Abgrenzung zwischen Placeholder, Dry-Run und produktiver Self-Edit-Ausführung

---

## Kurzfassung

Eliots Antwort bestätigt:

- `generate_self_edits.py` bleibt als Einstiegspunkt bestehen
- der Placeholder-Modus soll parallel erhalten bleiben
- für den MVP ist ein deterministischer regelbasierter Verifier vorgesehen
- akzeptierte Self-Edits müssen getrennt von der Quelle gespeichert werden
- alle Schritte müssen vollständig auditierbar bleiben

Damit liegt jetzt eine belastbare Planungsgrundlage für den nächsten SEAL-Ausbauschritt vor.