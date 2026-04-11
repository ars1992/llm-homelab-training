Datum: 2026-04-11
Status: Proposed
Entscheider: Maintainer llm-homelab-training
Geltungsbereich: Serving-Ausgabeformat, OpenAI-kompatibles API, Smoke/Regression Tests
Betroffene Artefakte: src/serve/app.py (oder Serving Prompt/Decode), scripts/serve_smoke.sh, Makefile (serve-test)
1. Kontext
Im Serving wurden Antworten beobachtet, die interne Template-Strukturen und Artefakte leaken, z.B.:

Dateinamen (*.md)
Wrapper wie ## Input: ...
Marker wie ### Instruction/Response
Das ist ein Qualitätsproblem (Output-Policy) und kann potentiell sensible Kontextmuster verstärken.

Es existiert bereits ein serve-test/serve_smoke.sh, aber die Leakage wird nicht zwingend als Fail-Gate erkannt.

2. Entscheidung
2.1 Serving muss „final answer only“ erzwingen
Serving erhält Guardrails auf drei Ebenen:

System Prompt: klare Policy („nur finale Antwort“, keine Wrapper, keine Dateinamen)
Stop/Cut Rules: Generation stoppt oder wird abgeschnitten bei typischen Markern:
###
## Input:
Kontext:, Antwort:, Instruction:
Sanitizer (Fail-safe): Post-Processing entfernt restliche Wrapper-Zeilen deterministisch.
2.2 serve-test wird zum Regression Gate für Leakage
make serve-test muss Leakage als Test-Fail behandeln.

Neue harte „MUST NOT CONTAIN“ Checks (mindestens):

## Input
###
.md
/home/
Wenn ein Check verletzt wird → Exit 1.

3. Konsequenzen
Vorteile

Serving wird robuster gegen Prompt-/Template-Leaks.
Regression-Tests verhindern, dass das Problem wiederkommt.
Nachteile

Stop/Sanitizer kann in seltenen Fällen legitime Inhalte abschneiden (Trade-off für MVP).
Tests müssen gepflegt werden (aber das ist gewollt).
4. Implementierungsnotizen (nicht normativ)
src/serve/app.py:
system prompt harden
stop sequences ergänzen
post-sanitize implementieren (z.B. line-based cut)
scripts/serve_smoke.sh:
mindestens 1 Prompt, der die Leakage zuvor reproduziert hat
Assertions implementieren (grep/exit)
5. Akzeptanzkriterien
Nach Änderungen: make serve-test ist grün.
Test reproduziert (bei altem Stand) das Leakage-Fail, und verhindert Regression.
Serving-Antworten enthalten keine Wrapper-/Dateinamen-Token mehr.
