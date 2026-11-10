"""foto_fehlteile.py - fehlende Bauteile DIREKT aus den Fotokanten finden (11.11., Regel 9e "Fotokanten entscheiden").

Bisher fand der Kreis Fehlteile nur ueber das Kantengitter (konvergenz_bericht 'fehlkanten', aus Fotos ABGELEITET, in der Laube fast leer):
das Kreuzrippengewoelbe der Laube wurde so nie Ziel, obwohl seine Rippen in ~40 Fotos gelb (Fotokante ohne Modellkante) erscheinen.
Hier: die gelben Flecken der Formliste (teil_fotoform: je Teil und Foto die groessten gelben Flecken mit Weltpunkt auf der Modellflaeche)
ueber ALLE Fotos sammeln, je Foto entdoppeln (derselbe Fleck erscheint bei mehreren Teilen mit gleichem Bildbereich), raeumlich clustern
(Einzelverkettung, Radius --radius, Abstaende auf der GPU) und nur Cluster behalten, die in >= --min_fotos verschiedenen Fotos auftreten.

Ausgabe (--aus JSON): Liste von Clustern {id, zentrum, lo, hi, fotos, n_fotos, px, teile} - gleiche Felder wie konvergenz_bericht 'fehlkanten'
(id/zentrum/lo/hi), damit bauteil_kreis sie als Fehlteil-Ziel nehmen kann; dazu 'quelle': 'fotokanten'.
Grenzen: Weltpunkt = Median der Modellflaechen-Treffer unter dem Fleck -> liegt AUF dem vorhandenen Modell (Gewoelbe vor der Rueckwand
erscheint auf Wand/Decke dahinter); Lage daher nur Suchkasten, Mass/Lage misst der Agent mit foto_mass (Strahlschnitt).
Aufruf: python -I tools/foto_fehlteile.py kaufhaus_grob3 [--formliste DATEI] [--radius 1.0] [--min_fotos 3] [--aus DATEI] [--synth]"""
import argparse, glob, json, os, sys
import numpy as np


def neueste_formliste(objekt, kreisdir="/media/oem/scan/rc-park_kreis"):
    fs = [p for p in glob.glob(os.path.join(kreisdir, objekt, "fotoform", "*.json")) if "_v" in os.path.basename(p) and not p.endswith(".teil")]
    return max(fs, key=os.path.getmtime) if fs else None


def beobachtungen(fl, min_px=2000):
    """Je (Foto, Fleck) eine Beobachtung; Doppelte (gleiches Foto, Weltpunkt < 0,3 m, von verschiedenen Teilen) zusammenfassen."""
    roh = []
    for teil, je in (fl.get("teile") or {}).items():
        for foto, e in je.items():
            if foto == "_gesamt" or not isinstance(e, dict): continue
            for g in e.get("gelb") or []:
                if g.get("xyz") is None or g.get("px", 0) < min_px: continue
                roh.append((foto, np.array(g["xyz"], float), int(g["px"]), teil))
    obs = []
    for foto in sorted({r[0] for r in roh}):
        rr = sorted([r for r in roh if r[0] == foto], key=lambda r: -r[2])
        for f_, x, px, t in rr:
            for o in obs:
                if o["foto"] == foto and np.linalg.norm(o["xyz"] - x) < 0.3:
                    o["teile"].add(t); o["px"] = max(o["px"], px); break
            else:
                obs.append({"foto": foto, "xyz": x, "px": px, "teile": {t}})
    return obs


def clustern(X, radius):
    """Einzelverkettung: Paarabstaende auf der GPU (n ~ 1e3, Nutzerregel GPU), Zusammenhangskomponenten per Union-Find."""
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    T = torch.tensor(X, dtype=torch.float32, device=dev)
    nb = (torch.cdist(T, T) < radius).cpu().numpy()   # kleine Menge (Beobachtungen, nicht Wolke) - cdist ist hier unkritisch
    par = list(range(len(X)))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i, j in zip(*np.nonzero(np.triu(nb, 1))): par[f(i)] = f(j)
    return np.array([f(i) for i in range(len(X))])


def cluster_bilden(obs, radius, min_fotos):
    if not obs: return []
    X = np.array([o["xyz"] for o in obs]); lab = clustern(X, radius); out = []
    for c in np.unique(lab):
        oo = [o for o, l in zip(obs, lab) if l == c]; fotos = sorted({o["foto"] for o in oo})
        if len(fotos) < min_fotos: continue
        P = np.array([o["xyz"] for o in oo]); w = np.array([o["px"] for o in oo], float)
        z = np.round(np.average(P, 0, w), 2); lo = np.round(P.min(0) - 0.5, 2); hi = np.round(P.max(0) + 0.5, 2)
        out.append({"id": "ff_%+d_%+d_%+d" % tuple(np.round(z).astype(int)), "quelle": "fotokanten", "zentrum": z.tolist(), "lo": lo.tolist(), "hi": hi.tolist(),
                    "n_fotos": len(fotos), "fotos": fotos, "px": int(w.sum()), "n_flecken": len(oo), "teile": sorted({t for o in oo for t in o["teile"]})})
    return sorted(out, key=lambda c: -c["px"])


def synth_test():
    """Beweistest: zwei echte Cluster (je 4 Fotos) + Streuflecken (je 1 Foto) + Doppelte ueber zwei Teile -> genau 2 Cluster, Doppelte entfernt."""
    rng = np.random.default_rng(1); te = {}
    def fleck(xyz, px=5000): return {"px": px, "xyz": list(xyz)}
    for k, (c, fotos) in enumerate([((0, 0, 5), ["a", "b", "c", "d"]), ((10, 0, 8), ["b", "c", "e", "f"])]):
        for f in fotos:
            p = np.array(c) + rng.normal(0, 0.2, 3)
            for t in ("t1", "t2"): te.setdefault(t, {}).setdefault(f, {"gelb": []})["gelb"].append(fleck(p))   # gleicher Fleck bei 2 Teilen
    for i, f in enumerate(["g", "h", "i"]): te.setdefault("t1", {}).setdefault(f, {"gelb": []})["gelb"].append(fleck((30 + 5 * i, 5, 2)))
    obs = beobachtungen({"teile": te}); cl = cluster_bilden(obs, 1.0, 3)
    ok = len(cl) == 2 and sorted(c["n_fotos"] for c in cl) == [4, 4] and all(c["n_flecken"] == 4 for c in cl)
    print("SYNTH", "BESTANDEN" if ok else "FALSCH", [(c["id"], c["n_fotos"], c["n_flecken"]) for c in cl]); return ok


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("--formliste"); ap.add_argument("--radius", type=float, default=1.0)
    ap.add_argument("--min_fotos", type=int, default=3); ap.add_argument("--min_px", type=int, default=2000); ap.add_argument("--aus"); ap.add_argument("--synth", action="store_true")
    a = ap.parse_args(argv)
    if a.synth: sys.exit(0 if synth_test() else 1)
    fp = a.formliste or neueste_formliste(a.objekt)
    if not fp: sys.exit("keine Formliste")
    fl = json.load(open(fp)); obs = beobachtungen(fl, a.min_px); cl = cluster_bilden(obs, a.radius, a.min_fotos)
    erg = {"formliste": fp, "stl_sha": fl.get("stl_sha"), "metrik": fl.get("metrik"), "radius": a.radius, "min_fotos": a.min_fotos, "beobachtungen": len(obs), "cluster": cl}
    for c in cl[:15]: print(f"{c['id']:16s} Fotos {c['n_fotos']:3d}  px {c['px']:8d}  zentrum {c['zentrum']}  teile {','.join(c['teile'])[:80]}")
    if a.aus: json.dump(erg, open(a.aus, "w"), indent=1, ensure_ascii=False)
    return erg


if __name__ == "__main__":
    main()
