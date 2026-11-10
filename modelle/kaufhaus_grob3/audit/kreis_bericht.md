# Kreis a053353 r1 - quader:gesims

## 1. Formbeschreibung (Stufe 0)
Fotos: 6161 (Uebersicht frontal), 6145 (schraeg West-Haelfte), 6115/b_03 (Naehe Erkerhelm), handy_18 (Nahfoto). Zonen von unten: glatte Wand -> rote Schraege mit Goldleisten (n 12,62->12,94, z 14,35->14,82) -> gruene Kupferrinne -> Dach. Querschnitt Profilleiste, Wiederholung keine, laeuft zwischen den Erkerhelmen und verschwindet dort im Helm. Formfamilie: vorhandenes quader mit `profil` (baukasten_gen), keine neue Familie noetig.
Aenderung am Altmodell: Enden liefen ca. 1 m (West) / 2,4 m (Ost) in die Helme hinein, Fuss lag laut Gitter/Pruefer zu tief.

## 2. Zaehlungen
Keine (Teil hat keine zaehlbaren Elemente); kein Z-Protokoll.

## 3. Pruefungen / Gate (konvergenz_bericht --teile_dir, Teil quader__gesims)
| Groesse | vorher | nachher |
|---|---|---|
| Wolkenbeleg | 0,632 | 0,691 |
| Fotokanten Recall | 0,484 | 0,480 |
| Fotokanten Praezision | 0,403 | 0,540 |
| Mittel Beleg/F1 | 0,536 | 0,600 (+0,064) |
Gate (>= +0,05, nichts > 0,02 gefallen): erfuellt. Bestehende gesims_front_z14_35/55/78 gruen (Sollwerte unveraendert). Neue rote Vorher-Pruefung NICHT moeglich: Pruefstand misst das Gesamtmodell, die Endkuerzung liegt im Helm (union-neutral, trimesh.contains: West 0,096 m3 und Ost 14,8-16,3 0,153 m3 zu 100 % im Helm). `tools/bauen_abnehmen.sh`: alle Pruefungen bestanden. Werkzeuge nicht geaendert, daher regression.py nicht noetig.

## 4. Overlays
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_gesims_{vorher,nachher}_{ip_IMG_6161,ip_IMG_6145,an_handy_2026-11-06_handy_18,an_handy_2026-11-06_b_handy_b_03,ip_IMG_6115}.jpg

## 5. Fehlerliste
- Enden im Helm (West -7,8, Ost 14,8): trifft (6161, 6115 selbst angesehen).
- Oberkante/Lippe, Schraege: trifft in 6161, 6145.
- Unterkante: ungefaehr (+-0,05 m); Widerspruch Foto-Messung 14,33-14,36 gegen Gitter 14,40-14,45 offen, nicht gemittelt.
- Stummel u 16,3-17,15 (ausserhalb Helm, 0,057 m3) entfernt = ANNAHME, nicht von Osten geprueft.
- Rinnenrundung, Wasserspeier, Dachgitter nicht modelliert. teile_lage_pruefen: Gesims Median 0,08 m. fehlteile: kein Treffer am Gesims. teile_sichtpruefung nicht gelaufen. freiraum_audit-Fehler (fehlende SFM-AUSRICHTUNG-buendig.json) Altfehler.

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (gesims u0/u1/z0/profil, werte_quellen, historie), masstabelle.json (beobachtungen_offen), modelle/NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md (L-GS5), automatisch neu gebaute STL/audit-Dateien, Overlays. Nichts committet.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug: Enden, die vollstaendig in einem Nachbarkoerper liegen, per Containment-Test kuerzen (druckneutral) | quader:gesims +0,064 | trimesh.contains + konvergenz_bericht.
