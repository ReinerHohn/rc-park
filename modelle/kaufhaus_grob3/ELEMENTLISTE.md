# Elementliste Grobgenerator Kaufhaus (Stand 2026-11-07)

Anzahl am Foto = nur aus Foto-Zaehlprotokollen (Regel 9, `messprotokoll/Z-*.json`, aus kaufhaus_null5 uebernommen; KEINE neue Handzaehlung in dieser Sitzung).
Anzahl im Generator = Huellen-Zaehlung der Teil-STL (generator_alt/teile/g_*.stl, Komponentenanalyse, Position entlang Fassade u) - der Generator liest keine dieser Zaehldateien (kein Selbstbezug).

| Element | Anzahl am Foto | Anzahl im Generator | Foto-Beleg | Abweichung |
|---|---|---|---|---|
| Laubenboegen Hauptfassade | 4 | 4 Boegen (u = -7.8/-2.9/2.0/7.0 m) + 5 Pfeiler | Z-004-001, Z-004-003 (Foto 004, 4 Boegen zwischen 5 Pfeilern); Foto 004 Overlay: Bogenform stimmt, Bogenlaibung gelb (fehlt) | keine |
| Grosse Fenster OG zwischen den Erkern | 5 | 5 (u = -7.1/-3.8/-0.4/2.9/6.3 m) | Z-004-002 (5), Z-043-001 (5) | keine |
| Erker | 2 (Ecken links/rechts) | 2 (u = -10.3 / 9.4 m) | Foto 004/043 sichtbar | keine |
| Erkerfenster je Erker | NICHT gezaehlt | 8 je Erker (Fensterhuellen u = -11.3..-9.2 bzw. 8.4..10.5) | OFFEN: keine Foto-Zaehlung vorhanden (Regel 9) | UNGEPRUEFT - Nutzer/Zaehlprotokoll noetig |
| Staffelgiebel Stufen je Flanke | 8 (Z-042-001, Z-075-001..004; nur 'automatisch, Saegezahn', keine Handzaehlung) | 2 Giebelkoerper mit nur 2 Horizontalebenen (z 10.85 / 12.26) = KEINE 8 Stufen; Krabben 42 Huellen | Z-042-001, Z-075-*; Foto 004/043 Overlay: Giebelspitzen reichen am Foto ca. 100 px (~2 m) ueber die Modellkante | **ABWEICHUNG** Giebel = einfache Prismen, Stufen fehlen, Spitze ca. 2-3 m zu niedrig |
| Gauben | NICHT gezaehlt | 10 (2 Hoehenreihen, 5 je Seite) | Foto 004 Dach: Gauben sichtbar, Zahl nicht gezaehlt | UNGEPRUEFT |
| Tuermchen/Helme | 2 (Erkerhelme links/rechts) | 2 (helm_gruen u = -10.3 / 9.4) | Foto 004/043 | keine |
| Figuren (Statuen) | NICHT gezaehlt (Foto 004: ca. 4 in der Galerie sichtbar) | siehe g_statuen (32 Huellen = Teile, nicht Figuren) | Foto 004 | UNGEPRUEFT |
| Galerie/Balkonband | 1 durchgehend | 2 Platten (z 6.2 / 6.9) | Foto 004 | zu pruefen |
| Dachziegel/-muster/-rauten | Foto: Ziegelmuster, kein Rautenmuster erkennbar | dachziegel 3120 Huellen, dachrauten 72 | Foto 004 Overlay: rote Ziegelkanten ohne Fotokante | **ABWEICHUNG** erfundene Dachmusterkanten (BS56: Entfernen verbessert 16/20 Fotos) |
| Gesamthoehe | Spitze 20.24-20.46 m (Triangulation, nicht neu) | Teile 16.45 m, Wolke 19.33 m | NICHTS_GEBRACHT BS72 | **ABWEICHUNG** ca. 2-3 m zu niedrig |

Hinweis: Foto-Zaehlungen in dieser Sitzung nicht neu erhoben; fuer die UNGEPRUEFT-Zeilen ist `tools/foto_zaehlung.py modelle/kaufhaus_grob/objekt.json <foto> --punkt ...` (Pixelpunkte) noetig.
