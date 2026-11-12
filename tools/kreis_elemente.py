#!/usr/bin/env python3
"""kreis_elemente.py - ELEMENT-MESSREGION fuer das Rauschtor (tools/kreis_rauschtor.py, Auftrag 12.11.).

Warum: bei Reihen-Teilen (Baldachine, Konsolen, Figuren) und Teilen mit viel Ornament (Erker) ist die Messregion des Rauschtors das GANZE Teil; ein Element
belegt nur wenige Pixel, und die Nullkontrollen (0,3 m verschoben / angehoben / 90 Grad gedreht) verschieben die ganze Reihe -> das Signal einer
Einzelaenderung geht unter (R f1 -0,058, f1_fein -0,037). Hier wird das Teil in ELEMENTE geteilt; jedes Element ist ein eigenes "Teil" fuer
teil_varianten_tor.py / teil_fotoform.py (Nullkontrollen nur auf das Element, Foto-F1 nur in der Bildregion des Elements).

Teilung (Quelle = die Geometrie des Teil-STL, keine Namen):
  1. zusammenhaengende Dreiecksgruppen (Reihe: Baldachin, Figur, Konsole = je ein Koerper) - wenn >= 2 Gruppen mit je >= MIN_FLAECHEN Dreiecken;
  2. sonst (ein verschmolzener Koerper, z. B. Erker) Raster aus Zellen der Kantenlaenge zelle_m ueber die Dreiecksmitten; Zellen mit >= MIN_FLAECHEN Dreiecken.
  Hoechstens max_n Elemente (groesste Dreiecksflaeche zuerst). Element = Elementbox (Min/Max der Dreiecksmitten, Meter) + Dreiecksmenge.
Zuordnung Nachher-Teil -> Elemente: jedes Dreieck zur naechsten Elementbox des Vorher-Standes (Abstand Mitte-Box <= tol_m), so bleibt die Elementidentitaet
auch bei verschobenem/veraendertem Element erhalten.

CLI (venv-seg, trimesh/numpy):
  kreis_elemente.py teilen    --stl TEIL.stl --aus DIR --massstab 87 [--zelle_m 1.5 --max_n 8]   -> DIR/<teil>~e<i>.stl + DIR/elemente.json
  kreis_elemente.py zuordnen  --stl TEIL.stl --elemente DIR/elemente.json --aus DIR2 --massstab 87 [--tol_m 0.6]  -> DIR2/<name>.stl (nur nicht leere) + DIR2/zuordnung.json
Kein Objektname im Code.
"""
import os, sys, json, hashlib, argparse
import numpy as np, trimesh

MIN_FLAECHEN = 20


def _lade(stl, massstab):
    m = trimesh.load(stl, force="mesh"); k = massstab / 1000.0
    return m, np.asarray(m.triangles_center, float) * k


def _flaeche(m, idx): return float(np.asarray(m.area_faces)[idx].sum())


def teilen(stl, massstab=87.0, zelle_m=1.5, max_n=8, min_flaechen=MIN_FLAECHEN):
    """-> (modus, [ {idx (Dreiecksnummern), lo, hi (Meter)} ], mesh). modus 'komponenten' | 'raster' | 'ganz' (nicht teilbar)."""
    m, c = _lade(stl, massstab)
    comps = trimesh.graph.connected_components(m.face_adjacency, nodes=np.arange(len(m.faces)), min_len=1)
    comps = [np.asarray(x) for x in comps if len(x) >= min_flaechen]
    if len(comps) >= 2: modus, gruppen = "komponenten", comps
    else:
        org = c.min(0); zi = np.floor((c - org) / zelle_m).astype(int); keys = {}
        for i, k in enumerate(map(tuple, zi)): keys.setdefault(k, []).append(i)
        gruppen = [np.asarray(v) for v in keys.values() if len(v) >= min_flaechen]
        modus = "raster" if len(gruppen) >= 2 else "ganz"
    gruppen.sort(key=lambda g: -_flaeche(m, g)); gruppen = gruppen[:max_n]
    # Reihenfolge fuer stabile Namen: nach Lage (x, dann y, dann z der Boxmitte), nicht nach Flaeche
    gruppen.sort(key=lambda g: tuple(np.round(c[g].mean(0), 1)))
    el = [{"idx": g, "lo": c[g].min(0), "hi": c[g].max(0)} for g in gruppen]
    return modus, el, m


def _abstand(c, lo, hi):
    d = np.maximum(np.maximum(lo - c, c - hi), 0.0); return np.sqrt((d * d).sum(1))


def zuordnen(stl, elemente, massstab=87.0, tol_m=0.6):
    """Dreiecke des Teil-STL den Elementboxen zuordnen -> {name: idx}; Dreiecke > tol_m von jeder Box bleiben unzugeordnet (neu)."""
    m, c = _lade(stl, massstab)
    if not elemente: return m, {}
    D = np.stack([_abstand(c, np.asarray(e["lo"], float), np.asarray(e["hi"], float)) for e in elemente], 1)
    best = D.argmin(1); ok = D[np.arange(len(c)), best] <= tol_m
    return m, {e["name"]: np.flatnonzero(ok & (best == i)) for i, e in enumerate(elemente)}


def sha_idx(m, idx, nd=3):
    """Inhaltshash eines Dreiecksteilsatzes (Lage der Dreiecksmitten, STL-Einheit) - gleich = Element unveraendert."""
    if len(idx) == 0: return "leer"
    c = np.round(np.asarray(m.triangles_center)[idx], nd); c = c[np.lexsort(c.T[::-1])]
    return hashlib.sha1(c.tobytes()).hexdigest()[:12]


def _schreibe(m, idx, pfad):
    sub = m.submesh([np.asarray(idx)], append=True); sub.export(pfad)


def kleinste_kante_m(m, idx, massstab):
    p = np.asarray(m.triangles)[idx].reshape(-1, 3) * (massstab / 1000.0); return float((p.max(0) - p.min(0)).min())


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("modus", choices=["teilen", "zuordnen", "verschieben"]); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--zelle_m", type=float, default=1.5); ap.add_argument("--max_n", type=int, default=8)
    ap.add_argument("--elemente"); ap.add_argument("--tol_m", type=float, default=0.6); ap.add_argument("--teil")
    ap.add_argument("--teile_dir"); ap.add_argument("--gesamt"); ap.add_argument("--element"); ap.add_argument("--d", default="0,0,0", help="verschieben: dx,dy,dz in Metern")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    teil = a.teil or os.path.basename(a.stl)[:-4]
    if a.modus == "teilen":
        modus, el, _ = teilen(a.stl, a.massstab, a.zelle_m, a.max_n)
        box = [{"name": f"{teil}~e{i}", "lo": e["lo"].tolist(), "hi": e["hi"].tolist()} for i, e in enumerate(el)]
        m, zu = zuordnen(a.stl, box, a.massstab, a.tol_m); out = []   # dieselbe Zuordnung wie spaeter fuer Nachher-Staende (kleine Reststuecke gehen an die naechste Box)
        for b in box:
            idx = zu[b["name"]]; _schreibe(m, idx, os.path.join(a.aus, b["name"] + ".stl"))
            out.append({"name": b["name"], "lo": np.round(b["lo"], 3).tolist(), "hi": np.round(b["hi"], 3).tolist(), "flaechen": int(len(idx)), "flaeche_m2": round(_flaeche(m, idx) * (a.massstab / 1000.0) ** 2, 2),
                        "kleinste_kante_m": round(kleinste_kante_m(m, idx, a.massstab), 3), "sha": sha_idx(m, idx)})
        json.dump({"teil": teil, "modus": modus, "zelle_m": a.zelle_m, "massstab": a.massstab, "tol_m": a.tol_m, "elemente": out}, open(os.path.join(a.aus, "elemente.json"), "w"), ensure_ascii=False, indent=1)
        print(json.dumps({"modus": modus, "n": len(out)}))
    elif a.modus == "verschieben":
        # SYNTHETISCHER TEST (Beweis Elementtor): ein Element um d Meter verschieben -> neues Teile-Verzeichnis (andere Teile als Symlink, Teil-STL ersetzt) + Gesamt-STL
        E = json.load(open(a.elemente))["elemente"]; m, zu = zuordnen(a.stl, E, a.massstab, a.tol_m); idx = zu[a.element]
        k = a.massstab / 1000.0; T = np.eye(4); T[:3, 3] = np.array([float(x) for x in a.d.split(",")]) / k
        el = m.submesh([idx], append=True); rest = m.submesh([np.setdiff1d(np.arange(len(m.faces)), idx)], append=True)
        el2 = el.copy(); el2.apply_transform(T); neu = trimesh.util.concatenate([rest, el2]); neu.export(os.path.join(a.aus, teil + ".stl"))
        for f in os.listdir(a.teile_dir):
            if f.endswith(".stl") and f not in (teil + ".stl", "gesamt.stl") and not os.path.lexists(os.path.join(a.aus, f)): os.symlink(os.path.abspath(os.path.join(a.teile_dir, f)), os.path.join(a.aus, f))
        g = trimesh.load(a.gesamt, force="mesh"); sk = {tuple(np.round(x, 3)) for x in el.triangles_center}
        keep = np.array([tuple(np.round(x, 3)) not in sk for x in g.triangles_center]); n_weg = int((~keep).sum())
        g2 = trimesh.util.concatenate([g.submesh([np.flatnonzero(keep)], append=True), el2]); g2.export(os.path.join(a.aus, "gesamt.stl"))
        print(json.dumps({"element": a.element, "dreiecke_element": int(len(idx)), "aus_gesamt_entfernt": n_weg}))
    else:
        E = json.load(open(a.elemente))["elemente"]; m, zu = zuordnen(a.stl, E, a.massstab, a.tol_m); out = {}
        for e in E:
            idx = zu[e["name"]]; sh = sha_idx(m, idx)
            if len(idx): _schreibe(m, idx, os.path.join(a.aus, e["name"] + ".stl"))
            out[e["name"]] = {"flaechen": int(len(idx)), "sha": sh, "vorher_sha": e.get("sha"), "geaendert": sh != e.get("sha")}
        json.dump(out, open(os.path.join(a.aus, "zuordnung.json"), "w"), ensure_ascii=False, indent=1)
        print(json.dumps({k: v["geaendert"] for k, v in out.items()}))


if __name__ == "__main__":
    main()
