#!/usr/bin/env python3
"""Test tools/teil_gelaende_tor.py + Einbindung in tools/sfm_seiten_modelle.py (24.11.2026, 1122z: Ost-Teil 6,4 m im Boden, kein Tor fand es).
Synthetische Szene in Metern (Strasse 40 x 40 m, Turm 10 x 10 x 20 m); Teil A im eigenen, gekippten System (0,5 m je Einheit), Teil B = eine Turmseite + Strasse davor im
eigenen System (Aehnlichkeit). Faelle:
  1. pruefen(): richtige Lage -> bestanden; B 6,4 m zu tief -> ABGELEHNT mit Bodenversatz ~6,4 m; ohne Massstab / ohne gemeinsame Strasse -> nicht pruefbar;
  2. Werkzeug (CLI) je Bindungsweg (klappung, eckmodell, gps, gps+querspur, gps+waende, gps+lod2): verschobenes Teil rc 3 + Logzeile mit Teil und Weg; richtiges rc 0;
     ohne GPS-Ergebnis (kein Massstab) rc 2;
  3. sfm_seiten_modelle.gelaende_stufe: Ergebnis + Wiederverwendung (gleiche Matrix = kein zweiter Aufruf, andere Matrix = neu);
  4. Einbau: EIN Aufruf im gemeinsamen Block 'rc == 0 and B_nach_A' vor modelle_zusammen (also fuer jeden Weg), Werkzeug im Code-Stand der Nachstufe.
Python: /media/oem/scan/venv-colmap/bin/python -I (scipy; pycolmap nur ueber sfm_seiten_modelle-Import)."""
import os, sys, json, tempfile, subprocess, re
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import teil_gelaende_tor as TG

F = 0


def pruef(name, ok, info=""):
    global F
    print(("    ok " if ok else "    FEHLER ") + name + (f" ({str(info)[:400]})" if info and not ok else "")); F += 0 if ok else 1


def drehung(achse, grad):
    a = np.asarray(achse, float); a /= np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]]); w = np.radians(grad)
    return np.eye(3) + np.sin(w) * K + (1 - np.cos(w)) * K @ K


rng = np.random.default_rng(7)
def strasse(x0, x1, y0, y1, dichte=25):
    n = int((x1 - x0) * (y1 - y0) * dichte); return np.c_[rng.uniform(x0, x1, n), rng.uniform(y0, y1, n), rng.normal(0, 0.03, n)]
def wand(p0, p1, h=20.0, dichte=25):
    L = np.linalg.norm(np.subtract(p1, p0)); n = int(L * h * dichte); t = rng.uniform(0, 1, n); z = rng.uniform(0, h, n)
    P = np.asarray(p0, float)[None] + t[:, None] * (np.subtract(p1, p0))[None]; return np.c_[P + rng.normal(0, 0.02, (n, 2)), z]

ecken = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
SA = np.vstack([strasse(-20, 20, -20, 20)] + [wand(ecken[i], ecken[(i + 1) % 4]) for i in range(4)])   # Teil A sieht alles (Meter)
SA = SA[~((np.abs(SA[:, 0]) < 4.9) & (np.abs(SA[:, 1]) < 4.9) & (SA[:, 2] < 0.2))]                   # keine Strasse im Turm
SB = np.vstack([strasse(5.5, 20, -15, 15), wand((5, -5), (5, 5))])                                    # Teil B: Ostseite + Strasse davor (Meter)
m_a = 0.5; Ra = drehung([1, 0.3, 0], 4.0); lot_a = Ra @ [0, 0, 1.0]
zu_A = lambda X: (X @ Ra.T) / m_a                                                                        # Meter -> A-System
sB = 1.7; Rb = drehung([0.2, 1, 0.4], 35.0); tb = np.array([3.0, -2.0, 1.0])
zu_B = lambda X: (X @ Rb.T) * sB + tb                                                                    # Meter -> B-System
DA = zu_A(SA); DB = zu_B(SB)
def matrix(dz_m=0.0):
    """B -> A: B-System -> Meter (-dz_m nach unten) -> A-System."""
    Mb = np.eye(4); Mb[:3, :3] = Rb * sB; Mb[:3, 3] = tb; Ma = np.eye(4); Ma[:3, :3] = Ra / m_a; V = np.eye(4); V[2, 3] = -dz_m
    return Ma @ V @ np.linalg.inv(Mb)

# ---------- 1 pruefen()
r0 = TG.pruefen(DA, DB, matrix(0.0), lot_a, m_a, teil=1, weg="gps")
pruef("1 richtige Lage bestanden", r0["rc"] == 0 and r0["ok"] is True and r0["anteil_b"] < 0.01, r0)
r1 = TG.pruefen(DA, DB, matrix(6.4), lot_a, m_a, teil=1, weg="gps")
pruef("1 B 6,4 m zu tief ABGELEHNT", r1["rc"] == 3 and r1["ok"] is False and r1["anteil_b"] > 0.5, r1)
pruef("1 Bodenversatz ~ +6,4 m gemeldet", r1["boden_versatz_m"] is not None and abs(r1["boden_versatz_m"] - 6.4) < 0.3 and "zu tief" in r1["meldung"], r1.get("meldung"))
r2 = TG.pruefen(DA, DB, matrix(0.0), lot_a, None, teil=1, weg="klappung")
pruef("1 ohne Massstab nicht pruefbar (rc 2)", r2["rc"] == 2 and r2["ok"] is None and "Massstab" in r2["meldung"], r2)
far = matrix(0.0); far[:3, 3] += Ra @ [400.0, 0, 0] / m_a
r3 = TG.pruefen(DA, DB, far, lot_a, m_a, teil=1, weg="gps")
pruef("1 ohne gemeinsame Strasse nicht pruefbar (rc 2)", r3["rc"] == 2, r3)
pruef("1 Massstab aus GPS-Rahmen", TG.massstab_aus_gps(dict(rahmen_a=dict(massstab=0.5))) == 0.5 and TG.massstab_aus_gps({}) is None and TG.massstab_aus_gps(dict(rahmen_a=dict(massstab="x"))) is None)

# ---------- 2 CLI je Weg
def ply(p, X):
    d = np.zeros(len(X), np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 3)])); d["p"] = X
    k = ("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\n"
         "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(X)).encode()
    open(p, "wb").write(k + d.tobytes())

with tempfile.TemporaryDirectory() as d:
    fa, fb, gj = os.path.join(d, "a.ply"), os.path.join(d, "b.ply"), os.path.join(d, "gps.json")
    ply(fa, DA); ply(fb, DB); json.dump(dict(rahmen_a=dict(massstab=m_a)), open(gj, "w"))
    def cli(M, weg, gps=True):
        mj = os.path.join(d, "m.json"); aus = os.path.join(d, "g.json"); json.dump(dict(B_nach_A=M.tolist()), open(mj, "w"))
        r = subprocess.run([sys.executable, "-I", os.path.join(T, "teil_gelaende_tor.py"), fa, fb, "--matrix", mj, "--aus", aus, "--teil", "1", "--weg", weg] + (["--gps", gj] if gps else []),
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr, (json.load(open(aus)) if os.path.isfile(aus) else {})
    for weg in ("klappung", "eckmodell", "gps", "gps+querspur", "gps+waende", "gps+lod2"):
        rc, out, j = cli(matrix(6.4), weg)
        pruef(f"2 Weg {weg}: verschobenes Teil rc 3 + Logzeile", rc == 3 and f"GELAENDE-TOR Teil 1 (Weg {weg}): ABGELEHNT" in out, out[-400:])
    rc, out, j = cli(matrix(0.0), "gps+waende"); pruef("2 richtige Lage rc 0 (Lot aus den Waenden geschaerft)", rc == 0 and "bestanden" in out and "Wandnormalen" in j.get("lot_quelle", ""), out[-300:])
    rc, out, j = cli(matrix(6.4), "klappung", gps=False); pruef("2 ohne GPS-Ergebnis rc 2 (nicht pruefbar, gemeldet)", rc == 2 and "NICHT PRUEFBAR" in out, out[-300:])

    # ---------- 3 gelaende_stufe (sfm_seiten_modelle)
    try:
        import sfm_seiten_modelle as SM
    except Exception as ex:
        SM = None; pruef("3 sfm_seiten_modelle importierbar", False, f"{type(ex).__name__}: {ex}")
    if SM is not None:
        ma = os.path.join(d, "modell_a"); os.makedirs(ma); open(os.path.join(ma, "images.bin"), "wb").write(b"x")
        A, B = dict(teil=0, modell=ma), dict(teil=1)
        n = [0]; echt = SM.LAUF
        def zaehl(cmd, log=None): n[0] += 1; return echt(cmd, log)
        SM.LAUF = zaehl
        try:
            g1 = SM.gelaende_stufe(os.path.join(d, "v_gelaende"), A, B, fa, fb, matrix(6.4), "gps+lod2", gj)
            pruef("3 gelaende_stufe: verschoben rc 3 mit Meldung", g1["rc"] == 3 and "ABGELEHNT" in g1.get("meldung", "") and n[0] == 1, g1)
            g2 = SM.gelaende_stufe(os.path.join(d, "v_gelaende"), A, B, fa, fb, matrix(6.4), "gps+lod2", gj)
            pruef("3 gleiche Eingabe wiederverwendet", n[0] == 1 and g2["rc"] == 3, n[0])
            g3 = SM.gelaende_stufe(os.path.join(d, "v_gelaende"), A, B, fa, fb, matrix(0.0), "gps+lod2", gj)
            pruef("3 neue Matrix -> neu geprueft, bestanden", n[0] == 2 and g3["rc"] == 0, (n[0], g3.get("meldung")))
        finally: SM.LAUF = echt
        pruef("4 Werkzeug im Code-Stand der Nachstufe", "teil_gelaende_tor.py" in SM.NACHSTUFE)

# ---------- 4 Einbau im gemeinsamen Block
q = open(os.path.join(T, "sfm_seiten_modelle.py")).read()
i_block = q.find('        if rc == 0 and "B_nach_A" in v:\n'); i_tor = q.find("gelaende_stufe(vo", i_block); i_zus = q.find("modelle_zusammen(", i_block)
pruef("4 EIN Aufruf im gemeinsamen Block vor modelle_zusammen", i_block > 0 and i_block < i_tor < i_zus and q.count("gelaende_stufe(vo") == 1, (i_block, i_tor, i_zus))
pruef("4 Ablehnung nimmt das Teil heraus (nicht_vereint + continue)", re.search(r'rc"\) == 3 and GELAENDE_TOR != "hinweis":\n\s+M_\.append\(.*WEGGELASSEN.*nicht_vereint"\]\.append\(B\["teil"\]\); continue', q) is not None)
print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
