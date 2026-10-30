# ⭐ LASER-KALIBRIERUNG Sculpfun S9 — am echten Gerät erkämpft (2026-10-19)

**EXTREM WICHTIG — nicht verlieren.** Diese Werte sind am echten S9 mit dem echten Material
getestet (Steck-Test + Lehre, vom User bestätigt). Ab hier gelten sie als Standard.

## Material
- **4 mm Pappelsperrholz**, plan, fixiert. Air Assist AN. Fokus vor jedem Materialwechsel neu (scharfe Linie).

## Schnitt (Cut) — brennt sauber durch
| Parameter | Wert |
|---|---|
| Leistung | **100 %** (S1000) |
| Vorschub | **300 mm/min** |
| Durchgänge | **4×** |

→ Bei Resten die nicht ganz durch sind: **langsamer (250 mm/min)** statt mehr Pässe (größenstabiler).
Große/lange Teile brauchen evtl. +1 Pass (Wärme-Effekt bei langen Strecken).

## Schlitz / Steck-Passform — der kritische Wert
- **Schlitzbreite nominal 3,6 mm** für 4-mm-Material → im Generator **`--fit -0.4`** (slotw = thickness 4 − 0,4 = 3,6).
- **Warum:** der Laser-**Kerf weitet den Schlitz auf ~4,0 mm** → die 4-mm-Rippe sitzt dann **stramm** (hält von selbst).
  Mit 4,15 mm (alter Default) war es **viel zu locker**. **Kerf ≈ 0,4 mm** bei diesem Material + 4 Pässen.
- Getestet mit Breiten-Lehre 3,4/3,6/3,8/4,0/4,2 → **3,6 greift**.

## ⭐ 3 mm Pappelsperr + glueless Steck-Joint (2026-10-19, am Gerät erkämpft)
Wechsel auf **3 mm** (statt 4 mm) für den Rahmen → **halbe Schnittzeit**.
- **Schnitt: 100 % / 300 mm/min / nur 2 DURCHGÄNGE** (bestätigt: Pass-Test + 1-vs-2-Vergleich; 1× reicht nicht, 2× sauber durch).
- **Steck-Joint für Rippen-Segmente (hält OHNE Kleber):**
  - **GERADE FINGER, KEIN Schwalbenschwanz/Taper!** Ein Dovetail lässt sich geradeaus **nicht** zusammenstecken (breite Spitze passt nie durch den schmalen Hals) → „passt gar nichts". Nur gerade Finger (`finger_split`) schieben sich zusammen + halten per Reibung.
  - **Teile GETRENNT mit Lücke** erzeugen (nicht überlappend in Steck-Position!) und **jedes einzeln um K nach außen** kompensieren (`buffer(+K, join_style=2)`). Übereinander-legen + Buffer = Konturen überlappen = Laser-Murks.
  - **Kerf-Ausgleich K ≈ 0,09 mm** (`truss_kit --kerf 0.09`). Fein-Sweep: K06 zu locker, **K09 passt**, K12/K15 zu stramm. ACHTUNG: **Kerf schwankt ~0,05 mm/Lauf** (Fokus/Ruß/Brettstelle) → lieber minimal lockerer (zu stramm = geht gar nicht rein).
- **Kalibrier-Tool:** `tools/laser_calib.py --mode pass|fit` (Quadrate/Schlitze, graviert beschriftet). Steck-Tests: gerade Finger-Paare getrennt, K-Sweep.
- Streben-SCHLITZ-`--fit` fürs 3 mm noch separat prüfen (Kerf ~0,3 → eher ~-0,15 statt der 4mm--0.4).

## Gravur (Beschriftung) — kräftig lesbar
| Parameter | Wert |
|---|---|
| Leistung | **85 %** (S850) |
| Vorschub | **1200 mm/min** |
| Durchgänge | 1 (läuft automatisch ZUERST) |
| Schrifthöhe | **~5 mm**, aufs Teil begrenzt (nie über Rand/in Schlitz) |

→ 20 %@3000 war unsichtbar, 75 %@1500 lesbar aber schwach → **85 %@1200** = kräftig.
Vorschub kleiner = kräftiger (ohne durchzuschneiden, solange 1 Pass).

## Frame / Nullpunkt
- **Framen** zum Ausrichten: **2 % Leistung** (`--frame-power 2`, schneidet nicht).
- **Nullpunkt = unten-links** (vordere-linke Ecke, bei dir). **+X nach rechts, +Y nach hinten.**
  Kopf an die vordere-linke Ecke der frischen Fläche → Schnitt wächst nach rechts+hinten.

## Die fertigen Befehle MIT diesen Werten
```bash
# Gerüst (Schlitz 3,6 + kleine Schrift)
python3 tools/terrain_eggcrate.py --dem daten/hoellental/dgm025_full.npy \
  --mm 1.5625 --nscale 6.25 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 22 --ny 18 --thickness 4 --base 12 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0.6 --min-gap 7 --fit -0.4 \
  --tunnel --track daten/hoellental/hoellental_track.npy --split-len 200 --finger 12 --gcode \
  --out modelle/hirschsprung_geruest

# Schneidplan Zonen (Cut 100%/300/4 + Gravur 85%/1200)
python3 tools/laser_zone_nest.py modelle/hirschsprung_geruest \
  --sheet 1200x600 --machine 410x400 --gcode --fdepth 3 --margin 2 \
  --eng-power 85 --eng-feed 1200 --out modelle/hirschsprung_geruest/zonen

# Senden (framen dann schneiden)
python3 tools/grbl_send.py --frame-only <datei.gcode>   # ausrichten (2%)
python3 tools/grbl_send.py --yes --no-frame <datei.gcode>  # schneiden
```

## Sender-Regeln (wichtig, teuer gelernt)
- **Während ein Cut läuft: Port NICHT ein zweites Mal öffnen** (DTR-Reset würde GRBL resetten/Job abbrechen).
  Fortschritt = die %-Ausgabe des Senders. Status `?` nur abfragen wenn NICHTS streamt.
- `grbl_send.py --yes` = ohne ENTER-Rückfrage (für Hintergrund-Lauf; sonst EOFError).
- S9 enumeriert nicht über den HP-Dock bei Hänger → **kompletter Netz-Drain** (Stecker ziehen, 30–60 s), direkt am Laptop.

Siehe `REPRODUKTION.md`, Memory `laser-sculpfun-s9`.
