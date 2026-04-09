# data/runs/

Dieses Verzeichnis enthält den **lokalen Laufzustand** und **kleine Steuerungsdateien** für Training, Evaluation, Promotion und Smoke-Workflows.

Ziel ist, den aktuellen Betriebszustand des Projekts deterministisch und nachvollziehbar abzulegen, ohne große Modellartefakte oder Logs mit diesem Zustand zu vermischen.

## Zweck

Unter `data/runs/` liegen insbesondere:

- Pointer auf den zuletzt technisch erfolgreichen Run
- Pointer auf den zuletzt fachlich freigegebenen Adapter
- Lock-Dateien zur Vermeidung paralleler Heavy-Runs
- kleine Status- und Metadatendateien für Orchestrierung und Audit
- Smoke-spezifische Statusartefakte

Dieses Verzeichnis enthält **keine großen Modellgewichte**, sondern nur kleine Zustands- und Steuerdateien.

## Typische Inhalte

### `LATEST_REALRUN_ID`
Enthält die `run_id` des zuletzt technisch erfolgreich abgeschlossenen Real-Runs.

Beispiel:
- `real-20260408T182928Z`

Bedeutung:
- Referenz für den letzten erzeugten Trainingslauf
- nicht automatisch gleichbedeutend mit fachlich freigegebenem Serving-Stand

### `LATEST_OK_ADAPTER_ID`
Enthält die `run_id` des zuletzt **promoteten** und damit für Serving freigegebenen Adapters.

Bedeutung:
- Source-of-Truth für den aktuell freigegebenen Adapter
- wird von Serving gelesen
- darf nur nach erfolgreicher Eval/Promotion aktualisiert werden

Wichtige Regel:
- Inhalt ist entweder **leer** oder enthält **genau eine gültige `run_id`**
- keine Kommentare oder Zusatztexte in diese Datei schreiben

### `LATEST_OK_ADAPTER_PATH`
Enthält den abgeleiteten Pfad zum aktuell promoteten Adapter.

Beispiel:
- `data/models/real-20260408T182928Z`

Bedeutung:
- Hilfsreferenz für Diagnose und Betrieb
- führende Quelle bleibt dennoch `LATEST_OK_ADAPTER_ID`

### `LATEST_EVAL_RUN_ID`
Enthält die Kennung des zuletzt ausgeführten Eval-Runs.

Bedeutung:
- Referenz auf den zuletzt geschriebenen Eval-Bericht
- wird für Promotion und Nachvollziehbarkeit verwendet

### `LATEST_PROMOTION_SUMMARY.json`
Enthält die letzte Promotionsentscheidung in strukturierter Form.

Typische Inhalte:
- Kandidat-Run
- Eval-Run
- Schwellenwerte
- beobachtete Metriken
- Entscheidung (`promoted` oder `kept_previous`)

### `LOCK`
Lock-Datei zur Verhinderung paralleler schwerer Läufe.

Bedeutung:
- schützt vor gleichzeitigen Training-/Eval-Workflows
- wird von Orchestrierungs-Targets genutzt
- stale Locks nur bewusst und kontrolliert entfernen

## Unterverzeichnis `smoke/`

Dieses Unterverzeichnis enthält Zustands- und Berichtsdaten für Smoke-Workflows.

Typische Inhalte:
- `LATEST_RUN_ID`
- `report.txt`

Zweck:
- Nachweis eines technischen Kurztests
- Trennung von Smoke-Artefakten und Real-Run-Zustand

## Betriebsregeln

1. Dateien unter `data/runs/` sind **klein, textbasiert und lokal**.
2. Inhalte müssen deterministisch und maschinenlesbar bleiben.
3. Pointer-Dateien dürfen nur den erwarteten Minimalinhalt enthalten.
4. Ein technischer Real-Run ist nicht automatisch ein freigegebener Serving-Run.
5. Promotion und Serving-Freigabe müssen getrennt von technischem Training betrachtet werden.
6. Lock-Dateien dürfen nicht blind gelöscht werden.
7. Bei Runtime-Reset müssen Pointer und Lock-Dateien in einen definierten Ausgangszustand zurückgesetzt werden.

## Abgrenzung

Nicht in dieses Verzeichnis gehören:

- Modellgewichte
- Checkpoints
- TensorBoard-Logs
- große Eval-Ausgaben
- Rohdatensätze

Dafür sind zuständig:

- `data/models/`
- `data/logs/`
- `data/evals/`
- `data/datasets/`

## Reset / Cleanup

Vor einem neuen vollständigen End-to-End-Test kann dieses Verzeichnis gezielt zurückgesetzt werden.

Dabei gilt:
- `LATEST_OK_ADAPTER_ID` leeren
- `LATEST_OK_ADAPTER_PATH` auf Platzhalter zurücksetzen
- alte Lock-Dateien entfernen
- veraltete Laufreferenzen löschen, wenn ein echter Fresh-Start gewünscht ist

Für wiederholbare Rücksetzungen ist ein dedizierter Reset-Workflow dem manuellen Löschen einzelner Dateien vorzuziehen.

## Hinweis zur Auditierbarkeit

Obwohl `data/runs/` lokale Laufzeitdaten enthält, ist dieses Verzeichnis für die Nachvollziehbarkeit des Betriebs besonders wichtig.

Änderungen an Pointer-Dateien und Promotionszuständen beeinflussen direkt:

- welchen Adapter Serving verwendet
- von welchem Adapter Continue-Training startet
- welcher Run als letzter technischer Stand gilt

Deshalb müssen Inhalte in diesem Verzeichnis klar, minimal und reproduzierbar gehalten werden.