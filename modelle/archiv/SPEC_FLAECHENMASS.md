# Spec: Flächenmaß (Formvergleich über Flächen statt Kanten)

Nutzerentscheid 11.11., 13:35: „Ja“.

## Anlass
Der Foto-F1 zählt Kanten und ist deshalb blind für Formfamilien:
- Treppe gegen Sägezahn: −0,002
- Rechteck gegen Bogen an der Laubenstirn
- Balkon-Stirnen: +0,004

Nutzerfunde vom 11.11. in `masstabelle.json` (`formfamilie_test`). Am 9.11. bewertete der Nutzer die Segmentierung mit SAM als „bester Stand“ (Memory `sam-segmentierung-vielversprechend`, `tools/editor_modell.py sam_flaechen`, `tools/sam_arches.py`).

## Idee
Je Foto und Teil wird verglichen, ob Foto und Modell im Teilausschnitt dieselbe Flächenaufteilung zeigen:
- **Foto:** SAM `facebook/sam-vit-large` (transformers mask-generation, `HF_HOME=/media/oem/scan/tools_src/hf_cache`, ca. 3,5 GB VRAM) zerlegt den Ausschnitt um die projizierte Teilbox (+30 % Rand) in Flächen. Kacheln wie im Memory, wenn der Ausschnitt groß ist.
- **Modell:** Render aus derselben Kamera (`render_kern.dreiecke_rastern`, gleicher Rahmen wie `teil_fotoform`). Daraus werden Flächen gebildet:
  - zusammenhängende Bereiche gleicher Fläche bzw. Normalenklasse des Zielteils,
  - „Loch“ = Bereich in der Teilsilhouette-Hülle, in dem man durch das Teil hindurchsieht (Tiefe springt weit nach hinten oder ins Leere).
- **Maß:**
  - Je Modellfläche die beste SAM-Fläche suchen (IoU), dann den mittleren IoU flächengewichtet über die sichtbaren Teilpixel.
  - Zusätzlich die Silhouette des Teils gegen den Himmel bzw. Hintergrund prüfen, für Giebel- und Dachkonturen: Grenze aus der SAM-Himmelsmaske, falls erkennbar. Ein einfacher Weg ist die Helligkeit bzw. eine Maske „oberste Fläche“.
  - Verdeckung wie in `teil_fotoform`: Pixel, die Modell oder Wolke verdecken, zählen nicht.
- Ausgabe je Teil und Foto: `iou_flaechen`, `iou_silhouette`, `n_flaechen_modell`, `n_flaechen_foto`, `px`. Im Teil-`_gesamt` pixelgewichtet.

## Werkzeug
- Neues `tools/flaechen_mass.py`. Aufruf: `objekt --teile_dir DIR --nur TEIL --fotos A,B,C --aus JSON [--bilder]`.
- `--bilder` gibt je Foto ein Bild aus mit SAM-Flächen | Modellflächen | Zuordnung (farbig).
- SAM-Masken je Foto und Ausschnitt in den Cache unter `/media/oem/scan/rc-park_tmp/flaechen_cache/` legen. Sie hängen nicht vom Modell ab. Schlüssel: Fotodatei + Ausschnitt + Parameter.

## Beweis (Pflicht): `tools/test_flaechen_mass.py`
Alle drei Fälle mit Vorher- und Nachher-Teilen. Zahlen müssen klar sein (Unterschied ≥ 0,05 im Maß); Bilder selbst ansehen.
1. **Laubenstirn West** (Rechteck statt Bogen):
   - Teil `bogenreihe__laube` bzw. die Teile an der Westöffnung, siehe Nutzerfund in der masstabelle mit `weltpunkt_m` [-4,7; 12,0; 7,5].
   - Fotos, die das Westende zeigen, z. B. `an_handy_2026-11-06_p_handy_11`.
   - Das heutige Modell muss deutlich SCHLECHTER abschneiden als eine Testvariante mit Bogenöffnung und Zwickelwand darüber. Diese Variante darf grob sein: im Worktree eine Wand mit Rundbogenöffnung an der Stirn ergänzen.
2. **Westgiebel:**
   - Sägezahn: Teile vorher aus Lauf a125135 (`teile_r1_vorher*`).
   - Treppe: nachher (Patch `/media/oem/scan/rc-park_kreis/kaufhaus_grob3/patches/staffelgiebel_treppe_a125135.patch`; Nachprüflauf kreis_a131641 erzeugt die Teile).
   - Die Treppe muss besser sein.
3. **Gegenprobe Tor:**
   - a091923 r2, `freiform__tor_b2__ausschnitt`: Das Foto zeigt einen Spitzbogen, nachher wurde er rund gebaut.
   - Nachher muss SCHLECHTER sein.

Zusätzlich die Wiederholbarkeit: zweimal messen, die Werte müssen gleich sein. SAM ist deterministisch; das ist zu prüfen.

## Randbedingungen
- Nur neue Dateien.
- GPU-Regeln aus CLAUDE.md:
  - SAM ca. 3,5 GB.
  - Der Kreis nutzt die GPU parallel, zusammen höchstens 7000 MiB.
  - Start über `JOB_GPU_MB=4000 tools/job_start.sh …`.
  - Im Vordergrund warten (`until grep -q JOB_ENDE …`).
- Kein Commit, nichts löschen, kein Objektname im Code.
- Worktree für Testvarianten unter `/media/oem/scan/rc-park_tmp/flaechen/`, nie in main bauen.
- Lizenz SAM: Eintrag in `modelle/LIZENZ_WERKZEUGE.md` prüfen. SAM ist Apache 2.0; der Eintrag fehlt, falls er nicht da ist. NUR berichten, nicht ändern.
