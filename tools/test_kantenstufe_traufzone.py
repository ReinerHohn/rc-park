#!/usr/bin/env python3
"""test_kantenstufe_traufzone.py - WAECHTER Traufzone der Kantenstufe (CPU, ohne Daten, ~30 s; 24.11.2026).
Verwandt/Vorlaeufer: tools/test_kantenstufe_kreis.py (Szene/Kameras/Stabilkarten-Muster), tools/kantenstufe.py (traufkanten/traufzone/traufzone_lauf/
suchfenster_trifft), tools/kanten_tiefe_sweep_flaeche.py (--ziel_flaeche).

Befund (Hoehen-Angleich 1122, modelle/FEATURE_FORMSITZ.md): ueber der LoD2-Wandoberkante (~36,9 m) fand die Kantenstufe KEINE triangulierten Fotokanten (40 von
53 199 Punkten ueber 36,5 m) - Traufkasten/Galerie/Dachfuss oben ohne zweite Quelle. Ursache (gemessen mit den 80 Kameras von 1122): 95 % der Traufstrahlen der
Kameras vor der Seite verfehlen den Messkoerper, ueber die Huellbox beginnt das Fenster 2,7-25 m vor der Traufe (steile Nahaufnahmen); nur 3,4 % der Traufpunkte
lagen in einem Suchfenster. Fix: zweiter Sweep um Schuerze + Decke je Wandoberkante (Hoehe aus Wolken-Dachfuss bzw. LoD2-Traufe + Rand), Punkte nur in der
Traufzone angehaengt (1122 Kopie, CPU: 40 -> 8 452 Kantenpunkte ueber 37 m).
 R  rote Probe (Turm 30 m, steiles Zeltdach 57 Grad wie 1122, 16 Nahaufnahmen 2-10 m vor der Wand): Traufpunkte im Suchfenster - alter Suchraum < 20 %,
    neuer (zusaetzlich Schuerze/Decke) >= 90 % (suchfenster_trifft = Fensterrechnung des Sweeps)
 N  voller Sweep (Kasten 10 m + Zeltdach, Kameras 10-36 m): Stirn-Ober- und Unterkante je >= 100 Punkte < 5 cm; >= 95 % der Punkte ueber der Wandoberkante
    < 20 cm an einer wahren Kante (Tiefenstreuung waagrechter Kanten); Bericht nennt die Traufzone; zwei Vormodelle -> bitgleiche sweep.npz; erster Lauf unveraendert, Zone nur angehaengt;
    --traufzone_rand 0 = alter Weg bitgleich zum ersten Lauf
 Z  traufzone(): Zone ohne Wolke = LoD2-Traufe + Rand; mit Wolke (Stirnpunkte) = Wolken-Dachfuss + Rand; Baum 3-4 m hoeher (Luecke >= vorn) hebt sie nicht;
    gestapelte Wandstuecke: nur die oberste Kante; fremde Wand vor der Kante deckelt die Wolke
rc 0 = bestanden.
"""
import sys, os, json, shutil, subprocess
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner
import kantenstufe as KS
H = os.path.dirname(os.path.abspath(__file__)); PY = sys.executable; F_ = 0; SK = 87.0
WAND_Y = -4.0; TK_Y = WAND_Y - 1.0


def pruef(ok, t):
    global F_
    print(("  ok     " if ok else "  FEHLER ") + t, flush=True); F_ += not ok


def stirn(z_w): return ((-5.6, TK_Y, z_w + 0.9), (5.6, TK_Y, z_w + 0.9)), ((-5.6, TK_Y, z_w + 0.5), (5.6, TK_Y, z_w + 0.5))


def kanten(z_w):
    so, su = stirn(z_w); f = z_w - 6.0
    return [((-3, WAND_Y, f), (-1, WAND_Y, f)), ((-3, WAND_Y, f + 2), (-1, WAND_Y, f + 2)), ((-3, WAND_Y, f), (-3, WAND_Y, f + 2)), ((-1, WAND_Y, f), (-1, WAND_Y, f + 2)),
            ((-5, WAND_Y, 0.5), (-5, WAND_Y, z_w)), ((5, WAND_Y, 0.5), (5, WAND_Y, z_w)), ((-5, WAND_Y, z_w), (5, WAND_Y, z_w)),
            so, su, ((-5.6, TK_Y, z_w + 0.5), (-5.6, TK_Y, z_w + 0.9)), ((5.6, TK_Y, z_w + 0.5), (5.6, TK_Y, z_w + 0.9))]


def messkoerper(z_w):
    P = np.array([[x, y, z] for x in (-5, 5) for y in (-4, 4) for z in (0, z_w)] + [[0, 0, z_w + 4.0 * 1.55]], float)   # Zeltdach 57 Grad (1122)
    return trimesh.convex.convex_hull(P)


def kamera(C, ziel, f=520.0, W=640, Hh=480):
    fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw); re_ = np.cross(fw, [0, 0, 1.0]); re_ /= np.linalg.norm(re_); un = np.cross(fw, re_)
    R = np.array([re_, un, fw]); return dict(R=R.tolist(), t=(-R @ C).tolist(), f_px_original=f, cx=W / 2, cy=Hh / 2, bild_b=W, bild_h=Hh, k=[0.0])


def karte(k, KANTEN):
    R = np.array(k["R"]); t = np.array(k["t"]); im = np.zeros((int(k["bild_h"]), int(k["bild_b"])), np.uint8)
    for A, B in KANTEN:
        P = np.linspace(A, B, 400) @ R.T + t; u = k["f_px_original"] * P[:, 0] / P[:, 2] + k["cx"]; v = k["f_px_original"] * P[:, 1] / P[:, 2] + k["cy"]
        for i in range(len(P) - 1): cv2.line(im, (int(round(u[i])), int(round(v[i]))), (int(round(u[i + 1])), int(round(v[i + 1]))), 255, 1)
    return im


def an_strecke(P, A, B):
    A = np.asarray(A, float); B = np.asarray(B, float); d = B - A; t = np.clip(((P - A) @ d) / (d @ d), 0, 1); return np.linalg.norm(P - (A + t[:, None] * d), axis=1)


def stl(m, p):
    m = m.copy(); m.apply_scale(1000.0 / SK); m.export(p); return p


def teil_z():
    """Z: traufzone()/traufkanten() direkt (ohne Sweep)."""
    z_w = 10.0; S = messkoerper(z_w); m, Z, txt = KS.traufzone(S, 2.0, 0.5, 1.0, None); so, su = stirn(z_w)
    vz = [z for z in Z if abs(z["n"][1] + 1) < 0.05]
    pruef(len(Z) == 4 and len(vz) == 1 and abs(vz[0]["z_oben"] - (z_w + 1.0)) < 0.02, f"Z ohne Wolke: {len(Z)} Wandoberkanten, Vorderwand Zone bis z {vz[0]['z_oben'] if vz else None} (Soll LoD2-Traufe + 1 = {z_w + 1:.1f})")
    rng = np.random.default_rng(0); n_ = 4000
    st = np.c_[rng.uniform(-5, 5, n_), np.full(n_, TK_Y) + rng.normal(0, 0.02, n_), rng.uniform(su[0][2], so[0][2], n_)]
    un = np.c_[rng.uniform(-5, 5, n_), rng.uniform(TK_Y, WAND_Y, n_), np.full(n_, su[0][2]) + rng.normal(0, 0.02, n_)]
    baum = np.c_[rng.uniform(-3, 3, n_), rng.uniform(-5.5, -4.5, n_), rng.uniform(so[0][2] + 3.0, so[0][2] + 4.0, n_)]
    for name, W in (("Stirn", np.vstack([st, un])), ("Stirn + Baum 3-4 m darueber", np.vstack([st, un, baum]))):
        _, Z2, _ = KS.traufzone(S, 2.0, 0.5, 1.0, W); v = [z for z in Z2 if abs(z["n"][1] + 1) < 0.05][0]; soll = so[0][2] + 1.0
        pruef(abs(v["z_oben"] - soll) <= 0.08, f"Z Wolke {name}: Zone bis z {v['z_oben']} (Soll Wolken-Dachfuss + 1 = {soll:.2f}), Dachfuss {v['wolke_dachfuss']}")
    q1 = trimesh.Trimesh([[-5, -4, 0], [5, -4, 0], [5, -4, 5], [-5, -4, 5]], [[0, 1, 2], [0, 2, 3]]); q2 = trimesh.Trimesh([[-5, -4, 5], [5, -4, 5], [5, -4, 10], [-5, -4, 10]], [[0, 1, 2], [0, 2, 3]])
    K2 = KS.traufkanten(trimesh.util.concatenate([q1, q2]))
    pruef(len(K2) >= 1 and all(abs(k["z"] - 10) < 1e-6 for k in K2), f"Z gestapelte Wand: Oberkanten bei z {[round(k['z'], 2) for k in K2]} (nur 10)")
    anbau = trimesh.creation.box(bounds=[(-2, -8, 0), (2, -4, 4)]); turm_vorn = trimesh.Trimesh([[-3, -9.0, 0], [3, -9.0, 0], [3, -9.0, 20], [-3, -9.0, 20]], [[0, 1, 2], [0, 2, 3]])
    S3 = trimesh.util.concatenate([anbau, turm_vorn]); W3 = np.c_[rng.uniform(-1.5, 1.5, n_), np.full(n_, -9.0), rng.uniform(4, 20, n_)]
    _, Z3, _ = KS.traufzone(S3, 2.0, 0.5, 1.0, W3); v3 = [z for z in Z3 if abs(z["n"][1] + 1) < 0.05 and z["z_e"] < 5]
    pruef(bool(v3) and v3[0]["z_oben"] <= 4 + 1.0 + 0.02, f"Z Guard: fremde Wand vor der Anbau-Kante -> Zone bis z {v3[0]['z_oben'] if v3 else None} (LoD2 + Rand, nicht Wolke bis 20 m)")


def teil_r():
    """R: Suchfenster-Deckung der Traufpunkte, Turm 30 m mit Nahaufnahmen (Geometrie wie 1122)."""
    z_w = 30.0; S = messkoerper(z_w); so, su = stirn(z_w); m, Z, _ = KS.traufzone(S, 2.0, 0.5, 1.0, None); v2 = max([2.0] + [z["z_oben"] - z["z_e"] for z in Z])
    Q = np.vstack([np.linspace(so[0], so[1], 25), np.linspace(su[0], su[1], 25)]); alt = neu = tot = 0
    for y in (-6.0, -8.0, -11.0, -14.0):                                          # Nahaufnahmen 2-10 m vor der Wand (Traufe steiler als das Dach; ab ~15 m trifft das Dach)
        for x in (-6, -2, 2, 6):
            C = np.array([x, y, 1.6]); o = KS.suchfenster_trifft(S, C, Q, 2.0, 0.5, True); n = o | KS.suchfenster_trifft(m, C, Q, v2, 0.5, False)
            tot += len(Q); alt += int(o.sum()); neu += int(n.sum())
    pruef(alt < 0.2 * tot, f"R rote Probe alter Suchraum (Messkoerper + Huelle): {alt} von {tot} Traufpunkt-Strahlen im Suchfenster ({100 * alt / tot:.0f} %, < 20 %)")
    pruef(neu >= 0.9 * tot, f"R neuer Suchraum (+ Schuerze/Decke): {neu} von {tot} im Suchfenster ({100 * neu / tot:.0f} %, >= 90 %)")


def main():
    tmp = temp_ordner("traufzone_"); bd = os.path.join(tmp, "bilder"); os.makedirs(bd)
    try:
        teil_z(); teil_r()
        z_w = 10.0; KANTEN = kanten(z_w); so, su = stirn(z_w); kams = {}; i = 0
        for y in (-14.0, -20.0, -28.0, -40.0):
            for x, z in ((-6, 1.5), (-2, 7.0), (2, 1.5), (6, 4.0)):
                C = np.array([x + 0.3 * (i % 3), y - 0.4 * (i % 2), z]); kams[f"k{i:02d}"] = kamera(C, (0, WAND_Y, 8.0)); i += 1
        AU = os.path.join(tmp, "ausrichtung.json"); json.dump(dict(kameras=kams), open(AU, "w"))
        stabil = {n: karte(k, KANTEN) for n, k in kams.items()}
        for n in kams: cv2.imwrite(os.path.join(bd, n + ".jpg"), np.zeros((8, 8), np.uint8))
        mk = stl(messkoerper(z_w), os.path.join(tmp, "messkoerper.stl")); m1 = stl(messkoerper(z_w), os.path.join(tmp, "vm1.stl"))
        m2 = stl(trimesh.util.concatenate([messkoerper(z_w), trimesh.creation.box(bounds=[(-5, -4.6, z_w), (5, -4.0, z_w + 0.3)])]), os.path.join(tmp, "vm2.stl"))

        def lauf(name, vm, *extra):
            d = os.path.join(tmp, name); os.makedirs(os.path.join(d, "stabil"))
            for n, im in stabil.items(): cv2.imwrite(os.path.join(d, "stabil", n + ".png"), im)
            oj = os.path.join(tmp, f"objekt_{name}.json"); json.dump(dict(name="traufzone", stl=vm, stl_massstab=SK), open(oj, "w"))
            r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(H, "kantenstufe.py"), oj, "--ausrichtung", AU, "--bilder", bd, "--aus", d, "--geraet", "cpu",
                                "--stabil_vorhanden", "--refs", "16", "--max_fotos", "16", "--messkoerper", mk] + list(extra), capture_output=True, text=True,
                               env=dict(os.environ, OMP_NUM_THREADS=os.environ.get("OMP_NUM_THREADS", "4")))   # CPU-Torch nicht ueberbuchen (parallele Agenten)
            sp = os.path.join(d, "sweep.npz"); Z = np.load(sp) if os.path.exists(sp) else None
            if Z is None: print((r.stdout + r.stderr)[-1500:])
            B = json.load(open(os.path.join(d, "kanten_bericht.json"))) if os.path.exists(os.path.join(d, "kanten_bericht.json")) else {}
            return (Z["P"].astype(float) if Z is not None else np.zeros((0, 3))), B, r

        Pa, Ba, ra = lauf("alt", m1, "--traufzone_rand", "0")
        P1, B1, r1 = lauf("neu", m1); P2, _, _ = lauf("neu_v2", m2)
        print("  (neu: " + str(B1.get("traufzone", {}).get("text")) + ")")
        da = np.minimum(an_strecke(Pa, *so), an_strecke(Pa, *su)) if len(Pa) else np.ones(1)
        do = an_strecke(P1, *so); du = an_strecke(P1, *su)
        pruef(int((do < 0.05).sum()) >= 100 and int((du < 0.05).sum()) >= 100, f"N Stirn-Oberkante {int((do < 0.05).sum())} / Unterkante {int((du < 0.05).sum())} Punkte < 5 cm (je >= 100; alter Suchraum zusammen {int((da < 0.05).sum())})")
        ob = P1[:, 2] > z_w + 0.1; dall = np.min([an_strecke(P1[ob], *k) for k in KANTEN], 0) if ob.any() else np.ones(1)
        pruef(ob.sum() > 0 and float((dall < 0.20).mean()) >= 0.95, f"N {int(ob.sum())} Punkte ueber der Wandoberkante, {float((dall < 0.20).mean()) * 100:.0f} % < 20 cm an einer wahren Kante (>= 95 %; "
              f"< 10 cm {float((dall < 0.10).mean()) * 100:.0f} % - waagrechte Traufkanten streuen in der Tiefe 0,1-0,2 m, keine Fremdstrukturen)")
        tz = B1.get("traufzone", {})
        pruef(tz.get("punkte", 0) > 0 and tz.get("zonen_anzahl") == 4 and "Wandoberkanten" in tz.get("text", ""), f"N Bericht: Traufzone {tz.get('zonen_anzahl')} Zonen, {tz.get('punkte')} Punkte angehaengt")
        pruef(P1.shape == P2.shape and np.array_equal(P1, P2), "N zwei Vormodelle -> bitgleiche sweep.npz (Suchraum modellfrei)")
        pruef(len(P1) > len(Pa) and np.array_equal(P1[:len(Pa)], Pa) and "traufzone" not in Ba, f"N erster Lauf unveraendert, Traufzone nur angehaengt ({len(Pa)} -> {len(P1)}); --traufzone_rand 0 = alter Weg")
    finally: shutil.rmtree(tmp, ignore_errors=True)
    print("BESTANDEN" if F_ == 0 else f"{F_} FEHLER"); return 1 if F_ else 0


if __name__ == "__main__":
    sys.exit(main())
