# GitGuideline.md

## Zweck

Diese Richtlinie definiert einen reproduzierbaren, auditierbaren Git-Workflow für `llm-homelab-training`.

Ziele:

1. Nachvollziehbare Historie (wer, was, warum, wann).
2. Kleine, prüfbare Commits statt großer Sammeländerungen.
3. Keine geheimen oder lokalen Artefakte im Repository.
4. Deterministische Build-/Trainingsgrundlage.

---

## Geltungsbereich

Diese Regeln gelten für alle Änderungen in:

- Infrastruktur (`docker/`, `configs/`)
- Quellcode (`src/`)
- Dokumentation (`docs/`, `.ai/`)
- Projekt-Metadaten (`README.md`, `.gitignore`, `.env.example`, etc.)

---

## Branch-Strategie

## Hauptbranch

- `main` ist immer lauffähig und in sich konsistent.
- Direktes Pushen auf `main` nur für kleine, risikoarme Änderungen (Doku, triviale Fixes) oder wenn kein Review-Prozess verfügbar ist.
- Für Feature-/Umbauarbeiten bevorzugt Feature-Branches.

## Branch-Namensschema

Format:

`<type>/<kurzbeschreibung-kebab-case>`

Typen:

- `feat/` – neue Funktion
- `fix/` – Fehlerbehebung
- `refactor/` – Umbau ohne Verhaltensänderung
- `docs/` – Dokumentation
- `chore/` – Infrastruktur/Wartung
- `test/` – Tests

Beispiele:

- `feat/lora-train-mvp`
- `fix/k80-oom-defaults`
- `docs/troubleshooting-k80`

---

## Commit-Hygiene

## Grundregeln

1. **Ein Commit = ein fachlich zusammenhängender Change.**
2. Commits müssen **build-/runtime-konsistent** sein (kein halb-fertiger Zustand).
3. Keine “WIP”-Commits auf `main`.
4. Kein Misch-Commit mit unzusammenhängenden Themen.
5. Keine generierten Binärartefakte (Modelle, Logs, große Datasets) committen.

## Commit-Nachrichten (verbindlich)

Verwende Conventional-Commit-Stil:

`<type>(<scope>): <kurze beschreibung>`

Empfohlene Types:

- `feat`
- `fix`
- `refactor`
- `docs`
- `chore`
- `test`
- `ci`

Beispiele:

- `feat(train): add MVP LoRA training script for JSONL datasets`
- `fix(config): reduce default seq length for K80 stability`
- `docs(readme): add quickstart for docker compose workflow`
- `chore(docker): pin torch/transformers dependency versions`

## Body (wenn nötig)

Im Commit-Body kurz dokumentieren:

- Motivation/Problem
- technische Entscheidung
- Auswirkungen/Migration
- ggf. Breaking Changes

Beispiel:

- Why: K80 runs frequently OOM with seq_len 1024
- What: default reduced to 512, accumulation increased
- Impact: slower wall-clock, higher run stability

---

## Staging-Regeln

Vor jedem Commit:

1. `git status` prüfen.
2. Nur relevante Dateien stagen (`git add <file>` statt blind `git add .`).
3. Diff prüfen (`git diff --staged`).
4. Sicherstellen, dass keine lokalen Secrets/Artefakte enthalten sind.

Nicht committen:

- `.env`
- `data/models/**`
- `data/logs/**`
- große Rohdaten
- Zugangsdaten/Tokens

---

## Rebase / Merge

1. Historie linear halten, wenn möglich.
2. Feature-Branches vor Merge auf aktuellen `main` rebasen.
3. Konflikte fachlich auflösen, nicht “blind accept”.
4. Merge-Commit nur verwenden, wenn Kontext dadurch klarer wird.

---

## Squash-Strategie

- Vor Merge dürfen “Arbeitscommits” gesquasht werden.
- Endhistorie soll fachliche Schritte zeigen, nicht Tippfehler-Korrekturen im Minutenabstand.
- Ein Squash-Commit muss eine präzise, auditierbare Nachricht haben.

---

## Versions-/Release-Hinweise

Bei Änderungen mit reproduzierungsrelevanter Wirkung (z. B. Docker Base Image, Dependency-Pins, Trainingsdefaults):

1. Commit klar kennzeichnen (`chore`, `feat`, `fix` mit Scope).
2. Relevante Doku aktualisieren:
   - `README.md`
   - `docs/TROUBLESHOOTING_K80.md`
   - `.ai/ADR-*.md` bei Architekturentscheidung
3. Falls Breaking Change: im Commit-Body explizit markieren.

---

## Definition of Done (Git-Sicht)

Ein Change ist “commit-ready”, wenn:

- [ ] Fachliche Änderung konsistent abgeschlossen ist.
- [ ] Nur relevante Dateien gestaged sind.
- [ ] Keine Secrets/Artefakte enthalten sind.
- [ ] Commit-Message konventionskonform ist.
- [ ] Doku/Configs bei Verhaltenänderung aktualisiert wurden.
- [ ] Diff für Reviewer ohne Zusatzwissen verständlich ist.

---

## Minimaler Standard-Workflow

1. Branch erstellen:
   - `git checkout -b feat/<thema>`
2. Änderung in kleinen, kohärenten Schritten umsetzen.
3. Selektiv stagen und committen.
4. Vor finalem Push:
   - Status prüfen
   - staged diff prüfen
   - Commit-Historie prüfen
5. Branch pushen und mergen (oder direkt auf `main`, wenn vereinbart und risikoarm).

---

## Anti-Patterns (zu vermeiden)

- `update`, `misc`, `fix stuff` als Commit-Message
- riesige Sammelcommits mit vielen Themen
- Formatierung + Refactor + Feature in einem Commit
- ungeprüfte Lockfile-/Version-Änderungen
- Committen von lokalen Experimentartefakten
- nachträgliches “Force Push” auf geteilte stabile Branches ohne Abstimmung

---

## Verantwortlichkeit / Auditierbarkeit

Jeder Commit muss beantworten können:

1. **Was** wurde geändert?
2. **Warum** wurde es geändert?
3. **Welche Auswirkungen** hat es auf Training, Reproduzierbarkeit oder Betrieb?
4. **Wie** kann der Zustand reproduziert werden (Config/Version/Doc-Verweis)?

Wenn diese Fragen nicht aus Commit und zugehöriger Doku hervorgehen, ist der Commit nicht ausreichend.