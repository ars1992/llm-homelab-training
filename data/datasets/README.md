# Dataset Card (Local Training Data)

## Zweck
Dieses Verzeichnis enthält lokale Trainings-, Evaluations- und Self-Edit-Daten für `llm-homelab-training`.

Es gibt aktuell zwei Datenfamilien:

1. Standard-LoRA-Daten im Schema:
   - `instruction`
   - `input`
   - `output`
2. Self-Edit-Daten im erweiterten Schema gemäß:
   - `src/datasets/schemas/self_edit.schema.json`

## Provenance (Herkunft)
- Quelle(n): **vom Projektbetreiber einzutragen**
- Erstellungsdatum: **YYYY-MM-DD**
- Erzeugt durch:
  - manuell kuratierte Beispiele und/oder
  - interne Skripte (z. B. `src/scripts/prepare_dataset.py`, `src/scripts/generate_self_edits.py`)
- Version/Stand: **vX.Y / run-id / commit**

## Nutzungskontext
- Einsatz ausschließlich für lokales LoRA/Fine-Tuning, Evaluation und Self-Edit-Experimente in dieser Umgebung.
- Keine automatische Weitergabe oder Veröffentlichung ohne separate Freigabe.

## Nutzungsbeschränkungen
1. **Keine Secrets** (API-Keys, Passwörter, Tokens) in Datensätzen speichern.
2. **Keine unzulässigen personenbezogenen Daten** ohne Rechtsgrundlage.
3. **Nur lizenzkonforme Inhalte** verwenden (Quellenrecht prüfen).
4. Daten nur für den definierten Projektzweck nutzen (Training/Eval/Self-Edit im Homelab).
5. Bei Unsicherheit zur Datenherkunft: Datensatz nicht verwenden.

## Qualitäts- und Formatregeln

### A) Standard-LoRA JSONL (`train.jsonl`)
- Eine Zeile = ein JSON-Objekt.
- Pflichtfelder:
  - `instruction` (nicht leer)
  - `output` (nicht leer)
- Optional:
  - `input` (String, darf leer sein)
- UTF-8, deterministische Reihenfolge empfohlen.

### A2) Regression-Val JSONL (`val.jsonl`)
- `val.jsonl` ist ein **Regression-Set** und folgt bewusst einem anderen Schema.
- Eine Zeile = ein JSON-Objekt mit:
  - `id` (z. B. `val-001`)
  - `instruction` (nicht leer)
  - `input` (String, leer erlaubt)
  - `expected_contains` (Liste mit 1–3 erwarteten Substrings)
  - `tags` (Liste, z. B. `["regression"]`)
- Beispielschema:
  - `{"id":"val-001","instruction":"...","input":"","expected_contains":["..."],"tags":["regression"]}`
- Zweck:
  - deterministische, substring-basierte Regressionsprüfung über `eval_val.py`
  - nicht als direktes LoRA-Trainingslabel-Set (`output`) gedacht.

### B) Self-Edit JSONL (`self_edit_train.jsonl`, `self_edit_val.jsonl`)
- Eine Zeile = ein JSON-Objekt im Self-Edit-Schema.
- Wichtige Pflichtfelder (Auszug):
  - `record_id`
  - `source_sample_id`
  - `created_at`
  - `instruction`
  - `input`
  - `original_output`
  - `edited_output`
  - `edit_rationale`
  - `status` (`draft|accepted|rejected`)
  - `audit` (inkl. `event_id`, `event_ts`, `actor_type`, `pipeline`, `base_model`)

## Aktuell vorhandene Starter-Dateien
- `train.jsonl` – Starter-Trainingsdaten (LoRA, `instruction/input/output`)
- `val.jsonl` – Regression-Validierungsdaten (`id/instruction/input/expected_contains/tags`)
- `self_edit_train.jsonl` – Starter-Self-Edit-Trainingsdaten
- `self_edit_val.jsonl` – Starter-Self-Edit-Validierungsdaten

## Usage Flow (empfohlen)

1. **LoRA-Baseline validieren**
   - Optional: `src/scripts/prepare_dataset.py` auf `train.jsonl`/`val.jsonl`
   - Training starten mit `configs/train_lora_3b_k80.yaml`

2. **Baseline evaluieren (zwei Pfade)**
   - Klassische Eval mit `src/scripts/eval.py` benötigt ein `output`-basiertes Eval-Set.
   - Regression-Eval mit `src/scripts/eval_val.py` nutzt `val.jsonl` (`expected_contains`-Schema).
   - Reports unter `data/evals/` prüfen.

3. **Self-Edit-Daten prüfen**
   - `self_edit_train.jsonl` und `self_edit_val.jsonl` gegen `self_edit.schema.json` validieren
   - `accepted`/`rejected` Verteilung und Edit-Qualität prüfen

4. **Self-Edit-Pipeline iterativ ausbauen**
   - `src/scripts/generate_self_edits.py` als Ausgangspunkt
   - später: Generate -> Critique -> Edit -> Verify -> Curate

## Audit-Hinweis
Für jeden Trainings- oder Self-Edit-Lauf dokumentieren:
- Datensatzdatei + Hash (z. B. SHA256)
- Quelle/Version
- Run-ID und verwendete Konfiguration
- Basismodell und ggf. Adapter-Referenz
- bei Self-Edit zusätzlich: Anteil `accepted` vs. `rejected`