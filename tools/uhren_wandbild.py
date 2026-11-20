#!/usr/bin/env python3
"""uhren_wandbild.py - Turmuhren aus dem Wandbild finden und vermessen (21.11.2026, Kettenstufe 'bauplan').

Anlass (Kettenluecke 9, modelle/KETTE_LUECKEN_2026-11-20.md): die Uhr gab es nur im Hand-Generator (schwab_v3_gen Z.141-146, martinstor_v4), der Erkenner kannte keine Klasse dafuer.
Ablauf je Fassade:
  1. ZONE = Erkennerkasten der Klasse 'uhr' (tools/fassade_parsing.py, OWLv2 "a clock"/"a clock face") mit >= --stimmen Stimmen und >= 40 % der Fotos, die die Stelle sehen.
     Der Kasten ist nur Suchfenster (KERNMETHODE: Erkennen = Zone, Gestalt aus dem Wandbild).
  2. MASS = Kreis im feinen Wandbild (fassade_fein, 1 cm): Kantenbild, Kreis-Hough in der Zone (Radius 0,35-0,65 x Kastengroesse); Aussenkreis = Kreis mit der
     staerksten Kantenstuetze; Innenkreis (Ziffernring innen) = staerkster konzentrischer Kreis mit 0,45-0,85 x Aussenradius (Mitte < 6 % R daneben), sonst keiner.
     Stuetze = Anteil der Kreispunkte mit Kante in 2 cm; Tor >= --min_stuetze, sonst verworfen (Name der Ursache im JSON).
Aufruf:  uhren_wandbild.py <objekt.json> <fassade_fein-ordner> --elemente <fassade/elemente.json> [--aus audit/uhren_auto.json]
Ausgabe: {fid: {o, d, n, uhren: [{u, z, d_aussen, d_innen, stuetze_aussen, stuetze_innen, kasten, quelle}], verworfen: [...]}} + Bild <aus>.jpg
rc 0 = mindestens eine Uhr, rc 3 = keine.
"""
import sys, os, json, argparse, numpy as np, cv2


def stuetze(kanten, cx, cy, r, tol=2):
    t = np.linspace(0, 2 * np.pi, max(60, int(2 * np.pi * r / 2)), endpoint=False); x = np.round(cx + r * np.cos(t)).astype(int); y = np.round(cy + r * np.sin(t)).astype(int)
    H, W = kanten.shape; ok = (x >= tol) & (x < W - tol) & (y >= tol) & (y < H - tol)
    if ok.mean() < 0.8: return 0.0
    k = cv2.dilate(kanten, np.ones((2 * tol + 1, 2 * tol + 1), np.uint8)); return float((k[y[ok], x[ok]] > 0).mean())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fein"); ap.add_argument("--elemente", required=True); ap.add_argument("--aus")
    ap.add_argument("--stimmen", type=int, default=3); ap.add_argument("--min_stuetze", type=float, default=0.85, help="21.11.: echte Uhr 98-100 %%, Scheinkreis im Erkerbild 77 %%"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "uhren_auto.json")
    E = json.load(open(a.elemente))["fassaden"]; FF = {f["id"]: f for f in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}; erg = {}; bilder = []; n_uhr = 0
    for fid, F in E.items():
        kand = [e for e in F.get("elemente", []) if e.get("klasse") == "uhr" and e.get("stimmen", 0) >= a.stimmen and e.get("stimmen", 0) >= 0.4 * max(1, e.get("gesehen", 1))]
        if not kand or fid not in FF: continue
        im = cv2.imread(os.path.join(a.fein, f"ortho_{fid}_fein.png"), cv2.IMREAD_GRAYSCALE); R_ = FF[fid].get("raster")
        if im is None or not R_: continue
        gr = cv2.imread(os.path.join(a.fein, f"ortho_{fid}.png"), cv2.IMREAD_GRAYSCALE)      # wie oeffnungen_wandbild: wo das feine Bild leer ist, das grobe auf demselben Raster einsetzen
        if gr is not None: gr = cv2.resize(gr, (im.shape[1], im.shape[0]), interpolation=cv2.INTER_CUBIC); im = np.where(im > 0, im, gr)
        c = float(R_["zelle"]); u0r, z1r = float(R_["u0"]), float(R_["z1"]); px = lambda u, z: ((u - u0r) / c, (z1r - z) / c)
        e_ = dict(o=F["o"], d=F["d"], n=F["n"], uhren=[], verworfen=[])
        for k in kand:
            g = max(k["u1"] - k["u0"], k["z1"] - k["z0"]); x0, y0 = px(k["u0"] - 0.3 * g, k["z1"] + 0.3 * g); x1, y1 = px(k["u1"] + 0.3 * g, k["z0"] - 0.3 * g)
            x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(im.shape[1], int(x1)), min(im.shape[0], int(y1)); A = im[y0:y1, x0:x1]
            ka, kb = px(k["u0"], k["z1"]), px(k["u1"], k["z0"]); Kz = im[max(0, int(ka[1])):int(kb[1]), max(0, int(ka[0])):int(kb[0])]      # Fuellgrad nur im Kasten selbst (Rand darf ueber die Fassade hinausragen)
            if A.size == 0 or Kz.size == 0 or (Kz > 0).mean() < 0.6: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund="Wandbild in der Zone leer")); continue
            s = min(1.0, 400.0 / max(A.shape)); As = cv2.resize(A, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); As = cv2.GaussianBlur(As, (5, 5), 1.2)
            kan = cv2.Canny(As, 40, 110); rg = 0.5 * g / c * s
            C = cv2.HoughCircles(As, cv2.HOUGH_GRADIENT, dp=1, minDist=3, param1=110, param2=15, minRadius=int(0.7 * rg), maxRadius=int(1.3 * rg) + 1)
            if C is None: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund="kein Kreis im Wandbild")); continue
            best = max(((stuetze(kan, cx, cy, r), cx, cy, r) for cx, cy, r in C[0][:40]), key=lambda t: t[0])
            if best[0] < a.min_stuetze: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund=f"Kreis nur zu {best[0] * 100:.0f} % von Kanten gestuetzt")); continue
            sa, cx, cy, r = best; innen = None
            for f_ in np.arange(0.45, 0.86, 0.01):
                for dx in (-0.04, 0, 0.04):
                    for dy in (-0.04, 0, 0.04):
                        si = stuetze(kan, cx + dx * r, cy + dy * r, f_ * r)
                        if innen is None or si > innen[0]: innen = (si, f_ * r)
            cx, cy, r = float(cx), float(cy), float(r); uc = u0r + (x0 + cx / s) * c; zc = z1r - (y0 + cy / s) * c; da = 2 * r / s * c; di = 2 * innen[1] / s * c if innen and innen[0] >= a.min_stuetze else None
            e_["uhren"].append(dict(u=round(uc, 3), z=round(zc, 3), d_aussen=round(da, 3), d_innen=round(di, 3) if di else None, stuetze_aussen=round(sa, 2), stuetze_innen=round(innen[0], 2) if innen else None,
                                    kasten=[round(k["u0"], 2), round(k["u1"], 2), round(k["z0"], 2), round(k["z1"], 2)], stimmen=k.get("stimmen"),
                                    quelle="Zone OWLv2 'uhr' (fassade_parsing) -> Kreis-Hough + Kantenstuetze im feinen Wandbild (1 cm)"))
            n_uhr += 1; print(f"{fid}: UHR Mitte u {uc:.2f} z {zc:.2f}, Durchmesser {da:.2f} m" + (f", innen {di:.2f} m" if di else ", Innenkreis nicht belegt") + f" (Kantenstuetze {sa * 100:.0f} %)")
            vis = cv2.cvtColor(As, cv2.COLOR_GRAY2BGR); cv2.circle(vis, (int(cx), int(cy)), int(r), (0, 255, 0), 2)
            if di: cv2.circle(vis, (int(cx), int(cy)), int(innen[1]), (0, 200, 255), 2)
            bilder.append(vis)
        for v in e_["verworfen"]: print(f"{fid}: verworfen {v['kasten']}: {v['grund']}")
        erg[fid] = e_
    os.makedirs(os.path.dirname(aus), exist_ok=True); json.dump(erg, open(aus, "w"), indent=1)
    if bilder:
        h = max(b.shape[0] for b in bilder); cv2.imwrite(aus[:-5] + ".jpg", np.hstack([np.pad(b, ((0, h - b.shape[0]), (0, 6), (0, 0))) for b in bilder]))
    print(f"-> {aus}: {n_uhr} Uhren"); return 0 if n_uhr else 3


if __name__ == "__main__": sys.exit(main())
