# Kreisbericht quader:laube_rueck (Lauf a021633 r2)

Ehrlicher Vorbehalt: In diesem Lauf wurden KEINE neuen Fotos gezaehlt oder gemessen. Ich habe die in Vorrunde s6-R2 angenommene Aenderung
(Commit 6346443, bisher nicht in main) auf die aktuelle Basis uebernommen (objekt.json, masstabelle.json, Pruefstand `ebene_ende`, Protokoll M-6124-021),
neu gebaut/abgenommen und das Overlay angesehen.

## 1. Formbeschreibung (aus Vorrunde, Fotos 6120/6117/6175/6124/6130/6176/6206; Overlay heute selbst angesehen: 6124/6130/6176)
Laubenrueckwand = EINE ebene Wand bei n 7,28 mit Fensterpaaren, Tuer/Tor, Sitzbank davor; im Westen endet sie am Eckpfeiler (u ca. -8,85).
Formfamilie: vorhandener `quader` (Platte). Sie liegt vollstaendig in `quader:rumpf_eg` (Doppelung, bleibt wegen Druck-Zusammenhalt aktiv).
## 2. Zaehlungen
Keine (Regel 9: Teil ist glatte Platte; Fenster/Tore sind andere Bauteile).
## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| laube_rueck_west_ende (Gesamtnetz!) | 9,34 FEHLER (Vorrunde) | 8,82 OK | 8,7-9,1 | M-6124-021 |
| Wolkenbeleg laube_rueck | 0,327 (Median 0,28 m) | 0,508 (Median 0,147 m), heute gemessen | - | konvergenz_bericht |
Abnahme: `bauen_abnehmen.sh` = alle Pruefungen bestanden (1 alter Widerspruch, 44 Beobachtungen ohne Pruefung). freiraum_audit-Fehler im Worktree:
untracked SFM-AUSRICHTUNG-buendel.json fehlt (Infrastruktur, bestand schon in s6).
## 4. Overlays
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_laube_rueck_westende.jpg (gelb vorher -9,339, rot nachher -8,82; nur Westkante, 3 Fotos)
- modelle/kaufhaus_grob3/audit/seiten.jpg angesehen: Westende ohne Stummel.
## 5. Fehlerliste
- Westende u0 -8,82: trifft (6124, 6130; 6176 nicht lesbar, kein Beleg).
- Wandebene n 7,28: ungeprueft in diesem Lauf (Vorrunde M-6120-021).
- n0 7,18: ANNAHME (Einbindung fuer Druck), nicht beobachtet. Der Beleggewinn 0,33->0,51 kommt vermutlich vor allem vom Wegfall der verdeckten Rueckflaeche, nicht von besserer Form.
- Ostende u1 16,31, Oberkante z 8,0: ungeprueft.
- Sockel/Sitzbank n 7,72: fehlt im Modell.
- Pruefung west_ende misst Gesamtnetz, rumpf_eg endet ebenfalls bei -8,82: trennt Teil nicht von Rumpf.
- teile_lage_pruefen, foto_diff, teile_sichtpruefung, regression.py: nicht gelaufen.
## 6. Geaenderte Dateien
objekt.json, masstabelle.json, tools/pruefstand.py (+ebene_ende), messprotokoll/M-6124-021.*, Overlay, NICHTS_GEBRACHT.md (BS156), REZEPT (L-LR5), generierte STL/Audit-Dateien durch Neubau.
## 7. Generalisierte Lehre
Beleg-Gewinn bei einem Teil, das in einem Nachbarkoerper liegt, ist oft ein Messartefakt (verdeckte Flaechen zaehlen mit) | laube_rueck 0,33->0,51 | konvergenz_bericht sollte verdeckte Flaechen ausblenden (offen).
