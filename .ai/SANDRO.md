# SANDRO.md — Projektübergreifendes Arbeitsgedächtnis

## Zweck
Dieses Dokument speichert projektübergreifende Arbeitsprinzipien, Entscheidungen und Zusammenarbeitserfahrungen.
Ziel ist, über mehrere Sessions konsistent, schneller und auditierbar zu arbeiten.

---

## Nutzerprofil (persistente Präferenzen)

- Rolle/Erwartung: IT-Projektplaner- und Architektursicht statt reiner Feature-Implementierung.
- Fokus: Enterprise-Software, Datenmanagement, Compliance, Security, Auditierbarkeit.
- Denkweise: Systemisch, formal, nachvollziehbar, dokumentationsorientiert.
- Prioritäten:
  1. Reproduzierbarkeit
  2. Lokaler Betrieb ohne Cloud-Zwang
  3. Saubere Strukturierung (Domänentrennung, IDs, Fehlerzustände, Audit-Trail)
- Kommunikationsstil:
  - präzise, ohne Marketing-Sprache
  - keine Floskeln, keine Emojis
  - Annahmen und Unsicherheiten explizit benennen

---

## Verbindliche Arbeitsweise (für zukünftige Sessions)

1. Immer mit kurzer, präziser Checkliste starten (3–7 Punkte).
2. Danach klare, nummerierte Schritte in logischer Reihenfolge.
3. Fehlende Informationen explizit als Annahme/Offene Frage markieren.
4. Jede Entität mit eindeutiger ID denken.
5. Jede Aktion auditierbar modellieren.
6. Fehler- und Sonderfälle deterministisch definieren.
7. Fachliche Domänen strikt trennen.

---

## Bisher bestätigte Qualitätskriterien

- „Commit-ready“ bedeutet:
  - Struktur vorhanden
  - Konfigurationen nachvollziehbar
  - Dokumentation konsistent
  - keine Secrets
- Doku ist Teil des Systems (nicht optional).
- Reproduzierbarkeit ist wichtiger als „fancy features“.

---

## Projektkontext-Memory

### Projekt: `llm-homelab-training`
- Ziel: reproduzierbare Container-Trainingsumgebung (LoRA/Fine-Tuning, 3B-Klasse) auf NVIDIA K80.
- Späterer Ausbau: SEAL-inspirierte Self-Edit-Pipeline.
- Betriebsmodus: lokal, ohne Cloud-Abhängigkeit.
- Wichtige Leitlinie: K80-Limits früh berücksichtigen (VRAM, Throughput, Precision-Kompatibilität).

---

## Was gut funktioniert hat

- Frühe Strukturierung in:
  - `docker/`, `src/`, `configs/`, `docs/`, `.ai/`
- Frühes Festlegen von:
  - Datenformat
  - Artefaktpfaden
  - Troubleshooting-Konzept
- Architekturentscheidungen in ADR-Form dokumentieren.

---

## Verbesserungsbedarf / Watchouts

- Bei YAML-Configs auf konsistente Key-Strukturen achten (flat vs. nested).
- Kompatibilitätsannahmen (CUDA/PyTorch/Driver) immer verifizieren, nicht implizit voraussetzen.
- Bei MVP-Skripten früh Validierung + klare Fehlermeldungen einbauen.
- Keine impliziten Betriebsannahmen (z. B. GPU-Sichtbarkeit im Container) ohne Check-Kommandos.

---

## Standard-Check vor Abschluss einer Aufgabe

- [ ] Zielbild und Scope klar definiert
- [ ] Dateistruktur vollständig
- [ ] Konfigurationen und Skripte konsistent
- [ ] Fehlerfälle dokumentiert
- [ ] Audit-/Nachvollziehbarkeit berücksichtigt
- [ ] Offene Fragen explizit gelistet
- [ ] Keine Secrets oder lokale Artefakte im Repo

---

## Offene-Fragen-Template (für neue Projekte)

1. Fachliche Zielprozesse und Grenzen?
2. Welche Entitäten + IDs sind verpflichtend?
3. Welche Events müssen auditierbar sein?
4. Welche Fehlerzustände sind fachlich kritisch?
5. Welche Reproduzierbarkeitsanforderungen sind „must-have“?
6. Welche regulatorischen/Compliance-Rahmen gelten?

---

## Änderungslog

- 2026-04-05:
  - Erstfassung als projektübergreifendes Gedächtnis angelegt.
  - Nutzerpräferenzen, Arbeitsprinzipien und Qualitätskriterien dokumentiert.
  - Kontext zu `llm-homelab-training` aufgenommen.
  - Eliot-Review zur Backup-Strategie ausgewertet und als Entscheidungsnotiz übernommen:
    - Bewertung Verzeichnisstrategie: „teilweise“, mit Ergänzungen „passt“.
    - Code-Source-of-truth unter `opt/projects/llm-homelab-training` bestätigt.
    - `opt/containers` nur als Runtime-Ort, nicht als alleinige Quelle für Compose/Env/Secrets.
    - Auditierbare Run-Metadaten als kleine, gesondert sicherbare Klasse priorisiert.
    - Artefakte in Klassen aufgeteilt:
      - Klasse 1: kritische, kleinere Outputs (finale/beste Adapter, Summarys) täglich sichern.
      - Klasse 2: nützliche, mittelgroße Logs regelmäßig sichern.
      - Klasse 3: große, ersetzbare Checkpoints/Caches standardmäßig nicht voll sichern.
    - Restore-Drills als Pflichtprozess aufgenommen:
      - Code-only-Rebuild
      - Audit-Restore eines konkreten Run-ID
      - Full-critical-Restore
      - monatlicher Dependency-Drift-Check