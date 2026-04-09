# CHECKLIST-SERVE-PROMOTION-MVP

## Dokumentkontrolle
- Status: Verbindlich
- Version: 1.0
- Datum: 2026-04-09
- Geltungsbereich: `llm-homelab-training` MVP für Serving + Promotion
- Ziel: Erstinbetriebnahme und Verifikation des separaten Serving-Stacks mit `LATEST_OK`-Promotion

---

## 1) Zweck und Scope

Diese Checkliste beschreibt den minimalen, prüfbaren Inbetriebnahmeablauf für:

1. separaten Serving-Service `serve`
2. Pointer-basierte Adapter-Freigabe über `data/runs/LATEST_OK_ADAPTER_ID`
3. Promotion eines neu trainierten Adapters nur nach erfolgreicher Eval
4. stabile OpenClaw-Anbindung über einen OpenAI-kompatiblen Serving-Endpunkt

Nicht Teil dieser Checkliste:

- Cron-/Systemd-Automatisierung
- Performance-Tuning
- Parallelbetrieb von Training und Serving auf derselben GPU
- produktionsreife Multi-Model-/Multi-Tenant-Szenarien

---

## 2) Voraussetzungen / Constraints

Vor Start müssen folgende Bedingungen erfüllt sein:

- Projektpfad: `/opt/projects/llm-homelab-training`
- Host-Baseline unverändert:
  - NVIDIA Driver: `470.256.02`
  - CUDA Runtime laut `nvidia-smi`: `11.4`
- Docker Compose verfügbar
- Serving-Compose-Datei vorhanden:
  - `docker/compose.serve.yaml`
- Serving-App vorhanden:
  - `src/serve/app.py`
- Trainings-/Eval-Pipeline funktionsfähig:
  - `make real-run-short`
  - `make eval-val`
  - `make promote-latest-ok`
- Pointer-Dateien vorhanden oder anlegbar:
  - `data/runs/LATEST_REALRUN_ID`
  - `data/runs/LATEST_OK_ADAPTER_ID`
  - `data/runs/LATEST_OK_ADAPTER_PATH`

Betriebsregel:
- Serving darf für Nightly-Trainingsläufe gestoppt und neu gestartet werden.
- Parallelbetrieb von Training und Serving ist für den MVP nicht erforderlich.

---

## 3) Kritische Zielregeln (verbindlich)

1. Jeder Trainingslauf erzeugt eine neue `run_id`.
2. Kein Adapter-Ordner wird überschrieben.
3. `LATEST_REALRUN_ID` ist nicht gleichbedeutend mit produktiv freigegebenem Adapter.
4. Serving liest ausschließlich `LATEST_OK_ADAPTER_ID`.
5. Promotion erfolgt nur nach erfolgreicher Eval gegen definierte Schwellenwerte.
6. Bei Eval-Fail bleibt Serving auf dem bisherigen Stand.
7. Retention darf promotete Adapter nicht unbeabsichtigt löschen.

---

## 4) Erstprüfung der Projektstruktur

### 4.1 In Projekt wechseln
- [ ] `cd /opt/projects/llm-homelab-training`

### 4.2 Pflichtdateien prüfen
- [ ] `test -f docker/compose.serve.yaml`
- [ ] `test -f src/serve/app.py`
- [ ] `test -f Makefile`
- [ ] `test -d data/runs`

### 4.3 Erwartung
- [ ] Alle Prüfungen erfolgreich
- [ ] Keine fehlenden Pflichtdateien

**No-Go Bedingungen**
- [ ] `docker/compose.serve.yaml` fehlt
- [ ] `src/serve/app.py` fehlt
- [ ] `Makefile` enthält keine `serve-*` Targets
- [ ] `data/runs/` fehlt oder ist nicht schreibbar

---

## 5) Basis-Preflight vor Serving

### 5.1 Host-/Projekt-Preflight
- [ ] `make preflight`

### 5.2 Erwartung
- [ ] Docker/Compose verfügbar
- [ ] Host-GPU sichtbar
- [ ] Projektpfade vorhanden

### 5.3 Optionaler Statusblick auf Pointer
- [ ] `cat data/runs/LATEST_OK_ADAPTER_ID`
- [ ] `cat data/runs/LATEST_REALRUN_ID`

Hinweis:
- Eine leere `LATEST_OK_ADAPTER_ID` ist vor der ersten Promotion zulässig.
- In diesem Zustand kann der Serving-Service starten, muss aber im Health-Status einen Fehler oder „nicht bereit“ melden.

---

## 6) Serving-Stack starten

### 6.1 Serving hochfahren
- [ ] `make serve-up`

### 6.2 Logs prüfen
- [ ] `make serve-logs`

### 6.3 Erwartung
- [ ] Docker-Service `serve` startet
- [ ] Container beendet sich nicht sofort
- [ ] Kein offensichtlicher Import-/Model-Load-Fehler im Log

**Fehlerbilder**
| Fehlerfall | Detektion | Ursache (vermutet/bestätigt) | Reaktion | Operator-Info |
|---|---|---|---|---|
| Container startet nicht | `make serve-up` fehlschlägt | Compose-/Build-Fehler | Build-/Config-Fehler isolieren | Serving nicht betriebsbereit |
| Container startet, beendet sich aber | `make serve-logs` zeigt Exit | Import-/Runtime-Fehler | Logs analysieren, Abhängigkeiten prüfen | Serving nicht betriebsbereit |
| Container läuft, aber kein Modell geladen | Health zeigt Fehler | `LATEST_OK_ADAPTER_ID` leer/ungültig | Promotion oder Pointer korrigieren | Erwartbar vor erster Freigabe |

---

## 7) Healthcheck prüfen

### 7.1 Health aufrufen
- [ ] `make serve-health`

### 7.2 Erwartung bei freigegebenem Adapter
- [ ] HTTP-Antwort erfolgreich
- [ ] Antwort enthält:
  - `status=ok`
  - `service=serve`
  - `adapter_run_id`
  - `adapter_path`
  - `runtime_device`

### 7.3 Erwartung ohne freigegebenen Adapter
- [ ] Antwort zeigt klaren Fehlerzustand
- [ ] Fehler verweist auf fehlenden/ungültigen Pointer
- [ ] Verhalten ist deterministisch und nachvollziehbar

**No-Go Bedingungen**
- [ ] Health-Endpunkt nicht erreichbar
- [ ] Antwort ist leer oder unstrukturiert
- [ ] Geladener Adapter entspricht nicht `LATEST_OK_ADAPTER_ID`

---

## 8) OpenAI-kompatiblen Endpunkt prüfen

### 8.1 Minimalen Chat-Test senden
- [ ] Befehl ausführen:

```/dev/null/serve-chat-test.sh#L1-12
curl -sS http://127.0.0.1:8901/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "latest-ok",
    "messages": [
      {"role": "system", "content": "Antworte kurz und präzise."},
      {"role": "user", "content": "Sage exakt: OK"}
    ],
    "temperature": 0.0,
    "max_tokens": 16
  }'
```

### 8.2 Erwartung
- [ ] JSON-Antwort vorhanden
- [ ] Struktur enthält:
  - `id`
  - `object`
  - `created`
  - `model`
  - `choices`
  - `usage`
- [ ] `choices[0].message.content` ist nicht leer

**Fehlerbilder**
| Fehlerfall | Detektion | Ursache (vermutet/bestätigt) | Reaktion | Operator-Info |
|---|---|---|---|---|
| HTTP 503 | Endpoint antwortet mit „not ready“ | kein promoteter Adapter geladen | Promotion durchführen | erwartbar vor erster Promotion |
| HTTP 500 | Serving-Fehler bei Generate | Modell-/Tokenizer-/Adapter-Ladeproblem | Logs prüfen, Pointer prüfen | Inferenz nicht stabil |
| HTTP 200, aber leere Antwort | `content` leer | Prompt-/Generationseffekt | mit zweitem Test validieren | fachlich prüfen |

---

## 9) Promotion-Vorbereitung

### 9.1 Falls noch kein promoteter Adapter existiert
- [ ] `make real-run-short`

### 9.2 Eval ausführen
- [ ] `make eval-val`

### 9.3 Promotion ausführen
- [ ] `make promote-latest-ok`

### 9.4 Erwartung
- [ ] `data/runs/LATEST_REALRUN_ID` enthält die letzte technische Run-ID
- [ ] `data/runs/LATEST_OK_ADAPTER_ID` wurde nur bei Eval-Pass aktualisiert
- [ ] `data/runs/LATEST_OK_ADAPTER_PATH` zeigt auf `data/models/<run-id>`
- [ ] `data/runs/LATEST_PROMOTION_SUMMARY.json` existiert

---

## 10) Promotion-Verifikation

### 10.1 Pointer prüfen
- [ ] `cat data/runs/LATEST_OK_ADAPTER_ID`
- [ ] `cat data/runs/LATEST_OK_ADAPTER_PATH`

### 10.2 Promotionssummary prüfen
- [ ] `cat data/runs/LATEST_PROMOTION_SUMMARY.json`

### 10.3 Erwartung
- [ ] `decision` ist entweder `promoted` oder `kept_previous`
- [ ] dokumentierte Schwellenwerte sind nachvollziehbar
- [ ] beobachtete Metriken sind enthalten
- [ ] bei `promoted`: Pointer zeigt auf neuen Run
- [ ] bei `kept_previous`: Pointer bleibt unverändert

**Verbindliche Start-Schwellenwerte**
- [ ] `pass_rate_exact_openbook >= 0.60`
- [ ] `avg_coverage_runbook_openbook >= 0.30`

---

## 11) Serving nach Promotion aktualisieren

### 11.1 Reload oder Neustart
- [ ] `make serve-reload`
- [ ] falls Reload nicht stabil funktioniert: `make serve-down && make serve-up`

### 11.2 Health erneut prüfen
- [ ] `make serve-health`

### 11.3 Erwartung
- [ ] `adapter_run_id` im Health entspricht `LATEST_OK_ADAPTER_ID`
- [ ] `adapter_path` entspricht `data/models/<run-id>`
- [ ] Service bleibt erreichbar

---

## 12) End-to-End Kurztest

### 12.1 Nach Promotion erneut Chat-Test senden
- [ ] denselben oder einen zweiten kontrollierten Prompt senden

### 12.2 Erwartung
- [ ] Endpoint antwortet erfolgreich
- [ ] Antwort ist nicht leer
- [ ] Serving läuft gegen den freigegebenen Adapter
- [ ] Keine direkte Abhängigkeit vom Trainingscontainer

---

## 13) Retention-Prüfung

### 13.1 Retention ausführen
- [ ] `make retention-clean`

### 13.2 Erwartung
- [ ] `LATEST_REALRUN_ID` bleibt gültig oder wird deterministisch repariert
- [ ] `LATEST_OK_ADAPTER_ID` bleibt erhalten, sofern der Adapter existiert
- [ ] kein promoteter Adapter wird unbeabsichtigt gelöscht

### 13.3 Nachprüfung
- [ ] `cat data/runs/LATEST_OK_ADAPTER_ID`
- [ ] `make serve-health`

---

## 14) Nightly-Run Kurzprüfung

### 14.1 Zielablauf prüfen
- [ ] `make nightly-run`

### 14.2 Erwartung
- [ ] Reihenfolge entspricht dem dokumentierten Zielablauf
- [ ] Continue erfolgt nur von `LATEST_OK`
- [ ] ohne gültigen `LATEST_OK` erfolgt Fallback auf `make real-run-short`
- [ ] Promotion erfolgt nur nach Eval
- [ ] Serving wird nur bei neuer Promotion neu gestartet

Hinweis:
- Für produktive Sonntagsläufe ist diese Checkliste nur die Inbetriebnahme- und Verifikationsbasis, kein Ersatz für Laufzeit-Monitoring.

---

## 15) Abnahmeentscheidung

### Mindestkriterien für „MVP betriebsbereit“
- [ ] `make serve-up` funktioniert
- [ ] `make serve-health` ist erreichbar
- [ ] `POST /v1/chat/completions` funktioniert
- [ ] `LATEST_OK_ADAPTER_ID` wird nur bei Eval-Pass aktualisiert
- [ ] Serving bleibt bei Eval-Fail auf vorherigem Stand
- [ ] `retention-clean` schützt promotete Referenzen
- [ ] Nightly-Ablauf ist deterministisch nachvollziehbar

### Ergebnis
- [ ] Abnahme erteilt
- [ ] Abnahme nicht erteilt

---

## 16) Run-Protokoll (auszufüllen)

- Datum/Zeit (UTC): __________________
- Operator: __________________
- Host: __________________
- Commit-Stand: __________________
- Vorherige `LATEST_OK_ADAPTER_ID`: __________________
- Neuer Kandidat `LATEST_REALRUN_ID`: __________________
- Promotionsentscheidung: [ ] promoted  [ ] kept_previous
- Geladener Serving-Adapter nach Abschluss: __________________
- Health erfolgreich: [ ] Ja  [ ] Nein
- Chat-Completion erfolgreich: [ ] Ja  [ ] Nein
- Retention geprüft: [ ] Ja  [ ] Nein
- Auffälligkeiten: __________________
- Nächste Maßnahme: __________________

---

## 17) Offene Punkte / Annahmen

- Annahme: OpenClaw benötigt für den MVP nur eine kleine OpenAI-kompatible Teilmenge des Endpunkts `POST /v1/chat/completions`.
- Annahme: Serving und Training werden nicht gleichzeitig auf derselben K80 betrieben.
- Offene Frage: Ob `POST /reload` langfristig stabiler ist als ein vollständiger Container-Neustart, muss im Betrieb validiert werden.
- Offene Frage: Ob zusätzliche Health-Informationen (z. B. Modellname, Pointer-Hash, VRAM-Nutzung) benötigt werden, ist noch nicht abschließend entschieden.