# QUALITAET-MENSCHLICHE-AUFGABEN-UND-PARAMETER

## Dokumentkontrolle
- Status: Verbindlich
- Version: 1.0
- Datum: 2026-04-10
- Geltungsbereich: `llm-homelab-training`, menschliche Qualitätssicherung und Trainingsparameter
- Ziel: Systematische Beschreibung der Aufgaben, die kein Automatismus übernehmen kann, sowie vollständige Parameterdokumentation

---

## Grundsatz

Das Modell optimiert auf das, womit es trainiert wird.
Wenn Eingabedaten, Schwellenwerte oder Regression-Sets schlecht sind, wird das Modell besser darin, genau das zu reproduzieren.

Die folgenden Aufgaben können nicht automatisiert werden, weil sie fachliches Urteilsvermögen erfordern.

---

## 1. Menschliche Qualitätssicherung

### 1.1 Regression-Set pflegen (`data/datasets/val.jsonl`)

Das Regression-Set ist die einzige stabile Qualitätsbremse im System.
Ein automatischer Lauf kann nur so gut prüfen, wie das Set es abdeckt.

#### Aufgaben

| Aufgabe | Frequenz | Begründung |
|---|---|---|
| Neue Fälle hinzufügen | nach jedem inhaltlichen Wissensänderung | neue Themen brauchen neue Tests |
| Bestehende `expected_contains` prüfen | monatlich | fachliche Wahrheit ändert sich |
| Fail-Cases analysieren | nach jedem Eval-Run | Verständnis warum das Modell scheitert |
| Coverage-Lücken erkennen | quartalsweise | blinde Flecken im Testset identifizieren |
| Überalterungen entfernen | bei Umbau von Systemen | tote Tests produzieren falschen Pass |

#### Konkretes Beispiel
Das Modell gibt auf eine Frage zu `make preflight` eine veraltete Antwort.
Das merkst du nur, wenn du `val.jsonl` um genau diese Frage erweitert hast.
Ohne val-Eintrag: kein Signal, kein Stopp, kein Rollback.

#### Qualitätskriterien für val-Einträge
- `instruction` ist eindeutig und nicht mehrdeutig interpretierbar
- `expected_contains` enthält 1–3 kurze, prüfbare Substrings
- `tags` erlauben sinnvolle Gruppierung nach Kategorie
- Jeder Eintrag hat eine stabile, eindeutige `id`
- Keine Secrets, Tokens oder Zugangsdaten

---

### 1.2 Trainingsdaten fachlich prüfen (`data/datasets/train.jsonl`)

#### Grundregel
Müll rein, Müll raus.
Ein falscher Output bedeutet: das Modell lernt diesen Fehler als Wahrheit.

#### Prüfpunkte

| Prüfpunkt | Schlecht | Gut |
|---|---|---|
| Instruction klar? | „Erkläre Docker." | „Erkläre, was `docker compose up -d` macht." |
| Output fachlich korrekt? | veraltet oder falsch | aktuell und verifiziert |
| Output-Länge sinnvoll? | 3 Wörter oder 50 Sätze | proportional zur Fragetiefe |
| Keine Dopplungen? | 40 fast identische Samples | Themenbreite anstreben |
| Domänenwissen enthalten? | generisches Lehrbuch | Eliot-/Projektspezifisch |

#### Dopplungs-Risiko
Wenn 30% der Trainingsdaten über das gleiche Thema handeln, lernt das Modell dieses Thema überproportional gut und alles andere schlechter.
Das nennt sich **Überrepräsentation** und führt zu verzerrten Antworten.

---

### 1.3 Promotion-Schwellenwerte hinterfragen

#### Aktuelle Werte
- `pass_rate_exact_openbook >= 0.60`
- `avg_coverage_runbook_openbook >= 0.30`

#### Wann anpassen?

| Situation | Maßnahme |
|---|---|
| Modell erreicht 0.90+ bei jedem Lauf | Schwellenwert erhöhen, sonst promotet Regressionsstände |
| Promotion schlägt mehrfach hintereinander fehl | val-Set oder Trainingsdaten prüfen, nicht Schwellenwert senken |
| Neue Themenbereiche im Training | Schwellenwert vorübergehend anpassen bis Coverage aufgebaut |

#### Warnung
Schwellenwert senken bei dauerhaftem Fail ist keine Lösung.
Das ist ein Signal, dass Daten oder Architektur das eigentliche Problem sind.

---

### 1.4 Self-Edit-Kandidaten stichprobenartig lesen

Sobald `generate_self_edits.py` echte Kandidaten erzeugt, gilt:

#### Prüfpflicht

| Queue | Prüffrequenz | Was prüfen? |
|---|---|---|
| `needs_review` | bei jedem Lauf | echte Grenzfälle oder Logikfehler? |
| `accepted` | Stichprobe min. 10% | ist das wirklich besser als das Original? |
| `rejected` | Reject-Gründe aggregiert | NO_OP zu hoch = Edit-Strategie zu schwach |

#### Zeichen für problematische Kandidaten
- Kandidat klingt besser, aber Fakten sind falsch
- Kandidat ist länger, sagt aber dasselbe
- Kandidat fügt Beispielbefehl hinzu, der nicht existiert

---

### 1.5 Holdout-Set führen

Das Holdout-Set ist eine kleine Sammlung von Fragen, die:
- niemals Teil von `train.jsonl` werden
- niemals Teil von `val.jsonl` werden
- nur für Drift-Erkennung genutzt werden

#### Zweck
Wenn das Modell auf dem val-Set besser wird, aber auf dem Holdout-Set schlechter, ist das Drift oder Regression.

#### Empfohlener Umfang
10–20 handverlesene Fragen aus verschiedenen Themengebieten.

#### Wann auswerten?
Nach jedem Promotion-Zyklus, bevor Serving mit neuen Adapter aktualisiert wird.

---

### 1.6 Signale für menschlichen Eingriff

| Signal | Ursache (vermutet) | Maßnahme |
|---|---|---|
| Promotion scheitert mehrfach hintereinander | Daten oder val-Set sind das Problem | Datenqualität prüfen, nicht Schwellenwert senken |
| `pass_rate` stagniert trotz mehr Training | Dataset zu klein, homogen oder fehlerhaft | Datenbasis erweitern und diversifizieren |
| `needs_review`-Queue wächst dauerhaft | Verifier-Logik zu restriktiv oder Edits zu schwach | Verifier-Regeln und Edit-Strategien überarbeiten |
| Modell antwortet auf bekannte Fragen schlechter | Regression | kein neuer Promote, zurück auf letzten OK-Adapter |
| LLM-Judge akzeptiert zu viel | Confirmation Bias oder Reward Hacking | Judge-Prompt und Kriterien schärfen |
| LLM-Judge akzeptiert zu wenig | Judge zu restriktiv oder falsche Kriterien | Kriterien überprüfen, Stichprobe manuell prüfen |

---

### 1.7 LLM-as-Judge: menschliche Kontrollpflicht

Wenn in Schritt 3 des SEAL-Loops ein LLM als Verifier eingesetzt wird:

#### Bekannte Risiken

| Risiko | Beschreibung | Gegenmaßnahme |
|---|---|---|
| Model Collapse | Generator lernt, was der Judge mag, nicht was korrekt ist | regelmäßig gegen externen Benchmark testen |
| Confirmation Bias | Generator und Judge haben gleiche blinde Flecken | unterschiedliche Modelle oder Modellversionen nutzen |
| Bias Amplification | Judge verstärkt Stilpräferenzen, nicht Faktenkorrektheit | Judge-Ausgaben stichprobenartig manuell prüfen |
| Reward Hacking | Generator optimiert auf Judge-Prompt, nicht auf Wahrheit | Judge-Prompts rotieren, nicht einfrieren |
| Distribution Shift | lokale Verbesserung verschlechtert anderen Wissensbereich | Holdout-Set nach jedem Lauf testen |

#### Bekannte Systeme mit LLM-as-Judge / gegenseitiger Verifikation
(Quelle: Eliot-Antwort 2026-04-10)

- Constitutional AI (Anthropic): Modell kritisiert sich selbst nach definierten Regeln
- RLHF + Reward Model (InstructGPT): Reward Model als separater Bewerter
- LLM-as-Judge / MT-Bench (LMSYS): paarweise Bewertung durch LLM
- AI Safety via Debate (Irving et al.): zwei Modelle argumentieren, Judge entscheidet
- SPIN: Self-Play Fine-Tuning ohne menschliche Labels

#### Einschätzung für K80-Homelab
Realistisch umsetzbar:
- deterministischer regelbasierter Verifier als MVP-Standard
- kleines Modell als offline Batch-Judge (kein Online-Inference während Training)
- Holdout-Eval gegen externes Set als Sicherheitsnetz

Nicht empfohlen für K80:
- vollständiges RLHF mit PPO
- große Self-Play-Loops mit vielen Iterationen
- simultaner Generator + Judge-Betrieb während Training

---

## 2. Trainingsparameter-Referenz

### Legende für alle Parametertabellen

```
PARAMETER        : technischer Bezeichner
Wert (aktuell)   : verwendeter Wert in diesem Projekt
Bereich (a–b)    : sinnvoller Wertebereich
Grenzwerte       : wann wird es kritisch
Effekt           : was passiert wenn der Wert steigt / fällt
Alternativen     : andere Ansätze mit ähnlichem Ziel
Sideeffect       : Nebenwirkungen bei Abweichung vom Standardwert
```

---

### 2.1 `max_seq_length`

```
PARAMETER        : max_seq_length
Wert (aktuell)   : 384
Bereich          : 128 – 2048 (K80: sicher 128–512)
Grenzwerte       : unter 128 = zu kurz für sinnvolle Instruktionen
                   über 512 auf K80 = OOM-Risiko hoch
Effekt           : höher → mehr Kontext, mehr VRAM-Verbrauch, längere Steps
                   niedriger → schnellere Steps, weniger Kontext, mehr Abschneidungen
Alternativen     : chunking von langen Dokumenten vor Training
Sideeffect       : zu kurz schneidet Outputs und Instruktionen ab → Qualitätsverlust
                   zu lang → Swap-Druck, OOM, instabiler Lauf auf K80
```

---

### 2.2 `per_device_train_batch_size`

```
PARAMETER        : per_device_train_batch_size
Wert (aktuell)   : 1
Bereich          : 1 – 8 (K80: praktisch nur 1)
Grenzwerte       : über 1 auf K80 mit 3B-Modell = OOM sehr wahrscheinlich
Effekt           : höher → stabileres Gradienten-Signal, schnellerer Durchsatz
                   niedriger → noisier Gradients, langsamer aber speicherschonend
Alternativen     : gradient_accumulation_steps erhöhen statt batch_size
Sideeffect       : batch_size=1 ohne hohe Akkumulation = sehr noisy Gradients
                   kann Trainingsinstabilität verursachen bei hohen Learning Rates
```

---

### 2.3 `gradient_accumulation_steps`

```
PARAMETER        : gradient_accumulation_steps
Wert (aktuell)   : 24
Bereich          : 4 – 64 (K80: 16–32 empfohlen)
Grenzwerte       : unter 8 bei batch_size=1 = sehr noisy, instabiles Training
                   über 64 = sehr seltene Gewichts-Updates, träges Lernen
Effekt           : höher → simuliert größere effektive Batchgröße
                   effektive Batchgröße = batch_size × grad_accum_steps
                   bei batch=1, accum=24 → effektive Batchgröße = 24
                   niedriger → häufigere aber weniger stabile Updates
Alternativen     : batch_size erhöhen (wenn VRAM reicht)
Sideeffect       : erhöht Laufzeit pro Epoche proportional
                   bei falscher Kombination mit lr → Overshooting oder Stagnation
```

---

### 2.4 `learning_rate`

```
PARAMETER        : learning_rate
Wert (aktuell)   : 2e-4 (typisch für LoRA)
Bereich          : 1e-5 – 5e-4
Grenzwerte       : über 5e-4 = instabiles Training, Loss-Spikes wahrscheinlich
                   unter 1e-5 = Modell lernt kaum, sehr lange Konvergenz
Effekt           : höher → schnelleres aber instabileres Lernen
                   niedriger → langsames aber stabiles Lernen
Alternativen     : lr_scheduler_type anpassen statt fester lr
Sideeffect       : zu hoch + batch_size=1 = Loss-Explosionen
                   zu niedrig = Training scheinbar stabil aber kein Fortschritt
```

---

### 2.5 `lora_r` (LoRA Rang)

```
PARAMETER        : lora_r
Wert (aktuell)   : 16
Bereich          : 4 – 64
Grenzwerte       : unter 4 = zu wenig Kapazität für komplexe Anpassungen
                   über 32 auf K80 = deutlich mehr VRAM, längere Steps
Effekt           : höher → mehr trainierbare Parameter, mehr Ausdruckskraft
                   niedriger → kompakter, schneller, weniger VRAM
Alternativen     : lora_alpha proportional anpassen (typisch lora_alpha = 2 × lora_r)
Sideeffect       : zu hoch ohne ausreichend Daten → Overfitting auf Trainingssatz
                   zu niedrig → Modell kann fachliche Spezifika nicht erlernen
```

---

### 2.6 `lora_alpha`

```
PARAMETER        : lora_alpha
Wert (aktuell)   : 32 (typisch = 2 × lora_r)
Bereich          : lora_r – 4 × lora_r
Grenzwerte       : deutlich kleiner als lora_r = sehr schwache Adapter-Gewichte
                   deutlich größer als 4 × lora_r = instabile Skalierung
Effekt           : höher → stärkerer Einfluss des Adapters auf das Basismodell
                   bestimmt den Skalierungsfaktor: alpha / r
Alternativen     : festes Verhältnis alpha = 2 × r als Faustregel beibehalten
Sideeffect       : falsche alpha/r-Ratio → inkonsistentes Lernverhalten
```

---

### 2.7 `lora_dropout`

```
PARAMETER        : lora_dropout
Wert (aktuell)   : 0.05
Bereich          : 0.0 – 0.2
Grenzwerte       : über 0.2 = zu viel Regularisierung, Modell lernt kaum
                   unter 0.01 = kein Regularisierungseffekt
Effekt           : höher → mehr Regularisierung, verhindert Overfitting
                   niedriger → weniger Regularisierung, schnelleres Lernen
Alternativen     : weight_decay als komplementäre Regularisierung
Sideeffect       : zu hoch auf kleinem Dataset = Underfitting
```

---

### 2.8 `num_train_epochs` / `max_steps`

```
PARAMETER        : max_steps (dominiert wenn gesetzt, überschreibt num_train_epochs)
Wert (aktuell)   : 60 (short run)
Bereich          : 30 – 1000 (abhängig von Dataset-Größe)
Grenzwerte       : unter 30 = zu wenig für sinnvolles Lernen
                   zu hoch bei kleinem Dataset = Overfitting
Effekt           : höher → mehr Lernzeit, potenziell bessere Qualität, höhere Laufzeit
                   niedriger → schneller, aber weniger gelernt
Alternativen     : num_train_epochs bevorzugen wenn Dataset-Größe bekannt
Sideeffect       : max_steps überschreibt epochs → bei falscher Kombination endet
                   Training zu früh oder zu spät für die Datenmenge
```

---

### 2.9 `gradient_checkpointing`

```
PARAMETER        : gradient_checkpointing
Wert (aktuell)   : true
Bereich          : true / false
Grenzwerte       : nicht anwendbar (boolescher Wert)
Effekt           : true → reduziert VRAM-Verbrauch erheblich
                         durch Neuberechnung von Aktivierungen im Backward-Pass
                         auf K80 praktisch zwingend für 3B-Modell
                   false → schnelleres Training, aber deutlich höherer VRAM
Alternativen     : keine sinnvolle Alternative auf K80 für 3B-Modell
Sideeffect       : leicht langsamere Steps (Neuberechnung kostet Zeit)
                   bei bestimmten Modell-/Adapter-Kombinationen muss
                   enable_input_require_grads() aktiv gesetzt werden
```

---

### 2.10 `fp16` / `bf16`

```
PARAMETER        : fp16
Wert (aktuell)   : true
Bereich          : fp16=true/false, bf16=true/false (nie beide gleichzeitig)
Grenzwerte       : bf16 auf K80 nicht unterstützt (Compute Capability 3.7)
                   fp32 auf K80 = sehr langsam und extrem hoher VRAM-Verbrauch
Effekt           : fp16=true → halbe VRAM-Nutzung für Aktivierungen und Gradienten
                             → schnellere Berechnungen auf CUDA
                   fp16=false → volle Präzision, mehr VRAM, langsamer
Alternativen     : bf16 auf neueren GPUs (Ampere+)
Sideeffect       : fp16 kann numerische Instabilität bei hohen lr erzeugen
                   bei Loss-NaN/Inf: lr senken oder fp16-Scaler prüfen
```

---

### 2.11 `warmup_ratio`

```
PARAMETER        : warmup_ratio
Wert (aktuell)   : 0.05
Bereich          : 0.01 – 0.1
Grenzwerte       : unter 0.01 = kein sinnvoller Warmup, frühe Instabilität möglich
                   über 0.15 = zu langer Warmup, verschenkte Steps
Effekt           : definiert Anteil der Steps zum linearen lr-Aufheizen
                   schützt vor Loss-Spikes am Trainingsanfang
Alternativen     : warmup_steps als absoluter Wert statt Ratio
Sideeffect       : kein Warmup + hohe lr = häufige Loss-Spikes in den ersten Steps
```

---

### 2.12 `lr_scheduler_type`

```
PARAMETER        : lr_scheduler_type
Wert (aktuell)   : cosine
Bereich          : linear / cosine / cosine_with_restarts / constant / constant_with_warmup
Grenzwerte       : constant ohne decay = lr bleibt hoch, Overfitting-Risiko
Effekt           : cosine → sanftes Abklingen der lr bis zum Trainingsende
                          → stabiles Konvergenzverhalten
                   linear → direktes lineares Abklingen
                   constant → keine Änderung der lr
Alternativen     : linear für sehr kurze Läufe (weniger Artefakte)
Sideeffect       : falscher Scheduler kann trotz korrekter lr zu schlechter
                   Konvergenz führen (zu schnelles Abklingen → kein Lernen mehr)
```

---

### 2.13 `tokenization_num_proc` / Dataloader-Parallelität

```
PARAMETER        : tokenization_num_proc
Wert (aktuell)   : 1
Bereich          : 1 – CPU-Kerne
Grenzwerte       : über 2 auf K80-Host mit RAM-Druck = Swap-Spitzen
Effekt           : höher → schnellere Tokenisierung durch Parallelität
                   niedriger → langsamer, aber RAM-schonend
Alternativen     : Dataset vor Training vorweg tokenisieren und cachen
Sideeffect       : hoher num_proc bei vollem RAM = Swap-Thrash schon vor Training
```

---

### 2.14 `save_steps` / `save_total_limit`

```
PARAMETER        : save_steps
Wert (aktuell)   : 30
Bereich          : 10 – 200
Grenzwerte       : zu häufig (unter 10) = I/O-Last, viel Speicher für Checkpoints
                   zu selten (über 200 bei 60 Steps) = kein Zwischenstand
Effekt           : häufiger → mehr Checkpoints, mehr Speicherplatz
                   seltener → weniger Checkpoints, weniger Overhead

PARAMETER        : save_total_limit
Wert (aktuell)   : 2
Bereich          : 1 – 5
Effekt           : limitiert Anzahl aufbewahrter Checkpoints auf Disk
                   bei 2: nur die letzten 2 Checkpoints bleiben erhalten
Sideeffect       : zu wenige Checkpoints → bei OOM-Abbruch kein guter Recovery-Punkt
```

---

## 3. Empfohlene Interventionsreihenfolge bei Problemen

### Bei OOM / Swap-Druck (verbindliche Reihenfolge)

```
1. max_seq_length reduzieren (512 → 384 → 256)
2. gradient_accumulation_steps erhöhen (16 → 24 → 32)
3. tokenization_num_proc auf 1 setzen
4. gradient_checkpointing = true sicherstellen
5. erst danach andere Parameter ändern
```

### Bei Loss-Spikes

```
1. learning_rate senken (z.B. 2e-4 → 1e-4)
2. warmup_ratio prüfen (min. 0.03)
3. fp16-Kompatibilität prüfen (NaN im Loss = Präzisionsproblem)
4. Datensatz auf fehlerhafte Samples prüfen
```

### Bei stagnierendem Loss / kein Lernfortschritt

```
1. learning_rate prüfen (zu niedrig?)
2. lora_r erhöhen (mehr Kapazität?)
3. Dataset-Qualität und -Größe prüfen
4. max_steps / num_train_epochs erhöhen
```

### Bei Overfitting (val schlechter als train)

```
1. lora_dropout erhöhen
2. weight_decay erhöhen
3. Dataset diversifizieren
4. max_steps reduzieren
```

---

## 4. Zusammenfassung: Was der Mensch macht, was das System macht

| Bereich | Mensch | System |
|---|---|---|
| Datensatz | pflegen, prüfen, diversifizieren | verarbeiten, tokenisieren |
| val-Set | erstellen, erweitern, fachlich verifizieren | ausführen, Passrate berechnen |
| Schwellenwerte | festlegen, anpassen, hinterfragen | anwenden |
| Hyperparameter | setzen, begründen, bei Problemen anpassen | konsumieren |
| Self-Edit-Kandidaten | stichprobenartig prüfen | erzeugen, verifizieren, exportieren |
| Holdout-Set | erstellen, auswerten, entscheiden | nicht bekannt |
| Drift-Erkennung | interpretieren, Maßnahmen ableiten | signalisieren (Metriken) |
| LLM-Judge-Bias | erkennen, korrigieren, rotieren | anwenden |
| Rollback-Entscheidung | treffen | nicht autonom |

---

## 5. Offene Entscheidungen

1. Ab welchem `pass_rate`-Wert soll der Promotionsschwellenwert angehoben werden?
2. Welche Stichprobengröße ist verbindlich für die manuelle Self-Edit-Prüfung?
3. Soll ein dediziertes Holdout-Set in `data/datasets/` angelegt werden?
4. Wird der LLM-as-Judge als erster oder zweiter Verifier eingesetzt?
5. Welche Rotationsfrequenz gilt für Judge-Prompts, wenn ein LLM-Judge aktiv ist?