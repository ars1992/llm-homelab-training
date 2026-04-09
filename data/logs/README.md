# data/logs/

Dieses Verzeichnis enthält lokale Laufzeit-Logs für Training, Evaluation und zugehörige Betriebsprozesse.

## Zweck

Die Inhalte unter `data/logs/` dienen dazu:

1. Trainingsläufe nachzuvollziehen
2. Fehlerbilder und Laufverhalten zu analysieren
3. Metriken und Ereignisse für Debugging und Audit zu prüfen
4. TensorBoard-kompatible Logdaten lokal bereitzuhalten

## Erwarteter Inhalt

Typischerweise wird pro Lauf ein eigener Unterordner angelegt:

- `data/logs/<run-id>/`

Beispiele für `run_id`:

- `real-20260409T010000Z`
- `smoke-20260406T092145Z`

In diesen Unterordnern können je nach Workflow unter anderem liegen:

- TensorBoard-Event-Dateien
- Trainingsmetriken
- Laufzeitdiagnostik
- weitere technische Log-Artefakte des jeweiligen Runs

## Betriebsregeln

- Keine manuellen Änderungen an aktiven Log-Dateien während eines laufenden Trainings
- Logs sind Laufzeit-Artefakte und in der Regel nicht versioniert
- Logs dürfen keine Secrets, Tokens oder Zugangsdaten enthalten
- Alte Logs dürfen im Rahmen von Retention oder Runtime-Reset bereinigt werden
- Für Audit und Fehleranalyse ist die Zuordnung über `run_id` verbindlich

## Abgrenzung

Dieses Verzeichnis ist nicht für folgende Inhalte vorgesehen:

- trainierte Adapter oder Checkpoints  
  → `data/models/`
- Evaluationsberichte und Vorhersagen  
  → `data/evals/`
- Pointer-Dateien und Run-Zustände  
  → `data/runs/`
- versionierte Referenzdatensätze  
  → `data/datasets/`

## Aufbewahrung / Cleanup

Da Log-Dateien mit der Zeit wachsen können, gilt:

- Nicht mehr benötigte alte Logs regelmäßig bereinigen
- Wichtige Logs bei Bedarf extern sichern
- Für vollständige Test-Neustarts kann ein Runtime-Reset durchgeführt werden
- Retention und Reset sind unterschiedliche Prozesse:
  - Retention: selektives Aufräumen bei Erhalt relevanter Runs
  - Reset: vollständige Rücksetzung des lokalen Laufzeitzustands

## Erwarteter Zustand nach frischem Reset

Nach einem vollständigen Runtime-Reset kann dieses Verzeichnis leer sein.
Das ist ein gültiger und erwarteter Zustand.

Neue Unterordner entstehen erst wieder durch einen neuen Trainings- oder Evaluationslauf.