#!/usr/bin/env python3
"""relief_einsatz.py - Relief-Einsatz aus dem Scan-Netz fuer eine Generatorwand (Nutzerentscheidung 15.11.2026 nach tools/relief_test.py).

Die WAND (Lage, Kanten, Oeffnungen) bleibt Sache des Generators. Aus dem Netz kommt nur das Hoehenbild d(u, z) VOR der Wandebene, als duenne Platte.
  Erzeugen:  relief_einsatz.py <netz.npz> <aus.npz> --ecke_a x y --ecke_b x y --aussen x y --feld u0 u1 z0 z1 [--px 0.04] [--klemme -0.08 0.15]
     netz.npz: V (Modellrahmen), F. Wandebene = senkrecht durch a, b; 'aussen' = Punkt vor der Wand (legt die Normale fest); Feld in u (ab a Richtung b) und z.
     Hoehenbild = Maximum je Zelle, Nadelloecher aus Nachbarn, groessere Loecher = 0 (glatte Wand), Ebenentrend abgezogen, Median = 0, geklemmt.
     aus.npz: rel (H x W, m), a, t, n, u0, z0, px, lochanteil, hub_p5_p95. Dazu aus.jpg (Schattierung) zum Ansehen.
  Im Generator:  from relief_einsatz import koerper;  k = koerper("modelle/<obj>/relief/<name>.npz", tiefe=0.06)   -> manifold3d.Manifold (wasserdicht),
     Platte von 'tiefe' HINTER der Wandebene bis zum Relief davor; mit dem Wandkoerper vereinigen. Rand laeuft auf die Wandebene aus (2 Zellen).
"""
import sys, os, argparse, numpy as np


def koerper(npz, tiefe=0.06, faktor=1.0, sockel=0.005, null_felder=(), trend=False, versatz=0.0, tief_felder=()):
    from manifold3d import Manifold, Mesh
    Z = np.load(npz); rel = Z["rel"].astype(np.float64) * faktor; H, W = rel.shape; a = Z["a"]; t = Z["t"]; n = Z["n"]; u0, z0, px = float(Z["u0"]), float(Z["z0"]), float(Z["px"])
    ii, jj = np.mgrid[0:H, 0:W]; niv = float(Z["putz_niveau_m"]) if "putz_niveau_m" in Z.files else 0.0      # Putzniveau (tools/relief_putz.py): Bauteilfelder im Putz liegen auf DIESER Hoehe, sonst zeichnet sich das Feld als Rechteck ab
    for f0, f1, g0, g1 in null_felder:                                   # Felder (u0, u1, z0, z1), in denen der Generator selbst ein scharfes Bauteil baut: Relief dort 0
        rel[(u0 + (jj + 0.5) * px >= f0) & (u0 + (jj + 0.5) * px <= f1) & (z0 + (H - 1 - ii + 0.5) * px >= g0) & (z0 + (H - 1 - ii + 0.5) * px <= g1)] = niv
    tief = np.zeros((H, W), bool)
    for f0, f1, g0, g1 in tief_felder:                                   # Felder, vor die ein FEINERER Einsatz gesetzt wird (tools/relief_mischen.py): Platte dort ganz zurueck, sonst fuellt sie dessen Fugen
        tief |= (u0 + (jj + 0.5) * px >= f0) & (u0 + (jj + 0.5) * px <= f1) & (z0 + (H - 1 - ii + 0.5) * px >= g0) & (z0 + (H - 1 - ii + 0.5) * px <= g1)
    rand = np.minimum.reduce([ii, jj, H - 1 - ii, W - 1 - jj]); rel = rel * np.clip(rand / 2.0, 0, 1)        # Rand auf 0 auslaufen
    if trend:                                                             # 15.11.2026: Wandanzug/Lage der Netzflaeche wieder aufschlagen (Nutzerbild: Wolke stand 0,15-0,3 m VOR der Modellfassade)
        tu, tz = [float(v) for v in Z["trend_je_m"]]; rel = rel + float(Z["ebene_abstand_m"]) + versatz + tu * (jj + 0.5) * px - tz * (ii + 0.5) * px   # d(u, z) der Ausgleichsebene; ii laeuft nach unten
    # sockel: Platte steht ueberall etwas vor der Wandebene - deckungsgleiche Flaechen mit der Wand ergeben Splitter (STL nicht wasserdicht, 656 Koerper)
    rel[tief] = -tiefe + 0.01; rel = np.maximum(rel, -tiefe + 0.01) + sockel; u = u0 + (jj + 0.5) * px; z = z0 + (H - 1 - ii + 0.5) * px
    def P(d): return np.c_[(a[0] + u * t[0] + d * n[0]).ravel(), (a[1] + u * t[1] + d * n[1]).ravel(), z.ravel()]
    V = np.r_[P(rel), P(np.full_like(rel, -tiefe))]; N = H * W; idx = (ii * W + jj)
    q00, q01, q10, q11 = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    F = [np.c_[q00, q10, q01], np.c_[q01, q10, q11], np.c_[q00 + N, q01 + N, q10 + N], np.c_[q01 + N, q11 + N, q10 + N]]
    ring = np.r_[idx[0, :-1], idx[:-1, -1], idx[-1, :0:-1], idx[:0:-1, 0]]; r2 = np.roll(ring, -1)                      # Rand im Uhrzeigersinn (von aussen gesehen)
    F += [np.c_[ring, r2, ring + N], np.c_[r2, r2 + N, ring + N]]; F = np.vstack(F).astype(np.uint32)
    m = Manifold(Mesh(vert_properties=V.astype(np.float32), tri_verts=F))
    if m.volume() < 0: m = Manifold(Mesh(vert_properties=V.astype(np.float32), tri_verts=F[:, ::-1].copy()))
    return m


def main():
    import cv2
    ap = argparse.ArgumentParser(); ap.add_argument("netz"); ap.add_argument("aus"); ap.add_argument("--ecke_a", nargs=2, type=float, required=True); ap.add_argument("--ecke_b", nargs=2, type=float, required=True)
    ap.add_argument("--aussen", nargs=2, type=float, required=True); ap.add_argument("--feld", nargs=4, type=float, required=True); ap.add_argument("--px", type=float, default=0.04)
    ap.add_argument("--klemme", nargs=2, type=float, default=[-0.08, 0.15]); ap.add_argument("--band", type=float, default=0.6, help="Suchtiefe +- um die Ebene (m); fuer Auskragungen/Erker groesser waehlen"); a = ap.parse_args()
    A = np.array(a.ecke_a); B = np.array(a.ecke_b); t = (B - A) / np.linalg.norm(B - A); n = np.array([t[1], -t[0]]); n = n if (np.array(a.aussen) - A) @ n > 0 else -n
    u0, u1, z0, z1 = a.feld; px = a.px; W = int(round((u1 - u0) / px)); H = int(round((z1 - z0) / px))
    Z = np.load(a.netz); tri = Z["V"].astype(np.float64)[Z["F"]]; c = tri.mean(1); uu = (c[:, :2] - A) @ t; dd = (c[:, :2] - A) @ n
    hi_ = (uu > u0) & (uu < u1) & (dd < -a.band) & (dd > -a.band - 6.0) & (c[:, 2] > z0) & (c[:, 2] < z1)      # Netz HINTER dem Band: dort ist die Wand offen (Tor, Laube, Nische) - nicht Verdeckung
    hinten = np.zeros((H, W), bool); hinten[np.clip((H - 1 - (c[hi_, 2] - z0) / px).astype(int), 0, H - 1), np.clip(((uu[hi_] - u0) / px).astype(int), 0, W - 1)] = True
    tri = tri[(uu > u0 - 0.1) & (uu < u1 + 0.1) & (np.abs(dd) < a.band) & (c[:, 2] > z0 - 0.1) & (c[:, 2] < z1 + 0.1)]
    w = np.random.default_rng(0).dirichlet((1, 1, 1), (len(tri), 12)); P = (w[:, :, :, None] * tri[:, None, :, :]).sum(2).reshape(-1, 3)
    uu = (P[:, :2] - A) @ t; dd = (P[:, :2] - A) @ n; iu = ((uu - u0) / px).astype(int); iv = (H - 1 - (P[:, 2] - z0) / px).astype(int); g = (iu >= 0) & (iu < W) & (iv >= 0) & (iv < H)
    hm = np.full((H, W), -9, np.float32); np.maximum.at(hm, (iv[g], iu[g]), dd[g].astype(np.float32)); loch = hm < -5; roh = float(loch.mean())
    fl = cv2.dilate(hm, np.ones((3, 3), np.uint8)); hm[loch] = fl[loch]; loch = hm < -5
    yy, xx = np.mgrid[0:H, 0:W]; G = np.c_[xx[~loch], yy[~loch], np.ones((~loch).sum())]; ko = np.linalg.lstsq(G, hm[~loch], rcond=None)[0]
    rel = hm - (ko[0] * xx + ko[1] * yy + ko[2]); rel -= np.median(rel[~loch]); rel[loch] = 0.0; q5, q95 = np.percentile(rel[~loch], [5, 95]); rel = np.clip(rel, a.klemme[0], a.klemme[1])
    oeffnung = loch & cv2.morphologyEx(cv2.dilate(hinten.astype(np.uint8), np.ones((5, 5), np.uint8)), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool)   # Loch UND Netz dahinter = Oeffnung (15.11.: steine_generieren laesst sie aus)
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True)
    np.savez_compressed(a.aus, rel=rel.astype(np.float32), a=A, t=t, n=n, u0=u0, z0=z0, px=px, oeffnung=oeffnung, lochanteil=float(loch.mean()), lochanteil_roh=roh, hub_p5_p95=float(q95 - q5), ebene_abstand_m=float(ko[2]),
                        trend_je_m=np.array([ko[0] / px, -ko[1] / px]))
    lx = np.gradient(rel, px, axis=1); lz = np.gradient(rel, px, axis=0); s = np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1); im = cv2.cvtColor((s * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR); im[loch] = (0, 0, 255)
    cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", cv2.resize(im, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    print(f"{os.path.basename(a.aus)}: {W}x{H} Zellen a {px*100:.0f} cm, Loecher {loch.mean()*100:.2f} % (roh {roh*100:.1f} %), Hub p5-p95 {(q95-q5)*100:.1f} cm = {(q95-q5)*1000/87:.2f} mm bei 1:87, "
          f"Netzflaeche im Mittel {ko[2]*100:+.1f} cm vor der Ebene, Trend {ko[0]/px*100:+.1f} cm/m entlang u, {-ko[1]/px*100:+.1f} cm/m nach oben")


if __name__ == "__main__":
    main()
