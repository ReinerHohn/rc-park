# Kreis a040948 r1 – quader:gesims (Traufgesims)

## 1. Formbeschreibung (Stufe 0)
Fotos: ip_IMG_6161 (Nah/frontal), an_handy_04 (Uebersicht), an_handy_18 (schraeg), ip_IMG_6145, b_handy_b_17 (nur grob).
Zonen von unten: glatte rote Wand → rote Schraege mit zwei Goldleisten (Fuss z ~14,33) → gruene Kupfer-Haengerinne (Lippe z ~14,8) → Dachschiefer.
Querschnitt: Schraege, 0,32 m Ausladung ueber 0,5 m Hoehe, entlang u -8,8..17,15 gerade. Wiederholungen: keine (Konsolen/Wasserspeier sind eigene Teile). Das Gesims ist KEIN Quader (Altmodell n 12,62..13,08 x z 14,1..14,7; sein Unterrand lag in Overlay 6161/04/18 auf glatter Wand).
Formfamilie: vorhandenes `quader` mit generischem `profil` (Querschnitt n,z entlang u extrudiert, baukasten_gen.py). Uebernommen aus verworfenem r3-Entwurf, gezielt verbessert (Pruefer-Kritik: Unterkante 0,1 m zu tief, Gate/8b).

## 2. Zaehlungen
Keine Zaehlmerkmale (Z-Protokoll entfaellt). Messprotokolle M-6161-017..021 (aus r3 uebernommen, Wolkenprofil lot2).

## 3. Pruefungen (masstabelle.json, 3 neue gesims_front_z14_35/55/78)
| Pruefung | Altstand | Neu | Soll | Quelle |
|---|---|---|---|---|
| Vorderflaeche z 14,35 | -0,08 FEHLER | 0,30 | 0,25..0,35 | Wolke lot2, M-6161-020 |
| z 14,55 | -0,08 FEHLER | 0,18 | 0,13..0,23 | Wolke, M-6161-018/019 |
| z 14,78 | 0,41 FEHLER | 0,07 | 0,03..0,13 | Wolke, M-6161-017 |
(z-14,15-Pruefung des r3 verworfen: Gesims beginnt jetzt bei 14,32.)
Abnahme: `bauen_abnehmen.sh` „alle Pruefungen bestanden“ (1 Teilnetz, wasserdicht). `regression.py --pruefen`: identisch. 
Gate (konvergenz_bericht, Teil quader__gesims): Beleg 0,465 → 0,637; Fotokanten Recall 0,507 → 0,485, Praezision 0,335 → 0,403, F1 0,403 → 0,441; Guete 0,434 → 0,536 (+0,10, Gate ≥0,05, keine Groesse faellt). Gesamt-Kanten 0,6471/0,0773 (vorher 0,6471/0,0765). 
Varianten (Zwischenlaeufe, nur Fakten): r3-Profil exakt Guete 0,440; Rueckseite 12,58 + 14,29/14,32: 0,464–0,474; Rueckseite 12,62 (gewaehlt): 0,536.
Hinweis: die Zeile „r1_vorher“ in konvergenz.jsonl ging durch ein versehentliches `git checkout` verloren; Vorher-Werte stammen aus dem ersten Messlauf dieser Sitzung (oben) und der Befundzeile.

## 4. Overlays (rot neu, blau alt)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_gesims_ip_IMG_6161.jpg
.../rundekreis1_gesims_an_handy_2026-11-06_handy_04.jpg
.../rundekreis1_gesims_an_handy_2026-11-06_handy_18.jpg
.../rundekreis1_gesims_ip_IMG_6145.jpg
.../rundekreis1_gesims_an_handy_2026-11-06_b_handy_b_17.jpg
Selbst angesehen: 6161, handy_04, handy_18 (rote Linien auf Goldleiste/Schraege/Rinne, blauer Altkasten auf glatter Wand). 6145 und b_17 erzeugt, nicht einzeln angesehen.

## 5. Fehlerliste
- Schraege u -7..14: trifft (3 Fotos angesehen); Wolke Median 0,078 m.
- Unterkante z 14,32: trifft in 6161/04/18 optisch, Pixelgenauigkeit nicht gemessen.
- Gutterlippe z 14,82 (Rinne z 14,56..14,82 als Teil des Profils): trifft grob; Rinnenrundung/Bauch, Wasserspeier, Dachgitter nicht modelliert.
- Enden u < -8 und > 14,6: ungeprueft (ANNAHME Rumpfenden, Erker verdeckt).
- Rueckseite buendig n 12,62 (eingebettet): nicht sichtbar, unpruefbar.
- teile_lage_pruefen: quader:gesims Median 0,10 m, 3 % > 0,5 m (ok). foto_diff 6161: Treffer 1 (Fotokante ohne Modell, ganze Fassade/Fenster, 1389 m) liegt nicht spezifisch am Gesims; Treffer 2-10 ausserhalb. fehlteile_finden lief in der Abnahme, Treffer am Gesims keine. teile_sichtpruefung: nicht gelaufen. freiraum_audit meldet weiter FEHLER (vorbestehend, am Altstand identisch).
- seiten.jpg angesehen: unauffaellig (Gesims in dieser Aufloesung nicht erkennbar).

## 6. Geaenderte Dateien
tools/baukasten_gen.py (quader `profil`), tools/gesims_overlay.py (neu), modelle/kaufhaus_grob3/objekt.json, masstabelle.json (3 Pruefungen, 3 Messgroessen, Beobachtung), messprotokoll/M-6161-017..021, audit/gitter_generator/rundekreis1_gesims_*, konvergenz.jsonl, regenerierte STL/Audit-Dateien, NICHTS_GEBRACHT, REZEPT (L-GS4). Kein Commit.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug
Rueckkanten eines Profilteils im Nachbarkoerper zaehlen als unbelegte Formkanten; Rueckseite buendig statt eingebettet | Guete 0,44 → 0,54 | baukasten_gen `profil`, konvergenz_bericht --trocken --json_aus (Varianten testen vor der Abnahme)
Vorher-Zeilen in konvergenz.jsonl nie per git checkout zuruecksetzen | Verlust der Vorher-Zeile | –
