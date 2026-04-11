Datum: 2026-04-11
Status: Proposed (nach Umsetzung → Accepted)
Entscheider: Maintainer llm-homelab-training
Geltungsbereich: llm-homelab-training (Training-Pipeline, Datasets, Audit)
Betroffene Artefakte: src/scripts/generate_self_edits.py, Makefile, data/-Layout, ggf. src/datasets/schemas/*, .ai/*
1. Kontext
Das Projekt llm-homelab-training hat einen stabilen MVP-Trainingspfad (Dataset → Train → Eval → Promotion → Serving). Der nächste Ausbau soll eine SEAL-inspirierte Self-Edit Pipeline ermöglichen, um gezielt “abgeleitete Trainingssamples” zu erzeugen und auditierbar in den Trainingspfad zurückzuführen.

Rahmenbedingungen:

Reproduzierbarkeit und Auditierbarkeit haben Priorität vor “Smartness”.
Zielhardware umfasst NVIDIA Tesla K80 (Legacy-Stack, Stabilität vor Komplexität).
Keine Cloud-Abhängigkeit, keine Secrets im Repo.
Der aktuelle Stand von generate_self_edits.py ist ein Placeholder (Pfad-/Formatstabilisierung), soll aber als Entry-Point bestehen bleiben.
2. Entscheidung
Wir implementieren einen SEAL-MVP als deterministischen, regelbasierten Self-Edit Loop mit vollständigem Audit Trail.

2.1 generate_self_edits.py als Orchestrator mit Modi
src/scripts/generate_self_edits.py bleibt der Einstiegspunkt und unterstützt mindestens zwei Modi:

--mode placeholder
Beibehaltung der bisherigen technischen Placeholder-Logik (für Debug/Pfadstabilität).
--mode generate
Neuer SEAL-MVP-Loop: Kandidaten erzeugen → normalisieren/dedupe → verifizieren → akzeptierte Derived Samples exportieren.
2.2 Deterministische Verifikation (MVP)
Der MVP nutzt keinen LLM-Judge, sondern einen regelbasierten Verifier:

Schema-/Pflichtfeld-Checks
No-op/Diff-Checks (kein identisches Derived Sample zur Quelle)
einfache Policy-Heuristiken (z.B. “keine Secrets”, “keine offensichtlichen absoluten Host-Pfade”)
Ergebnis: accept | reject | needs_review
2.3 Artefakt- und Pfadkonvention (verbindlich)
Pro Self-Edit Run wird ein vollständiger Artefaktsatz unter einem Run-Ordner erzeugt:

data/self_edits/runs/<run_id>/

sources.snapshot.jsonl
candidates.jsonl
verifications.jsonl
accepted.derived.jsonl
manifest.json
Zusätzlich wird ein stabiler Exportpfad für den Trainingspfad bereitgestellt:

data/training/derived/self_edits.accepted.jsonl
Trennung ist verbindlich:

Source bleibt read-only Referenz
Derived Samples sind getrennte, auditierbare Trainingsinputs mit Provenance
2.4 Datamodel (minimal)
Wir führen ein minimales, auditierbares Datenmodell ein (JSONL/Manifest), mindestens mit den Entitäten:

SourceSample
EditCandidate
VerificationRun
DerivedTrainingSample
SelfEditRun (Manifest-Klammer über den Run)
(Implementierung als JSON Schema oder Python-Validatoren ist zulässig; die Felder müssen jedoch stabil sein.)

2.5 Makefile-Integration
Es werden standardisierte Targets ergänzt:

make self-edits-generate
Erzeugt einen Run und exportiert self_edits.accepted.jsonl.
optional: make self-edits-validate
Validiert JSONL/Schemas, fail-fast bei Parse-/Schemafehlern.
3. Begründung (Trade-offs)
Vorteile
Auditierbarkeit: Jeder Schritt (Quelle → Kandidat → Verifikation → Export) ist nachvollziehbar.
Reproduzierbarkeit: deterministische Logik reduziert Drift und “magische” Entscheidungen.
Saubere Integration: Derived Samples können kontrolliert in Training gemerged werden (späterer Schritt).
Stabilität: Kein zusätzlicher LLM-Judge-Stack im MVP reduziert Failure Modes (K80/Legacy).
Nachteile
Qualitätsgrenze im MVP: rein regelbasierte Self-Edits sind weniger “intelligent” als modellgenerierte Kandidaten.
Mehr Artefakte: zusätzlicher Storage/Retention-Bedarf in data/.
Mehr Komplexität in Pipeline: neue Targets + neue Artefaktklassen müssen gepflegt werden.
4. Konsequenzen
Der Placeholder bleibt: Operatoren können weiterhin dry/debug runs machen.
SEAL-MVP ist deterministic: kein LLM-Judge, kein Re-prompting im MVP.
Training-Pipeline kann erweitert werden, aber nur über klaren, getrennten Exportpfad.
Retention/Permissions beachten: neue Ordner unter data/self_edits/ werden Teil der Retention-Policy; Container-Usermapping sollte sauber sein, damit keine root-owned Artefakte entstehen.
5. Implementierungsnotizen (nicht-normativ, aber hilfreich)
CLI Zielbild
python src/scripts/generate_self_edits.py \
  --mode generate \
  --input-jsonl data/datasets/train.jsonl \
  --output-dir data/self_edits/runs/<run_id> \
  --export-accepted data/training/derived/self_edits.accepted.jsonl \
  --max-sources 50 \
  --candidates-per-source 1 \
  --seed 1337
Akzeptanzkriterien (DoD)
make self-edits-generate läuft grün
alle Run-Artefakte + Manifest existieren
data/training/derived/self_edits.accepted.jsonl ist valide JSONL
Accepted Samples enthalten Provenance (candidate_id, source_sample_id, verification refs)
deterministisch: identische Inputs/Parameter → stabiler Output (bis auf run_id/timestamps)
6. Alternativen (bewertet)
A) LLM-Judge im MVP
Verworfen (zu viel Nicht-Determinismus, zusätzliche Abhängigkeit/Fehlerfläche, schwer auditierbar).
B) Self-Edits direkt ins Training schreiben ohne getrennten Export
Verworfen (Audit/Provenance leidet, Risiko von “silent contamination” des Trainingssets).
C) Neuer Entry-Point statt generate_self_edits.py
Verworfen (bestehender Placeholder/Pfadstabilität soll erhalten bleiben; ein stabiler Einstiegspunkt ist wertvoll).
7. Offene Punkte (nach MVP)
Optionaler 2nd Verifier (LLM-Judge) als separater, explizit aktivierter Modus
Human Review Queue für needs_review
Integration/Weighting beim Merge in train.jsonl (Sampling/Cap/Dedupe)
Spezifische Optimierung: SEAL gezielt für Runbook-coverage (expected_contains) einsetzen
