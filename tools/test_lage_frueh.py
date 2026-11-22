#!/usr/bin/env python3
"""Fester Test (CPU, synthetisch, ~1 min): Vorstufe 'Lage frueh' (tools/lage_frueh.py) - Ausrichtung + GPS-Tor + Lageproben auf dem duennen Netz VOR der dichten Wolke (22.11.2026).
  1 sparse_lesen/sparse_ply: COLMAP points3D.bin -> PLY im Format der dichten Wolke, Auswahl Spur >= 3 und Fehler < p90 (wie die Ausrichtung mit --sparse)
  2 Regel: lage_frueh_bestanden = lage_bestanden ohne Grundriss; eindeutig_durchgefallen nur bei rc 3 eines geprueften Tors fuer JEDE Loesung, nie bei abgestuerztem Tor
  3 Ende zu Ende auf einer kuenstlichen Szene (3 LoD2-Kaesten, sparse-Netz in gedrehtem/skaliertem SfM-System, Foto-GPS als Attrappe):
      richtiges GPS -> rc 0, Lage < 0,5 m; GPS 35 Grad verdreht -> rc 3 'DURCHGEFALLEN' mit benannter Ursache; Fotos ohne GPS -> rc 4 (kein Urteil);
      geschrieben wird nur in --aus (Objekt und Eingaben unberuehrt)
  4 Kette: sfm_mit_vorstufe mit Attrappen fuer lauf/notiz - rc 3 + Standard -> Abbruchtext, KEIN zweiter pipeline_objekt-Aufruf; bestanden -> zweiter Aufruf OHNE --neu
    und ohne RCPARK_PIPE_NEU (danach wiederhergestellt); 'hinweis' -> weiter trotz rc 3; SfM gescheitert -> rc durchgereicht, keine Vorstufe;
    pipeline_objekt endet bei --bis kameras VOR der dichten Wolke; gesamtkette ruft die Vorstufe (Schalter RCPARK_LAGE_FRUEH)
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_lage_frueh.py"""
import os, sys, json, math, struct, shutil, tempfile, io, contextlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ["ALIGN_CPU"] = "1"
import numpy as np
from scipy.spatial.transform import Rotation as Rot
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
for k_ in ("AUSR_GPS_EINE_QUELLE", "AUSR_GPS_EHRLICH", "AUSR_GPS_ANKER", "AUSR_LOT", "AUSR_ABDECKUNG", "AUSR_ZWISCHEN", "RCPARK_LAGE_FRUEH", "RCPARK_PIPE_NEU"): os.environ.pop(k_, None)
import lage_frueh as LF
import lage_proben as LP
import sfm_lod2_ausrichten as SA
import lage_gps_pruefen as LGP
import gps_ausrichtung, bilder_holen
import wolke_grundriss_pruefen as WG

FEHLER = []
def pruef(b, txt):
    print(("    ok    " if b else "    FEHLER ") + txt, flush=True)
    if not b: FEHLER.append(txt)

KAESTEN = [("ZIEL", (0.0, 0.0), (12.0, 8.0), 15.0), ("N1", (21.0, 1.0), (8.0, 10.0), 12.0), ("N2", (-6.0, 17.0), (10.0, 6.0), 10.0)]
def ecken(c, g):
    hx, hy = g[0] / 2, g[1] / 2; return np.array([[c[0] - hx, c[1] - hy], [c[0] + hx, c[1] - hy], [c[0] + hx, c[1] + hy], [c[0] - hx, c[1] + hy]])
def lod2_fake(obj, radius, dichte=0.35):
    rng = np.random.default_rng(0); pts, nrm, typ, eig, w2, g2 = [], [], [], [], [], []
    for nm, c, g, h in KAESTEN:
        E = ecken(c, g); g2.append(E.copy())
        for i in range(4):
            p0, p1 = E[i], E[(i + 1) % 4]; L = np.linalg.norm(p1 - p0); k = max(1, int(L * h / dichte ** 2)); u = rng.random((k, 2))
            P = np.c_[p0 + u[:, :1] * (p1 - p0), u[:, 1] * h]; d = (p1 - p0) / L; n = np.array([d[1], -d[0], 0.0])
            pts.append(P); nrm.append(np.repeat(n[None], k, 0)); typ.append(np.zeros(k, int)); eig.append(np.full(k, nm == "ZIEL")); w2.append(np.array([p0, p1, p1, p0]))
        k = int(g[0] * g[1] / dichte ** 2); u = rng.random((k, 2)); P = np.c_[c[0] - g[0] / 2 + u[:, 0] * g[0], c[1] - g[1] / 2 + u[:, 1] * g[1], np.full(k, h)]
        pts.append(P); nrm.append(np.repeat([[0, 0, 1.0]], k, 0)); typ.append(np.ones(k, int)); eig.append(np.full(k, nm == "ZIEL"))
    return np.vstack(pts), np.vstack(nrm), np.concatenate(typ), w2, g2, len(KAESTEN), np.concatenate(eig)
def grundrisse_fake(obj, radius): return [dict(id=nm, ground=[ecken(c, g)]) for nm, c, g, h in KAESTEN]
S_WAHR = 0.37; R_WAHR = Rot.from_euler("zyx", [63.0, 4.0, -7.0], degrees=True).as_matrix(); T_WAHR = np.array([3.0, -2.0, 5.0])
zu_sfm = lambda X: S_WAHR * np.asarray(X, float) @ R_WAHR.T + T_WAHR
MITTE = np.array([100500.0, 100500.0])

def points3d_schreiben(pfad, P, fehler, spur):
    with open(pfad, "wb") as f:
        f.write(struct.pack("<Q", len(P)))
        for i, (p, e, tl) in enumerate(zip(P, fehler, spur)):
            f.write(struct.pack("<Q3d3Bd", i + 1, *p, 120, 130, 140, e) + struct.pack("<Q", tl) + b"".join(struct.pack("<ii", j, j) for j in range(tl)))

def szene(ordner):
    """pipe-Ordner wie die Kette (sfm/sparse/0/points3D.bin, kameras.json), Fotos (leere JPEG), objekt.json. -> (pfade, Kamerastandorte Modell)."""
    rng = np.random.default_rng(1); W = []
    for nm, c, g, h in KAESTEN:
        E = ecken(c, g)
        for i in range(4):
            p0, p1 = E[i], E[(i + 1) % 4]; k = int(np.linalg.norm(p1 - p0) * h * 1.5); u = rng.random((k, 2))
            W.append(np.c_[p0 + u[:, :1] * (p1 - p0), u[:, 1] * h * 0.8] + rng.normal(0, 0.03, (k, 3)))
    ang = np.radians(np.arange(200, 341, 5)); rr = 16 + 2 * np.sin(3 * ang); Cm = np.c_[rr * np.cos(ang), rr * np.sin(ang), np.full(len(ang), 1.6)]
    Cm = Cm[(np.hypot(Cm[:, 0] - 21, Cm[:, 1] - 1) > 7) & (np.hypot(Cm[:, 0] + 6, Cm[:, 1] - 17) > 6)]
    for c in Cm: W.append(np.c_[c[0] + rng.uniform(-3, 3, 60), c[1] + rng.uniform(-3, 3, 60), rng.normal(0, 0.02, 60)])
    W = np.vstack(W); n = len(W); fehler = rng.uniform(0.2, 1.0, n); spur = rng.integers(3, 6, n); spur[:200] = 2; fehler[200:400] = 9.0     # 200 kurze Spuren, 200 grosse Fehler
    P = os.path.join(ordner, "pipe"); sp = os.path.join(P, "sfm", "sparse", "0"); os.makedirs(sp); points3d_schreiben(os.path.join(sp, "points3D.bin"), zu_sfm(W), fehler, spur)
    bilder = []
    for i, c in enumerate(Cm):
        fw = np.r_[-c[:2], 0.0]; fw /= np.linalg.norm(fw); rx = np.cross(fw, [0, 0, 1.0]); rx /= np.linalg.norm(rx); dn = np.cross(fw, rx)
        Rc = np.vstack([rx, dn, fw]) @ R_WAHR.T; Cs = zu_sfm(c[None])[0]; bilder.append(dict(name=f"eigen__IMG_{i:03d}.jpg", cam=1, R=Rc.tolist(), t=(-Rc @ Cs).tolist(), C=Cs.tolist()))
    json.dump(dict(bilder=bilder, kameras={"1": dict(params=[1500.0, 1000.0, 750.0], model="SIMPLE_PINHOLE", width=2000, height=1500)}), open(os.path.join(P, "kameras.json"), "w"))
    fd = os.path.join(ordner, "fotos"); os.makedirs(fd)
    for i in range(len(Cm)): open(os.path.join(fd, f"IMG_{i:03d}.jpg"), "wb").write(b"\xff\xd8\xff\xd9")
    obj = dict(name="Testtor", fotos_dir=fd, lod2=dict(gml=os.path.join(ordner, "fehlt.gml"), id="ZIEL"), rahmen=dict(mitte_utm=MITTE.tolist(), xhat_utm=[1.0, 0.0], yhat_utm=[0.0, 1.0], gelaende=0.0))
    od = os.path.join(ordner, "modelle", "testtor"); os.makedirs(od); json.dump(obj, open(os.path.join(od, "objekt.json"), "w"))
    return dict(objekt=os.path.join(od, "objekt.json"), pipe=P, fotos=fd, n_punkte=n, gut=int(((spur >= 3) & (fehler < np.percentile(fehler, 90))).sum())), Cm

def gps_setzen(Cm, dreh_grad=0.0, an=True):
    """Attrappe: EXIF-GPS = (E, N) direkt, wgs84_zu_utm = Identitaet; GPS = wahre Kamerastandorte (+-2 m), optional um die Objektmitte verdreht."""
    rng = np.random.default_rng(7); a = math.radians(dreh_grad); R2 = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    G = {f"IMG_{i:03d}.jpg": tuple(MITTE + R2 @ c[:2] + rng.normal(0, 2.0, 2)) for i, c in enumerate(Cm)}
    gps_ausrichtung.gps_exif = (lambda p: G.get(os.path.basename(p))) if an else (lambda p: None); LGP.gps_exif = gps_ausrichtung.gps_exif
    bilder_holen.wgs84_zu_utm = lambda la, lo, zone=32: (float(la), float(lo))

SA.lod2_ziel = lod2_fake; WG.grundrisse = grundrisse_fake
_alt = (gps_ausrichtung.gps_exif, LGP.gps_exif, bilder_holen.wgs84_zu_utm)
tmp = tempfile.mkdtemp(prefix="test_lage_frueh_")
try:
    # ---------- 1 sparse -> PLY
    p, Cm = szene(os.path.join(tmp, "stand"))
    ply = os.path.join(tmp, "x", "s.ply"); n = LF.sparse_ply(os.path.join(p["pipe"], "sfm", "sparse", "0"), ply)
    kopf = open(ply, "rb").read(400).decode(errors="ignore")
    Pl, Fl, El, Ll = LF.sparse_lesen(os.path.join(p["pipe"], "sfm", "sparse", "0", "points3D.bin"))
    pruef(len(Pl) == p["n_punkte"] and Fl[0].tolist() == [120, 130, 140] and n == p["gut"] and "property float nx" in kopf and "element vertex %d" % n in kopf,
          f"1 points3D.bin gelesen ({len(Pl)}), PLY mit {n} Punkten (Spur >= 3, Fehler < p90; erwartet {p['gut']}), Format der dichten Wolke")
    # ---------- 2 Regeln
    pruef(LP.lage_frueh_bestanden(dict(gps=0, lage_proben=None)) and not LP.lage_frueh_bestanden(dict(gps=3)) and not LP.lage_frueh_bestanden(dict(gps=0, lage_proben=3))
          and LP.lage_bestanden(dict(gps=0, lage_proben=0, grundriss=0)) == LP.lage_frueh_bestanden(dict(gps=0, lage_proben=0)), "2 lage_frueh_bestanden = lage_bestanden ohne Grundriss")
    l3 = dict(tore=dict(gps=3, lage_proben=None), kaputt=False, bestanden=False); l0 = dict(tore=dict(gps=0, lage_proben=None), kaputt=False, bestanden=True)
    lk = dict(tore=dict(gps=4, lage_proben=None), kaputt=True, bestanden=False); ln = dict(tore=dict(gps=0, lage_proben=None), kaputt=False, bestanden=False)
    pruef(LF.eindeutig_durchgefallen([l3, dict(l3, tore=dict(gps=0, lage_proben=3))]) and not LF.eindeutig_durchgefallen([l3, l0]) and not LF.eindeutig_durchgefallen([l3, lk])
          and not LF.eindeutig_durchgefallen([ln]) and not LF.eindeutig_durchgefallen([]), "2 eindeutig durchgefallen nur, wenn JEDE Loesung an einem geprueften Tor (rc 3) faellt")
    # ---------- 3 Ende zu Ende
    vorher = {os.path.join(dp, f): os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.join(tmp, "stand")) for f in fs}
    def lf(aus, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = LF.main([p["objekt"], p["pipe"], p["fotos"], "--ziel", "testtor", "--aus", aus, "--max-loesung", "2"] + ["--radius", "30"] + list(extra))
        return rc, buf.getvalue(), json.load(open(os.path.join(aus, "lage_frueh.json")))
    gps_setzen(Cm)
    rc, out, J = lf(os.path.join(tmp, "aus_gut"))
    print("      " + out.strip().replace("\n", "\n      ")[-900:])
    au = json.load(open(os.path.join(tmp, "aus_gut", "messprotokoll", "SFM-AUSRICHTUNG-testtor.json")))
    st = np.array([au["kameras"][f"eigen__IMG_{i:03d}"]["standort"] for i in range(len(Cm))])
    err = float(np.median(np.linalg.norm(st - Cm, axis=1)))
    pruef(rc == 0 and J["rc"] == 0 and J["laeufe"][0]["tore"]["gps"] == 0 and err < 0.5, f"3 richtiges GPS: rc {rc}, GPS-Tor {J['laeufe'][0]['tore']}, Kameras {err:.2f} m neben der Wahrheit")
    gps_setzen(Cm, dreh_grad=35.0)
    rc3, out3, J3 = lf(os.path.join(tmp, "aus_falsch"))
    print("      " + out3.strip().splitlines()[-1][:400])
    pruef(rc3 == 3 and "DURCHGEFALLEN" in J3["grund"] and all(l["tore"]["gps"] == 3 for l in J3["laeufe"]), f"3 GPS 35 Grad verdreht: rc {rc3}, {len(J3['laeufe'])} Loesung(en) am GPS-Tor verworfen, Grund benannt")
    gps_setzen(Cm, an=False)
    rc4, out4, J4 = lf(os.path.join(tmp, "aus_ohne"))
    pruef(rc4 in (0, 4) and rc4 != 3, f"3 Fotos ohne GPS: rc {rc4} ({J4['grund'][:120]}) - nie Abbruch ohne Urteil")
    nachher = {os.path.join(dp, f): os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.join(tmp, "stand")) for f in fs}
    pruef(nachher == vorher, "3 Objektordner und Eingaben unberuehrt (alles in --aus)")
    # ---------- 4 Kette
    def kette(rc_bis=0, rc_fr=0, modus=None, pipe_neu=None):
        aufrufe = []; B = dict(schritte=[]); P_ = os.path.join(tmp, "k_pipe"); os.makedirs(os.path.join(P_, "lage_frueh"), exist_ok=True)
        if modus is None: os.environ.pop("RCPARK_LAGE_FRUEH", None)
        else: os.environ["RCPARK_LAGE_FRUEH"] = modus
        if pipe_neu is None: os.environ.pop("RCPARK_PIPE_NEU", None)
        else: os.environ["RCPARK_PIPE_NEU"] = pipe_neu
        def lauf_(B_, name, cmd, log, ok=(0,), timeout=None, platz=()):
            aufrufe.append((name, list(cmd), os.environ.get("RCPARK_PIPE_NEU")))
            if name == "lage_frueh": json.dump(dict(rc=rc_fr, grund="Testgrund", laeufe=[dict(loesung=0, tore=dict(gps=rc_fr), bestanden=rc_fr == 0)]), open(os.path.join(P_, "lage_frueh", "lage_frueh.json"), "w"))
            return (rc_bis if name == "sfm_bis_kameras" else rc_fr if name == "lage_frueh" else 0), ""
        notizen = []
        r = LF.sfm_mit_vorstufe(B, lauf_, lambda B_, n_, ok_, **k: notizen.append((n_, ok_, k)), ["py", "pipeline_objekt.py", "z", "F", P_], ["--neu", "sfm"], "modelle/z/objekt.json", P_, "F", "z", "log", 60)
        return r, aufrufe, notizen, B
    r, au_, no_, B_ = kette(rc_fr=3)
    pruef(r[1] and "LAGE FRUEH" in r[1] and [a_[0] for a_ in au_] == ["sfm_bis_kameras", "lage_frueh"] and "--bis" in au_[0][1] and "--neu" in au_[0][1] and B_["lage"]["fehler"] == "lage_frueh"
          and no_[0][0] == "lage_frueh" and no_[0][1] is False, "4 rc 3 (Standard) -> Abbruch vor der dichten Wolke, kein zweiter Aufruf, Zeile lage_frueh rot")
    r, au_, no_, B_ = kette(rc_fr=0, pipe_neu="sfm")
    pruef(r == (0, None) and [a_[0] for a_ in au_] == ["sfm_bis_kameras", "lage_frueh", "sfm"] and "--neu" not in au_[2][1] and "--bis" not in au_[2][1] and au_[2][2] is None
          and au_[0][2] == "sfm" and os.environ.get("RCPARK_PIPE_NEU") == "sfm", "4 bestanden -> zweiter Aufruf ohne --neu/--bis und ohne RCPARK_PIPE_NEU (danach wiederhergestellt)")
    r, au_, _, _ = kette(rc_fr=3, modus="hinweis"); pruef(r == (0, None) and au_[-1][0] == "sfm", "4 RCPARK_LAGE_FRUEH=hinweis -> trotz rc 3 weiter")
    r, au_, _, _ = kette(rc_bis=2); pruef(r == (2, None) and len(au_) == 1, "4 SfM gescheitert -> rc durchgereicht, keine Vorstufe")
    r, au_, _, _ = kette(rc_fr=4); pruef(r == (0, None) and au_[-1][0] == "sfm", "4 Vorstufe ohne Urteil (rc 4) -> weiter")
    os.environ.pop("RCPARK_LAGE_FRUEH", None); os.environ.pop("RCPARK_PIPE_NEU", None)
    qp = open(os.path.join(T, "pipeline_objekt.py"), encoding="utf-8").read(); qg = open(os.path.join(T, "gesamtkette.py"), encoding="utf-8").read()
    i_bis = qp.find('== ["kameras"]:'); i_dicht = qp.find('fused = os.path.join(daten, "dicht", "fused.ply")'); i_kam = qp.find('kam_json = os.path.join(daten, "kameras.json")')
    pruef(0 < i_kam < i_bis < i_dicht, "4 pipeline_objekt --bis kameras endet nach kameras.json und VOR der dichten Wolke")
    pruef('__import__("lage_frueh").sfm_mit_vorstufe(' in qg and 'os.environ.get("RCPARK_LAGE_FRUEH", "1") != "0"' in qg, "4 gesamtkette ruft die Vorstufe (abschaltbar RCPARK_LAGE_FRUEH=0)")
finally:
    gps_ausrichtung.gps_exif, LGP.gps_exif, bilder_holen.wgs84_zu_utm = _alt
    shutil.rmtree(tmp, ignore_errors=True)
print("LAGE-FRUEH-TEST:", "bestanden" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
