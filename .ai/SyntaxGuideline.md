# SyntaxGuideline.md

## Zweck

Diese Richtlinie definiert verbindliche Markdown- und Dokumentationskonventionen für das Repository `llm-homelab-training`.

Ziele:

1. Konsistente, auditierbare Dokumentation
2. Hohe Lesbarkeit für Betrieb, Architektur und Incident-Analyse
3. Eindeutige Trennung von Fakten, Annahmen und offenen Punkten
4. Reproduzierbare Anleitungen ohne Interpretationsspielraum

---

## Geltungsbereich

Diese Konventionen gelten für alle Markdown-Dateien in:

- `README.md`
- `docs/*.md`
- `.ai/*.md`
- `src/datasets/README.md`
- weitere projektrelevante `.md`-Dateien

---

## Grundprinzipien

1. **Deterministisch schreiben**  
   Formuliere Schritte so, dass zwei Personen bei identischem Input zum gleichen Ergebnis kommen.

2. **Fakten von Annahmen trennen**  
   Unklare Punkte nie implizit als Tatsache formulieren.

3. **Auditierbarkeit vor Stilpräferenz**  
   Inhalte müssen prüfbar und referenzierbar sein.

4. **Kontext zuerst, Details danach**  
   Leser muss schnell verstehen: Was? Warum? Wie? Risiko?

5. **Keine Marketing-Sprache**  
   Keine Floskeln, keine Buzzwords ohne Definition.

---

## Sprach- und Stilregeln

- Primärsprache: **Deutsch** (technische Begriffe dürfen Englisch bleiben)
- Aktiv, präzise, ohne Füllwörter
- Kurze, eindeutige Sätze
- Keine Emojis
- Keine Ironie oder informelle Abkürzungen
- Keine unbelegten Superlative (z. B. „best“, „state-of-the-art“) ohne Kriterien

### Verbotene Muster (Beispiele)

- „einfach“, „offensichtlich“, „magisch“, „irgendwie“
- „sollte schon passen“
- unpräzise Zeitangaben wie „bald“, „später“ ohne Milestone

---

## Markdown-Formatregeln

## 1) Überschriftenstruktur

- Genau eine H1 (`#`) pro Datei
- Hierarchie ohne Sprünge (`#` -> `##` -> `###`)
- Überschriften klar, fachlich und substantivisch

Beispiel:

- `# TROUBLESHOOTING_K80`
- `## Typische Fehlerbilder`
- `### CUDA OOM beim Forward Pass`

## 2) Listen

- Für Sequenzen mit Reihenfolge: nummerierte Liste (`1.`)
- Für Aufzählungen ohne Reihenfolge: Bullet-Liste (`-`)
- Pro Listeneintrag ein fachlicher Gedanke
- Keine verschachtelten Listen tiefer als 2 Ebenen, wenn vermeidbar

## 3) Tabellen

Verwende Tabellen für:

- API-Übersichten
- Fehlerkataloge
- Entscheidungen/Tradeoffs
- Metrikdefinitionen

Mindestanforderung je Tabelle:

- Eindeutige Spaltennamen
- Keine leeren Pflichtspalten
- Einheitliche Werteformate innerhalb einer Spalte

## 4) Codeblöcke

- Nur verwenden, wenn exakte Syntax relevant ist (CLI, YAML, JSON, Python)
- Vor jedem Codeblock 1 Satz Kontext: Zweck + erwartetes Ergebnis
- Keine „Pseudo-Kommandos“ ohne Hinweis
- Platzhalter klar markieren (`<MODEL_NAME>`, `<RUN_ID>`)

## 5) Inline-Code

Folgende Elemente immer als Inline-Code markieren:

- Dateipfade und Verzeichnisse (`docker/compose.yaml`)
- Befehle (`docker compose up -d`)
- Variablen und Schlüssel (`CUDA_VISIBLE_DEVICES`, `max_seq_length`)
- IDs und Eventtypen (`run_id`, `evaluation_run_completed`)

---

## Dokumentstruktur (empfohlen)

Jede technische Dokumentdatei sollte – sofern passend – diese Reihenfolge nutzen:

1. Zweck und Scope
2. Voraussetzungen / Constraints
3. Hauptinhalt (Prozess, Architektur, Regeln)
4. Fehlerfälle / Sonderfälle
5. Verifikation / Prüfverfahren
6. Offene Punkte / Annahmen
7. Änderungswirkung (optional)

---

## Konventionen für Befehle und Ausführungsschritte

1. Jeder Schritt enthält:
   - Aktion
   - Befehl
   - erwartetes Ergebnis

2. Bei destruktiven Aktionen:
   - explizite Warnung
   - Rückfallstrategie

3. Bei GPU-/Treiber-Themen:
   - immer Host-vs-Container-Kontext angeben

Beispielschema:

- Schritt: „Container starten“
- Befehl: `docker compose -f docker/compose.yaml up -d --build`
- Erwartung: Service `trainer` läuft und ist per `exec` erreichbar

---

## Konfigurationen dokumentieren (YAML/ENV)

Wenn Konfigurationswerte beschrieben werden, immer mit:

- Schlüsselname
- Datentyp
- Default
- Gültiger Wertebereich
- Auswirkung auf Laufzeit/Qualität

Beispiel-Template:

- `max_seq_length`  
  - Typ: Integer  
  - Default: `512`  
  - Bereich: `128..2048` (hardwareabhängig)  
  - Wirkung: Höherer Wert erhöht Kontext, aber auch VRAM-Verbrauch.

---

## Fehler- und Sonderfall-Dokumentation

Für reproduzierbare Incident-Bearbeitung Fehlerfälle tabellarisch erfassen:

- Fehlerfall
- Detektion
- Ursache (vermutet/bestätigt)
- Reaktion
- Nutzer-/Operator-Info
- Follow-up

Hinweis: Ursache als „vermutet“ kennzeichnen, solange nicht verifiziert.

---

## Architektur- und Entscheidungsdokumente (ADR)

Für ADR-Dateien in `.ai/` gilt:

- Dateiname: `ADR-<laufende-nummer>-<kurztitel>.md`
- Statusfeld verpflichtend: `proposed | accepted | deprecated | superseded`
- Muss enthalten:
  1. Kontext
  2. Entscheidung
  3. Alternativen
  4. Tradeoffs
  5. Konsequenzen
  6. Review-/Revisionshinweis

---

## Referenzen und Nachvollziehbarkeit

- Interne Referenzen immer als relativer Pfad (`docs/TROUBLESHOOTING_K80.md`)
- Externe Referenzen mit kurzer Begründung, warum relevant
- Keine toten oder unkommentierten Links
- Versionsabhängige Aussagen mit Version versehen

---

## Anforderungen an „How to run“-Abschnitte

Jeder ausführbare Workflow muss mindestens enthalten:

1. Voraussetzungen (Docker, GPU, Treiber, Datenpfad)
2. Setup (`.env`, Build)
3. Startbefehl
4. Verifikationsbefehl (funktioniert es?)
5. Wo liegen Outputs/Logs?
6. Wie stoppen/aufräumen?

---

## Annahmen und offene Fragen kennzeichnen

Verwende explizite Marker:

- `Annahme:` für nicht verifizierte, aber notwendige Arbeitsannahmen
- `Offene Frage:` für fehlende fachliche/technische Informationen
- `Unsicherheit:` für Bereiche mit erhöhter Risikowirkung

Diese Marker sind verpflichtend in Architektur- und Planungsdokumenten.

---

## Dateinamen-Konventionen für Markdown

- Nur ASCII, keine Leerzeichen
- Kebab-Case oder etablierte Großschreibung für Standards
- Beispiele:
  - `ROADMAP.md`
  - `SEAL_NOTES.md`
  - `TROUBLESHOOTING_K80.md`
  - `ADR-0001-Container-TrainingStack.md`

---

## Qualitäts-Checkliste vor Commit

Vor jedem Commit einer Markdown-Datei prüfen:

- [ ] Eine klare H1 vorhanden
- [ ] Struktur logisch und vollständig
- [ ] Schritte reproduzierbar
- [ ] Pfade/Befehle korrekt formatiert
- [ ] Annahmen/Unsicherheiten explizit markiert
- [ ] Keine Secrets/Token enthalten
- [ ] Keine widersprüchlichen Aussagen zu Configs oder Pfaden
- [ ] Verweise auf bestehende Dateien korrekt

---

## Minimalbeispiel für konsistente Abschnittsform

### Zweck
Kurze fachliche Zieldefinition.

### Voraussetzungen
Konkrete technische Bedingungen.

### Ablauf
Nummerierte Schritte mit Befehlen und erwarteten Ergebnissen.

### Fehlerfälle
Tabelle mit Detektion und Reaktion.

### Verifikation
Wie überprüft wird, dass der Ablauf korrekt war.

### Offene Fragen
Noch fehlende Entscheidungen/Informationen.

---

## Änderungsmanagement für Dokumente

Bei relevanten Änderungen immer mit aktualisieren:

- `README.md` bei Bedienungs- oder Setup-Änderungen
- `docs/TROUBLESHOOTING_K80.md` bei neuem Fehlerbild/Workaround
- `.ai/ADR-*.md` bei Architekturentscheidungen
- `.ai/CONTEXT.md` bei strukturellen Projektänderungen

Wenn eine Entscheidung alte Dokumentation überholt, dies explizit markieren (z. B. „ersetzt durch …“).

---

## Schlussregel

Dokumentation ist Teil des Systems.  
Eine Änderung gilt erst dann als abgeschlossen, wenn Code, Konfiguration und Dokumentation konsistent sind.