#!/usr/bin/env python3
"""test_kantenstufe_kreis.py - WAECHTER gegen den Kreis in der KERNMETHODE (CPU, ohne Daten, ~1 min; 22.11.2026).

Befund: tools/kantenstufe.py rief den Kanten-Tiefen-Sweep mit `--flaeche <STL des Vormodells> --band 0.5` auf: Kanten wurden nur +-0,5 m um das
VORIGE Modell gesucht (Vordach/Erker/Traufe weiter davor nie gefunden, Strahlen durch gebaute Oeffnungen suchten an der Rueckwand), die Kamerawahl
(kam_wahl.json, auch fuer Foto-Tor und ebenen_bauplan) hing am Vormodell, ohne Vorlauf gab es keinen Suchraum.
Fix: Suchraum = modellfreier Messkoerper (fassade_ortho --nur-messkoerper), --vorn 2 m vor bis --band 0,5 m hinter der Flaeche, --huelle, Wolke nur Lage-Veto.

Synthetische Szene (Kasten 10 x 8 x 10 m, Vorderwand y = -4): Fensterrahmen auf der Wand, Wandkanten, VORDACH-Vorderkante 1,2 m vor der Wand (z 3 m).
12 Kameras, Stabilkarten = gezeichnete Kanten. Messkoerper = glatter Kasten (wie LoD2 flach).
 A  zwei verschiedene Vormodelle (glatter Kasten / Kasten mit falsch gebautem Vordach 0,6 m vor der Wand + Loch) und KEIN Vormodell (Lauf von null):
    sweep.npz und kam_wahl.json bitgleich; von null: rc 4 nur wegen fehlender Bewertung, Kanten trotzdem da.
 B  die Vordachkante 1,2 m vor der Wand wird gefunden (>= 100 Punkte < 5 cm an der Kante), Fensterrahmen auf der Wand ebenso.
 C  Gegenprobe alter Weg (--suchraum modell, glattes Vormodell): Vordachkante NICHT gefunden, und die zwei Vormodelle liefern verschiedene Kanten (der Waechter sieht den Kreis).
 D  Kette: gesamtkette ruft kantenstufe ohne --suchraum modell auf; Standard der Kantenstufe ist messkoerper.
rc 0 = bestanden.
"""
import sys, os, json, re, tempfile, shutil, subprocess
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner   # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H); PY = sys.executable
F_ = 0
SK = 87.0                                                                         # stl_massstab wie echte Objekte: STL in mm (1:87), Kette rechnet in Metern


def pruef(ok, t):
    global F_
    print(("  ok     " if ok else "  FEHLER ") + t, flush=True); F_ += not ok


def stl(m, p):
    m = m.copy(); m.apply_scale(1000.0 / SK); m.export(p); return p


def kasten(lo, hi): return trimesh.creation.box(bounds=[lo, hi])


# Wirklichkeit (Meter): Kanten als Strecken
WAND_Y = -4.0; VD_Y = WAND_Y - 1.2; VD_Z = 3.0
KANTEN = [((-3, WAND_Y, 4), (-1, WAND_Y, 4)), ((-3, WAND_Y, 6), (-1, WAND_Y, 6)), ((-3, WAND_Y, 4), (-3, WAND_Y, 6)), ((-1, WAND_Y, 4), (-1, WAND_Y, 6)),   # Fenster
          ((-5, WAND_Y, 0.5), (-5, WAND_Y, 10)), ((5, WAND_Y, 0.5), (5, WAND_Y, 10)), ((-5, WAND_Y, 10), (5, WAND_Y, 10)),                                # Wandkanten
          ((0.5, VD_Y, VD_Z), (4.0, VD_Y, VD_Z)), ((0.5, VD_Y, VD_Z), (0.5, WAND_Y, VD_Z)), ((4.0, VD_Y, VD_Z), (4.0, WAND_Y, VD_Z))]                     # Vordach (1,2 m vor der Wand)


def kamera(C, ziel, f=500.0, W=640, Hh=480):
    fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw); re_ = np.cross(fw, [0, 0, 1.0]); re_ /= np.linalg.norm(re_); un = np.cross(fw, re_)
    R = np.array([re_, un, fw]); return dict(R=R.tolist(), t=(-R @ C).tolist(), f_px_original=f, cx=W / 2, cy=Hh / 2, bild_b=W, bild_h=Hh, k=[0.0])


def karte(k):
    R = np.array(k["R"]); t = np.array(k["t"]); im = np.zeros((int(k["bild_h"]), int(k["bild_b"])), np.uint8)
    for A, B in KANTEN:
        P = np.linspace(A, B, 400) @ R.T + t; u = k["f_px_original"] * P[:, 0] / P[:, 2] + k["cx"]; v = k["f_px_original"] * P[:, 1] / P[:, 2] + k["cy"]
        for i in range(len(P) - 1): cv2.line(im, (int(round(u[i])), int(round(v[i]))), (int(round(u[i + 1])), int(round(v[i + 1]))), 255, 1)
    return im


def an_strecke(P, A, B):
    A = np.asarray(A, float); B = np.asarray(B, float); d = B - A; t = np.clip(((P - A) @ d) / (d @ d), 0, 1); return np.linalg.norm(P - (A + t[:, None] * d), axis=1)


def main():
    tmp = temp_ordner("kantenkreis_"); bd = os.path.join(tmp, "bilder"); os.makedirs(bd)
    try:
        kams = {}; i = 0
        for x in (-8, -4.5, -1.5, 1.5, 4.5, 8):
            for z in (1.5, 6.5):
                C = np.array([x, -15.0 - (i % 3), z + 0.3 * (i % 2)]); kams[f"k{i:02d}"] = kamera(C, (0, WAND_Y, 4.5)); i += 1
        AU = os.path.join(tmp, "ausrichtung.json"); json.dump(dict(kameras=kams), open(AU, "w"))
        stabil = {n: karte(k) for n, k in kams.items()}
        for n in kams: cv2.imwrite(os.path.join(bd, n + ".jpg"), np.zeros((8, 8), np.uint8))
        mk = stl(kasten((-5, -4, 0), (5, 4, 10)), os.path.join(tmp, "messkoerper.stl"))
        m1 = stl(kasten((-5, -4, 0), (5, 4, 10)), os.path.join(tmp, "vormodell1.stl"))
        m2_ = kasten((-5, -4, 0), (5, 4, 10)).difference(kasten((-2.8, -4.5, 4.2), (-1.2, -3.0, 5.8))) if trimesh.boolean.engines_available else kasten((-5, -4, 0), (5, 4, 10))
        m2 = stl(trimesh.util.concatenate([m2_, kasten((0.5, -4.6, 2.9), (4.0, -4.0, 3.0))]), os.path.join(tmp, "vormodell2.stl"))

        def lauf(name, vormodell, *extra):
            d = os.path.join(tmp, name); os.makedirs(os.path.join(d, "stabil"))
            for n, im in stabil.items(): cv2.imwrite(os.path.join(d, "stabil", n + ".png"), im)
            oj = os.path.join(tmp, f"objekt_{name}.json"); json.dump(dict(name="kreis", stl=vormodell, stl_massstab=SK), open(oj, "w"))
            r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(H, "kantenstufe.py"), oj, "--ausrichtung", AU, "--bilder", bd, "--aus", d, "--geraet", "cpu",
                                "--stabil_vorhanden", "--refs", "12"] + (["--messkoerper", mk] if "--suchraum" not in extra else []) + list(extra), capture_output=True, text=True)
            Z = np.load(os.path.join(d, "sweep.npz")) if os.path.exists(os.path.join(d, "sweep.npz")) else None
            if Z is None: print((r.stdout + r.stderr)[-1500:])
            return r.returncode, (Z["P"] if Z is not None else np.zeros((0, 3))), open(os.path.join(d, "kam_wahl.json")).read() if os.path.exists(os.path.join(d, "kam_wahl.json")) else "", r

        rc1, P1, W1, r1 = lauf("neu_v1", m1); rc2, P2, W2, _ = lauf("neu_v2", m2); rc0, P0, W0, r0 = lauf("neu_null", os.path.join(tmp, "gibt_es_nicht.stl"))
        print("  (neu_v1: " + (r1.stdout.strip().splitlines() or ["?"])[-1][:160] + ")")
        pruef(rc1 == 0 and len(P1) > 2000, f"A neuer Weg laeuft (rc {rc1}, {len(P1)} Kantenpunkte)")
        pruef(P1.shape == P2.shape and np.array_equal(P1, P2) and W1 == W2, "A zwei verschiedene Vormodelle -> sweep.npz und kam_wahl.json bitgleich")
        pruef(P0.shape == P1.shape and np.array_equal(P0, P1) and W0 == W1 and rc0 == 4 and "zum Bewerten" in r0.stdout, f"A Lauf von null (kein Vormodell): gleiche Kanten, rc {rc0} nur wegen fehlender Bewertung")
        dv = an_strecke(P1, *KANTEN[7]); df = np.min([an_strecke(P1, *k) for k in KANTEN[:4]], 0)
        pruef(int((dv < 0.05).sum()) >= 100, f"B Vordachkante 1,2 m vor der Wand gefunden: {int((dv < 0.05).sum())} Punkte < 5 cm (Median {np.median(dv[dv < 0.3]) if (dv < 0.3).any() else float('nan'):.3f} m)")
        pruef(int((df < 0.05).sum()) >= 200, f"B Fensterrahmen auf der Wand gefunden: {int((df < 0.05).sum())} Punkte < 5 cm")
        dall = np.min([an_strecke(P1, *k) for k in KANTEN], 0)
        pruef(float((dall < 0.10).mean()) >= 0.8, f"B Anteil Kantenpunkte < 10 cm an einer wahren Kante {float((dall < 0.10).mean()) * 100:.0f} % (>= 80 %)")
        rca, Pa, Wa, _ = lauf("alt_v1", m1, "--suchraum", "modell"); rcb, Pb, Wb, _ = lauf("alt_v2", m2, "--suchraum", "modell")
        dva = an_strecke(Pa, *KANTEN[7]) if len(Pa) else np.ones(1)
        pruef(int((dva < 0.05).sum()) < 20, f"C Gegenprobe alter Weg (+-0,5 m um glattes Vormodell): Vordachkante NICHT gefunden ({int((dva < 0.05).sum())} Punkte)")
        pruef(not (Pa.shape == Pb.shape and np.array_equal(Pa, Pb)), f"C Gegenprobe alter Weg: zwei Vormodelle -> verschiedene Kanten ({len(Pa)} / {len(Pb)} Punkte)")
        gk = open(os.path.join(H, "gesamtkette.py")).read(); aufr = re.findall(r'"tools/kantenstufe\.py"[^\n]*', gk)
        pruef(len(aufr) >= 1 and not any("modell" in z.split("--suchraum")[1][:12] for z in aufr if "--suchraum" in z), f"D Kette: {len(aufr)} Aufrufe der Kantenstufe, keiner mit --suchraum modell")
        ks = open(os.path.join(H, "kantenstufe.py")).read()
        pruef(re.search(r'"--suchraum", choices=\("messkoerper", "modell"\), default="messkoerper"', ks) is not None, "D Standard der Kantenstufe: --suchraum messkoerper")
    finally: shutil.rmtree(tmp, ignore_errors=True)
    print("BESTANDEN" if F_ == 0 else f"{F_} FEHLER"); return 1 if F_ else 0


if __name__ == "__main__":
    sys.exit(main())
