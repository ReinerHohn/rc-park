#!/usr/bin/env python3
"""test_keilsteine.py - fester synthetischer Test fuer quader_raster.keilsteine (21.11.2026 spaet), < 20 s, nur CPU.

Wandbild 1 cm: Spitzbogen (lichte Weite 3,0 m, Kaempfer 2,0 m, Scheitel 4,4 m). Davor 0,30 m glattes Gewaende ohne Fugen, dann ein Ring Keilsteine 0,30..0,80 m mit
RADIALEN hellen Fugen alle ~0,40 m Bogenlaenge, aussen Quadermauerwerk in Lagen (0,40 m hoch, Stossfugen versetzt). Drei 'Fotos' = dasselbe Bild mit Rauschen.
Erwartung: Ring r_in 0,30 +-0,08, Ruecken 0,80 +-0,12; gefundene Fugen liegen je <= 0,05 m an einer wahren Fuge, >= 70 % der wahren Fugen gefunden;
jede Keilstein-Grenze radial (Fugenzellen im Ring liegen auf Linien gleicher Bogenlaenge); Steine ausserhalb r > 1,2 m unveraendert; alte Rechtecksteine in der
Oeffnung entfernt. Gegenprobe: gleicher Bogen ohne Fugen im Ring (Putzbogen) -> keine Keilsteine. Wandbild mit Quadern bis an die Bogenlinie (keine radialen Fugen) -> keine.
"""
import sys, os, numpy as np
H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)
import quader_raster as Q
from scipy import ndimage as ndi
c = 0.01; U0, U1, Z0, Z1 = -3.0, 3.0, 0.0, 6.5
BOGEN = dict(form="spitz", u=0.0, breite=3.0, kaempfer=2.0, scheitel=4.4)


def bild(keil=True, quader_bis_innen=False, seed=0):
    uu = U0 + (np.arange(int((U1 - U0) / c)) + 0.5) * c; zz = Z1 - (np.arange(int((Z1 - Z0) / c)) + 0.5) * c; UU, ZZ = np.meshgrid(uu, zz)
    pts, tg, nrm, s = Q._bogen_linie(BOGEN, c)
    from scipy.spatial import cKDTree
    X = np.stack([UU.ravel(), ZZ.ravel()], 1); _, k = cKDTree(pts).query(X); v = X - pts[k]; r = np.einsum("ij,ij->i", v, nrm[k]).reshape(UU.shape); sk = s[k].reshape(UU.shape)
    am_ende = ((k < 2) | (k > len(pts) - 3)).reshape(UU.shape)
    innen = ((r < 0) & ~am_ende) | ((ZZ <= 2.0) & (np.abs(UU) < 1.5))
    g = np.full(UU.shape, 120.0)
    lage = (np.mod(ZZ, 0.40) < 0.025); versatz = np.where(np.mod(np.floor(ZZ / 0.40), 2) == 0, 0.0, 0.35); stoss = np.mod(UU + versatz, 0.70) < 0.025
    mauer = lage | stoss
    ring = (r >= 0.30) & (r <= 0.80) & ~am_ende & (ZZ > 2.0)
    fugen_s = np.arange(0.40, s[-1] - 0.2, 0.40)
    if quader_bis_innen: g[mauer & (r > 0) & ~innen] = 200.0
    else:
        g[mauer & ~innen & ~((r <= 0.80) & ~am_ende & (ZZ > 2.0))] = 200.0
        if keil:
            rf = np.min(np.abs(sk[..., None] - fugen_s[None, None, :]), axis=-1) < 0.0125
            g[ring & (rf | (np.abs(r - 0.80) < 0.0125))] = 200.0
        g[(r > 0) & (r < 0.30) & ~am_ende & (ZZ > 2.0)] = 80.0                 # glattes dunkles Gewaende
    g[innen] = 40.0
    rng = np.random.default_rng(seed); bilder = [np.clip(ndi.gaussian_filter(g, 1.0) + rng.normal(0, 6, g.shape), 1, 255) for _ in range(3)]
    return bilder, uu, zz, r, sk, innen, ring, fugen_s


def lauf(keil=True, quader_bis_innen=False):
    bilder, uu, zz, r, sk, innen, ring, fugen_s = bild(keil, quader_bis_innen)
    ant, nf = Q.fugen_antwort(bilder, c)
    stein = ~innen
    lab0, _, si = Q.raster_segmentieren(ant, stein, c)
    lab_alt = lab0.copy(); UU, ZZ = np.meshgrid(uu, zz); lab_alt[(np.abs(UU) < 0.3) & (ZZ > 3.0) & (ZZ < 3.4)] = lab0.max() + 1      # falscher alter 'Stein' in der Oeffnung
    frei = ndi.binary_dilation(innen, np.ones((5, 5)))
    lab, keil_ids, info = Q.keilsteine(ant, lab_alt, c, uu, zz, BOGEN, vz=1.0 if si["polaritaet"] == "hell" else -1.0, frei=frei, gueltig=nf >= 2)
    return lab_alt, lab, keil_ids, info, r, sk, innen, fugen_s


def main():
    F = 0
    def pruef(ok, t):
        nonlocal F; print(("  ok     " if ok else "  FEHLER ") + t); F += not ok
    lab_alt, lab, keil, info, r, sk, innen, fugen_s = lauf()
    pruef(len(keil) >= 5, f"Keilsteine: {len(keil)} ({ {k: v for k, v in info.items() if k not in ('kohaerenz', 'ruecken_je_stein', 'bogenbreite_je_stein_m')} })")
    pruef(abs(info.get("r_in", -9) - 0.30) <= 0.08 and abs(info.get("ruecken", -9) - 0.80) <= 0.12, f"Ring r_in {info.get('r_in')} (0,30), Ruecken {info.get('ruecken')} (0,80)")
    gr = np.cumsum([0.0] + info.get("bogenbreite_je_stein_m", []))[1:-1]
    treffer = [f for f in gr if np.abs(fugen_s - f).min() <= 0.05]; gefunden = [t for t in fugen_s if len(gr) and np.abs(gr - t).min() <= 0.05]
    pruef(len(gr) and len(treffer) == len(gr) and len(gefunden) >= 0.7 * len(fugen_s), f"Fugen {len(gr)}: {len(treffer)} an wahren Fugen, {len(gefunden)}/{len(fugen_s)} wahre gefunden")
    K = np.isin(lab, keil); grenz = K & (np.roll(lab, 1, 1) != lab) & np.roll(K, 1, 1) & (r > 0.4) & (r < 0.7)
    if grenz.any():
        abst = np.abs(sk[grenz][:, None] - gr[None, :]).min(1) if len(gr) else np.full(grenz.sum(), 9.0)
        pruef(np.mean(abst <= 0.03) >= 0.9, f"Grenzen zwischen Keilsteinen radial: {np.mean(abst <= 0.03):.0%} auf Linien gleicher Bogenlaenge")
    aussen = (r > 1.25) | ((r < -9))
    pruef(np.array_equal(lab[aussen & ~innen], lab_alt[aussen & ~innen]), "ausserhalb des Rings (r > 1,25 m) unveraendert")
    pruef(info.get("alte_steine_in_oeffnung", 0) >= 1 and not (lab[innen & (sk > 0.5) & (r < -0.2)] > 0).any(), f"alte Steine in der Oeffnung entfernt ({info.get('alte_steine_in_oeffnung')})")
    _, _, keil2, info2, *_ = lauf(keil=False)
    pruef(len(keil2) == 0, f"Putzbogen ohne Fugen: keine Keilsteine ({info2.get('grund')})")
    _, _, keil3, info3, *_ = lauf(quader_bis_innen=True)
    pruef(len(keil3) == 0, f"Quader bis an den Bogen (keine radialen Fugen): keine Keilsteine ({info3.get('grund', info3.get('keilsteine'))})")
    print(f"test_keilsteine: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
