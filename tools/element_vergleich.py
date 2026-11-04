#!/usr/bin/env python3
"""element_vergleich.py - Foto | Modell je ELEMENT automatisch nebeneinander + Oeffnungs-Abgleich (Register CF: "kleine Boegelchen" dreimal uebersehen).

Warum: Form-/Proportionsfehler (Bogenform, Zahl, Breite der Oeffnungen) sieht die Punktwolke nicht; ich habe sie nur gefunden, als ich Foto und Modell
desselben Bauteils von Hand nebeneinander gelegt habe. Dieses Werkzeug macht genau das ohne Handarbeit, fuer jedes Element und jedes kalibrierte Foto:
  1. Elemente kommen aus den Wolkenprofilen (profile_baender_*.json, Band 'offen'): Rundkoerper -> je Achsposition (+-tief, +-quer), Zentralkoerper -> je Seite.
  2. Mit der Fotokamera (K-<foto>.json) wird das Modell gerendert; Ausschnitt um die Projektion des Elements, im Foto UND im Render gleich gross.
  3. Lokaler Versatzausgleich (Kamera oben oft ungenau): Kantenbild des Renders in einem 1,6-fach groesseren Fotoausschnitt per Kreuzkorrelation suchen.
  4. Oeffnungsmasken im Band: Modell = Durchblick (Tiefe > Elementtiefe + 0,5 m oder kein Treffer), Foto = dunkel (Otsu im Band).
     Kennzahl IoU der Masken + Spaltenprofil (Anteil offen je Spalte) -> Korrelation. Beides landet in audit/element_vergleich_<foto>.json, das Bild mit
     Foto | Modell | Masken in audit/element_vergleich_<foto>.jpg - dieses Blatt ist nach JEDEM Bau anzusehen (CLAUDE.md 9b).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/element_vergleich.py modelle/<objekt>/objekt.json <foto> [--stl andere.stl] [--tag x]
Grenzen: Foto-Dunkelheit = Oeffnung ist eine Annahme (Schatten, dunkler Stein); Masstab-/Rotationsfehler der Kamera werden nur als Versatz ausgeglichen.
"""
import sys, os, json, glob, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF

def elemente(od):
    E = []
    for pf in sorted(glob.glob(os.path.join(od, "profile_baender_*.json"))):
        P = json.load(open(pf)); ach = P.get("achse") or {}; kn = P.get("koerper", os.path.basename(pf)[16:-5])
        for b in P.get("baender", []):
            if b.get("klasse") != "offen": continue
            z0, z1, r = b["z0"], b["z1"], b["r"]; tief, quer = ach.get("tief", 0.0), ach.get("quer", 0.0)
            if tief or quer:
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        E.append(dict(name=f"{kn} ({sx * tief:+.1f},{sy * quer:+.1f}) {z0}-{z1} m", c=(sx * tief, sy * quer), r=r, z0=z0, z1=z1, art="rund", halb=r * 1.25))
            else:
                hq = (b.get("breite_quer") or r) * 0.55
                for ax, s in ((0, 1), (0, -1), (1, 1), (1, -1)):
                    c = [0.0, 0.0]; c[ax] = s * r
                    E.append(dict(name=f"{kn} Seite {'+-'[s < 0]}{'xy'[ax]} {z0}-{z1} m", c=tuple(c), r=0.0, z0=z0, z1=z1, art="seite", normal=(ax, s), halb=max(hq, 1.2)))
    return E

def proj(R, t, f, cx, cy, P):
    q = R @ np.asarray(P, float) + t; return np.array([cx + f * q[0] / q[2], cy + f * q[1] / q[2]]), q[2]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--stl"); ap.add_argument("--tag", default=""); a = ap.parse_args(); nr = a.foto
    obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kp = os.path.join(od, "messprotokoll", f"K-{nr}.json"); K = json.load(open(kp)) if os.path.exists(kp) else {}
    if "kamera" not in K: print(f"element_vergleich {nr}: keine kalibrierte Kamera - uebersprungen"); return
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]; cx, cy = W / 2, H / 2
    R, t, f, quelle, _ = FF.kamera_laden(K, obj, nr, root, W, H); cam = -R.T @ t
    m = trimesh.load(a.stl or os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    if obj.get("zentrierung", "huelle") == "huelle": c0 = m.bounds.mean(0); m.apply_translation([-c0[0], -c0[1], -m.bounds[0, 2]])
    depth, nrm, pos = FF.render(m, R, t, f, W, H, cx, cy, n=10000000)
    dfill = depth.copy(); dfill[~np.isfinite(dfill)] = 1e6; dfill = cv2.erode(dfill.astype(np.float32), np.ones((5, 5), np.uint8))
    shade = np.clip(60 + 190 * np.abs(np.nan_to_num(nrm @ np.array([0.3, 0.4, 0.85]))), 0, 255).astype(np.uint8); shade[dfill >= 1e6] = 255
    shade = cv2.erode(shade, np.ones((3, 3), np.uint8)); gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    rows, erg = [], []
    for e in elemente(od):
        zc = (e["z0"] + e["z1"]) / 2
        if e["art"] == "rund":
            mitte = np.array([e["c"][0], e["c"][1], zc]); blick = cam[:2] - mitte[:2]
            vorne = mitte.copy(); vorne[:2] += e["r"] * blick / np.linalg.norm(blick)
        else:
            ax, s = e["normal"]; mitte = np.array([e["c"][0], e["c"][1], zc]); vorne = mitte
            if s * (cam[ax] - mitte[ax]) <= 0: continue                                            # Seite zeigt vom Foto weg
        uv, zcam = proj(R, t, f, cx, cy, vorne)
        if zcam <= 0 or not (0 <= uv[0] < W and 0 <= uv[1] < H): continue
        ppm = f / zcam; hw = int(e["halb"] * ppm); hz = int((e["z1"] - e["z0"]) / 2 * ppm * 1.6)
        if hw < 12: continue
        x0, x1, y0, y1 = int(uv[0]) - hw, int(uv[0]) + hw, int(uv[1]) - hz, int(uv[1]) + hz
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H: continue
        d_el = float(np.linalg.norm(vorne - cam))
        # 3) Versatz: Kantenbild des Renders im 1,6-fach groesseren Fotoausschnitt suchen
        mk = cv2.Canny(shade[y0:y1, x0:x1], 30, 90).astype(np.float32)
        px, py = int(0.3 * (x1 - x0)), int(0.3 * (y1 - y0)); X0, Y0 = max(0, x0 - px), max(0, y0 - py); X1, Y1 = min(W, x1 + px), min(H, y1 + py)
        fg = cv2.GaussianBlur(gray[Y0:Y1, X0:X1], (0, 0), max(1.0, 0.05 * ppm)); fk = cv2.Canny(fg, 20, 60).astype(np.float32)
        fk = cv2.GaussianBlur(fk, (0, 0), 2.0); mkb = cv2.GaussianBlur(mk, (0, 0), 2.0)
        if mkb.std() < 1e-3 or fk.shape[0] < mkb.shape[0] or fk.shape[1] < mkb.shape[1]: continue
        res = cv2.matchTemplate(fk, mkb, cv2.TM_CCORR_NORMED); _, best, _, loc = cv2.minMaxLoc(res); fx0, fy0 = X0 + loc[0], Y0 + loc[1]
        fc = im[fy0:fy0 + (y1 - y0), fx0:fx0 + (x1 - x0)]; fgc = gray[fy0:fy0 + (y1 - y0), fx0:fx0 + (x1 - x0)]
        # 4) Oeffnungsmasken im Band (Zeilen der Bandhoehe an der Elementfront)
        zb0 = proj(R, t, f, cx, cy, vorne + [0, 0, e["z0"] - zc])[0][1] - uv[1]; zb1 = proj(R, t, f, cx, cy, vorne + [0, 0, e["z1"] - zc])[0][1] - uv[1]
        r0, r1 = int(hz + min(zb0, zb1)), int(hz + max(zb0, zb1)); r0, r1 = max(0, r0), min(y1 - y0, r1)
        mo = (dfill[y0:y1, x0:x1] > d_el + 0.5); mo[:r0] = False; mo[r1:] = False
        sil = (dfill[y0:y1, x0:x1] < 1e6)
        cols = sil[r0:r1].any(0) if r1 > r0 else np.zeros(x1 - x0, bool)
        band = fgc[r0:r1][:, cols] if cols.any() else np.zeros((1, 1), np.uint8)
        thr, _ = cv2.threshold(band.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU) if band.size > 16 else (0, None)
        fo = np.zeros_like(mo); fo[r0:r1] = fgc[r0:r1] < thr; fo[:, ~cols] = False; mo[:, ~cols] = False
        inter, uni = (fo & mo).sum(), (fo | mo).sum(); iou = float(inter / uni) if uni else float("nan")
        pf, pm = fo[r0:r1].mean(0)[cols] if cols.any() else np.zeros(1), mo[r0:r1].mean(0)[cols] if cols.any() else np.zeros(1)
        korr = float(np.corrcoef(pf, pm)[0, 1]) if pf.std() > 1e-6 and pm.std() > 1e-6 else float("nan")
        anteil_f, anteil_m = float(fo[r0:r1][:, cols].mean()) if cols.any() else 0.0, float(mo[r0:r1][:, cols].mean()) if cols.any() else 0.0
        erg.append(dict(element=e["name"], iou_oeffnungen=round(iou, 3), spaltenprofil_korr=round(korr, 3), offen_anteil_foto=round(anteil_f, 3), offen_anteil_modell=round(anteil_m, 3),
                        versatz_px=[int(fx0 - x0), int(fy0 - y0)], kanten_korr=round(float(best), 3), ausschnitt=[x0, y0, x1, y1]))
        sc = 300.0 / (y1 - y0); z_ = lambda b: cv2.resize(b, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
        mviz = np.zeros(fo.shape + (3,), np.uint8); mviz[fo] = (0, 200, 255); mviz[mo] = (255, 80, 0); mviz[fo & mo] = (0, 220, 0)
        row = np.hstack([z_(fc), np.full((int(round((y1 - y0) * sc)), 6, 3), 255, np.uint8), z_(cv2.cvtColor(shade[y0:y1, x0:x1], cv2.COLOR_GRAY2BGR)), np.full((int(round((y1 - y0) * sc)), 6, 3), 255, np.uint8), z_(mviz)])
        cv2.putText(row, f"{e['name'][:38]}  IoU {iou:.2f} Profil {korr:.2f}  offen F {anteil_f:.2f} / M {anteil_m:.2f}", (6, 20), 0, 0.55, (0, 0, 255), 2); rows.append(row)
    out = os.path.join(root, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); os.makedirs(out, exist_ok=True); tag = ("_" + a.tag) if a.tag else ""
    if rows:
        wmax = max(r.shape[1] for r in rows); cv2.imwrite(os.path.join(out, f"element_vergleich_{nr}{tag}.jpg"), np.vstack([np.pad(r, ((0, 8), (0, wmax - r.shape[1]), (0, 0)), constant_values=255) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 88])
    json.dump(dict(foto=nr, kamera=quelle, stl=a.stl or obj["stl"], elemente=erg, legende="Foto | Modell | Masken (gelb nur Foto dunkel, blau nur Modell offen, gruen beide)"),
              open(os.path.join(out, f"element_vergleich_{nr}{tag}.json"), "w"), indent=1, ensure_ascii=False)
    print(f"element_vergleich {nr} ({quelle}): {len(erg)} Element(e) -> {out}/element_vergleich_{nr}{tag}.jpg")
    for r_ in erg: print(f"  {r_['element']:42s} IoU {r_['iou_oeffnungen']:.2f}  Profil-Korr {r_['spaltenprofil_korr']:+.2f}  offen Foto {r_['offen_anteil_foto']:.2f} Modell {r_['offen_anteil_modell']:.2f}  Versatz {r_['versatz_px']}")

if __name__ == "__main__":
    main()
