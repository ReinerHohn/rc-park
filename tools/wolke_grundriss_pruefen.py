#!/usr/bin/env python3
"""wolke_grundriss_pruefen.py - GENERISCH: Dichte Wolke (Modellrahmen) gegen die amtlichen LoD2-Grundrisse der Umgebung pruefen.

Lehre Schwabentor 2026-11-14: Ein ganzes Haus (Fluegel, 205 000 Punkte) lag in der Wolke AUF DER STRASSE, ausserhalb jedes
LoD2-Gebaeudes. Es wurde einen Tag lang per Augenmass, Farbtests und Reglern 'verschoben', statt einmal die Grundrisse darueber
zu legen. Ursachen: (1) Kamerakranz nur auf einer Halbebene (Luecke > 100 Grad, tools/kamera_abdeckung.py), (2) Turm von
mehreren Seiten aehnlich -> Gruppen/Zusatzfotos auf der falschen Seite registriert, (3) LoD2-Ausrichtung knapp
(beste 22,2 % Inlier gegen zweitbeste 19,4 %), niemand hat den Abstand gewertet.

Was das Werkzeug prueft (alles im Modellrahmen = objekt.json 'rahmen'):
  A  STRASSE: Anteil der Wandpunkte (Hoehe 1,5..9 m ueber Gelaende) ausserhalb aller LoD2-Grundrisse und > --wandabstand
     von jeder LoD2-Wand. Zusammenhaengende Haufen (1-m-Raster) werden mit Lage, Groesse und Punktzahl gelistet.
     Ein Haufen > --haufen Punkte auf der Strasse = WARNUNG (falsch verortetes Teilnetz oder Baum/Auto - am Foto klaeren).
  B  EINDEUTIGKEIT: Wandpunkte per FFT-Korrelation gegen die LoD2-Wandlinien, Drehung 0..359 Grad, mit und ohne Spiegelung.
     Verglichen werden die aktuelle Lage (Identitaet) und die beste Alternative (> 15 Grad weg oder gespiegelt).
     Alternative besser als aktuelle Lage, oder Abstand < --abstand (relativ) = HINWEIS (kein Tor: warnt auch am richtig liegenden Kaufhaus).
     Rueckgabe: 0 ok, 3 = Haufen auf der Strasse (Tor).
Quellen-Blindheit: LoD2 kennt keine Erker, Arkaden, Vordaecher, Baeume, Autos - Punkte dort landen in A als 'Strasse'.
Deshalb wird nur gewarnt und gelistet; die Entscheidung faellt am Foto (tools/foto_diff.py, Ueberlagerung).

  /media/oem/scan/venv-seg/bin/python -I tools/wolke_grundriss_pruefen.py modelle/<objekt>/objekt.json --wolke <punkte_modell.npy> [--radius 60]
Ausgabe: modelle/<objekt>/audit/wolke_grundriss.json und audit/wolke_grundriss.png; Exit 0 = ok, 3 = Strasse-Warnung, 4 = Lage nicht eindeutig (4 hat Vorrang).
"""
import sys, os, json, argparse, hashlib, pickle
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as LG

CACHE = "/media/oem/scan/rc-park_daten/_cache"


def grundrisse(obj, radius):
    r = obj["rahmen"]; m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float)
    gml = obj.get("_gml") or obj.get("lod2", {}).get("gml")
    if not gml or not os.path.exists(gml):                                   # Kachel per UTM suchen (LGL: LoD2_32_<E km>_<N km>_1_BW.gml)
        import glob
        hit = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/LoD2_32_{int(m0[0] // 1000)}_{int(m0[1] // 1000)}_1_BW.gml", recursive=True)
        if not hit: sys.exit(f"LoD2-GML fehlt ({gml}) und keine Kachel unter _geo gefunden - --gml angeben")
        print(f"LoD2: {gml} fehlt, nehme Kachel {hit[0]}"); gml = hit[0]
    st = os.stat(gml)
    k = hashlib.sha1(f"grund|{gml}|{st.st_size}|{int(st.st_mtime)}|{m0.tolist()}|{radius}".encode()).hexdigest()[:16]
    cp = os.path.join(CACHE, f"lod2_grund_{k}.pkl")
    if os.path.exists(cp):
        B = pickle.load(open(cp, "rb"))
    else:
        B = []
        for meta, polys in LG.extract(gml, center=tuple(m0), radius=radius):
            B.append(dict(id=meta["id"], ground=[P[:, :2] for t, P in polys if t == "GroundSurface"]))
        os.makedirs(CACHE, exist_ok=True); pickle.dump(B, open(cp, "wb"))
    tm = lambda U: np.c_[(U - m0) @ xh, (U - m0) @ yh]
    return [dict(id=b["id"], ground=[tm(g) for g in b["ground"]]) for b in B]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--radius", type=float, default=60.0)
    ap.add_argument("--wandabstand", type=float, default=1.5); ap.add_argument("--haufen", type=int, default=5000)
    ap.add_argument("--abstand", type=float, default=0.15); ap.add_argument("--zelle", type=float, default=0.25)
    ap.add_argument("--max_verschiebung", type=float, default=8.0, help="m; FFT-Treffer weiter weg passen auf Nachbarhaeuser (Schwabentor: 52 m), nicht zaehlen")
    ap.add_argument("--gml", default="", help="LoD2-GML statt objekt.json lod2.gml")
    a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    if a.gml: obj["_gml"] = a.gml
    B = grundrisse(obj, a.radius)
    from matplotlib.path import Path
    polys = [g for b in B for g in b["ground"] if len(g) >= 3]
    segs = []
    for g in polys:
        q = np.vstack([g, g[:1]])
        for p0, p1 in zip(q[:-1], q[1:]):
            n = max(2, int(np.linalg.norm(p1 - p0) / 0.1)); segs.append(p0 + np.linspace(0, 1, n)[:, None] * (p1 - p0))
    W = np.vstack(segs)
    X = np.load(a.wolke).astype(float)
    band = (X[:, 2] > 1.5) & (X[:, 2] < 9) & (np.hypot(X[:, 0], X[:, 1]) < a.radius * 0.8)
    Q = X[band][:, :2]
    # --- A: Strasse
    innen = np.zeros(len(Q), bool)
    for g in polys:
        innen |= Path(g).contains_points(Q)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gpu_knn import min_abstand   # GPU (Nutzerregel)
    z0 = lambda P: np.c_[P, np.zeros(len(P))]
    dwand = min_abstand(z0(Q), z0(W))
    strasse = ~innen & (dwand > a.wandabstand)
    gr = 1.0; ij = np.floor(Q[strasse] / gr).astype(int); haufen = []
    if len(ij):
        o = ij.min(0); sz = ij.max(0) - o + 1; G = np.zeros(sz[::-1], int); np.add.at(G, (ij[:, 1] - o[1], ij[:, 0] - o[0]), 1)
        lab, n = ndimage.label(G > 0, structure=np.ones((3, 3)))
        for k in range(1, n + 1):
            cnt = int(G[lab == k].sum())
            if cnt < 200: continue
            yy, xx = np.nonzero(lab == k)
            haufen.append(dict(punkte=cnt, mitte=[round(float((xx.mean() + o[0] + .5) * gr), 1), round(float((yy.mean() + o[1] + .5) * gr), 1)],
                               ausdehnung_m=[int(np.ptp(xx) + 1), int(np.ptp(yy) + 1)]))
        haufen.sort(key=lambda h: -h["punkte"])
    anteil = float(strasse.mean())
    # --- B: Eindeutigkeit (FFT, Drehung x Spiegelung)
    R = a.zelle; N = int(2 * a.radius / R); N += N % 2; half = N * R / 2
    def ras(p):
        g = np.zeros((N, N), np.float32); k = ((p + half) / R).astype(int); ok = (k >= 0).all(1) & (k < N).all(1); np.add.at(g, (k[ok, 1], k[ok, 0]), 1); return g
    import torch                                                             # FFT-Suche auf der GPU, alle 360 Drehungen je Spiegelung als Stapel
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cpu": print("WARNUNG: keine GPU, FFT laeuft auf CPU")
    L = ndimage.binary_dilation(ras(W) > 0, iterations=2).astype(np.float32)
    FL = torch.fft.rfft2(torch.as_tensor(L, device=dev))
    Qw = Q[~strasse]; ctr = Qw.mean(0); Qc = Qw - ctr
    g0 = np.minimum(ras(Qw), 5.0); ident = float((g0 * L).sum() / g0.sum())
    sh = torch.fft.fftfreq(N, d=1.0 / N, device=dev) * R                     # Verschiebung je FFT-Index (m)
    fenster = (sh[:, None] ** 2 + sh[None, :] ** 2) <= a.max_verschiebung ** 2
    res = []; Pt = torch.as_tensor(Qc, dtype=torch.float32, device=dev); ct = torch.as_tensor(ctr, dtype=torch.float32, device=dev)
    for sp in (0, 1):
        P0 = Pt * torch.tensor([-1.0 if sp else 1.0, 1.0], device=dev)
        for d0 in range(0, 360, 30):                                         # 30er-Stapel haelt VRAM klein
            degs = np.arange(d0, d0 + 30); t = torch.as_tensor(np.radians(degs), dtype=torch.float32, device=dev)
            c, s_ = torch.cos(t), torch.sin(t)
            X2 = (P0[None, :, 0] * c[:, None] - P0[None, :, 1] * s_[:, None]) + ct[0]
            Y2 = (P0[None, :, 0] * s_[:, None] + P0[None, :, 1] * c[:, None]) + ct[1]
            kx = ((X2 + half) / R).long(); ky = ((Y2 + half) / R).long(); ok = (kx >= 0) & (kx < N) & (ky >= 0) & (ky < N)
            b = torch.arange(len(degs), device=dev)[:, None].expand_as(kx)
            G = torch.zeros(len(degs) * N * N, device=dev)
            G.index_add_(0, (b * N * N + ky * N + kx)[ok], torch.ones(int(ok.sum()), device=dev))
            G = torch.clamp(G.view(len(degs), N, N), max=5.0)
            cc = torch.fft.irfft2(FL[None] * torch.conj(torch.fft.rfft2(G)), s=(N, N))
            cc = cc.masked_fill(~fenster, float("-inf"))
            mx, am = cc.view(len(degs), -1).max(1); su = G.view(len(degs), -1).sum(1)
            for i, deg in enumerate(degs):
                k0, k1 = divmod(int(am[i]), N); dy = (k0 if k0 < N / 2 else k0 - N) * R; dx = (k1 if k1 < N / 2 else k1 - N) * R
                res.append(dict(anteil=float(mx[i] / su[i]), spiegel=sp, drehung=int(deg), verschiebung=[round(dx, 2), round(dy, 2)]))
    res.sort(key=lambda r: -r["anteil"])
    def nah(r): return r["spiegel"] == 0 and min(r["drehung"], 360 - r["drehung"]) <= 15
    best_nah = next(r for r in res if nah(r)); best_alt = next(r for r in res if not nah(r))
    rel = (best_nah["anteil"] - best_alt["anteil"]) / max(best_nah["anteil"], 1e-9)
    warn_b = best_alt["anteil"] > best_nah["anteil"] or rel < a.abstand
    warn_a = bool(haufen) and haufen[0]["punkte"] > a.haufen
    out = dict(werkzeug="wolke_grundriss_pruefen.py", wolke=a.wolke, lod2_gebaeude=len(B), wandpunkte=int(len(Q)),
               strasse=dict(anteil=round(anteil, 4), haufen=haufen[:10], warnung=warn_a),
               eindeutigkeit=dict(identitaet_anteil=round(ident, 4), beste_nahe_identitaet=best_nah, beste_alternative=best_alt,
                                  abstand_relativ=round(rel, 3), warnung=warn_b, top5=res[:5]))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(out, open(os.path.join(od, "audit", "wolke_grundriss.json"), "w"), indent=1, ensure_ascii=False)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 10)); s = np.random.default_rng(0).choice(len(Q), min(150000, len(Q)), replace=False)
        ax.scatter(Q[s, 0], Q[s, 1], s=0.2, c=np.where(strasse[s], "red", "0.55"))
        for g in polys:
            q = np.vstack([g, g[:1]]); ax.plot(q[:, 0], q[:, 1], "k", lw=1)
        ax.set_aspect("equal"); lim = a.radius * 0.8; ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
        ax.set_title("Wandpunkte grau, auf der Strasse rot (%.1f %%), LoD2-Grundrisse schwarz" % (100 * anteil))
        plt.tight_layout(); plt.savefig(os.path.join(od, "audit", "wolke_grundriss.png"), dpi=70)
    except Exception as e:
        print("Bild nicht erzeugt:", e)
    print("A Strasse: %.1f %% der Wandpunkte ausserhalb LoD2 und > %.1f m von jeder Wand" % (100 * anteil, a.wandabstand))
    for h in haufen[:5]: print("   Haufen %6d Punkte bei (%.1f/%.1f), %dx%d m" % (h["punkte"], *h["mitte"], *h["ausdehnung_m"]))
    print("B Eindeutigkeit: aktuelle Lage %.3f, beste nahe Identitaet %.3f (%d Grad), beste Alternative %.3f (Spiegel %d, %d Grad), Abstand %.1f %%"
          % (ident, best_nah["anteil"], best_nah["drehung"], best_alt["anteil"], best_alt["spiegel"], best_alt["drehung"], 100 * rel))
    # Kontrolle 2026-11-14: B warnt auch am korrekt liegenden Kaufhaus (Abstand 4,4 %), Wandlinien-Ueberlapp trennt nicht -> B nur HINWEIS, Tor ist A
    # (Kaufhaus 0,4 % / Haufen <1200 Punkte, Schwabentor 10 % / Haufen 207 190 Punkte = falscher Fluegel).
    if warn_b: print("HINWEIS B: Drehlage gegen LoD2 nicht eindeutig (allein kein Fehlerbeleg, Kontrolle Kaufhaus warnt auch) - nur zusammen mit A deuten.")
    if warn_a: print("WARNUNG A: grosser Wolkenhaufen auf der Strasse - am Foto klaeren (falsch verortetes Teilnetz?), NICHT modellieren."); raise SystemExit(3)


if __name__ == "__main__":
    main()
