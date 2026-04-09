# data/datasets/

## Zweck

Dieses Verzeichnis enthält Datensätze und datensatznahe Artefakte für Training, Evaluation und vorbereitende Verarbeitungsschritte im Projekt `llm-homelab-training`.

Es dient als lokaler Arbeitsbereich für:

- Trainingsdatensätze
- Evaluationsdatensätze
- generierte Zwischenstände aus der Datensatzaufbereitung
- Prüf- und Berichtsdaten zur Dataset-Qualität

Die Inhalte in diesem Verzeichnis können je nach Datei entweder:

1. **versionierte Referenzdaten** sein, oder
2. **lokale, generierte Laufzeit-Artefakte** sein.

Die Unterscheidung ist für Betrieb, Cleanup und Auditierbarkeit relevant.

---

## Grundregel

Nicht jede Datei in `data/datasets/` ist gleich zu behandeln.

### A) Versionierte Referenzdateien
Diese Dateien bilden einen stabilen, prüfbaren Projektstand ab und dürfen bewusst im Repository liegen.

Beispiele:

- `val.jsonl`
- `runbook_samples.jsonl`
- `exact_extraction_samples.jsonl`

Diese Dateien dienen u. a. als:

- Regression-Referenz
- Seed-Daten
- kontrollierte Eingaben für reproduzierbare Tests

### B) Generierte Laufzeitdateien
Diese Dateien entstehen bei Prepare-, Merge-, Validate- oder Trainingsläufen und sind in der Regel **nicht** als dauerhafte Referenz gedacht.

Beispiele:

- `train.jsonl`
- `train_vault.jsonl`
- `train.normalized.jsonl`
- `prepare_report.json`
- `prepare_vault_report.json`
- `merge_report.json`
- `val_validate_report.json`
- `self_edits.jsonl`
- `self_edits.report.json`

Diese Dateien dürfen bei einem Runtime-Reset oder vor einem neuen End-to-End-Test entfernt und neu erzeugt werden.

---

## Typische Inhalte

### Trainingsdatensätze
Datensätze für LoRA-/Fine-Tuning-Läufe.

Beispiele:

- `train.jsonl`
- `train_vault.jsonl`

### Evaluations- und Referenzdatensätze
Kleine, kontrollierte Datensätze zur fachlichen oder technischen Bewertung.

Beispiele:

- `val.jsonl`

### Seed- und Ergänzungsdaten
Gezielt gepflegte Zusatzdaten für bestimmte Wissensbereiche oder Extraktionsmuster.

Beispiele:

- `runbook_samples.jsonl`
- `exact_extraction_samples.jsonl`

### Reports und Validierungsergebnisse
Prüfberichte über Datensatzstruktur, Erzeugung oder Merge-Ergebnisse.

Beispiele:

- `prepare_report.json`
- `merge_report.json`
- `val_validate_report.json`

---

## Erwartete Formate

### JSONL
Das Standardformat für Trainingsdaten ist UTF-8 codiertes JSONL.

Erwartetes Schema pro Zeile:

```/dev/null/dataset-schema.jsonl#L1-1
{"instruction":"...","input":"...","output":"..."}
```

Pflichtfelder:

- `instruction` als nicht-leerer String
- `output` als nicht-leerer String

Optional:

- `input` als String, leer erlaubt

### Regression-Eval Format
Für `val.jsonl` gelten zusätzliche fachliche Felder, z. B.:

```/dev/null/val-schema.jsonl#L1-1
{"id":"val-001","instruction":"...","input":"","expected_contains":["..."],"tags":["regression","openbook"]}
```

---

## Betriebsregeln

1. Keine Secrets, Tokens oder Zugangsdaten in Datensatzdateien speichern.
2. Generierte Trainingsdaten dürfen überschrieben oder bei Reset entfernt werden.
3. Versionierte Referenzdatensätze dürfen nicht versehentlich durch Laufzeitprozesse zerstört werden.
4. Datensatzänderungen mit Einfluss auf Reproduzierbarkeit müssen dokumentiert und nachvollziehbar sein.
5. Datensatzquellen aus externen Vaults oder Host-Mounts sind als Eingangsquellen zu behandeln, nicht als Repository-Source-of-Truth.

---

## Cleanup / Reset

Bei einem vollständigen Runtime-Reset werden typischerweise **generierte** Datensatzartefakte entfernt und später neu erzeugt.

Erhalten bleiben sollen in der Regel:

- `README.md`
- `val.jsonl`
- `runbook_samples.jsonl`
- `exact_extraction_samples.jsonl`
- `.gitkeep` (falls vorhanden)

Entfernt werden dürfen je nach Reset-Modus insbesondere:

- `train.jsonl`
- `train_vault.jsonl`
- `train.normalized.jsonl`
- vorbereitende Reports
- temporäre Self-Edit-Dateien

---

## Audit- und Nachvollziehbarkeit

Wenn Datensätze neu erzeugt oder verändert werden, sollten folgende Punkte nachvollziehbar sein:

- Quelle der Eingabedaten
- verwendeter Verarbeitungsschritt / Befehl
- Zeitpunkt der Erzeugung
- Zielpfad
- Anzahl erzeugter Samples
- relevante Skip- oder Filtergründe

Für reproduzierbare Projektstände gilt:
Nicht nur der Datensatz selbst, sondern auch die Erzeugungslogik und ihre Reports sind fachlich relevant.

---

## Hinweis für Bedienung und Betrieb

Dieses Verzeichnis ist ein Arbeitsbereich für Datenpipeline und Training, kein beliebiger Ablageort.

Neue Dateien in diesem Verzeichnis sollten vorab klar eingeordnet werden als:

- Referenzdatei
- generiertes Artefakt
- Bericht
- temporärer Zwischenstand

Wenn diese Einordnung nicht klar ist, steigt das Risiko für:

- Drift
- fehlerhafte Cleanup-Prozesse
- unklare Reproduzierbarkeit
- versehentliches Committen oder Löschen wichtiger Daten