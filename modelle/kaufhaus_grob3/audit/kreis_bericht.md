# Kreis r3: fensterreihe:eg1_tuer (kaufhaus_grob3, 2026-11-10)

## 1. Formbeschreibung (Stufe 0)
Fotos (angesehen): 6207 (4,7 m, Az +15, Nahfoto frontal), 6243 (7 m, Az -34), 6206 (8,7 m, Az +74, Streiflicht), 6120 (15 m, Uebersicht), d_17/d_20 (Gegenprobe). Modellpunkt vorher in alle Fotos projiziert.
- Zonen: Schwelle z 1,77 -> Tuerblatt (ein Blatt, Plankenfuge, 2 Bandbeschlaege, Klopfer) tief in der Laibung -> Schulter z ~2,77 (S-gekruemmte Steinkante), ab hier Laibungsnische 2,05 m breit mit je 3 Goldschaeften -> flacher Spitzbogen (Kaempfer ~3,92, Scheitel ~4,28) -> darueber Goldportal (Wimperg, Goldschraegen).
- Querschnitt: Wandfront n 7,28 (Tafel 7,291, Goldplaettchen 7,281); Tuerblatt n 6,772 (0,51 hinter der Wand); Goldrelief bis 7,376.
- Wiederholung: 1 Tuer, 3 Schaefte je Seite (nicht modelliert).
- Am Altmodell anders: Rechteckring (Breite 1,53) 0,12 vor der Wand, steht oberhalb der Schulter in der hohlen Nische; Nische nur 1,48 breit; Tuerblatt fehlt.
- Formfamilie: vorhandene `fensterreihe` mit freier `kontur` (keine neue Familie). Unsicher: Bogenform (ANNAHME Sinusast), Wimperg/Schaefte fehlen.

## 2. Zaehlungen
Z-6207-001, Z-6243-001 (je 1 Tuer, 2 Richtungen), bestehend Z-6120-005.

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| tuer_b3_rahmenfront (neu) | -0,12 ROT | -0,04 OK | -0,096..0 | M-6243-001/002/003 |
| Gesamt Pruefstand | 1 FEHLER (nur die neue) | alle bestanden, 1 Teilnetz, wasserdicht, Wandstaerke 0,13 | | |
Gate (Kreis): Wolkenbeleg 0,713 -> 0,990 (+0,28), Median 0,098 -> 0,034 m; Fotokanten Recall None / Praezision 0,0 unveraendert (Gitter hat dort 0 Punkte, nicht bewertbar). Gesamt-Kanten-Recall 0,696 / Praezision 0,112 unveraendert, laube_rueck Beleg 0,561 unveraendert (kein Rueckschritt).
Messungen: M-6207-001 Tuerblatt n 6,772 +-0,026 (Strahlabstand 0,016, 45 Grad; Rueckprojektion in d17, d20, 6120 trifft den Klopfer); erster Versuch Goldschaft-Fuss (Strahlabstand 0,19) verworfen und aus dem Ordner genommen; gueltig: M-6243-001 Tafelecke n 7,291, -002 Goldschraege n 7,376, -003 Goldplaettchen n 7,281; M-6207-002/003 Nischenbreite 2,05 (u 3,26..5,31), Schulter z 2,77.

## 4. Overlays (vorher | nachher)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis3_fensterreihe_eg1_tuer_6207.jpg, ..._6243.jpg, ..._6120.jpg 
(Selbst angesehen: 6207, 6243 = Nischenumriss und Bogen treffen gut; 6120 nur als Uebersicht erzeugt, nicht im Detail bewertet = ungeprueft.)

## 5. Fehlerliste
- Rahmenfront/Wandlage: trifft (Foto + Wolke).
- Nischenbreite rechts (Photo-links): trifft (6207). Links (Pillar-Seite): trifft ungefaehr, Modell ~0,05-0,1 breiter als das Gold (Messunsicherheit +-0,14).
- Bogen: Form nur ANNAHME (Sinusast); im 6207-Overlay liegt der Bogenscheitel etwas niedriger/flacher als der Steinbogen -> ungeprueft/teils trifft nicht.
- Tuerblatt (6,77): fehlt im Modell (Nische 6,98), offen (Wandstaerke, laube_rueck endet 6,83).
- Goldschaefte, Wimperg, Schwelle: nicht modelliert.
- Nischenfluegel Tiefe 0,11: nur aus Wolke, ungeprueft am Foto.

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (tiefe 0,08, kontur, neues quader:eg1_tuer_nische_fluegel), masstabelle.json (Messung, Pruefung, Beobachtung), messprotokoll M-6207-001..003, M-6243-001..003, K-6207/6243/d17/d20, Z-6207-001, Z-6243-001, Overlays, erzeugte STL/Audit-Dateien, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Beleg nach u/z/Normale zerlegen, bevor Tiefe verstellt wird (L-KR23) | Beleg 0,0 nur oben-links: Ring in hohler Nische | Diagnose-Skript (agent_scratch_kreis3/diag2.py), foto_mass |
| Triangulationspunkte nur scharf + Rueckprojektion (L-KR24) | M-6243-001 verworfen | foto_mass --tri |
| Altstand-Pruefung an gleicher Stelle messen (L-KR25) | Mess-Strahl z 3,0 -> 2,2 | pruefstand ebene_abstand |
