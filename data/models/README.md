# data/models/

Dieses Verzeichnis enthält die lokal erzeugten **Modellartefakte** des Projekts `llm-homelab-training`.

## Zweck

Unter `data/models/` werden die Ergebnisse einzelner Trainingsläufe abgelegt.  
Jeder erfolgreiche Lauf schreibt in ein eigenes Unterverzeichnis mit eindeutiger `run_id`.

Beispiel:

- `data/models/real-20260409T010000Z/`
- `data/models/smoke-20260406T092145Z/`

## Inhalt

Ein Run-Unterverzeichnis kann je nach Laufart und Trainingsfortschritt unter anderem enthalten:

- `adapter_config.json`  
  Konfiguration des erzeugten LoRA-Adapters

- `adapter_model.bin` oder ähnliche Modellgewichte  
  Tatsächliche Adapter-Artefakte des Trainingslaufs

- `final_metrics.json`  
  Abschließende Trainingsmetriken des Laufs

- `run_metadata.json`  
  Laufkontext wie `run_id`, Zeitstempel und verwendete Konfiguration

- `checkpoint-*/`  
  Zwischenstände eines Trainingslaufs zur Wiederaufnahme oder Analyse

- Tokenizer-Dateien, z. B.:
  - `tokenizer.json`
  - `tokenizer_config.json`
  - `special_tokens_map.json`
  - `merges.txt`
  - `vocab.json`

## Verzeichnislogik

Die Struktur ist bewusst laufbasiert:

- ein Lauf = ein eigenes Verzeichnis
- keine Überschreibung bestehender Run-Verzeichnisse
- technische Laufhistorie getrennt von produktiver Freigabe

Wichtige Pointer-Dateien liegen nicht hier, sondern unter `data/runs/`, z. B.:

- `data/runs/LATEST_REALRUN_ID`
- `data/runs/LATEST_OK_ADAPTER_ID`

## Betriebsregeln

- Keine bestehenden Run-Verzeichnisse manuell überschreiben.
- Nur vollständig erzeugte Adapter mit `adapter_config.json` gelten als technisch verwertbar.
- Serving darf nur auf Adapter zeigen, die über `LATEST_OK_ADAPTER_ID` freigegeben wurden.
- Alte Modellartefakte dürfen im Rahmen von Retention oder Reset entfernt werden, wenn keine geschützten Pointer mehr darauf verweisen.

## Für was dieses Verzeichnis nicht gedacht ist

Nicht in `data/models/` ablegen:

- allgemeine Logs
- Eval-Berichte
- Run-Pointer
- Secrets oder Zugangsdaten
- manuelle Notizen

Dafür sind andere Verzeichnisse vorgesehen:

- `data/logs/`
- `data/evals/`
- `data/runs/`

## Hinweise zu Berechtigungen

Da Artefakte häufig aus Containern heraus geschrieben werden, können Ownership- oder Rechteprobleme auftreten.  
Wenn lokale Bereinigung oder Retention fehlschlägt, zuerst die Besitzverhältnisse unter `data/` prüfen.

Beispiel:

- Host-Benutzer muss Dateien unter `data/models/` löschen dürfen
- für Neustarts oder vollständige Resets kann eine rekursive Ownership-Korrektur erforderlich sein

## Aufbewahrung / Cleanup

Dieses Verzeichnis kann schnell groß werden. Daher gilt:

- wichtige Läufe gezielt sichern
- nicht mehr benötigte Läufe kontrolliert bereinigen
- für vollständige Rücksetzung bevorzugt den projektseitigen Reset-/Cleanup-Workflow verwenden statt manuell einzelne Dateien zu löschen

## Kurzfassung

`data/models/` ist der lokale Ablageort für alle trainierten Adapter und Checkpoints.  
Die Inhalte sind laufzeitbezogene Artefakte, keine stabile Repository-Konfiguration.