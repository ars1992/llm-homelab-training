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
├── datasets/                  # Lokale Datensätze (JSONL/Parquet/etc.)
│   ├── train.jsonl
│   ├── val.jsonl
│   └── test.jsonl
├── models/                    # Trainierte Adapter/Checkpoints
│   └── <run-id>/
└── logs/                      # TensorBoard und Trainingslogs
    └── <run-id>/
```

## Erwartete Pfade im Projekt

- Trainingsdaten (MVP): `data/datasets/train.jsonl`
- LoRA-Adapter Output: `data/models/<run-id>/`
- TensorBoard-Logs: `data/logs/<run-id>/`

## Hinweis zur Reproduzierbarkeit

Reproduzierbarkeit wird durch folgende Kombination erreicht:

1. Gepinnte Abhängigkeiten im Container (`docker/requirements.txt`)
2. Feste Konfigurationen in `configs/`
3. Deterministische Pfadkonventionen unter `data/`
4. Trennung von Code und Laufzeitergebnissen

## Backup / Cleanup (lokal)

Da `data/` schnell groß werden kann:

- Regelmäßig alte Runs unter `data/models/` und `data/logs/` bereinigen
- Wichtige Runs gezielt extern sichern (z. B. NAS)
- Nur Metadaten/Configs ins Repo übernehmen, nicht Binärartefakte