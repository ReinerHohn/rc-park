#!/usr/bin/env python3
"""sfm_seiten_modelle.py <arbeitsordner> <fotoordner> [--seiten seiten.json] [--db-mapper db_mapper.db] [--db-ursprung db.db] [--min-bilder 30] [--nur-modelle] [--einsetzen]

JE SEITE EIN KAMERAMODELL, JE SEITE EINE DICHTE WOLKE, DANN VEREINEN (21.11.2026; Handbeweis Martinstor: modelle/GLOBALER_MAPPER_STABIL.md 12:23-14:42,
tools/versuche/mt_global_gefiltert_1121.sh). Die Seitenerkennung (tools/seiten_erkennen.py --streng) trennt aehnliche Seiten eines symmetrischen Baus in Bildteile ohne echte
Verbindung; ein Mapper kann sie nicht in ein Modell legen. Bisher meldete die Kette nur "Seite fehlt in sparse/0". Hier die bewiesene Folge:
  PHASE 1 modelle()         (CPU) je Bildteil mit >= --min-bilder Bildern (kleinere werden GEMELDET, nicht gerechnet): view_graph_calibrator auf einer DB-Kopie, dann
                            `colmap global_mapper --GlobalMapper.image_list_path teil<i>.txt` ZWEIMAL (Lauf a, b). a gegen b: tools/modell_lage_vergleich.py (Zahl in den Bericht),
                            Wahl des Laufs: lauf_wahl(), Sperrliste: tools/brennweite_schaerfe.py.
  PHASE 2 dicht_vereinen()  (GPU) je Teil tools/dicht_modell.py (OHNE Sperrliste, siehe DICHT_MIT_SPERRLISTE); Teil A = Teil mit den meisten Bildern im Modell; jeder weitere Teil gegen A: tools/seiten_vereinen.py
                            (URSPRUNGS-Datenbank mit den Querpaaren, NICHT db_seiten.db). rc 0 -> Teil wird in das VEREINTE Modell gelegt (modelle_zusammen), danach
                            tools/seiten_blick_tor.py auf dem vereinten Modell (rc 3 = dieser Teil wird wieder herausgenommen). rc 3/2 -> Teil bleibt draussen und wird mit den
                            Pruefwerten aus vereinen.json GEMELDET; ohne vereinten Teil gilt Teil A allein.
                            GPS-Weg (22.11.2026): ein Teil wird nur eingesetzt, wenn seine Lage UNABHAENGIG belegt ist (tools/seiten_lage_beleg.py); sonst weggelassen und als
                            FOTOLUECKE gemeldet ('fotoluecken' im Bericht; gesamtkette Stufe tore, foto_auftrag --seiten-modelle). RCPARK_TEIL_NUR_BELEGT=0 = alter Stand.
Ausgaben in <arbeitsordner>/seiten_modelle/: teil<i>.txt, teil<i>_a/, teil<i>_b/ (Mapper), teil<i>/{vgl_a_b.json, schaerfe.json, sperrliste.txt, dicht/}, vereinen_<A>_<B>/,
  vereint/sparse (EIN COLMAP-Modell, alle vereinten Seiten im System von Teil A, darin vereint.json) und vereint/dicht (COLMAP-Arbeitsordner: images, sparse, stereo, fused.ply).
  <arbeitsordner>/seiten_modelle.json = Bericht (Teile, Bildzahlen, Laufzeiten, gewaehlter Lauf, a/b-Abweichung, Pfade, Meldungen, 'ergebnis' fuer die Folgestufen).
  --einsetzen: 'ergebnis.sparse' nach <arbeitsordner>/sparse/0 kopieren (vorhandenes sparse/ wird beiseitegelegt, nichts geloescht) - das macht tools/iphone_sfm.py.
  Die dichte Wolke uebernimmt tools/pipeline_objekt.py (Verknuepfung dicht -> 'ergebnis.dicht'), damit sie nicht doppelt gerechnet wird.
Zwischenstaende werden wiederverwendet (Stand-Dateien mit Groesse + Zeit der Eingaben); aendern sich Datenbank oder seiten.json, wird seiten_modelle/ beiseitegelegt.
  Vereinen (Klappung, Foto-GPS) traegt zusaetzlich den CODE-STAND seines Werkzeugs (tools/code_stand.py) -> nach einer Codeaenderung laeuft nur das Vereinen neu; der Bericht
  traegt 'nachstufe_code' (NACHSTUFE), an dem tools/pipeline_objekt.py erkennt, dass sparse/0 zu altem Code gehoert.
WIE DAS VEREINTE MODELL ENTSTEHT (modelle_zusammen): pycolmap 4.2.1 kann Bilder eines zweiten Modells nicht per add_image uebernehmen ("Check failed: frame.RigPtr() == &rig" -
  Bild/Frame zeigen auf Rig-Objekte des alten Modells). Sauberer Weg: Modell B mit Reconstruction.transform(Sim3d aus 'B_nach_A') umrechnen, dann NEUES Modell aufbauen:
  Kamera + triviales Rig (add_camera_with_trivial_rig), Bild als NEUES Image (Name, Bildpunkte, Kamera-ID, Bild-ID) + trivialer Frame mit Lage (add_image_with_trivial_frame),
  3D-Punkte mit neuer ID und ihrer Spur (add_point3D). Bild-IDs bleiben (gleiche Datenbank, Teile sind bilddisjunkt -> Nachregistrieren gegen die DB geht weiter); Punkt-IDs neu;
  eine Kamera-ID, die in beiden Teilen mit VERSCHIEDENEN Werten vorkommt (Videoclip auf beiden Seiten, getrennt ausgeglichen), bekommt fuer den zweiten Teil eine neue ID.
  Fester Test tools/test_seiten_modelle.py. GRENZEN: nur Modelle mit einem Sensor je Rig; die Seiten haben KEINE gemeinsamen 3D-Punkte (tools/modell_zerlegen.py meldet zu Recht
  mehrere Stuecke - ihre Lage zueinander kommt aus seiten_vereinen, nicht aus Spuren); kein gemeinsamer Buendelausgleich; fused.ply.vis und consistency_graphs werden nicht vereint.
Rechenaufrufe (COLMAP, dicht_modell, Pruefwerkzeuge) laufen ueber LAUF(cmd, log) - im Test ersetzbar. rc 0 = Ergebnis da (auch 'Teil A allein'), 2 = weniger als zwei Teile mit
  genug Bildern (nichts gerechnet), 3 = kein Teilmodell entstanden.
Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap). Lange Laeufe nur per Skill langer-job (Martinstor Nord 538 Bilder: je Lauf ~15 min, Sued 102: ~2 min)."""
import os, sys, json, time, shutil, subprocess, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from pfade import PY, COLMAP
from sfm_seiten_vorstufe import _stand, _aktuell
from code_stand import code_stand

PYC = PY["col"]
CUDA_LIBS = ["/media/oem/scan/cuda-toolkit-combo/lib64", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib", "/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib",
             "/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib"]   # wie iphone_sfm.py (11:26 erster Handstart ohne: libcudart fehlte)
MIN_BILDER = 30          # ANNAHME (Vorschlag Auftrag, nicht gemessen): Martinstor Teile 538/102/55/34 gerechnet waeren 4, vereint wurden bisher nur 538 + 102
MIN_IM_MODELL = 10       # ANNAHME: ein Teilmodell mit weniger registrierten Bildern gilt als nicht entstanden (seiten_blick_tor zaehlt Gruppen ab 5 Bildern)
AB_WARNUNG = 0.25        # ANNAHME: mehr als 25 % der gemeinsamen Bilder > 2 % der Szene verschieden = "Laeufe uneinig" (gemessen: Nord 74 von 538 = 14 %, Sued 8 von 101 = 8 %)
SPERR_MAX = 0.5          # ANNAHME wie pipeline_objekt.py: sperrt die Schaerfe-Liste mehr als die Haelfte der Bilder, wird sie nicht angewandt
# DICHTE WOLKEN DER SEITEN OHNE SPERRLISTE (21.11.2026, Kettenlauf Martinstor: seiten_vereinen lehnte Teil 1 ab, "Turmhoehen 19,8 % verschieden", Bild: Sued ohne Dach).
# Ursache: die Sperrliste (Brennweite unbestimmt/zu_wenig) traf 39 von 101 Sued-Bildern - die Teleaufnahmen des Helms. In der Handwolke ohne Sperrliste haengen 71 % der
# Punkte im obersten Band (0,9-1,05 H) an weniger als 3 ungesperrten Bildern (Mitte 0,4-0,6 H: 23 %). Ohne Dach sucht seiten_vereinen die Spitze von B an der Traufe.
# Beleg: Kettenmodelle + Klappung unveraendert, nur die Sued-Wolke ohne Sperrliste -> vereint, Turmhoehen 1,9 % (Hand: Sperrliste nie fuer die dichte Wolke benutzt).
# Die Sperrliste wird weiter berechnet und gemeldet, fuer die dichten Wolken der Seiten aber nicht angewandt (alle Teile gleich, damit die Hoehenprobe Gleiches vergleicht).
DICHT_MIT_SPERRLISTE = False
# 22.11.2026 Rueckfall GPS: scheitert die Klappung (seiten_vereinen.py), legt tools/seiten_gps_vereinen.py den Teil ueber das Foto-GPS auf Teil A (Schwabentor: Teil 1 mit
# 24 von 26 GPS-Kameras; Blick-Tor 168 Grad, GPS-Seiten-Tor 4 % ueber 12 m am vereinten Modell). Abschalten: RCPARK_SEITEN_GPS=0.
GPS_VEREINEN = os.environ.get("RCPARK_SEITEN_GPS", "1") != "0"
# CODE-STAND DER NACHSTUFE (22.11.2026, Nulllauf kette-schwabentor-null-1122c: der GPS-Rueckfall war in main, lief aber nie - sparse/0 und seiten_modelle.json von 02:39 galten
# weiter, weil nur die Eingaben im Stand standen). Teuer und nur an Eingaben gebunden: Mapper je Teil, a/b-Vergleich, Sperrliste, dichte Wolke je Teil. Billig und an den CODE
# gebunden: Vereinen (Klappung, Foto-GPS), Zusammenlegen, Blick-/GPS-Seiten-Tor, Einsetzen. Die Werkzeuge der Nachstufe (samt ihrer Hilfsmodule, tools/code_stand.py) ergeben
# 'nachstufe_code' in seiten_modelle.json; tools/pipeline_objekt.py rechnet iphone_sfm.py erneut (nur die Nachstufe), wenn er nicht mehr zum Code passt.
NACHSTUFE = ("sfm_seiten_modelle.py", "seiten_eck_koppeln.py", "sim3_robust.py", "seiten_vereinen.py", "seiten_gps_vereinen.py", "seiten_blick_tor.py", "gps_seiten_pruefen.py", "sfm_gps_ausgleich.py", "seiten_querspur_binden.py",
             "seiten_lod2_je_teil.py", "seiten_lage_beleg.py", "seiten_waende_binden.py", "teil_gelaende_tor.py")
# 22.11.2026 TEILE UEBER QUERSPUREN BINDEN nach dem GPS-Vereinen (tools/seiten_querspur_binden.py, querspur_stufe; Nulllauf 1122f: GPS-Lage von Teil 1 nur +-3,6 Grad/+-12 %,
# Ostwand 1-2,5 m ausserhalb LoD2, Westwand doppelt). Querpaare der Ursprungs-DB -> 3D-3D -> RANSAC-Sim3 NUR im GPS-Korridor (GPS = Veto, nicht gemittelt). NUR auf dem GPS-Weg:
# auf dem Klappungs-Weg (Martinstor) SIND die Querpaare die Gegenseiten-Verwechslung und es gibt kein unabhaengiges Veto. Nach einer Bindung wird der GPS-Ausgleich AUSGELASSEN:
# die Teile haben im vereinten Modell keine gemeinsamen 3D-Punkte, sfm_gps_ausgleich zoege jeden Teil (>= 15 Geotags) wieder einzeln aufs GPS = Bindung rueckgaengig.
# Abschalten: RCPARK_QUERSPUR=0.
QUERSPUR = os.environ.get("RCPARK_QUERSPUR", "1") != "0"
# 22.11.2026 GEMEINSAMER AUSGLEICH MIT GPS-PRIOREN nach dem Vereinen (tools/sfm_gps_ausgleich.py, gps_ausgleich_stufe). Nur ab 40 unabhaengigen Geotags, nur wenn Bildfehler nicht
# schlechter und GPS-Rest kleiner; sonst unveraendert (gemeldet). Abschalten: RCPARK_GPS_AUSGLEICH=0. VERFORM_MAX_PROZ nur fuer die Meldung (Grenze steht im Werkzeug).
GPS_AUSGLEICH = os.environ.get("RCPARK_GPS_AUSGLEICH", "1") != "0"
VERFORM_MAX_PROZ = 0.002
# 22.11.2026 LoD2 JE TEIL nach dem GPS-Vereinen (tools/seiten_lod2_je_teil.py, lod2_stufe; Nutzerwunsch "amtlichen Grundriss tiefer einbeziehen", Nulllauf 1122f: Teile per GPS
# vereint, dann EIN gemeinsamer LoD2-Fit - der kann die Teile nicht gegeneinander verschieben). Jeder Teil wird EINZELN im Kasten seiner GPS-Unsicherheit gegen die Kanten des
# Zielgebaeudes gelegt; uebernommen nur bei eindeutiger Lage beider Teile, besserem Wanddicke-Mass, gehaltenem GPS-Korridor und widerspruchsfreien Teilen. WARUM HIER und
# nicht in gesamtkette.tore: LoD2 und DGM1 stehen schon seit der Stufe 'anlegen' bereit (objekt.json lod2/rahmen, rahmen_aus_lod2.py); die Lage der Teile ZUEINANDER muss vor
# dem Zusammenlegen (modelle_zusammen, dicht_zusammen) feststehen - in 'tore' gibt es nur noch das vereinte Modell + eine gemeinsame Ausrichtung. objekt.json kommt ueber
# RCPARK_SEITEN_OBJEKT (setzt tools/pipeline_objekt.py); fehlt es, wird die Stufe gemeldet und uebersprungen. NUR auf dem GPS-Weg (Martinstor: Klappung, Kaufhaus: ein Teil).
# Abschalten: RCPARK_LOD2_JE_TEIL=0.
LOD2_JE_TEIL = os.environ.get("RCPARK_LOD2_JE_TEIL", "1") != "0"
# 22.11.2026 TEILE UEBER EIN ECKMODELL KOPPELN (tools/seiten_eck_koppeln.py, eck_stufe; schwabentor-1122: seiten_erkennen --durchblick fand echte Brueckenpaare um die
# Turmecke, der globale Mapper knickte Teil 1 dort um 25 Grad). Nach gescheiterter Klappung und VOR dem GPS-Weg: gibt es in seiten.json bestaetigte Brueckenpaare zwischen
# A und B, wird ein kleines Eckmodell gebaut und B ueber gemeinsame 3D-Punkte an A gekoppelt (beide Kopplungen stimmig, Massstab belegt). Danach Blick-Tor + GPS-Seiten-Tor
# (Veto) wie beim GPS-Weg. Ohne Brueckenpaare (Martinstor, alle Laeufe ohne --durchblick) aendert sich nichts. Abschalten: RCPARK_ECK_KOPPELN=0.
ECK_KOPPELN = os.environ.get("RCPARK_ECK_KOPPELN", "1") != "0"
# 24.11.2026 GEGENSEITE UEBER GEMEINSAME WAENDE BINDEN (tools/seiten_waende_binden.py, waende_stufe; Kettenlauf 1122w Teil 1 = Suedseite: Klappung falscher Ansatz (keine
# Verwechslung), Querspur abgelehnt, GPS-Lage 10 Grad gekippt und 4-5 Grad verdreht). Nach der Querspur, vor LoD2 je Teil, nur auf dem GPS-Weg mit dichten Wolken beider Teile:
# Lot von B aus seinen Waenden, Grundriss-Suche der B-Waende auf den A-Waenden im (ehrlichen) GPS-Korridor, Proben: eindeutig, zwei Hoehenbaender, Geotags von B, Turmspitze.
# Weg 'gps+waende' gilt als belegt (seiten_lage_beleg). Abschalten: RCPARK_WAENDE=0.
WAENDE = os.environ.get("RCPARK_WAENDE", "1") != "0"
# 24.11.2026 TOR 'TEIL UNTER GELAENDE' FUER JEDEN BINDUNGSWEG (tools/teil_gelaende_tor.py, gelaende_stufe; 1122z: Ost-Teil 6,4 m im Boden, nur der Nutzer sah es im Viewer).
# Vor dem Zusammenlegen jedes Teils B (Klappung, Eckmodell, GPS, Querspur, Waende, LoD2 je Teil): > 5 % der B-Punkte in Strassenzellen von A > 1 m unter dem Boden von A
# -> Teil WEGGELASSEN (Meldung mit Bodenversatz). Nicht pruefbar (kein GPS-Massstab, keine gemeinsame Strasse) -> nur Meldung. RCPARK_GELAENDE_TOR=hinweis = nur melden, =aus = nicht pruefen.
# Nachtrag 24.11.: dasselbe Tor NACH dem GPS-Ausgleich (ausgleich_gelaende_stufe; der Ausgleich verschiebt die Teile noch einmal) -> Teil danach unter Gelaende = Ausgleich VERWORFEN.
# Ohne GPS-Weg (Klappung/Eck) Massstab aus dem GPS-Rahmen von Teil A allein (teil_gelaende_tor --bilder).
GELAENDE_TOR = os.environ.get("RCPARK_GELAENDE_TOR", "an")
# 22.11.2026 REGEL "TEIL NUR BEI BELEGTER LAGE EINSETZEN" (tools/seiten_lage_beleg.py; schwabentor-1122: Teil 1 nur ueber GPS gelegt, 3-4 m versetzt -> Grundriss-Tor A 17,6 %,
# Wanddicke 'doppelwand'). Ein Teil auf dem GPS-Weg wird nur eingesetzt, wenn eine eigene Probe seine Lage belegt (Querspur, LoD2 je Teil, oder GPS ehrlich belegt UND
# Wanddicke der GPS-Lage widerspruchsfrei); sonst WEGGELASSEN und als FOTOLUECKE gemeldet (ber['fotoluecken']). Abschalten: RCPARK_TEIL_NUR_BELEGT=0 (steht im Code-Stand).
import seiten_lage_beleg as SLB
NUR_BELEGT = SLB.NUR_BELEGT


def nachstufe_code():
    """Code-Stand der Nachstufe (Vereinen, Zusammenlegen, Tore, Einsetzen) - 12 Hex-Zeichen."""
    return code_stand(*NACHSTUFE, wurzel=T) + ("" if NUR_BELEGT else "+belegt0")   # Schalter wechselt = Nachstufe neu (sonst gaelte das alte sparse/0 weiter)


def _lauf(cmd, log=None):
    """Ein Rechenaufruf; Ausgabe haengt an <log> an. Die COLMAP-Binaerdatei braucht die CUDA-Bibliotheken im Suchpfad."""
    env = dict(os.environ, LD_LIBRARY_PATH=":".join(CUDA_LIBS + [x for x in [os.environ.get("LD_LIBRARY_PATH", "")] if x]))
    if log:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a") as f: return subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    return subprocess.run(cmd, env=env).returncode


LAUF = _lauf             # im Test ersetzt (tools/test_seiten_modelle.py)


def sag(*a): print(*a, flush=True)


# ---------- Bildteile
def teile_lesen(sj):
    """seiten.json -> [dict(teil=i, bilder=[Bildnamen der Datenbank])]: Bildliste je Teil = alle Bilder, deren Gruppe ('gemeinschaft') in 'gruppen' des Teils steht."""
    d = json.load(open(sj)); L = []
    for i, t in enumerate(d.get("seiten", [])):
        gs = set(t["gruppen"]); L.append(dict(teil=i, bilder=sorted(n for n, k in d.get("gemeinschaft", {}).items() if k in gs)))
    return L


# ---------- Modellwerte und Wahl des Laufs
def modell_werte(ordner):
    """Bestes Untermodell eines Mapper-Ausgabeordners (<ordner>/<n>/, meiste registrierte Bilder) -> dict(pfad, bilder, punkte, fehler_px, stuecke) oder None."""
    import pycolmap
    best = None; n = 0
    for k in sorted(os.listdir(ordner)) if os.path.isdir(ordner) else []:
        p = os.path.join(ordner, k)
        if not (k.isdigit() and os.path.isfile(os.path.join(p, "images.bin"))): continue
        try: r = pycolmap.Reconstruction(p)
        except Exception: continue
        n += 1; w = dict(pfad=p, bilder=int(r.num_reg_images()), punkte=int(r.num_points3D()), fehler_px=round(float(r.compute_mean_reprojection_error()), 4))
        if best is None or w["bilder"] > best["bilder"]: best = w
    if best: best["stuecke"] = n
    return best


def lauf_wahl(wa, wb, n_teil):
    """REGEL fuer den besseren der zwei globalen Laeufe eines Teils -> ('a'|'b'|None, Begruendung).
      1. Nur ein Lauf hat ein Modell -> dieser (wird gemeldet: die a/b-Probe fehlt).
      2. MEHR REGISTRIERTE BILDER, wenn der Unterschied mindestens 1 % der Teilbilder und mindestens 2 Bilder betraegt: mehr Bilder = mehr Wand gesehen; kleinere Unterschiede
         sind Laufstreuung des nicht deterministischen Mappers (gemessen: Sued 101/101, Nord 538/538).
      3. Sonst der KLEINERE MITTLERE BILDFEHLER (px): gleich viele Bilder, die Punkte passen besser zu den Kameras (Nord a 0,91 px gegen b 1,00 px - von Hand wurde a genommen).
      4. Sonst Lauf a.
    ANNAHME: die 1-%-Grenze ist gesetzt, nicht gemessen. Die Punktzahl entscheidet NICHT (Nord b hatte mehr Punkte bei groesserem Fehler). Die a/b-Abweichung der Kameralagen
    (modell_lage_vergleich) sagt nicht, WELCHER Lauf besser ist - sie steht als Zahl im Bericht und warnt ab 25 % uneinigen Bildern."""
    if not wa and not wb: return None, "kein Lauf lieferte ein Modell"
    if not wb: return "a", "nur Lauf a lieferte ein Modell (a/b-Probe fehlt)"
    if not wa: return "b", "nur Lauf b lieferte ein Modell (a/b-Probe fehlt)"
    grenze = max(2, int(round(0.01 * n_teil)))
    if abs(wa["bilder"] - wb["bilder"]) >= grenze:
        g = "a" if wa["bilder"] > wb["bilder"] else "b"; return g, f"mehr registrierte Bilder ({wa['bilder']} gegen {wb['bilder']}, Grenze {grenze})"
    if wa["fehler_px"] != wb["fehler_px"]:
        g = "a" if wa["fehler_px"] < wb["fehler_px"] else "b"; return g, f"Bildzahl gleichwertig ({wa['bilder']}/{wb['bilder']}), kleinerer Bildfehler ({wa['fehler_px']} gegen {wb['fehler_px']} px)"
    return "a", "beide Laeufe gleichwertig"


# ---------- Phase 1: Mapper je Teil
def modelle(w, fotos, sj, db_mapper, min_bilder=MIN_BILDER):
    """Phase 1 -> Bericht (dict). 'grund' gesetzt = dieser Weg laeuft nicht (weniger als zwei Teile mit genug Bildern); der Aufrufer rechnet dann wie bisher."""
    arb = os.path.join(w, "seiten_modelle"); sd = os.path.join(arb, "stand.json"); st = _stand(db_mapper, sj) + [min_bilder]
    ber = dict(zeit=time.strftime("%Y-%m-%d %H:%M"), arbeit=arb, seiten_json=os.path.abspath(sj), db_mapper=os.path.abspath(db_mapper), min_bilder=min_bilder, teile=[], meldungen=[])
    alle = teile_lesen(sj); gross = [t for t in alle if len(t["bilder"]) >= min_bilder]
    for t in alle:
        if len(t["bilder"]) < min_bilder:
            ber["teile"].append(dict(teil=t["teil"], bilder=len(t["bilder"]), gerechnet=False, grund=f"unter {min_bilder} Bildern"))
            if len(t["bilder"]) >= 5: ber["meldungen"].append(f"Teil {t['teil']} ({len(t['bilder'])} Bilder) unter {min_bilder} Bildern - KEIN eigenes Modell, fehlt im Ergebnis")
    n_mini = sum(1 for t in alle if len(t["bilder"]) < 5)
    if n_mini: ber["meldungen"].append(f"{n_mini} Bildteil(e) mit weniger als 5 Bildern nicht gerechnet")
    if len(gross) < 2:
        ber["grund"] = f"{len(gross)} Bildteil(e) mit >= {min_bilder} Bildern - Seitenmodelle brauchen mindestens zwei"; return ber
    if os.path.isdir(arb) and os.path.isfile(sd) and not _aktuell(sd, st):               # Datenbank/seiten.json geaendert: alte Teilmodelle gehoeren zu einem anderen Stand
        alt = arb + ".alt_" + time.strftime("%Y%m%d_%H%M%S"); os.rename(arb, alt); sag(f"SEITENMODELLE: Eingaben geaendert - alter Stand beiseitegelegt: {alt} (nichts geloescht)")
    os.makedirs(arb, exist_ok=True); json.dump(st, open(sd, "w")); dbg = os.path.join(arb, "db_global.db"); kalibriert = [False]

    def kalibrieren():
        """Kalibrierung aendert Intrinsik/Zweibild-Geometrien -> nur auf der Kopie; erst beim ersten Lauf, der wirklich rechnen muss."""
        if kalibriert[0]: return True
        shutil.copyfile(db_mapper, dbg); rc = LAUF([COLMAP, "view_graph_calibrator", "--database_path", dbg], os.path.join(arb, "kalib.log"))
        if rc != 0: ber["meldungen"].append(f"view_graph_calibrator gescheitert (rc {rc}, {arb}/kalib.log)"); return False
        kalibriert[0] = True; return True

    for t in gross:
        i = t["teil"]; n = len(t["bilder"]); liste = os.path.join(arb, f"teil{i}.txt"); txt = "\n".join(t["bilder"]) + "\n"; td = os.path.join(arb, f"teil{i}"); os.makedirs(td, exist_ok=True)
        if not os.path.isfile(liste) or open(liste).read() != txt: open(liste, "w").write(txt)
        e = dict(teil=i, bilder=n, gerechnet=True, liste=liste, laeufe={}); ber["teile"].append(e)
        for l in "ab":
            z = os.path.join(arb, f"teil{i}_{l}"); fj = os.path.join(z, "fertig.json"); lf = None
            try: lf = json.load(open(fj)) if os.path.isfile(os.path.join(z, "0", "images.bin")) else None
            except Exception: lf = None
            if lf and lf.get("liste") == txt: lf = dict(rc=lf["rc"], sekunden=lf["sekunden"], wiederverwendet=True)
            else:
                lf = dict(rc=None, sekunden=0, wiederverwendet=False)
                if kalibrieren():
                    os.makedirs(z, exist_ok=True); t0 = time.time(); sag(f"SEITENMODELLE: Teil {i} ({n} Bilder) globaler Mapper Lauf {l} ...")
                    lf["rc"] = LAUF([COLMAP, "global_mapper", "--database_path", dbg, "--image_path", fotos, "--output_path", z, "--GlobalMapper.image_list_path", liste], os.path.join(z, "log.txt"))
                    lf["sekunden"] = round(time.time() - t0)
                    if lf["rc"] == 0 and os.path.isfile(os.path.join(z, "0", "images.bin")): json.dump(dict(rc=0, sekunden=lf["sekunden"], liste=txt), open(fj, "w"))
            wv = modell_werte(z) if lf["rc"] == 0 else None
            if wv: lf.update(wv)
            e["laeufe"][l] = lf
            sag(f"SEITENMODELLE: Teil {i} Lauf {l}: rc {lf['rc']}, {lf['sekunden']} s" + (" (wiederverwendet)" if lf["wiederverwendet"] else "") + (f", {wv['bilder']} von {n} Bildern, {wv['punkte']} Punkte, {wv['fehler_px']} px" + (f", {wv['stuecke']} Modelle" if wv["stuecke"] > 1 else "") if wv else ", KEIN Modell"))
        wa = e["laeufe"]["a"] if "pfad" in e["laeufe"]["a"] else None; wb = e["laeufe"]["b"] if "pfad" in e["laeufe"]["b"] else None
        g, regel = lauf_wahl(wa, wb, n); e["gewaehlt"] = g; e["regel"] = regel
        if g is None: ber["meldungen"].append(f"Teil {i} ({n} Bilder): KEIN Modell - beide globalen Laeufe gescheitert ({arb}/teil{i}_a/log.txt)"); continue
        gw = e["laeufe"][g]; e["modell"] = gw["pfad"]; e["im_modell"] = gw["bilder"]
        if gw["bilder"] < MIN_IM_MODELL: ber["meldungen"].append(f"Teil {i}: nur {gw['bilder']} von {n} Bildern im Modell (unter {MIN_IM_MODELL}) - gilt als NICHT entstanden"); e.pop("modell"); continue
        if gw["bilder"] < 0.5 * n: ber["meldungen"].append(f"Teil {i}: nur {gw['bilder']} von {n} Bildern im Modell (unter 50 %)")
        if gw.get("stuecke", 1) > 1: ber["meldungen"].append(f"Teil {i}: Lauf {g} schrieb {gw['stuecke']} Modelle - verwendet wird das groesste ({gw['bilder']} Bilder)")
        if wa and wb:                                                                    # a/b-Abweichung als Zahl (Messwerkzeug, rc immer 0)
            vj = os.path.join(td, "vgl_a_b.json")
            if not _neuer(vj, wa["pfad"], wb["pfad"]): LAUF([PYC, "-I", os.path.join(T, "modell_lage_vergleich.py"), wa["pfad"], wb["pfad"], "--aus", vj], os.path.join(td, "vgl_a_b.log"))
            try:
                v = json.load(open(vj)); e["ab"] = dict(gemeinsam=v["gemeinsam"], lage_median_proz=round(v["lage_median"], 3), lage_p90_proz=round(v["lage_p90"], 2), ueber_2_proz=v["ueber2"], bericht=vj)
                if v["gemeinsam"] and v["ueber2"] > AB_WARNUNG * v["gemeinsam"]: ber["meldungen"].append(f"Teil {i}: Laeufe a/b UNEINIG - {v['ueber2']} von {v['gemeinsam']} Bildern > 2 % der Szene verschieden (Lage dieses Teils nicht wiederholbar)")
            except Exception: e["ab"] = None; ber["meldungen"].append(f"Teil {i}: a/b-Vergleich nicht moeglich (zu wenige gemeinsame Bilder oder {td}/vgl_a_b.log)")
        else: e["ab"] = None; ber["meldungen"].append(f"Teil {i}: {regel}")
        sj_ = os.path.join(td, "schaerfe.json"); sp = os.path.join(td, "sperrliste.txt")  # Sperrliste: Kameras, deren Brennweite das Modell nicht festlegt (unbestimmt + zu_wenig)
        if not _neuer(sp, gw["pfad"]): LAUF([PYC, "-I", os.path.join(T, "brennweite_schaerfe.py"), gw["pfad"], "--aus", sj_, "--liste", os.path.join(td, "unbestimmt.txt"), "--sperrliste", sp], os.path.join(td, "schaerfe.log"))
        ns = len([z_ for z_ in open(sp) if z_.strip()]) if os.path.isfile(sp) else None
        e["sperrliste"] = dict(pfad=sp, bilder=ns, angewandt=bool(ns) and ns <= SPERR_MAX * gw["bilder"])
        if ns is None: ber["meldungen"].append(f"Teil {i}: brennweite_schaerfe gescheitert ({td}/schaerfe.log) - dichte Wolke OHNE Sperrliste")
        elif ns and not e["sperrliste"]["angewandt"]: ber["meldungen"].append(f"Teil {i}: Sperrliste {ns} von {gw['bilder']} Bildern (> 50 %) - NICHT angewandt")
        sag(f"SEITENMODELLE: Teil {i} -> Lauf {g} ({regel})" + (f"; a/b: Median {e['ab']['lage_median_proz']} % der Szene, {e['ab']['ueber_2_proz']} von {e['ab']['gemeinsam']} Bildern > 2 %" if e.get("ab") else "") + f"; Sperrliste {ns} Bilder")
    if os.path.isfile(dbg): os.remove(dbg)                                               # eigene Arbeitskopie (Martinstor 2,8 GB); die Modelle sind der Zwischenstand
    if not any(e.get("modell") for e in ber["teile"]): ber["fehler"] = "kein Teilmodell entstanden"
    return ber


def _neuer(ziel, *quellen):
    """Zwischenergebnis <ziel> ist da und nicht aelter als seine Eingaben (Ordner: images.bin darin)."""
    q = [os.path.join(x, "images.bin") if os.path.isdir(x) else x for x in quellen]
    return os.path.isfile(ziel) and all(os.path.exists(x) and os.path.getmtime(ziel) >= os.path.getmtime(x) for x in q)


# ---------- dichte Wolke: Punktzahl, Abbildung, Zusammenlegen
PLY_SATZ = np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 3)])


def ply_kopf(p):
    """-> (Punktzahl, Laenge des Kopfes in Byte, Kopfzeilen) einer binaeren PLY; (0, 0, []) wenn nicht lesbar."""
    try:
        with open(p, "rb") as f:
            n = 0; Z = []
            for _ in range(60):
                l = f.readline()
                if not l: break
                Z.append(l.decode(errors="replace").strip())
                if Z[-1].startswith("element vertex"): n = int(Z[-1].split()[-1])
                if Z[-1] == "end_header": return n, f.tell(), Z
    except Exception: pass
    return 0, 0, []


def sim3_aus_matrix(M):
    """4x4 'B_nach_A' -> (Massstab, Drehmatrix, Verschiebung). GUARD: nur echte Aehnlichkeitsabbildungen (keine Spiegelung, keine Scherung) - sonst ValueError."""
    M = np.asarray(M, float); L = M[:3, :3]; det = float(np.linalg.det(L))
    if M.shape != (4, 4) or not np.isfinite(M).all() or det <= 0: raise ValueError("B_nach_A ist keine Aehnlichkeitsabbildung (det <= 0 oder nicht endlich)")
    s = det ** (1.0 / 3.0); R = L / s
    if np.abs(R @ R.T - np.eye(3)).max() > 1e-6: raise ValueError("B_nach_A ist keine Aehnlichkeitsabbildung (Drehteil nicht orthogonal)")
    return s, R, M[:3, 3].copy()


def wolken_zusammen(teile, ziel, block=2000000):
    """teile = [(fused.ply, 4x4 oder None)] -> eine fused.ply im System des ersten Teils (Punkte s*R*x+t, Normalen R*n, Farbe bleibt). Nur das COLMAP-Format
    (x y z nx ny nz r g b, 27 Byte je Punkt); anderes -> ValueError (keine geratene Umrechnung). Rueckgabe: Punktzahl."""
    K = [ply_kopf(p) for p, _ in teile]; soll = [z for z in K[0][2] if z.startswith("property")]
    for (p, _), (n, h, Z) in zip(teile, K):
        if n <= 0 or len([z for z in Z if z.startswith("property")]) != 9 or [z for z in Z if z.startswith("property")] != soll or "format binary_little_endian 1.0" not in Z or os.path.getsize(p) < h + n * 27:
            raise ValueError(f"{p}: keine COLMAP-fused.ply (9 Eigenschaften, 27 Byte je Punkt)")
    N = sum(n for n, _, _ in K); tmp = ziel + ".teil"
    with open(tmp, "wb") as aus:
        aus.write(("\n".join(z if not z.startswith("element vertex") else f"element vertex {N}" for z in K[0][2]) + "\n").encode())
        for (p, M), (n, h, _) in zip(teile, K):
            with open(p, "rb") as f:
                f.seek(h); rest = n
                while rest > 0:
                    d = np.frombuffer(f.read(min(rest, block) * 27), PLY_SATZ).copy(); rest -= len(d)
                    if M is not None:
                        s, R, t = sim3_aus_matrix(M); d["p"] = (s * d["p"].astype(np.float64) @ R.T + t).astype(np.float32); d["n"] = (d["n"].astype(np.float64) @ R.T).astype(np.float32)
                    aus.write(d.tobytes())
    os.replace(tmp, ziel); return N


def tiefenkarte_skalieren(quelle, ziel, s):
    """COLMAP-Tiefenkarte ('breite&hoehe&kanaele&' + float32) mit dem Massstab s malnehmen (Tiefe laengs der Blickrichtung waechst mit dem Modellmassstab)."""
    b = open(quelle, "rb").read(); k = -1
    for _ in range(3): k = b.index(b"&", k + 1)
    open(ziel, "wb").write(b[:k + 1] + (np.frombuffer(b[k + 1:], "<f4") * np.float32(s)).astype("<f4").tobytes())


# ---------- das vereinte sparse-Modell
def _kamera_gleich(a, b):
    return a.model == b.model and a.width == b.width and a.height == b.height and len(a.params) == len(b.params) and np.allclose(a.params, b.params, rtol=1e-9, atol=0)


def db_kameras(*dbs):
    """Kamera-IDs aller genannten Datenbanken (fehlende/unlesbare uebersprungen - dann loest colmap_rig_abgleich.angleichen eine Kollision) - fuer modelle_zusammen(belegt=...)."""
    import sqlite3
    out = set()
    for p in dbs:
        if not (p and os.path.isfile(p)): continue
        try:
            con = sqlite3.connect(f"file:{os.path.abspath(p)}?mode=ro", uri=True)
            try: out |= {int(c) for (c,) in con.execute("select camera_id from cameras")}
            finally: con.close()
        except sqlite3.DatabaseError as e: sag(f"SEITENMODELLE: Kamera-IDs aus {p} nicht lesbar ({e}) - neue Kamera-IDs nur ueber den Modell-IDs")
    return out


def modelle_zusammen(teile, ziel, herkunft=None, belegt=()):
    """teile = [(Modellordner, 4x4 oder None)] -> EIN COLMAP-Modell in <ziel> (System des ersten Teils); Weg und Grenzen im Dateikopf. Rueckgabe dict(bilder, punkte, kameras_neu,
    teile=[dict(pfad, bilder, punkte)]). ValueError, wenn es nicht sauber geht (Bild doppelt, Rig mit mehreren Sensoren, keine Aehnlichkeitsabbildung) - dann schreibt die
    Funktion NICHTS und der Aufrufer bleibt beim Rueckfall (Teil A allein, gemeldet).
    belegt = Kamera-IDs der Datenbank(en) (db_kameras). 23.11.2026 (Kette 1122r): die neue ID einer doppelt ausgeglichenen Kamera war max(Modell)+1 = 822..824 und damit in
    der Datenbank schon die Kamera ANDERER Videobilder -> Nachholen (tools/colmap_rig_abgleich.py probe) scheiterte an "existing_camera.width == camera.width (1280 vs. 1920)".
    Neue IDs liegen jetzt ueber allen belegten DB-IDs; colmap_rig_abgleich.angleichen legt die Kamera in der DB-Kopie an (und loest Altmodelle mit Kollision selbst)."""
    import pycolmap
    V = pycolmap.Reconstruction(); namen = set(); info = []; kneu = 0
    for pfad, M in teile:
        Q = pycolmap.Reconstruction(pfad)
        if M is not None: s, R, t = sim3_aus_matrix(M); Q.transform(pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t))
        if any(r.num_sensors() != 1 for r in Q.rigs.values()): raise ValueError(f"{pfad}: Rig mit mehreren Sensoren - Zusammenlegen nur fuer Einzelkameras gebaut")
        reg = sorted(Q.reg_image_ids()); rs = set(reg); kmap = {}
        for i in reg:
            c = Q.images[i].camera_id
            if c in kmap: continue
            q = Q.cameras[c]; neu = c
            if V.exists_camera(c):
                if _kamera_gleich(V.cameras[c], q): kmap[c] = c; continue
                neu = max(max(V.cameras), max(Q.cameras), max(kmap.values(), default=0), max(belegt, default=0)) + 1; kneu += 1   # gleiche ID, andere Werte: getrennt ausgeglichene Kamera
            V.add_camera_with_trivial_rig(pycolmap.Camera(model=q.model, width=q.width, height=q.height, params=q.params, camera_id=neu, has_prior_focal_length=q.has_prior_focal_length)); kmap[c] = neu
        for i in reg:
            im = Q.images[i]
            if im.name in namen or V.exists_image(i): raise ValueError(f"Bild {im.name} (ID {i}) steht in zwei Teilen - die Teile muessen bilddisjunkt aus EINER Datenbank kommen")
            namen.add(im.name); xy = np.array([p.xy for p in im.points2D], float).reshape(-1, 2)
            V.add_image_with_trivial_frame(pycolmap.Image(name=im.name, keypoints=xy, camera_id=kmap[im.camera_id], image_id=i), im.cam_from_world())
        np_ = 0
        for pid in sorted(Q.points3D):
            p = Q.points3D[pid]; tr = pycolmap.Track(); k = 0
            for el in p.track.elements:
                if el.image_id in rs: tr.add_element(el.image_id, el.point2D_idx); k += 1
            if k < 2: continue
            V.points3D[V.add_point3D(p.xyz, tr, p.color)].error = p.error; np_ += 1
        info.append(dict(pfad=os.path.abspath(pfad), bilder=len(reg), punkte=np_, matrix=None if M is None else np.asarray(M, float).tolist()))
    tmp = ziel.rstrip("/") + ".teil"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp); V.write(tmp)
    erg = dict(bilder=int(V.num_reg_images()), punkte=int(V.num_points3D()), kameras_neu=kneu, fehler_px=round(float(V.compute_mean_reprojection_error()), 4), teile=info)
    json.dump(dict(erg, zeit=time.strftime("%Y-%m-%d %H:%M"), herkunft=herkunft, hinweis="Seiten ohne gemeinsame 3D-Punkte, Lage aus tools/seiten_vereinen.py (B_nach_A); tools/modell_zerlegen.py meldet zu Recht mehrere Stuecke"),
              open(os.path.join(tmp, "vereint.json"), "w"), indent=1)
    if os.path.isdir(ziel): shutil.rmtree(ziel)                                           # nur der eigene, neu erzeugbare Zielordner
    os.rename(tmp, ziel); return erg


def dicht_zusammen(teile, ziel, belegt=()):
    """teile = [(dicht-Arbeitsordner eines Teils, 4x4 oder None)] -> EIN COLMAP-Arbeitsordner <ziel> im System des ersten Teils: images/ (Verknuepfungen), sparse/ (entzerrte Modelle
    vereint), stereo/depth_maps (Teil A verknuepft; umgerechnete Teile als KOPIE mit Massstab), stereo/normal_maps (Verknuepfungen: Normalen stehen im Kamerasystem),
    stereo/*.cfg (aneinandergehaengt), fused.ply (wolken_zusammen). fused.ply.vis und consistency_graphs fehlen (GRENZE)."""
    tmp = ziel.rstrip("/") + ".teil"; shutil.rmtree(tmp, ignore_errors=True)
    for u in ("images", "stereo/depth_maps", "stereo/normal_maps"): os.makedirs(os.path.join(tmp, u))
    for d, M in teile:
        d = os.path.abspath(d); s = None if M is None else sim3_aus_matrix(M)[0]
        for u in ("images", "stereo/normal_maps", "stereo/depth_maps"):
            for f in sorted(os.listdir(os.path.join(d, u))) if os.path.isdir(os.path.join(d, u)) else []:
                z = os.path.join(tmp, u, f)
                if os.path.lexists(z): continue
                if u.endswith("depth_maps") and s is not None and f.endswith(".bin"): tiefenkarte_skalieren(os.path.join(d, u, f), z, s)
                else: os.symlink(os.path.join(d, u, f), z)
        for c in ("fusion.cfg", "patch-match.cfg"):
            if os.path.isfile(os.path.join(d, "stereo", c)): open(os.path.join(tmp, "stereo", c), "a").write(open(os.path.join(d, "stereo", c)).read().rstrip("\n") + "\n")
    erg = dict(sparse=modelle_zusammen([(os.path.join(d, "sparse"), M) for d, M in teile], os.path.join(tmp, "sparse"), belegt=belegt))
    erg["punkte"] = wolken_zusammen([(os.path.join(d, "fused.ply"), M) for d, M in teile], os.path.join(tmp, "fused.ply"))
    if os.path.isdir(ziel): shutil.rmtree(ziel)
    os.rename(tmp, ziel); return erg


# ---------- Phase 2: dichte Wolken je Teil, vereinen, Blick-Tor
def dicht_vereinen(w, fotos, sj, db_ursprung, ber, ohne_dicht=False):
    """Phase 2 -> ber ergaenzt um 'teil_a', 'vereint', 'nicht_vereint', 'ergebnis' (sparse, dicht, fused, art = 'vereint' | 'teil_a_allein')."""
    arb = ber["arbeit"]; M_ = ber["meldungen"]; mit = [e for e in ber["teile"] if e.get("modell")]
    ber["nachstufe_code"] = nachstufe_code(); ber["db_ursprung"] = os.path.abspath(db_ursprung)
    if not mit: ber["fehler"] = "kein Teilmodell entstanden"; return ber
    for e in mit if not ohne_dicht else []:                                              # je Teil eine dichte Wolke (gleiche Einstellungen wie die Stufe 'dicht' der Kette)
        dd = os.path.join(arb, f"teil{e['teil']}", "dicht"); fu = os.path.join(dd, "fused.ply"); dj = os.path.join(dd, "fertig.json"); sek = 0; rc = 0; wieder = True
        mit_sp = DICHT_MIT_SPERRLISTE and bool((e.get("sperrliste") or {}).get("angewandt"))
        try: alt_sp = json.load(open(dj)).get("sperrliste_angewandt", bool((e.get("sperrliste") or {}).get("angewandt"))) if os.path.isfile(dj) else None   # alte Wolken ohne Vermerk: wie damals
        except Exception: alt_sp = None
        if not (ply_kopf(fu)[0] > 0 and _neuer(dj, e["modell"]) and alt_sp == mit_sp):
            if alt_sp is not None and alt_sp != mit_sp and os.path.isdir(dd):          # FALLE: dicht_modell nimmt eine vorhandene Bildwahl (sparse_dicht) und Tiefenkarten wieder -> alten Ordner beiseitelegen
                os.rename(dd, _frei(dd + time.strftime("_alt_%Y%m%d_%H%M%S"))); sag(f"SEITENMODELLE: Teil {e['teil']} alte dichte Wolke (Sperrliste {'mit' if alt_sp else 'ohne'}) beiseitegelegt")
            wieder = False; t0 = time.time(); sag(f"SEITENMODELLE: Teil {e['teil']} dichte Wolke ({e['im_modell']} Bilder im Modell" + (", ohne Sperrliste" if not mit_sp else "") + ") ...")
            rc = LAUF([PYC, "-I", os.path.join(T, "dicht_modell.py"), e["modell"], fotos, dd] + (["--ohne", e["sperrliste"]["pfad"]] if mit_sp else []), os.path.join(arb, f"teil{e['teil']}", "dicht.log"))
            sek = round(time.time() - t0)
            if rc == 0 and ply_kopf(fu)[0] > 0: json.dump(dict(sekunden=sek, sperrliste_angewandt=mit_sp), open(dj, "w"))
        else: sek = json.load(open(dj)).get("sekunden", 0)
        n = ply_kopf(fu)[0]; e["dicht"] = dict(ordner=dd, fused=fu if n > 0 else None, punkte=n, rc=rc, sekunden=sek, wiederverwendet=wieder, sperrliste_angewandt=mit_sp)
        sag(f"SEITENMODELLE: Teil {e['teil']} dichte Wolke: rc {rc}, {sek} s" + (" (wiederverwendet)" if wieder else "") + f", {n} Punkte")
        if n <= 0: M_.append(f"Teil {e['teil']}: dichte Wolke gescheitert (rc {rc}, {arb}/teil{e['teil']}/dicht.log) - Vereinen dieses Teils nur aus der duennen Wolke")
    mit.sort(key=lambda e: -e["im_modell"]); A = mit[0]; ber["teil_a"] = A["teil"]; fa = (A.get("dicht") or {}).get("fused"); ang = []; ber["vereint"] = [A["teil"]]; ber["nicht_vereint"] = []; ber["fotoluecken"] = []
    vz = os.path.join(arb, "vereint"); os.makedirs(vz, exist_ok=True); stand_sparse = None
    for B in mit[1:]:
        fb = (B.get("dicht") or {}).get("fused"); vo = os.path.join(arb, f"vereinen_{A['teil']}_{B['teil']}"); vj = os.path.join(vo, "vereinen.json"); vs = os.path.join(vo, "stand.json")
        st = _stand(os.path.join(A["modell"], "images.bin"), os.path.join(B["modell"], "images.bin"), db_ursprung, *(x for x in (fa, fb) if x)) + [code_stand("seiten_vereinen.py", wurzel=T)]; alt = None
        try: alt = json.load(open(vs)) if os.path.isfile(vj) else None
        except Exception: alt = None
        if alt and alt.get("stand") == st: rc = alt["rc"]
        else:
            sag(f"SEITENMODELLE: vereine Teil {B['teil']} mit Teil {A['teil']} (tools/seiten_vereinen.py) ...")
            rc = LAUF([PYC, "-I", os.path.join(T, "seiten_vereinen.py"), A["modell"], B["modell"], db_ursprung, "--aus", vo] + (["--dicht-a", fa, "--dicht-b", fb] if fa and fb else []), os.path.join(vo, "log.txt"))
            if os.path.isdir(vo): json.dump(dict(stand=st, rc=rc), open(vs, "w"))
        try: v = json.load(open(vj))
        except Exception: v = {}
        e = B["vereinen"] = dict(mit=A["teil"], rc=rc, ordner=vo, urteil=v.get("urteil"), pruefung=v.get("pruefung"), spitzen=v.get("spitzen"), lot_b=v.get("lot_b"), paare=v.get("paare"), inlier=v.get("inlier"), mit_dichten_wolken=bool(fa and fb), weg="klappung")
        if not (rc == 0 and "B_nach_A" in v) and ECK_KOPPELN and ber.get("db_mapper"):
            if "eck" not in ber: ber["eck"] = eck_stufe(os.path.join(arb, f"eck_{A['teil']}"), A, mit, ber["db_mapper"], sj, fotos)   # einmal fuer ALLE Teile
            ek = ber["eck"]; et = (ek.get("teile") or {}).get(str(B["teil"])) or {}
            e["eckmodell"] = dict(rc=ek.get("rc"), urteil=ek.get("urteil"), ordner=ek.get("ordner"), teil=et)
            if ek.get("rc") == 0 and et.get("ok"):
                v = dict(B_nach_A=et["M_nach_A"]); rc = 0; e.update(weg="eckmodell", urteil=f"ueber Brueckenmodelle gekoppelt, Weg {et.get('weg')}, Massstab-Unsicherheit {et.get('massstab_unsicher')}")
                M_.append(f"Teil {B['teil']}: Klappung gescheitert - ueber Brueckenmodelle an Teil {A['teil']} gekoppelt (Weg {et.get('weg')})")
            elif ek.get("rc") != 2: M_.append(f"Teil {B['teil']}: Brueckenkopplung NICHT uebernommen: {et.get('grund') or ek.get('urteil')}")
        if not (rc == 0 and "B_nach_A" in v) and GPS_VEREINEN:
            # RUECKFALL GPS (22.11.2026, Nulllauf schwabentor-1122): die Klappung von seiten_vereinen setzt gleich aussehende Gegenseiten voraus (Martinstor). Am Schwabentor
            # lieferte sie Massstab 0,012 -> "keine hoechsten Bauteile" -> Teil A allein -> einseitige Wolke, Ausrichtung 20 Grad gedreht, Abbruch. Haben beide Teile genug
            # Foto-GPS, legt tools/seiten_gps_vereinen.py B ueber das GPS auf A; danach dieselben Tore wie oben (Blick-Tor) + GPS-Seiten-Tor am vereinten Modell.
            vg = vo + "_gps"; vgj = os.path.join(vg, "vereinen.json"); stg = _stand(os.path.join(A["modell"], "images.bin"), os.path.join(B["modell"], "images.bin"), *(x for x in (fa, fb) if x)) + [code_stand("seiten_gps_vereinen.py", wurzel=T)]; altg = None
            try: altg = json.load(open(os.path.join(vg, "stand.json"))) if os.path.isfile(vgj) else None
            except Exception: altg = None
            if altg and altg.get("stand") == stg: rg = altg["rc"]
            else:
                sag(f"SEITENMODELLE: Teil {B['teil']} nicht ueber die Klappung vereint (rc {rc}) - versuche das Foto-GPS (tools/seiten_gps_vereinen.py) ...")
                rg = LAUF([PYC, "-I", os.path.join(T, "seiten_gps_vereinen.py"), A["modell"], B["modell"], "--bilder", fotos, "--aus", vg] + (["--dicht-a", fa, "--dicht-b", fb] if fa and fb else []), os.path.join(vg, "log.txt"))
                if os.path.isdir(vg): json.dump(dict(stand=stg, rc=rg), open(os.path.join(vg, "stand.json"), "w"))
            try: vgd = json.load(open(vgj))
            except Exception: vgd = {}
            e["gps"] = dict(rc=rg, ordner=vg, urteil=vgd.get("urteil"), pruefung=vgd.get("pruefung"))
            if rg == 0 and "B_nach_A" in vgd:
                M_.append(f"Teil {B['teil']}: Klappung gescheitert ({v.get('urteil') or 'rc ' + str(rc)}) - ueber das Foto-GPS gelegt: {vgd.get('urteil')}")
                v = vgd; rc = 0; e.update(weg="gps", urteil=vgd.get("urteil"), pruefung=vgd.get("pruefung"))
                qs = querspur_stufe(vo + "_querspur", A, B, db_ursprung, fa, fb, vgj) if QUERSPUR else dict(ok=False, urteil="abgeschaltet (RCPARK_QUERSPUR=0)")
                e["querspur"] = {k: qs.get(k) for k in ("rc", "ok", "urteil", "pruefung", "doppelwand", "doppelwand_aus", "ordner") if k in qs}
                if qs.get("ok") and "B_nach_A" in qs:
                    v = dict(vgd, B_nach_A=qs["B_nach_A"]); e.update(weg="gps+querspur", urteil=qs.get("urteil")); M_.append(f"Teil {B['teil']}: GPS-Lage ueber Querspuren an Teil A gebunden: {qs.get('urteil')}")
                else: M_.append(f"Teil {B['teil']}: Querspur-Bindung NICHT uebernommen - GPS-Lage bleibt: {qs.get('urteil')}")
                if e["weg"] == "gps" and WAENDE and fa and fb:                          # Querspuren banden nicht -> gemeinsame Waende der dichten Wolken (Gegenseite, 24.11.)
                    wb_ = waende_stufe(vo + "_waende", A, B, fa, fb, vgj, fotos)
                    e["waende"] = {k: wb_.get(k) for k in ("rc", "ok", "urteil", "pruefung", "korridor", "bild", "ordner") if k in wb_}
                    if wb_.get("ok") and "B_nach_A" in wb_:
                        v = dict(vgd, B_nach_A=wb_["B_nach_A"]); e.update(weg="gps+waende", urteil=wb_.get("urteil")); M_.append(f"Teil {B['teil']}: GPS-Lage ueber gemeinsame Waende gebunden: {wb_.get('urteil')}")
                    else: M_.append(f"Teil {B['teil']}: Waende-Bindung NICHT uebernommen - GPS-Lage bleibt: {wb_.get('urteil')}")
                if e["weg"] == "gps":                                                   # Querspuren banden nicht -> jeder Teil einzeln an LoD2 (Kasten = seine GPS-Unsicherheit)
                    lo = lod2_stufe(vo + "_lod2", A, B, fa, fb, vgj, fotos) if LOD2_JE_TEIL else dict(ok=False, urteil="abgeschaltet (RCPARK_LOD2_JE_TEIL=0)")
                    e["lod2_je_teil"] = {k: lo.get(k) for k in ("rc", "ok", "urteil", "ordner", "bild", "korridor") if k in lo}
                    e["lod2_je_teil"]["wand_dicke"] = SLB.wd_kurz(lo.get("wand_dicke"))         # Probe der GPS-Lage fuer die Regel 'nur bei belegter Lage'
                    e["lod2_je_teil"]["teile_eindeutig"] = {k: dict(eindeutig=t.get("eindeutig"), gruende=t.get("gruende") or ([t["grund"]] if t.get("grund") else [])) for k, t in (lo.get("teile") or {}).items() if isinstance(t, dict)}
                    if lo.get("ok") and "B_nach_A" in lo:
                        v = dict(vgd, B_nach_A=lo["B_nach_A"]); e.update(weg="gps+lod2", urteil=lo.get("urteil")); M_.append(f"Teil {B['teil']}: Lage je Teil an LoD2 gelegt: {lo.get('urteil')}")
                    else: M_.append(f"Teil {B['teil']}: LoD2 je Teil NICHT uebernommen - GPS-Lage bleibt: {lo.get('urteil')}")
                belegt, grund_b, _ = SLB.lage_belegt(e); e["lage_belegt"] = dict(belegt=belegt, grund=grund_b, regel_an=NUR_BELEGT)
                if not belegt and NUR_BELEGT:                                           # REGEL: nicht unabhaengig belegt -> weglassen, Fotoluecke melden (nichts erfinden/spiegeln)
                    az, az_her = SLB.richtung(fotos, A["modell"], B["modell"], os.environ.get("RCPARK_SEITEN_OBJEKT", ""))
                    fl = SLB.luecke(B["teil"], B["im_modell"], grund_b, az, az_her); ber.setdefault("fotoluecken", []).append(fl); e["fotoluecke"] = fl
                    M_.append(f"Teil {B['teil']} WEGGELASSEN (Lage nicht unabhaengig belegt: {grund_b}) - {fl['text']}"); sag(f"SEITENMODELLE: {fl['text']}")
                    ber["nicht_vereint"].append(B["teil"]); continue
                if not belegt: M_.append(f"ACHTUNG Teil {B['teil']}: Lage NICHT unabhaengig belegt ({grund_b}) - trotzdem eingesetzt, weil RCPARK_TEIL_NUR_BELEGT=0")
                if e["weg"] == "gps" and (vgd.get("pruefung") or {}).get("mass_sd_rel", 0) > 0.05:
                    M_.append(f"ACHTUNG Teil {B['teil']}: Massstab gegen Teil A nur auf +-{100 * vgd['pruefung']['mass_sd_rel']:.0f} % belegt (Foto-GPS) - Masse dieser Seite nicht ohne Gegenprobe (LoD2-Grundriss, foto_mass) verwenden")
        if rc == 0 and "B_nach_A" in v:
            if GELAENDE_TOR != "aus" and fa and fb:                                    # 24.11.2026: Unter-Gelaende-Tor fuer JEDEN Bindungsweg (vorher nur gps+waende; 1122z Ost-Teil 6,4 m im Boden)
                gt = gelaende_stufe(vo + "_gelaende", A, B, fa, fb, v["B_nach_A"], e.get("weg"), os.path.join(vo + "_gps", "vereinen.json"), fotos)
                e["gelaende_tor"] = {k: gt.get(k) for k in ("rc", "ok", "meldung", "anteil_b", "anteil_a", "zellen", "boden_versatz_m", "ordner") if k in gt}; sag("SEITENMODELLE: " + str(gt.get("meldung")))
                if gt.get("rc") == 3 and GELAENDE_TOR != "hinweis":
                    M_.append(f"Teil {B['teil']} WEGGELASSEN (Weg {e.get('weg')}): {gt.get('meldung')}"); ber["nicht_vereint"].append(B["teil"]); continue
                if gt.get("rc") == 3: M_.append(f"ACHTUNG Teil {B['teil']}: {gt.get('meldung')} - trotzdem eingesetzt (RCPARK_GELAENDE_TOR=hinweis)")
                elif gt.get("rc") != 0: M_.append(f"Teil {B['teil']}: {gt.get('meldung')}")
            kand = os.path.join(vz, f"versuch_{B['teil']}"); tj = os.path.join(vo, "seiten_blick.json")
            try:
                me = modelle_zusammen([(A["modell"], None)] + [(x["modell"], m) for x, m in ang] + [(B["modell"], v["B_nach_A"])], kand, herkunft=dict(teil_a=A["teil"], teile=[x["teil"] for x, _ in ang] + [B["teil"]]), belegt=db_kameras(db_ursprung, ber.get("db_mapper")))
            except Exception as ex:
                e["zusammenlegen"] = f"gescheitert: {ex}"; M_.append(f"Teil {B['teil']}: seiten_vereinen rc 0, aber das Zusammenlegen der Modelle scheiterte ({ex}) - Teil NICHT im Ergebnis"); ber["nicht_vereint"].append(B["teil"]); continue
            rt = LAUF([PYC, "-I", os.path.join(T, "seiten_blick_tor.py"), kand, sj, "--aus", tj], os.path.join(vo, "seiten_blick.log")); e["blick_tor"] = rt
            if rt == 0 and (e["weg"].startswith("gps") or e["weg"] == "eckmodell"):                                        # GPS-Lage: zweites unabhaengiges Tor - alle GPS-Fotos des vereinten Modells muessen zusammen passen
                rgs = LAUF([PYC, "-I", os.path.join(T, "gps_seiten_pruefen.py"), kand, "--bilder", fotos], os.path.join(vo + "_gps", "gps_seiten.log")); e["gps_seiten_tor"] = rgs
                if rgs == 3:
                    M_.append(f"Teil {B['teil']}: ueber das Foto-GPS gelegt, aber das GPS-Seiten-Tor am vereinten Modell fiel DURCH ({vo}_gps/gps_seiten.log) - Teil wieder herausgenommen"); ber["nicht_vereint"].append(B["teil"]); continue
            if rt == 0:
                ang.append((B, v["B_nach_A"])); ber["vereint"].append(B["teil"]); stand_sparse = kand; e["zusammenlegen"] = me
                sag(f"SEITENMODELLE: Teil {B['teil']} VEREINT mit Teil {A['teil']} ({v.get('urteil')}); vereintes Modell {me['bilder']} Bilder, {me['punkte']} Punkte, Blick-Tor bestanden"); continue
            M_.append(f"Teil {B['teil']}: seiten_vereinen rc 0, aber das Seiten-Blick-Tor auf dem vereinten Modell " + ("fiel DURCH (Seiten aufeinander, " if rt == 3 else f"stuerzte ab (rc {rt}, ") + f"{tj}) - Teil wieder herausgenommen")
        else:
            was = {3: "ABGELEHNT (Pruefung nicht bestanden)", 2: "zu wenige Verbindungen zwischen den Seitenmodellen"}.get(rc, f"gescheitert (rc {rc}, {vo}/log.txt)")
            M_.append(f"Teil {B['teil']} ({B['im_modell']} Bilder) NICHT vereint mit Teil {A['teil']}: {was}; Urteil: {v.get('urteil')}; Pruefwerte: {json.dumps(v.get('pruefung'), ensure_ascii=False)[:500]}"
                      + (f"; Foto-GPS: {e['gps']['urteil']}" if e.get("gps") else ""))
        ber["nicht_vereint"].append(B["teil"])
    if ang:                                                                              # das letzte angenommene Zwischenmodell ist das Ergebnis
        ziel = os.path.join(vz, "sparse"); dichte = [(A, None)] + ang; dicht_ok = True
        gebunden = [x["teil"] for x, _ in ang if (x.get("vereinen") or {}).get("weg") in ("gps+querspur", "gps+lod2", "gps+waende")]
        if not GPS_AUSGLEICH: ga = dict(ok=False, urteil="abgeschaltet (RCPARK_GPS_AUSGLEICH=0)")
        elif gebunden: ga = dict(ok=False, urteil=f"ausgelassen: Teile {gebunden} ueber Querspuren bzw. LoD2 je Teil gelegt - ohne gemeinsame 3D-Punkte zoege der GPS-Ausgleich sie wieder einzeln aufs GPS")
        else: ga = gps_ausgleich_stufe(vz, stand_sparse, fotos, sj, A, ang, M_)
        ber["gps_ausgleich"] = {k: v for k, v in ga.items() if k != "teile"}
        if ga.get("ok") and ga.get("sparse") and os.path.isfile(os.path.join(ga["sparse"], "images.bin")):
            D = {k: np.array(v["delta"]) for k, v in (ga.get("teile") or {}).items()}
            if all(str(x["teil"]) in D for x, _ in dichte):                              # dichte Wolken der Teile nachlegen: neu = delta_Teil * (B_nach_A bzw. Einheit fuer A)
                # Anker (meiste Bilder = Teil A) bleibt per Bau an seinem Ort (delta = Einheit bis auf die Verformung): None behalten, sonst kopiert dicht_zusammen alle Tiefenkarten von A
                neu = [(x, None if (m is None and ga.get("anker_teil") == str(x["teil"])) else (D[str(x["teil"])] @ (np.eye(4) if m is None else np.asarray(m, float))).tolist()) for x, m in dichte]
                # 24.11.2026 NACHPRUEFUNG: der Ausgleich verschiebt die Teile noch einmal (Wege Klappung, Eck, reines GPS) - dasselbe Unter-Gelaende-Tor auf der Lage NACH dem Ausgleich
                unter = ausgleich_gelaende_stufe(vz, neu, fotos, M_) if GELAENDE_TOR != "aus" else []
                ber["gps_ausgleich"]["gelaende_unter"] = unter
                if unter and GELAENDE_TOR != "hinweis":
                    M_.append(f"GPS-Ausgleich VERWORFEN: Teile {unter} laegen danach unter Gelaende (Tor wie vor dem Zusammenlegen) - Lage vor dem Ausgleich bleibt"); ber["gps_ausgleich"]["verworfen"] = True
                    sag(f"SEITENMODELLE: GPS-Ausgleich VERWORFEN (Teile {unter} danach unter Gelaende)")
                else:
                    if unter: M_.append(f"ACHTUNG GPS-Ausgleich: Teile {unter} danach unter Gelaende - trotzdem uebernommen (RCPARK_GELAENDE_TOR=hinweis)")
                    dichte = neu
                    schlecht = [k for k, v in ga["teile"].items() if not v.get("dicht_gueltig")]
                    if schlecht: dicht_ok = False; M_.append(f"GPS-Ausgleich: Teile {schlecht} innerlich verformt (> {100 * VERFORM_MAX_PROZ:.1f} % ihrer Ausdehnung) - ihre dichten Wolken passen nicht mehr, die Kette rechnet die dichte Wolke neu")
                    stand_sparse = os.path.join(vz, "gps_ausgleich_sparse"); shutil.rmtree(stand_sparse, ignore_errors=True); shutil.copytree(ga["sparse"], stand_sparse)
                    sag(f"SEITENMODELLE: GPS-Ausgleich uebernommen ({ga.get('urteil')})")
            else: M_.append(f"GPS-Ausgleich: Teil-Abbildungen fehlen ({sorted(D)}) - NICHT uebernommen")
        else: M_.append(f"GPS-Ausgleich nicht uebernommen: {ga.get('urteil')}")
        if os.path.isdir(ziel): shutil.rmtree(ziel)
        os.rename(stand_sparse, ziel); ber["ergebnis"] = dict(art="vereint", sparse=ziel, dicht=None, fused=None)
        if not dicht_ok: pass
        elif all((x.get("dicht") or {}).get("fused") for x, _ in dichte):
            try:
                dz = dicht_zusammen([(x["dicht"]["ordner"], m) for x, m in dichte], os.path.join(vz, "dicht"), belegt=db_kameras(db_ursprung, ber.get("db_mapper"))); ber["ergebnis"].update(dicht=os.path.join(vz, "dicht"), fused=os.path.join(vz, "dicht", "fused.ply"), punkte=dz["punkte"])
            except Exception as ex: M_.append(f"vereinte dichte Wolke NICHT geschrieben ({ex}) - die Kette rechnet die dichte Wolke auf dem vereinten Modell selbst")
        else: M_.append("vereinte dichte Wolke NICHT geschrieben (einem vereinten Teil fehlt die dichte Wolke) - die Kette rechnet sie auf dem vereinten Modell selbst")
    else:
        ber["ergebnis"] = dict(art="teil_a_allein", sparse=A["modell"], dicht=(A.get("dicht") or {}).get("ordner") if fa else None, fused=fa, punkte=(A.get("dicht") or {}).get("punkte"))
        M_.append(f"KEIN Teil vereint - die Kette verwendet Teil {A['teil']} ({A['im_modell']} Bilder) ALLEIN; es fehlen die Teile {ber['nicht_vereint']}"
                  + (f" (davon Fotoluecke, Lage nicht belegt: {[f_['teil'] for f_ in ber.get('fotoluecken', [])]})" if ber.get("fotoluecken") else ""))
    return ber


def gps_ausgleich_stufe(vz, sparse, fotos, sj, A, ang, M_):
    """GEMEINSAMER AUSGLEICH MIT GPS-PRIOREN nach dem Vereinen (22.11.2026, Nulllauf schwabentor-1122: Teile per GPS-Sim3 einzeln gelegt, kein gemeinsamer Ausgleich).
    tools/sfm_gps_ausgleich.py auf dem vereinten Modell; Waechter dort (>= 40 unabhaengige Geotags, Bildfehler nicht schlechter, GPS-Rest sinkt). Zwischenstand an Eingaben +
    Code gebunden (Modelle der Teile, B_nach_A, Code-Stand). -> gps_ausgleich.json (dict; ok False = Modell unveraendert)."""
    ao = os.path.join(vz, "gps_ausgleich"); aj = os.path.join(ao, "gps_ausgleich.json"); sf = os.path.join(ao, "stand.json")
    st = _stand(os.path.join(A["modell"], "images.bin"), *(os.path.join(x["modell"], "images.bin") for x, _ in ang)) + [np.round(np.asarray([m for _, m in ang], float), 9).tolist(), os.path.abspath(fotos), code_stand("sfm_gps_ausgleich.py", wurzel=T)]
    try: alt = json.load(open(sf)) if os.path.isfile(aj) else None
    except Exception: alt = None
    if not (alt and alt.get("stand") == st):
        os.makedirs(ao, exist_ok=True); tj = os.path.join(ao, "teile.json"); json.dump({n: t["teil"] for t in teile_lesen(sj) for n in t["bilder"]}, open(tj, "w"))
        sag("SEITENMODELLE: gemeinsamer Ausgleich mit GPS-Prioren (tools/sfm_gps_ausgleich.py) ...")
        rc = LAUF([PYC, "-I", os.path.join(T, "sfm_gps_ausgleich.py"), sparse, "--bilder", fotos, "--aus", ao, "--teile", tj], os.path.join(ao, "log.txt"))
        json.dump(dict(stand=st, rc=rc), open(sf, "w"))
    try: return json.load(open(aj))
    except Exception as ex: return dict(ok=False, urteil=f"kein Ergebnis ({type(ex).__name__}, {ao}/log.txt)")


def eck_stufe(eo, A, mit, db_mapper, sj, fotos):
    """TEILE UEBER BRUECKENMODELLE KOPPELN (tools/seiten_eck_koppeln.py), EINMAL fuer alle Teile (A zuerst). Zwischenstand an Modelle, Mapper-DB, seiten.json und Code gebunden.
    -> eck.json als dict mit 'rc', 'ordner', 'teile' {N: ok, M_nach_A, weg}."""
    ej = os.path.join(eo, "eck.json"); sf = os.path.join(eo, "stand.json"); tl = [A] + [x for x in mit if x is not A]
    st = _stand(*(os.path.join(x["modell"], "images.bin") for x in tl), db_mapper, sj) + [code_stand("seiten_eck_koppeln.py", wurzel=T)]
    try: alt = json.load(open(sf)) if os.path.isfile(ej) else None
    except Exception: alt = None
    if alt and alt.get("stand") == st: rc = alt["rc"]
    else:
        os.makedirs(eo, exist_ok=True); sag(f"SEITENMODELLE: Teile {[x['teil'] for x in tl[1:]]} ueber Brueckenmodelle an Teil {A['teil']} koppeln (tools/seiten_eck_koppeln.py) ...")
        rc = LAUF([PYC, "-I", os.path.join(T, "seiten_eck_koppeln.py"), db_mapper, sj, fotos, "--aus", eo] + [f"--teil={x['teil']}={x['modell']}" for x in tl], os.path.join(eo, "log.txt"))
        json.dump(dict(stand=st, rc=rc), open(sf, "w"))
    try: d = json.load(open(ej))
    except Exception as ex: d = dict(ok=False, urteil=f"kein Ergebnis ({type(ex).__name__}, rc {rc}, {eo}/log.txt)")
    d.update(rc=rc, ordner=eo)
    if rc != 0: d["ok"] = False
    return d


def querspur_stufe(qo, A, B, db_ursprung, fa, fb, vgj):
    """TEILE UEBER QUERSPUREN BINDEN (tools/seiten_querspur_binden.py) nach dem GPS-Vereinen von B. Zwischenstand an Eingaben (Modelle, Ursprungs-DB, dichte Wolken, GPS-Ergebnis)
    + Code-Stand gebunden. -> querspur.json als dict mit 'rc' und 'ordner' (ok False = GPS-Lage bleibt)."""
    qj = os.path.join(qo, "querspur.json"); sf = os.path.join(qo, "stand.json")
    st = _stand(os.path.join(A["modell"], "images.bin"), os.path.join(B["modell"], "images.bin"), db_ursprung, vgj, *(x for x in (fa, fb) if x)) + [code_stand("seiten_querspur_binden.py", wurzel=T)]
    try: alt = json.load(open(sf)) if os.path.isfile(qj) else None
    except Exception: alt = None
    if alt and alt.get("stand") == st: rc = alt["rc"]
    else:
        os.makedirs(qo, exist_ok=True); sag(f"SEITENMODELLE: Teil {B['teil']} ueber Querspuren an Teil {A['teil']} binden (tools/seiten_querspur_binden.py) ...")
        rc = LAUF([PYC, "-I", os.path.join(T, "seiten_querspur_binden.py"), A["modell"], B["modell"], db_ursprung, "--gps", vgj, "--aus", qo] + (["--dicht-a", fa, "--dicht-b", fb] if fa and fb else []), os.path.join(qo, "log.txt"))
        json.dump(dict(stand=st, rc=rc), open(sf, "w"))
    try: d = json.load(open(qj))
    except Exception as ex: d = dict(ok=False, urteil=f"kein Ergebnis ({type(ex).__name__}, rc {rc}, {qo}/log.txt)")
    d.update(rc=rc, ordner=qo)
    if rc != 0: d["ok"] = False
    return d


def waende_stufe(wo, A, B, fa, fb, vgj, fotos):
    """GEGENSEITE UEBER GEMEINSAME WAENDE BINDEN (tools/seiten_waende_binden.py) nach dem GPS-Vereinen von B, wenn die Querspur nicht band. Zwischenstand an Eingaben
    (Modelle, dichte Wolken, GPS-Ergebnis, Fotos) + Code-Stand gebunden. -> waende.json als dict mit 'rc' und 'ordner' (ok False = GPS-Lage bleibt)."""
    wj = os.path.join(wo, "waende.json"); sf = os.path.join(wo, "stand.json")
    st = _stand(os.path.join(A["modell"], "images.bin"), os.path.join(B["modell"], "images.bin"), fa, fb, vgj) + [os.path.abspath(fotos), code_stand("seiten_waende_binden.py", wurzel=T)]
    try: alt = json.load(open(sf)) if os.path.isfile(wj) else None
    except Exception: alt = None
    if alt and alt.get("stand") == st: rc = alt["rc"]
    else:
        os.makedirs(wo, exist_ok=True); sag(f"SEITENMODELLE: Teil {B['teil']} ueber gemeinsame Waende an Teil {A['teil']} binden (tools/seiten_waende_binden.py) ...")
        rc = LAUF([PYC, "-I", os.path.join(T, "seiten_waende_binden.py"), fa, fb, "--gps", vgj, "--aus", wo, "--modell-a", A["modell"], "--modell-b", B["modell"], "--bilder", fotos], os.path.join(wo, "log.txt"))
        json.dump(dict(stand=st, rc=rc), open(sf, "w"))
    try: d = json.load(open(wj))
    except Exception as ex: d = dict(ok=False, urteil=f"kein Ergebnis ({type(ex).__name__}, rc {rc}, {wo}/log.txt)")
    d.update(rc=rc, ordner=wo)
    if rc != 0: d["ok"] = False
    return d


def gelaende_stufe(go, A, B, fa, fb, M, weg, gj, fotos=None):
    """TOR 'TEIL UNTER GELAENDE' (tools/teil_gelaende_tor.py) fuer das gebundene Teil B, gleich welcher Weg B_nach_A lieferte. Zwischenstand an Eingaben (Modell A, dichte
    Wolken, Matrix, GPS-Ergebnis fuer den Massstab) + Code-Stand gebunden. -> gelaende.json als dict mit 'rc' und 'ordner' (rc 3 = abgelehnt, 2 = nicht pruefbar)."""
    os.makedirs(go, exist_ok=True); mj = os.path.join(go, "matrix.json"); gjo = os.path.join(go, "gelaende.json"); sf = os.path.join(go, "stand.json")
    Ms = json.dumps(np.asarray(M, float).round(9).tolist())
    st = _stand(os.path.join(A["modell"], "images.bin"), fa, fb, *([gj] if os.path.isfile(gj) else [])) + [Ms, str(weg), os.path.abspath(fotos) if fotos else None, code_stand("teil_gelaende_tor.py", wurzel=T)]
    try: alt = json.load(open(sf)) if os.path.isfile(gjo) else None
    except Exception: alt = None
    if alt and alt.get("stand") == st: rc = alt["rc"]
    else:
        json.dump(dict(B_nach_A=json.loads(Ms), weg=weg), open(mj, "w"))
        rc = LAUF([PYC, "-I", os.path.join(T, "teil_gelaende_tor.py"), fa, fb, "--matrix", mj, "--aus", gjo, "--modell-a", A["modell"], "--teil", str(B["teil"]), "--weg", str(weg)]
                  + (["--gps", gj] if os.path.isfile(gj) else []) + (["--bilder", fotos] if fotos and os.path.isdir(fotos) else []), os.path.join(go, "log.txt"))
        json.dump(dict(stand=st, rc=rc), open(sf, "w"))
    try: d = json.load(open(gjo))
    except Exception as ex: d = dict(ok=None, meldung=f"GELAENDE-TOR Teil {B['teil']}: kein Ergebnis ({type(ex).__name__}, rc {rc}, {go}/log.txt)")
    d.update(rc=rc, ordner=go)
    return d


def ausgleich_gelaende_stufe(vz, neu, fotos, M_):
    """NACHPRUEFUNG NACH DEM GPS-AUSGLEICH (24.11.2026): neu = [(A, M_A), (Teil, M_Teil), ...] = Abbildungen der dichten Wolken NACH dem Ausgleich (None = Einheit). Je Teil
    die Lage relativ zu A (M_A^-1 * M_Teil, also wieder im System von A) durch dasselbe Tor wie vor dem Zusammenlegen (gelaende_stufe). -> Liste der Teile mit rc 3 (unter Gelaende);
    der Aufrufer verwirft dann den Ausgleich (das ausgeglichene Modell laesst sich nicht je Teil zuruecknehmen)."""
    A = neu[0][0]; fa = (A.get("dicht") or {}).get("fused"); unter = []
    if not fa: return unter
    iMA = np.linalg.inv(np.eye(4) if neu[0][1] is None else np.asarray(neu[0][1], float))
    for x, m in neu[1:]:
        fb = (x.get("dicht") or {}).get("fused")
        if not fb: continue
        e = x.setdefault("vereinen", {}); vo = e.get("ordner") or ""; weg = f"{e.get('weg') or '?'}+gps_ausgleich"
        gt = gelaende_stufe(os.path.join(vz, f"gelaende_nach_ausgleich_{x['teil']}"), A, x, fa, fb, iMA @ (np.eye(4) if m is None else np.asarray(m, float)), weg,
                            os.path.join(vo + "_gps", "vereinen.json") if vo else "", fotos)
        e["gelaende_tor_nach_ausgleich"] = {k: gt.get(k) for k in ("rc", "ok", "meldung", "anteil_b", "anteil_a", "zellen", "boden_versatz_m", "ordner") if k in gt}
        sag("SEITENMODELLE: nach GPS-Ausgleich " + str(gt.get("meldung")))
        if gt.get("rc") == 3: unter.append(x["teil"])
        elif gt.get("rc") != 0: M_.append(f"Teil {x['teil']} nach GPS-Ausgleich: {gt.get('meldung')}")
    return unter


def lod2_stufe(lo_, A, B, fa, fb, vgj, fotos):
    """LoD2 JE TEIL (tools/seiten_lod2_je_teil.py) nach dem GPS-Vereinen von B. objekt.json aus RCPARK_SEITEN_OBJEKT. Zwischenstand an Eingaben (Modelle, dichte Wolken,
    GPS-Ergebnis, objekt.json, LoD2-GML) + Code-Stand gebunden. -> lod2_teile.json als dict mit 'rc' und 'ordner' (ok False = GPS-Lage bleibt)."""
    oj = os.environ.get("RCPARK_SEITEN_OBJEKT", "")
    if not oj or not os.path.isfile(oj): return dict(ok=False, urteil=f"nicht gerechnet: kein objekt.json (RCPARK_SEITEN_OBJEKT='{oj}', setzt tools/pipeline_objekt.py)")
    if not (fa and fb): return dict(ok=False, urteil="nicht gerechnet: dichte Wolke eines Teils fehlt")
    try: gml = (json.load(open(oj)).get("lod2") or {}).get("gml") or ""
    except Exception: gml = ""
    aj = os.path.join(lo_, "lod2_teile.json"); sf = os.path.join(lo_, "stand.json")
    st = _stand(os.path.join(A["modell"], "images.bin"), os.path.join(B["modell"], "images.bin"), fa, fb, vgj, oj, *([gml] if os.path.isfile(gml) else [])) + [os.path.abspath(fotos), code_stand("seiten_lod2_je_teil.py", wurzel=T)]
    try: alt = json.load(open(sf)) if os.path.isfile(aj) else None
    except Exception: alt = None
    if alt and alt.get("stand") == st: rc = alt["rc"]
    else:
        os.makedirs(lo_, exist_ok=True); sag(f"SEITENMODELLE: Teil {A['teil']} und Teil {B['teil']} einzeln an LoD2 legen (tools/seiten_lod2_je_teil.py) ...")
        rc = LAUF([PYC, "-I", os.path.join(T, "seiten_lod2_je_teil.py"), oj, A["modell"], B["modell"], "--bilder", fotos, "--gps", vgj, "--aus", lo_, "--dicht-a", fa, "--dicht-b", fb], os.path.join(lo_, "log.txt"))
        json.dump(dict(stand=st, rc=rc), open(sf, "w"))
    try: d = json.load(open(aj))
    except Exception as ex: d = dict(ok=False, urteil=f"kein Ergebnis ({type(ex).__name__}, rc {rc}, {lo_}/log.txt)")
    d.update(rc=rc, ordner=lo_)
    if rc != 0: d["ok"] = False
    return d


def _frei(p):
    """Freier Name fuer das Beiseitelegen (zwei Laeufe in derselben Sekunde: 'Directory not empty')."""
    k = 1; q = p
    while os.path.exists(q): q = f"{p}_{k}"; k += 1
    return q


def einsetzen(w, ber):
    """'ergebnis.sparse' nach <w>/sparse/0 kopieren (Zeitstempel bleiben: die dichte Wolke ist danach nicht 'aelter als das Netz'). Ein vorhandenes sparse/ mit Inhalt wird
    beiseitegelegt (sparse.alt_<zeit>), nichts geloescht."""
    q = (ber.get("ergebnis") or {}).get("sparse"); sp = os.path.join(w, "sparse")
    if not q or not os.path.isfile(os.path.join(q, "images.bin")): return False
    if os.path.isdir(sp) and os.listdir(sp): os.rename(sp, _frei(sp + ".alt_" + time.strftime("%Y%m%d_%H%M%S")))
    os.makedirs(sp, exist_ok=True); shutil.copytree(q, os.path.join(sp, "0")); ber["ergebnis"]["eingesetzt"] = os.path.join(sp, "0"); return True


def schreiben(w, ber):
    ber["zeit_ende"] = time.strftime("%Y-%m-%d %H:%M"); json.dump(ber, open(os.path.join(w, "seiten_modelle.json"), "w"), indent=1, ensure_ascii=False)
    for m in ber.get("meldungen", []): sag("ACHTUNG SEITENMODELLE: " + m)
    for f_ in ber.get("fotoluecken", []): sag("FOTOLUECKE SEITENMODELLE: " + f_["text"])
    e = ber.get("ergebnis")
    if e: sag(f"SEITENMODELLE ERGEBNIS: {e['art']} - Teile {ber.get('vereint')} im Modell {e['sparse']}" + (f", nicht vereint {ber['nicht_vereint']}" if ber.get("nicht_vereint") else "") + (f"; dichte Wolke {e['fused']}" if e.get("fused") else "; KEINE fertige dichte Wolke"))
    return ber


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("arbeit"); ap.add_argument("fotos"); ap.add_argument("--seiten"); ap.add_argument("--db-mapper"); ap.add_argument("--db-ursprung")
    ap.add_argument("--min-bilder", type=int, default=MIN_BILDER); ap.add_argument("--nur-modelle", action="store_true", help="nur Phase 1 (Mapper je Teil)"); ap.add_argument("--ohne-dicht", action="store_true", help="keine dichten Wolken (Vereinen aus den duennen Wolken - nicht der bewiesene Weg)")
    ap.add_argument("--einsetzen", action="store_true", help="Ergebnis nach <arbeit>/sparse/0 kopieren"); a = ap.parse_args(argv); w = a.arbeit
    sj = a.seiten or os.path.join(w, "seiten.json"); dbm = a.db_mapper or next((p for p in (os.path.join(w, "db_mapper.db"), os.path.join(w, "db_seiten.db")) if os.path.isfile(p)), None); dbu = a.db_ursprung or os.path.join(w, "db.db")
    for p, was in ((sj, "seiten.json"), (dbm, "Mapper-Datenbank (--db-mapper)"), (dbu, "Ursprungs-Datenbank (--db-ursprung)")):
        if not p or not os.path.isfile(p): sag(f"FEHLER: {was} fehlt: {p}"); return 4
    ber = modelle(w, a.fotos, sj, dbm, a.min_bilder)
    ber["db_mapper"] = os.path.abspath(dbm)
    if ber.get("grund"): sag("SEITENMODELLE: " + ber["grund"]); schreiben(w, ber); return 2
    if not ber.get("fehler") and not a.nur_modelle:
        dicht_vereinen(w, a.fotos, sj, dbu, ber, ohne_dicht=a.ohne_dicht)
        if a.einsetzen: einsetzen(w, ber)
    schreiben(w, ber)
    if ber.get("fehler"): sag("FEHLER SEITENMODELLE: " + ber["fehler"]); return 3
    return 0


if __name__ == "__main__": sys.exit(main())
