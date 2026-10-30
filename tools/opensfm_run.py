#!/usr/bin/env python3
"""opensfm_run.py — HEBEL 1-ERSATZ (Google-frei): aus geotaggten Fotos (z.B. aus
mapillary_rip.py --raw) via OpenSfM eine dichte, GPS-georeferenzierte 3D-Punktwolke
rekonstruieren. OpenSfM ist Mapillarys eigene SfM-Engine → passt perfekt zu den
Mapillary-Bildern (perspektiv/fisheye/sphärisch, EXIF-GPS-Georeferenz).

Dieses Tool macht die INTEGRATION (Dataset bauen + Lauf anstoßen + Ergebnis zeigen);
OpenSfM selbst muss installiert sein (am einfachsten als Docker-Image).

Ablauf:
  1) Dataset-Ordner anlegen: <ds>/images/ + exif_overrides.json (lat/lon/alt/compass
     je Bild aus manifest.json) + camera_models_overrides.json (sphärisch markieren)
     + config.yaml (Dense-Tiefe an).
  2) OpenSfM-Pipeline laufen (run_all: features→match→reconstruct→undistort→depthmaps).
  3) Ergebnis: dichte Punktwolke undistorted/depthmaps/merged.ply.
     → danach vernetzen/druckbar: tools/drone_to_print.py <ply> --mode detail,
       Maßstab am LOD2 (Hebel 3) ankern statt an der verrauschten GPS-Höhe.

Installation (einmalig):
  Docker:  docker pull mapillary/opensfm       (empfohlen, kein lokaler Build)
  lokal:   github.com/mapillary/OpenSfM (cmake + Ceres + OpenCV), dann --opensfm-path

  python3 tools/opensfm_run.py --images daten/martinstor/mapillary_raw \
      --ds modelle/martinstor_auto/sfm --run docker
"""
import argparse, os, sys, json, shutil, subprocess


def build_dataset(images_dir, ds):
    """Mapillary-Rohordner → OpenSfM-Dataset-Struktur. Gibt Bildanzahl zurück."""
    man_path = os.path.join(images_dir, "manifest.json")
    if not os.path.exists(man_path):
        sys.exit(f"Kein manifest.json in {images_dir} — erst: mapillary_rip.py --raw ...")
    man = json.load(open(man_path))
    views = man["views"]
    img_out = os.path.join(ds, "images")
    os.makedirs(img_out, exist_ok=True)

    exif_over, cam_over = {}, {}
    n = 0
    for v in views:
        src = os.path.join(images_dir, v["file"])
        if not os.path.exists(src):
            continue
        shutil.copy2(src, os.path.join(img_out, v["file"]))
        ov = {}
        if v.get("lat") is not None and v.get("lon") is not None:
            gps = {"latitude": v["lat"], "longitude": v["lon"], "dop": 5.0}
            if v.get("alt") is not None:
                gps["altitude"] = v["alt"]
            ov["gps"] = gps
        if v.get("cam_angle") is not None:
            ov["compass"] = {"angle": v["cam_angle"], "accuracy": 15.0}
        if ov:
            exif_over[v["file"]] = ov
        # sphärische Bilder brauchen das richtige Projektionsmodell
        if v.get("camera_type") in ("spherical", "equirectangular"):
            cam_over[v["file"]] = {"projection_type": "spherical"}
        n += 1

    json.dump(exif_over, open(os.path.join(ds, "exif_overrides.json"), "w"), indent=2)
    if cam_over:
        json.dump(cam_over, open(os.path.join(ds, "camera_models_overrides.json"), "w"), indent=2)
    # Dense-Rekonstruktion einschalten, GPS als weichen Anker nutzen
    with open(os.path.join(ds, "config.yaml"), "w") as f:
        f.write("processes: 4\n"
                "feature_type: SIFT\n"
                "align_method: auto\n"
                "use_altitude_tag: yes\n"
                "depthmap_method: PATCH_MATCH\n"
                "depthmap_resolution: 640\n"
                "depthmap_min_consistent_views: 2\n")
    print(f"  Dataset: {n} Bilder, {len(exif_over)} mit GPS, {len(cam_over)} sphärisch → {ds}")
    return n


def run_opensfm(ds, mode, opensfm_path):
    ds_abs = os.path.abspath(ds)
    if mode == "none":
        print("  --run none: Dataset gebaut, Lauf übersprungen.")
        return None
    if mode == "docker":
        cmd = ["docker", "run", "--rm", "-v", f"{ds_abs}:/data",
               "mapillary/opensfm", "bin/opensfm_run_all", "/data"]
    else:  # local
        if not opensfm_path:
            sys.exit("--run local braucht --opensfm-path (Pfad zum OpenSfM-Checkout).")
        cmd = [os.path.join(opensfm_path, "bin", "opensfm_run_all"), ds_abs]
    print(f"$ {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd)
    except FileNotFoundError:
        sys.exit("OpenSfM/Docker nicht gefunden. 'docker pull mapillary/opensfm' oder "
                 "lokal installieren (--opensfm-path).")
    if r.returncode != 0:
        sys.exit("OpenSfM-Lauf fehlgeschlagen (Log oben).")
    dense = os.path.join(ds, "undistorted", "depthmaps", "merged.ply")
    sparse = os.path.join(ds, "reconstruction.ply")
    out = dense if os.path.exists(dense) else sparse
    return out if os.path.exists(out) else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--images", required=True, help="Ordner mit Rohbildern + manifest.json")
    p.add_argument("--ds", required=True, help="OpenSfM-Dataset-Ordner (wird angelegt)")
    p.add_argument("--run", choices=["docker", "local", "none"], default="docker")
    p.add_argument("--opensfm-path", help="bei --run local: OpenSfM-Checkout")
    a = p.parse_args()

    n = build_dataset(a.images, a.ds)
    if n < 5:
        print(f"  WARN nur {n} Bilder — SfM braucht viele überlappende Ansichten "
              "(Radius in mapillary_rip erhöhen / --raw).")
    ply = run_opensfm(a.ds, a.run, a.opensfm_path)
    if ply:
        print(f"\nPunktwolke: {ply}")
        print(f"Nächster Schritt: python3 tools/drone_to_print.py {ply} "
              "--mode detail --foot 160 --out modelle/.../sfm_druck.stl")
        print("Maßstab/Lage am LOD2 (Hebel 3) ankern — GPS-Höhe ist verrauscht.")


if __name__ == "__main__":
    main()
