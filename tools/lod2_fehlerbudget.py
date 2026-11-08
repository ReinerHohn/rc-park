#!/usr/bin/env python3
"""lod2_fehlerbudget.py - Fehlerbudget der Quelle LoD2 statistisch: LGL-LoD2 gegen Stadt-LoD2 ueber ALLE Gebaeude im Umkreis
(300 m) um Kaufhaus und Martinstor (Plan 4c.5). Funktionen aus stadt_lod2_schneiden.py (kennzahlen, parse_gebaeude, stadt_lesen, rahmen_von)
und lod2_gebaeude.extract werden importiert, nicht kopiert. Nur vergleichen, nicht mitteln (Regel 5); keine Sollwerte.

Paarung: Kante LGL<->Stadt, wenn Ueberlapp >= 50 % der LGL- ODER der Stadtflaeche. Paar = Komponente 1:1 mit BEIDEN Anteilen >= 50 %;
Komponenten mit n:m (1:n, n:1) werden getrennt gezaehlt und ausgeschlossen. Differenzen Stadt - LGL, Hoehen absolut ue.NN.

  python tools/lod2_fehlerbudget.py [--radius 300] [--aus DIR]
"""
import argparse, datetime, glob, json, os, re, sys, time
import numpy as np
from shapely.strtree import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as LG
import stadt_lod2_schneiden as SL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STADT = "/media/oem/scan/rc-park_daten/freiburg_stadt/lod2/20261007_Freiburg_LoD2.gml"
OUT = "/media/oem/scan/rc-park_daten/freiburg_stadt/fehlerbudget"
LGL_GLOB = "/media/oem/scan/rc-park_daten/_geo/LoD2_32_*/LoD2_32_*_1_BW.gml"
OBJ = {"kaufhaus": ("modelle/kaufhaus_null5/objekt.json", "DEBW_0010007Tv9r"), "martinstor": ("modelle/martinstor/objekt.json", "DEBW_001000hPLcn")}
TYPL = {"WallSurface": "Wand", "RoofSurface": "Dach", "GroundSurface": "Boden", "ClosureSurface": "Verschluss"}


def zentrum(objpfad):
    return SL.rahmen_von(json.load(open(os.path.join(ROOT, objpfad))), os.path.join(ROOT, objpfad))[0]


def rec_von(gid, polys):
    kz, fl = SL.kennzahlen(polys)
    return dict(id=gid, kz=kz, fl=fl, abs_first=kz["boden_z_abs"] + kz["first_m"], abs_traufe=kz["boden_z_abs"] + kz["traufe_m"])


def typ(n):
    return "flach/pult (1-2)" if n <= 2 else ("sattel/walm (3-6)" if n <= 6 else "komplex (>6)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--radius", type=float, default=300.0); ap.add_argument("--aus", default=OUT)
    a = ap.parse_args(); t0 = time.time(); os.makedirs(a.aus, exist_ok=True)
    cen = {k: zentrum(v[0]) for k, v in OBJ.items()}; print("Zentren", {k: c.tolist() for k, c in cen.items()})
    # LGL: je Zentrum alle Gebaeude (Schwerpunkt im Radius), ueber alle Kacheln, Duplikate nach id
    lgl = {}
    for g in sorted(glob.glob(LGL_GLOB)):
        for k, c in cen.items():
            for m, polys in LG.extract(g, center=tuple(c), radius=a.radius):
                if m["id"] in lgl: lgl[m["id"]]["obj"].add(k); continue
                r = rec_von(m["id"], [(TYPL[t], P) for t, P in polys]); r["obj"] = {k}; r["ctr"] = m["center_utm"]; lgl[m["id"]] = r
    print(f"LGL: {len(lgl)} Gebaeude ({time.time() - t0:.0f} s)")
    # Stadt: streamend, nur Huellquader in den Kreis-Boxen
    boxen = [(c[0] - a.radius - 60, c[1] - a.radius - 60, c[0] + a.radius + 60, c[1] + a.radius + 60) for c in cen.values()]
    stadt, n_all = {}, 0
    # stadt_lesen filtert je bbox; wir rufen es einmal je Box nicht (2 Durchlaeufe), sondern mit Gesamtbox und filtern selbst
    gb = (min(b[0] for b in boxen), min(b[1] for b in boxen), max(b[2] for b in boxen), max(b[3] for b in boxen))
    for gid, txt in SL.stadt_lesen(STADT, gb):
        n_all += 1
        m = SL.ENV.search(txt); lo = [float(v) for v in m.group(1).split()]; hi = [float(v) for v in m.group(2).split()]
        mx, my = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        ok = [k for k, c in cen.items() if np.hypot(mx - c[0], my - c[1]) <= a.radius]
        if not ok: continue
        polys, attr = SL.parse_gebaeude(txt)
        if not polys or not any(t == "Dach" for t, _ in polys): continue
        r = rec_von(gid, polys); r["obj"] = set(ok); stadt[gid] = r
    print(f"Stadt: {len(stadt)} Gebaeude im Kreis ({n_all} in Boxen) ({time.time() - t0:.0f} s)")
    # Paarung
    L = list(lgl.values()); S = list(stadt.values()); tree = STRtree([s["fl"] for s in S]); kanten = []
    for i, l in enumerate(L):
        for j in tree.query(l["fl"]):
            ov = l["fl"].intersection(S[j]["fl"]).area
            if ov < 1e-6: continue
            pl, ps = ov / l["fl"].area, ov / S[j]["fl"].area
            if pl >= .5 or ps >= .5: kanten.append((i, j, pl, ps))
    # Komponenten
    par = {}
    def f(x):
        while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
        return x
    for i, j, _, _ in kanten: par[f(("L", i))] = f(("S", j))
    comp = {}
    for x in list(par): comp.setdefault(f(x), []).append(x)
    paare, n1n, nn1, nnm = [], 0, 0, 0; ausgeschl = []
    ed = {(i, j): (pl, ps) for i, j, pl, ps in kanten}
    for mem in comp.values():
        li = [x[1] for x in mem if x[0] == "L"]; sj = [x[1] for x in mem if x[0] == "S"]
        if len(li) == 1 and len(sj) == 1:
            pl, ps = ed[(li[0], sj[0])]
            if pl >= .5 and ps >= .5:
                l, s = L[li[0]], S[sj[0]]
                paare.append(dict(lgl_id=l["id"], stadt_id=s["id"], objekt=sorted(l["obj"] | s["obj"]), anteil_lgl=round(pl, 3), anteil_stadt=round(ps, 3),
                    lgl=dict(first_abs=l["abs_first"], traufe_abs=l["abs_traufe"], grundriss=l["kz"]["grundriss_m2"], n_dach=l["kz"]["n_dachflaechen"], boden=l["kz"]["boden_z_abs"]),
                    stadt=dict(first_abs=s["abs_first"], traufe_abs=s["abs_traufe"], grundriss=s["kz"]["grundriss_m2"], n_dach=s["kz"]["n_dachflaechen"], boden=s["kz"]["boden_z_abs"])))
                continue
        k = "1:n" if len(li) == 1 else ("n:1" if len(sj) == 1 else "n:m")
        if k == "1:n": n1n += 1
        elif k == "n:1": nn1 += 1
        else: nnm += 1
        ausgeschl.append(dict(art=k, lgl=[L[i]["id"] for i in li], stadt=[S[j]["id"] for j in sj]))
    gepaart_l = {p["lgl_id"] for p in paare}; gepaart_s = {p["stadt_id"] for p in paare}
    ohne_l = [l["id"] for l in L if not any(("L", i) in par for i in [L.index(l)])] if False else None
    inkomp_l = {x[1] for x in par if x[0] == "L"}; inkomp_s = {x[1] for x in par if x[0] == "S"}
    ohne_l = [L[i]["id"] for i in range(len(L)) if i not in inkomp_l]; ohne_s = [S[j]["id"] for j in range(len(S)) if j not in inkomp_s]
    for p in paare:
        d = {g: p["stadt"][g] - p["lgl"][g] for g in ("first_abs", "traufe_abs", "grundriss", "boden")}
        d["n_dach"] = p["stadt"]["n_dach"] - p["lgl"]["n_dach"]; d["grundriss_verh"] = p["stadt"]["grundriss"] / max(p["lgl"]["grundriss"], 1e-6)
        p["diff"] = {k: round(float(v), 3) for k, v in d.items()}; p["typ"] = typ(p["lgl"]["n_dach"])

    def stat(v):
        v = np.asarray(v, float)
        if not len(v): return dict(n=0)
        med = float(np.median(v)); mad = float(np.median(np.abs(v - med)))
        return dict(n=int(len(v)), median=round(med, 3), mad=round(mad, 3), sigma_rob=round(1.4826 * mad, 3), mittel=round(float(v.mean()), 3), std=round(float(v.std()), 3),
                    p5=round(float(np.percentile(v, 5)), 3), p95=round(float(np.percentile(v, 95)), 3), anteil_gt_0_5=round(float((np.abs(v) > .5).mean()), 3), anteil_gt_1_0=round(float((np.abs(v) > 1).mean()), 3))
    groessen = ["first_abs", "traufe_abs", "grundriss", "boden", "n_dach", "grundriss_verh"]
    st = {"alle": {g: stat([p["diff"][g] for p in paare]) for g in groessen}}
    for ty in sorted({p["typ"] for p in paare}):
        st[ty] = {g: stat([p["diff"][g] for p in paare if p["typ"] == ty]) for g in groessen}
    aus_first = [dict(lgl=p["lgl_id"], stadt=p["stadt_id"], d_first=p["diff"]["first_abs"], d_traufe=p["diff"]["traufe_abs"], n_dach_lgl=p["lgl"]["n_dach"], n_dach_stadt=p["stadt"]["n_dach"], typ=p["typ"], objekt=p["objekt"])
                 for p in paare if abs(p["diff"]["first_abs"]) > 3]
    aus_first.sort(key=lambda x: -abs(x["d_first"]))
    # Einordnung der beiden Objekte: Perzentil (Rang des Betrags und des Wertes) ihrer Differenzen
    einordnung = {}
    for k, (_, lid) in OBJ.items():
        p = next((q for q in paare if q["lgl_id"] == lid), None)
        if not p: einordnung[k] = dict(lgl_id=lid, hinweis="kein sauberes 1:1-Paar (Martinstor-Torbau/Kaufhaus gemeinsam mit Nachbarn) - siehe ausgeschlossen"); continue
        e = dict(lgl_id=lid, stadt_id=p["stadt_id"], diff=p["diff"])
        for g in ("first_abs", "traufe_abs", "grundriss_verh", "boden"):
            v = np.array([q["diff"][g] for q in paare]); x = p["diff"][g]
            e[g + "_perzentil_wert"] = round(float((v < x).mean() * 100), 1); e[g + "_perzentil_betrag"] = round(float((np.abs(v) < abs(x - (1 if g == "grundriss_verh" else 0))).mean() * 100), 1) if False else round(float((np.abs(v - np.median(v)) < abs(x - np.median(v))).mean() * 100), 1)
        einordnung[k] = e
    for k, (_, lid) in OBJ.items():
        if einordnung[k].get("stadt_id") is None:
            l = lgl[lid]; einordnung[k]["komponente"] = [c for c in ausgeschl if lid in c["lgl"]]
    out = dict(erzeugt=datetime.datetime.now().isoformat(timespec="seconds"), werkzeug="tools/lod2_fehlerbudget.py", radius_m=a.radius, zentren={k: c.tolist() for k, c in cen.items()},
               stadt_gml=STADT, n_lgl=len(L), n_stadt=len(S), n_paare=len(paare), ausgeschlossen=dict(n_1zun=n1n, n_nz1=nn1, n_nzm=nnm, komponenten=ausgeschl),
               ohne_partner=dict(lgl=len(ohne_l), stadt=len(ohne_s), lgl_ids=ohne_l[:200], stadt_ids=ohne_s[:200]), statistik=st, ausreisser_first_gt3m=aus_first,
               einordnung=einordnung, paare=paare, laufzeit_s=round(time.time() - t0, 1))
    json.dump(out, open(os.path.join(a.aus, "fehlerbudget_lod2.json"), "w"), ensure_ascii=False, indent=1)
    print(f"Paare {len(paare)}; ausgeschlossen 1:n {n1n}, n:1 {nn1}, n:m {nnm}; ohne Partner LGL {len(ohne_l)}, Stadt {len(ohne_s)}; Ausreisser {len(aus_first)}")
    for ty, d in st.items(): print(ty, {g: (d[g].get("n"), d[g].get("median"), d[g].get("sigma_rob")) for g in ("first_abs", "traufe_abs", "boden")})
    # Histogramme
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for axx, g, tit, lim in ((ax[0], "first_abs", "First absolut: Stadt - LGL (m)", 8), (ax[1], "traufe_abs", "niedrigste Traufe absolut: Stadt - LGL (m)", 8), (ax[2], "grundriss_verh", "Grundriss Stadt / LGL (-)", None)):
        v = np.array([p["diff"][g] for p in paare])
        if lim: bins = np.linspace(-lim, lim, 81); vv = np.clip(v, -lim, lim)
        else: bins = np.linspace(0.5, 1.5, 81); vv = np.clip(v, .5, 1.5)
        axx.hist(vv, bins=bins, color="#3b6ea8"); axx.set_title(tit); axx.set_ylabel("Gebaeude"); axx.axvline(np.median(v), color="k", ls="--", lw=1)
        axx.set_xlabel(tit + (" - Raender = geklemmt" if True else "")); axx.text(.02, .92, f"n={len(v)}  Median {np.median(v):.2f}\nsigma_rob {1.4826 * np.median(np.abs(v - np.median(v))):.2f}", transform=axx.transAxes, va="top")
        for k, e in einordnung.items():
            if e.get("diff"): axx.axvline(np.clip(e["diff"][g], bins[0], bins[-1]), color={"kaufhaus": "#d94", "martinstor": "#c33"}[k], lw=2, label=k)
    ax[0].legend(); plt.tight_layout(); plt.savefig(os.path.join(a.aus, "histogramme_lod2.png"), dpi=110)
    print(f"fertig {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
