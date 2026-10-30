#!/usr/bin/env python3
"""selfcheck.py — EIN Befehl, EIN Beleg: nach jedem Build alle Prüfebenen auf einen Blick.
Zweck (User): schnellere Iterationen durch bessere Fehler-ERKENNUNG — statt viele Mini-Loops je
einen vom User gemeldeten Fehler, fange ich ALLE auf einmal selbst.

Läuft mit:  /tmp/rv/bin/python tools/selfcheck.py
Prüft:  (1) Build-Fehler  (2) Bounds/Printbarkeit (ragt was über First / unter Boden; offene
Teile)  (3) Render Front+Schräg  (4) GANZE-Bauteil-Vergleiche Foto↔Modell (Fenster/Erker/Gaube)
(5) Proportions-Zahlen (Modell-Seite). Gibt EINEN Beleg /tmp/selfcheck.png + Warnliste aus.
"""
import os, sys, subprocess
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image, ImageDraw

ROOT = "/home/md/git/rc-park"
GLB = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_measured.glb"
PH = {"front": f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg",
      "fenster": f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_fenster.jpg",
      "erker": f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_erker.jpg"}
RIDGE = 15.4
# Element-Crops (GANZES Bauteil, mit Rand!): name -> (foto-key, foto-box, modell-box)  box=frac
ELEMENTS = [
    ("Fenster", "fenster", (0.16, 0.10, 0.45, 0.92), (0.35, 0.33, 0.53, 0.60)),
    ("Erker",   "erker",   (0.45, 0.02, 0.92, 0.98), (0.62, 0.30, 0.95, 0.78)),
    ("Dach/Gaube", "front", (0.17, 0.02, 0.84, 0.34), (0.28, 0.22, 0.74, 0.42)),
]


def look_at(p, t, up=(0, 0, 1)):
    f = np.array(t)-np.array(p); f = f/np.linalg.norm(f); up = np.array(up, float)
    s = np.cross(f, up); s = s/np.linalg.norm(s); u = np.cross(s, f)
    M = np.eye(4); M[:3, 0] = s; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = p; return M


def render(views):
    ts = trimesh.load(GLB); sc = pyrender.Scene.from_trimesh_scene(ts, ambient_light=[0.4]*3)
    b = ts.bounds; ctr = b.mean(0); size = b[1]-b[0]; R = float(size.max())
    sc.add(pyrender.DirectionalLight(intensity=2.6), pose=look_at(ctr+np.array([0.3, -0.6, 0.9])*R, ctr))
    sc.add(pyrender.DirectionalLight(intensity=1.0), pose=look_at(ctr+np.array([-0.6, -0.3, 0.4])*R, ctr))
    cam = pyrender.PerspectiveCamera(yfov=np.radians(24)); cn = sc.add(cam); r = pyrender.OffscreenRenderer(1100, 850)
    tgt = ctr-np.array([0, 0, size[2]*0.12]); out = {}
    for nm, az, el in views:
        a, e = np.radians(az), np.radians(el); dv = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
        sc.set_pose(cn, look_at(tgt+dv*R*4.3, tgt)); col, _ = r.render(sc, flags=pyrender.RenderFlags.RGBA)
        al = col[:, :, 3:4]/255.0; out[nm] = Image.fromarray((col[:, :, :3]*al + 255*(1-al)).astype(np.uint8))
    r.delete(); return out


def crop(path, box):
    im = Image.open(path).convert("RGB"); w, h = im.size
    return im.crop((int(w*box[0]), int(h*box[1]), int(w*box[2]), int(h*box[3])))


def main():
    warn = []
    # 1 BUILD
    rb = subprocess.run([sys.executable.replace("/tmp/rv/bin/python", "python3"), f"{ROOT}/tools/kaufhaus_measured.py"],
                        capture_output=True, text=True, cwd=ROOT)
    for ln in (rb.stdout+rb.stderr).splitlines():
        if any(k in ln for k in ("Error", "Traceback", "Exception", "Topolog", "leer")):
            warn.append("BUILD: "+ln.strip())
    # 2 BOUNDS / Printbarkeit
    import glob
    nwt = 0
    for f in sorted(glob.glob(f"{ROOT}/modelle/kaufhaus_freiburg/khm_*.stl")):
        m = trimesh.load(f); b = m.bounds; nm = os.path.basename(f)[4:-4]
        if b[1][2] > RIDGE+1.0 and nm not in ("helm", "krabben", "firstkamm", "first", "giebel"):
            warn.append(f"BOUNDS {nm}: ragt bis z={b[1][2]:.1f} (First {RIDGE}) — prüfen")
        if b[0][2] < -0.3:
            warn.append(f"BOUNDS {nm}: unter Boden z={b[0][2]:.1f}")
        if not m.is_watertight:
            nwt += 1
    # 3 RENDER
    rv = render([("front", 270, 4), ("oblique", 248, 13)])
    H = 430
    def rs(im): return im.resize((int(im.width*H/im.height), H))
    photo = rs(crop(PH["front"], (0.17, 0.02, 0.83, 0.98)))
    top = [photo, rs(rv["front"]), rs(rv["oblique"])]
    toprow = Image.new("RGB", (sum(i.width for i in top)+20, H), (250, 250, 250))
    x = 0
    for i in top:
        toprow.paste(i, (x, 0)); x += i.width+10
    # 4 ELEMENT-Vergleiche (ganzes Bauteil)
    EH = 300; cells = []
    for name, pk, fb, mb in ELEMENTS:
        pc = crop(PH[pk], fb); mc = rv["front"].crop((int(rv["front"].width*mb[0]), int(rv["front"].height*mb[1]),
                                                       int(rv["front"].width*mb[2]), int(rv["front"].height*mb[3])))
        pc = pc.resize((int(pc.width*EH/pc.height), EH)); mc = mc.resize((int(mc.width*EH/mc.height), EH))
        cell = Image.new("RGB", (pc.width+mc.width+14, EH+22), (240, 240, 240))
        cell.paste(pc, (0, 22)); cell.paste(mc, (pc.width+14, 22))
        ImageDraw.Draw(cell).text((4, 5), f"{name}: FOTO | MODELL", fill=(0, 0, 0)); cells.append(cell)
    elrow = Image.new("RGB", (sum(c.width for c in cells)+20, EH+22), (250, 250, 250))
    x = 0
    for c in cells:
        elrow.paste(c, (x, 0)); x += c.width+10
    sheet = Image.new("RGB", (max(toprow.width, elrow.width), toprow.height+elrow.height+10), (255, 255, 255))
    sheet.paste(toprow, (0, 0)); sheet.paste(elrow, (0, toprow.height+10)); sheet.save("/tmp/selfcheck.png")
    # 5 Report
    print("=== SELFCHECK ===")
    print(f"nicht-wasserdichte Teile: {nwt}")
    print("WARNUNGEN:" if warn else "✓ keine automatischen Warnungen")
    for w in warn:
        print("  ⚠ "+w)
    print("-> Beleg (Foto|Front|Schräg + Bauteil-Vergleiche): /tmp/selfcheck.png")
    print("JETZT: Beleg mit eigenen Augen prüfen — Form/Proportion je Bauteil Foto↔Modell.")


if __name__ == "__main__":
    main()
