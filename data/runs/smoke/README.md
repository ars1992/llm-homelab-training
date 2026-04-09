# README — `data/runs/smoke/`

## Zweck

Dieses Verzeichnis enthält den **Laufzustand und die kompakten Metadaten** für Smoke-Tests im Projekt `llm-homelab-training`.

Smoke-Runs dienen der schnellen, deterministischen End-to-End-Prüfung der Pipeline, bevor längere oder produktive Trainingsläufe gestartet werden.

Typischer Zweck eines Smoke-Runs:

1. Grundfunktion der Container-Umgebung prüfen
2. GPU-Sichtbarkeit im Container verifizieren
3. Trainingspfad mit kleinem Testdatensatz prüfen
4. Inferenz-/Eval-Pfad technisch verifizieren
5. Artefaktpfade und Run-Disziplin prüfen

---

## Inhalt

Typische Dateien in diesem Verzeichnis:

- `LATEST_RUN_ID`  
  Enthält die zuletzt verwendete Smoke-Run-ID.

- `report.txt`  
  Kompakter Bericht über den letzten Smoke-Lauf, z. B.:
  - Zeitstempel
  - verwendete Run-ID
  - Basis-Modell
  - Dataset-Pfad
  - Modell- und Eval-Artefaktpfade

---

## Abgrenzung

Dieses Verzeichnis enthält **keine eigentlichen Modellartefakte** und **keine vollständigen Logs**.

Diese liegen an anderen Stellen:

- Smoke-Modelle: `data/models/smoke-<run-id>/`
- Smoke-Eval-Artefakte: `data/evals/smoke-<run-id>/`
- Allgemeine Logs: `data/logs/<run-id>/`

`data/runs/smoke/` ist nur der **Zustands- und Referenzbereich** für Smoke-Läufe.

---

## Betriebsregeln

- Inhalte dürfen lokal gelöscht und neu erzeugt werden.
- Smoke-Runs sind technische Prüfungen, keine fachliche Freigabe.
- Ein erfolgreicher Smoke-Run ersetzt keine echte Regression-Eval auf Real-Runs.
- Die hier abgelegten Informationen müssen klein, lesbar und schnell prüfbar bleiben.

---

## Erwarteter Zielzustand

Nach einem erfolgreichen Smoke-Run sollte dieses Verzeichnis mindestens enthalten:

- `LATEST_RUN_ID`
- `report.txt`

Wenn diese Dateien fehlen, ist der Smoke-Lauf unvollständig oder fehlgeschlagen.

---

## Hinweise für Betrieb und Cleanup

- Dieses Verzeichnis darf im Rahmen von Reset-/Cleanup-Prozessen zurückgesetzt werden.
- Vor einem neuen vollständigen End-to-End-Test kann der Smoke-Zustand bewusst gelöscht werden.
- Für Audit und Fehlersuche ist `report.txt` vor dem Löschen kurz zu prüfen.

---

## Zusammenfassung

`data/runs/smoke/` ist das Zustandsverzeichnis für technische Kurzläufe.

Es dokumentiert:

- welche Smoke-Run-ID zuletzt verwendet wurde
- ob der letzte technische Kurztest Artefakte erzeugt hat
- welche Pfade für Modell- und Eval-Ausgaben relevant waren