# Stand 12.11.2026 vormittags (nach /clear zuerst lesen)

Anrede: "mein grosser Meister", Deutsch, ehrliche Fehlerliste und Realitaet %, keine Schoenfaerberei.
Ziel: ueberzeugendes H0-Modell kaufhaus_grob3 (Historisches Kaufhaus Freiburg) fuer Miniatur-Wunderland, ueber den Konvergenz-Kreis. Drucken ist NICHT das Ziel.
Viewer: https://claude.ai/artifact/9mpGqmnVR3bBqUYnh6jXyQ (Neubau: `bash /media/oem/scan/rc-park_tmp/viewer/neu_html.sh`, dann mit dem Artifact-Tool auf diese URL publizieren; Stand zuletzt v55).

## Prioritaeten des Nutzers
1. Erker Netzrippen (Gedaest, Rosetten, Rippenbuendel in die runde Saeule, Eckfiguren/Drachen). Schluesselfoto 6171 (dreisträngige Spitzbogenrippen, Rautennetz, Buendel); Rosetten am West-Erker in 6162 sichtbar.
2. Baldachine. 3. Wasserspeier. 4. Dachschindeln/Zipfel. 5. Erker-Fenster (Butzen, nicht Sprossen). 6. Seiten-/Gassenwand-Fenster (mehrfach gemeldet). 7. Laube Dienste (akzeptiert).
Offener Nutzerfund 20:59: "Erker Ost: aeusseres Segment fehlt (Gassenseite)" (Fotos 6259, i_09, n11_05/06). Ob mit Seitenfenstern Ost- oder Westwand gemeint ist, ist UNGEKLAERT (Agent ordnete n11_05/06 dem staffelgiebel__west zu; Ostwand unkalibriert) -> Nutzer fragen.

## Harte Regeln (Nutzer)
- Nie abbrechen wegen Platz ("Abbruch ist Kacke ... immer"). Platzwaechter tools/platz_waechter.sh (root <10 GB, Daten <14 GB -> auslagern).
- Prozess muss ohne Nutzer laufen; GPU/CPU voll nutzen; Nacht nicht verschwenden.
- Privaten Ordner handy_phone_2026-11-11/nicht_kaufhaus NIE oeffnen. Nie loeschen, nur verschieben. Grosse Daten nur unter /media/oem/scan.
- Lange Jobs nur per `JOB_GPU_MB=<MiB> tools/job_start.sh NAME LOG BEFEHL`. Commits nur eigene Dateien: `flock /media/oem/scan/rc-park_kreis/merge.lock git commit -- <pfade>`; Texte enden mit `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01BMC5F7JqzthTsrTAV2gKLz`.
- Fremde uncommittete Dateien nie anfassen: tools/konvergenz_bericht.py, tools/nachbarn_modellrahmen.py, tools/formfund_pruefen.py, realitaet_verlauf.jsonl.
- Nach tools-Aenderung `python3 tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen` ("identisch"). Keine Objektnamen im Code.
- masstabelle-Eintraege: beobachtungen_offen braucht datum, wer, text, naechster_schritt; vor Commit `bash tools/bauen_abnehmen.sh kaufhaus_grob3 --nur-pruefen` (Memory feedback-masstabelle-pruefen-vor-commit).
- Hotel-App-Nachrichten (QR-Code, Raspberry Pi) gehoeren zu einer anderen Sitzung.

## Was in der Nacht 11./12.11. passiert ist (ehrlich)
- Rauschtor (6fbe1c61) eingefuehrt: teil-lokale Nullkontrollen (0,3 m verschoben/angehoben, 90 Grad gedreht), Messwahl f1_fein/f1, Messbarkeits-Filter, Rueckgabe aus, Start-Abnahme main. Grund: Foto-F1-Schwelle 0,02 lag unter dem Rauschen (~0,03); in 4 Tagen keine Konvergenz (pixel ~71 %).
- Nachtlauf 00:30-07:45: 54 Runden (12 leer, 37 verworfen, 5 angenommen = Laubensockel/Satteldach, Aenderung +-0,00-0,01, nicht sichtbar). Erker/Baldachine/Figuren/Gauben waren NIE Ziel: globaler Sperrzaehler (MAX_GLOBAL 3) zaehlte Verwerfungen aus dem alten, rauschblinden Tor. Mein Fehler: vor dem Start nicht `--nur_wahl` angesehen. Eintrag in modelle/NICHTS_GEBRACHT.md.
- Verwertbare Reste: Balkonkonsolen-Patch (konvexe Huelle ueber konkaves Profil; f1_fein 0,432 -> 0,531, Rauschtor bestanden; nur abgelehnt wegen "Hoehenlage verdaechtig: 0,3-m-Kopie misst besser f1_h 0,807 vs 0,753") -> Neupruefung laeuft; Westgiebel +0,033 vom Pruefer als erfunden abgelehnt (diagonales rotes Band), Lehre: First laeuft laengs, Giebeldreieck an der +n-Stirn.
- Erker 0 (Ornamentik) und baldachinreihe__baldachine: Rauschtor findet KEIN trennendes Mass (Reihen-Teil, Region zu gross); fotowunsch.jsonl hat 15 Eintraege (Fenster EG0/EG2/OG, Nischen, Helme, Dienste-Sockel).

## Heutige Aenderungen (committet)
- eb6c10f7: Sperrzaehler zaehlt nur Rauschtor-Runden.
- 4681cbc0: Regel 1-4 gegen Wiederholung: (1) TOR_VERSION-Hash im kreis.jsonl, Sperrzaehler zaehlt nur aktuelle Torversion; (2) Regler startet stuendlich `bauteil_kreis.py --nur_wahl` -> wahl_probe.json (waehlbar, Nutzerfund-Teile, gesperrte Nutzerfunde); (3) Freigabe gesperrter Nutzerfunde (freigabe.json), wenn 1 h keine Runde an Nutzerfund-Teilen, max alle 3 h je Schluessel; (4) Stundenbericht in kreis_regler.log + /media/oem/scan/rc-park_kreis/kaufhaus_grob3/stundenbericht.txt mit ALARM-Zeilen.
- 68ed6955: Fehlalarm beim Start behoben. c23ad76d: Agentengrenze 35 statt 60 Minuten (`--max_minuten`).
- Regler: `tools/job_start.sh kreis_regler /media/oem/scan/rc-park_kreis/kreis_regler.log python3 tools/kreis_regler.py kaufhaus_grob3 --gpu_ziel 101 --max 4`. Aenderung an bauteil_kreis.py beendet Spuren an der Rundengrenze.

## Laufende Arbeiten (beim Wiedereinstieg pruefen)
1. Konsolen-Neupruefung (kein Agent): Job `rcpark-kreis_konsolen_regate`, Log /media/oem/scan/rc-park_kreis/kreis_konsolen_regate.log, Patch /media/oem/scan/rc-park_kreis/kaufhaus_grob3/patches/konsolen_huelle_20261112.patch. Wartete auf gpu_tor.lock. Bei Annahme: Viewer neu bauen + publizieren. Bei Ablehnung wegen Hoehe: Hoehen-Sweep der Konsolenreihe (tools/teil_sweep_gpu.py), Patch erneut.
2. Agent a3ee0950df4503a40 (Sonnet): Element-Messregion fuer Reihen-Teile (Baldachine, Erker 0), Worktree /media/oem/scan/rc-park_tmp/wt_element, Beweis synthetisch + Echttabelle je Element. Bericht kommt per Notification. Wiederverwendbar: tools/zier_ausschnitt.py (Elementboxen -> Vollaufloesungs-Ausschnitt), teil_varianten_tor.py. element_vergleich.py ist ungeeignet (Wolkenprofile).
3. Regler mit 4 Spuren laeuft; Zielwahl-Probe zeigt jetzt 24-27 Kandidaten, Erker 0/1 oben. Belegt waren zuletzt erker_polygon__1, bogenreihe__laube, staffelgiebel__ost, quader__laube_sockel_w.
4. Kontrolle um ca. 20 Uhr: mindestens eine sichtbare Erker-Annahme (fehlendes Segment oder Netzrippen). Morgen frueh: pixel-Realitaet > 72 % (heute ~71 %), sonst Weg wechseln. Zeitprognose "Miniatur-Wunderland-tauglich": 2-3 gute Naechte fuer Erker/Baldachine/Dach, Schaetzung, keine Zusage.

## Offene Punkte (Reihenfolge)
- Erker-Netzrippen: frische Agentenrunde mit voller Beschreibung aus Foto 6171 (Pruefer muss 6259 sehen; erker6/erker7-Runden scheiterten an Sperre/Formfund-Pruefer "erfunden").
- Erker-Segment aussen (Gassenseite) mit Foto 6259 als Pflichtfoto fuer den Formfund-Pruefer.
- Seitenfenster klaeren (Ost/West), dann Gassenwand-Runde.
- Turmfotos n11_01-03 nicht registriert (kaum gemeinsame 3D-Punkte, lockere Registrierung gab Kamerahoehe 42-98 m = falsch, verworfen). Idee: erst mit j_/c_-Handyfotos Turmpunkte triangulieren, dann PnP.
- Feinsuche (/media/oem/scan/rc-park_tmp/feinsuche/lauf_voll/ergebnis/): Cluster sind unbenannte Orte ("Feinform fehlt") und speisen den Kreis schon als Foto-Cluster; Import in die Masstabelle bewusst NICHT gemacht (keine Aufgabe fuer Agenten). Interpretation aus top10.jpg: Erker-Fenster mit Masswerk/Sprossen/Eckfigur, Laubenpfeiler-Sockel (achteckig profiliert statt rund), Traufe/Speier, Sprossenfenster, Gewoelberippen.
- Spaeter: Bild-zu-3D fuer Drachen/Speier/Figuren (SPAR3D/Hi3DGen; Hunyuan3D wegen EU-Lizenz ausgeschlossen), Dachdeckung, Erker-Fenster Butzen, Fehlteil-Pfad (56 Runden, 4 Annahmen, baut nichts) reparieren oder pausieren.
- Quota: ~70 % der Woche verbraucht (Reset 15.11. 9:00).

## Messfakten
- Grob-Foto-F1 (0,18 m Glaettung) ist fuer Ornament blind/invertiert; f1_fein (0,03 m) trennt Nullkontrollen. Rauschen je Teil: erker_polygon__1 f1 -0,070 / f1_fein +0,031 (nur f1_fein trennt); gaubenreihe__oben f1 +0,042; baldachine: kein Mass.
- Cache der Nullkontrollen: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/rauschen/ (131 Eintraege).
- Probe der Zielwahl jederzeit: `python3 tools/bauteil_kreis.py kaufhaus_grob3 --nur_wahl`.

## Nachtrag 12.11. ~08:45 (Kontext-Verschlankung + Alarm)
- CLAUDE.md/MEMORY.md verkleinert (Volltexte: modelle/REGELN_AUSFUEHRLICH.md, memory/archiv_index.md); nicht committet.
- Alarm "ueber 80 % Takte ohne Kandidat" vermutlich Fehlalarm: Zielwahl-Probe 08:41 zeigt 21 Kandidaten (waehlbar u.a. bruestung__balkon, kreuzgewoelbe__laube, figurenreihe__figuren, konsolenreihe__balkon). kreis_regler.py Z.293 zaehlt "kein Kandidat" je Takt; Z.243 Alarm bei >80 %. Noch zu pruefen: ob "warten: 4 Spuren = max" als leerer Takt zaehlt (dann Zaehler nur bei freier Spur werten).
- Konsolen-Patch ist gemergt (cc641e83), Viewer noch NICHT neu gebaut/publiziert (neu_html.sh, dann Artifact 9mpGqmnVR3bBqUYnh6jXyQ).
- Offene Frage an Nutzer: Erker-Fund "aeusseres Segment fehlt" - Ost- oder Westwand?

## Nachtrag (Sitzung nach /clear): Element-Messregion
- Agent-Bericht (Commit aed31a15): Element-Region nur synthetisch bewiesen; am echten Vorher-Stand ist bei Baldachine und Erker 0 kein Element messbar (alle R negativ). Nullkontrolle "hoch +0,3 m" schlaegt bei allen 4 Baldachinen den Vorher-Stand = Verdacht Hoehe zu tief (NICHT am Foto geprueft).
- `--element_region 1` bleibt AUS (kostet einmalig Baldachine ca. 25 min, Erker ca. 60 min GPU; Anbindung nur im Trockenlauf getestet).
- Nutzer hat "mache alles, was generell geht" gesagt. Naechste Schritte: (1) beobachtungen_offen-Eintrag Baldachinhoehe in masstabelle.json, dann am Foto messen (tools/foto_mass.py), dann Generator + tools/bauen_abnehmen.sh kaufhaus_grob3; (2) Erker-Elemente aus dem Generator statt Raster. Noch nichts davon begonnen.

## Nachtrag 12.11. ~10:45: Kreis-Regler gedrosselt (Nutzer: ja)
- `rcpark-kreis_regler` gestoppt (Quota ~70 % der Woche, Reset 15.11. 9:00; Kreis brachte kaum sichtbaren Gewinn). Laufende Runden (kreis_a*) laufen zu Ende, es startet keine neue.
- Wieder einschalten: `JOB_GPU_MB=0 tools/job_start.sh kreis_regler /media/oem/scan/rc-park_kreis/kreis_regler.log python3 tools/kreis_regler.py kaufhaus_grob3 --gpu_ziel 101 --max 4` (Originalbefehl; JOB_GPU_MB vorher gegen den alten Dienst pruefen).
- Erker-Netzrippen: neuer Weg `modelle/METHODE_MESSEN_DANN_BAUEN.md` (Pixelpicks je Rippe, Fotos 6171/6164/6161, Kurve anpassen, dann bauen). rippen_bogen mit Standardwerten ist der am 10.11. verworfene Ansatz und aus objekt.json wieder entfernt. Beobachtungseintrag in masstabelle.json (2026-11-12) vorhanden.

## Nachtrag 12.11. ~13:30: Erker-Rippen (Ziel: in H0 gut erkennbar)
- Neu: `tools/epilinie.py` (Epipolarlinie), `tools/kante_3d.py` (Kante aus 2 Fotos als 3D-Spline), `modelle/METHODE_MESSEN_DANN_BAUEN.md`, Generator `rippen_pfade` + `kappe_rueck` in `tools/baukasten_gen.py`. Messpunkte `M-6171-002..005` (L/R Eckknoten, Kreuzung X, Fuss E); `M-6171-001` UNBESTAETIGT. Nichts committet.
- Zwei Konfigurationen in `objekt.json` (erker_polygon:1.unterbau): (a) BESTANDEN-Stand: `rippen_pfade` mit `vor` -0,03, b 0,12, KEIN `kappe_rueck` -> alle Pruefungen bestanden, Rippen im Render kaum sichtbar; (b) SICHT-Stand (aktuell in der Datei): `kappe_rueck` 0,07, `vor` 0, b 0,16 -> Rippen klar sichtbar (Render 6171/6259), aber 2 Pruefungen rot: Unterbau-Reichweite z 7,6 (1,14 < 1,15) und z 6,6 (0,62 > 0,60); beide Soll aus der Wolke (Quellen-Blindheit fuer Rippen).
- OFFEN, Nutzerentscheid: diese zwei Sollwerte mit der Fotomessung (M-6171-002..005) als neuer Quelle anpassen (+ `historie`)? Bis dahin Modell "NICHT freigeben".
- Bekannte Maengel Sicht-Stand: Rippen einstraengig (Foto dreistraengig), B als Spiegel von A (R-Knoten ~0,1 m daneben), Kappen nicht konkav, Schraegflaechen und steile Rippen C/D fehlen, Rippenbreite 0,16 m ueberhoeht (ANNAHME fuer H0).
- Regression (tools/baukasten_gen.py geaendert): identisch (vor `kappe_rueck`, Standard 0 aendert nichts).

## Nachtrag Erker-Rippen (12.11. mittags, nicht committet)
- Sollwerte z 7,6 (1,10..1,4) und z 6,6 (0,4..0,65) mit Nutzerfreigabe angepasst (historie), Abnahme besteht komplett. Nutzer: Ornament nie an der Wolke pruefen; es geht um Strukturgenauigkeit, nicht um Druckbarkeit/Verbreitern.
- Neu: `tools/kante_auf_flaeche.py` (Pixelpfad EINES Fotos -> Modellflaeche, an Bogen A geprueft: Median 2,1 cm). Rippen R2/R4 (linke Flaeche) in objekt.json (rippen_pfade, ANNAHME, nicht am 3. Foto geprueft); R1 war Duplikat von C (entfernt); R3b bricht die Druckpruefung (93 Koerper).
- Generator: Breite je Rippe streut +-8 % (bw_), sonst Splitter. b 0,07 (am Foto gemessen 0,05-0,08) bricht noch die Druckpruefung -> b 0,10.
- Knoten: 6171-links = 6259-aussen-links (3 Kameras); 6259-Mitte = 6171-rechts. Der vom Nutzer markierte Bogen (6259 Mitte -> rechts unten) gehoert zur RECHTEN Schraegflaeche (nur gespiegelt). Es fehlen: rechte Flaeche gemessen, lange untere Boegen, Buendel am Fuss, ~14 weitere Rippen der Front. Foto-F1/Realitaets-% nicht neu gemessen.
- Renders: Scratchpad render4.py (Tiefenkanten), Vergleich Foto|Modell vor jeder Aussage ansehen.

## Nachtrag Rippen unter Erker (12.11. abends)
- Methode umgestellt: KEINE Tiefenmessung je Rippe mehr; Lage im Foto (Rippenmaske = schwarz neutral + Gold, Putz faellt weg -> Skelett) + Projektion auf die Flaeche. Werkzeuge: `kanten_ketten.py --farbe band`, `luecken_rippen.py` (ungedeckte Rippen, `--maske gold` fuer Buendel), `pfade_nachfuehren.py [--breite]` (Pfade auf Rippenmitte, Breite je Pfad = 0,72 x Maskenbreite).
- Ergebnis: Pfade sitzen auf Rippenmitte (Verschiebungen 0,3-24 px, max 5 cm), o10 ohne Haken, 4 Fussrippen + 3 Zwillingsrippen, Abnahme gruen (Commit 1dd8367e). rippen_f1 0,280 / Recall 0,572 unveraendert: Mass zaehlt Goldkanten (3-4 je Rippe), nicht Rippenmitten.
- Offen: Profilierung (Goldkanten), dichte Fussbuendel (Maske verschmilzt; Rippen dort ~2-3 cm breit), untere Randleiste (Wolke-Veto). Ziel "extrem gut in H0 erkennbar" NICHT als erreicht erklaert; Urteil Nutzer am Bild.
