#!/usr/bin/env python3
"""seiten_luecken.py <objekt.json> <fassaden-ordner> --sparse <SfM-Ordner mit images.bin> --ref-db <db.db> [--schwelle 0.2] [--min_m2 40] [--holen] [--download]

TOR + AUFTRAG: Welche Wand zeigt kein Foto - und woher kommen Fotos dafuer?
Nutzer 16.11.2026 (Schwabentor Ostseite): "Warum wurde es nicht automatisch gefunden? Er muss doch wissen, dass dort Bilder fehlen und die sich dann holen,
notfalls downloaden." Bisher meldete tools/kamera_abdeckung.py nur die Luecke im Kamerakranz (seit 14.11. bekannt) - niemand handelte danach.
Ablauf:
  1. Je Wand aus <fassaden-ordner>/fassaden.json (tools/fassade_ortho.py): Anteil der Wandzellen mit Bilddaten in ortho_fNN.png. < --schwelle = UNGESEHEN.
  2. Fotobestand (objekt.json fotos_dir) gegen die registrierten Bilder des SfM (images.bin) abgleichen -> Liste der NICHT registrierten Fotos (Kandidaten).
  3. Skript <audit>/seiten_luecken_holen.sh schreiben: Kandidaten mit ALIKED+LightGlue gegen das Netz nachregistrieren
     (tools/zusatzfotos_registrieren.py vorbereiten/merkmale/registrieren, tools/zusatzfotos_lightglue.py refnamen/paare/einlesen), Zielordner <daten>/seiten_nachholen.
     --download: davor ALLE freien Quellen: tools/commons_harvest.py (Geosuche 250 m + Namenssuche), tools/online_ansichten_holen.py (Hochblicke auf Commons),
     tools/openverse_holen.py (Flickr u. a., nur CC0/BY/BY-SA) nach <daten>/seiten_nachholen/{commons,hochblick,openverse}; Mapillary/Google NICHT (Lizenz, LIZENZ_WERKZEUGE.md);
     diese Bilder kommen zu den Kandidaten.
     --holen: das Skript sofort ausfuehren (GPU; nur ueber tools/job_start.sh starten, wenn es lange laeuft).
  4. Bericht <audit>/seiten_luecken.json. Exit-Code 3, solange eine Wand ungesehen ist.
  24.11.2026: auch TEILWEISE ungesehene Waende (>= TEIL_MIN_ANTEIL der Wand UND >= TEIL_MIN_M2 ohne Bilddaten, Bericht 'teilweise', 'zone_ohne_daten')
  loesen das Nachholen aus - je Kandidat nur EINMAL (versucht_kandidaten.json), danach nur Fotoauftrag.
Letzte Skriptschritte: tools/kameras_nachtragen.py (K-Dateien im Modellrahmen), kamera_verfeinern.py je neuer Kamera, tools/kameras_nachtragen_tor.py (Gueltigkeits-Tor:
unplausible/nicht am Modell belegte neue Kameras gesperrt; audit/kameras_nachtragen_tor.json je Wand: belegte neue Kameras mit Sicht). Die Kette (tools/gesamtkette.py, Stufe seiten)
wiederholt damit EINMAL Wandbild/Bau/Tore im selben Lauf, wenn die Abdeckung einer ungesehenen Wand messbar steigt (tools/seiten_wiederholung.py). Danach je ungesehener Wand: registrierte Neuzugaenge -> fassade_ortho/fassade_fein neu; bleibt ein Foto unregistriert, das die Wand zeigt (Kontaktbogen
<audit>/seiten_luecken_kandidaten.jpg ANSEHEN): Kamera aus gemessenen Modellpunkten + tools/fassade_ein_foto.py (modelle/PIPELINE_FASSADEN.md "Ungesehene Seite").
Grenze: Schritt 1 braucht einen fassade_ortho-Lauf; ob ein Kandidat die Wand wirklich zeigt, entscheidet erst die Registrierung bzw. der Blick auf den Kontaktbogen.
Umgebung: cv2 -> /media/oem/scan/venv-seg/bin/python -I tools/seiten_luecken.py ... (oder `tools/py tools/seiten_luecken.py ...`); SEITEN_NEU=1 erzwingt
erneutes Nachholen derselben Kandidaten. Exit: 0 = alle Waende gesehen, 2 = Einrichtungsfehler (Fassadenbild fehlt, keine Wand >= --min_m2, kein Foto),
3 = Wand ungesehen oder teilweise ungesehen ueber der Schwelle (Auftrag), 5 = Nachhol-Skript abgebrochen.
SCHNELL SCHEITERN (22.11.2026, schwabentor-1120 1122c/1122d: zweimal 44 min bis zum selben RigId-Absturz in zusatzfotos_lightglue einlesen):
  - Vorpruefung im Skript ganz vorn und nach 'merkmale': tools/colmap_rig_abgleich.py probe (Lade-Check von triangulate_points auf Mini-DB, Sekunden);
  - Zwischenstaende je Teilschritt (<daten>/seiten_nachholen/stand/<schritt>.ok, Schluesselkette, schritt_helfer) - ein Fehler im letzten Schritt verwirft die GPU-Paare nicht;
  - Fehlschlag-Marke fehlschlag_<schluessel>.json mit CODE-STAND der Nachhol-Werkzeuge (tools/code_stand.py): gleicher Fehlschlag bei unveraendertem Code -> sofort rc 5.
  - 23.11.2026: Speichermangel im abgebrochenen Schritt (tools/speicher_muster.py, z. B. SiftGPU 'out of memory') gibt Marke art='speicher' - die SPERRT NICHT
    (Kette 1122n/o: voruebergehend belegte GPU sperrte Wiederholung und Folgelauf). Ausgabe des Skripts auch in <daten>/seiten_nachholen/nachholen_letzter_lauf.log.
"""
import time, hashlib
import sys, os, json, glob, struct, argparse, subprocess, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from code_stand import code_stand, dateien as code_dateien
from speicher_muster import speicher_fehler
# Werkzeuge des Nachhol-Skripts (Unterprozesse - die Importsuche von code_stand sieht sie nicht, darum hier genannt): CODE-STAND der Fehlschlag-Marke
NACHHOL_WERKZEUGE = ("seiten_luecken.py", "colmap_rig_abgleich.py", "zusatzfotos_registrieren.py", "zusatzfotos_lightglue.py", "kameras_nachtragen.py", "kamera_verfeinern.py",
                     "kameras_nachtragen_tor.py", "commons_harvest.py", "online_ansichten_holen.py", "openverse_holen.py", "sift_paar_speicher.py")


def sperrt(F, cs):
    """Sperrt die Fehlschlag-Marke <F> einen neuen Versuch? Nur ein FESTER Fehler (nicht Speichermangel) bei gleichem CODE-STAND.
    23.11.2026 (Kette schwabentor-null-1122n/o): SiftGPU 'out of memory' (fremde GPU-Jobs) wurde als 'bekannter Fehlschlag' gemerkt - die Speicher-Wiederholung der Kette lief
    nach 8 s in die Sperre, der naechste Kettenlauf ebenso; Sued- und Ostwand blieben leer, obwohl am Code nichts falsch war."""
    return F.get("code_stand") == cs and F.get("art", "fest") != "speicher"


def skript_laufen(sk, logpfad, rest_zeilen=4000):
    """Nachhol-Skript ausfuehren, Ausgabe ZEILENWEISE weiterreichen (die Kette liest sie) und nach <logpfad> schreiben.
    Rueckgabe (rc, Ausgabe seit der letzten 'SCHRITT '-Zeile) - nur der abgebrochene Schritt entscheidet ueber 'Speichermangel' (ein frueherer, aufgefangener
    SiftGPU-Speicherfehler darf einen festen Fehler spaeter im Skript nicht als voruebergehend tarnen)."""
    import collections
    schluss = collections.deque(maxlen=rest_zeilen); os.makedirs(os.path.dirname(logpfad), exist_ok=True)
    with open(logpfad, "w", encoding="utf-8", errors="replace") as lg:
        p = subprocess.Popen(["bash", sk], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for b in p.stdout:
            z = b.decode("utf-8", "replace"); sys.stdout.write(z); sys.stdout.flush(); lg.write(z)
            if z.startswith("SCHRITT "): schluss.clear()
            schluss.append(z)
        sys.stdout.flush(); rc = p.wait()
    return rc, "".join(schluss)


def sift_schalter():
    """23.11.2026: RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT=1 beim Erzeugen des Skripts -> in den Befehl der Stufe merkmale schreiben (der Befehls-Hash der Schritt-Kette
    aendert sich mit, ein umgeschalteter Lauf uebernimmt keinen Zwischenstand des anderen Wegs). Standard AUS = Befehl unveraendert."""
    return "RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT=1 " if os.environ.get("RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT", "0") == "1" else ""


def schritt_helfer(Z, T):
    """Bash-Funktionen fuer ZWISCHENSTAENDE je Teilschritt des Nachhol-Skripts (22.11.2026: ein Absturz im 6. Schritt verwarf jedes Mal ~44 min Merkmale/LightGlue).
    Schluessel je Schritt = Kette (vorheriger Schluessel | Name | CODE-STAND der genannten Werkzeuge | Befehls-Hash); Kettenbeginn = Kandidatenbestand roh/.
    Passt <Z>/stand/<name>.ok zum Schluessel -> Schritt uebersprungen, sonst gerechnet (und alle folgenden, weil sich die Kette aendert).
    Teure Schritte (Merkmale, Paare) nennen keine Werkzeuge -> haengen nur an Eingaben + Befehl; billige Folgeschritte tragen ihren CODE-STAND (tools/code_stand.py)."""
    return [f"ST={Z}/stand",
            'schritt_noetig() {   # schritt_noetig <name> "<werkzeuge fuer CODE-STAND>" <befehls-hash>: 0 = rechnen, 1 = Zwischenstand passt',
            f'  local cs=""; [ -n "$2" ] && cs=$(python3 -I {T}/code_stand.py $2 | tail -1)',
            '  KETTE=$(printf "%s|%s|%s|%s" "$KETTE" "$1" "$cs" "$3" | sha1sum | cut -c1-16); echo "$1" > $ST/aktuell',
            '  if [ "$(cat $ST/$1.ok 2>/dev/null)" = "$KETTE" ]; then echo "SCHRITT $1: Zwischenstand uebernommen ($KETTE)"; return 1; fi',
            '  echo "SCHRITT $1: rechnen ($KETTE)"; rm -f $ST/$1.ok; return 0; }',
            'schritt_fertig() { echo "$KETTE" > $ST/$1.ok; }']


def kontaktboegen(dateien, pfad, je_seite=120, Tn=200):
    """ALLE Kandidaten als Kontaktboegen (je Seite 120 Kacheln, laufende Nummer + Namensende): <pfad>, dann <pfad ohne .jpg>_2.jpg, _3.jpg ...
    23.11.2026 (Kette 1122o): der Bogen zeigte nur die ersten 120 von 372 Kandidaten - die eigenen Nahaufnahmen der Feldseite (St.-Georg-Bild) lagen dahinter und
    waren nicht 'anzusehen', wie es der Hinweis der Stufe verlangt. Rueckgabe: Liste der geschriebenen Dateien."""
    raus = []
    for s0 in range(0, len(dateien), je_seite):
        kacheln = []
        for i, f in enumerate(dateien[s0:s0 + je_seite]):
            im = cv2.imread(f); c = np.zeros((Tn, Tn, 3), np.uint8)
            if im is not None:
                s = Tn / max(im.shape[:2]); im = cv2.resize(im, (max(int(im.shape[1] * s), 1), max(int(im.shape[0] * s), 1)), interpolation=cv2.INTER_AREA); c[:im.shape[0], :im.shape[1]] = im
            cv2.rectangle(c, (0, 0), (34, 15), (0, 0, 0), -1); cv2.putText(c, str(s0 + i), (2, 12), 0, 0.4, (0, 255, 255), 1)
            cv2.putText(c, os.path.splitext(os.path.basename(f))[0][-14:] + ("" if im is not None else " UNLESBAR"), (2, Tn - 5), 0, 0.4, (0, 255, 255), 1); kacheln.append(c)
        while len(kacheln) % 10: kacheln.append(np.zeros((Tn, Tn, 3), np.uint8))
        p = pfad if s0 == 0 else pfad[:-4] + f"_{s0 // je_seite + 1}.jpg"
        cv2.imwrite(p, np.vstack([np.hstack(kacheln[i:i + 10]) for i in range(0, len(kacheln), 10)])); raus.append(p)
    return raus


def utm32_nach_geo(e, n):
    """ETRS89/UTM Zone 32N -> (Breite, Laenge) in Grad (Reihenentwicklung, < 1 m Fehler; pyproj fehlt in venv-seg - 16.11.2026 brach der erste Gesamtlauf daran ab)."""
    import math
    a_, f_ = 6378137.0, 1 / 298.257222101; k0 = 0.9996; e2 = f_ * (2 - f_); ep2 = e2 / (1 - e2); x = e - 500000.0; M = n / k0; mu = M / (a_ * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256)); e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
    C1 = ep2 * math.cos(p1) ** 2; T1 = math.tan(p1) ** 2; N1 = a_ / math.sqrt(1 - e2 * math.sin(p1) ** 2); R1 = a_ * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5; D = x / (N1 * k0)
    lat = p1 - (N1 * math.tan(p1) / R1) * (D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24); lon = math.radians(9.0) + (D - (1 + 2 * T1 + C1) * D ** 3 / 6) / math.cos(p1)
    return math.degrees(lat), math.degrees(lon)


def nur_vorhandene(pfade):
    """(vorhandene, tote): tote = Verknuepfungen/Pfade ohne lesbares Ziel - nie als Kandidat ins Nachholskript."""
    tot = [f for f in pfade if not os.path.isfile(f)]; ts = set(tot)
    return [f for f in pfade if f not in ts], tot


def roh_neu_zeile(Z):
    """Bash-Zeile: alle Verknuepfungen (nur symlinks, nie echte Dateien) in Z/roh entfernen, bevor das Skript die Kandidaten DIESES Laufs verlinkt.
    23.11.2026 (Lauf 1122p): roh/ behielt 362 Verknuepfungen vom 22.11. (Fotoordner seither mit anderen Namen neu gebaut, eigen__vf_007.jpg ...), 305 davon tot -
    vorbereiten brach mit FileNotFoundError ab, die Ostseite blieb leer."""
    return (f"ALT=$(find {Z}/roh -maxdepth 1 -type l | wc -l); TOT=$(find {Z}/roh -maxdepth 1 -xtype l | wc -l); find {Z}/roh -maxdepth 1 -type l -delete; "
            f"echo \"roh/: $ALT Verknuepfungen frueherer Laeufe entfernt (davon $TOT tot), Neuaufbau aus den Kandidaten dieses Laufs\"")


def wand_daten(fassaden_dir, F, i, im=None, maske=None):
    """(daten, maske): Zellen mit Bilddaten in ortho_<id>.png und Wandzellen (polys_uz im Raster); None = Bild fehlt oder passt nicht zum Raster."""
    R = F["raster"]
    if maske is None:
        maske = np.zeros((R["nz"], R["nu"]), np.uint8)
        for poly in F["polys_uz"]: cv2.fillPoly(maske, [np.array([[(u - R["u0"]) / R["zelle"], (R["z1"] - z) / R["zelle"]] for u, z in poly], np.int32)], 1)
    if im is None: im = cv2.imread(os.path.join(fassaden_dir, f"ortho_{F.get('id', 'f%02d' % i)}.png"))
    if im is None or im.shape[:2] != maske.shape: return None
    daten = im.max(2) > 8; un_ = cv2.imread(os.path.join(fassaden_dir, f"uneinig_f{i:02d}.png"), 0) if os.environ.get("LUECKEN_MIT_UNEINIG") == "1" else None
    if un_ is not None and un_.shape == daten.shape: daten &= cv2.blur(un_.astype(np.float32), (9, 9)) <= 28      # widerspruechliche Zonen zaehlen nicht als gesehen (16.11.2026)
    return daten, maske


def wand_abdeckung(fassaden_dir, F, i, im=None, maske=None):
    """Anteil der Wandzellen (polys_uz im Raster) mit Bilddaten in ortho_<id>.png - EIN Mass fuer 'gesehen' (seiten_luecken und tools/seiten_wiederholung.py).
    None = Bild fehlt oder passt nicht zum Raster."""
    dm = wand_daten(fassaden_dir, F, i, im, maske)
    if dm is None: return None
    daten, maske = dm
    return float((daten & (maske > 0)).sum() / max(maske.sum(), 1))


# 24.11.2026 TEILWEISE UNGESEHEN (Kette schwabentor-null-1122x, Ostwand f02: 44 % gesehen, 239 m2 ohne Bilddaten): das Nachholen lief nur fuer
# GANZ ungesehene Waende (< --schwelle 0,2), die Stufe meldete 'keine Wand ganz ungesehen; ABER ...' mit rc 0 und die Kette tat nichts. Jetzt loest eine Wand mit
# BEIDEN Bedingungen ebenfalls das Nachholen aus (gleiche Wege wie 'ungesehen'):
#   Gezaehlt wird nur FOTOGRAFIERBARE Flaeche: Zellen an einem angebauten Nachbarhaus (nachbar_verdeckt, LoD2) sind nie zu sehen - 1122x f02: von 239 m2 ohne Bilddaten
#   lagen ~190 m2 hinter dem Nachbarhaus (z 0-17,7 m), fotografierbar fehlen ~57 m2 (23 % der freien Wand) darueber.
#   - ohne Bilddaten >= TEIL_MIN_ANTEIL (0,10) der fotografierbaren Wand: das 20-fache des Rand-/Rasterrests gesehener Waende (0-0,5 %, 1122x f00/f01/f03) und das Doppelte
#     des Gewinn-Tors MIN_GEWINN 0,05 (tools/seiten_wiederholung.py); verstreutes Rauschen an grossen Waenden loest nicht aus;
#   - UND >= TEIL_MIN_M2 (50 m2) absolut: ~7 x 7 m = ein Fassadenfeld ueber zwei Geschosse (H0 1:87: ~66 cm2 Modellflaeche) und an Waenden bis 1000 m2 >= MIN_GEWINN
#     (Gewinn bleibt messbar); kleine Waende (ab --min_m2 40) loesen damit nur als GANZ ungesehen aus. Darunter bleibt es bei der Meldung (ab 30 m2, foto_auftrag.py).
# KOSTEN: Nachholen ~48 min + Teillauf ~1,7 h (1122w). Darum gilt fuer teilweise ungesehene Waende zusaetzlich die KANDIDATEN-Liste versucht_kandidaten.json: Kandidaten (unabhaengig von
# den Zielwaenden - das Skript registriert ohnehin alle) werden nur EINMAL nachgeholt, auch ueber neu gerechnete SfM-Modelle hinweg; brachte das keine
# belegte Kamera fuer die Zone, bleibt nur der Fotoauftrag (kein zweiter Versuch, bis neue Fotos/Downloads den Kandidatenbestand aendern).
TEIL_MIN_ANTEIL = float(os.environ.get("RCPARK_TEIL_MIN_ANTEIL", "0.10"))
TEIL_MIN_M2 = float(os.environ.get("RCPARK_TEIL_MIN_M2", "50"))


def teilweise_ungesehen(w, min_anteil=None, min_m2=None):
    """Wand-Eintrag des Berichts -> True, wenn sie NICHT ganz ungesehen ist, aber ihre FOTOGRAFIERBARE Flaeche ohne Bilddaten beide Schwellen erreicht.
    Fotografierbar = nicht an einem angebauten Nachbarhaus (nachbar_verdeckt): 'ohne_daten_frei_m2' gegen 'flaeche_m2' - 'verdeckt_nachbar_m2'; fehlen die Felder
    (kein LoD2), zaehlt die ganze Flaeche ohne Bilddaten (ohne_daten_m2, abdeckung)."""
    min_anteil = TEIL_MIN_ANTEIL if min_anteil is None else min_anteil; min_m2 = TEIL_MIN_M2 if min_m2 is None else min_m2
    if w.get("ungesehen"): return False
    if w.get("ohne_daten_frei_m2") is not None:
        frei_m2 = float(w["ohne_daten_frei_m2"]); basis = float(w.get("flaeche_m2") or 0) - float(w.get("verdeckt_nachbar_m2") or 0)
        return frei_m2 >= min_m2 and basis > 0 and frei_m2 / basis >= min_anteil
    return float(w.get("ohne_daten_m2") or 0) >= min_m2 and 1.0 - float(w.get("abdeckung") or 0) >= min_anteil


NACHBAR_VOR_M = 1.0      # ANNAHME: Pruefpunkt 1 m vor der Wand - groesser als der Lagefehler Modell/LoD2 (~0,5 m), kleiner als jede Haustiefe


def nachbar_verdeckt(nb_netz, F, maske, schritt=5, vor_m=NACHBAR_VOR_M):
    """Wandzellen, vor denen ein ANGEBAUTES Nachbarhaus steht (nie fotografierbar - kein Ziel fuer Nachholen/Fotoauftrag): Punkt <vor_m> vor der Zelle (Normale nach aussen)
    liegt in einem LoD2-Nachbargebaeude = ueber UND unter ihm Flaechen dieses Netzes (Dach/Boden). Raster <schritt> Zellen (Sekunden), auf volle Aufloesung gedehnt.
    24.11.2026 (1122x f02: 239 m2 ohne Bilddaten, davon ~190 m2 z 0-17,7 m hinter dem Nachbarhaus; fotografierbar fehlen ~57 m2 darueber). -> bool-Feld wie maske."""
    from trimesh.ray.ray_triangle import RayMeshIntersector
    R = F["raster"]; vs = np.arange(0, R["nz"], schritt); us = np.arange(0, R["nu"], schritt); V, U = np.meshgrid(vs, us, indexing="ij")
    u = R["u0"] + (U + 0.5) * R["zelle"]; z = R["z1"] - (V + 0.5) * R["zelle"]
    xy = np.asarray(F["o"], float)[None] + u.reshape(-1, 1) * np.asarray(F["d"], float)[None] + vor_m * np.asarray(F["n"], float)[None]; P = np.c_[xy, z.reshape(-1)]
    ri = RayMeshIntersector(nb_netz); hoch = np.tile([0, 0, 1.0], (len(P), 1))
    grob = (ri.intersects_any(P, hoch) & ri.intersects_any(P, -hoch)).reshape(V.shape)
    zi = np.minimum(np.arange(R["nz"]) // schritt, len(vs) - 1); si = np.minimum(np.arange(R["nu"]) // schritt, len(us) - 1)
    return grob[zi][:, si] & (maske > 0)


def zone_ohne_daten(daten, maske, R, min_zeile=0.5):
    """Hoehenzone der groessten Luecke: zusammenhaengende Rasterzeilen, in denen >= <min_zeile> der Wandzellen keine Bilddaten haben; die mit der meisten Fehlflaeche.
    -> dict(z_von, z_bis, m2) in Wandkoordinaten (Zeile 0 = z1 oben) oder None. Ziel fuer Fotoauftrag/Bericht (die Kandidaten selbst sind vor der Registrierung ohne Pose)."""
    m = maske > 0; fehl = m & ~daten; n_m = m.sum(1); n_f = fehl.sum(1)
    leer = (n_m > 0) & (n_f >= min_zeile * np.maximum(n_m, 1)); best = None; r = 0
    while r < len(leer):
        if not leer[r]: r += 1; continue
        r1 = r
        while r1 + 1 < len(leer) and leer[r1 + 1]: r1 += 1
        s = int(n_f[r:r1 + 1].sum())
        if best is None or s > best[2]: best = (r, r1, s)
        r = r1 + 1
    if best is None: return None
    z = R["zelle"]; return dict(z_von=round(R["z1"] - (best[1] + 1) * z, 2), z_bis=round(R["z1"] - best[0] * z, 2), m2=round(best[2] * z * z, 1))


def kand_namen(kand):
    """Kandidaten als 'name:groesse' (eine geaenderte Datei gleichen Namens gilt als neu)."""
    return sorted(f"{os.path.basename(f)}:{os.path.getsize(f)}" for f in kand)


# 24.11.2026 (Kette 1122zb): der erste Versuch fuer f02 (244 Kandidaten, 29,6 min) lief mit der gekippten Abbildung SfM -> Modell (kameras_nachtragen, Massstab 0,0017):
# alle neuen Kameras auf einem Punkt im Turm, 0 sehen eine Wand - und stand trotzdem als 'versucht' in der Liste, d. h. die Kandidaten waeren nie wieder nachgeholt worden.
# Seitdem prueft kameras_nachtragen die Abbildung (rc 4 = Fehlschlag-Marke, kein Eintrag hier). Eintraege OHNE dieses Merkmal stammen von vor dem Tor und zaehlen nicht:
# genau EIN neuer Versuch je Bestand (danach gilt die Liste wieder).
VERSUCH_GEPRUEFT = "abbildung_geprueft"


def kandidaten_versucht(Z, kand):
    """Liste versucht_kandidaten.json in <Z>: sind ALLE Kandidaten schon in einem frueheren erfolgreichen Nachholen gewesen (Vereinigung aller Versuche)?
    -> (ja, text). Fuer TEILWEISE ungesehene Waende: kein zweiter Versuch ohne neues Foto (das Skript registriert ohnehin alle Kandidaten, unabhaengig von den
    Zielwaenden). ANNAHME: dieselben Fotos gegen ein neu gerechnetes SfM bringen keine neue Sicht auf die Zone - neue Fotos/Downloads oeffnen den Weg wieder."""
    try: V = json.load(open(os.path.join(Z, "versucht_kandidaten.json"))).get("versuche") or []
    except (OSError, ValueError): return False, "noch kein Versuch"
    n_alt = sum(1 for v in V if not v.get(VERSUCH_GEPRUEFT)); V = [v for v in V if v.get(VERSUCH_GEPRUEFT)]      # Versuche vor dem Abbildungs-Tor zaehlen nicht (siehe VERSUCH_GEPRUEFT)
    if not V: return False, "noch kein gueltiger Versuch" + (f" ({n_alt} vor dem Abbildungs-Tor von kameras_nachtragen - einmal neu)" if n_alt else "")
    alle = set(); [alle.update(v.get("kandidaten") or []) for v in V]; neu = [k for k in kand_namen(kand) if k not in alle]
    if neu: return False, f"{len(neu)} neue Kandidaten (z. B. {neu[0].rsplit(':', 1)[0]})"
    return True, f"alle {len(kand)} Kandidaten schon nachgeholt ({len(V)} Versuch(e), zuletzt {V[-1].get('zeit')} fuer {V[-1].get('waende')})"


def kandidaten_merken(Z, kand, waende, hoechstens=20):
    """Erfolgreiches Nachholen in versucht_kandidaten.json eintragen (die juengsten <hoechstens> Versuche bleiben)."""
    p = os.path.join(Z, "versucht_kandidaten.json")
    try: V = json.load(open(p)).get("versuche") or []
    except (OSError, ValueError): V = []
    V = (V + [dict(zeit=time.strftime("%Y-%m-%d %H:%M"), waende=list(waende), kandidaten=kand_namen(kand), **{VERSUCH_GEPRUEFT: True})])[-hoechstens:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); __import__("json_sicher").schreiben(p, dict(versuche=V))


def kamera_verfeinern_zeile(VS, T, objekt, fassaden_json, audit, Z):
    """Bash-Zeile: ALLE neuen Kameras (audit/kameras_nachtragen.json 'neu', in dieser Reihenfolge) in EINEM Prozess am Modell nachziehen (kamera_verfeinern.py --liste).
    23.11.2026 (Kette 1122q): bisher je Kamera ein eigener Prozess - 327 x (Importe, STL 958k Dreiecke laden, ALIKED/LightGlue laden, Referenz-Merkmale und
    -Tiefenbilder neu) = 75 min von 165 min der Stufe. 24.11.2026: nur rc 0/3 gelten (stapelweise Fehler je Foto faengt kamera_verfeinern selbst ab), ein Absturz beim Laden
    (1122u: leeres STL) bricht das Skript ab statt 'alles unbelegt' + Erfolgsmarke 'versucht' (die den naechsten Lauf ueberspringen liess). Der Stapel liest die K-Dateien je Foto frisch und schluesselt Tiefenbilder nach Kamera - Ergebnis wie die
    Einzelfolge (tools/test_kamera_verfeinern_stapel.py). rc 3 (Kamera bleibt unsicher) und Fehler brechen das Skript nicht ab (wie vorher '|| true' je Foto)."""
    L = f"{Z}/kamera_verfeinern_liste.txt"
    return (f"python3 -c \"import json; print('\\n'.join(e['foto'] for e in json.load(open('{audit}/kameras_nachtragen.json'))['neu']), end='')\" > {L} || : ; "
            f"if [ -s {L} ]; then {VS} -W ignore {T}/kamera_verfeinern.py {objekt} {fassaden_json} - --liste {L} --schreiben || [ $? = 3 ]; fi   # neue Kameras am Modell nachziehen (rc 3 = keine bestimmt, kein Abbruch; Absturz = Abbruch, 24.11.2026 1122u: '|| true' schluckte KeyError 'world' -> Erfolgsmarke trotz 0 belegt)")


def download_zeile(Z, name, cmd, bei_fehler):
    """Bash-Zeilen: Download-Befehl <cmd> nur, wenn sein letzter erfolgreicher Lauf (gleicher Befehl = gleiche Suche/Quelle) aelter ist als
    RCPARK_DOWNLOAD_FRISCH_H Stunden (Standard 24; 0 = immer laden) - endete er mit Drosselung (HTTP 429/503 in der Ausgabe), gilt RCPARK_DOWNLOAD_DROSSEL_H (Standard 6).
    24.11.2026 (Kette 1122w): Download 5 min, obwohl alle Bilder schon da waren - Commons-/Openverse-Abfragen (Seiten mit 2-3 s Pause) und Drossel-Versuche je Lauf.
    Die Werkzeuge laden schon Vorhandenes nicht neu (Datei-Cache) und warten bei 429 mit Retry-After/Backoff (tools/http_holen.py, Drossel-Marke 24 h);
    hier faellt zusaetzlich die ganze Abfrage weg, solange sie frisch ist. ANNAHME: Suchtreffer/Lizenzen freier Quellen aendern sich innerhalb eines Tages nicht nennenswert.
    Marke <Z>/download_stand/<name>_<befehls-hash>.ok bzw. .drossel; rc != 0 -> <bei_fehler> (kein Abbruch, keine Marke)."""
    h = hashlib.sha1(cmd.encode()).hexdigest()[:12]; D = f"{Z}/download_stand"; M = f"{D}/{name}_{h}"; L = f"{D}/{name}.log"
    return [f"mkdir -p {D}; FH=${{RCPARK_DOWNLOAD_FRISCH_H:-24}}; DH=${{RCPARK_DOWNLOAD_DROSSEL_H:-6}}",
            f'if [ "$FH" != 0 ] && {{ [ -n "$(find {M}.ok -mmin -$((FH * 60)) 2>/dev/null)" ] || [ -n "$(find {M}.drossel -mmin -$((DH * 60)) 2>/dev/null)" ]; }}; then',
            f'  echo "DOWNLOAD {name}: letzter Lauf frisch (< $FH h, gedrosselt < $DH h) - Abfrage uebersprungen, vorhandene Bilder bleiben (neu laden: RCPARK_DOWNLOAD_FRISCH_H=0)"',
            "else",
            f"  RC=0; {cmd} 2>&1 | tee {L}; RC=${{PIPESTATUS[0]}}; rm -f {M}.ok {M}.drossel",
            f'  if [ $RC != 0 ]; then {bei_fehler}; elif grep -q -E "HTTP (429|503)|[Dd]rossel" {L}; then touch {M}.drossel; else touch {M}.ok; fi',
            "fi"]


def stl_dreiecke(p):
    """Zahl der Dreiecke einer STL-Datei (binaer oder ASCII), ohne trimesh (venv-colmap hat es nicht). None = keine lesbare STL."""
    try:
        n_b = os.path.getsize(p)
        with open(p, "rb") as f: kopf = f.read(84)
        if len(kopf) == 84 and n_b == 84 + 50 * struct.unpack("<I", kopf[80:84])[0]: return struct.unpack("<I", kopf[80:84])[0]
        if kopf[:5].lower() == b"solid":
            n = 0
            with open(p, "rb") as f:
                for z in f: n += z.lstrip().lower().startswith(b"facet")
            return n
    except OSError: pass
    return None


def belegbar(objekt_json, min_ref=1):
    """FRUEH-ABBRUCH (24.11.2026, Kette schwabentor-null-1122u: seiten_luecken 3737 s, Ende '264 nachgetragen, 0 BELEGT, 264 gesperrt'):
    'belegt' heisst am MODELL nachgezogen (tools/kamera_verfeinern.py). Das braucht (1) das Modell-STL aus objekt.json 'stl' mit Dreiecken und (2) mindestens <min_ref>
    Referenzkamera(s) (K-Datei mit 'kamera' im gueltigen Rahmen, tools/kamera_rahmen.py - dieselbe Regel wie kamera_verfeinern). 1122u: STL leer (Rueckwand-Fehler) ->
    kamera_verfeinern stuerzte gleich beim Laden ab (KeyError 'world'), '|| true' schluckte es, nach ~60 min Merkmale/LightGlue/Registrieren wurde jede Kamera 'unbelegt'.
    Rueckgabe (ok, grund). Prueft in Sekunden, BEVOR Download und Nachregistrieren laufen."""
    od = os.path.dirname(os.path.abspath(objekt_json)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(objekt_json))
    if not obj.get("stl"): return False, "objekt.json nennt kein Modell-STL ('stl') - kamera_verfeinern kann keine Kamera am Modell belegen"
    p = obj["stl"] if os.path.isabs(obj["stl"]) else os.path.join(root, obj["stl"])
    if not os.path.isfile(p): return False, f"Modell-STL {p} fehlt - kamera_verfeinern kann keine Kamera am Modell belegen"
    n = stl_dreiecke(p) if p.lower().endswith(".stl") else (1 if os.path.getsize(p) > 0 else 0)
    if not n: return False, f"Modell-STL {p} ist " + ("unlesbar" if n is None else "LEER (0 Dreiecke)") + " - kamera_verfeinern stuerzt beim Laden ab, jede neue Kamera bliebe 'unbelegt'"
    mp = os.path.join(od, "messprotokoll"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kamera_rahmen as KR; ST = KR.aktuell(mp); m = 0
    for kp in glob.glob(os.path.join(mp, "K-*.json")):
        try: k = json.load(open(kp)).get("kamera")
        except (OSError, ValueError, AttributeError): continue
        if isinstance(k, dict) and "rvec" in k and not KR.veraltet(k, mp, kp, ST):
            m += 1
            if m >= min_ref: return True, f"Modell-STL {n} Dreiecke, >= {m} Referenzkamera(s)"
    return False, f"nur {m} Referenzkamera(s) im gueltigen Rahmen unter {mp} (noetig {min_ref}) - kamera_verfeinern haette nichts, woran es neue Kameras belegt"


def registrierte(sparse):
    namen = []
    with open(os.path.join(sparse, "images.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            f.read(4 + 32 + 24 + 4); b = b""
            while True:
                c = f.read(1)
                if c == b"\x00": break
                b += c
            k = struct.unpack("<Q", f.read(8))[0]; f.read(24 * k); namen.append(b.decode())
    return namen


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassaden"); ap.add_argument("--sparse", required=True); ap.add_argument("--ref-db", required=True); ap.add_argument("--schwelle", type=float, default=0.2)
    ap.add_argument("--min_m2", type=float, default=40.0); ap.add_argument("--holen", action="store_true"); ap.add_argument("--download", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); audit = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); os.makedirs(audit, exist_ok=True)
    FJ = json.load(open(os.path.join(a.fassaden, "fassaden.json"))); waende = []; nb_ = {}
    def nachbarn():                                                     # LoD2-Nachbarn im Modellrahmen, erst bei Bedarf (eine Wand mit grosser Luecke) und einmal
        if "netz" not in nb_:
            nb_["netz"] = None
            if obj.get("lod2", {}).get("gml") and obj.get("rahmen"):
                try: import fassade_ortho as FO_; nb_["netz"] = FO_.nachbarn_netz(obj)[0]
                except Exception as e_: print(f"WARNUNG: LoD2-Nachbarn nicht geladen ({type(e_).__name__}: {str(e_)[:120]}) - Flaeche am Nachbarhaus zaehlt als 'ohne Bilddaten'")
            else: print("HINWEIS: objekt.json ohne lod2.gml/rahmen - Flaeche an angebauten Nachbarn nicht abziehbar, zaehlt als 'ohne Bilddaten'")
        return nb_["netz"]
    for i, F in enumerate(FJ["fassaden"]):
        if F.get("flaeche_m2", 0) < a.min_m2: continue
        p = os.path.join(a.fassaden, f"ortho_{F.get('id', 'f%02d' % i)}.png"); R = F["raster"]; maske = np.zeros((R["nz"], R["nu"]), np.uint8)      # Kennung aus fassaden.json (bei --nur ist die Kennung nicht die Listenposition)
        im_ = cv2.imread(p)
        if im_ is None or im_.shape[:2] != maske.shape:                # 17.11.2026: ein fehlendes/unlesbares oder nicht zu fassaden.json passendes Bild zaehlte als "Wand ungesehen" und loeste Download + 30 min Nachregistrieren aus
            print(f"FEHLER: Fassadenbild {p} " + ("fehlt/unlesbar" if im_ is None else f"hat {im_.shape[1]}x{im_.shape[0]} px, fassaden.json sagt {R['nu']}x{R['nz']}") + " - Ausgabe von fassade_ortho unvollstaendig oder aus zwei Laeufen gemischt; KEINE Luecken-Aussage"); return 2
        for poly in F["polys_uz"]: cv2.fillPoly(maske, [np.array([[(u - R["u0"]) / R["zelle"], (R["z1"] - z) / R["zelle"]] for u, z in poly], np.int32)], 1)
        ant = wand_abdeckung(a.fassaden, F, i, im_, maske); daten_, _ = wand_daten(a.fassaden, F, i, im_, maske)
        w_ = dict(nr=i, id=F.get("id", "f%02d" % i), normale=F["n"], mitte=F["o"], flaeche_m2=F["flaeche_m2"], abdeckung=round(ant, 3), fotos=len(F.get("fotos", {})), ungesehen=ant < a.schwelle, ohne_daten_m2=round(float(F["flaeche_m2"]) * (1 - ant), 1))
        if w_["ohne_daten_m2"] >= min(TEIL_MIN_M2, 30) and not w_["ungesehen"] and nachbarn() is not None:      # 24.11.2026: Flaeche am angebauten Nachbarhaus ist nie fotografierbar
            try:
                ver_ = nachbar_verdeckt(nachbarn(), F, maske); nm_ = max(int((maske > 0).sum()), 1); fl_ = float(F["flaeche_m2"])
                w_["verdeckt_nachbar_m2"] = round(fl_ * float(ver_.sum()) / nm_, 1); w_["ohne_daten_frei_m2"] = round(fl_ * float(((maske > 0) & ~daten_ & ~ver_).sum()) / nm_, 1); daten_ = daten_ | ver_
            except Exception as e_: print(f"WARNUNG: Nachbar-Verdeckung f{i:02d} nicht bestimmt ({type(e_).__name__}: {str(e_)[:120]}) - ganze Luecke zaehlt")
        w_["teilweise"] = teilweise_ungesehen(w_); w_["zone_ohne_daten"] = zone_ohne_daten(daten_, maske, R) if w_["ohne_daten_m2"] >= 30 else None; waende.append(w_); zo_ = w_["zone_ohne_daten"]
        print(f"Wand f{i:02d}: Normale ({F['n'][0]:+.2f}, {F['n'][1]:+.2f}), {F['flaeche_m2']:.0f} m2, {ant * 100:5.1f} % mit Bilddaten aus {len(F.get('fotos', {}))} Fotos" + ("   <-- UNGESEHEN" if ant < a.schwelle else (f"   <-- TEILWEISE{' (NACHHOLEN)' if w_['teilweise'] else ''}: {F['flaeche_m2'] * (1 - ant):.0f} m2 ohne Bilddaten" + (f" (davon {w_['verdeckt_nachbar_m2']:.0f} m2 am angebauten Nachbarhaus, fotografierbar fehlen {w_['ohne_daten_frei_m2']:.0f} m2)" if w_.get("ohne_daten_frei_m2") is not None else "") + (f", groesste Zone z {zo_['z_von']:.1f}-{zo_['z_bis']:.1f} m ({zo_['m2']:.0f} m2)" if zo_ else "") if F["flaeche_m2"] * (1 - ant) >= 30 else "")))
    reg = set(os.path.splitext(os.path.basename(n))[0] for n in registrierte(a.sparse)); fd = os.path.join(root, obj["fotos_dir"]); alle = sorted(f for f in glob.glob(os.path.join(fd, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not waende: print(f"FEHLER: KEINE Wand geprueft (keine Fassade >= {a.min_m2:g} m2 unter {len(FJ['fassaden'])} in fassaden.json) - das ist KEIN 'alle Waende gesehen'; --min_m2 senken oder fassade_ortho pruefen"); return 2      # 17.11.2026: lief mit rc 0 und 'alle Waende gesehen' durch
    alle, tot = nur_vorhandene(alle)      # 23.11.2026: tote Verknuepfung im Fotoordner waere ein Kandidat ohne Datei (Nachholen stuerzte in vorbereiten/md5 ab)
    if tot: print(f"WARNUNG: {len(tot)} tote Verknuepfung(en) im Fotoordner {fd} - KEINE Kandidaten (z. B. {os.path.basename(tot[0])} -> {os.readlink(tot[0]) if os.path.islink(tot[0]) else '?'})")
    if not alle: print(f"FEHLER: kein Foto in fotos_dir {fd} - Einrichtungsfehler, keine Luecken-Aussage"); return 2
    kand = [f for f in alle if os.path.splitext(os.path.basename(f))[0] not in reg]; print(f"Fotobestand {len(alle)}, im SfM registriert {len(alle) - len(kand)}, NICHT registriert {len(kand)}")
    ung = [w for w in waende if w["ungesehen"]]; teil = [w for w in waende if w.get("teilweise")]; ziel = ung + teil; daten = os.path.join(os.environ.get("SEITEN_LUECKEN_DATEN", "/media/oem/scan/rc-park_daten"), os.path.basename(od)); Z = os.path.join(daten, "seiten_nachholen"); T = os.path.join(root, "tools"); VC = "/media/oem/scan/venv-colmap/bin/python -I"; VS = "/media/oem/scan/venv-seg/bin/python -I"
    zeilen = ["#!/bin/bash", "# erzeugt von tools/seiten_luecken.py - Kandidaten fuer ungesehene Waende nachregistrieren", "set -e", f"mkdir -p {Z}/roh {Z}/stand", f"rm -f {Z}/stand/aktuell",
              f"{VC} {T}/colmap_rig_abgleich.py probe --db {a.ref_db} --sparse {a.sparse}   # 22.11.2026 SCHNELL SCHEITERN: Lade-Check von triangulate_points (Kamera/Rig Modell vs. DB) in Sekunden statt nach 44 min", roh_neu_zeile(Z)] + schritt_helfer(Z, T)
    if a.download and obj.get("koordinate_utm"):
        lat, lon = utm32_nach_geo(*obj["koordinate_utm"][:2])
        # freie Lizenzen, manifest.json; 17.11.2026: rc 2 bei 0 Bildern darf das Nachholen (set -e) nicht abbrechen. 24.11.2026: frische Abfragen nicht wiederholen (download_zeile)
        zeilen += download_zeile(Z, "commons", f"{VS} {T}/commons_harvest.py --lat {lat:.6f} --lon {lon:.6f} --radius 250 --max 60 --search \"{obj.get('name', '')} {obj.get('ort', '')}\" --out {Z}/commons",
                                 'echo "Commons: nichts geholt (rc $RC) - weiter mit den anderen Quellen"')
        nm = f"{obj.get('name', '')} {obj.get('ort', '').split(' im ')[0]}".strip(); ort = obj.get("ort", "").split(" im ")[0]
        zeilen += download_zeile(Z, "hochblick", f"python3 {T}/online_ansichten_holen.py --aus {Z}/hochblick --suche \"{nm}\" \"{ort} Luftbild\" \"{ort} Panorama\" --max 40", ":")      # Hochblicke (Commons): sehen Seiten ueber Nachbardaechern
        zeilen += download_zeile(Z, "openverse", f"python3 {T}/openverse_holen.py --aus {Z}/openverse --suche \"{nm}\" \"{obj.get('name', '')}\" \"{ort} Altstadt Blick\" --max 150", ":")      # Flickr u. a. ueber Openverse, nur CC0/BY/BY-SA
        zeilen.append(f"for f in {Z}/commons/*.jpg {Z}/hochblick/orig/*.jpg {Z}/openverse/*.jpg; do [ -e \"$f\" ] && ln -sf \"$f\" {Z}/roh/dl_$(basename $(dirname \"$f\"))__$(basename \"$f\"); done")
    zeilen += [f"ln -sf \"{f}\" {Z}/roh/" for f in kand]
    vf = kamera_verfeinern_zeile(VS, T, os.path.abspath(a.objekt), os.path.join(os.path.abspath(a.fassaden), 'fassaden.json'), audit, Z)
    # (name, Werkzeuge im CODE-STAND (nur billige Folgeschritte, tools/code_stand.py), vor dem Neurechnen loeschen, Befehl) - teure Schritte haengen nur an den Eingaben
    schritte = [("vorbereiten", "", f"{Z}/bilder {Z}/vorbereitet.json {Z}/merkmale.json {Z}/db.db {Z}/lg", f"{VC} {T}/zusatzfotos_registrieren.py vorbereiten --fotos {Z}/roh --aus {Z} --unten 0.0"),
                ("merkmale", "", f"{Z}/db.db {Z}/db.db-shm {Z}/db.db-wal {Z}/merkmale.json", sift_schalter() + f"{VC} {T}/zusatzfotos_registrieren.py merkmale --ref-db {a.ref_db} --sparse {a.sparse} --aus {Z}"),
                ("probe_db", "colmap_rig_abgleich.py", "", f"{VC} {T}/colmap_rig_abgleich.py probe --db {Z}/db.db --sparse {a.sparse}   # zweite Vorpruefung auf der erweiterten DB, VOR den GPU-Paaren"),
                ("refnamen", "", "", f"{VC} {T}/zusatzfotos_lightglue.py refnamen --ziel {Z} --ref-sparse {a.sparse}"),
                ("paare", "", "", f"{VS} {T}/zusatzfotos_lightglue.py paare --ziel {Z} --ref-sparse {a.sparse} --ref-bilder {fd}"),
                ("einlesen", "zusatzfotos_lightglue.py colmap_rig_abgleich.py", "", f"{VC} {T}/zusatzfotos_lightglue.py einlesen --ziel {Z} --ref-sparse {a.sparse}"),
                ("registrieren", "zusatzfotos_registrieren.py", "", f"{VC} {T}/zusatzfotos_registrieren.py registrieren --sparse {Z}/lg/ref_tri --aus {Z}/lg --je-bild --kalibrieren"),
                # 24.11.2026 (1122zb): VOR dem Nachtragen abgeleitete Altkameras im Gebaeude sperren - kameras_nachtragen ueberschreibt vorhandene K-Dateien nie
                ("kameras_nachtragen", "kameras_nachtragen.py kameras_nachtragen_tor.py", "", f"{VS} -W ignore {T}/kameras_nachtragen_tor.py {os.path.abspath(a.objekt)} --fassaden {os.path.join(os.path.abspath(a.fassaden), 'fassaden.json')} --altbestand && "
                 f"{VC} {T}/kameras_nachtragen.py {os.path.abspath(a.objekt)} {Z}/lg/sparse_handy/0 --bilder {Z}/roh   # neue Posen als K-Dateien in den Modellrahmen (Gegenprobe gegen vorhandene Kameras; rc 4 = Abbildung unbrauchbar)"),
                ("kamera_verfeinern", "kamera_verfeinern.py", "", vf),
                # 23.11.2026 (Kette 1122q: 327 neue Kameras, 'gegenprobe' 0 pruefte keine davon): Gueltigkeits-Tor - unplausible und nicht am Modell belegte neue Kameras gesperrt,
                # je Wand Zahl der belegten neuen Kameras, die sie sehen (audit/kameras_nachtragen_tor.json; die Kette entscheidet damit ueber die Wiederholung von Wandbild/Bau)
                ("kameras_tor", "kameras_nachtragen_tor.py kamera_plausibel.py", "", f"{VS} -W ignore {T}/kameras_nachtragen_tor.py {os.path.abspath(a.objekt)} --fassaden {os.path.join(os.path.abspath(a.fassaden), 'fassaden.json')} || [ $? = 3 ]   # rc 3 = keine belegte Kamera (kein Abbruch)")]
    zeilen.append(f"KETTE=$(ls -lL {Z}/roh | sha1sum | cut -c1-16)   # Kette der Schritt-Schluessel beginnt mit dem Kandidatenbestand (Downloads aendern ihn)")
    for n_, cw, weg, cmd in schritte:
        zeilen += [f"if schritt_noetig {n_} '{cw}' {hashlib.sha1(cmd.encode()).hexdigest()[:12]}; then"] + ([f"  rm -rf {weg}"] if weg else []) + [f"  {cmd}", f"  schritt_fertig {n_}", "fi"]
    zeilen.append("echo NACHHOLEN_FERTIG")
    zeilen.append(f"rm -rf {Z}/lg {Z}/db.db {Z}/db.db-shm {Z}/db.db-wal {Z}/stand   # 17.11.2026: Zwischenstaende nach dem letzten Schritt wegraeumen (am Kettenturm 3,2 GB; der naechste Lauf loescht und rechnet sie ohnehin neu) - die Datenplatte fiel dadurch unter die 5-GB-Grenze")
    sk = os.path.join(audit, "seiten_luecken_holen.sh"); open(sk, "w").write("\n".join(zeilen) + "\n"); os.chmod(sk, 0o755)
    for alt in glob.glob(os.path.join(audit, "seiten_luecken_kandidaten_*.jpg")): os.remove(alt)      # Folgeseiten eines frueheren Laufs
    if ziel and kand: kontaktboegen(kand, os.path.join(audit, "seiten_luecken_kandidaten.jpg"))
    sys.path.insert(0, T); __import__("json_sicher").schreiben(os.path.join(audit, "seiten_luecken.json"), dict(waende=waende, ungesehen=[w["nr"] for w in ung], teilweise=[w["nr"] for w in teil], teil_schwellen=dict(anteil=TEIL_MIN_ANTEIL, m2=TEIL_MIN_M2), fotobestand=len(alle), nicht_registriert=[os.path.basename(f) for f in kand], skript=sk, zielordner=Z))
    if not ziel:
        klein = [w for w in waende if w["ohne_daten_m2"] >= 30]      # 16.11.2026: "alle Waende gesehen" stand neben einem Fotoauftrag ueber 240 m2 - die Wandschwelle (20 %) sieht grosse Loecher in einer sonst gesehenen Wand nicht
        print("keine Wand ganz ungesehen" + ("; ABER " + ", ".join(f"f{w['nr']:02d} {w['ohne_daten_m2']:.0f} m2" + (f" (fotografierbar {w['ohne_daten_frei_m2']:.0f} m2)" if w.get("ohne_daten_frei_m2") is not None else "") for w in klein) + f" ohne Bilddaten - unter der Nachhol-Schwelle (>= {TEIL_MIN_ANTEIL:.0%} der fotografierbaren Wand UND >= {TEIL_MIN_M2:g} m2), nur Fotoauftrag (Ziele: tools/foto_auftrag.py)" if klein else " - alle Waende gesehen")); return 0
    if teil: print("TEILWEISE UNGESEHEN (loest Nachholen aus): " + ", ".join(f"f{w['nr']:02d} {w.get('ohne_daten_frei_m2', w['ohne_daten_m2']):.0f} m2 fotografierbar ohne Bilddaten" + (f" (Zone z {w['zone_ohne_daten']['z_von']:.1f}-{w['zone_ohne_daten']['z_bis']:.1f} m)" if w.get("zone_ohne_daten") else "") for w in teil), flush=True)
    print(f"{'UNGESEHEN' if ung else 'NACHHOLEN FUER TEILWEISE UNGESEHENE'}: {', '.join('f%02d' % w['nr'] for w in ziel)} -> {len(kand)} nicht registrierte Fotos als Kandidaten; Skript {sk}" + ("" if a.holen else "  (mit --holen ausfuehren; --download holt zusaetzlich Commons-Fotos)"))
    if a.holen:
        ok_b, grund_b = belegbar(a.objekt)      # 24.11.2026 FRUEH-ABBRUCH: ohne Modell/Referenzkameras endet das Nachholen sicher mit '0 belegt' - nicht erst nach ~60 min
        if not ok_b and os.environ.get("SEITEN_NEU") != "1":
            print(f"FEHLER: Nachholen UEBERSPRUNGEN (Frueh-Abbruch, keine Fehlschlag-Marke - laeuft von selbst, sobald die Eingabe stimmt): {grund_b}; erzwingen: SEITEN_NEU=1"); return 5
        # 16.11.2026 (Stabilisierung): jeder Kettenlauf wiederholte ~30 min Nachregistrieren derselben Kandidaten mit demselben Ergebnis
        schl = hashlib.sha1(("|".join(sorted(f"{os.path.basename(f)}:{os.path.getsize(f)}" for f in kand)) + "|" + ",".join(str(w["nr"]) for w in ziel) + "|" + open(sk).read()).encode()).hexdigest()[:16]
        marke = os.path.join(Z, "versucht_" + schl + ".txt"); fmarke = os.path.join(Z, "fehlschlag_" + schl + ".json"); cs = code_stand(*NACHHOL_WERKZEUGE)
        if os.path.exists(marke) and os.environ.get("SEITEN_NEU") != "1":
            print(f"Nachholen UEBERSPRUNGEN: dieselben {len(kand)} Kandidaten fuer dieselben Waende wurden schon versucht ({open(marke).read().strip()}); neu erzwingen: SEITEN_NEU=1"); return 3
        kv_, kv_text = kandidaten_versucht(Z, kand)
        if not ung and kv_ and os.environ.get("SEITEN_NEU") != "1":      # 24.11.2026: nur TEILWEISE ungesehen -> dieselben Kandidaten nie ein zweites Mal (Kosten ~48 min + Teillauf)
            print(f"Nachholen UEBERSPRUNGEN (teilweise ungesehen): {kv_text} - kein zweiter Versuch ohne neues Foto; "
                  f"bleibt die Zone leer: FOTOAUFTRAG (tools/foto_auftrag.py, audit/foto_auftrag.png). Neu erzwingen: SEITEN_NEU=1"); return 3
        # 22.11.2026 FEHLSCHLAG-MARKE: 1122c und 1122d stuerzten an derselben Stelle ab (RigId, 44 min) - die Erfolgsmarke fehlte, also rechnete jeder Lauf alles neu.
        # Gleiche Eingaben + gleicher CODE-STAND der Nachhol-Werkzeuge -> derselbe Fehler, sofort rc 5 (in 1 s). Nach einer Codeaenderung laeuft es wieder (Zwischenstaende je Schritt bleiben).
        try: F = json.load(open(fmarke)) if os.path.exists(fmarke) else None
        except ValueError: F = None
        if F and sperrt(F, cs) and os.environ.get("SEITEN_NEU") != "1":
            print(f"FEHLER: Nachholen UEBERSPRUNGEN - bekannter Fehlschlag ({F.get('zeit')}, rc {F.get('rc')}, Schritt {F.get('schritt')}) bei gleichen Eingaben und gleichem CODE-STAND {cs} "
                  f"(eingerechnet: {', '.join(os.path.basename(p) for p in code_dateien(*NACHHOL_WERKZEUGE))}); "
                  f"erst Werkzeug beheben (dann laeuft es von selbst neu) oder SEITEN_NEU=1 erzwingen. Marke {fmarke}"); return 5
        if F and not sperrt(F, cs): print(f"Fehlschlag-Marke {os.path.basename(fmarke)} sperrt nicht ({'Speichermangel - voruebergehend' if F.get('art') == 'speicher' else 'CODE-STAND geaendert ' + str(F.get('code_stand')) + ' -> ' + cs}): neuer Versuch", flush=True)
        if os.environ.get("SEITEN_NEU") == "1": subprocess.call(["rm", "-rf", os.path.join(Z, "stand")])      # erzwungen: auch die Zwischenstaende je Schritt verwerfen
        t0 = time.time(); rc, schluss = skript_laufen(sk, os.path.join(Z, "nachholen_letzter_lauf.log"))
        if rc:
            try: schritt = open(os.path.join(Z, "stand", "aktuell")).read().strip()
            except OSError: schritt = "vor dem ersten Schritt (Vorpruefung/Download)"
            art = "speicher" if speicher_fehler(rc, schluss) else "fest"
            os.makedirs(Z, exist_ok=True); __import__("json_sicher").schreiben(fmarke, dict(zeit=time.strftime("%Y-%m-%d %H:%M"), rc=rc, schritt=schritt, sekunden=round(time.time() - t0), code_stand=cs, art=art,
                                                                                          werkzeuge=list(NACHHOL_WERKZEUGE), skript=sk, log=os.path.join(Z, "nachholen_letzter_lauf.log")))
            print(f"FEHLER: Nachholen abgebrochen, rc {rc} im Schritt {schritt} nach {time.time() - t0:.0f} s (Skript {sk}); Fehlschlag-Marke {fmarke} (CODE-STAND {cs}"
                  + (", SPEICHERMANGEL im Schritt - Marke sperrt NICHT, Wiederholung rechnet neu)" if art == "speicher" else ")")); return 5      # 17.11.2026: endete mit rc 3 wie 'Wand ungesehen, Nachholen gelaufen' - die Kette wertete das abgebrochene Skript als in Ordnung
        else:
            os.makedirs(Z, exist_ok=True); open(marke, "w").write(time.strftime("%Y-%m-%d %H:%M") + f", {len(kand)} Kandidaten")
            kandidaten_merken(Z, kand, [w["id"] for w in ziel])      # Kandidaten-Liste (teilweise ungesehene Waende versuchen dieselben Kandidaten nicht erneut)
            if os.path.exists(fmarke): os.remove(fmarke)
    return 3


if __name__ == "__main__":
    sys.exit(main())
