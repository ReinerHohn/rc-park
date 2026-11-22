#!/usr/bin/env python3
"""vorbau_fototor.py - FOTO-TOR fuer gebaute Vorbauten (Erker, Galerie, Vordach) je Gruppe aus audit/vorbauten_auto.json (22.11.2026, Kettenstufe 'bauplan').

Anlass (Kettenlauf schwabentor-1122n): der Bilderker der Stadtseite fehlte, ohne dass ein Tor es meldete; foto_diff bewertet nur das ganze Modell.
Hier je Vorbau-Gruppe:
  1. EXPORT (Generator-Umgebung, manifold3d): bauteile.vorbauten_aus_json nur mit dieser Gruppe auf leerem Koerper -> <teile>/vorbau_<fid>_<k>.stl
     (Massstab wie das Modell-STL: m x 1000/SKALA, Rahmen nicht zentriert).
  2. FOTO-F1 (teil_fotoform, GPU): Praezision/Recall/F1 der Teilkanten gegen die Fotokanten in den Fotos, die die Fassade am besten sehen (fassaden.json 'fotos', Zellen).
     --vorher_stl: zusaetzlich PHANTOM-Messung (Bereich des neuen Teils am Modell OHNE Vorbau) = Foto-F1 vorher/nachher.
  3. TOR je Gruppe: BELEGT, wenn >= --min_fotos Fotos das Teil beurteilen und die Praezision (Anteil Modellkanten mit Fotokante <= 0,14 m) >= --praez_min
     (ANNAHME 0,5: mehr als die Haelfte der gebauten Kanten liegt auf Fotokanten = nicht erfunden). Sonst NICHT BELEGT (rc 2), ohne Beurteilung rc 3.
Aufruf: vorbau_fototor.py <objekt> <fassaden.json> [--fotos 8] [--stl S] [--vorher_stl S] [--aus audit/vorbau_fototor.json] [--bilder_dir D]
Export allein (rcpark-Umgebung): vorbau_fototor.py --export <vorbauten_auto.json> <teile-ordner> [--skala 87]
"""
import sys, os, json, argparse, subprocess, tempfile

HIER = os.path.dirname(os.path.abspath(__file__)); R0 = os.path.dirname(HIER); sys.path.insert(0, HIER)
GEN_PY = os.path.expanduser("~/.venvs/rcpark/bin/python")


def exportieren(vj, td, skala=87.0):
    """Je Gruppe ein STL (mm, Modellrahmen). Liefert Liste (name, fid, k)."""
    import numpy as np, trimesh
    from manifold3d import Manifold as M
    from bauteile import vorbauten_aus_json
    J = json.load(open(vj)); out = []; os.makedirs(td, exist_ok=True); K = 1000.0 / skala
    for F in J.get("fassaden", []):
        for k, g in enumerate(F["gruppen"]):
            tj = os.path.join(td, f"_vb_{F['id']}_{k}.json")
            json.dump(dict(J, fassaden=[dict(F, gruppen=[g])]), open(tj, "w"))
            # vordach_profil.json liegt neben vorbauten_auto.json und wird ueber (id, gruppe) zugeordnet -> Gruppe k muss Gruppe k bleiben
            if k:
                json.dump(dict(J, fassaden=[dict(F, gruppen=[dict(g0, kanten_mass=None, galerie=None, w=[[0.0]]) for g0 in F["gruppen"][:k]] + [g])]), open(tj, "w"))
            vp = os.path.join(os.path.dirname(os.path.abspath(vj)), "vordach_profil.json")
            if os.path.exists(vp): __import__("shutil").copy(vp, os.path.join(td, "vordach_profil.json"))
            kp, _ = vorbauten_aus_json(M(), tj)
            os.remove(tj)
            if kp.is_empty(): continue
            m = kp.scale((K, K, K)).to_mesh(); nm = f"vorbau_{F['id']}_{k}"
            trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts)).export(os.path.join(td, nm + ".stl")); out.append((nm, F["id"], k))
    vp_ = os.path.join(td, "vordach_profil.json")
    if os.path.exists(vp_): os.remove(vp_)
    return out


def urteil(je, min_fotos=3, praez_min=0.5):
    """je = teil_fotoform erg['teile'][name]. (BELEGT|NICHT BELEGT|KEIN URTEIL, gesamt)."""
    g = (je or {}).get("_gesamt")
    if not g or g.get("fotos", 0) < min_fotos: return "KEIN URTEIL", g
    return ("BELEGT" if g["praez"] >= praez_min else "NICHT BELEGT"), g


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("fassaden", nargs="?")
    ap.add_argument("--export", nargs=2, metavar=("VORBAUTEN_JSON", "TEILE")); ap.add_argument("--skala", type=float, default=float(os.environ.get("SCALE", "87")))
    ap.add_argument("--fotos", type=int, default=8); ap.add_argument("--stl"); ap.add_argument("--vorher_stl"); ap.add_argument("--aus"); ap.add_argument("--bilder_dir")
    ap.add_argument("--min_fotos", type=int, default=3); ap.add_argument("--praez_min", type=float, default=0.5); a = ap.parse_args(argv)
    if a.export:
        for nm, fid, k in exportieren(a.export[0], a.export[1], a.skala): print("EXPORT", nm)
        return 0
    od = os.path.join(R0, "modelle", a.objekt); vj = os.path.join(od, "audit", "vorbauten_auto.json")
    if not os.path.exists(vj) or not json.load(open(vj)).get("fassaden"): print("keine Vorbauten gebaut - nichts zu pruefen"); return 3
    td = tempfile.mkdtemp(prefix="vbft_", dir=os.environ.get("TMPDIR") or None)
    r = subprocess.run([GEN_PY, "-W", "ignore", "-I", os.path.abspath(__file__), "--export", vj, td, "--skala", str(a.skala)], capture_output=True, text=True)
    teile = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("EXPORT ")]
    if not teile: print("Export ohne Teile:", (r.stderr or r.stdout)[-300:]); return 3
    FA = {F.get("id", f"f{i:02d}"): F for i, F in enumerate(json.load(open(a.fassaden))["fassaden"])}
    import teil_fotoform as TF
    wo_ = os.path.join(od, "sfm", f"punkte_modell_{a.objekt}.npy")      # eigene dichte Wolke als Verdecker (ohne kreis.wolke nimmt teil_fotoform sonst eine fremde Standardwolke)
    if os.path.exists(wo_) and not (json.load(open(os.path.join(od, "objekt.json"))).get("kreis") or {}).get("wolke"): TF_WOLKE = ["--wolke", wo_]
    else: TF_WOLKE = []
    bericht = dict(quelle="tools/vorbau_fototor.py (teil_fotoform je Vorbau-Gruppe)", praez_min=a.praez_min, min_fotos=a.min_fotos, gruppen={}); rc = 0
    for nm in teile:
        fid = nm.split("_")[1]; F = FA.get(fid) or {}
        fotos = [f_ for f_, _ in sorted((F.get("fotos") or {}).items(), key=lambda kv: -kv[1].get("zellen", 0))][:a.fotos]
        if not fotos: bericht["gruppen"][nm] = dict(urteil="KEIN URTEIL", grund="keine Fotos der Fassade"); continue
        arg = [a.objekt, "--teile_dir", td, "--nur", nm, "--fotos", ",".join(fotos)] + TF_WOLKE + (["--stl", a.stl] if a.stl else []) + (["--bilder", "--bilder_dir", a.bilder_dir] if a.bilder_dir else [])
        e_n = TF.main(arg + ["--etikett", "nachher"]); u_, g_ = urteil(e_n["teile"].get(nm), a.min_fotos, a.praez_min)
        b_ = dict(urteil=u_, nachher=g_, fotos=fotos, je_foto={k: dict(praez=v["praez"], recall=v["recall"]) for k, v in (e_n["teile"].get(nm) or {}).items() if k != "_gesamt"})
        if a.vorher_stl:      # Phantom: Teilbereich des neuen Teils, Modellkanten aus dem Stand OHNE Vorbau (teil_fotoform --bereich_von)
            tv = tempfile.mkdtemp(prefix="vbft_v_", dir=os.environ.get("TMPDIR") or None)
            e_v = TF.main([a.objekt, "--teile_dir", tv, "--nur", nm, "--bereich_von", td, "--stl", a.vorher_stl, "--fotos", ",".join(fotos)] + TF_WOLKE + (["--bilder", "--bilder_dir", a.bilder_dir, "--etikett", "vorher"] if a.bilder_dir else []))
            b_["vorher"] = (e_v["teile"].get(nm) or {}).get("_gesamt")
        bericht["gruppen"][nm] = b_
        f1n = (g_ or {}).get("f1"); f1v = (b_.get("vorher") or {}).get("f1")
        print(f"VORBAU-FOTOTOR {nm}: {u_}" + (f"  Praez {g_['praez']:.3f} Recall {g_['recall']:.3f} F1 {g_['f1']:.3f} ({g_['fotos']} Fotos)" if g_ else "") + (f"  | vorher F1 {f1v:.3f} -> nachher {f1n:.3f}" if f1v is not None and f1n is not None else ""))
        if u_ == "NICHT BELEGT": rc = 2
        elif u_ == "KEIN URTEIL" and rc == 0: rc = 3
    aus = a.aus or os.path.join(od, "audit", "vorbau_fototor.json"); json.dump(bericht, open(aus, "w"), indent=1, ensure_ascii=False); print("->", aus)
    return rc


if __name__ == "__main__": sys.exit(main())
