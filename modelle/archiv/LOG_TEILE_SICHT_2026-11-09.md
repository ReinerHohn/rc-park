# Log teile_sichtpruefung 2026-11-09 (Agent)

Auftrag: Ein Bauteil darf nicht "trifft" gelten, nur weil EIN Nahfoto passt (Runde 5: 6120 passte, 6261 zeigte Westumriss ueber dem Nachbarhaus, Erker teilweise, EG-Fenster Bogen 3 daneben).
Neu (nur neue Dateien): `tools/teile_sichtpruefung.py`, `tools/test_teile_sichtpruefung.py`, Bilder `modelle/kaufhaus_grob3/audit/teile_sicht/{runde5,formen_helme,formen_saeulen}`.

## Was das Werkzeug tut
- Teil-STL je aktives Bauteil ueber den Generatoraufruf aus objekt.json mit `NUR_BAUTEIL` (kein Objektname im Code). Teile ohne eigenes Netz (nur Schnitt, abhaengig von Vorgaenger) -> UNGEPRUEFT.
- Fotoauswahl: alle Kameras der kam_lot2.json grob gerastert (GPU), je Teil unverdeckte + nicht streifende Pixelflaeche, verschiedene Blickrichtungen (>= 15 Grad), dazu `--pflicht`-Fotos.
- Mass je (Teil, Foto) in der entzerrten Lochkamera (k1): hit (Modellkante hat Fotokante), Lagesuche +-1,2 m (gewinn/versatz), Himmel-Anteil, Wolke hinten, und - Nutzerergaenzung Helm - **Gegenrichtung**: recall (Fotokanten im Umfeld ohne Modellkante) und sil_recall (Himmelssilhouette ohne Modellkante).
- Urteil: GRUEN (>= 2 auswertbare Fotos aus >= 2 Richtungen, Anteil schlechter Fotos < 0,34), ROT, UNGEPRUEFT (zu wenig Flaeche/Richtungen). Gate Exit 1 bei ROT.
- Zweiter Einsatzort: `--formen DATEI [--adapter helme|saeulen|teile]` prueft Formfit-Ergebnisse der Kantenkette (min. 3 Fotos, Wolke verdeckt, Umfeld = halbe Teilbreite).

## Ergebnisse (siehe Abschlussbericht des Agenten; Zahlen aus teile_sicht.json je Ordner)
- Runde-5-Stand (git 928c312): ROT 20, GRUEN 2 (fensterreihe:og, stl_teil:figuren), UNGEPRUEFT 4. Alle verlangten ROT sind ROT (staffelgiebel:west, erker:0/1, fensterreihe:eg1, helm_w/o, GANZ).
- Synthetik (Schwellen dort kalibriert): erker:0, helm_w korrekt GRUEN; 1 m seitlich, 1 m hoch, 20 % gross, halbe Breite ROT.
- Formfit: helme.json beide ROT (Fuss zu schmal). **Saeulen R 0,437: nicht GRUEN, alle ROT (OFFEN)** - siehe Fehlerliste.

## Fehlerliste (eigene Sichtung der Blaetter)
1. Saeulen ROT trotz sichtbar passender Zylinder in 6261: glatte Zylinder haben in der Stabilitaetskarte kaum Kanten (hit ~0,5), Umfeld enthaelt nicht modellierte Arkadendetails (recall niedrig), Handfotos mit Kamerafehler > 0,1 m. Naechster Schritt: Farbgradient an der Silhouette (Maximum quer zur Kante) statt binaerer Stabilitaetskarte; Test erst synthetisch.
2. Spezifitaet gering: 20 von 22 Teilen ROT. Teilweise echt (Westgiebel ragt nachweislich ueber den Himmel, Fenster Bogen 3 / Tuer daneben, Helmkegel zu schmal), teilweise Messartefakte: Handfotos (nubia) mit Kameraresten, Passanten (wolke_vorn nicht gewertet), Himmelsmaske auf Nahfotos oft unplausibel (dann None).
3. Rasterartefakt: in Nahaufnahmen aus < 5 m (GANZ i_04, Giebel) erscheinen rote Strahlenbuendel (sehr flache Dreiecke, Modell fast streifend). Zweite Differenz fuer Tiefensprung eingebaut, Buendel bleiben teils -> hit in diesen Fotos zu niedrig. Abhilfe offen: Fotos mit z_med < 5 m fuer hit nicht werten.
4. gaubenreihe:* und quader:eg1_*nische: allein nicht baubar -> UNGEPRUEFT (Gauben brauchen satteldach als Vorgaenger). Abhilfe: Vorgaenger mitbauen und Teilnetz per Dreiecksdifferenz bilden.
5. Wolke (kanten3d_k80) ist duenn: wolke_hinten 0,3-0,6 an einzelnen Fotos (Helm i_04) kann Wolkenluecke sein; nur zusammen mit anderen Befunden gewichten.
6. Schwellen thr_gewinn 0,15 / thr_recall 0,45 / thr_sil 0,55 / thr_himmel 0,06 sind synthetisch, nicht an echten Referenzen verifiziert (es gibt noch keinen als sicher richtig bestaetigten Referenzdatensatz ausser fensterreihe:og).
7. Laufzeit stark von GPU-Auslastung anderer Agenten abhaengig (56 s bis 833 s fuer denselben Lauf).

## Vorgeschlagene Zeilen (nicht eingebaut)
bauen_abnehmen.sh, nach dem Pruefstand-Block, vor test_regeln_cb:
```
D=/media/oem/scan/rc-park_daten/kaufhaus_alle   # besser: objekt.json "teile_sicht": {kameras,bilder,stabil,wolke}
$PY -W ignore -I tools/teile_sichtpruefung.py "$1" --kameras $D/sfm/kam_lot2.json --bilder $D/bilder --stabil $D/stabil --wolke $D/kanten3d_k80.npz --pflicht ip_IMG_6120.jpg,ip_IMG_6261.jpg | tail -4 || { echo "TEILE-SICHT: Bauteil ROT"; [ "$RC" = "0" ] && RC=4; }
```
gitter_kette.sh: STUFEN "... formen formsicht wiederh ..." und
```
if stufe formsicht; then
  log "5b formsicht (Regel 9d): Helme/Pfeiler gegen >= 3 Fotos aus >= 2 Richtungen"
  for X in "helme:$K/helme.json" "saeulen:$K/g3_formen.json"; do $PY -I tools/teile_sichtpruefung.py kaufhaus_grob3 --formen ${X#*:} --adapter ${X%%:*} --out $AUD/formsicht_${X%%:*} --kameras "$KAM" --bilder $D/bilder --stabil $STAB --wolke $D/kanten3d_k80.npz >> $K/formen.log 2>&1 || log "   FORMSICHT ${X%%:*}: Teil ROT"; done
fi
```

## Nachtrag: Synthetik-Befund (ehrlich, Test steht auf FEHLGESCHLAGEN)
- erker:0 und zylinder:helm_w: korrekt GRUEN, alle 4 Fehlervarianten ROT (1 m seitlich, 1 m hoch, 20 % gross, halbe Breite).
- **fensterreihe:og (periodische Fensterreihe): korrekt GRUEN, aber ALLE Fehlervarianten ebenfalls GRUEN** (hit 0,92-0,98, recall 0,78-0,83). Periodische/dichte Strukturen sind fuer Kantenpraesenz-Masse blind: ein um 1 m verschobener Satz trifft die naechste Fensterkante. Folge: das GRUEN von fensterreihe:og (und stl_teil:figuren) ist KEIN Beleg, dass das Teil passt. Eine Aussenkontur-Masszahl (rand_hit) half nicht (0,86-0,97 auch verschoben), bleibt als Zusatzfeld im JSON.
- Naechster Schritt (nicht gebaut): identitaetsbehaftetes Mass statt Kantenpraesenz, z. B. Fensterverteilung/Lage gegen Wolkenebene + Ortho-Muster (Periode und Phase aus muster_fit), oder Farbgradient quer zur Kante mit Phasenpruefung.
- Echt: ROT ist damit belastbar fuer Teile, bei denen Himmel/Wolke/Silhouette greifen (Westgiebel, Helme, Erker), GRUEN ist nur "kein Widerspruch gefunden".


## Runde 2 (2026-11-09 abends, Agent): Spezifitaet, periodische Strukturen, Saeulen, GPU/Laufzeit
Dateien geaendert: `tools/teile_sichtpruefung.py`, `tools/test_teile_sichtpruefung.py`; neu `tools/kamera_sfm_guete.py` (Reprojektions-Guete aus sparse/0, nur Ersatz). NICHT angefasst: baukasten_gen.py, objekt.json, masstabelle.json, bauen_abnehmen.sh, bauteil_sichtliste.py (Formel kopiert, siehe 1.).
Scratch: `/media/oem/scan/rc-park_daten/kaufhaus_alle/agent_scratch_ts2/` (r5 = git 928c312, r6 = HEAD 41f63e9/a01e768; out_f_r5/out_f_r6 = Endlauf, tab_final.txt, synth9_*.log/synth10_*.log).

### Was geaendert wurde und warum (jede Schwelle am Synth begruendet)
1. **Fotowahl** wie `bauteil_sichtliste.py`: Wert = sichtbare nicht streifende Pixel x Sichtanteil x Bildanteil x (1 - Fremdverdeckung)^2, Fremdverdeckung = Wolke > `fremd_m` 0,5 m vor dem Teil (Gewoelbe, Passanten); Nahfotos (mittlere Tiefe < `min_z` 5 m) und Posen 'unbrauchbar' (Gueterating `audit/kamera_guete_lot2.json`; 'grob' nur bei fehler_m < tol_m) werden nicht gewaehlt; Nahfotos zaehlen auch nicht als auswertbar (Strahlenbuendel, Fehlerliste 3). Vorwahl wird gecacht (Hash Netz+Kameras+Wolke): kalt ~80 s, warm 1 s. Sichtliste selbst nicht aufgerufen (Skript ohne importierbare Funktion), Formel uebernommen - bei Aenderung dort hier nachziehen.
2. **Kamera-Restversatz** (GANZ-Verschiebung je Foto, `--kamera-korrektur`) gebaut, aber **Standard AUS**: SfM-Posen sind mm-genau (Koordinator, kamera_guete_lot2), ein abgezogener Versatz wuerde Modell-/Rahmenfehler verstecken. Reprojektionsfehler allein (kamera_sfm_guete) trennt nichts (alle ~1 px, Memo 7.11.).
3. **Lagesuche als Profil** statt Einzelmaximum: Kantentreffer ueber +-1,8 m (2D, 0,1-m-Raster, 3x3 geglaettet); Maximum auf Haelfte A der Modellkanten, Gewinn gegen das beste Nah-Maximum (|s| <= 0,25 m) auf der zurueckgehaltenen Haelfte B; Maximum muss gegen seinen Ring (0,4-0,8 m) eine Prominenz >= 0,03 haben (`thr_prom`; Dichtegefaelle im Foto, Maximum am Rand, wird so kein Versatz); `lift >= 0,12` (`lift_gut`) hebt einen schwachen Versatzbefund auf. Beleg: Synth, korrekte Teile haben lift 0,15-0,5, versetzte 1 m < 0,10 (Luecke 0,10-0,15, Mitte 0,12). Tie-Erkennung (`profil_tie`) bei periodischen Teilen: Nebenmaximum >= 0,5 m gleich hoch -> Foto nicht auswertbar (ehrlich UNGEPRUEFT statt blindes GRUEN).
4. **Periodische Reihen**: Endelement-Test (erstes/letztes Element, hit und lift gegen 0,5-m-Decoys) gebaut und GEMESSEN: trennt NICHT (korrekt 0,99/0,26, 1 m versetzt Reihenende nicht auswertbar bzw. 1,0/0,04 beim Erker; bei Decoy-Dichte 0,8 saettigt jede Toleranz). Messfeld bleibt in teile_sicht.json (`ende_hit`, `ende_lift`), Schwellen inaktiv (`thr_ende` 0, `thr_ende_lift` -9). Aussenkontur `rand_hit` nur noch Messfeld (`thr_rand` 0). Was Fensterreihe:og am Synth trennt: das Lagesuche-Profil (Punkt 3), nicht die Reihenenden.
5. **Saeulen/glatte Koerper**: `glatt` = Normalen-Resultierende < 0,85 (gekruemmt) UND < 20 % Innenkanten; dort Silhouetten-Gradient (Median ueber den Umriss von max |Gradient . Aussennormale| im Fenster +-tol, geteilt durch dieselbe Groesse an 4 um 0,35 m verschobenen Umrissen) statt hit/Lagesuche. `thr_grad` 1,1: Saeulen korrekt 1,4-2,1, 1 m seitlich 0,0-1,1 (Mittel), 150 % Radius 0,5-1,2. Bei 1,25 wurde die korrekte Saeule 2 in 2 von 3 Seeds ROT -> 1,1. Unsichtbar bleiben (Grenze, nicht Fehler): Hoehenversatz 1 m und Radius +20 % bei glatten Zylindern; halbe Saeulenbreite ist zu duenn (UNGEPRUEFT, < min_px).
6. **Recall** (Fotokanten im Umfeld ohne Modellkante) nur noch fuer freistehende runde kompakte Teile (`rund`, Ausdehnung <= 3 m, `frei` = Silhouettenanteil des Randes >= 0,5): eingebettete Teile (Tuer in der Wand) haben unmodellierte Details im Umfeld (Fehlerliste 1).
7. **Himmel in mehreren Fotos** (Koordinator-Hypothese 1): >= `himmel_n` 2 auswertbare Fotos mit himmel > 0,06 aus >= 2 Richtungen = harter Befund. Synth: korrekte Teile 0 Fotos mit Himmel (alle Seeds), versetzt/vergroessert Helm und Erker 1-5. Echt R5 (Zaehlung aus teile_sicht.json): staffelgiebel:west 4, helm_o 3, erker:1 meist 1 (Wolke hinten), laube_rueck/rumpf_eg/Tuer/eg2 <= 1: Hypothese trifft fuer Giebel und Helm, fuer Erker:1 nicht (hier tragen versatz/wolke_hinten). Das Kriterium bleibt; es ersetzt nichts.
8. **Wolkenbeleg als zweite Spalte** (Koordinator 2): `--wolke-voll` (j_voll_lot2.npy, VOLL), Definition wie konvergenz_bericht (nah 1 m, beleg 0,15 m, GPU-knn), Feld `wolkenbeleg` je Teil, nicht im Urteil. Siehe Tabelle.
9. Test: `--stand r5 r6`, Scratch auf der Datenplatte, Wolkenbeleg-Spalte, Synthetik mit **echtem Fotoersatz** (Albedo je Bauteil + Schattierung + Textur + Klutter, Stabilitaetskarte = Wahrheitskanten mit 30 % Luecken + Canny-Klutter, Decoy-Rate 0,5-0,8 wie echt (0,3-0,7); Himmel = Nichtmodell) statt nur Kantenbild; 3 Saeulen R 0,437 aus g3_formen.json mit passenden Kameras (7-26 m, Bildmitte, nicht schlecht); `halbe_breite`/`seitlich_05m` nur Info (siehe Grenzen).

### Synth-Ergebnis (3 Seeds, thr_grad 1,1; Teile fensterreihe:og, helm_w, erker:0, 3 Saeulen)
- korrekt: 12 von 12 GRUEN in jedem Seed. 1 m seitlich: 12 von 12 ROT in jedem Seed (og: ROT trotz Periodik, Prominenz 0,04).
- hoch 1 m: og/Helm/Erker ROT (Helm nur ueber Himmel; Saeule unsichtbar, Info). gross 20 %: Erker ROT; Helm/Saeule/og je nach Seed GRUEN (liegt unter 0,1 m bei Saeule; Reihe/Helm Nachweisgrenze).
- halbe Breite: Erker ROT; Helm und Saeule 3 GRUEN bei thr_grad 1,1 (bei 1,25 ROT, dafuer Saeule 2 korrekt zweimal ROT) - offen.
- 0,5 m seitlich: Erker bleibt GRUEN (Nachweisgrenze zwischen 0,5 und 1 m); Saeulen/Helm ROT.
- Frueherer Befund bestaetigt: Kantenpraesenz allein ist bei Decoy-Rate 0,8 blind (hit 0,98 korrekt gegen 0,90 versetzt).

### Beweistabelle Echt (Endlauf out_f_r5 / out_f_r6, Schwellen wie oben)
Stand r5 (928c312): erwartet ROT: staffelgiebel:west ROT, erker:0 ROT, erker:1 ROT, zylinder:helm_w ROT, helm_o ROT, GANZ ROT, **fensterreihe:eg1 GRUEN (Fehlstelle)**. Wolkenbeleg eg1 0,0 (Daten 1,0) - die modellfremde Wolke sieht den Fehler, die Sichtpruefung nicht: Foto-Kanten von Bogen 3 liegen nahe an Nachbarfenster-Kanten.
Erwartet nicht ROT: bruestung GRUEN, fensterreihe:og GRUEN (4/4), **konsolenreihe:balkon ROT, fensterreihe:eg1_tuer ROT** -> 2 falsche ROT (Ziel <= 1, NICHT erreicht).
- Konsolen: ROT aus 2 von 4 Fotos mit Versatz 1,2-1,7 m, Prominenz 0,25-0,3 und hit 0,31-0,34 (n_11, 6120); Brüstung im selben Foto e_12 hit 0,98. Wolkenbeleg 0,72 (Koordinator R6 0,82) spricht fuer passend. WIDERSPRUCH Foto vs Wolke - nicht gemittelt, offen (naechster Schritt: Detailrender Konsolen gegen n_11/6120 nebeneinander).
- Tuer r5: Wolkenbeleg 0,156 stuetzt ROT; die Erwartung 'passt' gilt eher fuer r6 (Wolke 0,77, Sichtpruefung GRUEN 4/6). Erwartungsliste fuer r5 ist fuer die Tuer fraglich.
Stand r6 (41f63e9): erker:0/1 ROT (Wolke 0,29/0,26), og GRUEN (6/6), Bruestung GRUEN, eg1 GRUEN (Wolke 0,94), eg1_tuer GRUEN, helm_geschweift:o GRUEN, helm_geschweift:w ROT (wolke_hinten in 3 Fotos; Wolke 0,44 mittel), **konsolenreihe ROT** -> 2 falsche ROT (Ziel <= 1, NICHT erreicht). Gesamt R6: ROT 13, GRUEN 8, UNGEPRUEFT 8 (vorher 19/3/7); R5: ROT 18, GRUEN 4, UNGEPRUEFT 4 (vorher 20/2/4).
Spezifitaet damit besser (R6 19 -> 13 ROT, Foto-/Pose-Artefakte gefallen), aber das Gate-Ziel ist verfehlt. **Kein Gate einbauen** bevor Konsolen (Foto/Wolke-Widerspruch) und helm_geschweift:w geklaert sind.

### GPU-Budget und Laufzeit (gemessen, nvidia-smi alle 2 s, `agent_scratch_ts2/gpu_*.csv`)
Einzellauf r5 kalt (Vorwahl neu, Himmelsmasken im Cache): 157 s; r6 kalt 230 s (zwei parallel); warm (Vorwahl gecacht) ~140 s. Spitze 644 MiB gesamt bei 183 MiB Grundlast = ~460 MiB eigener VRAM, GPU-Auslastung im Mittel ~75 %. `JOB_GPU_MB=1000` reicht (1500 stand in der Voreinstellung; bei 8 parallelen Jobs Laufzeit 360 s). Ziel < 5 min erreicht (allein). CPU-Teile: Himmelsmasken (foto_pick, gecacht), kantenpixel/Lagesuche (numpy).

### Offen / Grenzen (ehrlich)
- Konsolen und helm_geschweift:w: Foto sagt ROT, Wolke sagt passend/mittel. Nicht beigelegt.
- fensterreihe:eg1 (R5) wird nicht gefunden (Kantenpraesenz blind bei dichter Fassade); Wolkenbeleg faengt es. Vorschlag: Wolkenbeleg < 0,35 bei Datenanteil >= 0,5 als eigenes hartes Kriterium - erst nach Synth (Wolke-Synth fehlt) und 2. Objekt.
- Nachweisgrenze Versatz ~0,5-1 m; 10-cm-Genauigkeit prueft dieses Werkzeug nicht.
- Versatzflags mit kleinem Gewinn (0,03-0,1) sind in echten Fassaden rauschanfaellig; die Schwellen stammen aus dem Synth, dessen Foto-Ersatz eine Annahme ist (ANNAHME: Klutterdichte so, dass Decoy-Rate 0,5-0,8).
