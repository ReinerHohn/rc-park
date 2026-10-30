#!/usr/bin/env python3
"""foto_zu_config.py — HALBAUTOMATISCHER VERMESSER: aus Foto-Ordner + LOD2 eine
bauwerke/<name>.json erzeugen, die bauwerk_generator.py direkt liest. Das fehlende
Bindeglied, das die Einzel-Tools (lod2_gebaeude, fenster_ml, Farbmessung) zu EINEM
Ablauf verkettet — das Herzstück der Hero-Modell-Produktion.

Philosophie (ehrlich halbautomatisch): das Tool füllt, was ZUVERLÄSSIG messbar ist,
und FLAGGT, was der Mensch prüfen muss — kein Augenmaß als Gewissheit verkaufen.

  ZUVERLÄSSIG (auto):  Traufe/First (LOD2), Fassadenrhythmus (fenster_ml:
                       Reihen/Anzahl/Rundbögen), dominante Farben (Foto), Dachtyp.
  UNSICHER (geflaggt): exakte Frontbreite/Tiefe (LOD2-Kantenheuristik versagt bei
                       komplexen Grundrissen), Zierdetail (Erker/Statuen/Türmchen),
                       welche Aufnahme frontal ist, n_axes.

Ausgabe: bauwerke/<name>.json  +  <name>.REPORT.md (was auto, was TODO).

  python3 tools/foto_zu_config.py --name kaufhaus_auto \
      --gml daten/kaufhaus_freiburg/lod2/.../LoD2_32_414_5316_1_BW.gml \
      --lod2-name "Historisches Kaufhaus" \
      --front daten/kaufhaus_freiburg/fotos/kh_front1.jpg \
      --ml-python /tmp/ml/bin/python
"""
import argparse, os, sys, json, subprocess
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run_lod2(gml, lod2_name, center, out_stl, out_json):
    cmd = [PY, f"{ROOT}/tools/lod2_gebaeude.py", "--gml", gml,
           "--stl", out_stl, "--info", out_json]
    if lod2_name: cmd += ["--name", lod2_name]
    elif center:  cmd += ["--center", center, "--radius", "15"]
    print("  LOD2 ...", subprocess.run(cmd, capture_output=True, text=True).returncode == 0)
    return json.load(open(out_json)) if os.path.exists(out_json) else None


def run_fenster(front_foto, ml_python, out_json):
    cmd = [ml_python, f"{ROOT}/tools/fenster_ml.py", front_foto, "--out", out_json]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = os.path.exists(out_json)
    print(f"  fenster_ml ... {'ok' if ok else 'FEHLT (ML-venv? ' + r.stderr.strip()[-80:] + ')'}")
    return json.load(open(out_json)) if ok else None


def dominant_colors(foto, box_frac):
    """Fassade/Fenster/Dach-Farbe grob aus dem Foto. box_frac = Gebäude-Box."""
    img = cv2.imread(foto)
    if img is None: return {}
    H, W = img.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in (box_frac[0]*W, box_frac[1]*H, box_frac[2]*W, box_frac[3]*H)]
    crop = img[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0: return {}
    bh = crop.shape[0]
    # Dach = oberes Drittel, Fassade = Mitte; Median (robust gegen Ausreißer)
    def med(region):
        b, g, r = [int(np.median(region[..., i])) for i in range(3)]
        return [r, g, b]                             # BGR→RGB
    dach = med(crop[: bh//3])
    fass = med(crop[bh//3: 2*bh//3])
    # Fenster = dunkle Pixel im Fassadenbereich
    mid = crop[bh//3: 2*bh//3]
    gray = cv2.cvtColor(mid, cv2.COLOR_BGR2GRAY)
    dark = mid[gray < np.percentile(gray, 20)]
    fen = [int(np.median(dark[..., i])) for i in (2, 1, 0)] if len(dark) else [50, 52, 60]
    return {"fassade": fass, "dach": dach, "fenster": fen}


def facade_rows(fen, ridge_m, front_w_est):
    """fenster_ml-Reihen (z_frac/x_frac) → body_rows in Metern (GROB, geflaggt)."""
    rows = []
    arcade_n = 0
    for r in fen.get("rows", []):
        z_m = round(r["z_frac"] * ridge_m, 2)
        w_m = round(r["w_frac"] * front_w_est, 2)
        h_m = round(r["h_frac"] * ridge_m, 2)
        arched = any(r.get("arched", []))
        if r["z_frac"] < 0.3 and arched:             # untere Bogenreihe = Arkade
            arcade_n = max(arcade_n, r["n"])
        rows.append({"z": z_m, "n": r["n"], "w": max(w_m, 0.6),
                     "h": max(h_m, 0.9), "arched": arched})
    return rows, arcade_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Projekt-/Config-Name (kebab)")
    ap.add_argument("--gml", required=True)
    ap.add_argument("--lod2-name", default="", help="<gml:name> des Gebäudes")
    ap.add_argument("--center", default="", help="UTM E,N falls kein Name")
    ap.add_argument("--front", required=True, help="frontale Fassadenaufnahme")
    ap.add_argument("--ml-python", default=PY, help="python mit torch/transformers (z.B. /tmp/ml/bin/python)")
    ap.add_argument("--out", default="", help="Config-Pfad (default bauwerke/<name>.json)")
    a = ap.parse_args()

    out_dir = f"modelle/{a.name}"
    os.makedirs(f"{ROOT}/{out_dir}", exist_ok=True)
    cfg_path = a.out or f"{ROOT}/bauwerke/{a.name}.json"

    print("Vermesse ...")
    lod2 = run_lod2(a.gml, a.lod2_name, a.center,
                    f"{ROOT}/{out_dir}/{a.name}_lod2.stl", f"{ROOT}/{out_dir}/{a.name}_lod2.json")
    if not lod2 or not lod2.get("gebaeude"):
        sys.exit("LOD2 lieferte nichts — Name/Center prüfen.")
    g = lod2["gebaeude"][0]
    eave, ridge = round(g["eave_m"], 2), round(g["ridge_m"], 2)
    bbox = lod2["bbox_lbh_m"]
    front_w_est = round(max(bbox[0], bbox[1]), 1)     # Hüll-Maximum (sicherer als Kantenheuristik)
    depth_est = round(min(bbox[0], bbox[1]), 1)

    fen = run_fenster(a.front, a.ml_python, f"{ROOT}/{out_dir}/{a.name}_fenster.json")
    colors = dominant_colors(a.front, fen["building_box_frac"] if fen else [0.1, 0.1, 0.9, 0.9])
    rows, arcade_n = facade_rows(fen, ridge, front_w_est) if fen else ([], 0)
    dachtyp = g.get("dachtypen", ["?"])[0]
    satteldach = dachtyp in ("3100", "3200")          # 3100=Satteldach

    flags = []
    cfg = {
        "name": a.name,
        "out_dir": out_dir,
        "prefix": a.name[:4],
        "glb": f"{a.name}_measured.glb",
        "quelle": f"AUTO: Massing LOD2 {g['id']}, Fassade fenster_ml + Farben aus {os.path.basename(a.front)}",
        "measure": {"foto": a.front, "box": [0.05, 0.04, 0.95, 0.98], "n_axes": 4},
        "massing": {
            "W": front_w_est,
            "eave": eave,
            "lod2_ridge": ridge,
            "lod2_depth": depth_est,
            "wall_thick": 0.5,
            "_FLAG_W_depth": "Hüll-Bbox, NICHT echte Front/Tiefe — bei komplexem Grundriss am Foto gegenprüfen"
        },
        "facade": {
            "floors": max(2, round(eave / 3.2)),
            "body_rows": rows,
            "arcade": {"n": arcade_n} if arcade_n else {},
            "fenster_auto": f"{out_dir}/{a.name}_fenster.json"
        },
        "elements": {
            "putzfassade": {"string_course": True},
            "fensterraster": {},
            "erdgeschoss": {"door": True},
            ("satteldach" if satteldach else "dach"): {},
            "dachziegel": {"tile_w": 0.18, "course_h": 0.15, "relief": 0.045, "slopes": "both"},
            "gauben": {"n": 3},
            "dachrinne": {}
        },
        "colors": {k: v for k, v in colors.items()},
        "use_measured_colors": True
    }
    json.dump(cfg, open(cfg_path, "w"), indent=2, ensure_ascii=False)

    # --- Ehrlicher Report ---
    if front_w_est and depth_est and abs(front_w_est - depth_est) < 2:
        flags.append("Front≈Tiefe (fast quadratische Hülle) — Frontseite am Foto bestimmen")
    flags.append("W/Tiefe = Hüll-Bbox (LOD2-Kantenheuristik unzuverlässig bei mehrteiligem Grundriss)")
    flags.append("z/w/h der Fensterreihen aus Foto-Fraktionen × Höhe GESCHÄTZT — grob")
    if not fen: flags.append("fenster_ml lief NICHT → facade.body_rows leer, manuell/anderer foto")
    flags.append("Zierdetail (Erker/Statuen/Türmchen/Maßwerk) NICHT auto — als elements ergänzen")
    flags.append("welche Aufnahme frontal ist + n_axes prüfen")

    rep = [f"# {a.name} — Vermesser-Report", "",
           f"**Config:** `{os.path.relpath(cfg_path, ROOT)}`", "",
           "## AUTO (zuverlässig)",
           f"- Massing LOD2 `{g['id']}`: Traufe **{eave} m**, First **{ridge} m**, Dachtyp {dachtyp}"
           f" ({'Satteldach' if satteldach else 'anderer'})",
           f"- Hülle (bbox) **{bbox[0]:.1f} × {bbox[1]:.1f} × {bbox[2]:.1f} m**",
           f"- Fassade: **{fen['n_windows'] if fen else 0} Fenster** in **{len(rows)} Reihen**"
           f"{', Arkade mit ' + str(arcade_n) + ' Bögen' if arcade_n else ''}",
           f"- Farben aus Foto: fassade {colors.get('fassade')}, dach {colors.get('dach')}, fenster {colors.get('fenster')}",
           "", "## TODO MENSCH (geflaggt)"] + [f"- [ ] {f}" for f in flags] + [
           "", "## Nächster Schritt",
           f"`python3 tools/bauwerk_generator.py --config {os.path.relpath(cfg_path, ROOT)}` "
           "→ Render neben Foto prüfen → geflaggte Werte nachziehen → Juror/Validator."]
    rep_path = cfg_path.replace(".json", ".REPORT.md")
    open(rep_path, "w").write("\n".join(rep))

    print(f"\nConfig  → {os.path.relpath(cfg_path, ROOT)}")
    print(f"Report  → {os.path.relpath(rep_path, ROOT)}  ({len(flags)} Flags für den Menschen)")
    print(f"Auto gefüllt: Traufe/First, {len(rows)} Fensterreihen"
          f"{', Arkade '+str(arcade_n) if arcade_n else ''}, {len(colors)} Farben.")


if __name__ == "__main__":
    main()
