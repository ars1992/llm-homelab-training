# data/

Dieses Verzeichnis enthält **lokale Laufzeit-Artefakte** für Training und Evaluation.  
Ziel: Reproduzierbarkeit der Pipeline bei gleichzeitiger Trennung von Source-Code und erzeugten Outputs.

## Wichtig

- Inhalte unter `data/` sind überwiegend **nicht versioniert** (siehe `.gitignore`).
- Keine Secrets, Tokens oder Zugangsdaten in Dateien unter `data/` speichern.
- Große Modellartefakte und Logs bleiben lokal auf dem Host.

## Empfohlene Struktur

```text
data/
├── README.md                  # Diese Datei
├── datasets/                  # Lokale Datensätze (JSONL/Reports/Seeds)
│   ├── train.jsonl
│   ├── val.jsonl
│   └── runbook_samples.jsonl
├── models/                    # Trainierte Adapter/Checkpoints
│   └── <run-id>/
├── logs/                      # TensorBoard und Trainingslogs
│   └── <run-id>/
├── evals/                     # Eval- und Serving-Smoke-Reports
│   └── <run-id>/
├── self_edits/                # SEAL-MVP Run-Artefakte
│   └── runs/
│       └── <run-id>/
└── training/
    └── derived/               # Exportierte, abgeleitete Trainingssamples
        └── self_edits.accepted.jsonl
```

## Erwartete Pfade im Projekt

- Trainingsdaten (MVP): `data/datasets/train.jsonl`
- LoRA-Adapter Output: `data/models/<run-id>/`
- TensorBoard-Logs: `data/logs/<run-id>/`
- Eval-Reports: `data/evals/<run-id>/`
- Self-Edit Run-Artefakte: `data/self_edits/runs/<run-id>/`
- Derived Export (SEAL-MVP): `data/training/derived/self_edits.accepted.jsonl`

## Hinweis zur Reproduzierbarkeit

Reproduzierbarkeit wird durch folgende Kombination erreicht:

1. Gepinnte Abhängigkeiten im Container (`docker/requirements.txt`)
2. Feste Konfigurationen in `configs/`
3. Deterministische Pfadkonventionen unter `data/`
4. Trennung von Code und Laufzeitergebnissen

## Backup / Cleanup (lokal)

Da `data/` schnell groß werden kann:

- Regelmäßig alte Runs unter `data/models/`, `data/logs/`, `data/evals/` und `data/self_edits/runs/` bereinigen
- Wichtige Runs und abgeleitete Trainingsdaten (`data/training/derived/`) gezielt extern sichern (z. B. NAS)
- Nur Metadaten/Configs ins Repo übernehmen, nicht große Binärartefakte oder flüchtige Laufzeitoutputs