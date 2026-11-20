#!/usr/bin/env python3
"""test_wolke_solid.py - Beweise T1-T4' der Spec S3b (vorab festgelegt, modelle/archiv/SPEC_S3b_WOLKE_ZUERST.md + Nutzerentscheid 5.11. 20:10/20:15).

Unterbefehle (jeder einzeln aufrufbar; foto_diff ist GPU-Arbeit -> per tools/job_start.sh, GPU-Sperre):
  fotodiff  OBJEKT.json STL AUSORDNER FOTOS(Komma) MASKENORDNER   foto_diff mit --bewertung-maske (kosten_lr) wie der lr-Nachtest (Register CM)
  vergleich KAUFHAUS|MARTINSTOR C'-AUSORDNER                       Tabelle C' gegen A, B, C (kosten_lr, gepaarter t), Pruefstand, Dach gegen DOM1/Stadtmesh (rein informativ)
Gate-Wort fuer job_start (GPU-Werkzeug-Liste): foto_diff.py
"""
import os, sys, json, glob, subprocess, time, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
BASIS = "/media/oem/scan/rc-park_null/beweis_ansatz"; PYSEG = "/media/oem/scan/venv-seg/bin/python"


def fotodiff(objp, stl, aus, fotos, maskdir):
    env = dict(os.environ, PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True", FD_GPU="1"); erg = {}
    for nr in fotos:
        a = os.path.join(aus, nr); os.makedirs(a, exist_ok=True); t0 = time.time()
        r = subprocess.run([PYSEG, "-W", "ignore", "-I", os.path.join(HERE, "foto_diff.py"), objp, nr, "--stl", stl, "--aus", a, "--mehrstufig", "--bewertung-maske", os.path.join(maskdir, f"{nr}.png")], cwd=ROOT, env=env, capture_output=True, text=True)
        try: j = json.load(open(os.path.join(a, f"foto_diff_{nr}.json")))
        except Exception: open(os.path.join(a, "fehler.log"), "w").write(f"rc {r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-3000:]}"); erg[nr] = None; print("Fehler", nr, flush=True); continue
        erg[nr] = dict(kosten_lr=j.get("kosten_lr"), kosten_param=j.get("kosten_param"), rot=j.get("anteil_modellkanten_ohne_foto"), gelb=j.get("anteil_fotokanten_ohne_modell"), s=round(time.time() - t0, 1))
        print(nr, erg[nr], flush=True)
    json.dump(erg, open(os.path.join(aus, "lr_ergebnis.json"), "w"), indent=1)


def fassaden_martinstor(aus, stl, zelle=0.10):
    """Martinstor-Nordfassade fuer den Test T3: LoD2-Wandebene (fassade_ortho.lod2_waende/fassaden_gruppieren, keine Fotos noetig), gewaehlt wird die Wand, deren Aussenseite zur Nordwolke zeigt;
    u/z-Raster aus LoD2-Breite (+1 m) und Modellhoehe. Die Ebene wird danach vom Widerspruchstest gegen die Wolke geprueft (wolke_solid.wand_status)."""
    import trimesh, beweis_ansatz as BA, fassade_ortho as FO
    objp = os.path.join(ROOT, "modelle", "martinstor_lod2", "objekt.json"); obj = json.load(open(objp)); import objekt_rahmen as OR; obj = OR.ergaenzen(obj, os.path.dirname(objp))
    k = BA.konfig(os.path.join(ROOT, "modelle", "martinstor", "objekt.json"), aus); X, N, _ = BA.wolke_modellrahmen(k["dicht"], k["ausr"], 3)
    waende, gr = FO.lod2_waende(obj); G = FO.fassaden_gruppieren(waende, gr, min_flaeche=4.0); cen = np.median(X[:, :2], 0); dirv = (cen - gr) / np.linalg.norm(cen - gr)
    m = trimesh.load(stl); m.apply_scale(87 / 1000.0); zmax = float(m.bounds[1][2]); zmin = float(m.bounds[0][2])
    cand = [g for g in G if np.array(g["n"]) @ dirv > 0.5]
    if not cand: raise SystemExit(f"keine LoD2-Wand zur Nordwolke (Richtung {dirv}); Waende: {[g['n'] for g in G]}")
    F = dict(cand[0]); F["id"] = "n00"; F["u"] = [F["u"][0] - 1.0, F["u"][1] + 1.0]; F["z"] = [zmin, zmax]; nu = int(np.ceil((F["u"][1] - F["u"][0] + 1.0) / zelle)); nz = int(np.ceil((zmax - zmin + 1.0) / zelle))
    F["raster"] = dict(u0=F["u"][0] - 0.5, z1=zmax + 0.5, nu=nu, nz=nz, zelle=zelle); F["flaeche_m2"] = round(float((F["u"][1] - F["u"][0]) * (zmax - zmin)), 1); F.pop("polys_uz", None)
    os.makedirs(aus, exist_ok=True); pf = os.path.join(aus, "fassaden_martinstor.json"); json.dump(dict(fassaden=[F], quelle="LoD2 Wand + Modellhoehe", richtung_wolke=dirv.tolist()), open(pf, "w")); return pf


def synth(aus, stark=True):
    """T1: Wahrheit = Martinstor-Generator-Variante (beweis_ansatz_synth 'stark'), Wolke = nur von den 10 echten Kameras sichtbare Oberflaechenpunkte (>= 2 Kameras, 5 cm Rauschen; wolke_synth.npz des Beweislaufs),
    Start-'Modell' = Standardgenerator (basis). Die Wolke bekommt dummy-vis (3 Kameras je Punkt) und Identitaetsausrichtung; Freiraum entfaellt (keine Kamerazentren in der Wolkendatei)."""
    import trimesh, wolke_solid as WS, beweis_ansatz_synth as BS
    B = os.path.join(BASIS, "synthetisch_stark" if stark else "synthetisch"); z = np.load(os.path.join(B, "wolke_synth.npz")); Pp, Nn = z["P"], z["N"]; d = os.path.join(aus, "synth_dicht"); os.makedirs(d, exist_ok=True)
    hd = ("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\nend_header\n" % len(Pp)).encode()
    with open(os.path.join(d, "fused.ply"), "wb") as f: f.write(hd); f.write(np.c_[Pp, Nn].astype("<f4").tobytes())
    vis = [np.array([len(Pp) & 0xffffffff, len(Pp) >> 32], "<u4")]; rec = np.tile(np.array([3, 0, 1, 2], "<u4"), (len(Pp), 1)); open(os.path.join(d, "fused.ply.vis"), "wb").write(vis[0].tobytes() + rec.tobytes())
    ausr = os.path.join(d, "ausrichtung.json"); json.dump(dict(transformation=dict(s=1.0, rvec=[0, 0, 0], t=[0, 0, 0])), open(ausr, "w"))
    basis = os.path.join(B, "basis_1-87.stl"); wahr = os.path.join(B, "wahrheit_1-87.stl"); pf = fassaden_martinstor(aus, basis)
    erg = WS.lauf(os.path.join(ROOT, "modelle", "martinstor", "objekt.json"), basis, pf, os.path.join(aus, "lauf"), dicht=d, ausr=ausr, dach="wolke", freiraum=False, min_flaeche=4.0)
    g = {n: BS.geometrie_gegen_wahrheit(wahr, st) for n, st in (("C_basis", basis), ("Cp_wolke_solid", erg["stl_ausgabe"]))}
    # unbeobachtet: Oberflaechenpunkte von C', die weiter als 0,5 m von jedem Wolkenpunkt entfernt sind, muessen dem Modell entsprechen
    from scipy.spatial import cKDTree
    m = trimesh.load(erg["stl_ausgabe"]); m.apply_scale(87 / 1000.0); mb = trimesh.load(basis); mb.apply_scale(87 / 1000.0)
    S, _ = trimesh.sample.sample_surface(m, 100000, seed=3); S = np.asarray(S); fern = cKDTree(Pp).query(S, distance_upper_bound=0.5)[0] > 0.5
    from trimesh.proximity import closest_point
    dist = np.abs(trimesh.proximity.ProximityQuery(mb).signed_distance(S[fern][:20000])) if fern.any() else np.array([])
    erg_t1 = dict(geometrie=g, unbeobachtet_anteil=round(float(fern.mean()), 3), unbeobachtet_abstand_zu_C_median_m=round(float(np.median(dist)), 4) if len(dist) else None, unbeobachtet_anteil_ueber_3_5cm=round(float(np.mean(dist > 0.035)), 3) if len(dist) else None)
    json.dump(erg_t1, open(os.path.join(aus, "t1.json"), "w"), indent=1); print(json.dumps(erg_t1, indent=1)); return erg_t1


def endvergleich(objekt, stls, aus_json):
    """T4' / Endvergleich (REIN INFORMATIV, kein Eingang ins Modell): Dach der Modelle gegen DOM1 (Zellmaximum und Strahl, BA.dach_dom1) und gegen Stadtmesh (Strahl auf Zellmitte), First = hoechster Punkt.
    stls: Name=Pfad (STL mm 1:87)."""
    import trimesh, beweis_ansatz as BA
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    k = BA.konfig(os.path.join(ROOT, "modelle", objekt, "objekt.json"), "/tmp"); D = BA.dom1_laden(k); eigen, art = BA.eigener_grundriss(k, D); out = dict(dom1=D["quelle"], grundriss=art)
    smp = os.path.join(ROOT, "modelle", objekt, "audit", "referenz_stadtmesh", "mesh.ply"); ms = trimesh.load(smp) if os.path.exists(smp) else None
    Z = D["Z"]; gy, gx = np.gradient(np.where(np.isfinite(Z), Z, 0.0)); zellen = eigen & (Z > 3) & (np.hypot(gx, gy) <= 2.5) & np.isfinite(Z); zi, zj = np.where(zellen)
    org = np.c_[D["lx"][zi, zj], D["ly"][zi, zj], np.full(len(zi), 200.0)]
    def strahl(m):
        loc, ri, _ = RayMeshIntersector(m).intersects_location(org, np.tile([0, 0, -1.0], (len(org), 1)), multiple_hits=True); H = np.full(len(org), np.nan)
        for q, l in zip(ri, loc): H[q] = l[2] if np.isnan(H[q]) else max(H[q], l[2])
        return H
    HS = strahl(ms) if ms is not None else None; out["first_dom1_max_m"] = round(float(np.nanmax(Z)), 2)
    for n, p in stls.items():
        m = trimesh.load(p, force="mesh"); m.apply_scale(87 / 1000.0); r, _ = BA.dach_dom1(m, D, eigen); H = strahl(m); d = {}
        d["first_m"] = round(float(m.bounds[1][2]), 2); d["dach_dom1_zellmax"] = r["zellmax"]; d["dach_dom1_strahl"] = r["strahl"]
        if HS is not None:
            ok = np.isfinite(H) & np.isfinite(HS); d["dach_stadtmesh_strahl"] = dict(zellen=int(ok.sum()), median_abs_m=round(float(np.median(np.abs(H - HS)[ok])), 3), bias_m=round(float(np.mean((H - HS)[ok])), 3)) if ok.any() else None
        out[n] = d
    json.dump(out, open(aus_json, "w"), indent=1); print(json.dumps(out, indent=1)); return out


def gepaart_t(a, b):
    d = np.array(a) - np.array(b); return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))) if len(d) > 1 and d.std(ddof=1) > 0 else float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd")
    f = sp.add_parser("fotodiff"); f.add_argument("objekt"); f.add_argument("stl"); f.add_argument("aus"); f.add_argument("fotos"); f.add_argument("masken"); f.add_argument("--gpu-werkzeug", help="nur Marker fuer tools/job_start.sh (GPU-Sperre): foto_diff.py")
    ev = sp.add_parser("endvergleich"); ev.add_argument("objekt"); ev.add_argument("stls", nargs="+"); ev.add_argument("--aus", required=True)
    sy = sp.add_parser("synth"); sy.add_argument("aus"); sy.add_argument("--schwach", action="store_true")
    m_ = sp.add_parser("fassaden_martinstor"); m_.add_argument("aus"); m_.add_argument("stl")
    v = sp.add_parser("vergleich"); v.add_argument("objekt"); v.add_argument("aus", nargs="+", help="eine oder mehrere C'-Ausordner mit lr_ergebnis.json; Name=Ordner"); v.add_argument("--bericht")
    a = ap.parse_args(argv)
    if a.cmd == "fotodiff": fotodiff(a.objekt, a.stl, a.aus, a.fotos.split(","), a.masken)
    elif a.cmd == "endvergleich": endvergleich(a.objekt, dict(x.split("=", 1) for x in a.stls), a.aus)
    elif a.cmd == "synth": synth(a.aus, not a.schwach)
    elif a.cmd == "fassaden_martinstor": print(fassaden_martinstor(a.aus, a.stl))
    elif a.cmd == "vergleich":
        tab = json.load(open(os.path.join(BASIS, "lr_tabelle.json")))[a.objekt]; fotos = sorted(k for k in tab["A"] if k[0].isdigit() or True)
        out = {}
        L = {v: {k: tab[v][k][0] for k in tab[v]} for v in ("A", "B", "C")}
        fotos = sorted(L["A"])
        for kv in a.aus:
            n, d = kv.split("=", 1); r = json.load(open(os.path.join(d, "lr_ergebnis.json"))); L[n] = {k: (r[k] or {}).get("kosten_lr") for k in fotos}
        print("Foto " + " ".join(f"{v:>9}" for v in L));
        for k in fotos: print(k, " ".join(f"{(L[v][k] if L[v][k] is not None else float('nan')):9.4f}" for v in L))
        mean = {v: float(np.mean([L[v][k] for k in fotos if L[v][k] is not None])) for v in L}; print("Mittel", " ".join(f"{mean[v]:9.4f}" for v in L))
        for n in [x.split("=")[0] for x in a.aus]:
            out[n] = dict(mittel=mean[n], t_gegen_A=gepaart_t([L[n][k] for k in fotos], [L["A"][k] for k in fotos]), t_gegen_C=gepaart_t([L[n][k] for k in fotos], [L["C"][k] for k in fotos]), t_gegen_B=gepaart_t([L[n][k] for k in fotos], [L["B"][k] for k in fotos]))
        out["_mittel"] = mean; out["_je_foto"] = L; print(json.dumps(out, indent=1))
        if a.bericht: json.dump(out, open(a.bericht, "w"), indent=1)


if __name__ == "__main__":
    main()
