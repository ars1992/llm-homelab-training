# ADR-0002: Trainings-/Evaluationsdaten im Repository mit kompaktem Regression-Set

- **Datum:** 2026-04-07
- **Status:** Accepted
- **Entscheider:** Projektmaintainer `llm-homelab-training`
- **Geltungsbereich:** Datenhaltung für Training/Evaluation im Projekt `llm-homelab-training`
- **Betroffene Artefakte:** `data/datasets/`, `data/evals/`, `configs/datasets/`, `.gitignore`, `src/scripts/eval_val.py`, `Makefile`

---

## 1. Kontext

Das Projekt verfolgt lokale, reproduzierbare LoRA/Fine-Tuning-Läufe auf NVIDIA K80 mit klarer Auditierbarkeit.  
Bisher war `data/` weitgehend als nicht versionierter Laufzeitbereich konzipiert. Für belastbare Regressionstests fehlte jedoch ein kleines, festes Testset im Repository.

Erforderlich war daher eine Entscheidung, wie Daten im Projekt strukturiert werden sollen, ohne:
1. das Repository mit großen Artefakten aufzublähen,
2. Reproduzierbarkeit zu verlieren,
3. sensible Inhalte ins Git zu bringen.

---

## 2. Entscheidung

### 2.1 Grundsatz

Trainings- und Evaluationsdaten werden **hybrid** behandelt:

1. **Kleine, relevante Referenzdaten** (Regression-Set) werden im Repository versioniert.
2. **Große Laufzeitartefakte** (Modelle, Logs, umfangreiche Datensätze) bleiben ignoriert.

### 2.2 Konkrete Umsetzung

- Versioniert im Repo:
  - `data/datasets/val.jsonl` (Regression-Set, 30 Items)
  - `data/datasets/.gitkeep`
  - `data/evals/.gitkeep`
  - `configs/datasets/val_regression.yaml`
- Eval-Mechanik:
  - `src/scripts/eval_val.py` prüft `expected_contains` je Item (Pass/Fail)
  - Report-Ausgabe unter `data/evals/<RUN_ID>/val_report.json`
- Workflow:
  - `make eval-val` als standardisierter Regressionstest

### 2.3 Fixes Datenschema für Regression

Jede Zeile in `data/datasets/val.jsonl` folgt:

```json
{"id":"val-001","instruction":"...","input":"","expected_contains":["..."],"tags":["regression"]}
```

---

## 3. Begründung

Die Entscheidung balanciert Reproduzierbarkeit und Repository-Hygiene:

- Ein kleines versioniertes Regression-Set ermöglicht stabile Vergleichbarkeit zwischen Commits.
- `expected_contains`-Checks sind deterministisch und CI-/Smoke-fähig.
- Große, volatile Dateien bleiben außerhalb der Versionskontrolle.
- Die Methode ist kompatibel mit der bestehenden K80-Stabilitätsstrategie (konservativer, auditierbarer Betrieb).

---

## 4. Konsequenzen

### Vorteile

1. **Nachvollziehbare Regressionen** über feste IDs (`val-001` … `val-030`).
2. **Schnelle technische Validierung** via `make eval-val`.
3. **Auditierbarkeit** durch versionierte Testdaten + Reports im standardisierten Pfad.
4. **Geringes Git-Risiko**, da nur kleine Datensets committed werden.

### Nachteile

1. `expected_contains` ist inhaltlich begrenzt und kein vollwertiges Qualitätsurteil.
2. Pflegeaufwand für das Regression-Set bei Scope-Änderungen.
3. Gefahr von Overfitting auf explizite Substrings, wenn Set nicht regelmäßig überarbeitet wird.

---

## 5. Abgrenzung (nicht Teil dieser ADR)

Nicht entschieden in dieser ADR:

- Vollständige Versionierung großer Trainingskorpora
- Speicherung großer Eval-Outputs im Git
- Externe Datenplattformen/Objektspeicher
- Fachliche Gold-Standards über Substring-Checks hinaus (z. B. Richtermodell)

---

## 6. Betriebsregeln (verbindlich)

1. `val.jsonl` bleibt klein und reviewbar.
2. Keine Secrets/privaten Daten in versionierten Datensätzen.
3. `expected_contains` enthält pro Item 1–3 kurze, prüfbare Substrings.
4. Vor Merge in `main` soll `make eval-val` ausführbar sein und Report erzeugen.
5. Große Trainingsdaten bleiben standardmäßig außerhalb des Repos oder explizit ignoriert.

---

## 7. Technische Referenzen

- Dataset: `data/datasets/val.jsonl`
- Dataset-Config: `configs/datasets/val_regression.yaml`
- Evaluator: `src/scripts/eval_val.py`
- Build/Run Target: `make eval-val`
- Ignore-Regeln: `.gitignore`
- Externe Doku-Referenzen (nur Verweis):
  - `ADR_Trainingsdaten_im_llm-homelab-training_repo_2026-04-06`
  - `Dokumentation_Projektplan_TrainingData_Blueprint_2026-04-06`
  - `Dokumentation_Dataset_Quality_Checklist_Eval_Gates_2026-04-06`

---

## 8. Risiken und Gegenmaßnahmen

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| Regression-Set zu klein/zu statisch | geringe Aussagekraft | regelmäßige Erweiterung/Rotation |
| Substring-Checks zu schwach | falsche Positivbefunde | zusätzliche Metriken/striktere Regeln schrittweise ergänzen |
| versehentliche Versionierung großer Daten | Repo-Blähung | `.gitignore` strikt halten, Review-Gate |
| unklare Ergebnisinterpretation | Fehlentscheidungen | Report immer mit Run-ID + Kontext interpretieren |

---

## 9. Erfolgskriterium

Die ADR gilt als erfolgreich umgesetzt, wenn:

1. `val.jsonl` (30 Regression-Items) versioniert ist,
2. `make eval-val` einen `val_report.json` erzeugt,
3. große Artefakte weiterhin nicht versioniert werden,
4. Änderungen am Regression-Set über normalen Reviewprozess nachvollziehbar sind.

---

## 10. Änderungsprozess

Änderungen an dieser ADR sind zulässig bei:

- Wechsel der Evaluationsmethodik,
- signifikanten Änderungen der Datenstrategie,
- Einführung zusätzlicher verpflichtender Quality Gates.

Jede Änderung muss die Auswirkungen auf Reproduzierbarkeit, Auditierbarkeit und Repository-Größe explizit dokumentieren.