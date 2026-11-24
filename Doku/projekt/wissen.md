# 📚 Wissen verwalten: ablegen, finden, nicht doppelt bauen  ← [PROJEKT.md](../../PROJEKT.md)
Werkzeuge: `tools/wissen_suchen.py` (Suche mit Rangfolge) · `tools/werkzeug_aehnlich.py` (Doppelgaenger-Werkzeuge) · `tools/wissensbaum_luecken.py` (Vollstaendigkeit) · `tools/wissen_ablage_pruefen.py` (Ablage-Tor) · `tools/wissen_wiederfinden.py` (Nachweis Recall@5) · `modelle/WIDERSPRUECHE.md` · Vorschlag fuer alle Projekte: `tools/claude_mds_vorschlag/`

## Gilt
- Vor jedem neuen Ansatz, jedem Agentenauftrag und jedem neuen Werkzeug: `python3 -I tools/wissen_suchen.py <Befund in eigenen Worten>` und `python3 -I tools/werkzeug_aehnlich.py "<Befund>"`. Die TOP-5-Zeilen kommen woertlich unter "Vorarbeit" in den Auftrag [Skill kette-schleife 3., modelle/VORLAGE_BAUTEIL_RUNDE.md]
- Jedes neue `tools/*.py` nennt im Kopf `Verwandt/Vorlaeufer: ...` ("keine", wenn die Suche nichts fand). Der Schnelltest prueft das fuer Werkzeuge ab 25.11. (`werkzeug_aehnlich.py --kopf-pruefen`, Basis `tools/werkzeug_basis.json`)
- Wissen liegt nach Thema im Baum, nicht nur im Objekt-Register. Jeder Register-, Erkenntnis-, Logbuch-, Archiv- und Memory-Eintrag hat eine Baumzeile; das prueft `wissensbaum_luecken.py` (= 0). Ein Ast ueber dem Budget bekommt einen Unterast, nie verdichten
- "0 fehlend" gilt nur mit dem Werkzeug, nie nach einer Stichprobe von Hand oder aus Auszuegen von Explore-Agenten
- Wissensdateien werden eingecheckt. Was nur auf einem Rechner liegt, findet der andere nicht. `wissen_ablage_pruefen.py` meldet nicht eingecheckte Dateien und Verweise darauf. Fremde Dateien entscheidet der Nutzer
- Register-IDs vergibt man eindeutig. Neue Doppelungen sind rot (Sperrklinke `tools/wissen_ablage_basis.json`). Parallele Agenten nehmen sonst dieselbe "naechste freie" ID (L55 5x, L-KR28 5x)
- Hat dasselbe Mass mehrere Werte, kommt der Fall als Zeile mit Status in `modelle/WIDERSPRUECHE.md`, auch wenn er geklaert ist. Vor dem Rechnen mit einem Mass dort nachsehen
- Fehlsuche = Lernstoff: Wer das richtige Wort erst im zweiten Anlauf findet, traegt es als Synonym ein (`tools/wissen_synonyme.json`). Den Fall traegt er mit natuerlichen Suchwoertern in `tools/wissen_wiederfinden.json` ein
- Nachweis statt Behauptung: `wissen_wiederfinden.py` (Recall@5 der Verlustfaelle >= 0,9) laeuft im Schnelltest. Der Kontrollsatz wird nie zum Abstimmen benutzt

## Versucht
- 20.11. · Wissensbaum aus Auszuegen von Explore-Agenten, Ast-Budget 110 Zeilen → ✗ · Der Baum meldete "0 fehlend", tatsaechlich fehlten 942 Eintraege (66 von 125 Registerabschnitten beim Verdichten verloren) · Werkzeug `wissensbaum_luecken.py` statt Stichprobe [ERKENNTNISSE §Bildwert/Sweet-Spot]
- 24.11. · Wortsuche ohne Synonyme ("Bildauswahl", Quelle sagt "Teilmenge/Fotoauswahl") → ✗ · Bildwert/Sweet Spot (Register BM/BN, `foto_wichtigkeit`, `bildwert`, `sweetspot`, `dicht_bildwahl`) neu beauftragt · Synonymgruppen + Memory-Archiv in `wissen_suchen.py`
- 24.11. · Suche als ODER ueber Woerter ohne Rangfolge → ✗ · "Formmass Flaeche" gab 164 Baumtreffer, oben bahn-anlage (Druckflaeche) · ↺ Rangfolge: IDF, Abdeckung aller Begriffe, Stamm/Teilwort, Fuellwoerter weg, Meta-Werkzeuge ausgeschlossen
- 24.11. · Nachweis Recall@5 auf 12 echten Verlustfaellen → ✓ · Alte Suche 6/12, nur neue Rangfolge 7/12, Rangfolge + gelernte Synonyme 12/12 · ⚠ Kontrollsatz (8 Faelle, nicht abgestimmt): vorher 4/8, nachher 4/8. Der Gewinn kommt aus den gelernten Synonymen, die Rangfolge verallgemeinert noch nicht [ERKENNTNISSE §Wiederfinde-Nachweis]
- 24.11. · Doppelgaenger-Suche ueber den Wortschatz der Werkzeugkoepfe (TF-IDF, Stamm + 4-Gramme fuer Komposita) → ✓ · 15 von 129 Werkzeugen ab 18.11. haben einen aehnlichen aelteren Vorlaeufer, den ihr Kopf nicht nennt. Nur 1 von 873 Werkzeugen nannte ueberhaupt einen Vorlaeufer · `werkzeug_aehnlich.py`
- 24.11. · Synonym-Teilwort in beide Richtungen ("Flaeche" in "Flaechenmass") → ✗ · Ein allgemeines Wort zog eine Fachgruppe mit; "Drahtgitter" (Kantenmodell) zog die Oberleitungs-Gruppe · ↺ nur Suchwort ⊃ Gruppenwort; ein genauer Gruppentreffer hat Vorrang
- 24.11. · Spec nur lokal (`archiv/SPEC_FLAECHENMASS`, 11.11., nie eingecheckt; `tools/flaechen_mass.py` verweist darauf) → ⚠ Falle · `formsitz.py` wurde 24.11. als "trennscharfes Formmass" neu erdacht (anderes Verfahren: Tiefen-IoU gegen die Wolke statt SAM-Flaechen; Oberkontur ~ iou_silhouette) · Ablage-Tor
- 24.11. · Geklaertes Mass nicht als Widerspruch vermerkt → ⚠ Falle · Martinstor-Spitze: 31.10. Laser 54,8 m (60-66 m widerlegt); 19.11. Kettentest rechnete mit "Turm ~60 m" und dem LoD2-First 45 m als Turmhoehe · `modelle/WIDERSPRUECHE.md`
- 24.11. · Bildwert-Stufe 1 mit Teilmenge der Fotos → ✗ wiederholt · Die Lehre "Teilmengen verlieren Dichte" (Register BM, 02.11.) stand nur im Martinstor-Register; Formsitz lag bei 60-70 % von "alle" [Commit 91a986e83]

## Offen
- Kontrollsatz-Recall (4/8) heben, ohne an ihm abzustimmen: Relevanz je Eintrag (Abschnitt) statt je Zeile; Logbuch-Absaetze als Einheit
- Nicht eingecheckte Archivdateien im Haupt-Checkout (SPEC_FLAECHENMASS, STAND_2026-11-10_NACHMITTAG, STAND_2026-11-12_VORMITTAG_lang) und QUALITAETSSTUFEN.md (Verweis aus `tools/qualitaetsstufen.py`, Datei fehlt im Repo): Nutzer entscheidet
- 33 doppelt vergebene Register-IDs (49 Doppelungen, REZEPT 42) umbenennen. Das geht nur mit Nachziehen der Baumverweise und braucht den Nutzer
- Weitere Familien mit Doppelgaenger-Verdacht pruefen: Oeffnungen (oeffnungen_bogen/-wandbild/-aus_kanten, nischen_fenster, schlitze_wandbild), Haufen (haufen_am_foto/-herkunft/-klaeren), `brennweite_waehlen` gegen `exif_brennweite`
- Generische Fassung nach `~/git/claude-mds` (Skill doku-pflege) uebernehmen. Danach werden die rc-park-Kopien zu Aufrufen
