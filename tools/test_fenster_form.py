#!/usr/bin/env python3
"""test_fenster_form.py - fester synthetischer Test: FENSTERFORM aus Bildkanten + Einzelfotos, Form-Tor, hand_vergleich prueft die Form, Druckmindesttiefe (21.11.2026 spaet).

Befund, nachgestellt mit eigenen Massen (Schwabentor f00, Lauf 1121s): zwei Rundbogenfenster in Rundbogennischen; der Erkenner hat nur fuer die RECHTE Nische einen
Kasten, das linke Fenster steht als Rechteck in der Liste (fenster_tiefe_tor). Vorher: links Rechteck ohne Nische, hand_vergleich 'PASST' (nur Hoehe/Anzahl).
Erwartung:
  T1 nischen_fenster: 2 Eintraege, beide Fenster 'rund' mit Nische 'rund' (links ueber die Geschwister-Suchzone), Form aus >= 3 Einzelfotos (form_quelle);
     ein Einzelfoto ohne Kanten stimmt nicht mit.
  T2 fenster_form_tor: alte Liste (links Rechteck) -> FALSCH, rc 2; neue Liste -> kein FALSCH, rc 0.
  T3 hand_vergleich 'rundbogenfenster': alte Liste -> FALSCH wegen form; neue Liste -> form PASST.
  T4 bauteile.fenster_aus_json: Nische 0,03 m wird auf Druckmindestmass (MINMM 0,8 x SCALE 87 = 0,0696 m) vertieft, Beleg nennt ANNAHME; DURCH-Eintrag
     hat das 7. Feld (Laibungstiefe), aushoehlen() kommt damit klar.
< 20 s, nur CPU.
"""
import sys, os, json, tempfile, shutil, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import nischen_fenster as NF

U0, U1, Z0, Z1, C = -3.6, 3.6, 22.3, 26.0, 0.01
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def bild(seed=7, du=0.0, dz=0.0, kontrast=1.0, leer=False):
    """Wandbild mit zwei Rundbogenfenstern in Rundbogennischen (links Mitte -2,0, rechts +2,0); du/dz = Lagefehler eines Einzelfotos."""
    rng = np.random.default_rng(seed); H_, W_ = int((Z1 - Z0) / C), int((U1 - U0) / C)
    g = np.full((H_, W_), 180.0) + rng.normal(0, 2.0, (H_, W_))
    if leer: return np.clip(g, 1, 255).astype(np.uint8)
    uu = U0 + C * (np.arange(W_) + 0.5) - du; zz = Z1 - C * (np.arange(H_) + 0.5) - dz; UU, ZZ = np.meshgrid(uu, zz)

    def rund(m, b, zs, zk):
        a = b / 2; return (np.abs(UU - m) <= a) & (ZZ >= zs) & ((ZZ <= zk) | ((UU - m) ** 2 + (ZZ - zk) ** 2 <= a * a))
    for m in (-2.0, 2.0):
        g[rund(m, 2.0, 23.0, 24.4)] = 180 - 18 * kontrast        # Nische (schwach)
        g[rund(m, 0.6, 23.0, 24.5)] = 180 - 120 * kontrast       # Fenster (dunkel)
    return np.clip(g, 1, 255).astype(np.uint8)


def tiefe():
    c = 0.04; H_, W_ = int((Z1 - Z0) / c), int((U1 - U0) / c)
    uu = U0 + c * (np.arange(W_) + 0.5); zz = Z1 - c * (np.arange(H_) + 0.5); UU, ZZ = np.meshgrid(uu, zz); w = np.zeros((H_, W_), np.float32)
    for m in (-2.0, 2.0):
        w[(np.abs(UU - m) < 1.0) & (ZZ > 23.0) & ((ZZ < 24.4) | ((UU - m) ** 2 + (ZZ - 24.4) ** 2 < 1.0))] = -0.15
        w[(np.abs(UU - m) < 0.3) & (ZZ > 23.0) & ((ZZ < 24.5) | ((UU - m) ** 2 + (ZZ - 24.5) ** 2 < 0.09))] = -0.35
    return dict(w=w, gut=np.ones_like(w, bool), sicher=np.ones_like(w), u0=U0, z1=Z1, zelle=c)


def main():
    import cv2
    d = tempfile.mkdtemp(prefix="test_fform_"); fo = os.path.join(d, "fassade"); ff = os.path.join(d, "fassade_fein"); au = os.path.join(d, "audit"); ez = os.path.join(ff, "ortho_f00_einzeln")
    for x in (fo, ff, au, ez): os.makedirs(x)
    cv2.imwrite(os.path.join(ff, "ortho_f00.png"), bild()); np.savez(os.path.join(fo, "tiefe_f00.npz"), **tiefe())
    for i, (du, dz) in enumerate(((0.02, 0.0), (-0.03, 0.01), (0.01, -0.02))): cv2.imwrite(os.path.join(ez, f"foto{i}.png"), bild(seed=10 + i, du=du, dz=dz, kontrast=0.8))
    cv2.imwrite(os.path.join(ez, "foto_leer.png"), bild(seed=99, leer=True))
    json.dump(dict(fassaden=[dict(id="f00", raster=dict(u0=U0, z1=Z1, nu=720, nz=370, zelle=C))]), open(os.path.join(ff, "fassaden.json"), "w"))
    el = [dict(klasse="bogen", u0=0.95, u1=3.08, z0=22.93, z1=25.45, stimmen=4), dict(klasse="fenster", u0=1.72, u1=2.33, z0=23.06, z1=24.75, stimmen=6),   # rechts: Paar
          dict(klasse="fenster", u0=-2.28, u1=-1.66, z0=23.08, z1=24.72, stimmen=5)]                                                                         # links: nur Fenster
    json.dump(dict(fassaden=dict(f00=dict(elemente=el))), open(os.path.join(fo, "elemente.json"), "w"))
    alt = dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fotos=[], fenster=[dict(u0=-2.30, u1=-1.66, z0=23.21, z1=24.81, teiler=[], kaempfer=None, scheiben=1, stimmen_min=7, sprossen=[])]))
    fa = os.path.join(au, "fenster_auto.json"); json.dump(alt, open(fa, "w"))
    # --- T1
    sys.argv = ["nischen_fenster.py", fa, fo, ff]; rc = NF.main(); pruef(rc == 0, f"T1 nischen_fenster rc {rc}")
    J = sorted(json.load(open(fa))["f00"]["fenster"], key=lambda q: q["u0"])
    pruef(len(J) == 2 and all(q.get("nische") for q in J), f"T1 2 Fenster mit Nische (ist {len(J)}, Nischen {[bool(q.get('nische')) for q in J]})")
    for q, m in zip(J, (-2.0, 2.0)):
        N = q.get("nische") or {}; fq = q.get("form_quelle", "")
        pruef((q.get("bogen") or {}).get("form") == "rund" and (N.get("bogen") or {}).get("form") == "rund", f"T1 Mitte {m:+.0f}: Fenster {(q.get('bogen') or {}).get('form')}, Nische {(N.get('bogen') or {}).get('form')} (soll rund/rund)")
        pruef(abs((q["u0"] + q["u1"]) / 2 - m) <= 0.04 and abs(q["z1"] - 24.8) <= 0.05 and abs(N.get("u1", 0) - N.get("u0", 0) - 2.0) <= 0.06, f"T1 Mitte {m:+.0f}: Lage u {q['u0']:.2f}..{q['u1']:.2f} Scheitel {q['z1']:.2f}, Nische {N.get('u1', 0) - N.get('u0', 0):.2f} m")
        n_ = int(fq.split()[0]) if fq[:1].isdigit() else 0
        pruef(n_ >= 3 and "von 3" in fq, f"T1 Mitte {m:+.0f}: Formfamilie aus Einzelfotos '{fq}' (>= 3, leeres Foto ohne Stimme)")
        pruef(abs(N.get("tiefe", 0) - 0.15) <= 0.05, f"T1 Mitte {m:+.0f}: Nischentiefe {N.get('tiefe')} (0,15)")
    links = next((r for r in json.load(open(os.path.join(au, "nischen_fenster.json")))["f00"] if r.get("art") == "einzeln"), {})
    pruef(bool(links.get("geschwister")), "T1 links ueber Geschwister-Suchzone vermessen")
    # --- T2
    neu = json.load(open(fa)); fa_alt = os.path.join(au, "alt.json"); json.dump(alt, open(fa_alt, "w"))
    T = os.path.join(H, "fenster_form_tor.py")
    r1 = subprocess.run([sys.executable, "-I", T, fa_alt, ff, "--aus", os.path.join(au, "tor_alt.json")], capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, "-I", T, fa, ff], capture_output=True, text=True)
    pruef(r1.returncode == 2 and "FALSCH" in r1.stdout, f"T2 Form-Tor alt (Rechteck) -> FALSCH rc {r1.returncode}: {r1.stdout.strip().splitlines()[:1]} {r1.stderr[-200:]}")
    pruef(r2.returncode == 0, f"T2 Form-Tor neu -> rc {r2.returncode}: {r2.stdout.strip()[-200:]} {r2.stderr[-200:]}")
    # --- T3 hand_vergleich (Referenz nur mit Massen; Form kommt aus dem BAUTEILNAMEN)
    ob = os.path.join(d, "objekt.json"); json.dump({}, open(ob, "w"))
    json.dump(dict(quelle="test", bauteile=[dict(bauteil="rundbogenfenster", masse=dict(anzahl=2, sohlbank_z=23.0, nische_breite=2.0), toleranz_m=0.4)]), open(os.path.join(d, "referenz_hand.json"), "w"))
    HV = os.path.join(H, "hand_vergleich.py")
    tor_neu = os.path.join(au, "fenster_form_tor.json"); shutil.copy(tor_neu, os.path.join(au, "tor_neu.json"))
    alt2 = json.loads(json.dumps(alt)); alt2["f00"]["fenster"].append(sorted(neu["f00"]["fenster"], key=lambda q: q["u0"])[1])   # links Rechteck (alt), rechts Bogen
    json.dump(alt2, open(fa, "w")); subprocess.run([sys.executable, "-I", T, fa, ff], capture_output=True, text=True)       # Tor auf genau dieser Liste
    subprocess.run([sys.executable, "-I", HV, ob], capture_output=True, text=True); e1 = json.load(open(os.path.join(au, "hand_vergleich.json")))["bauteile"][0]
    json.dump(neu, open(fa, "w")); shutil.copy(os.path.join(au, "tor_neu.json"), tor_neu)
    subprocess.run([sys.executable, "-I", HV, ob], capture_output=True, text=True); e2 = json.load(open(os.path.join(au, "hand_vergleich.json")))["bauteile"][0]
    pruef(e1["urteil"] == "FALSCH" and not e1["masse"].get("form", {}).get("ok", True), f"T3 hand_vergleich alt: {e1['urteil']} form {e1['masse'].get('form')}")
    pruef(e2["urteil"] == "PASST" and e2["masse"].get("form", {}).get("ok"), f"T3 hand_vergleich neu: {e2['urteil']} form {e2['masse'].get('form')}")
    # --- T4 Bau: Druckmindesttiefe + DURCH 7. Feld
    os.environ["SCALE"] = "87"; os.environ["MINMM"] = "0.8"
    import bauteile as BT
    from manifold3d import Manifold as M
    q = dict(u0=-0.3, u1=0.3, z0=1.0, z1=2.0, stimmen_min=5, bogen=dict(form="rund", kaempfer=1.7, scheitel=2.0), tiefe=0.12, tiefe_quelle="ANNAHME 0.12 m (test)",
             nische=dict(u0=-1.0, u1=1.0, z0=1.0, z1=3.0, bogen=dict(form="rund", kaempfer=2.0, scheitel=3.0), tiefe=0.03))
    fj = os.path.join(au, "bau.json"); json.dump(dict(f00=dict(o=[0.0, 0.0], d=[1, 0], n=[0, -1], fenster=[q])), open(fj, "w"))
    k = M.cube((6.0, 4.0, 5.0)).translate((-3.0, 0.0, 0.0))   # Wand y = 0, aussen -y, u = x
    BT.DURCH.clear(); k2, bel = BT.fenster_aus_json(k, fj)
    dmin = 0.8 * 87 / 1000.0; nfl = NF_fl(q["nische"]); ffl = NF_fl(q); dv = k.volume() - k2.volume(); erw = dmin * nfl + 0.12 * ffl
    pruef(abs(dv - erw) <= 0.05 * erw, f"T4 Nische 0,03 -> {dmin:.3f} m: Abzug {dv:.4f} m3 (erwartet {erw:.4f}, mit 0,03 waere {0.03 * nfl + 0.12 * ffl:.4f})")
    pruef(bool(bel) and "ANNAHME" in bel[0].get("annahmen", "") and "rund in Nische" in json.dumps(bel[0].get("formen")), f"T4 Beleg: {bel[0].get('annahmen', '')[:90]} | {bel[0].get('formen')}")
    pruef(len(BT.DURCH) == 1 and len(BT.DURCH[0]) == 7 and abs(BT.DURCH[0][6]["tiefe"] - (dmin + 0.12)) < 1e-6, "T4 DURCH mit Laibungstiefe (7. Feld)")
    try: k3, n_off, _ = BT.aushoehlen(k2, d=0.1, min_m3=0.1); pruef(n_off == 1, f"T4 aushoehlen mit 7er-DURCH: {n_off} Fenster offen")
    except Exception as ex: pruef(False, f"T4 aushoehlen: {ex}")
    shutil.rmtree(d, ignore_errors=True)
    print(f"test_fenster_form: {F} Fehler"); return 1 if F else 0


def NF_fl(o):
    b = o["bogen"]; P = NF.umriss(b["form"], o["u0"], o["u1"], o["z0"], b["kaempfer"], b["scheitel"], schritt=0.005)
    x, y = P[:, 0], P[:, 1]; return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


if __name__ == "__main__": sys.exit(main())
