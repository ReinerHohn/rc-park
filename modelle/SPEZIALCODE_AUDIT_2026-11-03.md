# Spezialcode-Audit (2026-11-03, Nutzerauftrag "Suche nach Spezialcode. Ich will generalisieren.")

Gelesen: `modelle/martinstor_v4_gen.py` (416 Zeilen) ganz, `tools/bauteile.py`, Stichprobe `tools/*.py` (56 Werkzeuge nennen "martinstor").
Massstab: **Spezialcode** = Zahl/Anzahl/Form im Code statt in Daten (masse.json/fassade.json/Profil) ODER objektspezifische Logik, die eine Bibliothek allgemein koennte.

## A. Generator: Handkonstanten und Einzelbauteile (Prioritaet = Sichtbarkeit x Fehlerrisiko)
| # | Zeilen | Element | Was ist speziell | Generalisierung |
|---|---|---|---|---|
| 1 | 196-206 | Zinnenkranz | **Anzahl 5 im Code** (Regel 9/CB: Zahl nur aus Foto-Zaehlung), Zinnenmasse 0,8/1,0/0,35, Holzkonsolen | `bauteile.zinnenkranz(n aus Z-Protokoll, Masse aus Wolkenband)`, n je Seite aus masse.json |
| 2 | 321-379 | Ecktuermchen-Altpfad (ohne Wolkenprofil) | komplette Handkonstruktion (Fenster 2 Zonen, X-Schlitze 38 Grad, Leisten, Helm OR*0,86) - laeuft im Nullstart-Erstlauf `generator0` | loeschen; Erstlauf nutzt `baender_rundkoerper` mit Rueckfallbaendern aus masse.json |
| 3 | 128-145 | Torbogen | 15 Keilsteine, Rahmen 0,95/0,5/1,15/0,6 im Code | `bauteile.rundbogen_tor(breite, kaempfer, n_keil aus Foto)` |
| 4 | 105-115 | Eckturm NW | Hoehen 10,6/0,25/3,3/13,9, Fenster 4,0/8,0 im Code | `baender_rundkoerper` + Profil (wie Ecktuermchen) |
| 5 | 161-163 | Fenster Ost/West 6,5/10,5 m | umgeht fassade.json | in fassade.json |
| 6 | 147-160 | Inschrifttafel, Adler | Lage/Groesse/5 Zeilen, Adler aus 5 Kugeln | `bauteile.relieftafel(daten)`, Werte in fassade.json |
| 7 | 175-188 | Giebel ueber der Uhr | Exponent 2,6, Spannweite UR+1, 12 Marken | Profilkurve als Daten (gemessen M-031) |
| 8 | 119-122 | Bruchstein-Aussparungen | feste Zonen 4,1/9,4/2,6/10,7 | aus Torbogen-/Fensterlage ableiten |
| 9 | 260-281 | Kreuzarme, Goldkugeln, Knauf, Nadel | 0,24/0,14/0,34/0,10/0,04 im Code | masse.json |
| 10 | 226-234 | Schallarkaden-Rahmen | 0,3/0,12 Rahmen, Ost/West = ANNAHME Kopie | Rahmen als Mass; Ost/West fotografieren |
| 11 | 296, 305-306 | zum_turm 0,3; Tuermchenfenster 0,45x1,0 bei +1,5 | im Code | Parameter/Profil |
| 12 | 315-319 | Tuermchenachse symmetrisch (+-tief, +-quer) | Wolke: (-3,83/+4,19), (-3,78/-4,50), r 1,65 statt 1,55 | Kreisfit JE Tuermchen (wolke_baender) |

## B. Bibliothek `bauteile.py`: ANNAHMEN im Code
`baender_rundkoerper`: Wand 0,2, Hohlraum 0,5 hinter Achse, Sturz 0,08, Mindestpfeiler 0,12, Schlitzwinkel 38 Grad, 8 Traufkonsolen, Leisten 0,12 -> als Parameter mit Default + Herkunft in die Signatur/Daten.

## C. Werkzeuge mit Martinstor-Spezialwissen
- `foto_silhouette_gpu.py` (Fotoliste + ROI je Foto 042/043/044 im Code), `foto_dachtest_gpu.py`/`foto_profil_gpu.py` (Standardfotos 042-044), `kanten_richtung.py` (030/031/040/041) -> aus objekt.json lesen.
- Masstabelle: Messungen mit festen Koordinaten (z. B. quer 4,42, z 34,27) -> wie `_band_fenster` aus Profilen ableiten (Register CG).

## D. Reihenfolge (Vorschlag)
1 Zinnen (Regelverstoss Anzahl), 12 Tuermchenachse je Tuermchen (sichtbarer Versatz), 2 Altpfad loeschen, 3/4 Tor + Eckturm in Bibliothek, Rest nachziehen.
Jeder Schritt: Pruefung rot -> Bibliothek -> bauen_abnehmen -> Regression -> Nullstart.
