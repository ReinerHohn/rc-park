#!/usr/bin/env python3
"""Fester Test (CPU, Sekunden): EINE Funktion je Groesse fuer Ausrichtung (sfm_lod2_ausrichten) und Lage-Tore (lage_gps_pruefen, lage_proben) - 22.11.2026.
Befund Lage-Pruefstand (schwabentor-1120): Ausrichtung '+-11,2 Grad, 1 Gruppe, 105 von 174, kein Fernfoto -> GPS legt nicht fest', GPS-Tor auf derselben Lage '+-1,7 Grad,
2 Gruppen, 10 Fernfotos -> festgelegt'; Kameraauswahl mit verschiedenen Mustern/Filtern; Veto ungerundet gegen Tor gerundet; Lot Kameraebene gegen Bild-x-Achsen;
Objektwand-Abdeckung 0 % bei Kameras rundum.
  1 Kameraauswahl   gps_unsicherheit.foto_pfad/gps_kameras: alle Namensmuster, NaN/0,0/> 5 km weg; Ausrichtung (gps_massstab -> GPS_KAM_ALLE) == Tor (gps_daten), auch bei
                    streuenden Geotags (vorher 3D-RANSAC-Vorfilter nur in der Ausrichtung)
  2 Veto-Rundung    gps_tor_urteil rechnet auf standort_runden (= geschriebene Standorte) -> gleiches Urteil wie das Tor auf der Datei
  3 Lot             seiten_gps_vereinen.lot_info: Vorzeichen per Median (steil nach oben blickende + wenige kopfstehende Bilder: Mittel kippt, Median nicht);
                    Fixture 1120 (Netzsystem vor dem Feinfit): Kameraebenen-Rahmen -> GPS-Fit ohne Fernfotos, kein Anker (Befund nachgestellt), Bild-x-Rahmen -> 125 von 174,
                    10 Fernfotos, Anker = GPS-Tor auf der fertigen Lage; die Ausrichtung nimmt lot_info (Quelltext)
  4 Abdeckung       lage_proben.wand_gesehen: Kameras rundum -> alle Waende gesehen (Schwerpunkt-Regel: 0), Kameras auf einer Seite -> nur die zugewandte Wand;
                    gesehene_kanten unveraendert (alte Formel inline)
  5 Pruefstand      lage_pruefstand.eine_funktion: gleiche Groessen -> GRUEN; 1120-Befund (Ehrlichkeit), andere Kameramenge, Lot 2,3 Grad, Veto/Tor uneinig -> ROT
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_lage_eine_funktion.py"""
import os, sys, json, math, io, contextlib, tempfile, shutil
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
for k_ in ("AUSR_GPS_EINE_QUELLE", "AUSR_GPS_EHRLICH", "AUSR_GPS_ANKER", "AUSR_LOT", "AUSR_ABDECKUNG"): os.environ.pop(k_, None)
import gps_unsicherheit as GU
import lage_gps_pruefen as LGP
import lage_proben as LP
import seiten_gps_vereinen as SG
import sfm_lod2_ausrichten as SA
import lage_pruefstand as LPS
import gps_ausrichtung
from bilder_holen import wgs84_zu_utm

FEHLER = []
def pruef(b, txt):
    print(("    ok    " if b else "    FEHLER ") + txt, flush=True)
    if not b: FEHLER.append(txt)

tmp = __import__("pfade").temp_ordner("test_lage_eine_funktion_")      # Temp auf der Datenplatte, raeumt selbst auf (Waechter test_temp_ordner)
try:
    # ---------- 1 Kameraauswahl
    fd = os.path.join(tmp, "fotos"); os.makedirs(fd)
    dateien = ["IMG_1.jpg", "122_netz.jpg", "eigen__IMG_3.jpeg", "IMG_4.jpg", "IMG_5.jpg", "IMG_6.jpg", "IMG_7.png", "IMG_8.jpg"]
    for d in dateien: open(os.path.join(fd, d), "wb").write(b"\xff\xd8\xff\xd9")
    lat0, lon0 = 47.99, 7.85; e0, n0 = wgs84_zu_utm(lat0, lon0)
    gps = {"IMG_1.jpg": (lat0 + 1e-4, lon0), "122_netz.jpg": (lat0, lon0 + 1e-4), "eigen__IMG_3.jpeg": (lat0 - 1e-4, lon0), "IMG_4.jpg": (float("nan"), lon0),
           "IMG_5.jpg": (0.0, 0.0), "IMG_6.jpg": (lat0 + 0.1, lon0), "IMG_7.png": (lat0, lon0), "IMG_8.jpg": None}
    lesen = lambda p: gps.get(os.path.basename(p))
    pruef(GU.foto_pfad("eigen__IMG_1", fd).endswith("IMG_1.jpg") and GU.foto_pfad("122", fd).endswith("122_netz.jpg") and GU.foto_pfad("IMG_3", fd).endswith("eigen__IMG_3.jpeg")
          and GU.foto_pfad("IMG_7", fd) is None and GU.foto_pfad("IMG_9", [os.path.join(tmp, "leer"), fd]) is None, "1 foto_pfad: Praefix, <name>_*, *__<name>.*, nur JPEG")
    namen = ["eigen__IMG_1", "122", "IMG_3", "IMG_4", "IMG_5", "IMG_6", "IMG_7", "IMG_8", "IMG_9"]
    s0 = GU.gps_kameras(namen, fd, gps_lesen=lesen); s1 = GU.gps_kameras(namen, fd, mitte_utm=[e0, n0], gps_lesen=lesen)
    pruef(s0["namen"] == ["eigen__IMG_1", "122", "IMG_3", "IMG_6"] and s1["namen"] == ["eigen__IMG_1", "122", "IMG_3"] and s0["gefunden"] == 7,
          f"1 gps_kameras: NaN/0,0/ohne GPS weg, > 5 km nur mit Mitte weg ({s0['namen']} / {s1['namen']}, gefunden {s0['gefunden']})")
    # Ausrichtung gegen Tor auf denselben Fotos (Attrappe fuer EXIF-GPS in beiden Modulen); 30 Kameras, 6 davon mit falschem Geotag (Streuung > 2 -> alter 3D-Vorfilter)
    rng = np.random.default_rng(3); n = 30; Cm = np.c_[rng.uniform(-25, 25, n), rng.uniform(-25, 25, n), np.full(n, 1.6)]
    fd2 = os.path.join(tmp, "fotos2"); os.makedirs(fd2); gps2 = {}
    for i in range(n):
        nm = f"IMG_{i:03d}.jpg" if i % 3 else f"x__IMG_{i:03d}.jpg"; open(os.path.join(fd2, nm), "wb").write(b"\xff\xd8\xff\xd9")
        off = rng.normal(0, 2, 2) + (np.array([300.0, -200.0]) * rng.uniform(0.5, 1.5) if i < 6 else 0)
        e, nn = e0 + Cm[i, 0] + off[0], n0 + Cm[i, 1] + off[1]
        lat = lat0 + (nn - n0) / 111200.0; lon = lon0 + (e - e0) / (111200.0 * math.cos(math.radians(lat0))); gps2[nm] = (lat, lon)
    lesen2 = lambda p: gps2.get(os.path.basename(p))
    alt_g, alt_l = gps_ausrichtung.gps_exif, LGP.gps_exif; gps_ausrichtung.gps_exif = lesen2; LGP.gps_exif = lesen2
    try:
        class _Im:
            def __init__(s_, nm): s_.name = nm
        ims = [_Im(f"eigen__IMG_{i:03d}.jpg") for i in range(n)]; Csfm = Cm * 0.1
        obj = dict(rahmen=dict(mitte_utm=[e0, n0], xhat_utm=[1.0, 0.0], yhat_utm=[0.0, 1.0]))
        with contextlib.redirect_stdout(io.StringIO()):
            SA.gps_massstab(ims, Csfm, obj, tmp, fd2)
            nt, *_ = LGP.gps_daten({f"eigen__IMG_{i:03d}": dict(standort=Cm[i].tolist()) for i in range(n)}, fd2, mitte_utm=[e0, n0])
        na = [os.path.splitext(ims[i].name)[0] for i, _ in SA.GPS_KAM_ALLE]
        pruef(sorted(na) == sorted(nt) and len(nt) == n, f"1 Ausrichtung (GPS_KAM_ALLE {len(na)}) und Tor (gps_daten {len(nt)}) sehen dieselben Kameras, auch *__<name> und falsche Geotags")
    finally:
        gps_ausrichtung.gps_exif, LGP.gps_exif = alt_g, alt_l
    q = open(os.path.join(T, "sfm_lod2_ausrichten.py"), encoding="utf-8").read()
    pruef("gps_kameras_alle(GPS_KAM_ALLE" in q and "GU.gps_kameras(" in q and "GU.gps_kameras(" in open(os.path.join(T, "lage_gps_pruefen.py"), encoding="utf-8").read(),
          "1 Verdrahtung: gps_fit der Ausrichtung auf GPS_KAM_ALLE, beide Stufen ueber GU.gps_kameras")

    # ---------- 2 Veto-Rundung
    G = Cm[:, :2] + rng.normal(0, 3, (n, 2)); Xm = Cm[:, :2] + 0.004
    with contextlib.redirect_stdout(io.StringIO()): r_t = LGP.urteil([f"k{i}" for i in range(n)], np.round(Xm, 2), G, zeiten=[None] * n)
    r_v = SA.gps_tor_urteil([f"k{i}" for i in range(n)], Xm, G, [None] * n)
    pruef(r_v[0] == r_t[0] and json.dumps(r_v[1], default=str, sort_keys=True) == json.dumps(r_t[1], default=str, sort_keys=True) and "standort=standort_runden(c)" in q,
          "2 GPS-Veto rechnet auf den geschriebenen (gerundeten) Standorten = GPS-Tor bitgleich")

    # ---------- 3 Lot
    def kam(blick, roll=0.0):
        f = np.asarray(blick, float); f /= np.linalg.norm(f); x = np.cross(f, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(f, x)
        if roll: x, y = -x, -y
        return np.vstack([x, y, f])
    Rs = [kam([math.cos(a), math.sin(a), math.tan(math.radians(75))]) for a in np.linspace(0, 1.5, 7)] + [kam([math.cos(a), math.sin(a), 0.0], roll=True) for a in np.linspace(2, 3, 3)]
    Rs = Rs * 2
    ob_mittel = np.mean([-R[1] for R in Rs], 0); li = SG.lot_info(Rs)
    pruef(ob_mittel[2] < 0 and li["quelle"] == "bildachsen" and li["oben"][2] > 0.999, f"3 lot_info Vorzeichen per Median (Mittel der Bild-oben-Richtungen {ob_mittel[2]:+.2f} zeigt nach unten)")
    FX = json.load(open(os.path.join(T, "test_lage_eine_funktion_fixture.json"))); Gf = np.array(FX["gps_modell"]); Zf = FX["zeiten"]
    fe = GU.gps_fit(np.array(FX["kamera_ebene"]), Gf, Zf); fb = GU.gps_fit(np.array(FX["kamera_bildachsen"]), Gf, Zf)
    print(f"      1120 vor dem Feinfit: Kameraebene {fe['ransac']}, fern {fe['n_fern_inlier']}, +-{fe['sd_drehung_grad']:.1f} Grad, Anker {fe['anker'] is not None} | "
          f"Bild-x {fb['ransac']}, fern {fb['n_fern_inlier']}, +-{fb['sd_drehung_grad']:.1f} Grad, Anker {fb['anker'] is not None}")
    pruef(fe["n_fern_inlier"] == 0 and fe["anker"] is None and fe["sd_drehung_grad"] > 8, "3 Befund nachgestellt: GPS-Fit im Kameraebenen-Rahmen ohne Fernfotos, 'legt nicht fest'")
    pruef(fb["ransac"] and fb["ransac"]["inlier"] == 125 and fb["n_fern_inlier"] == 10 and fb["anker"] is not None and fb["sd_drehung_grad"] < 1.5 and fb["systematik"]["n_gruppen"] == 2,
          "3 Bild-x-Rahmen: 125 von 174, 10 Fernfotos, 2 Gruppen, Anker = GPS-Tor auf der fertigen 1120-Lage")
    pruef("_SG.lot_info(" in q and 'LOT["quelle"] = "bildachsen"' in q and "return lot_info(Rs)[\"oben\"]" in open(os.path.join(T, "seiten_gps_vereinen.py"), encoding="utf-8").read(),
          "3 Verdrahtung: Ausrichtung und seiten_gps_vereinen nehmen lot_info")

    # ---------- 4 Abdeckung / Sicht
    sq = np.array([[-6, -6], [6, -6], [6, 6], [-6, 6]], float); S, N = [], []
    for i in range(4):
        p0, p1 = sq[i], sq[(i + 1) % 4]; e = (p1 - p0) / np.linalg.norm(p1 - p0); nrm = np.array([e[1], -e[0]])
        for t in np.linspace(0.05, 0.95, 20): S.append(p0 + t * (p1 - p0)); N.append(nrm)
    S, N = np.array(S), np.array(N); wand = np.repeat(np.arange(4), 20)
    ang = np.radians(np.arange(0, 360, 15)); Cr = np.c_[20 * np.cos(ang), 20 * np.sin(ang)]; Vr = -Cr
    alt = (((Cr.mean(0) - S) * N).sum(1) > 0)
    neu = LP.wand_gesehen(S, N, Cr, Vr, np.full(len(Cr), 35.0))
    a1 = np.radians(np.arange(240, 301, 10)); C1 = np.c_[20 * np.cos(a1), 20 * np.sin(a1)]; n1 = LP.wand_gesehen(S, N, C1, -C1, np.full(len(C1), 35.0))
    pruef(neu.mean() == 1.0 and alt.mean() < 0.6, f"4 Kameras rundum: neu {100 * neu.mean():.0f} % gesehen (Schwerpunkt-Regel {100 * alt.mean():.0f} %, Mitte im Gebaeude)")
    pruef(n1[wand == 0].all() and not n1[wand == 2].any(), "4 Kameras auf einer Seite: nur die zugewandte Wand gesehen")
    def kanten_alt(polys, C, V, halb_fov_grad, max_m=LP.SICHT_MAX_M, schritt=0.5):   # Formel bis 22.11.2026 (inline), muss gleich bleiben
        C = np.asarray(C, float)[:, :2]; V = np.asarray(V, float)[:, :2]; V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9); cf = np.cos(np.radians(np.asarray(halb_fov_grad, float)))
        seg = []; alle = [g for _, g in polys]
        for k, g in enumerate(alle):
            A = 0.5 * np.sum(g[:, 0] * np.roll(g[:, 1], -1) - np.roll(g[:, 0], -1) * g[:, 1]); vz = 1.0 if A > 0 else -1.0
            for p0, p1 in zip(g, np.roll(g, -1, 0)):
                L = float(np.linalg.norm(p1 - p0)); e = (p1 - p0) / L; nn_ = vz * np.array([e[1], -e[0]]); m = max(2, int(L / schritt)); S_ = p0 + (np.arange(m) + 0.5)[:, None] / m * (p1 - p0)
                probe = S_ + 0.3 * nn_; brand = np.zeros(m, bool)
                for j, h in enumerate(alle):
                    if j != k and np.all(h.min(0) - 1 <= probe.max(0)) and np.all(h.max(0) + 1 >= probe.min(0)): brand |= LP.in_polygon(probe, h)
                D = C[None, :, :] - S_[:, None, :]; dist = np.linalg.norm(D, axis=2); vorn = (D @ nn_) > 0
                blick = (-(D / np.maximum(dist[..., None], 1e-9)) * V[None]).sum(2) >= cf[None]
                if ((((dist <= max_m) & vorn & blick).sum(1) >= LP.SICHT_MIN_KAMERAS) & ~brand).mean() >= 0.5: seg.append(np.array([p0, p1]))
        return seg
    polys = [("A", sq), ("B", sq + [14.0, 0.0]), ("C", sq[::-1] + [-30.0, 5.0])]
    for Cx, Vx in ((C1, -C1), (Cr, Vr), (Cr, np.c_[np.ones(len(Cr)), np.zeros(len(Cr))])):
        Cx3 = np.c_[Cx, np.full(len(Cx), 1.6)]; Vx3 = np.c_[Vx, np.zeros(len(Vx))]; fov = np.linspace(20, 50, len(Cx))
        s_neu = LP.gesehene_kanten(polys, Cx3, Vx3, fov); s_alt = kanten_alt(polys, Cx3, Vx3, fov)
        pruef(len(s_neu) == len(s_alt) and all(np.array_equal(a_, b_) for a_, b_ in zip(s_neu, s_alt)), f"4 gesehene_kanten ueber wand_gesehen = alte Formel ({len(s_neu)} Kanten)")
    pruef("LP.wand_gesehen(Wo[:, :2], Wn[:, :2], Cm_" in q, "4 Verdrahtung: Objektwand-Abdeckung der Ausrichtung nimmt wand_gesehen")

    # ---------- 5 Pruefstand-Zeile 'eine Funktion'
    eh_t = dict(anker=True, sd_drehung_grad=1.02, n_gruppen=2)
    gv = dict(kameras=dict(ausrichtung=174, tor=174, n_nur_ausrichtung=0, n_nur_tor=0), ehrlich=dict(ausrichtung=dict(anker=True, sd_drehung_grad=1.05, n_gruppen=2), tor=eh_t),
              fit=dict(ausrichtung=dict(rc=0), tor=dict(rc=0)))
    lot = dict(quelle_ausrichtung="bildachsen", ausrichtung_gegen_bildachsen_grad=0.0)
    e0_ = LPS.eine_funktion(gv, lot); pruef(e0_["farbe"] == "gruen" and not e0_["abweichungen"] and len(e0_["je"]) == 4, f"5 gleiche Groessen -> GRUEN {e0_['je']}")
    gv1 = json.loads(json.dumps(gv)); gv1["ehrlich"]["ausrichtung"] = dict(anker=False, sd_drehung_grad=11.2, n_gruppen=1)
    e1_ = LPS.eine_funktion(gv1, lot); pruef(e1_["farbe"] == "rot" and e1_["je"]["ehrlichkeit"] is False and "Ehrlichkeit" in e1_["abweichungen"][0], f"5 1120-Befund (+-11,2 / +-1,0 Grad) -> ROT: {e1_['abweichungen']}")
    gv2 = json.loads(json.dumps(gv)); gv2["kameras"].update(ausrichtung=105, n_nur_tor=69)
    pruef(LPS.eine_funktion(gv2, lot)["je"]["kameramenge"] is False, "5 andere Kameramenge -> ROT")
    pruef(LPS.eine_funktion(gv, dict(lot, ausrichtung_gegen_bildachsen_grad=2.3, quelle_ausrichtung="kameraebene"))["farbe"] == "rot", "5 Lot 2,3 Grad daneben -> ROT")
    gv3 = json.loads(json.dumps(gv)); gv3["fit"]["tor"]["rc"] = 3
    pruef(LPS.eine_funktion(gv3, lot)["je"]["veto"] is False, "5 Veto besteht, Tor verwirft dieselbe Lage -> ROT")
    pruef(LPS.eine_funktion({}, {})["farbe"] == "grau", "5 nichts gerechnet -> GRAU (kein Urteil)")
    pq = open(os.path.join(T, "lage_pruefstand.py"), encoding="utf-8").read()
    pruef('lauf["eine_funktion"] = eine_funktion(' in pq and "eine Funktion {ef['farbe'].upper()}" in pq, "5 Pruefstand schreibt die Zeile je Loesung")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("LAGE-EINE-FUNKTION-TEST:", "bestanden" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
