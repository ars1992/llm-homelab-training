# Datasets

Dieses Verzeichnis definiert den Daten-Layer für Training, Evaluation und spätere Self-Edit-Erweiterungen.

Ziele:
- Einheitliches, reproduzierbares Datenformat
- Klare Trennung zwischen Rohdaten, aufbereiteten Daten und generierten Daten
- Kompatibilität mit dem MVP-Training (`src/scripts/train_lora.py`)
- Vorbereitung auf SEAL-inspirierte Self-Edit-Datensätze (`schemas/self_edit.schema.json`)

---

## Verzeichnislogik

Empfohlene lokale Struktur (unter `data/`, nicht im Repo versioniert):

- `data/datasets/raw/`  
  Ursprungsdaten (Exports, Notizen, Logs, etc.)
- `data/datasets/processed/`  
  Aufbereitete, bereinigte Trainingsdaten
- `data/datasets/train.jsonl`  
  Standard-Eingabe für MVP-LoRA-Training
- `data/datasets/val.jsonl`  
  Optional für Evaluierung/Monitoring
- `data/datasets/test.jsonl`  
  Optional für finale Vergleichsläufe

Schema-Definitionen bleiben im Repo unter:
- `src/datasets/schemas/`

---

## MVP-Trainingsformat (JSONL)

`train_lora.py` erwartet **JSONL** mit genau einem JSON-Objekt pro Zeile:

```json
{"instruction":"...", "input":"...", "output":"..."}
```

Pflichtfelder:
- `instruction` (string, nicht leer)
- `output` (string, nicht leer)

Optional:
- `input` (string, darf leer sein `""`)

Konventionen:
- UTF-8 Encoding
- Eine Zeile = ein Sample
- Keine mehrzeiligen JSON-Objekte über mehrere Zeilen
- Deterministische Reihenfolge bei wiederholbarer Datenerzeugung (z. B. sortiert nach Quelle + ID)

---

## Prompt-Template-Konvention (für Training)

Beim Tokenisieren wird pro Sample ein konsistentes Prompt-Format aufgebaut, z. B.:

1. `instruction`
2. optional `input` (nur falls nicht leer)
3. Zieltext `output`

Beispiel (konzeptionell):
- Mit Input: `Instruction + Input -> Output`
- Ohne Input: `Instruction -> Output`

Wichtig:
- `output` ist die gewünschte Modellantwort
- Beim Causal-LM-Training wird üblicherweise der gesamte Text als Sequenz trainiert; Details sind in `train_lora.py` dokumentiert

---

## Qualitätsregeln für Samples

Mindestanforderungen:
1. **Eindeutigkeit**: Kein widersprüchliches Ziel pro identischer Aufgabe
2. **Konsistenz**: Gleiches Sprachregister und gleiches Antwortformat innerhalb eines Datensatzes
3. **Kürze/Präzision**: Keine unnötigen Fülltexte in `output`
4. **Datenschutz**: Keine Secrets, Tokens, personenbezogenen Daten ohne Rechtsgrundlage
5. **Lizenzkonformität**: Nur Datenquellen verwenden, deren Nutzung für Training erlaubt ist

Empfehlungen:
- Duplikate entfernen
- Extrem lange Samples markieren oder trennen
- Problematische/rauschhafte Samples in Quarantäne-Datei auslagern

---

## Validierung vor Training

Vor jedem Lauf prüfen:
- Datei existiert und ist lesbar
- Jede Zeile ist valides JSON
- Pflichtfelder vorhanden und vom Typ `string`
- Leere Pflichtfelder (`""`) ausgeschlossen
- Datensatzgröße ausreichend für den geplanten Lauf
- Optional: Länge pro Sample (Zeichen/Tokens) im Zielbereich für K80-konforme Trainingssettings

---

## Versionierung und Reproduzierbarkeit

- Datendateien unter `data/` werden standardmäßig **nicht committed**
- Reproduzierbarkeit erfolgt über:
  - Skripte in `src/scripts/`
  - Konfigurationen in `configs/`
  - Schemas in `src/datasets/schemas/`
- Für nachvollziehbare Runs empfohlen:
  - Dataset-Hash (z. B. SHA256) pro Trainingslauf loggen
  - Quelle/Generierungsdatum dokumentieren
  - Run-ID in Logs und Modellpfaden konsistent verwenden

---

## Bezug zu Self-Edit-Pipeline (später)

Für die nächste Ausbaustufe werden zusätzlich Datensätze benötigt, die:
- Modellantworten,
- erkannte Fehler,
- vorgeschlagene Selbstkorrekturen,
- und Akzeptanzkriterien

strukturiert enthalten.  
Dafür ist `src/datasets/schemas/self_edit.schema.json` vorgesehen.