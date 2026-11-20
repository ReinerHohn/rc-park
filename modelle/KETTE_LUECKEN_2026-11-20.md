# Kette-Luecken 20.11.2026: Faehigkeiten, die nicht in die Kette fliessen (ohne Vorbauten/Galerie/Vordach)
Nur gelesen. Zeilennummern gelten fuer den Stand 20.11. nachmittags; gesamtkette.py und bauteile.py werden gerade von der Hauptsitzung bearbeitet, die Zeilen verschieben sich (deshalb "~").
Rangliste nach dem, was man am Ende im Modell sieht, dann nach Aufwand.

## A. Kettenergebnis wird gerechnet, aber nicht gebaut (Sackgassen) - belegt
1. AUSSENFENSTER aus dem Wandbild. Was fehlt: Die Stufe bauplan rechnet fuer die Aussenwaende Umriss, Stege und gemessene Tiefe jeder Oeffnung (gesamtkette.py ~Z.411 -> audit/oeffnungen_aussen.json). Die Vorlage baut die Aussenfenster aber weiter als Rechtecknische aus fenster_auto.json (objekt_anlegen.py Z.69-71 -> bauteile.fenster_aus_json Z.183-197, Beleg-Hinweis "Nischentiefe und Rahmenbreiten ANNAHME"). oeffnungen_aussen.json liest sie nur fuer laube_aus_wandbild (Z.81-84, nur wenn es innenwaende gibt) und fuer die Rueckwandtiefe (rueckwand_tiefe.py).
   Von Hand: schwab_v3_gen.py Z.114-123 (Rundbogenfenster: Blendnische, Oeffnung, Sohlbank); kaufhaus_gk_gen.py Z.84-88 (form_aus_wandbild.teil: Umriss, Pfosten, Gewaendestufen).
   Vorhanden: bauteile.oeffnungen_aus_wandbild (Z.223, baut Umriss und Stege); form_aus_wandbild.py (Z.621 teil(), dazu Gewaendeprofil). Keine Stufe schreibt form_*.npz.
   Kleinster Einbau: in der Vorlage nach fenster_aus_json die Zeile oeffnungen_aus_wandbild(koerper, audit/oeffnungen_aussen.json) fuer die Aussenwaende; Rechtecke aus fenster_auto nur dort, wo das Wandbild keine Oeffnung hat.
   Risiko: Fenster doppelt geschnitten. Schwabentor-1120: Tiefe 0 ergab 'flach', dazu falsche Kaesten (Commit ed80cd3a3). Das Tor ncc_min und 'flach wird nicht gebaut' fangen das ab, dann bleibt die Wand zu statt eines erfundenen Fensters. Fuer die Sohlbank gibt es noch keine Funktion.
2. MONO-FEINRELIEF. Die Stufe mono rechnet <wand>_mono.npz (Depth Anything, GPU). Die Notiz sagt selbst: "fassaden_kette.anbauen setzt <wand>_mono.npz noch NICHT ein (Generator von Hand ...)" (gesamtkette.py ~Z.378). anbauen() (fassaden_kette.py Z.253) kennt kein _mono.
   Von Hand: schwab_v3_gen.py Z.85-93 sowie Sued Z.213-215 und West Z.246 (relief_koerper(..., trend=True, rand_auslauf=False), dazu null_felder).
   Einbau: in anbauen(): wenn w["mono"]["datei"] gesetzt ist, relief_einsatz.koerper(mono, trend=True, rand_auslauf=False) setzen und das Feld im groben Relief als tief_felder ausnehmen. Folge im Modell: Bossen, Quader und Sockel unter 10 m bleiben sonst Netzbrei. Aufwand klein.
   Risiko: Doppelrelief. Das Korrelationstor (>= 0,2) besteht schon.
3. FEHLENDE FOTOKANTEN. kantenstufe.py schreibt fehlende_kanten_haufen (Z.15/Z.116, "Arbeitsliste fuer Generator-Features (kanten_features.py --sweep)") und sweep.npz. Beides liest nur die Bewertung (grep: kein weiterer Leser).
   Die Werkzeuge aus dem Skill linien-features (kanten_features.py, features_in_objekt.py) sind keine Stufe. Damit wird die KERNMETHODE "Form = Fotokanten" in der Kette nur gemessen, nicht gebaut.
   Folge: Gesimse, Baender, Lisenen und Rippen fehlen. Einbau: Teilstufe nach 'kanten': Haufen -> kanten_features --sweep -> features_in_objekt. Die Vorlage hat aber keinen Leser fuer Pfade (das Format kommt aus baukasten_gen). Aufwand hoch, Risiko Rauschen (der Skill verlangt Stabilkarten).
4. BEFUNDE OHNE ABARBEITER. bauen_abnehmen.sh Z.56-57 (foto_breitenprofil --eintragen, fehlteile_finden FEHLT/ERFUNDEN) traegt beobachtungen_offen ein, aber keine Stufe arbeitet sie ab. Offen sind: schwab_v3 37, kaufhaus_gk2 7, schwabentor-1120 3. PIPELINE_FASSADEN.md Z.271 nennt das schon ("Hinweise ... nicht abgearbeitet").
   Kein Modellteil direkt, aber das ist der Entdecker fuer alles unten. Einbau: Notiz in gesamtkette mit Anzahl und Ort jeder Beobachtung (rot ab n > 0).
5. ERKENNERKLASSEN, DIE NIEMAND NUTZT. fassade_parsing.py Z.25-32 erkennt 'gaube', 'balkon' und 'figur'. Verbraucht werden nur fenster, bogen und tuer (fenster_aus_parsing Z.72; oeffnungen_wandbild Z.6: "Andere Klassen (gaube, figur ...) werden nicht benutzt").
   Funktionen dafuer gibt es: bauteile.schleppgaube Z.519, balkon Z.440, figur Z.648. Die Messwerkzeuge gauben_fit, gauben_tri, wolke_gauben_messen und wolke_balkon_messen kommen in keiner Stufe vor.
   Folge: Gauben fehlen auf dem Dach (gut sichtbar). Balkon gehoert zum Vorbau-Sweep der Hauptsitzung. Einbau Gaube: Kasten auf der Dachebene -> Masse aus dem Wandbild/Sweep -> schleppgaube. Aufwand mittel bis hoch.

## B. Hand-Faehigkeiten, die die Vorlage nie aufruft - belegt
6. BAUTEILE_FOTO-BLOCK. kaufhaus_gk_gen.py Z.36-100 liest objekt.json "bauteile_foto" schon datengetrieben (laube, staffelgiebel, schleppgaube, erker_polygon, schindeln, saeule, balkon, vorhangbogen_fenster, figur, baldachin, form_wandbild). Die Vorlage objekt_anlegen.py Z.51-115 enthaelt den Block nicht, und kein Werkzeug schreibt bauteile_foto (grep tools: 0 Treffer).
   Kleinster Einbau: Block 1:1 in die Vorlage. Ohne Daten tut er nichts (Risiko klein, Reihenfolge laube -> aushoehlen -> Rest beachten). Danach kann jede Bauteil-Runde ihre Masse ohne eigenen Generator einbringen. Schreiber automatisch: siehe 5.
7. RUNDE BAUTEILE (Treppenturm, Ecktuermchen). schwab_v3_gen.py Z.271-290 (Zylinder plus Haube als Rotationsprofil TT_PROF von Hand, Oeffnungen aus der Abwicklung); martinstor_v4_gen.py Z.307-334 (baender_rundkoerper + wolke_baender).
   Vorhanden: fassade_zylinder.py (Abwicklung, findet Oeffnungen), bauteile.zylinder_oeffnungen Z.328, zylinder_mass.py, helm_profil_wolke.py, helm_silhouette_foto.py, baukasten_gen @bauteil zylinder/helm_geschweift. Nichts davon steht in der Kette; fassade_ortho kennt nur Ebenen.
   PIPELINE_FASSADEN.md Z.277 "NAECHSTER SCHRITT ... als Zylinder-Schnitte in den Generator" und Z.152 "Treppenturm mit Haube (Rotationsprofil) ... nicht generisch".
   Folge: Der Turm bleibt ein flacher LoD2-Klotz (schwab_v3 Z.271: "LoD2-Nebenteil D-foermig, flach"). Einbau: LoD2-Teil mit kreisfoermigem Grundriss (Kreisfit der Wolke = Lage) -> fassade_zylinder --fotos auto -> zylinder_oeffnungen; Haube aus dem Silhouettenprofil. Aufwand hoch.
8. LATERNE, DACHREITER, KNAUF. schwab_v3_gen.py Z.183-192 (Laterne mit Zwiebelhaube, Profil von Hand); martinstor_v4_gen.py Z.277-285 (Dachreiter, Mast, Knauf, Nadel). Eine Funktion in bauteile.py fehlt (PIPELINE_FASSADEN Z.152). dach_vermessen fittet nur Flaechen >= 3 m.
   Folge: Spitze und Silhouette fehlen. Einbau: Profil r(z) ueber dem First aus den Himmelsmasken (Weg wie helm_silhouette_foto) -> neue generische Funktion rotationskoerper(profil, n_ecken).
   ANNAHME: umriss_tor (Stufe fenster, Z.~396) meldet eine fehlende Laterne als Beobachtung - nicht geprueft.
9. UHR. Es gibt zwei Bauteile: Wand.zifferblatt (bauteile Z.151) und Bau.clock/clock3 (Z.998). Von Hand: schwab_v3 Z.140-148, martinstor_v4 Z.182-194. Einen Erkenner gibt es nicht (keine Parsing-Klasse). Einbau: OWLv2-Klasse "a clock face" plus Kreisfit im feinen Wandbild -> zifferblatt. Aufwand klein bis mittel, Risiko Rosette/Wappen (Gegenbegriffe sind vorhanden).
10. FACHWERK. fachwerk_aus_ortho.py laeuft nur in schwab_nachbar_gen.py Z.50-54, in der Kette nie. Die Ausgabe ist schon im relief_einsatz-Format, der Aufwand ist also klein. Folge in der Freiburger Altstadt: Fachwerk fehlt ganz.
    Risiko: Das Werkzeug arbeitet mit einer Helligkeitsschwelle, und der Skill linien-features verbietet Farbschwellen. Deshalb nur als Vorschlag mit foto_diff-Tor oder auf Kanten umstellen.
11. ECKQUADER und glatte Steinfelder. relief_quader_eben.py ist keine Stufe, "Felder und Schwelle werden von Hand gesetzt" (PIPELINE_FASSADEN.md Z.134-135). quoins/mauerwerk_aus_protokollen (Z.965/Z.1136) gibt es nur bei Martinstor (martinstor_v4 Z.171-175). steine_aus_foto steckt schon in der Kette (--fotosteine). Einbau: Felder = Nicht-Putz-Zellen der Putzmaske an den Wandecken. Folge mittel (Beulen statt Quader).
12. KLEINES. Zinnen von Hand ohne Funktion (martinstor_v4 Z.201-211), foto_zaehlung.py ist keine Stufe. ortgang_quader, masswerk_fischblase und blendfeld_mandel gibt es nur in schwab_nachbar Z.102-128, staffelgiebel nur bei Kaufhaus. umgang (Z.339; schwab_v3 Z.291-296), ein Ruecksprung unter der Traufe. ANNAHME: fassade_tiefe mit --w < 0 sieht auch Ruecksprunge, das Gegenstueck zu den Vorbauten. laserdach.py fuer verwinkelte Daecher (schwab_nachbar Z.17-19) ist nicht in der Kette.

## C. Tore und Struktur - belegt
13. teil_fotoform.py laeuft in keiner Stufe und nicht in bauen_abnehmen.sh (grep: 0), obwohl CLAUDE.md "Jede Kette: ... Foto-F1 (teil_fotoform)" verlangt. foto_diff nennt es nur im Kommentar (Z.19).
14. baukasten_gen.py ist ein zweiter generischer Generator mit 29 Bauteiltypen (u. a. helm_geschweift, zylinder, erker_polygon, gaubenreihe, konsolenreihe, bruestung, pyramide). Er bedient nur die alten Kaufhaus-Objekte (objekt.json "bauteile"); die Vorlage und die Kette kennen ihn nicht. Bauteile, die schon fertig sind, liegen also doppelt herum. Vor neuen Funktionen (7, 8) dort nachsehen.
15. Kleiner: kanten_bericht_fertig.json bleibt ohne Rueckkopplung (nur eine Notiz). feinteil_tor ist nur ein Hinweis (bauen_abnehmen Z.39).

## Empfohlene Reihenfolge
Wirkung je Aufwand: 2 (Mono, klein) -> 6 (bauteile_foto in die Vorlage, klein) -> 1 (Aussenfenster aus dem Wandbild, mittel) -> 10/9 (Fachwerk/Uhr) -> 4 (Beobachtungen rot) -> 13 (Tor) -> 7/8 (Rundkoerper, Laterne) -> 3 (Kanten bauen) -> 5 (Gauben).

## Stand der Abarbeitung (21.11.2026)
- Vorbauten (Erker, Galerie, Vordach): ERLEDIGT 20.11. ~00:00. Werkzeuge `tools/vorbauten_bauplan.py` und `bauteile.vorbauten_aus_json`, Stufe bauplan. Beweis: Am Schwabentor liegen 95 % der Erker-Fotokanten am Modell (vorher 22 %).
- Nr. 2, Mono-Feinrelief: ERLEDIGT 21.11. `fassaden_kette.anbauen` baut `<wand>_mono.npz` ein. Schwabentor: 4 Wände. Kantenmaß neutral (60,4 % → 59,6 % der Punkte ≤ 5 cm), die Steine sind sichtbar einzeln.
- Nr. 9, Uhr: ERLEDIGT 21.11. Erkennerklasse `uhr` in `fassade_parsing.py`, Messung mit `tools/uhren_wandbild.py` (Kreis im 1-cm-Wandbild), Bau mit `bauteile.uhren_aus_json`. Schwabentor f00: 5,10 / 3,47 m, Kantenstütze 98 %. Handmaß in der Maßtabelle: 4,95 m.
- Neu, Sackgassen-Tor in `gesamtkette.py` vor 'html': Ein Kettenergebnis, das kein Generator verbaut, ergibt jetzt `ok: False` statt still „in Ordnung“.
- Torbogen-Befund: Er IST gebaut (`oeffnungen_bogen.py`, spitz, 4,79 m breit, Scheitel 6,20 m), aber nur 0,6 m tief, weil die Gegenseite f01 nur 4 Fotos hat (18 % Abdeckung). Datenlücke, keine Werkzeuglücke.
- Neu, Fenster-Tiefen-Tor (21.11. 00:30): `tools/fenster_tiefe_tor.py` in der Stufe bauplan, nach dem Sweep.
  - Am Schwabentor f00 verwirft es die Konsolenfelder unter dem Erker. OWLv2 hatte sie mit 10 von 10 Stimmen als „Fenster“ gemeldet; im Sweep liegen 0–1 % der Zellen dahinter und 23–39 % davor.
  - Es ergänzt das linke Rundbogenfenster (3 von 7 Stimmen, 58 % der Zellen hinter der Wand).
  - Auf f03 urteilt es nicht, weil der Sweep im Ring unsicher ist (33–58 % < 70 %).
  - OFFEN: Das rechte Rundbogenfenster findet der Erkenner gar nicht (kein Kasten).
