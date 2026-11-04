#!/usr/bin/env python3
"""fotos_einsortieren.py - PIPELINE-SCHRITT (2026-11-04): Bilder aus einem Eingangsordner (mapillary_rip.py: manifest 'views'; bilder_holen.py: manifest 'images')
ins Objekt uebernehmen - fortlaufende Nummer, Kopie in fotos_dir als NNN_<quelle>_<id>.jpg, Eintrag im Foto-Manifest (Lizenz/URL fuer lizenz_register.py),
objekt.json 'fotos' (Quelle, Lizenzklasse, Brennweite) und SfM-Liste (sfm.<netz>). Bereits uebernommene IDs werden uebersprungen.

Brennweite: 360-Grad-Ausschnitte (mapillary_rip, camera_type spherical) sind synthetische Lochkameras mit bekanntem Bildwinkel -> f = (W/2)/tan(fov/2)
als objekt.json fotos.<nr>.brennweite_px (dritte Prior-Quelle in sfm_netz.py), Quelle 'Bildwinkel des Ausschnitts'. Perspektivbilder ohne EXIF: kein Prior.
  python3 -I tools/fotos_einsortieren.py modelle/<objekt>/objekt.json <eingang> [--netz alle] [--fov 70] [--lizenz TEXT] [--max N] [--trocken]
"""
import sys, os, json, glob, shutil, math, argparse
from PIL import Image


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("eingang"); ap.add_argument("--netz", default=None, help="SfM-Liste (Standard: sfm.hauptseite)")
    ap.add_argument("--fov", type=float, default=70.0, help="Bildwinkel der 360-Grad-Ausschnitte (mapillary_rip --fov)"); ap.add_argument("--lizenz", default="Mapillary (CC BY-NC-SA laut Projektregel)", help="Lizenz, falls das Manifest keine nennt (Mapillary: CC BY-NC-SA laut LIZENZ_WERKZEUGE.md -> Klasse nc)")
    ap.add_argument("--max", type=int, default=0); ap.add_argument("--trocken", action="store_true"); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(objp)))
    fd = os.path.realpath(os.path.join(root, obj["fotos_dir"])); mp = os.path.join(fd, "manifest.json"); FM = json.load(open(mp))
    M = json.load(open(os.path.join(a.eingang, "manifest.json"))); E = M.get("views") or M.get("images") or []
    netz = a.netz or obj.get("sfm", {}).get("hauptseite") or "alle"
    belegt = {int(os.path.basename(p)[:3]) for p in glob.glob(os.path.join(fd, "[0-9][0-9][0-9]_*"))}; nr = max(belegt | {0}) + 1
    schon = {str(m.get("quelle_id")) for m in FM["images"] if m.get("quelle_id")}
    neu = []
    for e in E:
        qid = str(e.get("mapillary_id") or e.get("pageid") or e.get("title") or e["file"])
        src = os.path.join(a.eingang, e["file"])
        if qid in schon or not os.path.exists(src): continue
        if a.max and len(neu) >= a.max: break
        while nr in belegt: nr += 1
        n3 = f"{nr:03d}"; quelle = "mapillary" if e.get("mapillary_id") else "eingang"; ziel = f"{n3}_{quelle}_{qid}.jpg"[:120]
        W, H = Image.open(src).size; lic = e.get("license") or a.lizenz
        url = e.get("url") or (f"https://www.mapillary.com/app/?pKey={e['mapillary_id']}" if e.get("mapillary_id") else "")
        f_px = (W / 2) / math.tan(math.radians(a.fov) / 2) if e.get("camera_type") == "spherical" or e.get("tag") == "360" else None
        neu.append(dict(nr=n3, src=src, ziel=ziel, W=W, H=H, lic=lic, url=url, qid=qid, f=f_px, e=e)); belegt.add(nr)
    print(f"{len(neu)} neue Bilder (von {len(E)}), Nummern {neu[0]['nr'] if neu else '-'}..{neu[-1]['nr'] if neu else '-'}, Netz '{netz}', davon mit Bildwinkel-Brennweite {sum(1 for x in neu if x['f'])}")
    if a.trocken or not neu: return
    import lizenz_register as LR
    for x in neu:
        shutil.copy2(x["src"], os.path.join(fd, x["ziel"]))
        FM["images"].append(dict(file=x["ziel"], title=x["ziel"], url=x["url"], license=x["lic"], author=x["e"].get("author", "Mapillary-Beitragende" if "mapillary" in x["ziel"] else ""), quelle_id=x["qid"],
                                 lat=x["e"].get("lat"), lon=x["e"].get("lon"), aufnahme=x["e"].get("captured_at")))
        f = dict(lizenz_klasse=LR.klasse(x["lic"], x["url"]), seite="unbekannt", vollbild=[x["W"], x["H"]], sfm_netz=netz,
                 quelle=f"fotos_einsortieren.py: {x['ziel']} ({x['lic']}, {x['url']})")
        if x["f"]: f.update(brennweite_px=round(x["f"], 1), brennweite_quelle=f"Bildwinkel des 360-Grad-Ausschnitts {a.fov} Grad (mapillary_rip --fov)")
        obj.setdefault("fotos", {})[x["nr"]] = f; obj.setdefault("sfm", {}).setdefault(netz, [])
        if x["nr"] not in obj["sfm"][netz]: obj["sfm"][netz].append(x["nr"])
    json.dump(FM, open(mp, "w"), indent=1, ensure_ascii=False); json.dump(obj, open(objp, "w"), indent=1, ensure_ascii=False)
    print("uebernommen:", len(neu), "->", fd, "| objekt.json fotos + sfm." + netz)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); main()
