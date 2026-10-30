#!/usr/bin/env python3
"""auto_bauwerk.py — ORCHESTRATOR der vollautomatischen Bauwerk-Pipeline.
Verkettet die 8 Hebel zu EINEM Befehl; jeder Hebel ist ein austauschbares Modul
(Strategy-Pattern). Fehlt eine Quelle, fällt die Pipeline sauber auf die nächste
zurück (Geometrie: Hebel 1 → 3 → 5). Kein eigener Fotoaufwand.

  python3 tools/auto_bauwerk.py --name "Historisches Kaufhaus" \
      --lat 47.9956 --lon 7.8522 \
      --gml daten/freiburg/lod2/LoD2_32_412_5319_1_BW.gml \
      --work modelle/kaufhaus_auto --scale 1:160

Hebel-Schalter: --geo {google,lod2,openbuildings,auto}  --skip-fotos  --skip-relief
"""
import argparse, os, sys, subprocess, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(desc, cmd):
    print(f"\n=== {desc} ===\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd)
    ok = r.returncode == 0
    print(f"  {'OK' if ok else 'FEHLGESCHLAGEN (Fallback greift)'}")
    return ok


def geometrie(a, work):
    """HEBEL 1/3/5: grobes Massenmodell beschaffen (mit Fallback-Kette)."""
    obj = os.path.join(work, "roh_geometrie.obj")
    order = (["google", "lod2", "openbuildings"] if a.geo == "auto" else [a.geo])
    for src in order:
        if src == "google":                 # HEBEL 1 (bzw. 8 = anderer tile-endpoint)
            cmd = [PY, f"{ROOT}/tools/google3d_to_obj.py", "--lat", str(a.lat),
                   "--lon", str(a.lon), "--radius", str(a.radius), "--out", obj]
            if a.tiles_base: cmd += ["--base", a.tiles_base]   # HEBEL 8: Proxy/Alt-Endpoint
            if run("HEBEL 1 Google 3D Tiles", cmd) and os.path.exists(obj): return obj
        elif src == "lod2":                  # HEBEL 3
            if not a.gml: print("  LOD2 übersprungen (kein --gml)"); continue
            cmd = [PY, f"{ROOT}/tools/lod2_gebaeude.py", "--gml", a.gml,
                   "--stl", obj.replace(".obj", "_lod2.stl")]
            if a.name: cmd += ["--name", a.name]
            if run("HEBEL 3 LOD2-CityGML", cmd):
                return obj.replace(".obj", "_lod2.stl")
        elif src == "openbuildings":         # HEBEL 5
            cmd = [PY, f"{ROOT}/tools/openbuildings_fallback.py", "--lat", str(a.lat),
                   "--lon", str(a.lon), "--out", obj.replace(".obj", "_ob.obj")]
            if run("HEBEL 5 OpenBuildings/GlobalBuildingAtlas", cmd):
                return obj.replace(".obj", "_ob.obj")
    sys.exit("Keine Geometriequelle lieferte ein Mesh.")


def fotos(a, work):
    """HEBEL 2: fassaden-Views beschaffen — Google Street View ODER Mapillary (Google-frei)."""
    out = os.path.join(work, "fotos")
    if a.fotos == "mapillary":
        run("HEBEL 2 Mapillary Rip (Google-frei)", [PY, f"{ROOT}/tools/mapillary_rip.py",
            "--lat", str(a.lat), "--lon", str(a.lon), "--out", out, "--radius", "45"])
    else:
        run("HEBEL 2 Street View Rip", [PY, f"{ROOT}/tools/streetview_rip.py",
            "--lat", str(a.lat), "--lon", str(a.lon), "--out", out,
            "--zoom", str(a.zoom), "--views", "3"])
    return out


def relief(a, work, sv_dir):
    """HEBEL 6+7: je Fassaden-View Maske (fenster_ml) + Displacement (foto_displacement)."""
    patches = []
    for img in sorted(glob.glob(os.path.join(sv_dir, "sv_*.jpg"))):
        mask = img.replace(".jpg", "_window.png")
        run("HEBEL 6 Fassaden-Segmentierung", [PY, f"{ROOT}/tools/fenster_ml.py",
            img, "--out-mask", mask])
        dep = img.replace(".jpg", "_disp.png")
        mesh = img.replace(".jpg", "_relief.stl")
        cmd = [PY, f"{ROOT}/tools/foto_displacement.py", "--img", img,
               "--out-depth", dep, "--out-mesh", mesh, "--depth", a.depth,
               "--min-feature-mm", str(a.min_feature), "--scale", a.scale]
        if os.path.exists(mask): cmd += ["--mask", mask]
        if run("HEBEL 7 Tiefe→Relief + Druck-Guard", cmd) and os.path.exists(mesh):
            patches.append(mesh)
    return patches


def druck(a, work, geo):
    """HEBEL 4: wasserdicht/manifold + Bodenplatte + Druckmaßstab."""
    stl = os.path.join(work, f"{(a.name or 'bauwerk').split()[0].lower()}_druck.stl")
    run("HEBEL 4 Druckvorbereitung", [PY, f"{ROOT}/tools/drone_to_print.py", geo,
        "--mode", "detail", "--foot", str(a.foot), "--out", stl])
    return stl


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name"); p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--gml"); p.add_argument("--work", required=True)
    p.add_argument("--geo", choices=["google", "lod2", "openbuildings", "auto"], default="auto")
    p.add_argument("--radius", type=float, default=150)
    p.add_argument("--tiles-base", help="HEBEL 8: alternativer 3D-Tiles-Endpoint/Proxy")
    p.add_argument("--fotos", choices=["streetview", "mapillary"], default="mapillary",
                   help="Hebel-2-Quelle (mapillary = Google-frei, Default)")
    p.add_argument("--zoom", type=int, default=4)
    p.add_argument("--depth", choices=["ml", "classic"], default="classic")
    p.add_argument("--min-feature", type=float, default=0.8)
    p.add_argument("--foot", type=float, default=160)
    p.add_argument("--scale", default="1:160")
    p.add_argument("--skip-fotos", action="store_true")
    p.add_argument("--skip-relief", action="store_true")
    a = p.parse_args()
    os.makedirs(a.work, exist_ok=True)

    geo = geometrie(a, a.work)                          # Hebel 1/3/5 (+8)
    sv_dir = None if a.skip_fotos else fotos(a, a.work) # Hebel 2
    if not a.skip_relief and sv_dir:
        relief(a, a.work, sv_dir)                       # Hebel 6+7
    stl = druck(a, a.work, geo)                         # Hebel 4

    man = {"name": a.name, "coord": [a.lat, a.lon], "geometrie": geo,
           "streetview": sv_dir, "druck_stl": stl, "scale": a.scale}
    with open(os.path.join(a.work, "pipeline.json"), "w") as f:
        json.dump(man, f, indent=2)
    print(f"\nFERTIG. Druck-STL: {stl}\nManifest: {a.work}/pipeline.json")


if __name__ == "__main__":
    main()
