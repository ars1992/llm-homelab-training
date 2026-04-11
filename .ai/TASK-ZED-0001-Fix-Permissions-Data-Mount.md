# TASK-ZED-0001 — Fix Permissions Data Mount (Bind-Mount Ownership / Retention)

## Kontext
Im laufenden Betrieb entstehen unter `data/` teilweise root-owned Artefakte (z. B. in `data/evals/`), weil Containerprozesse mit UID/GID `0:0` schreiben.  
Folge: `retention-clean` kann auf Hostseite fehlschlagen oder manuelle `chown`-Eingriffe erfordern.

## Ziel
Deterministisch verhindern, dass neue Artefakte unter `data/` root-owned sind.  
`retention-clean` soll ohne manuelle Rechtekorrektur reproduzierbar laufen.

## Scope
### In Scope
1. `docker/compose.yaml` (Service `trainer`)
2. `.env.example`
3. Kurzer Dokuhinweis in `.ai/CONTEXT.md` (oder alternativ in `docs/`), wie bei Permission-Problemen zu verfahren ist.

### Out of Scope
- Umstellung der kompletten Image-User-Strategie im Dockerfile.
- SELinux/AppArmor-Härtung.
- Änderungen am Retention-Algorithmus selbst.

---

## Fachliche Anforderungen
1. Containerprozess des `trainer`-Service muss mit Host-UID/GID laufen:
   - `user: "${USERMAP_UID:-1000}:${USERMAP_GID:-1000}"`.
2. `.env.example` muss `USERMAP_UID` und `USERMAP_GID` enthalten, inkl. kurzer Erklärung.
3. Betriebsdoku muss eindeutig erklären:
   - Ursache der Permission-Probleme,
   - Prävention per UID/GID-Mapping,
   - einmaliger Recovery-Run per `chown` für Altartefakte.

---

## Technische Änderungen (Soll-Zustand)

### 1) `docker/compose.yaml`
Im Service `trainer` ergänzen:
- `user: "${USERMAP_UID:-1000}:${USERMAP_GID:-1000}"`

### 2) `.env.example`
Neue Variablen ergänzen:
- `USERMAP_UID=1000`
- `USERMAP_GID=1000`

Mit Hinweis:
- Werte hostseitig mit `id -u` / `id -g` prüfen und bei Bedarf anpassen.

### 3) Dokuhinweis
In `.ai/CONTEXT.md` oder `docs/` kurzen Block ergänzen:
- Symptom: root-owned Dateien unter `data/*`
- Prävention: UID/GID-Mapping in Compose
- Recovery:
  - `sudo chown -R <user>:<group> data/evals`
  - optional `data/logs data/models data/datasets`
- Danach `retention-clean` erneut ausführen.

---

## Akzeptanzkriterien (Definition of Done)
1. Nach `docker compose -f docker/compose.yaml down && up -d --build` schreibt `trainer` neue Artefakte unter `data/` mit Host-Owner (nicht root).
2. `make retention-clean` läuft ohne `Permission denied`.
3. Keine Regression in bestehenden Targets (`prepare-dataset-augmented`, `real-run-*`, `eval-val`).
4. `.env.example` dokumentiert die neuen Variablen nachvollziehbar.

---

## Testplan
1. Hostwerte prüfen:
   - `id -u`
   - `id -g`
2. `.env` mit passenden `USERMAP_UID`/`USERMAP_GID` setzen.
3. Trainer-Stack neu starten (`down`, `up -d --build`).
4. Einen schreibenden Workflow laufen lassen (z. B. `make eval-val` oder `make prepare-dataset-augmented`).
5. Owner prüfen:
   - `ls -l data/evals data/logs data/models data/datasets`
6. `make retention-clean` ausführen und auf erfolgreiche Ausführung prüfen.

---

## Recovery (Einmalig für Altzustand)
Wenn bereits root-owned Artefakte vorhanden sind:
- `sudo chown -R <user>:<group> data/evals`
- optional:
  - `sudo chown -R <user>:<group> data/logs data/models data/datasets`

---

## Risiken / Nebenwirkungen
1. Falsche UID/GID in `.env` kann weiterhin Schreibprobleme verursachen.
2. Auf Hosts mit abweichender Standard-UID (`!=1000`) muss `.env` zwingend angepasst werden.
3. Für den separaten Serving-Stack kann analoges Mapping später sinnvoll sein; in dieser Task ist nur `trainer` Pflicht.

---

## Audit-Notizen
- Änderung ist rein betrieblich (Ownership/Permissions), keine fachliche Modelllogik.
- Rückverfolgbar über:
  - Compose-Diff (`user:`-Eintrag),
  - `.env.example`-Diff,
  - Betriebsnachweis via erfolgreichem `retention-clean` ohne `chown`.