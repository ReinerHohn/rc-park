#!/usr/bin/env python3
"""flaeche_oder_oeffnung.py - Regel "Flaeche vs. Oeffnung" (Nutzer 9.11.): je Flaechenhypothese (Erdgeschoss-Front, Stirnwaende, Laubenrueckwand) Raster 0,5 m;
je Zelle Wolkenpunkte AUF der Flaeche (|d| < 15 cm) gegen Punkte HINTER der Flaeche (bis 8 m), deren Sehstrahl von einer Kamera VOR der Flaeche die Zelle durchstoesst.
Da die Wolke keine Kamera-Zuordnung je Punkt traegt (kanten3d: vis/kan = Stimmzahlen), zaehlt jeder Punkt insgesamt 1 Stimme, verteilt auf die Zellen, die seine Strahlen
zu allen Kameras vor der Flaeche (< 45 m) durchstossen (ANNAHME Sichtbarkeit). Verhaeltnis hinter/auf > 3 -> Oeffnung; auf >= 3 und Verhaeltnis <= 3 -> Wand; sonst unentschieden.
Aufruf (venv-seg, GPU): flaeche_oder_oeffnung.py WOLKE.npz KAM.json ROH.json KOERPER_v10.json AUS.json [--zell 0.5]"""
import sys, os, json, math
import numpy as np, torch

a = sys.argv; ZELL = float(a[a.index("--zell") + 1]) if "--zell" in a else 0.5
P = torch.from_numpy(np.load(a[1])["P"].astype(np.float32)).cuda(); KAM = json.load(open(a[2])); A = json.load(open(a[3])); D = json.load(open(a[4]))
u = torch.tensor(A["u"], dtype=torch.float32).cuda(); n = torch.tensor(A["n"], dtype=torch.float32).cuda(); ez = torch.tensor([0, 0, 1.0]).cuda()
of = A["off_front"]; ol = A["off_laube"]; zb = A["z_boden"]; zp0 = D["balkon"]["platte"]["z0"]; aw_u, ae_u = D["rumpf_unten_along"]
C_all = torch.tensor([k["C"] for k in KAM.values()], dtype=torch.float32).cuda()


def test(name, origin_val, normal, ax1, ax2, r1, r2, tiefe=8.0):
    """Flaeche: normal . X = origin_val (normal zeigt nach AUSSEN = zur Kamera-Seite); Zellen entlang ax1 (r1) und ax2 (r2)."""
    d = P @ normal - origin_val; auf_m = d.abs() < 0.15; hinter_m = (d < -0.15) & (d > -tiefe)
    c1 = P @ ax1; c2 = P @ ax2; inner = (c1 >= r1[0]) & (c1 < r1[1]) & (c2 >= r2[0]) & (c2 < r2[1])
    n1 = int(math.ceil((r1[1] - r1[0]) / ZELL)); n2 = int(math.ceil((r2[1] - r2[0]) / ZELL))
    def idx(x1, x2): return ((x1 - r1[0]) / ZELL).long().clamp(0, n1 - 1) * n2 + ((x2 - r2[0]) / ZELL).long().clamp(0, n2 - 1)
    auf = torch.zeros(n1 * n2, device="cuda"); auf.index_add_(0, idx(c1[auf_m & inner], c2[auf_m & inner]), torch.ones(int((auf_m & inner).sum()), device="cuda"))
    # Kameras vor der Flaeche, nahe am Feld
    mitte = ax1 * float(np.mean(r1)) + ax2 * float(np.mean(r2)) + normal * (origin_val - float((ax1 @ normal) * np.mean(r1) + (ax2 @ normal) * np.mean(r2)))
    cm = ((C_all @ normal - origin_val) > 0.5) & ((C_all - mitte).norm(dim=1) < 45.0); C = C_all[cm]
    hinter = torch.zeros(n1 * n2, device="cuda"); Q = P[hinter_m]; Q = Q[torch.randperm(len(Q), device="cuda")[:200000]]
    for i in range(0, len(Q), 2048):
        q = Q[i:i + 2048]; V = q[:, None, :] - C[None, :, :]; den = V @ normal; t = (origin_val - (C @ normal))[None, :] / den
        ok = (t > 0) & (t < 1) & (den < 0); X = C[None] + t[..., None] * V; x1 = X @ ax1; x2 = X @ ax2
        ok &= (x1 >= r1[0]) & (x1 < r1[1]) & (x2 >= r2[0]) & (x2 < r2[1]); w = ok.float() / ok.float().sum(1, keepdim=True).clamp(min=1)
        hinter.index_add_(0, idx(x1[ok], x2[ok]), w[ok])
    auf = auf.view(n1, n2).cpu().numpy(); hinter = hinter.view(n1, n2).cpu().numpy(); ratio = hinter / np.maximum(auf, 1)
    kl = np.full(auf.shape, "unentschieden", dtype=object); kl[(ratio > 3) & (hinter >= 3)] = "oeffnung"; kl[(auf >= 3) & (ratio <= 3)] = "wand"
    # zusammenhaengende Oeffnungsfelder (4er-Nachbarschaft) -> Bounding-Boxen
    seen = np.zeros(auf.shape, bool); komp = []
    for i in range(n1):
        for j in range(n2):
            if kl[i, j] != "oeffnung" or seen[i, j]: continue
            st = [(i, j)]; seen[i, j] = True; cells = []
            while st:
                p, q = st.pop(); cells.append((p, q))
                for dp, dq in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    pp, qq = p + dp, q + dq
                    if 0 <= pp < n1 and 0 <= qq < n2 and not seen[pp, qq] and kl[pp, qq] == "oeffnung": seen[pp, qq] = True; st.append((pp, qq))
            ii = [c[0] for c in cells]; jj = [c[1] for c in cells]
            komp.append({"zellen": len(cells), "ax1": [r1[0] + min(ii) * ZELL, r1[0] + (max(ii) + 1) * ZELL], "ax2": [r2[0] + min(jj) * ZELL, r2[0] + (max(jj) + 1) * ZELL],
                         "hinter": float(sum(hinter[c] for c in cells)), "auf": float(sum(auf[c] for c in cells))})
    komp.sort(key=lambda k: -k["zellen"])
    erg = {"name": name, "zelle_m": ZELL, "n_kameras_vor": int(cm.sum()), "n_punkte_hinter": int(hinter_m.sum()), "n_punkte_auf": int((auf_m & inner).sum()),
           "ax1_bereich": list(r1), "ax2_bereich": list(r2), "auf": auf.round(1).tolist(), "hinter": hinter.round(1).tolist(), "klasse": kl.tolist(),
           "anteil": {k: float((kl == k).mean()) for k in ("oeffnung", "wand", "unentschieden")}, "oeffnungen": komp}
    print(f"{name}: Kameras vor {int(cm.sum())}, Punkte auf {erg['n_punkte_auf']}, hinter {erg['n_punkte_hinter']}; Zellen Oeffnung {erg['anteil']['oeffnung']:.2f} Wand {erg['anteil']['wand']:.2f} unentschieden {erg['anteil']['unentschieden']:.2f}")
    for k in komp[:8]: print(f"   Oeffnung {k['zellen']} Zellen ax1 {np.round(k['ax1'], 1).tolist()} ax2 {np.round(k['ax2'], 1).tolist()} hinter/auf {k['hinter']:.0f}/{k['auf']:.0f}")
    # Textbild: Zeilen = ax2 (z) von oben, Spalten = ax1
    zeich = {"oeffnung": ".", "wand": "#", "unentschieden": "?"}
    for j in range(n2 - 1, -1, -1): print("   z%5.1f |" % (r2[0] + j * ZELL) + "".join(zeich[kl[i, j]] for i in range(n1)) + "|")
    return erg


aus = {"regel": "hinter/auf > 3 und hinter >= 3 -> oeffnung; auf >= 3 und <= 3 -> wand; sonst unentschieden; Strahlen zu allen Kameras vor der Flaeche (< 45 m), Stimme je Punkt = 1 (ANNAHME Sichtbarkeit)", "flaechen": []}
aus["flaechen"].append(test("front_eg", of, n, u, ez, (aw_u, ae_u), (zb, zp0)))
aus["flaechen"].append(test("rueckwand_laube", ol, n, u, ez, (aw_u, ae_u), (zb, zp0)))
lo, hi = sorted([ol, of])
aus["flaechen"].append(test("stirn_minus", -aw_u, -u, n, ez, (lo, hi), (zb, zp0)))
aus["flaechen"].append(test("stirn_plus", ae_u, u, n, ez, (lo, hi), (zb, zp0)))
json.dump(aus, open(a[5], "w"), indent=1); print("->", a[5])
