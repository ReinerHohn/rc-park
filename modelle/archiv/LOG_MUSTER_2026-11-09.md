# LOG muster_fit / kanten_tor 2026-11-09
- tools/muster_fit.py (Familien fenster, gaube; rotation/konsole/pfeiler nur Tor-Parameteransicht) + tools/kanten_tor.py (Kanten-Tor).
- Fenster: 5 Gruppen x 3 Lichter, Periode 3,9663 (Plateau 3,958..3,973), --synth fenster BESTANDEN.
- Gaube: Dachebene RANSAC, 5 Blobs, --synth gaube BESTANDEN (Fehler w 0,028 h1 0,006 m 0,001; Synth ohne Dachpunkte unter der Gaube). Echte Formfamilie offen.
- kanten_tor --synth: Fall 1 (Mittel-Kaempfer hoeher) und 2 (Wolke leer) BESTANDEN, Fall 3 (Wolke widerspricht) FEHLGESCHLAGEN.
- Offen: Vorhangbogen-Koepfe je Licht (Kopf derzeit Giebellinien), M-6120-Regression, Baluster 68/0,306 erneut, Konsole/Pfeiler Synth, Overlays kanten_tor_*_entwurf.jpg ungesehen.

## Runde 2 (Zusatzauftrag)
- Synth Fall 3 repariert (Halbwertsbreite statt Plateau95, Signifikanz bei 5 k MAD gedeckelt): alle 3 Faelle BESTANDEN.
- Datenlage-Fehler: Fotoauswahl vor Sichtbarkeit begrenzt (30 naechste Fotos je Instanz, danach Z-Puffer) -> Sohlbank 'min 1/median 3'. Nach Fix 12-16 sehende Fotos. Z-Puffer-Median z-zb ~2 m ist echte Verdeckung durch die Konsolenreihe, kein Toleranzfehler. Sohlbank bleibt dennoch OFFEN (Kurven nicht signifikant).
- tor_json: Fenster-Korrekturen immer je_licht[L].z_*; Konflikt (zwei Werte auf einem Pfad) -> nicht schreiben, offen; Untergruppen die nach Instanz statt nach Licht trennen brauchen je_instanz (Format fehlt).
- M-6120-Regression (tools/muster_regression.py): Rueckwandebene aus der Wolke 7,29 (Handebene 6,54 +-0,3 war 0,75 m daneben); Handpixel auf 7,29 umgerechnet. 2 von 9 Kanten innerhalb 0,06 m (Fensterkopf +0,004, Fensterbank +0,015), Rest OFFEN mit Grund (Wolke 0 Punkte im Kasten bzw. Widerspruch).
- Baluster-Tor: OFFEN (keine Quelle trennscharf, 4-px-Baluster auf 1500-px-Karten); falsche Korrektur +0,117 wird nicht mehr geschrieben.
- Vorhangbogen je Licht als Parabel aus Wolkenspalten (Aussenlichter steigen von Aussenpfosten 12,58 zum Innenpfosten 13,40, Mittellicht flach 13,35); Overlay *_entwurf bleibt (16 von 39 Lichtern Umriss-abgenommen, Elemente nicht einzeln).
- Overlay 6261: 5 Hauptfassadenfenster gruen, die Fortsetzung im Takt in Nachbarhaus/Erker/Turm rot = korrekt verworfen.

## Runde 3
- Mindest-Pixelbreite (TOR_MINPX=9 px, `sweep(mass_m=)`): UNGEPRUEFT statt OFFEN. Baluster liegt mit 0,144 m = 25 px (Vollbild-Gradient, 174 px/m) darueber -> Tor bleibt OFFEN wegen schwachem Signal (Wolke 3,0 MAD, Einigkeit 28 %; Fotos 2,3 MAD, 31 %). Baluster 68 / Periode 0,30623 stammen aus baluster_abgenommen.json (Tor-Eingabe), kein Neufit in muster_fit.
- zuruecklesen kt_koerper4_TOR.json auf Kopie ($D/muster/koerper_tor): 2 Korrekturen (je_licht[1].z_kaempfer 12,279; je_licht[0].z_scheitel 12,704), koerper_v11.py bauen -> wasserdicht, 0 offene Kanten, STL $D/muster/koerper_tor/koerper_v11.stl.
- Fenster: Fehlerliste je Licht und Element (Sohle, Pfosten l/r, Kaempfer, Bogen) in muster_fenster_fehlerliste.json. Abgenommene Gruppen: Kaempfer 15/15, Pfosten 14/15, Bogen 8/15, Sohle 0/15 -> 24 Elemente ohne Fotobeleg, Overlay bleibt *_entwurf. Sohle: z-Sweep +-0,3 und +0,3..0,9 ohne klares Maximum (Kantenanteil 0,35-0,41 ueberall), Ursache offen.
- Gauben: Fotoauswahl-Fehler (Rahmen-n zeigt hinter das Haus, Vorderseitenbedingung falsch herum) behoben: 10 Fotos je Gaube plus od_00/od_01. Kantentest gauben_unterscheidung.py: OFFEN (First 1/5, Giebel 3/5, Schleppkante 1/5, Wange 0/5, Frontunterkante 2/5) -> Test zu unempfindlich, Synth fehlt. gaube3: schlepp RMS 0,036 / satteldach 0,037 (Wolke trennt nicht). Foto-Tor 0/5 auf Stabilitaetskarten: Lage im Overlay 6261 stimmt, Umrisse zu gross (Front 1,4 m), Dachflaeche dunkel -> Karten ohne Kanten.
