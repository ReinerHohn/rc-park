#!/usr/bin/env python3
"""laserdach.py - Dach eines Gebaeudeteils als HOEHENFELD direkt aus dem DOM1-Laser (1-m-Raster), statt einer angepassten Dachform.

Warum (16.11.2026, Schwabentor-Nachbarhaus, Fluegel = LoD2-Teil 0): die Formanpassung (Sattel, RMS 1,1 m, 'nicht eindeutig') stellte ein 21,7 m hohes
Satteldach ueber den ganzen Teil - in Wirklichkeit ein verwinkeltes Dach mit Traufe ~10-14 m; die hohe Giebelwand verdeckte im Modell den halben
Fachwerkgiebel. Vom Boden ist das Dach nicht zu sehen (Fotos/Wolke blind), der Laser sieht es von oben. Also: Laserhoehe je Rasterpunkt (bilinear aus den
1-m-Pixeln) als Deckflaeche, Grundriss = LoD2-Polygon. Grob (1 m), aber ohne erfundene Form. Kanten/Traufen bleiben Foto-Aufgabe.
  from laserdach import laserdach_koerper;  k = laserdach_koerper(OBJ, polygon_uv, px=0.5)      -> manifold3d.Manifold (wasserdicht), z ab 0
"""
import os, sys, json, numpy as np


def prisma(polygon_uv, hoehe):
    """Grundriss-Polygon (beliebiger Umlaufsinn, fast doppelte Ecken erlaubt) zu einem Prisma z 0..hoehe. Im Uhrzeigersinn liefert manifold3d sonst 'InvalidConstruction'
    (16.11.2026: dadurch wurde das ganze Nachbarhaus leer)."""
    from manifold3d import Manifold, CrossSection
    P = np.asarray(polygon_uv, float); Q = [P[0]]
    for p_ in P[1:]:
        if np.linalg.norm(p_ - Q[-1]) > 0.05: Q.append(p_)
    if np.linalg.norm(Q[-1] - Q[0]) <= 0.05: Q.pop()
    Q = np.array(Q); fl = 0.5 * float(np.sum(Q[:, 0] * np.roll(Q[:, 1], -1) - np.roll(Q[:, 0], -1) * Q[:, 1]))
    return Manifold.extrude(CrossSection([(Q if fl > 0 else Q[::-1]).tolist()]), hoehe)


def laserdach_koerper(objekt_json, polygon_uv, px=0.5, zmin=2.5, aufmass=0.03):
    from manifold3d import Manifold, Mesh, CrossSection
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from dom1_kachel import dom1_hoehe
    obj = json.load(open(objekt_json)); r = obj["rahmen"]; m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float); g0 = float(r["gelaende"])
    P = np.asarray(polygon_uv, float); x0, y0 = P.min(0) - 1.0; x1, y1 = P.max(0) + 1.0; xs = np.arange(x0, x1 + px, px); ys = np.arange(y0, y1 + px, px); Z = np.zeros((len(xs), len(ys)))
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            E, N = m0 + x * xh + y * yh; e0, n0 = np.floor(E - 0.5) + 0.5, np.floor(N - 0.5) + 0.5; fe, fn = E - e0, N - n0; v = []
            for de, dn, w in ((0, 0, (1 - fe) * (1 - fn)), (1, 0, fe * (1 - fn)), (0, 1, (1 - fe) * fn), (1, 1, fe * fn)):
                try: v.append((float(dom1_hoehe(e0 + de, n0 + dn, "dom1")) - g0, w))
                except Exception: pass
            Z[i, j] = sum(h * w for h, w in v) / max(sum(w for _, w in v), 1e-9) if v else zmin
    Z = np.maximum(np.nan_to_num(Z, nan=zmin, posinf=zmin, neginf=zmin), zmin); nx, ny = Z.shape; ii, jj = np.mgrid[0:nx, 0:ny]; X = xs[ii]; Y = ys[jj]      # Laser ohne Wert (NaN) -> Mindesthoehe; NaN-Ecken machten den Koerper ungueltig
    V = np.r_[np.c_[X.ravel(), Y.ravel(), Z.ravel()], np.c_[X.ravel(), Y.ravel(), np.zeros(nx * ny)]]; N_ = nx * ny; idx = ii * ny + jj
    q00, q01, q10, q11 = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    F = [np.c_[q00, q10, q01], np.c_[q01, q10, q11], np.c_[q00 + N_, q01 + N_, q10 + N_], np.c_[q01 + N_, q11 + N_, q10 + N_]]
    ring = np.r_[idx[0, :-1], idx[:-1, -1], idx[-1, :0:-1], idx[:0:-1, 0]]; r2 = np.roll(ring, -1); F += [np.c_[ring, r2, ring + N_], np.c_[r2, r2 + N_, ring + N_]]; F = np.vstack(F).astype(np.uint32)
    k = Manifold(Mesh(vert_properties=V.astype(np.float32), tri_verts=F))
    if k.volume() < 0: k = Manifold(Mesh(vert_properties=V.astype(np.float32), tri_verts=F[:, ::-1].copy()))
    sp_ = P.mean(0); Q = sp_ + (P - sp_) * (1.0 + aufmass / max(float(np.linalg.norm(P - sp_, axis=1).mean()), 1e-6))     # wenige cm Aufmass: deckungsgleiche Flaechen mit dem ausgeschnittenen Grundriss gaben Splitterkoerper
    return k ^ prisma(Q, float(Z.max()) + 5.0)
