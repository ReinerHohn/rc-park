# Audit "stille Erfolge" in tools/gesamtkette.py (23.11.2026)

Fehlermuster: Eine Stufe meldet rc 0, "in Ordnung", "GEWINN" oder "BELEGT", hat aber keinen echten Beleg geliefert.
Agent im Worktree-Zweig `worktree-agent-a6c575e6d4faef694`, nur Code und kleine Proben, nicht gemergt.

## Umfang
- In `gesamtkette.py` geprueft: 102 verschiedene `lauf()`-Stufen, 48 `notiz()`-Zeilen und 25 `except Exception`.
- Abgeglichen mit dem fertigen Lauf 1122t (`job_logs/kette-schwabentor-null-1122t.log`, 197 Stufen, 4 rot) und mit `rc-park_daten/schwabentor-1122/gesamtkette.log`.
- Klassen der Pruefung:
  - Beleg geprueft
  - nur rc geprueft
  - rc verworfen
  - nur Existenz geprueft
  - Altdatei taeuscht Frische vor
  - still uebersprungen
- Vorbilder, schon von anderen bearbeitet und hier nicht angefasst:
  - SIFT in zusatzfotos
  - seiten_gewinn
  - Vorbau-Fototor
  - fassaden_kette Steinzone
  - ortho_einzeln
- `modelle/NICHTS_GEBRACHT.md` enthaelt keinen Eintrag zu einem Beleg-Helfer oder zu stillen Erfolgen.

## Rangliste nach Schaden (Form/Lage vor Bericht)
1. **Altstaende des Ebenen-Sweeps** (`bauplan_sweep_fNN`, `vorbauten_fNN`).
   - `fassade_tiefe.py` endet bei rc 2 ("nur 2 Fotos") VOR dem Schreiben.
   - `vorbauten_bauplan` las dann `vorbauten_fNN.json` und `tiefe_fNN.npz` eines frueheren Laufs.
   - BELEGT 1122t 16:28: Fuer f01 gab es weder "kein Sweep" noch "nicht belastbar", also wurde die Datei von 12:25 gelesen.
   - Folge: ein Vorbau aus einem alten Rahmen. Fassadennummern koennen sich zwischen Laeufen verschieben.
   - BEHOBEN.
2. **Fensterkette ohne Frischepruefung.**
   - Betroffen: `fassade/fassaden.json`, `elemente.json`, `audit/fenster_auto.json`, `oeffnungen_auto.json`.
   - Scheiterte fenster_ortho, das Parsing oder fenster_aus_parsing, dann rechneten bauplan und seiten mit dem alten Wandbild weiter.
   - Der Generator baute in diesem Fall die Fenster und Tore des alten Laufs.
   - BEHOBEN.
3. **`bauplan_oeffnungen_aussen`: rc verworfen** (`== 0: pass`).
   - Nach einem Absturz oder ohne feines Wandbild lasen rueckwand_tiefe und loch_gewaende die alte `oeffnungen_aussen.json`.
   - Folge: falsche Rueckwandtiefe und falsche Tueren.
   - BEHOBEN.
4. **Kantenstufe.**
   - Bei rc 4 ("kein Suchraum") werden `kam.json` und `kam_wahl.json` nicht geschrieben, bei weniger als 6 Kameras fehlt `sweep.npz`.
   - Danach rechneten Foto-Tor, bauplan_ebenen, vordach_profil und kanten_fertig mit den Kameras und dem Sweep des Vorlaufs.
   - `bauplan_ebenen` wurde ohne kam_wahl STILL uebersprungen. Eine alte `ebenen/ebenen.json` speiste oeffnungen_aus_kanten.
   - BEHOBEN.
5. **Stufe mono.**
   - Sie lief, sobald `fassaden_kette.json` existierte, auch wenn fassaden_kette in diesem Lauf gescheitert war.
   - Sie rechnete dann auf altem Relief und schrieb die alte JSON mit NEUEM Zeitstempel zurueck. Damit war der Altstand als frisch getarnt.
   - BEHOBEN.
6. **Haupt-SfM `iphone_sfm.py`.**
   - GPU-SIFT ohne Pruefung auf fehlende Bilder. Das ist das Geschwister von Vorbild 1.
   - Bei SiftGPU-OOM fehlen Bilder still in der SfM. Der Cache bemerkte es erst im naechsten Lauf.
   - BEHOBEN: Die fehlenden Bilder werden auf der CPU nachgeholt, der Rest wird laut gemeldet.
7. **befundliste und neben_details:** Ohne frische JSON stand `befundliste_ergebnis` trotzdem auf ok True. Die Agenten-Schleife haette dann alte Befunde abgearbeitet. BEHOBEN.
8. **koerper_schleife.json:** Ein Altstand stiess Bau und Abgleich an. **hinweis_radar/lotfeld** und **foto_auftrag.json** wurden ohne Frischepruefung gemeldet, der Fotoauftrag geht an den Nutzer. BEHOBEN.
9. BEHOBEN 24.11. (Nachtrag unten): `mono` meldete ok True auch bei 0 Waenden. Der Grund ist sichtbar, weil die Waende einzeln rc 4 melden.
   - `tor_kamera` rc 2: Die Kranzluecke von 168 Grad steht nur als Hinweis im Log. Gilt als Hinweis-Tor, Absicht.
10. OFFEN, Kandidaten fuer den naechsten Agenten:
    - `bauplan_spitze_umriss` rc 4 setzt laterne_foto still auf 3. Es gibt keine eigene Zeile "Laterne nicht gerechnet", nur `erg_` in der Zeile bauplan.
    - BEHOBEN 24.11.: `bauplan_oeffnungen_aussen` meldete "nicht offen (keine Tiefenkarte)" mit rc 0. Eine fehlende Eingabe entscheidet hier "geschlossen".
    - `bauplan_rueckwand` "aus 0 Fenstern -> ANNAHME" ist gekennzeichnet.
    - Die `druck`-Masken `relief/*_putz.npz` haben keinen Frischeabgleich.
    - `sfm_netz.py` und `video_sfm.py` extrahieren ohne Pruefung auf fehlende Bilder.
    - BEHOBEN 24.11. (STL-Beleg in bauen_abnehmen.sh): `dachfoto`/`bauen_mit_fotodach` und `bauen_mit_*` pruefen nur ERGEBNIS, nicht die Frische des STL. Nur der erste Bau prueft `frisch(stl)`.

## Nachtrag 24.11.2026 (Agent-Zweig `worktree-agent-aa0cd9f1f5eb2fd59`, Test `tools/test_stille_erfolge_24.py` im Schnelltest, am alten Stand 9 Faelle rot)
- **Punkt 9 mono, 0 Waende: BEHOBEN.** Zeile `mono` nutzt `kette_beleg.bearbeitet_urteil`: ohne eine Wand mit Mono-Relief ist sie NICHT in Ordnung, mit rc je Wand und den uebersprungenen Waenden (fehlender Messkoerper wird genannt).
- **"nicht offen (keine Tiefenkarte)": BEHOBEN.** `oeffnungen_wandbild.py` markiert einen Bogen ohne Tiefenkarte (oder mit zu wenigen sicheren Zellen) als `unentschieden`, `flach: null`, nicht gebaut, und endet mit rc 3 "UNENTSCHIEDEN". `bauplan_oeffnungen_aussen` wird dadurch rot. `bauplan_innen_oeffnungen` ist ebenfalls rot, die Innenwand-Kette nimmt die Datei aber weiter an (rc 0/3).
- **NEU 1122u, leeres STL im Zwischenbau: BEHOBEN.** Der Generator schrieb 84 Byte, `bauen_abnehmen.sh` meldete bei RCPARK_NUR_BAUEN=1 rc 0 mit ERGEBNIS-Zeile, und alle Folgestufen stuerzten mit KeyError 'world'.
  - Jetzt prueft das Skript nach jedem Generatorlauf das STL aus objekt.json (Modus NUR_BAUEN und voller Modus). Es muss existieren, seit Baubeginn geschrieben sein und mehr als 0 Dreiecke haben (`kette_beleg.py stl`).
  - Sonst endet das Skript mit rc 4 ohne ERGEBNIS-Zeile, und die Kette meldet die Stufe rot.
  - Damit gilt die Pruefung auch fuer `bauen_mit_*` und `bauen_mit_fotodach`. Vorher pruefte nur der erste Bau `frisch(stl)`, siehe Punkt 10.
- **Muster "Ausgabe alt, rc 0", zwei weitere Faelle BEHOBEN:**
  - `bauplan_vorbauten`: Stuerzte `vorbauten_bauplan.py` ab, baute der Generator die `audit/vorbauten_auto.json` des Vorlaufs. Jetzt prueft ein Beleg die Datei, ein Altstand kommt beiseite.
  - `hand_vergleich`: befundliste und die Agenten-Schleife lasen `audit/hand_vergleich.json` eines frueheren Laufs. Jetzt prueft ein Beleg die Datei, ein Altstand kommt beiseite.
- **Weiter OFFEN, gleiches Muster:**
  - JSON-Bloecke in `dach_profil.json` (`spitze_foto`, `traufe_foto`, `flaeche_foto`): Stuerzt das Werkzeug ab oder endet es mit rc 3 vor dem Schreiben, bleibt der Block des Vorlaufs stehen und wird gebaut (`laterne_foto` ist durch die Pruefung von spitze_foto geschuetzt). Abhilfe: Zeitmarke je Block und Abgleich mit dem Stufenstart.
  - `befundliste.py` laedt die Tor-JSONs (`fenster_form_tor`, `umriss_tor` usw.) ohne Frischeabgleich. Abhilfe: `seit` mitgeben.
  - `dachfoto` (rc 0/3) loest `bauen_mit_fotodach` aus, ohne zu belegen, dass der Block `foto` in dach.json frisch ist.
  - Aus Punkt 10 bleiben offen: `bauplan_spitze_umriss` (rc 4, keine eigene Zeile), die druck-Masken `relief/*_putz.npz` sowie `sfm_netz.py` und `video_sfm.py` (fehlende SIFT-Bilder).

## Loesung (generisch)
- Neuer Helfer `tools/kette_beleg.py` mit diesen Funktionen:
  - `pruefen(pfade, seit, inhalt)`: prueft Existenz, ob die Datei seit Stufenstart geschrieben wurde, und optional den Mindestinhalt (`mindestens_eins`).
  - `beiseite(...)`: benennt Altdateien in `.veraltet_<zeit>` um. Es wird nichts geloescht.
  - `db_fehlende_bilder(db, namen)`.
- In `gesamtkette.py`:
  - `beleg(B, name, pfade, seit, ...)` schreibt bei einem Verstoss die Zeile `<name>_beleg` als NICHT in Ordnung, mit Grund und Folge. Die Kette laeuft weiter.
  - `sweep_altstand(...)` legt Altstaende beiseite. Die Stufe bleibt in Ordnung, denn rc 2/4 ist ein Urteil.
- Es gibt keine neuen Schwellen und kein gelockertes Tor.
- Test: `tools/test_kette_beleg.py`, eingetragen in `tools/schnelltest.sh`. Er laeuft gruen, ebenso test_verlustbilanz und test_foto_auftrag_skizze.
