#!/usr/bin/env python3
"""ansichten_foto_paare.py - FUER JEDES MODELL: Kantenbild des Modells aus den kalibrierten Kameras NEBEN dem Foto, ueber alle Blickrichtungen UND Hoehenwinkel (von oben, eben, von unten).
Anlass 13.11.: Erker nur von vorn geprueft, fehlende Seiten/Fenster/Rippen fielen nicht auf. Der Nutzer will: bei jedem Modell Rundumblick, nicht nur gedreht, sondern oben/unten, alles vergleichen.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/ansichten_foto_paare.py modelle/<objekt>/objekt.json [--ziel u n z | gesamt] [--radius 6] [--az 8] [--aus DIR] [--max 24]
Ziel 'gesamt' = Mitte der Modellhuelle; sonst Punkt (u,n,z) im Fassadenrahmen (--nx/--ny Achse). Je Bin (Azimut x Hoehenwinkel: unten < -8, eben, oben > 20 Grad) wird die kalibrierte Kamera gewaehlt,
die das Ziel im Bild hat und am naechsten an der Bin-Mitte liegt. Ausgabe: DIR/paar_<kamera>.jpg (links Foto, rechts Modellkanten) + DIR/paare_uebersicht.json (Bin -> Kamera, ohne Kamera = LUECKE: dort fehlt ein Foto, Aufnahmeauftrag!).
Kanten = Normalenknick > 25 Grad / Tiefensprung > 0,25 m. Reine Geometrie; Beurteilung durch Ansehen (Foto links = Soll)."""
import sys, os, json, glob, math, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as RK
a = sys.argv[1:]
if not a or a[0].startswith("-"): sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.dirname(os.path.abspath(a[0]))
aus = opt("--aus", os.path.join(od, "audit", "paare")); os.makedirs(aus, exist_ok=True); naz = int(opt("--az", 8)); mx = int(opt("--max", 24))
nx, ny = float(opt("--nx", 0.3338)), float(opt("--ny", 0.9426))
m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); c0 = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
if "--ziel" in a and a[a.index("--ziel") + 1] != "gesamt":
    i = a.index("--ziel"); u_, n_, z_ = float(a[i + 1]), float(a[i + 2]), float(a[i + 3]); T0 = np.array([u_ * ny + n_ * nx, -u_ * nx + n_ * ny, z_])
else: T0 = m.bounds.mean(0)
Ns = np.asarray(m.face_normals); kams = {}
for p in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
    try: k = json.load(open(p))["kamera"]
    except Exception: continue
    R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float); sh = np.asarray(k["rahmen_verschiebung"] if "rahmen_verschiebung" in k else [-c0[0], -c0[1], -m.bounds[0, 2]], float)
    C = -R.T @ t - sh; X = R @ (T0 + sh) + t   # Kamerazentrum im Modellrahmen (ohne Verschiebung); Ziel in Kamera
    if X[2] <= 0.5: continue
    px = k["f_px"] * X[0] / X[2] + k["cx"], k["f_px"] * X[1] / X[2] + k["cy"]; W, H = k.get("bild", [3000, 4000]); 
    if not (0.1 * W < px[0] < 0.9 * W and 0.1 * H < px[1] < 0.9 * H): continue
    d = C - T0; hor = math.hypot(d[0], d[1]); az = math.degrees(math.atan2(d[1], d[0])) % 360; el = math.degrees(math.atan2(d[2], hor))
    kams[os.path.basename(p)[:-5]] = dict(k=k, R=R, t=t, sh=sh, az=az, el=el, dist=float(np.linalg.norm(d)))
bins = {}
for kid, v in kams.items():
    eb = "unten" if v["el"] < -8 else ("oben" if v["el"] > 20 else "eben"); ab = int(((v["az"] + 180 / naz) % 360) // (360 / naz)); key = (ab, eb)
    if key not in bins or abs(v["dist"] - 8) < abs(kams[bins[key]]["dist"] - 8): bins[key] = kid
uebers = {f"az{b * 360 // naz:03d}_{e}": k for (b, e), k in sorted(bins.items())}
alle = [f"az{b * 360 // naz:03d}_{e}" for b in range(naz) for e in ("unten", "eben", "oben")]; luecken = [k for k in alle if k not in uebers]
def kanten(m, v, W, H):
    R, t, k, sh = v["R"], v["t"], v["k"], v["sh"]; res = RK.dreiecke_rastern(m, R, t + R @ sh, k["f_px"], k["cx"], k["cy"], W, H); depth, fid = np.asarray(res[0], np.float32), np.asarray(res[1]); tr = fid >= 0
    nn = np.zeros((H, W, 3), np.float32); nn[tr] = Ns[fid[tr]]; dp = np.where(tr, depth, 1e3).astype(np.float32); kan = np.zeros((H, W), bool)
    for dx in (1, 0):
        s1, s2 = (slice(None), slice(0, -1)) if dx else (slice(0, -1), slice(None)); t1, t2 = (slice(None), slice(1, None)) if dx else (slice(1, None), slice(None))
        e = ((nn[s1, s2] * nn[t1, t2]).sum(-1) < math.cos(math.radians(25))) | (np.abs(dp[s1, s2] - dp[t1, t2]) > 0.25) | (tr[s1, s2] != tr[t1, t2]); kan[s1, s2] |= e
    img = np.full((H, W, 3), 255, np.uint8); img[tr] = (235, 235, 235); img[cv2.dilate(kan.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (60, 30, 40); return img
fotos = {}
for p in glob.glob(os.path.join(root, obj["fotos_dir"], "*")): fotos[os.path.basename(p)[:os.path.basename(p).find("_", os.path.basename(p).find("_") + 1)] if os.path.basename(p).count("_") > 2 and os.path.basename(p)[0] in "nhcdp" and os.path.basename(p)[1:3].isdigit() else os.path.basename(p).split("_")[0]] = p
for (key, kid) in list(bins.items())[:mx]:
    kid = bins[key]; v = kams[kid]; pf = fotos.get(kid[2:]) or next((q for q in glob.glob(os.path.join(root, obj['fotos_dir'], kid[2:] + '_*'))), None); 
    if not pf: continue
    im = cv2.imread(pf); H, W = im.shape[:2]; mod = kanten(m, v, W, H);
    X = v["R"] @ (T0 + v["sh"]) + v["t"]; cx_, cy_ = int(v["k"]["f_px"] * X[0] / X[2] + v["k"]["cx"]), int(v["k"]["f_px"] * X[1] / X[2] + v["k"]["cy"]); r = int(float(opt("--radius", 6)) * v["k"]["f_px"] / X[2]); r = max(r, 300)
    x0, y0, x1, y1 = max(cx_ - r, 0), max(cy_ - r, 0), min(cx_ + r, W), min(cy_ + r, H)
    A, B = im[y0:y1, x0:x1], mod[y0:y1, x0:x1]; h = 700; f = lambda z: cv2.resize(z, (int(z.shape[1] * h / z.shape[0]), h))
    A, B = f(A), f(B); cv2.putText(A, f"{kid} az{v['az']:.0f} el{v['el']:+.0f}", (10, 35), 0, 1.0, (255, 255, 255), 3); cv2.putText(B, "Modell (Kanten)", (10, 35), 0, 1.0, (0, 0, 200), 3)
    cv2.imwrite(os.path.join(aus, f"paar_{kid}.jpg"), np.hstack([A, B]), [cv2.IMWRITE_JPEG_QUALITY, 85])
json.dump(dict(ziel=[round(float(x), 2) for x in T0], bins=uebers, luecken_ohne_foto=luecken), open(os.path.join(aus, "paare_uebersicht.json"), "w"), indent=1)
print(f"{len(uebers)} von {len(alle)} Bins mit Foto, {len(luecken)} Luecken (kein kalibriertes Foto) -> {aus}")
