#!/usr/bin/env python3
"""dach_profil_wolke.py - DACH ALS SCHICHTPROFIL AUS DER DICHTEN WOLKE (Ueberstand, Neigung, Laterne ohne Musterteil), 21.11.2026.

Anlass: tools/wolke_rest.py zeigte am Schwabentor einen Ring der Wolke um die Traufe (z 37-46) und einen Haufen ueber der Spitze - das Modelldach (LoD2 + Laser) hat keinen
Ueberstand und keine Laterne. Im Handlauf kam das Dach aus vier gemessenen Traufecken + Laterne aus Fotomassen; hier ohne Vorwissen:
  1. Rahmen = Richtung der groessten Fassade (fassaden.json: d, n), Achse = Mitte des Modells knapp unter dem Dach.
  2. Je Hoehenscheibe (--schritt 0,5 m) die Ausdehnung der Wolke in +-d und +-n (2./98. Perzentil, nur Punkte bis --rand um die vorige Scheibe -> Ausreisser/Nachbardach fallen weg).
  3. DACHBEGINN z0 = unterste Scheibe, in der die Wolke mindestens --ueber (0,3 m) ueber das Modell hinaussteht ODER das Modell schmaler wird (Dachfuss), frueheste von beiden.
  4. Ende, wo die Wolke weniger als --min_p Punkte je Scheibe hat (Spitze/Knauf fehlen dann - im Bericht).
Ausgabe audit/dach_profil.json {o (Achse), d, n, z0, scheiben [[z, u_lo, u_hi, v_lo, v_hi, punkte]]} -> bauteile.dach_aus_profil (Modell ueber z0 abtragen, Schichtkoerper aufsetzen).
Kernmethode: die Wolke gibt die GROBE Dachform (Kanten koennen Ziegelflaechen nicht); Traufkanten danach aus Fotokanten nachmessen (offen).
Aufruf: dach_profil_wolke.py <objekt.json> <wolke.npy> <fassaden.json> [--stl S]
"""
import sys, os, json, argparse, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("wolke"); ap.add_argument("fassaden"); ap.add_argument("--stl"); ap.add_argument("--schritt", type=float, default=0.5); ap.add_argument("--min_p", type=int, default=80)
    ap.add_argument("--rand", type=float, default=0.7); ap.add_argument("--ueber", type=float, default=0.3); a = ap.parse_args()
    import trimesh
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); stl = a.stl or os.path.join(ROOT, obj["stl"]); m = trimesh.load(stl); m.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    F = max(json.load(open(a.fassaden))["fassaden"], key=lambda f: f.get("flaeche_m2", 0)); d = np.array(F["d"], float); n = np.array(F["n"], float); S = np.asarray(m.sample(1200000)); zt = float(S[:, 2].max())
    # Hauptkoerper = oberstes Drittel; Achse = Mitte seiner Wandscheibe in halber Hoehe dieses Drittels (Anbauten/Nachbarn liegen tiefer)
    zb = zt * 0.62; s = (S[:, 2] > zb) & (S[:, 2] < zb + 2.0); c = (np.percentile(S[s][:, :2], 2, 0) + np.percentile(S[s][:, :2], 98, 0)) / 2
    uv = lambda P: ((P[:, :2] - c) @ d, (P[:, :2] - c) @ n)
    W = np.asarray(np.load(a.wolke, mmap_mode="r")[:, :3]); W = W[W[:, 2] > zb]; wu, wv = uv(W); su, sv = uv(S)

    def aus(u, v, z, z0, g=None):
        k = (z >= z0) & (z < z0 + a.schritt)
        if g is not None: k &= (u > g[0] - a.rand) & (u < g[1] + a.rand) & (v > g[2] - a.rand) & (v < g[3] + a.rand)
        if k.sum() < a.min_p: return None
        return [float(np.percentile(u[k], 2)), float(np.percentile(u[k], 98)), float(np.percentile(v[k], 2)), float(np.percentile(v[k], 98)), int(k.sum())]
    wand = aus(su, sv, S[:, 2], zb); z0 = None; Z = np.arange(zb, zt + 8.0, a.schritt); g = [wand[0] - 2.0, wand[1] + 2.0, wand[2] - 2.0, wand[3] + 2.0]
    for z in Z:                                                                              # Dachbeginn suchen
        mo = aus(su, sv, S[:, 2], z); wo = aus(wu, wv, W[:, 2], z, g)
        if mo is None or wo is None: continue
        if (wo[1] - wo[0]) - (mo[1] - mo[0]) > 2 * a.ueber or (wo[3] - wo[2]) - (mo[3] - mo[2]) > 2 * a.ueber or (mo[1] - mo[0]) < (wand[1] - wand[0]) - 0.4: z0 = float(z); break
    if z0 is None: print("kein Dachbeginn gefunden (Wolke steht nirgends ueber das Modell hinaus)"); return 3
    # Je Scheibe und SEITE (-d, +d, -n, +n) getrennt: Punkte im Sektor dieser Seite (dominante Richtung); Seite ohne Wolke (Dachflaeche von keinem Foto gesehen) -> Ausdehnung des
    # bisherigen Modells (LoD2 + Laser) in dieser Hoehe, als 'modell' vermerkt (ANNAHME, nicht gespiegelt). Erste Fassung nahm Perzentile ueber alle Punkte: die Sued-Dachflaeche
    # fehlt in der Wolke, das Profil wanderte auf die Nordflaeche (halbe Breite 0,6 m, Mitte +4,7 m).
    P = []; g = [wand[0] - 2.0, wand[1] + 2.0, wand[2] - 2.0, wand[3] + 2.0]; leer = 0; n_mod = 0
    def schale(q):                                                                           # AEUSSERSTE DICHTE Schale statt 97. Perzentil: Rauschpunkte vor der Dachflaeche blaehten das Profil auf
        h, k = np.histogram(q, bins=np.arange(float(q.min()), float(q.max()) + 0.2, 0.1)); i = np.nonzero(h >= max(0.3 * h.max(), 3))[0][-1]; return float(k[i] + 0.05)   # (1. Bau: Wolke am Modell 70 -> 68 %, Dachlinie der Wolke lag IM Modell)
    def seiten(u, v, z, z0, g, mp):
        k = (z >= z0) & (z < z0 + a.schritt); u, v = u[k], v[k]; r = []
        for co, ot, vz, gi in ((u, v, -1, 0), (u, v, 1, 1), (v, u, -1, 2), (v, u, 1, 3)):
            q = co[(vz * co > np.abs(ot)) & (vz * co < vz * g[gi] + a.rand)]; r.append(schale(vz * q) * vz if len(q) >= mp else None)
        return r, int(k.sum())
    for z in np.arange(z0, zt + 8.0, a.schritt):
        wo, nw = seiten(wu, wv, W[:, 2], z, g, max(a.min_p // 4, 15)); mo, _ = seiten(su, sv, S[:, 2], z, [-99, 99, -99, 99], 50); que = []
        for i in range(4):
            if wo[i] is None and mo[i] is not None: wo[i] = mo[i]; que.append("-d +d -n +n".split()[i]); n_mod += 1
        if any(x is None for x in wo) or wo[1] - wo[0] < 0.1 or wo[3] - wo[2] < 0.1:
            leer += 1
            if leer >= 2: break
            continue
        leer = 0; P.append([round(float(z), 2)] + [round(x, 3) for x in wo] + [nw, que]); g = wo
    # Seite ohne Wolke: NICHT das alte Modelldach (lag am Schwabentor ~2 m zu tief/1,5 m zu schmal -> schiefes Dach), sondern Gegenseite an der GEMESSENEN Achse gespiegelt:
    # Achse je Richtung = Median der Mitten aller Scheiben, in denen beide Seiten aus der Wolke kommen. Bleibt ANNAHME (im Bericht + Fotoauftrag), Modellwert nur ohne Gegenseite.
    cu = float(np.median([(p[1] + p[2]) / 2 for p in P if "-d" not in p[6] and "+d" not in p[6]] or [0.0])); cv_ = float(np.median([(p[3] + p[4]) / 2 for p in P if "-n" not in p[6] and "+n" not in p[6]] or [0.0])); n_sp = 0
    for p in P:
        for nm, i, j, cc in (("-d", 1, 2, cu), ("+d", 2, 1, cu), ("-n", 3, 4, cv_), ("+n", 4, 3, cv_)):
            if nm in p[6] and nm.replace("-", "#").replace("+", "-").replace("#", "+") not in p[6]: p[i] = round(2 * cc - p[j], 3); n_sp += 1
    Q = np.array([p[1:5] for p in P]); G = Q.copy()
    for k in range(1, len(P) - 1): G[k] = np.median(Q[k - 1:k + 2], 0)                       # Median ueber 3 Scheiben: einzelne Ausreisser an der Traufe (97. Perzentil) glaetten
    for p, q in zip(P, G): p[1:5] = [round(float(x), 3) for x in q]
    if len(P) < 4: print(f"zu wenige Scheiben mit Wolke ueber z {z0:.1f} ({len(P)})"); return 3
    hb = lambda p: ((p[2] - p[1]) / 2, (p[4] - p[3]) / 2); e = hb(P[0]); mi = P[len(P) // 3]; em = hb(mi); nei = float(np.degrees(np.arctan2(mi[0] - P[1][0], max(hb(P[1])[0] - em[0], 1e-3))))
    print(f"Achse x {c[0]:.2f} y {c[1]:.2f}; Wand halb {(wand[1] - wand[0]) / 2:.2f} x {(wand[3] - wand[2]) / 2:.2f} m; Dachbeginn z {z0:.1f}: halb {e[0]:.2f} x {e[1]:.2f} m (Ueberstand {e[0] - (wand[1] - wand[0]) / 2:+.2f} / {e[1] - (wand[3] - wand[2]) / 2:+.2f} m)")
    print(f"{len(P)} Scheiben bis z {P[-1][0] + a.schritt:.1f} (Modell bisher bis {zt:.1f}); Neigung unteres Drittel ~{nei:.0f} Grad; oberste Scheibe halb {hb(P[-1])[0]:.2f} x {hb(P[-1])[1]:.2f} m")
    A = os.path.join(od, "audit"); json.dump(dict(quelle="tools/dach_profil_wolke.py", wolke=a.wolke, o=[float(c[0]), float(c[1])], d=d.tolist(), n=n.tolist(), z0=z0, schritt=a.schritt, wand_halb=[(wand[1] - wand[0]) / 2, (wand[3] - wand[2]) / 2],
                                                 modell_hoehe_vorher=zt, seiten_aus_modell=n_mod, seiten_gespiegelt=n_sp, achse_uv=[cu, cv_], neigung_grad=round(nei, 1), scheiben=P), open(os.path.join(A, "dach_profil.json"), "w"), indent=1)
    print(f"Seiten ohne Wolke (ANNAHME): {n_mod} von {4 * len(P)}, davon {n_sp} an der gemessenen Achse (u {cu:+.2f}, v {cv_:+.2f}) gespiegelt"); print("->", os.path.join(A, "dach_profil.json")); return 0


if __name__ == "__main__": sys.exit(main())
