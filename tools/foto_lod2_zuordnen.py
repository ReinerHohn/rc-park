#!/usr/bin/env python3
"""foto_lod2_zuordnen.py - GENERISCH: Was ist das Ding im Foto? LoD2-Gebaeude der Umgebung in die kalibrierte Kamera eines Fotos
projizieren und fuer eine Bildstelle (u, v) sagen, welche Gebaeude dort liegen (mit Entfernung, Hoehe, Kennung).

Wozu: unbekannte Bauteile/Nachbarn im Foto (z. B. 'runder Kuppelturm links vom Martinstor in Foto 061') nicht raten, sondern aus
den amtlichen Gebaeudemodellen ablesen. Kamera: messprotokoll/K-<foto>.json ["kamera"] (foto_kalibrieren.py) oder ["kamera_netz_nord"].
Modellrahmen: anker3d.json (mitte_utm, xhat_utm, yhat_utm, gelaende) - derselbe wie Generator und Wolke.

  foto_lod2_zuordnen.py modelle/<objekt>/objekt.json 061 --gml-dir /pfad/zu/LoD2_tiles --radius 300 --u 2300 --v 480 [--toleranz 25]
Ausgabe: Tabelle der Gebaeude, deren Projektion die Bildstelle (+- Toleranz px) ueberdeckt, nach Entfernung sortiert; Kontrollbild
audit/lod2_im_foto_<foto>.jpg (Umrisse aller projizierten Gebaeude, Treffer hervorgehoben); JSON audit/lod2_im_foto_<foto>.json.
"""
import sys, os, json, glob, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--gml-dir", required=True)
    ap.add_argument("--radius", type=float, default=300.0); ap.add_argument("--u", type=float, required=True); ap.add_argument("--v", type=float, required=True)
    ap.add_argument("--toleranz", type=float, default=25.0); ap.add_argument("--kamera", default="kamera", help="Schluessel im K-Protokoll (kamera | kamera_netz_nord)")
    a = ap.parse_args(); import cv2; import lod2_gebaeude as LG
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od))
    A = json.load(open(os.path.join(od, "anker3d.json"))); mitte = np.array(A["mitte_utm"]); xh = np.array(A["xhat_utm"]); yh = np.array(A["yhat_utm"]); gel = float(A["gelaende"])
    K = json.load(open(os.path.join(od, "messprotokoll", f"K-{a.foto}.json"))); cam = K.get(a.kamera) or K.get("kamera") or K.get("kamera_netz_nord")
    R = np.array(cam["R"]) if "R" in cam else cv2.Rodrigues(np.array(cam["rvec"], float))[0]; t = np.array(cam["t"], float)
    f = float(cam.get("f") or cam.get("f_px") or cam.get("f_px_original")); cx, cy = float(cam["cx"]), float(cam["cy"])
    def proj(X):
        Xc = X @ R.T + t; return np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], Xc[:, 2]
    def modell(P):   # UTM (E, N, H) -> Modell (x Sued, y Ost, z ueber Gelaende)
        d = P[:, :2] - mitte; return np.c_[d @ xh, d @ yh, P[:, 2] - gel]
    geb = []
    for g in sorted(glob.glob(os.path.join(a.gml_dir, "**", "*.gml"), recursive=True)):
        for meta, polys in LG.extract(g, center=tuple(mitte), radius=a.radius):
            V = modell(np.vstack([P for _, P in polys])); uv, z = proj(V)
            if z.min() <= 1: continue
            geb.append(dict(id=meta["id"], name=meta.get("name") or "", hoehe=round(float(V[:, 2].max()), 1), first=meta.get("ridge_m"), dach=meta.get("rooftypes", [])[:3],
                            mitte_modell=[round(float(x), 1) for x in V.mean(0)[:2]], entfernung=round(float(np.median(z)), 1), u0=float(uv[:, 0].min()), u1=float(uv[:, 0].max()), v0=float(uv[:, 1].min()), v1=float(uv[:, 1].max()), uv=uv, polys=[proj(modell(P))[0] for _, P in polys]))
    print(f"{len(geb)} LoD2-Gebaeude im Umkreis {a.radius:.0f} m projiziert (Kamera {a.kamera}: f {f:.0f} px)")
    tr = [g for g in geb if g["u0"] - a.toleranz <= a.u <= g["u1"] + a.toleranz and g["v0"] - a.toleranz <= a.v <= g["v1"] + a.toleranz]
    tr.sort(key=lambda g: g["entfernung"])
    print(f"Bildstelle u {a.u:.0f} v {a.v:.0f} (+-{a.toleranz:.0f} px): {len(tr)} Treffer, nach Entfernung:")
    for g in tr: print(f"  {g['id']:28s} {g['name'][:24]:24s} Entf {g['entfernung']:7.1f} m  Hoehe {g['hoehe']:5.1f} m  Modell-Mitte x {g['mitte_modell'][0]:7.1f} y {g['mitte_modell'][1]:7.1f}  Dach {'/'.join(g['dach'])}  Bild u {g['u0']:.0f}..{g['u1']:.0f} v {g['v0']:.0f}..{g['v1']:.0f}")
    # Keine Ueberdeckung? Dann die Gebaeude in derselben Bildspalte, deren Oberkante der Bildstelle am naechsten liegt (LoD2 schneidet Kuppeln/Aufsaetze ab)
    sp = sorted([g for g in geb if g["u0"] - a.toleranz <= a.u <= g["u1"] + a.toleranz], key=lambda g: abs(g["v0"] - a.v))[:8]
    print(f"Gebaeude in der Bildspalte u {a.u:.0f}, nach Abstand der Oberkante zur Bildstelle:")
    for g in sp: print(f"  {g['id']:28s} {g['name'][:24]:24s} Oberkante v {g['v0']:.0f} ({g['v0'] - a.v:+.0f} px)  Hoehe {g['hoehe']:5.1f} m  Modell-Mitte x {g['mitte_modell'][0]:7.1f} y {g['mitte_modell'][1]:7.1f}  Dach {'/'.join(g['dach'])}")
    fn = glob.glob(os.path.join(repo, obj["fotos_dir"], a.foto + "_*"))[0]; im = cv2.imread(fn)
    for g in geb:
        col = (0, 0, 255) if g in tr else (0, 200, 0)
        for P2 in g["polys"]: cv2.polylines(im, [P2.astype(np.int32).reshape(-1, 1, 2)], True, col, 2 if g in tr else 1)
    for g in tr: cv2.putText(im, f"{g['id'][-6:]} {g['hoehe']:.0f}m", (int(g["u0"]), int(g["v0"]) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.circle(im, (int(a.u), int(a.v)), int(a.toleranz), (255, 0, 255), 2)
    u0, v0 = max(int(a.u) - 600, 0), max(int(a.v) - 500, 0); crop = im[v0:v0 + 1000, u0:u0 + 1200]
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); out = os.path.join(od, "audit", f"lod2_im_foto_{a.foto}.jpg"); cv2.imwrite(out, crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
    json.dump(dict(foto=a.foto, kamera=a.kamera, bildstelle=[a.u, a.v], toleranz_px=a.toleranz, treffer=[{k: v for k, v in g.items() if k not in ("uv", "polys")} for g in tr]), open(out.replace(".jpg", ".json"), "w"), indent=1, ensure_ascii=False)
    print("Kontrollbild:", out)

if __name__ == "__main__":
    main()
