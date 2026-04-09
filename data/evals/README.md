# data/evals/

Dieses Verzeichnis enthält **lokale Evaluationsartefakte** des Projekts `llm-homelab-training`.

Ziel dieses Ordners ist die **nachvollziehbare Ablage von Eval-Ergebnissen pro Lauf**, getrennt von Source-Code, Konfiguration und trainierten Modellartefakten.

## Zweck

Unter `data/evals/` werden Ergebnisse von Auswertungen abgelegt, zum Beispiel:

- Vorhersagen eines Modells für ein Eval-Dataset
- zusammenfassende Bewertungsberichte
- Regression-Reports für einen bestimmten Adapter-Run
- Smoke-Eval-Artefakte für technische Kurztests

Die Inhalte sind **laufzeitbezogene Outputs** und in der Regel **nicht versioniert**.

## Typische Struktur

```text
data/evals/
├── README.md
├── smoke-20260406T092145Z/
│   ├── predictions.jsonl
│   └── summary.json
├── val-real-20260408T182928Z-20260408T205138Z/
│   ├── val_predictions.jsonl
│   └── val_report.json
└── <eval-run-id>/
    └── ...
```

## Namenskonventionen

Je nach Evaluationsart werden unterschiedliche Run-IDs verwendet:

- `smoke-<timestamp>`  
  Technischer Kurztest mit kleinem Datensatz

- `val-<train-run-id>-<timestamp>`  
  Regression-Evaluation für einen konkreten Trainingslauf

- weitere `<eval-run-id>`  
  projektspezifische Eval-Läufe mit eindeutigem Zeitbezug

## Inhaltstypen

Typische Dateien in Unterordnern:

- `predictions.jsonl`  
  Modellvorhersagen pro Sample

- `summary.json`  
  kompakte technische Metrikzusammenfassung

- `val_predictions.jsonl`  
  Vorhersagen der Regression-Evaluation

- `val_report.json`  
  strukturierter Report mit Pass-/Fail-Bewertung, Coverage und Teilmetriken

## Betriebsregeln

- Jeder Eval-Lauf schreibt in einen **neuen Unterordner**.
- Vorhandene Eval-Verzeichnisse werden **nicht überschrieben**.
- Eval-Artefakte sind an eine eindeutige Run-ID gebunden.
- Große oder alte Eval-Ergebnisse dürfen lokal bereinigt werden, sofern keine Audit-/Vergleichspflicht mehr besteht.
- Relevante Freigabeentscheidungen werden nicht aus Dateinamen, sondern aus den zugehörigen Pointer-/Summary-Dateien unter `data/runs/` abgeleitet.

## Beziehung zu anderen Verzeichnissen

- `data/models/`  
  enthält die trainierten Adapter/Checkpoints, gegen die evaluiert wird

- `data/logs/`  
  enthält Trainingslogs, nicht die fachlichen Eval-Ergebnisse

- `data/runs/`  
  enthält Pointer und Statusdateien wie `LATEST_REALRUN_ID`, `LATEST_OK_ADAPTER_ID` oder Promotionszusammenfassungen

## Aufbewahrung / Cleanup

Dieses Verzeichnis kann mit der Zeit stark anwachsen. Daher gilt:

- alte Eval-Läufe regelmäßig prüfen
- nur benötigte Vergleichs- und Audit-Artefakte aufbewahren
- bei vollständigem Test-Neustart können lokale Eval-Artefakte kontrolliert entfernt werden
- Cleanup darf nicht mit fachlicher Freigabe verwechselt werden

## Wichtig

- Keine Secrets, Tokens oder Zugangsdaten in diesem Verzeichnis speichern.
- Keine manuelle Bearbeitung von Eval-Reports, wenn diese als Nachweis dienen sollen.
- Dieses Verzeichnis ist ein **Runtime-Output-Bereich**, keine Quelle für Konfiguration oder Geschäftslogik.