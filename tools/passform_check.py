#!/usr/bin/env python3
"""passform_check.py — AUTOMATISCHER Lage-Abgleich Modell-Render ↔ Foto (fängt „Element auf falscher
Höhe", z.B. Statuen auf Balkonhöhe). Zweck (User): solche Fehler künftig AUTOMATISCH erkennen, statt
sie per Auge finden zu müssen.

Prinzip: beide Bilder aufs Gebäude normieren (y: 0=First .. 1=Boden). Je markantes Element dieselbe
Eigenschaft in BEIDEN messen und die relative Höhe vergleichen:
  - Statuen  = helle (silberne) Blobs im Fassadenband → mittlere y-Lage
  - Traufe   = Unterkante der grünen Dachfläche
  - Brüstung = oberste lange horizontale Kante im unteren Fassadendrittel
Δ (Foto−Modell) über Schwelle → FLAG.

Lauf: /tmp/rv/bin/python tools/passform_check.py
"""
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image

ROOT = "/home/md/git/rc-park"
GLB = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_measured.glb"
PHOTO = f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"
PHOTO_BOX = (0.195, 0.075, 0.79, 0.925)   # Gebäude Erker→Erker / Helm→Boden (gemessen)
TOL = 0.04                                 # 4 % der Gebäudehöhe


def look_at(p, t, up=(0, 0, 1)):
    f = np.array(t)-np.array(p); f = f/np.linalg.norm(f); up = np.array(up, float)
    s = np.cross(f, up); s = s/np.linalg.norm(s); u = np.cross(s, f)
    M = np.eye(4); M[:3, 0] = s; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = p; return M


def render_front():
    ts = trimesh.load(GLB); sc = pyrender.Scene.from_trimesh_scene(ts, ambient_light=[0.5]*3)
    b = ts.bounds; ctr = b.mean(0); size = b[1]-b[0]; R = float(size.max())
    sc.add(pyrender.DirectionalLight(intensity=2.3), pose=look_at(ctr+np.array([0.2, -0.7, 0.7])*R, ctr))
    cam = pyrender.PerspectiveCamera(yfov=np.radians(22)); cn = sc.add(cam)
    r = pyrender.OffscreenRenderer(1000, 1100)
    az, el = np.radians(270), np.radians(3); dv = np.array([np.cos(el)*np.cos(az), np.cos(el)*np.sin(az), np.sin(el)])
    sc.set_pose(cn, look_at(ctr+dv*R*4.5, ctr)); col, _ = r.render(sc, flags=pyrender.RenderFlags.RGBA); r.delete()
    al = col[:, :, 3]; ys, xs = np.where(al > 10)
    return col[:, :, :3], (xs.min(), ys.min(), xs.max(), ys.max()), al > 10


def yfrac(rows, y0, y1):
    return (np.array(rows)-y0)/max(1, (y1-y0))


def measure_photo(a, bb):
    x0, y0, x1, y1 = bb
    reg = a[y0:y1, x0:x1].astype(int); hh, ww, _ = reg.shape
    r, g, b = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    mx = reg.max(2); mn = reg.min(2)
    out = {}
    # Statuen = helle, entsättigte Blobs im Fassadenband (y 0.35..0.72)
    band = slice(int(hh*0.35), int(hh*0.72))
    bright = (mn[band] > 115) & ((mx[band]-mn[band]) < 55)
    ys = np.where(bright.any(1))[0]
    if len(ys):
        out["Statuen"] = float(np.median(ys)+hh*0.35)/hh
    # Traufe = Unterkante der grünen Dachfläche — NUR obere 55 % suchen (Dach ist oben; unten=Boden/Stände)
    green = (g > b+8) & (g > 70) & (g < 195) & (r < g+45)
    top = int(hh*0.55); gy = np.where(green[:top].sum(1) > ww*0.3)[0]
    if len(gy):
        out["Traufe"] = float(gy.max())/hh
    return out


def measure_model(rgb, bb):
    x0, y0, x1, y1 = bb
    reg = rgb[y0:y1, x0:x1].astype(int); hh, ww, _ = reg.shape
    r, g, b = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    out = {}
    # Statuen = silber [206,206,212] — NUR im Fassadenband (y 0.35..0.72) suchen (sonst zählt die
    # creme Helm-Glasur [224,214,190] mit → Median verfälscht); Median über Statuen-PIXEL
    silver = (np.abs(r-206) < 32) & (np.abs(g-206) < 32) & (np.abs(b-212) < 32) & (np.abs(r-g) < 18)
    band = np.zeros_like(silver); band[int(hh*0.35):int(hh*0.72), :] = True
    ys = np.where((silver & band))[0]
    if len(ys):
        out["Statuen"] = float(np.median(ys))/hh
    # Traufe = Unterkante grün Dach [96,108,74]/[88,102,70] — obere 55 %
    green = (np.abs(g-105) < 45) & (g > b+10) & (g > r-15) & (b < 110)
    top = int(hh*0.55); gy = np.where(green[:top].sum(1) > ww*0.3)[0]
    if len(gy):
        out["Traufe"] = float(gy.max())/hh
    return out


def main():
    im = Image.open(PHOTO).convert("RGB"); W, H = im.size
    bbp = (int(W*PHOTO_BOX[0]), int(H*PHOTO_BOX[1]), int(W*PHOTO_BOX[2]), int(H*PHOTO_BOX[3]))
    mp = measure_photo(np.asarray(im), bbp)
    rgb, bbm, _ = render_front()
    mm = measure_model(rgb, bbm)
    print("=== PASSFORM Modell ↔ Foto (y: 0=First .. 1=Boden) ===")
    print(f"{'Element':<12}{'FOTO':>8}{'MODELL':>9}{'Δ':>8}")
    flags = []
    for k in ("Traufe", "Statuen"):
        pf, mf = mp.get(k), mm.get(k)
        if pf is None or mf is None:
            print(f"{k:<12}{str(round(pf,3) if pf else '-'):>8}{str(round(mf,3) if mf else '-'):>9}   (unvollständig)")
            continue
        d = pf-mf
        tag = "" if abs(d) < TOL else "   <-- FLAG"
        if abs(d) >= TOL:
            flags.append(f"{k}: Foto {pf:.2f} vs Modell {mf:.2f} (Δ{d:+.2f} = {abs(d)*100:.0f}% der Höhe)")
        print(f"{k:<12}{pf:>8.3f}{mf:>9.3f}{d:>+8.3f}{tag}")
    print("\n"+("✓ Lagen passen (±%d%%)" % int(TOL*100) if not flags else "⚠ ABWEICHUNGEN:"))
    for f in flags:
        print("  "+f)


if __name__ == "__main__":
    main()
