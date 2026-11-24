#!/usr/bin/env python3
"""seiten_lage_beleg.py - REGEL "TEIL NUR BEI BELEGTER LAGE EINSETZEN" fuer tools/sfm_seiten_modelle.py (22.11.2026, schwabentor-1122).

WARUM: Teil 0 des Schwabentors (394 Bilder inkl. 10 Fernfotos) liegt richtig (0,88 m neben der 1120-Lage, GPS-Tor und Lageproben belegt). Teil 1 (Westseite, 127 Bilder,
2,37 px Reprojektionsfehler, 23-25 GPS-Fotos, sieht nur EINE Wand) wurde trotzdem eingesetzt - allein ueber das Foto-GPS (tools/seiten_gps_vereinen.py, +-3,5 Grad / +-12 %
Bootstrap; ehrlich mit Sitzungsfehler deutlich mehr). Er liegt 3-4 m westlich versetzt -> Grundriss-Tor A 17,6 % rot und Wanddicke 'doppelwand' NUR wegen Teil 1.
Querspuren = Gegenseiten-Verwechslung (belegt), LoD2 je Teil fuer Teil 1 mehrdeutig entlang der Wand. Ein Teil, dessen Lage keine eigene Probe belegt, ist eine ERFUNDENE Lage:
er wird WEGGELASSEN (KERNMETHODE: Ungesehenes nie erfinden -> Fotos suchen), die Kette laeuft mit dem Hauptteil weiter und meldet die Seite als FOTOLUECKE.

REGEL (lage_belegt, je Teil B, Quellen nicht gemittelt - jede Probe muss fuer sich bestehen):
  weg 'klappung'      -> eingesetzt wie bisher (Martinstor: seiten_vereinen + Blick-Tor; die Regel gilt nur fuer den GPS-Weg).
  weg 'gps+querspur'  -> belegt: eigene Bildpunkt-Probe (RANSAC-Sim3 der Querspuren) im GPS-Korridor, Guete-Regeln in seiten_querspur_binden.
  weg 'gps+lod2'      -> belegt: LoD2 je Teil (seiten_lod2_je_teil) - beide Teile eindeutig, Wanddicke-Mass besser, GPS-Korridor gehalten, Teile widerspruchsfrei.
  weg 'gps' (nur GPS) -> belegt NUR, wenn BEIDES gilt:
     (1) GPS ehrlich belegt: pruefung.lage_b_belegt (Zufall + systematischer Sitzungsfehler, tools/gps_unsicherheit.py; Grenzen MAX_DREH_SD/MAX_MASS_SD in seiten_gps_vereinen);
     (2) Wanddicke-Probe der GPS-Lage (seiten_lod2_je_teil 'wand_dicke.vorher' = A an LoD2, B per GPS an A): mindestens eine LoD2-Kante mit Wandbeleg BEIDER Teile und
         keine Kante 'versetzt'/'doppelwand' (Grenzen tools/wand_dicke_tor.py DICKE_MAX_M 1,2 m / VERSATZ_MAX_M 0,5 m, am Kontrollobjekt schwabentor-1120 begruendet).
     Der GPS-Korridor (dritte Bedingung des Auftrags) ist fuer die GPS-Lage selbst trivial erfuellt. Ohne LoD2-je-Teil-Ergebnis (kein objekt.json, RCPARK_LOD2_JE_TEIL=0,
     Rahmen eines Teils taugt nicht) ist (2) nicht pruefbar -> NICHT belegt.
FOTOLUECKE (luecke): Teil, Bildzahl, Himmelsrichtung der Seite (richtung: Azimut der GPS-Fotos des Teils um die Mitte des Zielgebaeudes - LoD2-Grundflaeche aus objekt.json,
  sonst Rahmenmitte (ANNAHME), sonst Richtung von Teil A nach Teil B im GPS (ANNAHME, nur grob)), Grund, Text fuer Bericht/Kette/Fotoauftrag, benoetigte Fotos.
Abschalten: RCPARK_TEIL_NUR_BELEGT=0 (alter Stand: GPS-Lage wird eingesetzt); der Schalter steht im Code-Stand der Nachstufe (sfm_seiten_modelle.nachstufe_code).
Test: tools/test_seiten_lage_beleg.py (+ Kettenfaelle in tools/test_seiten_modelle.py, Abschnitt 4i)."""
import os, sys, math
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
NUR_BELEGT = os.environ.get("RCPARK_TEIL_NUR_BELEGT", "1") != "0"
try:
    from wand_dicke_tor import DICKE_MAX_M, VERSATZ_MAX_M
except Exception:                                                                    # wand_dicke_tor importiert nur numpy; Rueckfall nur fuer kaputte Umgebungen
    DICKE_MAX_M, VERSATZ_MAX_M = 1.2, 0.5
FOTOS_NOETIG = ["Brueckenfotos schraeg ueber Eck: von der Ecke zwischen dieser Seite und der Seite des Hauptteils, beide Waende im selben Bild, 8-12 Fotos im Bogen, je 2-3 m Seitenschritt",
                "Fernfotos mit GPS aus 80-300 m, auf denen diese Seite UND eine Seite des Hauptteils zu sehen sind (legen Drehung und Massstab fest)"]
SCHLECHT = ("versetzt", "doppelwand")


def wd_kurz(wd):
    """lod2_teile.json 'wand_dicke' {vorher, nachher} -> kurze Fassung fuer seiten_modelle.json (je Kante nur Urteil und Lageunterschied)."""
    if not isinstance(wd, dict): return None
    aus = {}
    for k in ("vorher", "nachher"):
        w = wd.get(k)
        if not isinstance(w, dict): continue
        aus[k] = dict(rc=w.get("rc"), urteil=w.get("urteil"), kanten_mit_beiden=w.get("kanten_mit_beiden"), max_lageunterschied_m=w.get("max_lageunterschied_m"),
                      kanten=[dict(von=x.get("von"), bis=x.get("bis"), urteil=x.get("urteil"), lageunterschied_m=x.get("lageunterschied_m"), dicke_gesamt_m=x.get("dicke_gesamt_m")) for x in (w.get("kanten") or [])])
    return aus


def wanddicke_probe(wd_vorher):
    """Wanddicke-Probe der GPS-Lage -> (bestanden, text)."""
    if not isinstance(wd_vorher, dict): return False, "Wanddicke der GPS-Lage nicht gemessen (kein Ergebnis von LoD2 je Teil)"
    K = wd_vorher.get("kanten") or []; beide = [k for k in K if k.get("lageunterschied_m") is not None]
    if not beide: return False, "keine LoD2-Kante mit Wandbeleg beider Teile - Lageunterschied nicht messbar"
    schlecht = [k for k in K if k.get("urteil") in SCHLECHT]
    if schlecht: return False, "; ".join(f"Kante {k.get('von')}->{k.get('bis')} {k['urteil']} (Teile {k.get('lageunterschied_m')} m auseinander, Grenze {VERSATZ_MAX_M} m; Dicke {k.get('dicke_gesamt_m')} m, Grenze {DICKE_MAX_M} m)" for k in schlecht)
    return True, f"{len(beide)} Kante(n) mit beiden Teilen, Lageunterschied max {max(k['lageunterschied_m'] for k in beide)} m <= {VERSATZ_MAX_M} m"


def lage_belegt(e):
    """e = B['vereinen'] aus sfm_seiten_modelle (weg, pruefung, lod2_je_teil, querspur). -> (belegt, grund, proben{name: (bestanden, text)})."""
    weg = e.get("weg") or "?"; pr = {}
    if weg == "klappung": return True, "Klappung (seiten_vereinen) + Blick-Tor - Regel gilt nur fuer den GPS-Weg", pr
    if weg == "gps+querspur": return True, "Querspur-Bindung bestanden (eigene Bildpunkt-Probe im GPS-Korridor): " + str((e.get("querspur") or {}).get("urteil")), pr
    if weg == "eckmodell": return True, "Eck-Kopplung (seiten_eck_koppeln: gemeinsame 3D-Punkte beider Seiten stimmig, Massstab belegt): " + str((e.get("eckmodell") or {}).get("urteil")), pr
    if weg == "gps+waende": return True, "Waende-Bindung bestanden (gemeinsame Waende eindeutig, zwei Hoehenbaender einig, Geotags von B, GPS-Korridor; seiten_waende_binden): " + str((e.get("waende") or {}).get("urteil")), pr
    if weg == "gps+lod2": return True, "LoD2 je Teil uebernommen (beide Teile eindeutig, Wanddicke besser, GPS-Korridor, widerspruchsfrei): " + str((e.get("lod2_je_teil") or {}).get("urteil")), pr
    if weg != "gps": return False, f"unbekannter Weg '{weg}'", pr
    p = e.get("pruefung") or {}
    g_ok = p.get("lage_b_belegt") is True
    pr["gps_ehrlich"] = (g_ok, f"Drehung +-{p.get('dreh_sd_ehrlich_grad')} Grad, Massstab +-{100 * float(p.get('mass_sd_ehrlich_rel') or float('nan')):.0f} % (Zufall + Sitzungsfehler)" if "dreh_sd_ehrlich_grad" in p
                         else "keine ehrliche GPS-Unsicherheit im Ergebnis (lage_b_belegt fehlt)")
    lo = e.get("lod2_je_teil") or {}
    pr["wanddicke_gps_lage"] = wanddicke_probe(((lo.get("wand_dicke") or {}).get("vorher")))
    tb = (lo.get("teile_eindeutig") or {}).get("b")
    if tb is not None: pr["lod2_teil_b"] = (bool(tb.get("eindeutig")), "; ".join(tb.get("gruende") or []) or "eindeutig")   # nur Bericht: mehrdeutig entlang der Wand = keine eigene Lage aus LoD2
    belegt = pr["gps_ehrlich"][0] and pr["wanddicke_gps_lage"][0]
    grund = "; ".join(f"{n}: {'bestanden' if ok else 'NICHT bestanden'} ({t})" for n, (ok, t) in pr.items())
    return belegt, ("nur GPS, unabhaengig belegt - " if belegt else "nur GPS, Lage NICHT unabhaengig belegt - ") + grund, pr


def seite_name(az):
    """Kompass-Azimut (Grad, 0 = Nord, im Uhrzeigersinn) -> 'Westseite' usw. (8 Richtungen)."""
    if az is None or not np.isfinite(az): return None
    return ["Nordseite", "Nordostseite", "Ostseite", "Suedostseite", "Suedseite", "Suedwestseite", "Westseite", "Nordwestseite"][int(((az % 360) + 22.5) // 45) % 8]


def richtung_aus_punkten(ost_nord_b, mitte=None, ost_nord_a=None):
    """Azimut der Seite: Median der GPS-Lagen (Ost, Nord in Metern) von Teil B um die Gebaeudemitte; ohne Mitte die Richtung Teil A -> Teil B (ANNAHME, grob).
    -> (azimut_grad, herkunft) oder (None, grund)."""
    B = np.asarray(ost_nord_b, float).reshape(-1, 2)
    if len(B) < 3: return None, f"nur {len(B)} GPS-Fotos im Teil"
    mb = np.median(B, 0)
    if mitte is not None: v = mb - np.asarray(mitte, float); her = "GPS-Fotos des Teils um die Gebaeudemitte"
    elif ost_nord_a is not None and len(np.asarray(ost_nord_a).reshape(-1, 2)) >= 3: v = mb - np.median(np.asarray(ost_nord_a, float).reshape(-1, 2), 0); her = "Richtung Hauptteil -> Teil im GPS (ANNAHME, ohne Gebaeudemitte grob)"
    else: return None, "keine Bezugsmitte"
    if np.linalg.norm(v) < 1.0: return None, "GPS-Mitte des Teils liegt auf der Bezugsmitte"
    return float(math.degrees(math.atan2(v[0], v[1])) % 360.0), her


def richtung(fotos, modell_a, modell_b, objekt_json=None):
    """Azimut der Seite von Teil B aus dem EXIF-GPS seiner Fotos (Gebaeudemitte aus der LoD2-Grundflaeche des Zielgebaeudes bzw. Rahmenmitte in objekt.json). Nie Absturz."""
    try:
        import pycolmap, json
        import seiten_gps_vereinen as SG
        na = [im.name for im in pycolmap.Reconstruction(modell_a).images.values()]; nb = [im.name for im in pycolmap.Reconstruction(modell_b).images.values()]
        roh = SG.gps_roh(fotos, na + nb) if os.path.isdir(fotos) else {}
        if not roh: return None, "keine GPS-Fotos"
        from bilder_holen import wgs84_zu_utm
        U = {n: np.asarray(wgs84_zu_utm(la, lo), float) for n, (la, lo) in roh.items()}; mitte = None; her_m = ""
        if objekt_json and os.path.isfile(objekt_json):
            obj = json.load(open(objekt_json))
            try: obj = __import__("objekt_rahmen").ergaenzen(obj, os.path.dirname(os.path.abspath(objekt_json)))   # wie seiten_lod2_je_teil.main
            except Exception: pass
            R = obj.get("rahmen") or {}
            try:
                import seiten_lod2_je_teil as SL
                kn = SL.ziel_kanten(obj)
                if kn and R.get("mitte_utm"):
                    c = np.mean(np.vstack(kn), 0); mitte = np.asarray(R["mitte_utm"], float) + c[0] * np.asarray(R["xhat_utm"], float) + c[1] * np.asarray(R["yhat_utm"], float); her_m = " (LoD2-Grundflaeche)"
            except Exception: mitte = None
            if mitte is None and R.get("mitte_utm"): mitte = np.asarray(R["mitte_utm"], float); her_m = " (Rahmenmitte objekt.json, ANNAHME)"
        Ub = [U[n] for n in nb if n in U]; Ua = [U[n] for n in na if n in U]
        if mitte is not None:                                                              # Fernfotos (> 150 m) zaehlen nicht fuer die Seite
            Ub = [u for u in Ub if np.linalg.norm(u - mitte) < 150]
        az, her = richtung_aus_punkten(Ub, mitte, Ua if mitte is None else None)
        return az, her + her_m
    except Exception as ex: return None, f"Richtung nicht bestimmbar ({type(ex).__name__}: {ex})"


def luecke(teil, bilder, grund, az=None, az_herkunft=""):
    """Eintrag fuer seiten_modelle.json 'fotoluecken' (lesen: gesamtkette Stufe tore, foto_auftrag --seiten-modelle)."""
    s = seite_name(az) or f"von Teil {teil} (Richtung unbekannt)"
    return dict(teil=teil, bilder=bilder, seite=s, azimut_grad=None if az is None else round(az, 1), azimut_herkunft=az_herkunft, grund=grund, fotos_noetig=FOTOS_NOETIG,
                text=f"Seite {s}: Lage nicht belegt, nicht gebaut - Fotos noetig: Brueckenfotos schraeg ueber Eck / Fernfotos (Teil {teil}, {bilder} Bilder; Wand bleibt 'ungesehen', nichts gespiegelt)")
