#!/usr/bin/env python3
"""test_messflaeche_kreis.py - WAECHTER gegen zirkulaere Messung (CPU, wenige Sekunden, ohne Daten; 22.11.2026, Kreisfall Einzelorthos schwabentor-1120).

Befund: die Kettenstufen fenster_ortho / fenster_ortho_fein (fassade_ortho --einzeln) projizierten die Fotos auf das STL des VORIGEN Kettenlaufs.
Dessen gebaute Oeffnungen/Relief waren Naehte in der Projektionsflaeche, an denen Kanten in jedem Foto klebten -> fenster_form_tor, nischen_fenster,
laibung, sohlbank, uhren, umgang, oeffnungen_aus_kanten ... massen das eigene Vormodell nach (Tor je Lauf 4,3 / 5,2 m). Ohne Vorlauf (von null) fehlte das STL ganz.
Fix: fassade_ortho --messflaeche eben = modellfreier Messkoerper (LoD2 flach + Wandversatz aus Fotokanten), in der Kette Pflicht fuer alle Messorthos.

Regel des Waechters: dieselbe Messung mit ZWEI VERSCHIEDENEN Vormodellen muss dasselbe Ergebnis liefern.
 A  fassade_ortho --messflaeche eben mit Vormodell 1 (glatter Kasten), Vormodell 2 (Nische ausgehoehlt + falscher Vorbau davor) und OHNE Vormodell (Lauf von null):
    Einzelorthos, fusioniertes Ortho und Relief bitgleich.
 B  Gegenprobe: --messflaeche modell mit denselben zwei Vormodellen liefert VERSCHIEDENE Einzelorthos (der Waechter sieht den Kreis wirklich).
 C  wandversatz: Wandebene aus audit/schleife_korrekturen.json (Fotokanten) wird nach Normale + Ebene zugeordnet (-0,15 m), fremde Fassade/abgelehnte nicht;
    Relief-PNG traegt den Versatz, Messkoerper liegt dort.
 D  Kette: jede fassade_ortho-Stufe mit --einzeln ausserhalb bauplan_innen_* laeuft mit --messflaeche eben und ohne --stl; mono nutzt den Messkoerper.
rc 0 = bestanden.
"""
import sys, os, json, re, tempfile, shutil, glob, contextlib, io
import numpy as np, cv2, trimesh
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import fassade_ortho as FO
F_ = 0


def pruef(ok, t):
    global F_
    print(("  ok     " if ok else "  FEHLER ") + t); F_ += not ok


def kamera(C, ziel, f=1500.0, W=1000, Hh=800):
    fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw); re_ = np.cross(fw, [0, 0, 1.0]); re_ /= np.linalg.norm(re_); un = np.cross(fw, re_)
    R = np.array([re_, un, fw]); return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=(-R @ C).tolist(), f_px=f, cx=W / 2, cy=Hh / 2, k1=0.0), R


# Wirklichkeit: Kasten x -5..5, y -4..4, z 0..10; Vorderwand y = -4 mit Nische x 1..2,4, z 3..5,5, 0,6 m tief
NI = (1.0, 2.4, 3.0, 5.5, 0.6)


def wand_textur(x, z): return 128 + 55 * np.sign(np.sin(2 * np.pi * x / 0.7)) * np.sign(np.sin(2 * np.pi * z / 0.5)) + 20 * np.sin(x * 3.1 + z * 1.7)


def foto(kk, R, C, W=1000, Hh=800):
    jj, ii = np.meshgrid(np.arange(W) + 0.5, np.arange(Hh) + 0.5); D = np.stack([(jj - kk["cx"]) / kk["f_px"], (ii - kk["cy"]) / kk["f_px"], np.ones_like(jj)], -1) @ R
    t = (-4.0 - C[1]) / D[..., 1]; x = C[0] + t * D[..., 0]; z = C[2] + t * D[..., 2]
    img = np.full((Hh, W), 210.0)                                                                       # Himmel / Umgebung
    wand = (t > 0) & (np.abs(x) <= 5) & (z >= 0) & (z <= 10); img[wand] = wand_textur(x[wand], z[wand])
    ni = wand & (x >= NI[0]) & (x <= NI[1]) & (z >= NI[2]) & (z <= NI[3])
    t2 = (-4.0 + NI[4] - C[1]) / D[..., 1]; x2 = C[0] + t2 * D[..., 0]; z2 = C[2] + t2 * D[..., 2]
    rueck = ni & (x2 >= NI[0]) & (x2 <= NI[1]) & (z2 >= NI[2]) & (z2 <= NI[3]); img[ni] = 90; img[rueck] = 40 + 30 * np.sign(np.sin(2 * np.pi * x2[rueck] / 0.3))
    return np.clip(img, 0, 255).astype(np.uint8)


def lod2_fake(obj):
    x0, x1, y0, y1, z1 = -5.0, 5.0, -4.0, 4.0, 10.0
    W = lambda a, b: np.array([[a[0], a[1], 0], [b[0], b[1], 0], [b[0], b[1], z1], [a[0], a[1], z1]], float)
    return [("WallSurface", W((x0, y0), (x1, y0))), ("WallSurface", W((x1, y0), (x1, y1))), ("WallSurface", W((x1, y1), (x0, y1))), ("WallSurface", W((x0, y1), (x0, y0))),
            ("RoofSurface", np.array([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)), ("GroundSurface", np.array([[x0, y0, 0], [x0, y1, 0], [x1, y1, 0], [x1, y0, 0]], float))]


def box(lo, hi): return trimesh.creation.box(bounds=np.array([lo, hi], float))


def stl_mm(m, p): m = m.copy(); m.apply_scale(1000.0 / 87.0); m.export(p); return p


def lauf(objekt, aus, *arg):
    with contextlib.redirect_stdout(io.StringIO()):
        try: FO.main([objekt, "--aus", aus, "--einzeln", "--zelle", "0.05", "--ohne-gpu", "--ohne-nachbarn", "--arbeiter", "2", "--max-fotos", "0", "--beste", "3"] + list(arg))
        except SystemExit as e_:
            if e_.code not in (None, 0): raise
    return {os.path.relpath(p, aus): cv2.imread(p, cv2.IMREAD_UNCHANGED) for p in sorted(glob.glob(os.path.join(aus, "**", "*.png"), recursive=True))}


def gleich(A, B): return set(A) == set(B) and all(A[k].shape == B[k].shape and np.array_equal(A[k], B[k]) for k in A)


def main():
    FO.lod2_eigen = lod2_fake; FO.lod2_waende = lambda obj: ([P for t, P in lod2_fake(obj) if t == "WallSurface"], np.zeros(2))
    T = temp_ordner("messflaeche_kreis_")
    try:
        od = os.path.join(T, "obj"); fd = os.path.join(T, "fotos"); os.makedirs(os.path.join(od, "messprotokoll")); os.makedirs(fd)
        for nr, C in (("cam1", np.array([-4.0, -16.0, 3.0])), ("cam2", np.array([5.0, -14.0, 6.0])), ("cam3", np.array([0.5, -12.0, 4.0]))):
            kk, R = kamera(C, (0.5, -4.0, 4.5)); cv2.imwrite(os.path.join(fd, nr + ".png"), cv2.cvtColor(foto(kk, R, C), cv2.COLOR_GRAY2BGR))
            json.dump(dict(kamera=kk), open(os.path.join(od, "messprotokoll", f"K-{nr}.json"), "w"))
        objekt = os.path.join(od, "objekt.json"); json.dump(dict(name="kreis", zentrierung="achse", fotos_dir=fd, masstabelle=os.path.join(od, "masstabelle.json"), stl_massstab=87), open(objekt, "w"))
        v1 = stl_mm(box((-5, -4, 0), (5, 4, 10)), os.path.join(T, "vor1.stl"))                                       # Vormodell 1: glatter Kasten
        teile = [box((-5, -4 + NI[4], 0), (5, 4, 10)), box((-5, -4, 0), (NI[0], -4 + NI[4], 10)), box((NI[1], -4, 0), (5, -4 + NI[4], 10)),
                 box((NI[0], -4, 0), (NI[1], -4 + NI[4], NI[2])), box((NI[0], -4, NI[3]), (NI[1], -4 + NI[4], 10)), box((-3, -4.4, 2), (-2, -4, 8))]   # Vormodell 2: Nische hohl + falscher Vorbau 0,4 m
        v2 = stl_mm(trimesh.util.concatenate(teile), os.path.join(T, "vor2.stl"))
        E1 = lauf(objekt, os.path.join(T, "e1"), "--messflaeche", "eben", "--stl", v1)
        E2 = lauf(objekt, os.path.join(T, "e2"), "--messflaeche", "eben", "--stl", v2)
        E0 = lauf(objekt, os.path.join(T, "e0"), "--messflaeche", "eben")
        ein = [k for k in E1 if "_einzeln" in k]
        pruef(len(ein) >= 2 and all(int((E1[k] > 0).any(axis=-1).sum()) > 2000 for k in ein), f"A eben: {len(ein)} Einzelorthos mit Inhalt ({', '.join(ein)})")
        pruef(gleich(E1, E2), "A eben: Vormodell glatt und Vormodell mit Nische+Vorbau -> alle Bilder bitgleich (keine Naht des Vormodells)")
        pruef(gleich(E1, E0), "A eben: Lauf von null (kein STL) -> dasselbe Ergebnis")
        FJ = json.load(open(os.path.join(T, "e0", "fassaden.json")))
        pruef(FJ.get("stl") is None and FJ.get("messflaeche") == "eben" and FJ.get("verdecker_selbstbau", {}).get("zustand") == "messkoerper", "A eben: fassaden.json ohne STL, messflaeche eben")
        M1 = lauf(objekt, os.path.join(T, "m1"), "--stl", v1); M2 = lauf(objekt, os.path.join(T, "m2"), "--stl", v2)
        dif = [k for k in M1 if "_einzeln" in k and (k not in M2 or M1[k].shape != M2[k].shape or not np.array_equal(M1[k], M2[k]))]
        pruef(len(dif) >= 1, f"B Gegenprobe modell: Vormodell veraendert {len(dif)} Einzelorthos (Kreis sichtbar, der Waechter greift)")
        # C Wandversatz aus Fotokanten
        fa = FO.fassaden_gruppieren(*FO.lod2_waende({}))
        f0 = [F for F in fa if F["n"][1] < -0.9][0]; fs = [F for F in fa if F["n"][0] > 0.9][0]
        os.makedirs(os.path.join(od, "audit")); n0 = np.array(f0["n"]); o0 = np.array(f0["o"])
        KK = [dict(id="k0", art="wandversatz", fassade="f??", o=(o0 + 2.0 * np.array(f0["d"])).tolist(), n=f0["n"], w_soll=-0.15, angenommen=True),
              dict(id="k1", art="wandversatz", o=fs["o"], n=fs["n"], w_soll=0.4, angenommen=False), dict(id="k2", art="fleck", o=f0["o"], n=f0["n"], w_soll=0.3)]
        json.dump(dict(korrekturen=KK), open(os.path.join(od, "audit", "schleife_korrekturen.json"), "w"))
        w0, q0 = FO.wandversatz(objekt, f0); ws, _ = FO.wandversatz(objekt, fs)
        pruef(abs(w0 + 0.15) < 1e-6 and "k0" in q0 and ws == 0.0, f"C wandversatz: Vorderwand {w0:+.3f} ({q0}), Seitenwand {ws:+.2f} (abgelehnt/fremd nicht genommen)")
        EV = lauf(objekt, os.path.join(T, "ev"), "--messflaeche", "eben", "--stl", v2)
        rk = [k for k in EV if k.startswith("relief_")]; FJ = json.load(open(os.path.join(T, "ev", "fassaden.json")))
        fv = [F for F in FJ["fassaden"] if F["n"][1] < -0.9][0]; rv = EV[f"relief_{fv['id']}.png"]; ww = (rv[rv > 0].astype(float) - 10000) / 1000
        pruef(len(rk) == 4 and abs(fv["messflaeche"]["versatz"] + 0.15) < 1e-6 and len(ww) and np.allclose(ww, -0.15), f"C Relief der Vorderwand = Wandversatz {np.unique(np.round(ww, 3)) if len(ww) else '-'}")
        for F in fa: F["messflaeche"] = dict(versatz=FO.wandversatz(objekt, F)[0])
        MK = FO.messkoerper(lod2_fake({}), fa); P = np.asarray(MK.triangles_center); vf = np.abs(np.asarray(MK.face_normals)[:, 1]) > 0.99
        pruef(vf.sum() >= 2 and np.allclose(P[vf & (P[:, 1] < 0), 1], -3.85) and np.isclose(MK.vertices[:, 2].max(), 10.0), "C Messkoerper: Vorderwand 0,15 m hinter LoD2, Dach aus LoD2")
        # D Kette
        src = open(os.path.join(H, "gesamtkette.py")).read(); st = re.findall(r'lauf\(B, "([a-z_]+)", \[([^\]]*tools/fassade_ortho\.py[^\]]*)\]', src)
        mess = [(n, a_) for n, a_ in st if "--einzeln" in a_ and not n.startswith("bauplan_innen")]
        pruef(len(mess) >= 2 and all('"--messflaeche", "eben"' in a_ and '"--stl"' not in a_ for _, a_ in mess), "D Kette: Messorthos " + ", ".join(n for n, _ in mess) + " auf --messflaeche eben, ohne --stl")
        pruef(any(n == "mono_messkoerper" and "--nur-messkoerper" in a_ for n, a_ in st) and 'stl_m = os.path.join(D, "messkoerper.stl")' in src, "D Kette: mono waehlt Fotos gegen den Messkoerper")
    finally: shutil.rmtree(T, ignore_errors=True)
    print("BESTANDEN" if F_ == 0 else f"{F_} FEHLER"); return 1 if F_ else 0


if __name__ == "__main__":
    sys.exit(main())
