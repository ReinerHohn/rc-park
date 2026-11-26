# SPEC: "Ich fotografiere nur" - Vollautomatik Fotos -> druckbares 3D-Modell

Stand 26.11.2026, Interview mit dem Nutzer (Skill /spec). Baut auf `modelle/ZIEL_PIPELINE_H0.md` (Abnahmekriterien 1-5, Pipeline von null) auf.
Verhältnis zu `modelle/SPEC_SCHWABENTOR_DEMONSTRATOR.md`: beide gelten; Schwabentor bleibt Priorität und darf halbautomatisch fertig werden,
jeder dabei nötige Handschritt wird danach als Kettenstufe nachgebaut (Regel `PLAN_HANDMODELL_IN_KETTE.md`). Diese Spec ist der Fahrplan dazu.

## Ziel
Der Nutzer lädt nur Fotos eines Gebäudes hoch (nach einer Aufnahme-Anleitung). Ohne weiteren Eingriff liefert die Kette ein druckbares H0-Modell (1:87)
oder, wo Fotos fehlen, einen konkreten Fotoauftrag. Ein Durchlauf dauert höchstens eine Nacht (bis 8 Stunden).

## Nicht-Ziele
- Kein Eingeben von Ort, Name oder Maßen durch den Nutzer (Gegenproben holt die Kette selbst, nur als Abgleich).
- Kein Erfinden oder Spiegeln ungesehener Flächen; keine Innenräume; keine Bemalung.
- Keine Qualitätsverbesserung an Einzelobjekten durch Handeinträge, auch nicht "nur dieses eine Mal".
- Nicht verlangt: Ergebnis in unter 2 Stunden vor Ort (Nutzer hat "über Nacht" gewählt).

## Anforderungen (Reihenfolge = Priorität, Nutzer 26.11.)
1. **Abdeckung zuerst (Fotos reichen nicht ins Netz).**
   a. Aufnahme-Anleitung (eine Seite, mit Skizze): Rundgang, Überlappung, Abstände, Höhen, Weitwinkel/Detail, feste Linse, keine Zoom-Wechsel; aus den Messungen der Handyfotos 26.11. begründet
      (Schwabentor, Handyfotos 26.11.: 739 aufgenommen, 241 gewählt, 97 davon eingeordnet = 40 %; Brücke/Treppe/Unterdurchgang/Treppenturm fehlten im Netz; Nutzer 26.11.: diese Zahl ist die Basis, die frühere "283 von 677" ist überholt).
   b. Automatische Abdeckungsmeldung nach der Registrierung: je Wand, Dach und Sonderstelle (Brücke, Treppe, Vorbau) Anzahl Fotos, Blickwinkelfächer, Tiefenabdeckung;
      Ausgabe als Bild + Liste. Schwellen aus Daten herleiten oder als `ANNAHME` eintragen.
   c. **Fotoauftrag statt Erfinden:** Fehlt Abdeckung, nennt die Kette die Stelle und von wo/wie zu fotografieren ist (Karte oder Skizze, Standpunkt, Blickrichtung);
      im Modell steht dort "nicht belegt". Kein Spiegeln, keine Katalogteile, kein Raten.
   d. Nicht eingeordnete Fotos werden mit Grund gemeldet (keine Korrespondenz / zu wenige Matches / Lage nicht berechenbar), nicht stillschweigend verworfen.
   **Stand 26.11. (Werkzeug; seit 26.11. abends in `gesamtkette.py` Stufe seiten, Schritt `abdeckung_zusatz`, wenn objekt.json `zusatzfotos` gesetzt):** `tools/abdeckung_meldung.py` + Zonenliste `modelle/<obj>/abdeckung_zonen.json` erfüllt b–d
   (Bild + Markdown + JSON), Test `tools/test_abdeckung_meldung.py` im Schnelltest. Echte Handyfotos: 97/241, Gründe 63 keine Korrespondenz / 53 zu wenige Matches /
   28 Lage nicht berechenbar; Fotoauftrag Brücke, Treppe, Unterdurchgang (Lage nicht im Netz). **Treppenturm belegt – geklärt 26.11.:** die Kontaktbogen-Aussage „Treppenturm fehlt“ war falsch (27 eingeordnete Handyfotos
   zeigen ihn, Bild `audit_treppenturm_20261126/bogen_handy.jpg`); die Zählung 320 war aber zu großzügig (Straßenblicke durch Nachbarhäuser) -> Spurbeleg: 186 Kameras, 24 Handy, Fächer 229 Grad.
2. **Laufzeit: Foto bis Modell höchstens 8 Stunden** je Gebäude (ANNAHME der Größenordnung ~700 Fotos; heute messbar: SIFT-Matching 677 Fotos ~1,4 h,
   LightGlue grob 840 157 Paare ~95 min bei ~145 Paaren/s, Registrierung ~10 min, Teilmodell-Mapper offen).
   Die 8 h werden nur gemeldet, nie erzwungen: kein Abbruch wegen Zeit (ein halbes Modell widerspricht Randfall 1); Abweichung = Meldung mit langsamster Stufe (Nutzer 26.11.).
   a. Jede Stufe schreibt Beginn, Ende und Auslastung (CPU/GPU) ins Laufprotokoll; Stufen ohne Abhängigkeit laufen parallel (RAM-/VRAM-Buchung bleibt).
   b. Paarauswahl statt aller Paare prüfen: erst Messung an kleinem Beispiel (Matches und Einordnungsquote mit/ohne Auswahl), erst bei gleicher Quote einführen.
   c. Einzelprozesse mit schlechter Auslastung (z. B. LightGlue 1 Kern, GPU 43 %) werden aufgeteilt oder die Auslastung begründet.
3. **Form und Details ohne Handarbeit** (Wand flach, Tür nur Kasten, Brücke fehlt): Handschritt -> Kettenstufe laut `PLAN_HANDMODELL_IN_KETTE.md`
   (Zone im Wandbild, Kanten-Sweep, Maßliste, generischer Baustein). Neue Bausteine nur generisch in `tools/bauteile.py` mit rotem Test
   (Beispiel: `ueberdachter_gang`, Zweig worktree-agent-af57fdd5b839f216f, noch nicht in der Kette).
4. **Weniger Handgriffe im Ablauf:** ein Aufruf `tools/gesamtkette.py` (ZIEL_PIPELINE_H0.md Nr. 1); Seitennamen nur aus Konvention; Tore melden selbst
   rot/grün mit Grund; Merge nach main nur durch Schnelltest 0 + Bestand-Tor, nicht per Hand abgesprochen. Offen: Liste der heutigen Handgriffe (je Lauf zählen).
5. **Nie schlechter als der Bestand** (Bestand-Tor, `audit/neben_*.jpg` ansehen, Rückschritt nicht mergen). Keine Handeinträge zum Bestehen eines Tores.

## Randfälle
- Zu wenige Fotos insgesamt: Kette bricht vor dem Mapper mit Grund und Fotoauftrag ab, kein halbes Modell.
- Foto ohne EXIF/GPS: Lage aus Netz + unabhängiger Gegenprobe (Lot, Maßstab); fehlt sie, "Lage nicht belegt", Ergebnis nicht als fertig melden.
- Fotos verschiedener Tageszeiten/Zoom: Kalibrierung je Gerät; bei Zoom-Wechsel Warnung statt falscher Brennweite.
- Symmetrische Türme: Seitenverwechslung prüfen (`METHODE_SEITEN_SFM.md`), bei Verdacht Fotoauftrag für eindeutiges Merkmal.
- GPU/RAM belegt: Job wartet nach Buchung; kein stiller Abbruch, kein CPU-Fallback ohne Meldung.
- Nur Wolke belegt, nicht am Foto: gilt als vorläufig, im Bericht gekennzeichnet.

## Abnahmekriterien
- Hauptkriterium (Nutzer 26.11.): **Gleiche Fotos, weniger Hand.** Für Schwabentor, Martinstor und Kaufhaus: Kette von null ohne Handeintrag; Ergebnis mindestens
  so gut wie der beste Bestand (Bestand-Tor grün, Bild "Foto neben Modell" je Wand vom Nutzer gesehen). Messgröße zusätzlich: Anzahl Hand-Eingriffe je Lauf (Ziel 0). **Zählregel:** Jeder Aufruf außerhalb von `tools/gesamtkette.py` und jede Dateiänderung an JSON/`masstabelle.json` während eines Laufs zählt; die Kette schreibt die Zahl selbst ins Laufprotokoll (Nutzer 26.11.).
- Abdeckungsmeldung auf den Handyfotos 26.11.: nennt Brücke, Treppe, Unterdurchgang und Treppenturm als Fotoauftrag, solange dort die Einordnung fehlt (**automatischer Test** mit festem Mini-Datensatz, im Schnelltest rot, wenn eine der vier Stellen fehlt; Nutzer 26.11.).
- Laufzeitprotokoll zeigt eine Gesamtdauer; Ziel <= 8 h; Abweichung benennt die langsamste Stufe.
- Nicht verlangt: Test mit einem neuen, nie gesehenen Gebäude (Nutzer hat ihn nicht gewählt); bleibt als spätere Gegenprobe erlaubt.

## Offene Punkte
- Welche Handgriffe gibt es heute je Lauf? Mit der Zählregel (Abnahme) erfassen, dann abschaffen. Zählung im Laufprotokoll noch zu bauen.
- Paarauswahl: Wirkung auf Einordnungsquote ungemessen (Anforderung 2b).
- Ergebnis Teilmodell-Mapper und LightGlue auf den Handyfotos 26.11. steht aus (läuft); Quote gegen die 42 % vergleichen.
- Mindest-Fotozahl und Abdeckungsschwellen: aus Daten herleiten (ANNAHME bis dahin).
- Wo Aufnahme-Anleitung und Fotoauftrag erscheinen (Datei, Bild, App): Nutzer entscheidet später; zunächst Bild + Markdown im Objektordner.
