# SPEC: Neue Verfahren mit Runpod erproben, um druckbare H0-Modelle aus Bildern besser zu erreichen (27.11.2026)

Auftrag (Nutzer 27.11.): "wie koennen wir, dadurch dass wir jetzt Runpod haben, weitere Verfahren probieren, um unser Ziel, aus Bildern druckbare H0-Modelle zu erstellen, besser zu erreichen?"
Entscheidungen im Interview (27.11.): Abnahme = Foto-F1 + Bild (Bestand-Tor); Testobjekt = Schwabentor inkl. Bruecke; Lizenz = auch NC, aber nur als Test; Budget/Autonomie = selbst entscheiden, **25 USD gesamt** (Guthaben 27.11. abends 52,81 USD).

## Ausgangslage (belegt, nicht wiederholen)
- Auf Runpod gemessen: Mehr Aufloesung der dichten Wolke (1600 -> 5800 px) bringt Punkte (0,60 -> 1,83 Mio), aber **keine ebenere und keine vollstaendigere Wand** (Ostwand: Streuung 7,9-8,0 cm, belegte Flaeche 10-cm-Zellen 34-35 % in allen Stufen). Registrierung der 241 Handyfotos in voller Aufloesung: **91/241** (2000 px: 97/241). Der RAM (14,7 GB bei 4000 px) ist die erste echte Grenze der 4060, aber ohne Qualitaetsgewinn dahinter.
- Folgerung: Speicher/Aufloesung ist nicht der Hebel. Hebel sind **Kameras an schwachen Stellen (Bruecke, Treppe, Unterdurchgang, Treppenturm), Kantenmessung und Bewertung** (Doku/projekt/foto-sfm/grundbegriffe.md, bauteile-kreis/bruecke.md: Baustein `bruecke_render` scheitert an Strafe gegen geringe Kantenpraezision).
- Gesperrt/verworfen laut `modelle/RECHERCHE_BESSER_2026-11-25.md`, `NICHTS_GEBRACHT.md`, `LIZENZ_WERKZEUGE.md`: generative Bild-zu-3D (TRELLIS/Hunyuan), Splatting als Geometrie, Mono-Tiefe als Hoehe, freie Vertex-Optimierung, PolyFit (GPL). NC-Verfahren (MASt3R, DUSt3R, VGGT, Pi3, LoMa) nur Test.

## Ziel
Ein Messprogramm, das auf Runpod-GPUs (24 GB, bis 125 GB RAM) die aussichtsreichsten Verfahren gegen den **Bestand** auf dem Schwabentor testet und je Verfahren eine belegte Antwort liefert: bringt es Foto-F1/Bild besser, ja/nein/unklar, mit Kosten und Lizenz. Gewinner gehen als Kettenstufe in die Kette (Worktree-Agent, Merge nur bei Schnelltest 0), nicht als Handeintrag.

## Nicht-Ziele
- Kein Druck. Keine Bauteil-Handwerte. Keine Verfahren, die Geometrie erfinden (generativ). Keine Aenderung von Sollwerten.
- NC-Ergebnisse werden nie ins Verkaufsmodell uebernommen; sie dienen nur als Obergrenze. Ein lizenzfreier Ersatz ist ein eigener Auftrag.
- Kein dauerhaft laufender Pod, kein Cron/Loop fuer Pod-Checks (Memory 22.11.).

## Kandidaten (Reihenfolge = Entscheidung beim Bauen, begruendet; jeder Versuch hat vorab Archivsuche + Messplan + Skeptiker nach Skill `versuch-messen`)
K1. **Kameras fuer schwierige Fotos**: ALIKED+LightGlue voll aufgeloest (laeuft, Pod `ajc546q1dpbnep`), danach MP-SfM (Apache, MIT-SuperPoint, DA-V2-Small/DepthPro) und MapAnything-Apache; **NC-Obergrenze** mit MASt3R/VGGT nur zum Test. Messgroesse: zusaetzlich eingeordnete Bruecken-/Treppenfotos von 144 nicht eingeordneten, Reprojektion < 2 px, Seiten-/GPS-/Doppelgaenger-Tor gruen.
K2. **Linien-Triangulation je Bauteilzone (LIMAP + DeepLSD)** auf den Bruecken-/Turmkameras: Kernmethode ohne Wolkentiefe. Messgroesse: Foto-F1 der Zone gegen Bestand.
K3. **Robuste Bewertung im Bruecken-Baustein** (Strafe gegen geringe Kantenpraezision ersetzen): reine Code-Arbeit im Worktree `bruecke_baustein`; Rechnen auf Runpod nur fuer den echten Lauf.
K4. **Parameter-Feinabgleich per differenzierbarem Rendern** (wenige Parameter, Holdout, Startwert-Stoerung) als Foto-Tor ohne Handmodell; nvdiffrast ist gesperrt, eigener Rasterer `render_kern.py` oder PyTorch3D.
K5. **Dichter Matcher (RoMa, EfficientLoFTR) nur fuer die nicht eingeordneten Fotos**; Lizenz der Gewichte vorab lesen.

## Anforderungen (je mit Nachweis)
R1. **Vor jedem Versuch** steht Archivsuche (`python3 -I tools/wissen_suchen.py "<begriff>"`), Lizenz-Zeile aus `LIZENZ_WERKZEUGE.md` (Code UND Gewichte; NC markiert "nur Test") und ein Messplan mit Messgroesse, Nullkontrolle und Abbruchschwelle im Versuchsregister. *Nachweis:* je Versuch eine Zeile in `Doku/projekt/<ast>.md` (Gilt/Versucht/Offen) mit Datum, vor dem Start geschrieben (git-Zeitstempel vor dem Pod-Start).
R2. **Basislinie zuerst**: jeder Versuch nennt die Zahl des Bestands (zuletzt Handvergleich 10/11, Registrierung 97/241 bzw. 91/241, Foto-F1 je Bauteil) auf demselben festen Fotosatz. *Nachweis:* Bericht enthaelt Bestand und Neu nebeneinander aus derselben Messfunktion.
R3. **Bild vor Zahl**: Ergebnis wird nur gemeldet, wenn `audit/neben_*.jpg` bzw. ein Foto-neben-Modell-Bild zusammen mit dem Bestandsbild dem Nutzer gezeigt wurde (SendUserFile); Bestand-Tor rot = Rueckschritt, nicht melden als Fortschritt, nicht mergen. *Nachweis:* Bildpfade im Bericht; Bestand-Tor-Ausgabe zitiert.
R4. **Tauschtest/Nullkontrolle je Versuch** (Erkenntnis 25.11.): Das Verfahren muss gleich bleiben, wenn Vormodell/Schwelle getauscht wird, und eine absichtlich falsche Eingabe (Fremdbild, Seitenverwechslung, verschobene Huelle) muss es zurueckweisen. *Nachweis:* roter Lauf zitiert, danach gruener.
R5. **Kostenwaechter**: Gesamtausgabe fuer diese Spec <= 25 USD. Vor jedem Pod Preis/h und erwartete Dauer nennen; nach dem Lauf Pod loeschen und per Lesen (`runpodctl pod list`) pruefen; Guthaben (`get-balance`) im Bericht. Bei Erreichen von 20 USD stoppt der Versuchsbetrieb, Stand zeigen. *Nachweis:* Bericht listet Pods, Laufzeit, Kosten; Summe <= 25 USD.
R6. **Daten nur ueber das Netzwerk-Volume `ghhv7k1089`** (EU-RO-1), je Lauf eigener Ausgabeordner, ein Schreiber je Ordner; Ergebnisse vor dem Pod-Loeschen lokal gespiegelt (Groessenvergleich, bei Binaerdaten >= 1 MB nur auf `/media/oem/rcdaten`, nie in git ohne LFS). *Nachweis:* Groessenvergleich zitiert.
R7. **Dummy-Test vor jedem Langlauf** (Memory Smoketest; Pod-Skript, kleine Eingabe) und Pruef-Termin einmalig, kein wiederkehrender Check; Warter immer mit Ende-Marke und Timeout. *Nachweis:* Dummy-Ausgabe zitiert.
R8. **Keine Handeintraege, nur Automatik**: ein Gewinner wird als Stufe in `tools/` (generisch, mit Test, `bash tools/schnelltest.sh` = 0) eingebaut, im Worktree, Merge nur bei Schnelltest 0; Doku im betroffenen Ordner aktualisiert (Skill `doku-pflege`). *Nachweis:* Schnelltest-Ausgabe, Commit-Hash, Doku-Zeile.
R9. **Ehrlicher Bericht je Versuch**: Fehlerliste vor Lob, Realitaets-% als Foto-F1 (nicht Augenmass), Annahmen als `ANNAHME:`, negative Ergebnisse mit benannter Ursache im Register (`NICHTS_GEBRACHT.md`). *Nachweis:* Berichtsabschnitt vorhanden.

## Randfaelle
E1. Pod nicht verfuegbar (Capacity-Fehler): naechste GPU-Klasse in derselben Region (L4/A5000/A6000 statt 4090), nie Region wechseln ohne Volume-Kopie; Frage an Nutzer bei Aenderung > 0,5 USD/h.
E2. Verfahren verbiegt das Netz (Lehre ALIKED 1.11., Kette 25 Grad): Einpassung nur starr, Qualitaetstor `teilmodell_qualitaetstor` (Rest relativ <= 0,025, Drehfehler <= 0,6 Grad); sonst Ergebnis "unsicher", nicht ins Hauptnetz.
E3. Seitenverwechslung symmetrischer Tuerme: Seitennamen nur aus `objekt.json seiten_konvention`; verklebt eine Seite, Versuch verwerfen mit Ursache.
E4. Nutzer ist vor Ort und liefert Fotos (Fotoauftrag, `foto-vor-ort`): neue Fotos sofort in die Basislinie aufnehmen; Vergleich nur auf gleichem Fotosatz.
E5. Pod haengt/OOM: Stufe wiederholen (Memory Speichermangel), Pod nach 2 Fehlversuchen beenden, Ursache ins Register.
E6. Schluessel/Zugang: nur `~/.runpod/` (Modus 600); nie ins Repo; `~/Downloads/credentials` wird nur nach ausdruecklichem "Ja" des Nutzers geloescht.

## Abnahmekriterien
A1. Fuer K1-K5 liegt je eine Zeile "bringt/bringt nicht/unklar" mit Zahl gegen Bestand, Bild, Kosten und Lizenz vor.
A2. Mindestens ein Verfahren verbessert Foto-F1 oder die Zahl eingeordneter Bruecken-/Treppenfotos gegen den Bestand **bei gruenem Bestand-Tor**, oder alle sind mit benannter Ursache ins Register eingetragen (dann Fotoauftrag als naechster Hebel).
A3. Keine Runpod-Pods laufen am Ende (Liste leer), Gesamtkosten <= 25 USD, alle Ergebnisse lokal.
A4. Der Nutzer hat die Bilder "Foto neben Modell" fuer jeden gemeldeten Gewinn gesehen.

## Offene Punkte
- Wie viel der 25 USD gehen an die NC-Obergrenze? Vorschlag: hoechstens 6 USD.
- `tools/cloud_job.py` (Router nach VRAM/RAM/Zeit) ist erst Teil dieser Spec, wenn ein zweiter Versuch ihn braucht; bis dahin Skripte im Scratchpad.
- Lizenz RoMa-Gewichte und EfficientLoFTR-Registrierung ungeklaert (K5 erst nach Lesen).
- Ergebnis des laufenden LightGlue-Laufs (Pod `ajc546q1dpbnep`) ist Eingang fuer K1.
