#!/usr/bin/env python3
"""Nachweis tools/foto_tor_bezug.py an Paaren mit BEKANNTEM Ausgang (Auftrag 17.11.2026). Bezug = schwab_v3 (eingefrorene Kopie /media/oem/scan/rc-park_tmp/fototor_bezug/v3_frei.stl)
mit seinen Kameras, 15 Fotos (5 eigene, 10 Commons). Faelle (alle mit dmed des Bezugs), jeder auch UMGEKEHRT (Bezug = Variante, neu = v3 -> Soll "besser"):
  dx002/dx005             2 / 5 cm seitlich (unter Druckaufloesung)      -> Soll gleich (Rauschgrenze)
  dx02/dx05/dx10, mdx02/mdx05, dy02/dy05/mdy02/mdy05   0,2-1 m seitlich  -> schlechter
  dz02/dz05/mdz02/mdz05   0,2 / 0,5 m Hoehe                              -> schlechter
  s102/s098               Massstab +-2 % um den Fusspunkt                -> schlechter
  falsch                  Kamera des naechsten Fotos gleicher Groesse auf diesem Bild -> schlechter
  auto_k                  schwab_auto mit SEINEN Kameras (ganze Kette, bekannt schlechter) -> schlechter
  auto_v3k                schwab_auto-STL mit den v3-Kameras (nur Modell) -> schlechter
  wieder                  gleiches Modell zweimal                        -> gleich, Differenz exakt 0
Modellvarianten als gleichwertige Kameratrafo (foto_tor_bezug.messen modell_trafo; kein STL je Variante, Datenplatte voll).
Masken je Fall und Foto werden unter <WD>/masken zwischengespeichert (--neu = neu rechnen, ~25 min GPU); Auswertung je Foto UND Gesamt (Mittel ueber Fotos, foto_tor_bezug.gesamt).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_foto_tor_bezug.py [--neu] [--fotos a,b] [--teil 6]   -> <WD>/ergebnis.json
"""
import sys, os, json, time, argparse, itertools, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_tor_bezug as T

ROOT = T.ROOT; WD = "/media/oem/scan/rc-park_tmp/fototor_bezug"; MD = os.path.join(WD, "masken"); os.makedirs(MD, exist_ok=True)
O3 = os.path.join(ROOT, "modelle/schwab_v3/objekt.json"); OA = os.path.join(ROOT, "modelle/schwab_auto/objekt.json")
FOTOS = ["eigen__IMG_20261106_" + x for x in ("113337", "113545_1", "113744_1", "113852", "114133")] + ["commons_orig2__" + x for x in ("004", "009", "012", "016", "019", "033", "044", "045", "047", "048")]
EINH = 0.087
VERSATZ = dict(dx002=(0.02, 0, 0), dx005=(0.05, 0, 0), dx02=(0.2, 0, 0), dx05=(0.5, 0, 0), dx10=(1.0, 0, 0), mdx02=(-0.2, 0, 0), mdx05=(-0.5, 0, 0),
               dy02=(0, 0.2, 0), dy05=(0, 0.5, 0), mdy02=(0, -0.2, 0), mdy05=(0, -0.5, 0), dz02=(0, 0, 0.2), dz05=(0, 0, 0.5), mdz02=(0, 0, -0.2), mdz05=(0, 0, -0.5))
MASSSTAB = dict(s102=1.02, s098=0.98)
GLEICH = ("dx002", "dx005")
DEUTLICH = ("dx05", "dx10", "mdx05", "dy05", "mdy05", "dz05", "mdz05", "s102", "s098", "falsch", "auto_k", "auto_v3k")   # >= 0,5 m, 2 %, falsche Kamera, Fremdmodell


def messen_alle(fotos, neu=False):
    b3 = os.path.join(WD, "v3_frei.stl"); ba = os.path.join(WD, "auto_frei.stl")
    for q, z in ((os.path.join(ROOT, "modelle/stl/schwab_v3_1-87.stl"), b3), (os.path.join(ROOT, "modelle/stl/schwab_auto_1-87.stl"), ba)):
        if not os.path.exists(z): import shutil; shutil.copy(q, z)
    m0 = trimesh.load(b3); fuss = (np.r_[m0.bounds.mean(0)[:2], m0.bounds[0, 2]] * EINH).tolist(); del m0
    bild = {nr: os.path.join(ROOT, "daten/schwab_v3/fotos", nr + ".jpg") for nr in fotos}; mp = os.path.join(MD, "meta.json")
    meta = json.load(open(mp)) if os.path.exists(mp) and not neu else {}; zeiten = []
    def da(k, nr): return os.path.exists(os.path.join(MD, f"{k}__{nr}.npz")) and not neu
    def spei(k, nr, m): T._speichern(os.path.join(MD, f"{k}__{nr}.npz"), m); meta.setdefault(nr, {}).setdefault("sitz", {})[k] = m["sitz"]
    for nr in fotos:
        if da("orig", nr) and "sekunden" in meta.get(nr, {}): continue
        t0 = time.time(); b = T.messen(O3, nr, bild[nr], b3); zeiten.append(time.time() - t0); spei("orig", nr, b)
        meta[nr].update(dmed=b["dmed"], ppm=b["ppm"], form=list(b["mk"].shape), bild=bild[nr], sekunden=round(zeiten[-1], 1))
        w = T.messen(O3, nr, bild[nr], b3, dmed_fix=b["dmed"]); spei("wieder", nr, w); print(nr, "Bezug", round(zeiten[-1], 1), "s", flush=True)
    json.dump(meta, open(mp, "w"))
    for i, nr in enumerate(fotos):
        js = [fotos[(i + k) % len(fotos)] for k in range(1, len(fotos)) if meta[fotos[(i + k) % len(fotos)]]["form"] == meta[nr]["form"]]
        if js and not da("falsch", nr): spei("falsch", nr, T.messen(O3, js[0], bild[nr], b3, dmed_fix=meta[nr]["dmed"])); meta[nr]["falsch_kamera"] = js[0]
    faelle = [(k, O3, b3, dict(d=list(d), s=1.0, p=fuss)) for k, d in VERSATZ.items()] + [(k, O3, b3, dict(d=[0, 0, 0], s=s, p=fuss)) for k, s in MASSSTAB.items()] + [("auto_k", OA, ba, None), ("auto_v3k", O3, ba, None)]
    for k, o, stl, tr in faelle:
        for nr in fotos:
            if da(k, nr): continue
            t0 = time.time(); spei(k, nr, T.messen(o, nr, bild[nr], stl, dmed_fix=meta[nr]["dmed"], modell_trafo=tr)); zeiten.append(time.time() - t0)
        json.dump(meta, open(mp, "w")); print(k, flush=True)
    return meta, zeiten


def auswerten(fotos, meta, teil):
    p = dict(T.STANDARD); faelle = ["wieder", "falsch", "auto_k", "auto_v3k"] + list(VERSATZ) + list(MASSSTAB); E = {}
    for k in faelle:
        for nr in fotos:
            q = os.path.join(MD, f"{k}__{nr}.npz")
            if not os.path.exists(q): continue
            b = T._laden(os.path.join(MD, f"orig__{nr}.npz")); b["ppm"] = meta[nr]["ppm"]; n = T._laden(q); sb, sn = meta[nr]["sitz"]["orig"], meta[nr]["sitz"][k]
            for rueck in (False, True):
                e = T.vergleichen(n, b, p) if rueck else T.vergleichen(b, n, p); e.pop("_kacheln", None)
                if T.sitz_sperre(sb, sn, p) and e.get("urteil") != "nicht beurteilbar": e["urteil_roh"] = e["urteil"]; e["urteil"] = "nicht beurteilbar"; e["grund"] = "sitzt nicht"
                for f in e.get("fassaden", {}).values(): f.pop("kanten_px", None)
                E.setdefault(k + ("_r" if rueck else ""), {})[nr] = e
        print("ausgewertet", k, flush=True)
    soll = lambda k: ("besser" if k.endswith("_r") else "schlechter") if k.split("_r")[0] not in GLEICH + ("wieder",) else "gleich"
    Z = {}
    for k, ef in E.items():
        g = T.gesamt(ef, p); us = [e["urteil"] for e in ef.values()]
        d = {nr: e["diff"] for nr, e in ef.items() if e["urteil"] != "nicht beurteilbar"}; teil_u = []
        for sub in list(itertools.combinations(sorted(d), min(teil, len(d))))[:200]:          # Gesamtkette prueft weniger Fotos: Untermengen
            teil_u.append(T.gesamt({s: ef[s] for s in sub}, p, seed=len(teil_u))["urteil"])
        Z[k] = dict(soll=soll(k), gesamt=g["urteil"], mittel=g.get("mittel_diff"), ki90=g.get("ki90"), fotos={u: us.count(u) for u in sorted(set(us))},
                    vorzeichen_richtig=sum(1 for v in d.values() if (v > 0) == (soll(k) == "schlechter")) if soll(k) != "gleich" else None, beurteilbar=len(d),
                    teil=dict(n=min(teil, len(d)), richtig=round(float(np.mean([u == soll(k) for u in teil_u])), 3) if teil_u else None,
                              falsche_richtung=round(float(np.mean([u in ("besser", "schlechter") and u != soll(k) for u in teil_u])), 3) if teil_u else None),
                    fassaden={f: v["urteil"] for f, v in g["fassaden"].items()})
    def q(sel, feld="gesamt"):
        ks = [k for k in Z if sel(k)]; return dict(richtig=sum(Z[k][feld] == Z[k]["soll"] for k in ks), faelle=len(ks), falsche_richtung=sum(Z[k][feld] in ("besser", "schlechter") and Z[k][feld] != Z[k]["soll"] for k in ks))
    basis = lambda k: k.split("_r")[0]
    vz_n = sum(Z[k]["beurteilbar"] for k in Z if Z[k]["vorzeichen_richtig"] is not None); vz_ok = sum(Z[k]["vorzeichen_richtig"] for k in Z if Z[k]["vorzeichen_richtig"] is not None)
    fo_n = sum(Z[k]["beurteilbar"] for k in Z if Z[k]["soll"] != "gleich"); fo_ok = sum(1 for k in Z if Z[k]["soll"] != "gleich" for nr, e in E[k].items() if e["urteil"] == Z[k]["soll"])
    fa = [(f, u, Z[k]["soll"]) for k in Z if basis(k) in DEUTLICH for f, u in Z[k]["fassaden"].items() if u != "nicht beurteilbar"]
    hb = [(e["ki95"][1] - e["ki95"][0]) / 2 for k in E for e in E[k].values() if e.get("ki95") and e["urteil"] != "nicht beurteilbar"]
    R = dict(deutlich=q(lambda k: basis(k) in DEUTLICH), alle_ab_02m=q(lambda k: Z[k]["soll"] != "gleich"), gleich_faelle=q(lambda k: Z[k]["soll"] == "gleich"),
             teil_deutlich=round(float(np.mean([Z[k]["teil"]["richtig"] for k in Z if basis(k) in DEUTLICH and Z[k]["teil"]["richtig"] is not None])), 3),
             teil_falsche_richtung_max=max(Z[k]["teil"]["falsche_richtung"] or 0 for k in Z),
             je_foto_vorzeichen=dict(richtig=vz_ok, von=vz_n), je_foto_signifikant=dict(richtig=fo_ok, von=fo_n),
             je_fassade_deutlich=dict(richtig=sum(u == s for f, u, s in fa), von=len(fa), falsche_richtung=sum(u in ("besser", "schlechter") and u != s for f, u, s in fa)),
             rauschen=dict(wiederholung_max_abs=max(abs(e.get("diff") or 0) for e in E["wieder"].values()), je_foto_bootstrap_halbbreite_median=round(float(np.median(hb)), 4),
                           mittel_2cm=Z["dx002"]["mittel"], mittel_5cm=Z["dx005"]["mittel"], pool_floor=p["pool_floor"]),
             sitz_bezug={nr: meta[nr]["sitz"]["orig"]["gewinn"] for nr in fotos})
    return Z, R, E


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--neu", action="store_true"); ap.add_argument("--fotos"); ap.add_argument("--teil", type=int, default=6)
    a = ap.parse_args(); fotos = a.fotos.split(",") if a.fotos else FOTOS
    meta, zeiten = messen_alle(fotos, a.neu)
    Z, R, E = auswerten(fotos, meta, a.teil)
    R["sekunden_je_foto_messung"] = dict(median=round(float(np.median([meta[nr]["sekunden"] for nr in fotos])), 1), max=round(float(max(meta[nr]["sekunden"] for nr in fotos)), 1))
    json.dump(dict(parameter=T.STANDARD, fotos=fotos, ergebnis=R, faelle=Z, einzeln=E), open(os.path.join(WD, "ergebnis.json"), "w"), indent=1, ensure_ascii=False)
    for k, z in Z.items(): print(f"{k:11s} soll {z['soll']:10s} GESAMT {z['gesamt']:17s} Mittel {z['mittel']} KI90 {z['ki90']} | Fotos {z['fotos']} | {z['teil']['n']} Fotos: {z['teil']['richtig']} | Fassaden {z['fassaden']}")
    print(json.dumps(R, ensure_ascii=False))
    d = R["deutlich"]; return 0 if d["richtig"] >= 0.9 * d["faelle"] and d["falsche_richtung"] == 0 and R["gleich_faelle"]["falsche_richtung"] == 0 else 1


if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("test_foto_tor_bezug")
    sys.exit(main())
