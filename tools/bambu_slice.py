#!/usr/bin/env python3
"""bambu_slice.py - STL -> .gcode.3mf fuer den Bambu P1S ueber die Kommandozeile von Bambu Studio (Register CB, Lehre 2026-11-03).
Loest die Vererbung ('inherits') der System-Profile auf (sonst nimmt die CLI 0,2 mm Standard), setzt Plattenart/Brim/Fuellung/Betttemperatur
und prueft das Ergebnis (Schichthoehe, Bett M190, Zeit, Gramm). Die Plattenart MUSS zu tools/p1s_print.py passen (bed_type textured_plate -> 55-60 C).
  tools/bambu_slice.py <aus.gcode.3mf> <teil.stl> [<teil2.stl> ...] [--schicht 0.2|0.12] [--fuellung 12%] [--brim 8] [--bett 60] [--platte "Textured PEI Plate"] [--wande 3] [--stuetzen]
Programm: /media/oem/scan/bambu_studio/squashfs-root (entpackt; --appimage-extract-and-run wuerde 567 MB nach /tmp legen!). Ausgabe: JSON-Zeile mit Zeit/Gramm/Schichten.
"""
import sys, os, json, glob, subprocess, re, argparse, tempfile, shutil
BS = "/media/oem/scan/bambu_studio/squashfs-root"; R = BS + "/resources/profiles/BBL"

def flat(idx, kind, name):
    d = idx[(kind, name)]; base = flat(idx, kind, d["inherits"]) if d.get("inherits") else {}
    o = dict(base); o.update(d); o.pop("inherits", None); return o

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("aus"); ap.add_argument("stl", nargs="+"); ap.add_argument("--schicht", default="0.12"); ap.add_argument("--fuellung", default="12%"); ap.add_argument("--brim", default="8")
    ap.add_argument("--bett", default="60"); ap.add_argument("--platte", default="Textured PEI Plate"); ap.add_argument("--wande", default="3")
    ap.add_argument("--stuetzen", action="store_true", help="Baumstuetzen (tree(auto)) an; Standard aus wie bisher"); a = ap.parse_args()
    idx = {}
    for kind in ("machine", "process", "filament"):
        for f in glob.glob(f"{R}/{kind}/*.json"):
            try: d = json.load(open(f))
            except Exception: continue
            idx[(kind, d.get("name"))] = d
    pname = {"0.08": "0.08mm Extra Fine @BBL X1C", "0.12": "0.12mm Fine @BBL X1C", "0.16": "0.16mm Optimal @BBL X1C", "0.2": "0.20mm Standard @BBL X1C"}[a.schicht]
    m = flat(idx, "machine", "Bambu Lab P1S 0.4 nozzle"); p = flat(idx, "process", pname); f = flat(idx, "filament", "Bambu PLA Basic @BBL P1S 0.4 nozzle")
    m["curr_bed_type"] = p["curr_bed_type"] = a.platte; p.update(brim_type="outer_only", brim_width=a.brim, sparse_infill_density=a.fuellung, wall_loops=a.wande)
    if a.stuetzen: p.update(enable_support="1", support_type="tree(auto)")
    f["textured_plate_temp"] = [a.bett]; f["textured_plate_temp_initial_layer"] = [a.bett]
    td = tempfile.mkdtemp(prefix="bs_", dir="/media/oem/scan/tmp")
    for n, d in (("m", m), ("p", p), ("f", f)): json.dump(d, open(f"{td}/{n}.json", "w"))
    out = os.path.abspath(os.path.dirname(a.aus)) or "."; name = os.path.basename(a.aus)
    cmd = ["xvfb-run", "-a", BS + "/AppRun", "--slice", "1", "--load-settings", f"{td}/m.json;{td}/p.json", "--load-filaments", f"{td}/f.json", "--arrange", "1", "--orient", "0",
           "--outputdir", td, "--export-3mf", name, *[os.path.abspath(s) for s in a.stl]]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800); g = f"{td}/plate_1.gcode"
    if not os.path.exists(g): sys.exit("Slice fehlgeschlagen: " + (r.stdout + r.stderr)[-500:])
    t = open(g).read(); gv = lambda k: (re.search(rf"^; {k}\s*[:=]\s*(.*)$", t, re.M) or [None, None])[1]
    res = dict(schichthoehe=gv("layer_height"), schichten=gv("total layer number"), zeit=(re.search(r"total estimated time: ([0-9hms ]+)", t) or [None, None])[1], gramm=gv("total filament weight \\[g\\]"), bett=re.search(r"^M190 S(\d+)", t, re.M).group(1), platte=gv("curr_bed_type"), hoehe_mm=gv("max_z_height"))
    shutil.copy(f"{td}/{name}", a.aus); shutil.rmtree(td, ignore_errors=True); print(json.dumps(res, ensure_ascii=False))

if __name__ == "__main__":
    main()
