#!/usr/bin/env python3
"""Fester Test (CPU, synthetisch, ~1 min): Lage-Pruefstand + Zwischenstand der Ausrichtung (22.11.2026).
  1 sfm_lod2_ausrichten.ausrichten als Funktion auf einer kuenstlichen Szene (3 LoD2-Kaesten, Wolke + Kameras in einem gedrehten/skalierten SfM-System):
    findet die Lage (Kameras < 0,3 m), rc 0, alle Loesungen mit Kamerastandorten im Ergebnis.
  2 DER CACHE AENDERT DAS ERGEBNIS NICHT: kalt (rechnet + legt ab), warm (nur Treffer, 0 neu) und ohne Cache (AUSR_ZWISCHEN=0) liefern bitgleiche Transformation,
    Loesungsliste, Kamerastandorte und dieselbe geschriebene SFM-AUSRICHTUNG-Datei; --loesung 1 aus dem warmen Cache rechnet keine Grobsuche neu.
  3 Schluessel nach Inhalt: anderer Datenstand (eine Kamera verschoben) -> neue Rechnung; Code-Abschnitt 'fein'/'grob' haengt nur an seinem Text (Marken eindeutig).
  4 lage_vergleich: bekannte Drehung/Massstab/Versatz zwischen zwei Kamerasaetzen wird gemessen; zu wenig gemeinsame Fotos -> Grund statt Absturz.
  5 Pruefstand Ende zu Ende auf dem synthetischen Stand (Konfig-JSON, Kopie von objekt.json im eigenen Ordner, NICHTS in den Eingabeordnern geschrieben),
    fehlender Stand -> 'fehlt', Zeile mit Toren; gesamtkette nutzt dieselbe Tor-Regel (lage_proben.tor_rc / lage_bestanden)."""
import os, sys, json, math, shutil, tempfile, hashlib, io, contextlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ["ALIGN_CPU"] = "1"                 # nie die GPU (Kettenjob)
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import sfm_lod2_ausrichten as SA
import lage_pruefstand as LPS
from scipy.spatial.transform import Rotation as Rot

FEHLER = []
def pruef(b, txt):
    print(("    ok    " if b else "    FEHLER ") + txt, flush=True)
    if not b: FEHLER.append(txt)

# ---------- synthetische Szene (Modellsystem m)
KAESTEN = [("ZIEL", (0.0, 0.0), (12.0, 8.0), 15.0), ("N1", (21.0, 1.0), (8.0, 10.0), 12.0), ("N2", (-6.0, 17.0), (10.0, 6.0), 10.0)]
rng0 = np.random.default_rng(42)

def ecken(c, g):
    hx, hy = g[0] / 2, g[1] / 2; return np.array([[c[0] - hx, c[1] - hy], [c[0] + hx, c[1] - hy], [c[0] + hx, c[1] + hy], [c[0] - hx, c[1] + hy]])

def lod2_fake(obj, radius, dichte=0.35):
    """Ersatz fuer sfm_lod2_ausrichten.lod2_ziel (gleiche Rueckgabe): Waende/Daecher der Kaesten abgetastet."""
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

def grundrisse_fake(obj, radius):
    return [dict(id=nm, ground=[ecken(c, g)]) for nm, c, g, h in KAESTEN]

S_WAHR = 0.37; R_WAHR = Rot.from_euler("zyx", [63.0, 4.0, -7.0], degrees=True).as_matrix(); T_WAHR = np.array([3.0, -2.0, 5.0])
zu_sfm = lambda X: S_WAHR * np.asarray(X, float) @ R_WAHR.T + T_WAHR

def szene(ordner, kamera_versatz=0.0):
    """Schreibt objekt.json, kameras.json, fused.ply, leeren Fotoordner. -> (pfade, Kamerastandorte im Modellsystem)."""
    os.makedirs(ordner, exist_ok=True); rng = np.random.default_rng(1)
    W = []                                                                              # Wolke: Fassaden (alle Seiten), Boden um die Kameras
    for nm, c, g, h in KAESTEN:
        E = ecken(c, g)
        for i in range(4):
            p0, p1 = E[i], E[(i + 1) % 4]; k = int(np.linalg.norm(p1 - p0) * h * 6); u = rng.random((k, 2))
            W.append(np.c_[p0 + u[:, :1] * (p1 - p0), u[:, 1] * h * 0.8] + rng.normal(0, 0.03, (k, 3)))
    # Kameras wie Strassenfotos auf EINER Seite (Bogen im Sueden). Ein voller Ring um das Objekt legt den Kameraschwerpunkt ins Gebaeude -> 'Objektwand-Abdeckung'
    # der Ausrichtung (Waende, die zum Kameraschwerpunkt zeigen) wird 0 und die richtige Loesung verliert (Befund dieses Tests, 22.11.2026; Werkzeug unveraendert).
    ang = np.radians(np.arange(200, 341, 5)); rr = 16 + 2 * np.sin(3 * ang); Cm = np.c_[rr * np.cos(ang), rr * np.sin(ang), np.full(len(ang), 1.6)]
    Cm = Cm[(np.hypot(Cm[:, 0] - 21, Cm[:, 1] - 1) > 7) & (np.hypot(Cm[:, 0] + 6, Cm[:, 1] - 17) > 6)]; Cm[0, 0] += kamera_versatz
    for c in Cm: W.append(np.c_[c[0] + rng.uniform(-3, 3, 150), c[1] + rng.uniform(-3, 3, 150), rng.normal(0, 0.02, 150)])
    W = np.vstack(W); Ws = zu_sfm(W)
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    V = np.zeros(len(Ws), dt); V["x"], V["y"], V["z"] = Ws.T; V["r"] = 128
    with open(os.path.join(ordner, "fused.ply"), "wb") as f:
        f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {len(V)}\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\n"
                "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n".encode()); f.write(V.tobytes())
    bilder = []
    for i, c in enumerate(Cm):
        fw = np.r_[-c[:2], 0.0]; fw /= np.linalg.norm(fw); rx = np.cross(fw, [0, 0, 1.0]); rx /= np.linalg.norm(rx); dn = np.cross(fw, rx)   # Blick waagerecht zur Mitte
        Rm = np.vstack([rx, dn, fw]); Rc = Rm @ R_WAHR.T; Cs = zu_sfm(c[None])[0]
        bilder.append(dict(name=f"eigen__IMG_{i:03d}.jpg", cam=1, R=Rc.tolist(), t=(-Rc @ Cs).tolist(), C=Cs.tolist()))
    json.dump(dict(bilder=bilder, kameras={"1": dict(params=[1500.0, 1000.0, 750.0], model="SIMPLE_PINHOLE", width=2000, height=1500)}), open(os.path.join(ordner, "kameras.json"), "w"))
    os.makedirs(os.path.join(ordner, "fotos"), exist_ok=True)
    obj = dict(name="Testtor", fotos_dir=os.path.join(ordner, "fotos"), lod2=dict(gml=os.path.join(ordner, "fehlt.gml"), id="ZIEL"),
               rahmen=dict(mitte_utm=[100500.0, 100500.0], xhat_utm=[1.0, 0.0], yhat_utm=[0.0, 1.0], gelaende=0.0))
    od = os.path.join(ordner, "modelle", "testtor"); os.makedirs(od, exist_ok=True); json.dump(obj, open(os.path.join(od, "objekt.json"), "w"))
    return dict(objekt=os.path.join(od, "objekt.json"), kameras=os.path.join(ordner, "kameras.json"), dicht=os.path.join(ordner, "fused.ply"), fotos=os.path.join(ordner, "fotos")), Cm

ARGS_KLEIN = ["--radius", "30", "--zelle", "0.5", "--fein-punkte", "3000", "--fit_punkte", "60000"]

def lauf(p, *extra, schreiben=True):
    argv = [p["objekt"], "--kameras", p["kameras"], "--dicht", p["dicht"], "--name", "testtor"] + ARGS_KLEIN + (["--schreiben"] if schreiben else []) + ["--fotos", p["fotos"]] + list(extra)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): E = SA.ausrichten(argv)
    return E, buf.getvalue()

def kern(E):
    """Vergleichbarer Kern des Ergebnisses (bitgleich gefordert)."""
    return (E["rc"], E["loesung_nr"], E["n_unterscheidbar"], json.dumps(E["transformation"], sort_keys=True), np.asarray(E["kameras_gewaehlt"]).tobytes(),
            json.dumps([(l["guete"], l["rms_m"], l["inlier"], l["abdeckung"], l["p"]) for l in E["loesungen"]]), E.get("s_sigma_prozent"), json.dumps(E.get("t_sigma_m")))

SA.lod2_ziel = lod2_fake
import wolke_grundriss_pruefen as WG; WG.grundrisse = grundrisse_fake
tmp = tempfile.mkdtemp(prefix="test_lage_pruefstand_")
try:
    p, Cm = szene(os.path.join(tmp, "stand"))
    os.environ.pop("AUSR_ZWISCHEN", None)
    # 1 + 2
    E1, log1 = lauf(p); au = os.path.join(os.path.dirname(p["objekt"]), "messprotokoll", "SFM-AUSRICHTUNG-testtor.json"); au1 = open(au, "rb").read()
    err = np.linalg.norm(np.asarray(E1["kameras_gewaehlt"]) - Cm, axis=1)
    pruef(E1["rc"] == 0 and np.median(err) < 0.3, f"1 ausrichten() findet die Lage: rc {E1['rc']}, Kameras Median {np.median(err):.3f} m daneben, {E1['n_unterscheidbar']} unterscheidbare Loesung(en)")
    pruef(len(E1["loesungen"]) == E1["n_unterscheidbar"] and all(np.asarray(l["kameras_modell"]).shape == Cm.shape for l in E1["loesungen"]) and E1["lot"]["quelle"] in ("kameraebene", "kamerablick"),
          "1 Ergebnis traegt alle Loesungen mit Kamerastandorten + Lot")
    z1 = E1["zwischenstand"]; pruef(z1["an"] and z1["neu"].get("grob", 0) >= 1 and z1["neu"].get("fein", 0) >= 5 and not z1["treffer"], f"2 kalt: alles gerechnet und abgelegt {z1['neu']}")
    E2, log2 = lauf(p); au2 = open(au, "rb").read(); z2 = E2["zwischenstand"]
    pruef(not z2["neu"] and z2["treffer"].get("grob") == 1 and z2["treffer"].get("fein", 0) == z1["neu"]["fein"], f"2 warm: nur Treffer {z2['treffer']}, neu {z2['neu']}")
    os.environ["AUSR_ZWISCHEN"] = "0"; E3, log3 = lauf(p); au3 = open(au, "rb").read(); os.environ.pop("AUSR_ZWISCHEN")
    pruef(kern(E1) == kern(E2) == kern(E3), "2 Cache aendert das Ergebnis nicht: kalt == warm == ohne Cache (Transformation, Loesungsliste, Kameras, Bootstrap-Sigma bitgleich)")
    pruef(au1 == au2 == au3, "2 geschriebene SFM-AUSRICHTUNG-Datei bitgleich (kalt/warm/ohne Cache)")
    if E1["n_unterscheidbar"] > 1:
        E4, _ = lauf(p, "--loesung", "1"); z4 = E4["zwischenstand"]
        pruef(E4["rc"] == 0 and E4["loesung_nr"] == 1 and z4["treffer"].get("grob") == 1 and not z4["neu"].get("grob"), f"2 --loesung 1 aus dem warmen Cache ohne neue Grobsuche ({z4['neu']})")
    else:
        E4, _ = lauf(p, "--loesung", "1"); pruef(E4["rc"] == 5, "2 --loesung 1 bei nur einer Loesung: rc 5 (Loesung 0 bleibt)")
    # 3
    p5, _ = szene(os.path.join(tmp, "stand_b"), kamera_versatz=0.5)
    os.makedirs(os.path.join(os.path.dirname(p5["objekt"]), "messprotokoll"), exist_ok=True)
    shutil.copy(os.path.join(os.path.dirname(p["objekt"]), "messprotokoll", ".ausr_zwischen-testtor.pkl"), os.path.join(os.path.dirname(p5["objekt"]), "messprotokoll", ".ausr_zwischen-testtor.pkl"))
    E5, log5 = lauf(p5)
    pruef(not E5["zwischenstand"]["treffer"] and "anderer Datenstand" in log5, "3 andere Kameras (0,5 m) = anderer Datenstand -> fremder Zwischenstand wird nicht benutzt")
    q = open(os.path.join(T, "sfm_lod2_ausrichten.py"), encoding="utf-8").read()
    h_f, h_g = SA.code_abschnitt("fein"), SA.code_abschnitt("grob")
    kopie = os.path.join(tmp, "sa_kopie.py"); open(kopie, "w").write(q.replace("def gps_tor_urteil(", "def gps_tor_urteil(  ", 1))
    kopie2 = os.path.join(tmp, "sa_kopie2.py"); open(kopie2, "w").write(q.replace("loss=\"huber\", f_scale=sw / 3", "loss=\"huber\", f_scale=sw / 3.0", 1))
    pruef(SA.code_abschnitt("fein", kopie) == h_f and SA.code_abschnitt("grob", kopie) == h_g and SA.code_abschnitt("fein", kopie2) != h_f and SA.code_abschnitt("grob", kopie2) == h_g,
          "3 Code-Abschnitt: Aenderung am Veto aendert keinen Schluessel, Aenderung im Feinfit nur 'fein'")
    try: SA.code_abschnitt("gibtsnicht"); pruef(False, "3 fehlende Marke muss scheitern")
    except RuntimeError: pruef(True, "3 fehlende Marke -> Fehler (kein stiller Schluessel)")
    # 4
    A = rng0.uniform(-30, 30, (40, 3)); A[:, 2] = rng0.uniform(0, 3, 40); Rz = Rot.from_euler("z", 4.0, degrees=True).as_matrix()
    B = 1.0 / 1.05 * A @ Rz.T + [1.0, -0.5, 0.2]; ka = {f"eigen__{i}": a_ for i, a_ in enumerate(A.tolist())}; kb = {f"eigen__{i}.jpg": b_ for i, b_ in enumerate(B.tolist())}
    v = LPS.lage_vergleich(ka, kb)
    pruef(v["n"] == 40 and abs(v["drehung_grad"] - 4.0) < 0.01 and abs(v["massstab"] - 1.05) < 1e-3 and v["kippung_grad"] < 0.01 and v["rest_median_m"] < 1e-6,
          f"4 lage_vergleich misst Drehung {v['drehung_grad']} Grad, Massstab x{v['massstab']}, Kippung {v['kippung_grad']}")
    v2 = LPS.lage_vergleich(dict(list(ka.items())[:3]), kb); pruef("grund" in v2 and v2["n"] == 3, "4 zu wenig gemeinsame Fotos -> Grund")
    # 5 Pruefstand Ende zu Ende
    vorher = {f: os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.join(tmp, "stand")) for f in fs}
    vorher_n = sum(len(fs) for _, _, fs in os.walk(os.path.join(tmp, "stand")))
    kfg = dict(wurzel=os.path.join(tmp, "stand"), aus=os.path.join(tmp, "aus"), python_colmap=sys.executable, ausrichtung_args=ARGS_KLEIN,
               staende=dict(testtor=dict(ziel="testtor", objekt="modelle/testtor/objekt.json", kameras=p["kameras"], dicht=p["dicht"], fotos=p["fotos"], daten=os.path.join(tmp, "stand"),
                                         referenzen={"wahr": "wahr.json"}),
                            weg=dict(ziel="weg", daten=os.path.join(tmp, "gibtsnicht"))))
    json.dump(dict(kameras={f"eigen__IMG_{i:03d}": dict(standort=c.tolist()) for i, c in enumerate(Cm)}), open(os.path.join(tmp, "stand", "wahr.json"), "w"))
    kp = os.path.join(tmp, "konfig.json"); json.dump(kfg, open(kp, "w"))
    vorher_n += 1
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = LPS.main(["--konfig", kp, "--cpu"])
    aus = buf.getvalue(); erg = json.load(open(os.path.join(tmp, "aus", "pruefstand.json")))
    st = {s["stand"]: s for s in erg["staende"]}
    print("      " + aus.replace("\n", "\n      ").rstrip())
    pruef(rc == 0 and st["weg"]["status"] == "fehlt" and "FEHLT" in aus, "5 fehlender Stand -> 'fehlt' mit Liste, kein Absturz")
    l0 = (st["testtor"].get("laeufe") or [{}])[0]; ref = (l0.get("referenz") or {}).get("wahr") or {}
    pruef(st["testtor"]["status"] == "gelaufen" and ref.get("versatz_median_m", 9) < 0.3 and abs(ref.get("massstab", 9) - 1) < 0.02, f"5 Stand gelaufen, Lage gegen Referenz {ref}")
    tg = l0.get("tore") or {}
    pruef(set(("gps", "lage_proben", "grundriss", "wand_dicke", "teil_beleg")) <= set(tg) and tg["grundriss"]["rc"] == 0 and tg["gps"]["farbe"] == "rot" and tg["wand_dicke"]["farbe"] == "grau"
          and "grundriss GRUEN" in aus and "Ref wahr:" in aus, f"5 Tore mit Farbe + Wert (Grundriss {tg.get('grundriss', {}).get('wert')}, GPS {tg.get('gps', {}).get('wert')}: Fotos ohne GPS = nicht geprueft/rot)")
    pruef(os.path.isfile(os.path.join(tmp, "aus", "testtor", "objekt.json")) and os.path.isfile(os.path.join(tmp, "aus", "testtor", "audit", "wolke_grundriss.json"))
          and os.path.isfile(os.path.join(tmp, "aus", "testtor", "messprotokoll", "SFM-AUSRICHTUNG-testtor.json")), "5 Ausgaben im eigenen Ordner (objekt.json-Kopie, audit/, messprotokoll/)")
    nachher = {f: os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.join(tmp, "stand")) for f in fs}
    pruef(all(nachher.get(f) == t_ for f, t_ in vorher.items()) and len(nachher) == vorher_n, "5 Eingabeordner unberuehrt (keine Datei neu oder geaendert)")
    lo = st["testtor"].get("lot") or {}; pruef(lo.get("ausrichtung_gegen_bildachsen_grad") is not None and lo["ausrichtung_gegen_bildachsen_grad"] < 1.0, f"5 Lot-Gegenprobe {lo}")
    import lage_proben as LPR
    qg = open(os.path.join(T, "gesamtkette.py")).read()
    pruef("_LPR.tor_rc(" in qg and '__import__("lage_proben").lage_bestanden' in qg and LPR.tor_rc(dict(lage_proben=dict(ergebnis="bestaetigt")))[0] == 0
          and LPR.tor_rc({})[0] is None and not LPR.lage_bestanden(dict(gps=3, grundriss=0)), "5 Kette und Pruefstand nutzen dieselbe Tor-Regel")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print(f"LAGE-PRUEFSTAND-TEST: {'bestanden' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
