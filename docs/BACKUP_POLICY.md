# BACKUP_POLICY — llm-homelab-training

## 1. Zweck und Geltungsbereich

Diese Richtlinie definiert die verbindliche Backup- und Restore-Strategie für das Projekt `llm-homelab-training` mit Fokus auf:

- Reproduzierbarkeit von Training/Evaluation und Self-Edit-Abläufen
- Auditierbarkeit von Runs (Training, Eval, Promotion, Self-Edit)
- Trennung von Source-of-Truth und Laufzeitartefakten
- Speicherökonomie bei großen ML-Artefakten
- Schutz der für den SEAL-MVP kritischen Manifest-/Provenance-Artefakte

Geltungsbereich:

- Projektpfad: `opt/projects/llm-homelab-training`
- Projektinhalte: Code, Konfiguration, Dokumentation, Metadaten, ausgewählte Laufzeitartefakte
- explizit eingeschlossen: Self-Edit-Artefakte unter `data/self_edits/runs/<run_id>/` sowie der Exportpfad `data/training/derived/self_edits.accepted.jsonl`
- Nicht im Scope: beliebige Host-weite Vollbackups außerhalb der hier definierten Pfade

---

## 2. Leitprinzipien

1. **Source-of-Truth zuerst sichern**  
   Code, Konfiguration und Run-Metadaten haben Vorrang vor großen, rekonstruktionsfähigen Zwischenartefakten.

2. **Reproduzierbarkeit vor Vollständigkeit**  
   Es wird nicht jedes große Artefakt gesichert, sondern die für reproduzierbare Wiederherstellung erforderliche Teilmenge.

3. **Klassifizierung vor Frequenz**  
   Backup-Zyklen richten sich nach Artefaktklasse (kritisch/mittel/ersetzbar), nicht nach Verzeichnisnamen allein.

4. **Restore-Fähigkeit ist verpflichtend**  
   Backup gilt nur als wirksam, wenn Restore-Drills regelmäßig erfolgreich durchgeführt werden.

---

## 3. Verzeichnis- und Verantwortungsmodell

### 3.1 Source-of-Truth

- Primärer Projektort: `opt/projects/llm-homelab-training`
- Dieser Pfad ist die referenzierbare Basis für:
  - Code (`src/`, `scripts/`)
  - Konfiguration (`configs/`)
  - Dokumentation (`docs/`, `.ai/`)
  - Betriebsdefinition (`docker/`, `Makefile`, `.env.example`)

### 3.2 Runtime-Ort

- `opt/containers` ist ausschließlich Runtime-/Stack-Ort.
- Verbot: Kritische Projektdefinitionen dürfen **nicht nur** in `opt/containers` existieren.

### 3.3 Rollen

| Rolle | Verantwortung |
|---|---|
| Projekt-Owner | Freigabe der Policy, Priorisierung von Restore-Drills |
| Betreiber | Durchführung von Backups, Monitoring, Restore-Tests |
| Entwickler | Pflege reproduzierbarer Run-Metadaten, Einhaltung Pfadkonventionen |

---

## 4. Artefaktklassen

### Klasse 1 — Kritisch (hoch priorisiert)

Ziel: Verlust darf nicht akzeptiert werden.

Beispiele:
- Repository-Inhalt (Code, Konfiguration, Dokumentation)
- Run-Metadaten (Run-ID, Config-Snapshot, Dataset-Manifest, Metrik-Summary)
- Finale oder beste Adapter-Artefakte (`best`/`final`)
- Self-Edit-Manifeste und Verifikationsartefakte pro Run:
  - `data/self_edits/runs/<run_id>/manifest.json`
  - `data/self_edits/runs/<run_id>/verifications.jsonl`
- Stabiler Derived-Export:
  - `data/training/derived/self_edits.accepted.jsonl`

Backup-Frequenz:
- mindestens täglich
- zusätzlich nach relevanten Änderungen/abgeschlossenen wichtigen Runs

### Klasse 2 — Relevant (mittel priorisiert)

Ziel: Wiederherstellung wünschenswert, aber mit tolerierbarer Lücke.

Beispiele:
- TensorBoard-Logs, Evaluationsreports, sekundäre Auswertungen

Backup-Frequenz:
- mindestens wöchentlich
- optional täglich bei aktiver Analysephase

### Klasse 3 — Ersetzbar (niedrig priorisiert)

Ziel: Keine Standard-Sicherung, nur selektiv.

Beispiele:
- große Zwischencheckpoints
- temporäre Caches (`.cache`, HF-Cache, pip-Cache)
- reproduzierbare Zwischenprodukte

Backup-Frequenz:
- standardmäßig keine
- nur bei expliziter Entscheidung (z. B. Experimente mit hoher Rechenzeit)

---

## 5. Backup-Matrix (verbindlich)

| Bereich | Klasse | Sicherung | Frequenz | Aufbewahrung |
|---|---|---|---|---|
| `opt/projects/llm-homelab-training` (ohne Excludes) | 1 | Voll/inkrementell | täglich | langfristig |
| `data/` Run-Metadaten + finale Adapter | 1 | selektiv | täglich / nach Run | langfristig |
| `data/self_edits/runs/<run_id>/manifest.json` + `verifications.jsonl` | 1 | selektiv | nach jedem Self-Edit-Run | langfristig |
| `data/training/derived/self_edits.accepted.jsonl` | 1 | selektiv | nach jedem Self-Edit-Run | langfristig |
| `data/` Logs/Reports sekundär | 2 | selektiv | wöchentlich | mittel |
| Caches/temporäre Artefakte | 3 | standardmäßig ausgeschlossen | n/a | n/a |

---

## 6. Excludes (Ausschlüsse)

Folgende Pfade/Arten werden standardmäßig **nicht** gesichert, sofern keine explizite Ausnahme freigegeben wurde:

- `.cache/`
- HuggingFace-Cache-Verzeichnisse
- temporäre Build-/Paket-Caches
- große, vollständig rekonstruierbare Zwischencheckpoints
- temporäre Testartefakte ohne Audit-Relevanz

Hinweis: Ausschlüsse dürfen nicht dazu führen, dass Klasse-1-Metadaten verloren gehen.

---

## 7. Metadatenpflicht pro Trainingslauf

Für jeden relevanten Run sind mindestens folgende Informationen zu sichern:

- `run_id`
- Zeitstempel UTC
- verwendeter Commit-Stand
- effektive Konfiguration
- Basismodell-Referenz
- Dataset-Referenz inkl. Hash/Manifest (sofern verfügbar)
- zentrale Kennzahlen (`summary`)
- Pfad auf finalen/besten Adapter

Ohne diese Metadaten gilt ein Run als **nicht vollständig auditierbar**.

---

## 8. Aufbewahrungsrichtlinie

1. Klasse 1:
   - langfristig aufbewahren
   - nur kontrollierte Löschung nach Freigabe

2. Klasse 2:
   - zeitlich begrenzt aufbewahren (z. B. rollierend)
   - ältere Daten gemäß Kapazitätsplanung bereinigen

3. Klasse 3:
   - kurzlebig
   - automatische oder manuelle Bereinigung zulässig

---

## 9. Restore-Drills (verbindlich)

### Drill A — Code-only Rebuild (monatlich)

Ziel:
- Nachweis, dass das Projekt aus gesichertem Source-of-Truth lauffähig wiederhergestellt werden kann.

Erfolgskriterium:
- Build/Start der Containerumgebung erfolgreich
- Grundlegende Projektkommandos ausführbar

### Drill B — Audit-Restore eines einzelnen Runs (monatlich)

Ziel:
- Nachweis, dass ein konkreter Run anhand gesicherter Metadaten nachvollziehbar ist.

Erfolgskriterium:
- Metadaten vollständig lesbar
- zugehöriger finaler/bester Adapter referenzierbar und ladbar

### Drill C — Kritischer Partial-Restore (quartalsweise)

Ziel:
- Simulierter Verlust von `data/` und Wiederherstellung der Klasse-1-Artefakte.

Erfolgskriterium:
- zentrale Ergebnisse (Metadaten + finale Artefakte) wiederherstellbar
- Evaluationspfad erneut ausführbar

### Drill D — Dependency-Drift-Check (monatlich)

Ziel:
- Erkennen von Reproduzierbarkeitsdrift durch Abhängigkeitsänderungen.

Erfolgskriterium:
- dokumentierter Vergleich von altem Run-Kontext vs. aktuellem Build-Kontext
- Abweichungen mit Maßnahmenplan

### Drill E — Self-Edit Restore und Provenance-Kette (monatlich)

Ziel:
- Nachweis, dass ein Self-Edit-Run vollständig und auditierbar wiederhergestellt werden kann.

Pflichtartefakte:
- `data/self_edits/runs/<run_id>/manifest.json`
- `data/self_edits/runs/<run_id>/sources.snapshot.jsonl`
- `data/self_edits/runs/<run_id>/candidates.jsonl`
- `data/self_edits/runs/<run_id>/verifications.jsonl`
- `data/self_edits/runs/<run_id>/accepted.derived.jsonl`
- `data/training/derived/self_edits.accepted.jsonl` (stabiler Exportpfad)

Erfolgskriterium:
- alle Pflichtartefakte sind parsebar
- `accepted.derived.jsonl` enthält nachvollziehbare Provenance-Referenzen auf Candidate/Source/Verification
- Restore-Protokoll dokumentiert Run-ID, Zeitstempel, Verantwortlichen und Ergebnis

---

## 10. Validierung und Monitoring

Nach jedem Backup-Zyklus:

- Job-Status dokumentieren (Erfolg/Fehler)
- Größe und Dauer erfassen
- Anzahl gesicherter Klasse-1-Artefakte prüfen
- Abweichungen eskalieren

Nach jedem Restore-Drill:

- Protokoll mit Datum, Verantwortlichem, Ergebnis, Abweichungen
- Korrekturmaßnahmen mit Termin

---

## 11. Sicherheitsanforderungen

- Keine Secrets im Projekt-Repository.
- Zugriffsrechte auf Backup-Ziele nach Minimalprinzip.
- Transport/Storage-Verschlüsselung gemäß Betriebsstandard.
- Restore-Tests in kontrollierter Umgebung durchführen.

---

## 12. Änderungsmanagement

Änderungen an dieser Policy sind nur gültig, wenn:

1. Begründung dokumentiert ist
2. Auswirkungen auf Reproduzierbarkeit/Auditierbarkeit benannt sind
3. betroffene Doku (README, CONTEXT, Runbooks) aktualisiert wurde
4. mindestens ein entsprechender Restore-Drill nach Änderung erfolgreich war

---

## 13. Konsistenzprüfung (Policy-intern)

- Trennung von Source-of-Truth und Runtime ist definiert.
- Artefaktklassen sind eindeutig.
- Frequenz- und Ausschlusslogik ist festgelegt.
- Restore-Drills sind konkret benannt.
- Auditierbare Mindestmetadaten sind verpflichtend.

---

## 14. Annahmen und offene Punkte

### Annahmen

- Backup-Infrastruktur für tägliche und wöchentliche Jobs ist vorhanden.
- Speicherbudget für Klasse-1-Langzeitaufbewahrung ist eingeplant.
- Betreiberteam führt Restore-Drills regelmäßig durch.

### Offene Punkte

1. Konkrete numerische Retention-Werte pro Klasse final festlegen (Tage/Wochen/Monate).
2. Konkrete Exclude-Whitelist pro Host validieren.
3. Verantwortliche Person für monatliche Drift-Checks verbindlich benennen.
4. Eskalationsweg bei wiederholt fehlgeschlagenen Backups dokumentieren.