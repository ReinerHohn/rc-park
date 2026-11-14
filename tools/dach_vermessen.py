"""dach_vermessen.py <objekt.json> [--wolke npy] - Dachform je LoD2-Grundflaeche aus Laser DOM1 (allgemein, je Objekt; Nullstart-Schritt 'dach').

Quelle: DOM1 (Laser von oben) sieht Dachflaechen ('hoehe_flaeche' laut pruefstand.QUELLEN), ist aber blind fuer Nadeln/Spitzen und
verschmiert Strukturen < ~3 m (Treppengiebel, Gauben, Erker). Darum: nur die GROSSFORM wird gefittet; Details bleiben Foto-Aufgabe.
Die dichte Wolke (--wolke, Modellrahmen) ist nur Gegenprobe (Hoehe der hoechsten Punkte je Zelle), nie Fit-Quelle.

Ablauf je Grundflaeche (> --min_flaeche m2) des Objekts (objekt.json lod2.id):
  1. DOM1-Pixelmitten im Grundriss (1 m innen geschrumpft: Randpixel mischen Strasse/Wand), Hoehe ueber rahmen.gelaende
  2. Familien im Achsensystem des kleinsten umschliessenden Rechtecks (a lang, b kurz): flach, pult (4 Richtungen), sattel_a/sattel_b
     (First-Versatz), walm_a (Firstlaenge > 0), zelt. Jede Form als Ebenenliste g = max_i(ca a + cb b + d) -> tools/dach_bauen.py baut sie. Je Form z = zf - k * g(a,b): zf, k linear (getrimmte Kleinste Quadrate, GPU-Stapel)
  3. Auswahl nach BIC (Fehlerquadrate + Parameterstrafe); Abstand zur Zweitbesten wird gemeldet (eindeutig?)
Ausgabe: <objekt>/dach.json (von tools/dach_bauen.py gelesen), audit/dach.png (DOM1, Modell, Rest). Rueckgabe 0; 2 = keine DOM1-Daten.
"""
import sys, os, json, argparse
import numpy as np, torch
from matplotlib.path import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as LG
from lod2_gebaeude import grundflaechen
from dom1_kachel import dom1_hoehe

DEV = "cuda" if torch.cuda.is_available() else "cpu"


def schrumpfen(uv, d):
    """Polygon um d nach innen (grob: Ecken Richtung Schwerpunkt, genuegt fuer Pixelauswahl)."""
    c = uv.mean(0); r = np.linalg.norm(uv - c, axis=1, keepdims=True); return c + (uv - c) * np.maximum(0, (r - d)) / np.maximum(r, 1e-9)


def rechteck_achsen(uv):
    """Achsen des kleinsten umschliessenden Rechtecks (entlang einer Huellkante). PCA ist bei quadratischem Grundriss unbestimmt
    (Schwabentor 2026-11-14: PCA waehlte die Diagonale, Halbachsen 8,4 statt 6 m). Rueckgabe Mitte, ea (lange Seite), eb, ha, hb."""
    from scipy.spatial import ConvexHull
    h = uv[ConvexHull(uv).vertices]; best = None
    for i in range(len(h)):
        e = h[(i + 1) % len(h)] - h[i]; n_ = np.linalg.norm(e)
        if n_ < 1e-6: continue
        ea = e / n_; eb = np.array([-ea[1], ea[0]]); pa, pb = h @ ea, h @ eb; fl = np.ptp(pa) * np.ptp(pb)
        if best is None or fl < best[0]: best = (fl, ea, eb, pa, pb)
    _, ea, eb, pa, pb = best
    if np.ptp(pb) > np.ptp(pa): ea, eb, pa, pb = eb, -ea, pb, -pa
    c = ea * (pa.max() + pa.min()) / 2 + eb * (pb.max() + pb.min()) / 2
    return c, ea, eb, np.ptp(pa) / 2, np.ptp(pb) / 2


def g_ebenen(a, b, ebenen):
    """g(a,b) = max_i(ca*a + cb*b + d) >= 0; leere Liste = flach (g = 0). Dieselbe Darstellung baut tools/dach_bauen.py."""
    if not ebenen: return torch.zeros_like(a)
    return torch.stack([ca * a + cb * b + d for ca, cb, d in ebenen], 0).max(0).values


def formen(ha, hb):
    """Liste (name, param, ebenen). Dach z = first - steigung * max_i(ca*a + cb*b + d) im Rechteck-Achsensystem (a lang, b kurz)."""
    out = [("flach", {}, [])]
    out += [("pult_a+", {}, [(1.0, 0.0, ha)]), ("pult_a-", {}, [(-1.0, 0.0, ha)]), ("pult_b+", {}, [(0.0, 1.0, hb)]), ("pult_b-", {}, [(0.0, -1.0, hb)])]
    for s in np.linspace(-0.4, 0.4, 17):                                     # Firstversatz in Anteilen der Halbbreite
        out.append(("sattel_a", {"first_versatz_b": float(s * hb)}, [(0.0, 1.0, -s * hb), (0.0, -1.0, s * hb)]))   # First laeuft laengs a
        out.append(("sattel_b", {"first_versatz_a": float(s * ha)}, [(1.0, 0.0, -s * ha), (-1.0, 0.0, s * ha)]))
    for c in np.linspace(0, 1, 21):                                          # Walm; Firstlaenge 0 = Zelt (gleiche Neigung aller Flaechen)
        ca = float(c * max(ha - hb, 0))
        out.append(("walm_a" if ca > 0 else "zelt", {"first_halblaenge": ca}, [(1.0, 0.0, -ca), (-1.0, 0.0, -ca), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)]))
    seen = set(); uniq = []
    for nm, par, eb in out:                                                  # doppelte Formen (Zelt) nur einmal
        k = (nm, tuple(np.round(np.array(eb, float).ravel(), 4)))
        if k not in seen: seen.add(k); uniq.append((nm, par, eb))
    return uniq


def fit(z, g, trim=0.9):
    """z ~ zf - k g, getrimmt; Rueckgabe zf, k, rms, maske."""
    w = torch.ones_like(z, dtype=torch.bool)
    for _ in range(4):
        A = torch.stack([torch.ones_like(g[w]), -g[w]], 1); sol = torch.linalg.lstsq(A, z[w, None]).solution[:, 0]
        res = (z - (sol[0] - sol[1] * g)).abs(); w = res <= torch.quantile(res, trim)
    return float(sol[0]), float(sol[1]), float(torch.sqrt((res[w] ** 2).mean())), w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("--wolke", default=""); ap.add_argument("--min_flaeche", type=float, default=20.0)
    ap.add_argument("--rand", type=float, default=1.0, help="m Grundriss innen ignorieren (Randpixel)")
    a_ = ap.parse_args()
    obj = json.load(open(a_.objekt)); od = os.path.dirname(os.path.abspath(a_.objekt)); r = obj["rahmen"]
    m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float); g0 = float(r["gelaende"])
    meta, gr, wa = grundflaechen(obj, obj["lod2"]["gml"])
    if meta is None: sys.exit(f"LoD2 {obj['lod2']['id']} nicht in {obj['lod2']['gml']}")
    W = np.vstack([w for w in wa]) if wa else np.zeros((0, 3))
    X = np.load(a_.wolke).astype(float) if a_.wolke else None
    teile = []; bilder = []
    for gi, p in enumerate(gr):
        uv = np.c_[(p[:, :2] - m0) @ xh, (p[:, :2] - m0) @ yh]
        fl = 0.5 * abs(np.dot(uv[:, 0], np.roll(uv[:, 1], 1)) - np.dot(uv[:, 1], np.roll(uv[:, 0], 1)))
        if fl < a_.min_flaeche: continue
        E0, E1 = np.floor(p[:, 0].min()) - 1, np.ceil(p[:, 0].max()) + 1; N0, N1 = np.floor(p[:, 1].min()) - 1, np.ceil(p[:, 1].max()) + 1
        EE, NN = np.meshgrid(np.arange(E0, E1) + 0.5, np.arange(N0, N1) + 0.5); E, N = EE.ravel(), NN.ravel()   # LGL-Pixelmitten auf x,5
        U = np.c_[(np.c_[E, N] - m0) @ xh, (np.c_[E, N] - m0) @ yh]
        inn = Path(schrumpfen(uv, a_.rand)).contains_points(U)
        z = dom1_hoehe(E[inn], N[inn]) - g0; ok = np.isfinite(z); U = U[inn][ok]; z = z[ok]
        if len(z) < 12: print(f"Teil {gi}: nur {len(z)} DOM1-Pixel - uebersprungen"); continue
        c, ea, eb, ha, hb = rechteck_achsen(uv)                              # Achsen aus Wandkanten, nicht PCA
        A = torch.as_tensor((U - c) @ ea, dtype=torch.float32, device=DEV); Bt = torch.as_tensor((U - c) @ eb, dtype=torch.float32, device=DEV)
        Z = torch.as_tensor(z, dtype=torch.float32, device=DEV); n = len(z)
        erg = []
        for nm, par, ebn in formen(ha, hb):
            g = g_ebenen(A, Bt, ebn)
            if nm == "flach": zf = float(torch.quantile(Z, 0.5)); res = (Z - zf).abs(); w = res <= torch.quantile(res, 0.9); rms = float(torch.sqrt((res[w] ** 2).mean())); k = 0.0
            else: zf, k, rms, w = fit(Z, g)
            if nm != "flach" and k <= 0: continue
            npar = {"flach": 1, "pult": 2, "zelt": 2}.get(nm.split("_")[0], 3)
            erg.append(dict(form=nm, **par, ebenen=[[round(float(x), 4) for x in e] for e in ebn], first=zf, steigung=k, neigung_grad=float(np.degrees(np.arctan(k))), rms_m=rms,
                            bic=float(n * np.log(max(rms, 1e-3) ** 2) + npar * np.log(n))))
        erg.sort(key=lambda e: e["bic"]); best = erg[0]
        gb = g_ebenen(A, Bt, best["ebenen"])
        rest = (Z - (best["first"] - best["steigung"] * gb)).cpu().numpy(); sp = rest > 2.0
        spitze = None
        if sp.sum():                                                           # schmaler Aufsatz ueber der Dachflaeche (Spitze/Dachreiter); DOM1 blind fuer Nadeln
            j = np.argmax(z); spitze = dict(dom1_max=float(z[j]), lage_uv=U[j].round(2).tolist(), pixel=int(sp.sum()),
                                            hinweis="DOM1 1-m-Raster: Spitze eher HOEHER; Hoehe aus masstabelle (Gesamthoehe) nehmen, Form Foto-Aufgabe")
        zweit = next((e for e in erg if e["form"].split("_")[0] != best["form"].split("_")[0] or e["form"] != best["form"]), None)
        wand = float(W[:, 2].max() - meta["ground_z"]) if len(W) else None
        # Gegenprobe Wolke: hoechste Punkte im Grundriss (Rahmen = Modellsystem)
        wg = None
        if X is not None:
            mi = Path(uv).contains_points(X[:, :2]); wg = float(np.percentile(X[mi, 2], 99.5)) if mi.sum() > 100 else None
        t = dict(teil=gi, flaeche_m2=round(fl, 1), pixel=n, mitte_uv=c.round(3).tolist(), achse_a=ea.round(5).tolist(), halb_a=round(ha, 3), halb_b=round(hb, 3),
                 grundriss_uv=uv.round(3).tolist(), dom1_max=float(z.max()), dom1_p95=float(np.percentile(z, 95)), wand_oberkante_lod2=wand,
                 wolke_p995=wg, spitze=spitze, beste=best, zweitbeste=zweit, eindeutig=bool(zweit is None or zweit["bic"] - best["bic"] > 10),
                 alle=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in e.items() if k != "ebenen"} for e in erg[:8]])
        teile.append(t)
        print(f"Teil {gi} ({fl:.0f} m2, {n} Pixel): {best['form']} First {best['first']:.2f} m, Neigung {best['neigung_grad']:.0f} Grad, RMS {best['rms_m']:.2f} m"
              f" | zweit {zweit['form'] if zweit else '-'} RMS {zweit['rms_m'] if zweit else float('nan'):.2f} | DOM1-max {z.max():.2f}"
              + (f" | Wolke p99,5 {wg:.1f}" if wg else "") + (f" | SPITZE {spitze['pixel']} Pixel bis {spitze['dom1_max']:.1f}" if spitze else ""))
        bilder.append((gi, U, z, best, c, ea, eb, ha, hb, uv))
    erg = dict(werkzeug="dach_vermessen.py", quelle="Laser DOM1 (LGL 2017) ueber rahmen.gelaende; Grossform, Details (Treppengiebel, Gauben) NICHT erfasst",
               lod2_id=obj["lod2"]["id"], teile=teile)
    json.dump(erg, open(os.path.join(od, "dach.json"), "w"), indent=1, ensure_ascii=False)
    if bilder:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, axs = plt.subplots(len(bilder), 3, figsize=(15, 4.6 * len(bilder)), squeeze=False)
        for row, (gi, U, z, best, c, ea, eb, ha, hb, uv) in zip(axs, bilder):
            A = torch.as_tensor((U - c) @ ea, dtype=torch.float32); Bt = torch.as_tensor((U - c) @ eb, dtype=torch.float32)
            g = g_ebenen(A, Bt, best["ebenen"]).numpy()
            zm = best["first"] - best["steigung"] * g; q = np.vstack([uv, uv[:1]])
            for ax, val, tt, cm in ((row[0], z, f"Teil {gi}: DOM1 ueber Gelaende", "turbo"), (row[1], zm, f"Modell {best['form']}", "turbo"), (row[2], z - zm, "Rest DOM1 - Modell (m)", "RdBu")):
                sc = ax.scatter(U[:, 0], U[:, 1], c=val, s=60, marker="s", cmap=cm, vmin=(-2 if cm == "RdBu" else None), vmax=(2 if cm == "RdBu" else None))
                ax.plot(q[:, 0], q[:, 1], "k", lw=1); ax.set_aspect("equal"); ax.set_title(tt); plt.colorbar(sc, ax=ax)
        os.makedirs(os.path.join(od, "audit"), exist_ok=True); plt.savefig(os.path.join(od, "audit", "dach.png"), dpi=70, bbox_inches="tight")
    print("->", os.path.join(od, "dach.json"))
    return 0 if teile else 2


if __name__ == "__main__":
    sys.exit(main())
