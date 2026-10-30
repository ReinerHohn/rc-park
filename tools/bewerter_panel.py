#!/usr/bin/env python3
"""bewerter_panel.py — PANELS statt Einzel-Juroren.

Pro Kategorie (Markanz · Geometrie-Treue/Modelltreue · Fertigbarkeit) sitzen 3 UNABHÄNGIGE
Juroren mit je anderer Methode. Sie stimmen HART ab:

  Kategorie-Urteil:
    PASS  nur wenn ALLE 3 Juroren PASS sagen (EINSTIMMIG).
    FAIL  sobald ein Juror FAIL sagt.
    WARN  gemischt (kein FAIL, aber nicht einstimmig) — Uneinigkeit wird benannt.

Verschiedene Methoden pro Kategorie, damit Einstimmigkeit echte Sicherheit bedeutet
(Redundanz würde nur Scheinsicherheit geben). "Modellgetreu" ist das oberste Ziel →
die Geometrie-Treue-Kategorie ist am strengsten und für Bauwerke architektonisch hart.
"""
import os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bewerter_common as bc
import validate_modell as vm


def V(score, warn=55, pas=70):
    return "PASS" if score >= pas else ("WARN" if score >= warn else "FAIL")


def J(name, score, reason):
    return {"name": name, "score": round(float(bc.clamp(score)), 1),
            "verdict": V(bc.clamp(score)), "reason": reason}


# ============================ Kontext (einmal rechnen) ============================

def build_context(m):
    ctx = {"m": m, "typ": m.get("typ", "gelaende")}
    spec = m.get("bauwerk")
    ctx["is_bauwerk"] = bool(ctx["typ"] == "bauwerk" and spec and spec.get("stl")
                             and os.path.exists(spec["stl"]))
    if ctx["is_bauwerk"]:
        import bewerter_bauwerk_geom as bg
        ctx["probe"] = bg.probe(spec["stl"])
        ctx["spec"] = spec
    # DEM-Kontext (Gelände-Site; Bauwerke haben oft auch ein Gelände-DEM für Markanz)
    try:
        rel = bc.load_relief(m)
        ctx["relief"] = rel
        ctx["cell"] = m["cell_m"]
        recon, support = vm.nan_smooth(rel, m["smooth"])
        ctx["err_mm"] = (recon - rel) * m["nscale"] * m["vscale"]
        ctx["support"] = support
        ctx["slope"] = bc.slope_deg(rel, m["cell_m"])
        ctx["best"] = bc.best_window_drama(rel, m["cell_m"], 0.5, 45.0)
    except Exception:
        ctx["relief"] = None
    # Artefakte
    svgs, stls = bc.parse_artifacts(m)
    bstl = m.get("bauwerk", {}).get("stl", "")
    if bstl and os.path.exists(bstl) and bstl not in stls:
        stls = stls + [bstl]
    ctx["svgs"], ctx["stls"] = svgs, stls
    return ctx


# ============================ GEOMETRIE / MODELLTREUE ============================
# drei unabhängige Lesarten: punktweise RMS · Grat-/Kantentreue · Form-Statistik
# (für Bauwerke: Durchsicht-Topologie · Rhythmus/Relief · Proportion+Mesh)

def geo_terrain(ctx):
    rel, err, sup = ctx["relief"], ctx["err_mm"], ctx["support"]
    e = err[sup]
    rms = float(np.sqrt(np.mean(e**2))) if e.size else 0.0
    p95 = float(np.percentile(np.abs(e), 95)) if e.size else 0.0
    # G1 punktweise Oberflächentreue
    g1 = J("Oberflächen-RMS", bc.lin(8 - rms, 0, 6),
           f"RMS {rms:.2f} mm, P95 {p95:.2f} mm (ganze Fläche)")
    # G2 Grat-/Kantentreue (unabhängig: nur steilste 20 %)
    gy, gx = np.gradient(rel); grad = np.hypot(gx, gy)
    mask = sup & (grad >= np.percentile(grad[sup], 80))
    er = err[mask]; rr = float(np.sqrt(np.mean(er**2))) if er.size else 0.0
    g2 = J("Grat-/Kantentreue", bc.lin(12 - rr, 0, 9),
           f"RMS {rr:.2f} mm auf den steilsten 20 % (scharfe Kanten)")
    # G3 Form-Statistik (unabhängig: bleibt die Steilheits-Verteilung erhalten?)
    cell = ctx["cell"]
    steep_raw = (bc.slope_deg(rel, cell) >= 30).mean()
    recon = rel + err / (ctx["m"]["nscale"] * ctx["m"]["vscale"])   # geglättetes Modell (m)
    steep_mod = (bc.slope_deg(recon, cell) >= 30).mean()
    ratio = steep_mod / (steep_raw + 1e-9)
    g3 = J("Form-Statistik", bc.lin(ratio, 0.55, 0.9),
           f"Steilflächen-Erhalt {ratio*100:.0f} % (Hang-Verteilung modelltreu?)")
    return [g1, g2, g3]


def geo_bauwerk(ctx):
    p, spec = ctx["probe"], ctx["spec"]
    arch = spec.get("archetyp", "viadukt")
    N = spec.get("n", 0); L = spec.get("L", p["L"]); H = spec.get("H", p["H"])
    # B1 Durchsicht-Topologie (Viadukt: Löcher; Mauer: muss massiv sein)
    if arch in ("viadukt", "bruecke"):
        dn = abs(p["n_through"] - N)
        s = 100 - bc.clamp(dn * 22) - (45 if p["fill"] > 0.72 else 0)
        b1 = J("Durchsicht-Topologie", s,
               f"{p['n_through']} Durchsichten (Soll {N}), Füllgrad {p['fill']} "
               f"{'— WAND MIT NISCHEN!' if p['fill']>0.72 else ''}")
    elif arch in ("bogenstaumauer", "bogenmauer"):
        leak = p["openness_through"] > 0.06 or p["fill"] < 0.85
        b1 = J("Dichtheit/Massivität", 100 - (55 if leak else 0),
               f"Durchsicht {p['openness_through']}, Füllgrad {p['fill']} "
               f"{'— durchsichtig, hält kein Wasser!' if leak else '(massiv ✓)'}")
    else:
        b1 = J("Dichtheit/Massivität", 100 - (40 if p["openness_through"] > 0.06 else 0),
               f"Durchsicht {p['openness_through']} (massiver Block erwartet)")
    # B2 Rhythmus / Relief-Bögen + Regelmäßigkeit (unabhängig von B1)
    n_meas = p["n_through"] if arch in ("viadukt", "bruecke") else p["n_relief"]
    cv = max(p["gap_cv"], p["width_cv"]); dn = abs(n_meas - N)
    s2 = 100 - bc.clamp(dn * 18) - (0 if cv <= 0.15 else bc.clamp((cv - 0.15) * 200))
    b2 = J("Bogen-Rhythmus", s2,
           f"{n_meas} Bögen (Soll {N}), Regelmäßigkeit-CV {cv:.2f}")
    # B3 Proportion + Mesh-Solidität (unabhängig)
    lh_err = abs(p["LH"] / (L / H) - 1)
    s3 = 100 - bc.clamp(lh_err * 140) - (0 if p["watertight"] else 15)
    b3 = J("Proportion+Mesh", s3,
           f"L:H {p['LH']} (Soll {round(L/H,2)}, Δ{lh_err*100:.0f} %), "
           f"watertight={p['watertight']} (euler {p['euler']})")
    return [b1, b2, b3]


def panel_geometrie(ctx):
    return geo_bauwerk(ctx) if ctx["is_bauwerk"] else geo_terrain(ctx)


# ============================ MARKANZ ============================
# drei unabhängige Lesarten: Fallhöhe · Wand-Schärfe · Prägnanz/Rhythmus

def markanz_terrain(ctx):
    rel, cell = ctx["relief"], ctx["cell"]
    relief_m = float(rel.max())
    sf, prel, p95, box = ctx["best"]
    m1 = J("Fallhöhe/Relief", bc.lin(relief_m, 25, 180), f"Reliefspanne {relief_m:.0f} m")
    m2 = J("Wand-Schärfe", bc.lin(sf, 0.03, 0.25) * 0.6 + bc.lin(p95, 22, 58) * 0.4,
           f"Steilwand {sf*100:.0f} % ≥45°, p95-Neigung {p95:.0f}° (bester Ausschnitt)")
    # robuste Formfülle (TRI), ZELLGRÖSSEN-normiert (dimensionslos) — fair für symm. Kegel
    tri = bc.ruggedness(rel, cell) / cell
    m3 = J("Formfülle", bc.lin(tri, 0.20, 0.50), f"Geländerauheit {tri:.2f} (mittl. Steigung, skulptiert?)")
    return [m1, m2, m3]


def markanz_bauwerk(ctx):
    p, spec = ctx["probe"], ctx["spec"]
    arch = spec.get("archetyp", "viadukt")
    n = p["n_through"] if arch in ("viadukt", "bruecke") else p["n_relief"]
    cv = max(p["gap_cv"], p["width_cv"]); L, H = spec.get("L", p["L"]), spec.get("H", p["H"])
    is_arch = arch in ("viadukt", "bruecke", "bogenstaumauer", "bogenmauer")
    m1 = J("Größe/Präsenz", bc.lin(max(L, H), 40, 160) * 0.65 + bc.lin(H, 10, 55) * 0.35,
           f"Bauwerk ~{L}×{H} m")
    if is_arch:
        m2 = J("Bogen-Rhythmus", bc.lin(n, 1, 9), f"{n} Bögen (Mehrbogen = ikonisch)")
        m3 = J("Regelmäßigkeit", bc.lin(0.2 - cv, 0, 0.18), f"Rhythmus-CV {cv:.2f}")
    else:
        # monolithischer Block: beeindruckend, aber wenig unverwechselbar → gedeckelt
        m2 = J("Unverwechselbarkeit", 55, "monolithischer Block ohne Rhythmus (gedeckelt)")
        m3 = J("Höhe", bc.lin(H, 20, 70), f"Höhe {H} m")
    return [m1, m2, m3]


def panel_markanz(ctx):
    return markanz_bauwerk(ctx) if ctx["is_bauwerk"] else markanz_terrain(ctx)


# ============================ FERTIGBARKEIT ============================
# drei unabhängige Lesarten: passt aufs Bett · Robustheit · Aufwand/Material

def _bboxes(svgs):
    import bewerter_fertigung as jf
    return jf._svg_part_bboxes(svgs)


def fertigung(ctx):
    m = ctx["m"]; bx, by = m["bed"]; svgs, stls = ctx["svgs"], ctx["stls"]
    # F1 passt aufs Bett
    if svgs:
        bbs = _bboxes(svgs); over = [b for b in bbs if b[1] > bx or b[2] > by]
        f1 = J("Bett-Fit", 100 - 40 * bool(over),
               f"{len(svgs)} Teile, {len(over)} zu groß fürs Bett {bx}×{by}")
    elif stls:
        ok = True; dims = []
        for s in stls:
            try:
                sh = bc.stl_health(s, bx, by); dims.append(sh); ok &= sh["fits_bed"]
            except Exception:
                pass
        f1 = J("Bett-Fit", 100 - (30 if not ok else 0),
               f"{len(stls)} STL, Bett-ok={ok}" + (f", {dims[0]['mm']} mm" if dims else ""))
    else:
        rel = ctx.get("relief");
        if rel is None:
            return [J("Bett-Fit", 60, "keine Artefakte, kein DEM — nur grobe Schätzung")]*1 + \
                   [J("Robustheit", 60, "n/a"), J("Aufwand", 60, "n/a")]
        ny, nx = rel.shape; w = nx * m["mm_per_cell"]; h = ny * m["mm_per_cell"]
        tiles = int(np.ceil(w / bx)) * int(np.ceil(h / by))
        f1 = J("Bett-Fit", 100 - bc.clamp(8 * (tiles - 1)),
               f"Szene {w:.0f}×{h:.0f} mm → {tiles} Bett-Kacheln")
    # F2 Robustheit (dünne Stellen / watertight / Mini-Teile)
    if svgs:
        bbs = _bboxes(svgs); tiny = [b for b in bbs if min(b[1], b[2]) < 8]
        f2 = J("Robustheit", 100 - bc.clamp(6 * len(tiny)),
               f"{len(tiny)} Mini-Teile <8 mm (Bruchrisiko)")
    elif stls:
        wt = True
        for s in stls:
            try: wt &= bc.stl_health(s, bx, by)["watertight"]
            except Exception: pass
        f2 = J("Robustheit", 100 - (30 if not wt else 0),
               f"STL watertight={wt}" + ("" if wt else " → reparieren"))
    else:
        f2 = J("Robustheit", 80, "ohne Artefakt: adaptive Rippen/min-web greifen (Annahme)")
    # F3 Aufwand/Material — Gelände über Bretter, BAUWERK über die Struktur (nicht die DEM-Site!)
    rel = ctx.get("relief")
    if rel is not None and not ctx["is_bauwerk"]:
        ny, nx = rel.shape; w = nx * m["mm_per_cell"]; h = ny * m["mm_per_cell"]
        sheets = max(1, int(np.ceil((w * h) / (bx * by * 0.6))))
        f3 = J("Aufwand", 100 - bc.clamp(6 * (sheets - 1)),
               f"~{sheets} Bretter (≈{sheets*8} min Schnitt)")
    elif ctx["is_bauwerk"]:
        vol = ctx["probe"]
        f3 = J("Aufwand", 85, f"Bauwerk ~{vol['L']}×{vol['H']} m: ein Druck/Teilesatz")
    else:
        f3 = J("Aufwand", 85, "ein Teilesatz")
    return [f1, f2, f3]


# ============================ Aggregation ============================

def consensus(subs):
    """HART: PASS nur einstimmig; FAIL sobald ein Juror FAIL; sonst WARN."""
    verds = [s["verdict"] for s in subs]
    if any(v == "FAIL" for v in verds):
        cat = "FAIL"
    elif all(v == "PASS" for v in verds):
        cat = "PASS"
    else:
        cat = "WARN"
    score = float(np.mean([s["score"] for s in subs]))
    unanimous = len(set(verds)) == 1
    dissent = [s for s in subs if s["verdict"] != max(set(verds), key=verds.count)]
    return {"verdict": cat, "score": round(score, 1), "unanimous": unanimous,
            "subs": subs, "dissent": dissent}


WEIGHT = {"Geometrie-Treue": 0.40, "Markanz": 0.35, "Fertigbarkeit": 0.25}


def evaluate(m):
    ctx = build_context(m)
    cats = {
        "Geometrie-Treue": consensus(panel_geometrie(ctx)),
        "Markanz": consensus(panel_markanz(ctx)),
        "Fertigbarkeit": consensus(fertigung(ctx)),
    }
    mean = sum(WEIGHT[k] * c["score"] for k, c in cats.items())
    verds = [c["verdict"] for c in cats.values()]
    all_unanimous = all(c["unanimous"] for c in cats.values())
    if any(v == "FAIL" for v in verds):
        overall = "NACHBESSERN"
    elif all(v == "PASS" for v in verds) and all_unanimous:
        overall = "BAUEN (einstimmig)"
    elif all(v == "PASS" for v in verds):
        overall = "BAUEN"
    elif not any(v == "FAIL" for v in verds) and mean >= 60:
        overall = "BEDINGT"
    else:
        overall = "VERWERFEN"
    # größter Einwand: niedrigster Sub-Juror über alle Kategorien
    allsubs = [(k, s) for k, c in cats.items() for s in c["subs"]]
    worst_k, worst = min(allsubs, key=lambda t: t[1]["score"])
    return {"name": m.get("name", "?"), "mean": round(mean, 1), "overall": overall,
            "cats": cats, "worst": f"{worst_k}/{worst['name']}", "einwand": worst["reason"]}


def report(res):
    ic = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
    oic = {"BAUEN (einstimmig)": "🟢🟢", "BAUEN": "🟢", "BEDINGT": "🟡",
           "NACHBESSERN": "🟠", "VERWERFEN": "🔴"}[res["overall"]]
    print("=" * 70)
    print(f"{oic}  {res['name']}  —  {res['mean']}/100  →  {res['overall']}")
    print("=" * 70)
    for k, c in res["cats"].items():
        u = "EINSTIMMIG" if c["unanimous"] else "uneinig"
        print(f"{ic[c['verdict']]} {k:<18} {c['score']:5.1f}  [{c['verdict']}, {u}]")
        for s in c["subs"]:
            print(f"      {ic[s['verdict']]} {s['name']:<22}{s['score']:5.1f}  {s['reason']}")
        if not c["unanimous"]:
            dn = ", ".join(f"{s['name']}={s['verdict']}" for s in c["subs"])
            print(f"      ⟹ nicht einstimmig: {dn}")
    print(f"\n  Größter Einwand: [{res['worst']}] {res['einwand']}\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--batch", nargs="*", default=[])
    ap.add_argument("--rank", action="store_true")
    a = ap.parse_args()
    paths = ([a.manifest] if a.manifest else [])
    for g in a.batch:
        paths += sorted(glob.glob(g))
    results = [evaluate(bc.load_manifest(p)) for p in paths]
    if a.rank:
        order = {"BAUEN (einstimmig)": 0, "BAUEN": 1, "BEDINGT": 2, "NACHBESSERN": 3, "VERWERFEN": 4}
        results.sort(key=lambda r: (order[r["overall"]], -r["mean"]))
        print("\n########  RANGLISTE (Panels, 3×3 Juroren, einstimmig gefordert)  ########")
        for i, r in enumerate(results, 1):
            print(f"{i:2}. {r['mean']:5.1f}  {r['overall']:<18} {r['name']:<30} (schwach: {r['worst']})")
        print()
    else:
        for r in results:
            report(r)
