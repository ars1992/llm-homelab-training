Datum: 2026-04-11
Status: Proposed
Entscheider: Maintainer llm-homelab-training
Geltungsbereich: Promotion-Mechanismus, nightly-run, Pointer-Files unter data/runs/
Betroffene Artefakte: Makefile, ggf. src/scripts/* (Promotion-Auswertung), data/runs/*
1. Kontext
Die Promotion entscheidet, welcher Adapter über LATEST_OK_ADAPTER_ID in Serving/OpenClaw genutzt wird.
Bisherige Policy: Promotion nur wenn beide Gates erfüllt sind:

pass_rate_exact_openbook >= 0.60
avg_coverage_runbook_openbook >= 0.30
Für Testzwecke wurde avg_coverage_runbook_openbook temporär stark abgesenkt (z.B. 0.003), um Serving schneller auf neue Runs zu schieben. Das führt jedoch zu:

Risiko: Serving nimmt „schwache“ Adapter zu früh
Audit-/Policy-Drift: Gate-Werte sind nicht mehr aussagekräftig
Downstream: Serving Leakage / Formatprobleme werden schneller “produktiv”
2. Entscheidung
2.1 Strikte Gates bleiben „Wahrheit“
Die Default-Gates werden wieder auf realistische Werte gesetzt (mindestens):

PROMOTE_MIN_PASS_RATE_EXACT_OPENBOOK = 0.60
PROMOTE_MIN_AVG_COVERAGE_RUNBOOK_OPENBOOK = 0.30
2.2 Shadow-Candidate statt „Cheating“
Wenn ein neuer Run die Gates nicht erfüllt, wird er nicht promotet, aber als Candidate persistiert:

Neue Pointer/Artefakte:

data/runs/LATEST_CANDIDATE_ADAPTER_ID
data/runs/LATEST_CANDIDATE_EVAL_RUN_ID
data/runs/LATEST_CANDIDATE_PROMOTION_SUMMARY.json
Ziel: Man kann Candidate gezielt testen (manuell / Canary), ohne LATEST_OK_* zu verändern.

2.3 nightly-run Verhalten
Serving-Restart erfolgt nur bei echter Promotion (Update von LATEST_OK_ADAPTER_ID).
Candidate-only wird am Ende klar geloggt (CANDIDATE_ONLY), damit Operatoren sehen: „Es gab Fortschritt, aber kein Release“.
3. Konsequenzen
Vorteile

Serving bleibt stabil und auditierbar.
Thresholds bleiben bedeutungsvoll.
Kandidaten können trotzdem bequem getestet werden.
Nachteile

Mehr Pointer-Files/Artefakte unter data/runs/.
Operator muss aktiv entscheiden, wann Candidate getestet wird.
4. Implementierungsnotizen (nicht normativ)
Makefile promote-latest-ok erweitert:
bei KEEP zusätzlich Candidate-Files schreiben (wenn RUN_ID existiert und Eval-Report vorhanden ist)
Promotion-Report muss die verwendeten Gate-Werte ausgeben (IST/SOLL), damit Overrides auditierbar bleiben.
5. Akzeptanzkriterien
Bei avg_coverage_runbook_openbook < 0.30 bleibt LATEST_OK_ADAPTER_ID unverändert.
Candidate-Pointer werden aktualisiert.
nightly-run bleibt End-to-End „grün“, ohne Serving auf Candidate zu schalten.
