#!/usr/bin/env python3
"""overlay_diff.py — AUTOMATISCH jede Abweichung Modell↔Foto finden, MÜLL-ROBUST + mit SCORE (zum Ratschen).

Render aufs Foto normieren, im Raster die „Offenheit" (dunkel=Öffnung vs. hell=Wand) vergleichen.
MÜLL-ROBUST: Menschen (Hautton) + Boden-/Standband (unten) + entsättigter Himmel werden MASKIERT,
damit nicht Marktstände/Passanten die Arkade rot färben. Gibt einen GLOBAL-SCORE (mittlere Abweichung
über gültige Zellen) + die größten Abweichzonen. Niedriger Score = besser → Ratschen.

Lauf: /tmp/rv/bin/python tools/overlay_diff.py [--json]
"""
import os, sys, json
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = "/home/md/git/rc-park"
GLB = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_measured.glb"
PHOTO = f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"
PBOX = (0.195, 0.075, 0.79, 0.925)
NX, NY = 18, 26
GROUND_ROWS = 8           # Arkade/Boden ausblenden (Stände/Passanten/Durchgang = unvergleichbar; Bogen-Anzahl ist separat validiert)


def look_at(p, t, up=(0, 0, 1)):
    f = np.array(t)-np.array(p); f = f/np.linalg.norm(f); up = np.array(up, float)
    s = np.cross(f, up); s = s/np.linalg.norm(s); u = np.cross(s, f)
    M = np.eye(4); M[:3, 0] = s; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = p; return M


def render():
    import json
    try:                                                     # ANGEPASSTE Kamera (kamera_fit.py) → Perspektive wie das Foto
        k = json.load(open(f"{ROOT}/modelle/kaufhaus_freiburg/kamera.json")); AZ, EL, FOV = k["az"], k["el"], k["fov"]
    except Exception:
        AZ, EL, FOV = 270, 2.5, 20
    ts = trimesh.load(GLB); sc = pyrender.Scene.from_trimesh_scene(ts, ambient_light=[0.35]*3)
    b = ts.bounds; ctr = b.mean(0); size = b[1]-b[0]; R = float(size.max())
    sc.add(pyrender.DirectionalLight(intensity=1.8), pose=look_at(ctr+np.array([0.1, -0.8, 0.6])*R, ctr))
    cam = pyrender.PerspectiveCamera(yfov=np.radians(FOV)); cn = sc.add(cam)
    r = pyrender.OffscreenRenderer(900, 1200)
    az, el = np.radians(AZ), np.radians(EL); dv = np.array([np.cos(el)*np.cos(az), np.cos(el)*np.sin(az), np.sin(el)])
    sc.set_pose(cn, look_at(ctr+dv*R*4.5*(20.0/FOV), ctr)); col, _ = r.render(sc, flags=pyrender.RenderFlags.RGBA); r.delete()
    al = col[:, :, 3]; ys, xs = np.where(al > 10)
    return Image.fromarray(col[:, :, :3]).crop((xs.min(), ys.min(), xs.max(), ys.max()))


def cell_edge(im, nx, ny):
    """KANTEN-/KONTUR-Merkmal: pro Zelle die Kanten-Energie (Sobel-Betrag), JE BILD normiert → Render-
    vs-Foto-Texturdichte hebt sich raus. Lichtunabhängig + okklusions-robust (Konturen von vertieften
    Fenstern bleiben sichtbar, auch wenn die Füllung verdeckt ist)."""
    g = np.asarray(im.convert("L").resize((nx*16, ny*16))).astype(float)
    gx = ndimage.sobel(g, axis=1); gy = ndimage.sobel(g, axis=0)
    mag = np.hypot(gx, gy); mag /= (mag.mean()+1e-6)
    out = np.zeros((ny, nx))
    for j in range(ny):
        for i in range(nx):
            out[j, i] = mag[j*16:(j+1)*16, i*16:(i+1)*16].mean()
    return np.tanh(out)                           # sättigen → robust gegen einzelne Textur-Ausreißer


def edge_profiles(im):
    """1D-STRUKTURPROFILE: Kanten auf Zeilen/Spalten projiziert. Textur innerhalb eines Bandes
    mittelt sich weg → nur die BAND-/TEILUNGS-LAGEN bleiben (geometrisch, textur-/okklusions-robust)."""
    g = np.asarray(im.convert("L").resize((288, 416))).astype(float)
    gy = ndimage.sobel(g, axis=0); gx = ndimage.sobel(g, axis=1)
    hp = np.abs(gy).mean(1); vp = np.abs(gx).mean(0)                 # waagrechte Bänder / senkrechte Teilungen
    hp = hp/(hp.max()+1e-6); vp = vp/(vp.max()+1e-6)
    return hp, vp   # len 416 (Zeilen), len 288 (Spalten), beide auf Gebäude-BBox normiert


def profile_score(im_photo, im_model):
    """Score = Fehllage der Struktur-Profile im Fassadenbereich (y 0.28..0.74) + volle Breite.
    0 = Bänder/Teilungen liegen deckungsgleich. Robust gegen Licht/Textur/Verdeckung der Füllung."""
    hpP, vpP = edge_profiles(im_photo); hpM, vpM = edge_profiles(im_model)
    H = len(hpP); lo, hi = int(H*0.28), int(H*0.74)                  # Fassade (ohne Boden/Arkade & ohne Dachtextur)
    s_h = np.abs(hpP[lo:hi]-hpM[lo:hi]).mean()
    s_v = np.abs(vpP-vpM).mean()
    return float(0.6*s_h+0.4*s_v), (hpP, hpM, vpP, vpM)


def cell_feats(im, nx, ny):
    a = np.asarray(im.resize((nx*16, ny*16))).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    dark = (r < 105) & (g < 105) & (b < 110)     # (nur noch für Himmel-/Hautmaske)
    # Haut/Passanten: HELL+rosa (nicht die dunkle Ochsenblut-Wand r116/g38!) → g muss hoch sein
    skin = (r > 140) & (g > 85) & (b > 60) & (r-g > 15) & (r-g < 75) & (g-b < 55)
    op = np.zeros((ny, nx)); sk = np.zeros((ny, nx))
    for j in range(ny):
        for i in range(nx):
            op[j, i] = dark[j*16:(j+1)*16, i*16:(i+1)*16].mean()
            sk[j, i] = skin[j*16:(j+1)*16, i*16:(i+1)*16].mean()
    return op, sk


def main():
    ph = Image.open(PHOTO).convert("RGB"); W, H = ph.size
    pc = ph.crop((int(W*PBOX[0]), int(H*PBOX[1]), int(W*PBOX[2]), int(H*PBOX[3])))
    rd = render()
    score, (hpP, hpM, vpP, vpM) = profile_score(pc, rd)
    # größte Höhen-Abweichungen (waagrechte Bänder) im Fassadenbereich
    Hn = len(hpP); lo, hi = int(Hn*0.28), int(Hn*0.74)
    dband = np.abs(hpP-hpM); dband[:lo] = 0; dband[hi:] = 0
    tops = sorted(range(Hn), key=lambda r: -dband[r])[:5]
    if "--json" in sys.argv:
        print(json.dumps({"score": round(score, 4),
                          "top_band_yrel": [round(r/Hn, 3) for r in tops]}))
        return
    # Belegbild: Foto | Modell | Band-Profile übereinander
    base = pc.resize((300, int(300*pc.height/pc.width))); bm = rd.resize((300, int(300*rd.height/rd.width)))
    plot = Image.new("RGB", (240, base.height), (255, 255, 255)); d = ImageDraw.Draw(plot)
    for r in range(Hn-1):
        y0 = int(r/Hn*plot.height); y1 = int((r+1)/Hn*plot.height)
        d.line([(10+hpP[r]*100, y0), (10+hpP[r+1]*100, y1)], fill=(0, 160, 0), width=2)        # Foto grün
        d.line([(130+hpM[r]*100, y0), (130+hpM[r+1]*100, y1)], fill=(220, 40, 40), width=2)     # Modell rot
    d.text((10, 2), "Foto", fill=(0, 120, 0)); d.text((130, 2), "Modell", fill=(200, 0, 0))
    sheet = Image.new("RGB", (base.width+bm.width+plot.width+30, base.height+16), (255, 255, 255))
    sheet.paste(base, (0, 8)); sheet.paste(bm, (base.width+10, 8)); sheet.paste(plot, (base.width+bm.width+20, 8))
    sheet.save("/tmp/overlay_diff.png")
    print(f"SCORE (Struktur-Profil-Fehllage, 0=perfekt): {score:.4f}")
    print("größte Band-Abweichungen (y-rel): " + ", ".join(f"{r/Hn:.2f}" for r in tops))
    print("-> /tmp/overlay_diff.png (Foto | Modell | Band-Profile: grün=Foto rot=Modell)")


if __name__ == "__main__":
    main()
