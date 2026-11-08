#!/usr/bin/env python3
"""test_element_einpassen.py - S9 Beweis 1 (synthetisch, Wahrheit bekannt, VOR dem Kaufhaus gelaufen):
Rund-, Stich-, Spitzbogen verschiedener Masse (je andere Breite/Hoehe/Lage) + Kleeblattbogen (gehoert keiner Familie an).
Eingabe sind SYNTHETISCHE Einzel-Orthos (Wandtextur, dunkle Oeffnung, hellere Bogenleibung, Rauschen, je Foto wechselnde Stoerkanten, schwarze Leerstellen,
eine feste Stoerkante) -> dieselbe Kantenextraktion + Anpassung wie am Kaufhaus. Kasten des Kandidaten um bis zu 0,4 m versetzt (OWLv2-Ungenauigkeit).
Formdaten = Leere-Maske (Carving-artig: 0,1-m-Voxel, Randrauschen, Klumpen); unabhaengige Pruefung = Canny-Kantenkontrast auf den synthetischen Orthos.
Sollwerte (vorab): Familie richtig; Kronen-/Pfostenkurve gegen Wahrheit: Median < 0,03 m, P95 < 0,05 m (an den Maskendaten + Kantenfeinlage); Kleeblatt (2 Varianten) ABGELEHNT.
NEGATIV=1: Wahrheitsfamilie vertauscht -> Test muss durchfallen (Exit 1).
  ~/.venvs/rcpark/bin/python -I tools/test_element_einpassen.py [aus]"""
import os, sys, json, tempfile, shutil
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import element_einpassen as EE
from scipy.spatial import cKDTree

Z = 0.05; NU, NZ = 320, 200; U0 = -8.0; Z1 = 9.0; ZB = 0.0


def wahrheit_maske(fam, p, U, Zz):
    if fam == "klee2":      # tiefe Kerben: drei Kreise r = 0,22 w, Seitenlappen auf den Pfosten, Kopf darueber
        uc, w, zs = p; r = 0.22 * w; ok = (Zz >= ZB) & (Zz <= zs) & (np.abs(U - uc) <= w / 2)
        for cu, cz in ((uc - w / 2 + r, zs), (uc + w / 2 - r, zs), (uc, zs + 0.38 * w)): ok |= (U - cu) ** 2 + (Zz - cz) ** 2 <= r * r
        return ok
    if fam == "klee":
        uc, w, zs = p; r = w / 4; ok = (Zz >= ZB) & (Zz <= zs) & (np.abs(U - uc) <= w / 2)
        for cu, cz in ((uc - w / 4, zs), (uc + w / 4, zs), (uc, zs + r * 3 ** 0.5 / 2 * 1.0 + 0.0)):
            ok |= (U - cu) ** 2 + (Zz - cz) ** 2 <= r * r
        return ok
    return EE.in_oeffnung(fam, p, ZB, U, Zz, 0.0)


def wahrheit_kurve(fam, p):
    if fam == "klee2": uc, w, zs = p; return np.array([[uc - w / 2, zs], [uc, zs + 0.38 * w + 0.22 * w]])
    if fam == "klee":
        uc, w, zs = p; r = w / 4; pts = []
        for cu, cz, a0, a1 in ((uc - w / 4, zs, 180, 90 - 60 + 0), (uc, zs + r * 3 ** 0.5 / 2, 150, 30), (uc + w / 4, zs, 120, 0)):
            a = np.radians(np.linspace(a0, a1, 200)); pts.append(np.c_[cu + r * np.cos(a), cz + r * np.sin(a)])
        return np.vstack(pts)
    return EE.profil(fam, p, ZB, 0.01)


def synth_ortho(ordner, fam, p, seed, n_fotos=6):
    rng = np.random.default_rng(seed); ed = os.path.join(ordner, "ortho_fx_einzeln"); os.makedirs(ed, exist_ok=True)
    xs, ys = np.meshgrid(np.arange(NU), np.arange(NZ)); U = U0 + (xs + .5) * Z; Zz = Z1 - (ys + .5) * Z
    m = wahrheit_maske(fam, p, U, Zz).astype(np.uint8)
    dist_aussen = cv2.distanceTransform(1 - m, cv2.DIST_L2, 3) * Z                     # Abstand ausserhalb der Oeffnung (m)
    band = (dist_aussen > 0) & (dist_aussen < 0.25)
    textur = cv2.GaussianBlur(rng.normal(0, 1, (NZ, NU)).astype(np.float32), (0, 0), 2) * 14
    basis = np.where(m > 0, 55, np.where(band, 225, 175)).astype(np.float32) + textur
    zt = max(wahrheit_kurve(fam, p)[:, 1]) + 0.9
    for k in range(n_fotos):
        g = basis + rng.normal(0, 5, basis.shape).astype(np.float32) + rng.uniform(-12, 12)
        for _ in range(7):                                                              # wechselnde Stoerer (Passanten, Schilder)
            x0, y0 = rng.integers(0, NU - 30), rng.integers(0, NZ - 30); g[y0:y0 + rng.integers(8, 40), x0:x0 + rng.integers(5, 25)] = rng.uniform(20, 240)
        g[int((Z1 - zt) / Z):int((Z1 - zt) / Z) + 2, :] = 90                           # feste Stoerkante (Gesims)
        img = np.clip(g, 0, 255).astype(np.uint8); img = np.dstack([img, img, img]); img[img.sum(2) == 0] = 1
        for _ in range(2):                                                              # schwarze Leerstellen
            x0, y0 = rng.integers(0, NU - 40), rng.integers(0, NZ - 60); img[y0:y0 + rng.integers(20, 60), x0:x0 + rng.integers(8, 30)] = 0
        cv2.imwrite(os.path.join(ed, f"{k:03d}.png"), img)
    return dict(u0=U0, z1=Z1, zelle=Z, nu=NU, nz=NZ)


def kurven_abstand(fam_w, p_w, fam_f, p_f):
    A = wahrheit_kurve(fam_w, p_w); B = EE.profil(fam_f, p_f, ZB, 0.01)
    mk = A[:, 1] >= (p_w[2] - 1.2)
    d1 = cKDTree(B).query(A[mk])[0]; d2 = cKDTree(A).query(B[B[:, 1] >= p_w[2] - 1.2])[0]
    d = np.r_[d1, d2]; return float(np.median(d)), float(np.percentile(d, 95)), float(d.max())


FAELLE = [  # (Name, Familie, p) p = (uc, w, zs[, h])
    ("rund_a", "rund", (-3.0, 3.6, 2.4)), ("rund_b", "rund", (2.5, 5.0, 2.0)),
    ("stich_a", "stich", (-2.0, 4.2, 2.6, 1.1)), ("stich_b", "stich", (3.0, 3.3, 3.0, 0.9)),
    ("spitz_a", "spitz", (-1.0, 3.0, 2.2, 2.6)), ("spitz_b", "spitz", (1.0, 3.4, 2.5, 2.94)),
    ("klee", "klee", (0.0, 3.6, 2.2)), ("klee_tief", "klee2", (0.5, 3.6, 2.2)),
]


def synth_maske(fam, p, seed, vox=0.1, ds=0.05):
    """Carving-artige Leere: Wahrheit auf 0,1-m-Voxel gerastert (zufaellige Teilvoxel-Phase), Randvoxel mit 15 % Flip, 3 Klumpen (Waren, Personen) im Inneren/Zwickel."""
    rng = np.random.default_rng(seed); ph = rng.uniform(0, vox, 2)
    xs, ys = np.meshgrid(np.arange(NU), np.arange(NZ)); U = U0 + (xs + .5) * Z; Zz = Z1 - (ys + .5) * Z
    Uq = np.floor((U - ph[0]) / vox) * vox + vox / 2 + ph[0]; Zq = np.floor((Zz - ph[1]) / vox) * vox + vox / 2 + ph[1]
    E = wahrheit_maske(fam, p, Uq, Zq)
    rand = cv2.dilate(E.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) ^ cv2.erode(E.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool); E = np.where(rand & (rng.random(E.shape) < 0.15), ~E, E)
    for _ in range(3):
        cx, cy = rng.integers(10, NU - 10), rng.integers(40, NZ - 10); E[cy - 4:cy + 5, cx - 3:cx + 4] = ~E[cy - 4:cy + 5, cx - 3:cx + 4]
    return E


def main():
    aus = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="s9synth_"); os.makedirs(aus, exist_ok=True)
    neg = os.environ.get("NEGATIV") == "1"; erg = []; fehler = 0
    for i, (name, fam, p) in enumerate(FAELLE):
        d = os.path.join(aus, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        ra = synth_ortho(d, fam, p, 100 + i); D, G, V, nf = EE.kantenpunkte(d, "fx", ra, (), log=lambda *a: None)
        Er = synth_maske(fam, p, 200 + i); Bp, Bn = EE.maske_rand(Er, U0, Z1, Z)
        k = wahrheit_kurve(fam, p); rng = np.random.default_rng(7 + i); w = p[1]
        kasten = dict(u0=p[0] - w / 2 + rng.uniform(-.3, .3), u1=p[0] + w / 2 + rng.uniform(-.3, .3), z0=ZB, z1=float(k[:, 1].max()) + rng.uniform(-.3, .3))
        e = EE.bogen_aus_maske(Bp, kasten, ZB, D, G, log=lambda *a: None)
        kk = e["kantenkontrast"]; kt = f"Kantenkontrast Stuetze {kk['stuetze']:.2f} Verh. {kk['verhaeltnis']:.1f}"
        if fam in ("klee", "klee2"):
            ok = not e["angenommen"]; txt = f"abgelehnt={not e['angenommen']} ({'; '.join(e['ablehngrund'])}) beste Familie {e['familie']} med {e['rest']['median_m']:.3f} p90 {e['rest']['p90_m']:.3f}/{e['rest']['p90_rand_m']:.3f}; {kt}"
            erg.append(dict(fall=name, wahr="kleeblatt", familie=e["familie"], angenommen=e["angenommen"], ok=ok, rest=e["rest"], ablehngrund=e["ablehngrund"]))
        else:
            fam_gt = {"rund": "spitz", "spitz": "stich", "stich": "rund"}[fam] if neg else fam
            md, p95, mx = kurven_abstand(fam, p, e["familie"], e["p"]) if e["familie"] == fam else (9.9, 9.9, 9.9)      # NEGATIV: erwartete Familie vertauscht -> Familienpruefung muss durchfallen
            ok = e["familie"] == fam_gt and md < 0.03 and p95 < 0.05 and e["angenommen"]
            txt = f"Familie {e['familie']} (Wahrheit {fam_gt}), p_fit {np.round(e['p'], 3).tolist()} gegen {p}, Kurve med {md * 100:.1f} cm P95 {p95 * 100:.1f} cm max {mx * 100:.1f} cm, Rest med {e['rest']['median_m'] * 100:.1f} cm angenommen {e['angenommen']} {e['ablehngrund']}; {kt}"
            erg.append(dict(fall=name, wahr=fam_gt, familie=e["familie"], p_fit=e["p"], p_wahr=list(p), kurve_med_cm=md * 100, kurve_p95_cm=p95 * 100, kurve_max_cm=mx * 100, angenommen=e["angenommen"], ok=bool(ok), rest=e["rest"], kantenkontrast=kk,
                            bic={k_: round(v["bic"], 1) for k_, v in e["alle_familien"].items()}))
        print(("OK   " if ok else "FEHL ") + f"{name}: {txt}", flush=True); fehler += (not ok)
    json.dump(erg, open(os.path.join(aus, "synth_ergebnis.json"), "w"), indent=1)
    print(f"{len(FAELLE) - fehler}/{len(FAELLE)} bestanden -> {aus}/synth_ergebnis.json")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
