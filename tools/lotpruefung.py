#!/usr/bin/env python3
"""lotpruefung.py - Lot-/Neigungspruefung der Wandflaechen einer Punktwolke OHNE den Generator (Plan 2.3).

Misst, ob eine als senkrecht bekannte Wand in der Wolke senkrecht steht: je z-Schicht (+-dz) die Tiefe d = P . u der Aussenflaeche (Modus eines 5-cm-Histogramms im
Mittelstreifen |v| < --streifen, wie hybrid_abgleich.schicht_halbbreite; nur Schichten, in denen der Modus >= --anteil der Punkte im Band +-0,15 m vereint) und daraus die
NEIGUNG dd/dz (Theil-Sen, robust) mit Bootstrap-Unsicherheit ueber Schichten und getrennt fuer zwei Hoehenbaender. Eine senkrechte Wand muss ~0 liefern; der Wert ist die
SCHERUNG der Wolke (SfM-Verbiegung), unabhaengig vom Generator. Kontrolle: derselbe Lauf auf dem Generator-STL (--stl, muss ~0 sein; sonst ist das Werkzeug falsch, nicht die Wolke).
Zweite Messgroesse: seitliche Verschiebung der Mitte (y) der Flaeche (Mittel der Rand-Perzentile p2/p98 der Punkte im Band um die Front) gegen z - ein Lot der senkrechten Kanten.
ANNAHMEN (Argumente): Wandkoerper ist zwischen z 6 und 40 m senkrecht (Turmschaft; Erker/Gesimse stoeren einzelne Schichten und werden vom Modus/Theil-Sen ausgeblendet);
Genauigkeit begrenzt durch Schichtrauschen ~0,05-0,1 m. Quellblindheit: Fotos/Dokumente liefern hier nichts, nur Wolken (SfM/Drohne) und das Modell.
  python3 -I tools/lotpruefung.py modelle/<objekt>/objekt.json --wolke a.npy [--wolke b.npy] [--stl modell.stl] [--seite Nord(-x)] [--zlo 6 --zhi 40] [--ausgabe name]
  python3 -I tools/lotpruefung.py --selbsttest
Ausgabe: audit/lotpruefung_<name>.json. Exit 0 immer (Messung); die Entscheidung trifft die Pruefzeile (--grenze-mm-m: nur Hinweis in der Ausgabe).
"""
import sys, os, json, argparse, numpy as np

SEITEN = {"Nord(-x)": (-1.0, 0.0), "Sued(+x)": (1.0, 0.0), "Ost(+y)": (0.0, 1.0), "West(-y)": (0.0, -1.0)}      # wie hybrid_abgleich.SEITEN

def theil_sen(z, y):
    i, j = np.triu_indices(len(z), 1); dz = z[j] - z[i]; k = np.abs(dz) > 1e-9; s = (y[j][k] - y[i][k]) / dz[k]; b = float(np.median(s)); a = float(np.median(y - b * z)); return a, b

def schichten(P, u, a):
    u = np.array(u, float); v = np.array([-u[1], u[0]]); d = P[:, :2] @ u; l = P[:, :2] @ v; zs, ds, ls, ns = [], [], [], []
    for z in np.arange(a.zlo, a.zhi + 1e-6, a.schritt):
        k = (np.abs(P[:, 2] - z) <= a.dz) & (np.abs(l) < a.streifen) & (d > a.dmin) & (d < a.dmax)
        if k.sum() < a.minpts: continue
        dd, ll = d[k], l[k]; h, e = np.histogram(dd, bins=np.arange(a.dmin, a.dmax + 0.05, 0.05)); hs = np.convolve(h, np.ones(3) / 3, "same"); m = int(np.argmax(hs)); d0 = 0.5 * (e[m] + e[m + 1])
        band = np.abs(dd - d0) <= 0.15
        if band.mean() < a.anteil: continue
        d0 = float(np.median(dd[band])); lb = ll[np.abs(dd - d0) <= 0.3]; zs.append(z); ds.append(d0); ls.append(float(0.5 * (np.percentile(lb, 2) + np.percentile(lb, 98)))); ns.append(int(k.sum()))
    return np.array(zs), np.array(ds), np.array(ls), np.array(ns)

def neigung(z, y, n_boot=300, seed=0):
    """-> dict(mm_je_m, grad, ci95_mm_je_m, rest_rms_m); Bootstrap ueber Schichten."""
    if len(z) < 5: return None
    a0, b = theil_sen(z, y); res = y - (a0 + b * z); rng = np.random.default_rng(seed); bs = []
    for _ in range(n_boot):
        s = rng.integers(0, len(z), len(z))
        if len(np.unique(z[s])) >= 3: bs.append(theil_sen(z[s], y[s])[1])
    lo, hi = np.percentile(bs, [2.5, 97.5]) if bs else (np.nan, np.nan)
    return dict(n_schichten=int(len(z)), mm_je_m=round(1000 * b, 2), grad=round(float(np.degrees(np.arctan(b))), 3), ci95_mm_je_m=[round(1000 * float(lo), 2), round(1000 * float(hi), 2)], rest_rms_m=round(float(np.sqrt(np.mean(res ** 2))), 3))

def messe(P, u, a):
    z, d, l, n = schichten(P, u, a)
    if len(z) < 5: return dict(status="zu wenige Schichten (%d)" % len(z))
    zm = 0.5 * (a.zlo + a.zhi); unten, oben = z <= zm, z > zm
    return dict(status="ok", z_von=float(z.min()), z_bis=float(z.max()), tiefe=neigung(z, d), seitlich=neigung(z, l), tiefe_unten=neigung(z[unten], d[unten]), tiefe_oben=neigung(z[oben], d[oben]),
                schichten=[[round(float(x), 2), round(float(y), 3), round(float(w), 3), int(c)] for x, y, w, c in zip(z, d, l, n)])

def segmente_aus(z, d, sprung=0.12, minlaenge=6, luecke=1.5):
    """Zusammenhaengende z-Laeufe ohne Stufe (|d(z+1)-d(z)| < sprung) der KONTROLLE -> [(z0, z1)]; keine Handgrenzen. Stufen/Gesimse trennen Abschnitte."""
    ab, start = [], 0
    for i in range(1, len(z) + 1):
        if i == len(z) or abs(d[i] - d[i - 1]) >= sprung or z[i] - z[i - 1] > luecke:
            if i - start >= minlaenge: ab.append((float(z[start]), float(z[i - 1])))
            start = i
    return ab

def je_segment(P, u, a, segs):
    z, d, l, n = schichten(P, u, a); out = []
    for z0, z1 in segs:
        k = (z >= z0 - 1e-6) & (z <= z1 + 1e-6); r = neigung(z[k], d[k]) if k.sum() >= 5 else None
        out.append(dict(z=[z0, z1], tiefe=r))
    return out

def selbsttest(a):
    rng = np.random.default_rng(2); fehler = []
    for lean, soll in ((0.0, 0.0), (0.02, 20.0), (-0.01, -10.0)):
        z = rng.uniform(5, 42, 150000); d = 4.5 + lean * z + rng.normal(0, 0.06, z.size); y = rng.uniform(-3, 3, z.size); o = rng.random(z.size) < 0.25; d[o] += rng.uniform(-0.6, 0.6, o.sum())   # Rauschen/Gesimse
        P = np.c_[-d, y, z]; r = messe(P, SEITEN["Nord(-x)"], a); ist = r["tiefe"]["mm_je_m"] if r.get("tiefe") else None
        print(f"  Neigung Soll {soll:+.1f} mm/m -> gemessen {ist} (CI {r['tiefe']['ci95_mm_je_m']})");
        if ist is None or abs(ist - soll) > 3.0: fehler.append(soll)
    print("SELBSTTEST", "BESTANDEN" if not fehler else f"FEHLGESCHLAGEN bei {fehler}"); return 1 if fehler else 0

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("--wolke", action="append", default=[]); ap.add_argument("--stl"); ap.add_argument("--stl-faktor", type=float, default=87 / 1000.0)
    ap.add_argument("--seite", default="Nord(-x)", choices=list(SEITEN)); ap.add_argument("--zlo", type=float, default=6.0); ap.add_argument("--zhi", type=float, default=40.0); ap.add_argument("--dz", type=float, default=0.5); ap.add_argument("--schritt", type=float, default=1.0)
    ap.add_argument("--streifen", type=float, default=1.8); ap.add_argument("--dmin", type=float, default=2.0); ap.add_argument("--dmax", type=float, default=8.0); ap.add_argument("--minpts", type=int, default=300); ap.add_argument("--anteil", type=float, default=0.15)
    ap.add_argument("--grenze-mm-m", type=float, default=5.0, help="ANNAHME: > 5 mm/m (0,3 Grad) Neigung einer senkrechten Wand = Scherung"); ap.add_argument("--eigene-abschnitte", action="store_true", help="Abschnitte je Wolke aus ihrer eigenen Tiefenreihe bestimmen"); ap.add_argument("--wolke-sprung", type=float, default=0.2); ap.add_argument("--wolke-min", type=int, default=4)
    ap.add_argument("--ausgabe"); ap.add_argument("--selbsttest", action="store_true")
    a = ap.parse_args()
    if a.selbsttest: sys.exit(selbsttest(a))
    if not a.objekt or not (a.wolke or a.stl): sys.exit("objekt.json und --wolke/--stl noetig")
    od = os.path.dirname(os.path.abspath(a.objekt)); Q = {}
    for wp in a.wolke: Q[os.path.basename(os.path.dirname(wp)) + "/" + os.path.basename(wp)] = np.load(wp).astype(float)
    if a.stl:
        import trimesh; m = trimesh.load(a.stl); m.apply_scale(a.stl_faktor); Q["KONTROLLE " + os.path.basename(a.stl)] = np.asarray(trimesh.sample.sample_surface(m, 600000, seed=0)[0], float)
    erg = {}; print(f"Seite {a.seite}, z {a.zlo}-{a.zhi} m (ANNAHME: Wand dort senkrecht); Grenze {a.grenze_mm_m} mm/m\n{'Quelle':44}{'Schichten':>10}{'Neigung mm/m':>14}{'CI95':>18}{'unten':>9}{'oben':>9}{'seitl.':>9}")
    for nm, P in Q.items():
        r = messe(P, SEITEN[a.seite], a); erg[nm] = r
        if r["status"] != "ok": print(f"{nm:44}{r['status']}"); continue
        t = r["tiefe"]; f = lambda x: f"{x['mm_je_m']:+9.1f}" if x else "        -"
        print(f"{nm:44}{t['n_schichten']:10d}{t['mm_je_m']:+14.1f}{str(t['ci95_mm_je_m']):>18}{f(r['tiefe_unten'])}{f(r['tiefe_oben'])}{f(r['seitlich'])}" + ("   SCHERUNG" if abs(t["mm_je_m"]) > a.grenze_mm_m and not nm.startswith("KONTROLLE") else ""))
    kn = next((k for k in Q if k.startswith("KONTROLLE")), None); seg_erg = None
    if kn and erg[kn].get("status") == "ok":
        sc = np.array(erg[kn]["schichten"]); segs = segmente_aus(sc[:, 0], sc[:, 1]); seg_erg = {nm: je_segment(P, SEITEN[a.seite], a, segs) for nm, P in Q.items()}
        print(f"\nAbschnitte ohne Stufe (aus dem Generator, automatisch): {[(round(x, 1), round(y, 1)) for x, y in segs]}\nNeigung dd/dz je Abschnitt in mm/m (Differenz zur KONTROLLE = Scherung der Wolke gegen das Modell; CI95 Bootstrap):")
        print(f"{'Quelle':44}" + "".join(f"{'z %.0f-%.0f' % tuple(sg):>22}" for sg in segs))
        for nm, rs in seg_erg.items():
            ref = seg_erg[kn]
            cells = [(f"{r['tiefe']['mm_je_m']:+7.1f} ({r['tiefe']['mm_je_m'] - q['tiefe']['mm_je_m']:+6.1f})" if r['tiefe'] and q['tiefe'] and nm != kn else (f"{r['tiefe']['mm_je_m']:+7.1f}" if r['tiefe'] else "-")) for r, q in zip(rs, ref)]
            print(f"{nm:44}" + "".join(f"{c:>22}" for c in cells))
        print("(Klammer = Differenz zum Generator; Wolkenwerte mit CI, die die Differenz nicht ueberdeckt, sind belegt abweichend)")
    eig = {}
    if a.eigene_abschnitte:
        print(f"\nAbschnitte aus der WOLKE selbst (Stufe >= {a.wolke_sprung} m trennt, mind. {a.wolke_min} Schichten; keine Generatorgrenzen), Neigung mm/m [CI95]:")
        for nm, P in Q.items():
            if nm.startswith("KONTROLLE"): continue
            z, d, l, n = schichten(P, SEITEN[a.seite], a); segs = segmente_aus(z, d, a.wolke_sprung, a.wolke_min, luecke=3.0) if len(z) else []; eig[nm] = []
            for z0, z1 in segs:
                k = (z >= z0 - 1e-6) & (z <= z1 + 1e-6); r = neigung(z[k], d[k]); eig[nm].append(dict(z=[z0, z1], tiefe=r))
            print(f"  {nm:44}" + ("  ".join(f"z {z0:.0f}-{z1:.0f}: {r['mm_je_m']:+.1f} [{r['ci95_mm_je_m'][0]:+.0f},{r['ci95_mm_je_m'][1]:+.0f}]" for (z0, z1), r in zip(segs, [e['tiefe'] for e in eig[nm]]) if r) or "keine Abschnitte"))
        print("(Abschnitte aus der Wolke koennen ECHTE Gesimsstufen als Abschnittsgrenze behandeln und Rauschstufen als echt - Vergleich nur mit gleicher Schwelle je Quelle)")
    pf = os.path.join(od, "audit", f"lotpruefung_{a.ausgabe or 'wolken'}.json"); os.makedirs(os.path.dirname(pf), exist_ok=True)
    json.dump(dict(seite=a.seite, parameter={k: getattr(a, k) for k in ("zlo", "zhi", "dz", "schritt", "streifen", "dmin", "dmax", "minpts", "anteil", "grenze_mm_m")}, annahme="Wand zwischen zlo und zhi senkrecht; Grenze 5 mm/m ist ANNAHME", quellen=erg, abschnitte=seg_erg, abschnitte_eigene=eig), open(pf, "w"), indent=1, ensure_ascii=False)
    print("Bericht:", pf)

if __name__ == "__main__":
    main()
