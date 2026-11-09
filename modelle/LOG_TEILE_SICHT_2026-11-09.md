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
