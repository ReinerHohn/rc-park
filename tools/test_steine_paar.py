#!/usr/bin/env python3
"""Test steine_aus_foto.py Paar-Probe (21.11.2026, Schwabentor West w00): synthetische Quaderwand (3 x 3 m, Schichten 35 cm, Fugen 2 cm) und vier Fotos.
  A1 = naechstes Foto, aber verwackelt; A2 = gleicher Standort, scharf; C = anderer Standort, Kamera FALSCH (Brennweite im K um 35 % zu gross, wie eigen__192);
  B = anderer Standort, richtig. Erwartet: Paare mit C verworfen ('Kamera falsch, kein Verdecker'), Hauptfoto A2 (bestaetigt), Gegenfoto B, Quader-Tor bestanden, Steine.
Vorher: Gegenfoto = erstes Foto vom anderen Standort (C) -> fast die ganze Wand 'widerspruechlich' ausgeblendet -> Quader-Tor 0 % -> glatte Wand.
Nur CPU (ohne --stl), < 10 s. Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_steine_paar.py (rc 0 = ok)"""
import sys, os, json, tempfile, subprocess, numpy as np, cv2
HIER = os.path.dirname(os.path.abspath(__file__))


def textur(rng, c=0.005, u=(-1.5, 4.5), z=(-1.5, 4.5)):
    nu = int((u[1] - u[0]) / c); nz = int((z[1] - z[0]) / c); T = np.zeros((nz, nu, 3), np.float32); hs = 0.35; fu = 0.02
    for k in range(int((z[1] - z[0]) / hs) + 1):
        z0 = z[0] + k * hs; r0 = int((z[1] - z0 - hs) / c); r1 = int((z[1] - z0) / c); x = u[0] - rng.uniform(0, 0.6)
        while x < u[1]:
            L = rng.uniform(0.4, 0.8); c0 = max(int((x - u[0]) / c), 0); c1 = min(int((x + L - u[0]) / c), nu)
            T[max(r0, 0):max(r1, 0), c0:c1] = (rng.uniform(60, 70), rng.uniform(80, 90), rng.uniform(155, 170)); x += L      # Sandstein: Steine fast gleich, Struktur steckt im Korn
            T[max(r0, 0):max(r1, 0), max(c1 - int(fu / c), 0):c1] = (35, 35, 45)      # Stossfuge
        T[max(r1 - int(fu / c), 0):max(r1, 0)] = (35, 35, 45)                          # Lagerfuge
    korn = cv2.GaussianBlur(rng.normal(0, 1, T.shape[:2]).astype(np.float32), (0, 0), 2.0); T += (korn / korn.std() * 22)[..., None]      # Korn ~1-2 cm
    return np.clip(T, 0, 255).astype(np.uint8), u, z, c


def blick(C, ziel):
    z = np.asarray(ziel, float) - C; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x); return np.array([x, y, z])


def foto(T, u, z, c, C, R, f, W=900, H=900):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64); d = np.stack([(xx - W / 2) / f, (yy - H / 2) / f, np.ones_like(xx)], -1) @ R      # Strahl in Welt
    s = -C[1] / d[..., 1]; P = C + s[..., None] * d; mx = ((P[..., 0] - u[0]) / c).astype(np.float32); my = ((z[1] - P[..., 2]) / c).astype(np.float32)
    return cv2.remap(T, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(200, 180, 150))


def main():
    rng = np.random.default_rng(7); T, u, z, c = textur(rng); d = tempfile.mkdtemp(prefix="steine_paar_"); od = os.path.join(d, "modelle", "obj"); mp = os.path.join(od, "messprotokoll"); fd = os.path.join(d, "fotos")
    os.makedirs(mp); os.makedirs(fd); json.dump(dict(fotos_dir="fotos", stl="-"), open(os.path.join(od, "objekt.json"), "w"))
    ziel = np.array([1.5, 0.0, 1.5]); f = 1000.0
    for name, C, f_k, unscharf in (("A1", (1.5, -5.8, 1.4), f, float(os.environ.get("TEST_UNSCHARF", 7.0))), ("A2", (1.62, -6.0, 1.45), f, 0.0), ("C", (-2.5, -8.0, 1.5), 1.35 * f, 0.0), ("B", (4.5, -7.5, 1.6), f, 0.0)):
        C = np.array(C); R = blick(C, ziel); b = foto(T, u, z, c, C, R, f)
        if unscharf: k_ = np.zeros((int(unscharf) * 2 + 1, 1), np.float32) + 1.0; b = cv2.filter2D(b, -1, k_ / k_.sum())      # senkrecht verwackelt (wie eigen__..114052: Lagerfugen verschmiert)
        b = np.clip(b + rng.normal(0, 4, b.shape), 0, 255).astype(np.uint8)                  # Bildrauschen
        cv2.imwrite(os.path.join(fd, name + ".jpg"), b, [cv2.IMWRITE_JPEG_QUALITY, 92])
        json.dump(dict(kamera=dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=(-R @ C).tolist(), f_px=f_k, cx=450.0, cy=450.0, k1=0.0)), open(os.path.join(mp, f"K-{name}.json"), "w"))
    H_, W_ = 60, 60; np.savez_compressed(os.path.join(od, "rel.npz"), rel=np.zeros((H_, W_), np.float32), px=0.05, u0=0.0, z0=0.0, a=np.array([0.0, 0.0]), t=np.array([1.0, 0.0]), n=np.array([0.0, -1.0]),
                                         trend_je_m=np.array([0.0, 0.0]), ebene_abstand_m=0.0, putz_niveau_m=0.0)
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "steine_aus_foto.py"), os.path.join(od, "rel.npz"), os.path.join(d, "aus.npz"), "-", "0", "-", "--foto", "auto", "--objekt", os.path.join(od, "objekt.json"),
                        "--feld", "0.1", "2.9", "0.1", "2.9", "--px", "0.03", "--nah", "0"], capture_output=True, text=True); o = r.stdout + r.stderr; fe = []
    fe += [] if "Fotopaare verworfen" in o and "+C:" in o.split("Fotopaare verworfen")[1].splitlines()[0] or "C+" in o.split("Fotopaare verworfen")[1].splitlines()[0] else ["Paare mit der falschen Kamera C nicht verworfen"] if "Fotopaare verworfen" in o else ["keine Paar-Probe ('Fotopaare verworfen' fehlt)"]
    fe += [] if "Foto A2:" in o else ["Hauptfoto nicht das scharfe A2: " + " | ".join(l for l in o.splitlines() if l.startswith("Foto "))]
    fe += [] if "Gegenfoto B:" in o else ["Gegenfoto nicht B: " + " | ".join(l for l in o.splitlines() if l.startswith("Gegenfoto"))]
    fe += [] if r.returncode == 0 and os.path.exists(os.path.join(d, "aus.npz")) and int(np.load(os.path.join(d, "aus.npz"))["steine"]) >= 20 else [f"keine Steine (rc {r.returncode}): " + o.strip().splitlines()[-1][:200] if o.strip() else "keine Ausgabe"]
    if r.returncode == 0 and os.path.exists(os.path.join(d, "aus.npz")):      # 21.11.2026: ebene Steine + druckbare Rillen statt erfundener Bosse (quader_raster.quader_relief)
        Za = np.load(os.path.join(d, "aus.npz")); qr_ = json.loads(str(Za["quader_relief"])) if "quader_relief" in Za.files else None
        fe += [] if qr_ and qr_["rille_mm"][0] >= 0.8 - 1e-6 and qr_["rille_mm"][1] >= 0.4 - 1e-6 else [f"Steine ohne druckbare Rillen / ebene Stirnflaeche: {qr_}"]
    if fe or os.environ.get("TEST_ZEIGEN"): print(o)
    import shutil; shutil.rmtree(d, ignore_errors=True)
    print("\n".join("FEHLER " + x for x in fe) if fe else "steine_aus_foto Paar-Probe ok"); return 1 if fe else 0


if __name__ == "__main__":
    sys.exit(main())
