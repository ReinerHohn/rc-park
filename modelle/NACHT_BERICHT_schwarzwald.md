# Nacht-Bericht — Schwarzwald-Kandidaten + Selbstbewertung (3 Juroren + Voting)

Auftrag: schwarzwaldtypische, **markante** Modelle finden, die sich gut mit 3D-Druck +
Lasercut bauen lassen; dann ein **eigenes Bewertungssystem** bauen (mehrere Tools, die
abstimmen) und **kritisch** sein.

## 1. Was gebaut wurde

**Kandidaten-Katalog** (`tools/schwarzwald_katalog.py` → `modelle/schwarzwald_kandidaten.md/.json`)
16 Natur-Features + 18 Bauwerke, alle mit **verifizierten Koordinaten** (WebSearch) und
**berechneter LGL-2km-Kachel** (DGM025/DOP20-URL direkt ableitbar). Ehrlich markiert, was
NICHT dramatisch ist (Titisee, Schluchsee-*Gelände*) und was nicht parametrisch nachbaubar
ist (Freiburger Münster-Helm, ausgedehnte Burgruinen → brauchen LiDAR/LOD2).

**Drei unabhängige Juroren** (verschiedene Perspektiven, stimmen ab):
- `bewerter_geometrie.py` — **Geometrie-Treue**: frisst Glättung/Auflösung die Kanten weg?
  (Glättungs-Rest vs. Roh-DEM in Modell-mm, gesamt + steilste 20 %).
- `bewerter_fertigung.py` — **Fertigbarkeit**: baubar auf S9/Drucker? (Teile ≤ Bett,
  Mini-Bruchstücke, STL watertight; ohne Artefakt: Schätzung Bretter/Rippen/Zeit).
- `bewerter_markanz.py` — **Markanz**: lohnt es sich? (Fallhöhe, Steilwand-Anteil +
  p95-Hangneigung in der **dramatischsten Teilregion**, See-Signatur).
- `bewerter_voting.py` — **Voting**: gewichtet (Markanz .40 · Geometrie .33 · Fertigung .27),
  **kritisch**: jedes FAIL deckelt auf WARN; „BAUEN" nur bei Schnitt ≥68 + ≥2× PASS; nennt
  den größten Einwand + nächsten Schritt. `--batch ... --rank` für Ranglisten.

## 1b. PANEL-Upgrade (`bewerter_panel.py`) — 3 Juroren pro Kategorie, einstimmig

Statt 1 Juror/Kategorie jetzt **3 unabhängige Juroren je Kategorie** (je andere Methode),
die HART abstimmen: Kategorie PASS nur **einstimmig**, FAIL sobald einer FAILt, sonst WARN
(Uneinigkeit wird namentlich benannt). Gesamt **„BAUEN (einstimmig)"** nur wenn alle 9 PASS.
Verschiedene Methoden → Einstimmigkeit bedeutet echte Sicherheit statt Redundanz. Jeder Juror
einzeln fair kalibriert, damit ein FAIL ein ECHTER Defekt ist (nicht ein Metrik-Artefakt).

| Kategorie | Juror 1 | Juror 2 | Juror 3 |
|---|---|---|---|
| Geometrie Gelände | Oberflächen-RMS | Grat-/Kantentreue | Form-Statistik (Steilflächen-Erhalt) |
| Geometrie Bauwerk | Durchsicht/Dichtheit | Bogen-Rhythmus+Regelmäßigkeit | Proportion+Mesh |
| Markanz Gelände | Fallhöhe | Wand-Schärfe | Formfülle (TRI) |
| Markanz Bauwerk | Größe/Präsenz | Bogen-Rhythmus | Regelmäßigkeit |
| Fertigbarkeit | Bett-Fit | Robustheit | Aufwand/Material |

Panel-Rangliste: Hirschsprung 96 · Belchen 92 · Ravenna 91 = **BAUEN (einstimmig)**;
Linach 90 · Schluchsee 87 = BEDINGT (je 1 ehrlicher WARN); Triberg · Feldsee = NACHBESSERN
(Bett-Fit: Fenster zu groß → kacheln). Aufruf: `python3 tools/bewerter_panel.py --batch '…' --rank`.

## 2. Rangliste (Einzel-Juror-Version, historisch)

| # | Modell | Gesamt | Urteil | schwächster Juror → Hebel |
|--:|---|--:|---|---|
| 1 | Hirschsprung / Höllental | 95 | 🟢 BAUEN | Markanz top, nichts offen |
| 2 | Belchen | 91 | 🟢 BAUEN | Fertigbarkeit (groß → kacheln) |
| 3 | Triberger Wasserfälle | 83 | 🟢 BAUEN | Fertigbarkeit |
| 4 | Schluchsee-Staumauer | 76 | 🟢 BAUEN | Markanz: Fenster zu weit → auf Mauer-Front zuschneiden |
| 5 | Feldsee | 75 | 🟡 BEDINGT | Fertigbarkeit: 1562 mm → 25 Bretter, enger croppen / kleinerer Maßstab |

## 3. Kritische Erkenntnisse (die das Voting selbst aufgedeckt hat)

- **Schluchsee als *Gelände* ist NICHT markant** (erster Lauf: Markanz 28 → FAIL). Das
  Markante ist die **Staumauer als Bauwerk** — die Topografie allein trägt das Modell nicht.
  Konsequenz: Schluchsee braucht einen **parametrischen Gewichtsstaumauer-Generator**
  (Trapez-Querschnitt, leicht gekrümmter Grundriss; 63,5 m × 250 m, Daten liegen vor),
  nicht nur ein Höhenfeld.
- **Loses Fenster verwässert Dramatik.** Erst maß der Markanz-Juror über das ganze Fenster
  und strafte gute Features für ihre sanfte Umgebung ab (Feldsee-Karwand, Belchen-Kegel
  fielen durch). Fix: Juror sucht jetzt die **dramatischste Teilregion** (so wie man den
  Ausschnitt rahmt) und nennt den Fensterkern zum Zuschneiden. Das ist zugleich eine
  **konkrete Handlungsanweisung** pro Modell.
- **Der limitierende Faktor ist fast nie die Geometrie-Treue** (DGM 0,25 m ist überall
  exzellent: RMS < 0,5 mm), sondern **Markanz** (richtiger Ausschnitt) und **Fertigbarkeit**
  (Größe/Maßstab). Genau da muss die Arbeit rein.

## 4. Empfehlung (Reihenfolge zum Bauen)

1. **Hirschsprung** — schon gebaut/geschnitten, Spitzenreiter. Fertig machen.
2. **Belchen** — ikonischer Kegel, bei kleinerem Maßstab (≈ 60 cm) sofort baubar.
3. **Triberger Wasserfälle** — perfektes Lasercut-Stufenmodell (163 m über enge Felsrinne).
4. **Schluchsee-Staumauer** — erst den Gewichtsstaumauer-Generator bauen (nächster Tool-Schritt).
5. **Ravenna-/Sauschwänzle-Viadukte, Linach** — Generatoren existieren teils schon.

## 4b. Harter Geometrie-Test für Bauwerke (`bewerter_bauwerk_geom.py`, nachgerüstet)

Der Geometrie-Juror war für Bauwerke zu weich (maß nur Gelände). Jetzt ein **harter
architektonischer Test** — mit der Kern-Einsicht, dass „Bögen" je Archetyp GEGENSÄTZLICH sind:

| Archetyp | Was „richtig" bedeutet | harter Test |
|---|---|---|
| Viadukt/Brücke | echte **Durchsichten** (Tageslicht) | Loch-Topologie der Silhouette; Füllgrad niedrig |
| Bogen-Staumauer | **Nischen** auf **massiver** Wand (hält Wasser!) | Relief-Rhythmus; darf NICHT durchsichtig sein |
| Gewichtsmauer | massiver Block | keine Fehl-Öffnungen; L:H |

Zusätzlich: Bogenzahl, Öffnungsgrad, **Regelmäßigkeit** (gap/width-CV), Proportion, Mesh.
**Bewiesen an echten STLs** — jedes richtige Modell PASS, jedes falsche FAIL:
- Ravenna→viadukt ✅ · Linach-Bogenmauer→bogenstaumauer ✅ · Schluchsee→gewichtsmauer ✅
- Kreuztests FAIL: Linach ALS Viadukt (❌ „Wand mit Nischen statt Durchsicht"), solides
  Korbbogen-STL ALS Viadukt (❌ 0 Durchsichten), massive linach_mauer ALS Bogenmauer (❌).

## 5. Offen / ehrliche Grenzen

- Nur 5 Kandidaten haben echte DGM-Daten geladen; der Rest ist katalogisiert, aber noch
  nicht durchgerechnet (DEM je Kachel nachladen → Manifest → Voting; vollautomatisierbar).
- Markanz ist eine **Geometrie-Heuristik**, kein echtes „Wiedererkennen". Sie misst Drama
  (Steilheit/Wand/Fallhöhe), nicht kulturelle Bekanntheit — bewusst, weil messbar.
- Bauwerke werden ohne Artefakt nur geschätzt; finales Fertigbarkeits-Urteil erst nach
  Generierung der echten Teile.
