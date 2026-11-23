#!/usr/bin/env python3
"""Test steine_aus_foto.py Fotowahl je STANDORT (23.11.2026, Schwabentor Sued w05/w07 "STRENG: kein Ergebnis (kein Gegenfoto)").
Befund: die Rangliste nahm die 12 Fotos mit der feinsten Aufloesung - am Schwabentor Sued 8 Aufnahmen EINER Serie (eigen__..113849-113907, ein Standort)
plus 4 Fotos mit falscher Kamera. Die richtigen Gegenfotos von anderen Standorten (eigen__..113836/113837_1 5,7 m daneben, einig 48-85 %,
commons_orig2__133, ..._1, TodorBozhinov_14) lagen auf Rang 13+ und wurden nie geprueft -> Paar-Probe ohne Partner -> --streng lieferte nichts.
Synthetisch: Quaderwand (wie tools/test_steine_paar.py), 14 Serienfotos von Standort A (nah, fein), Foto B von einem anderen Standort (weiter weg, grober,
also Rang 15). Erwartet mit --streng: Gegenfoto B, rc 0, Steine. Vorher: 'STRENG: kein Ergebnis (kein Gegenfoto)', rc 3.
Nur CPU (ohne --stl), < 20 s. Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_steine_standort.py (rc 0 = ok)"""
import sys, os, json, subprocess, shutil, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner
from test_steine_paar import textur, blick, foto
HIER = os.path.dirname(os.path.abspath(__file__))


def main():
    rng = np.random.default_rng(11); T, u, z, c = textur(rng); d = temp_ordner("steine_standort_"); od = os.path.join(d, "modelle", "obj"); mp = os.path.join(od, "messprotokoll"); fd = os.path.join(d, "fotos")
    os.makedirs(mp); os.makedirs(fd); json.dump(dict(fotos_dir="fotos", stl="-"), open(os.path.join(od, "objekt.json"), "w"))
    ziel = np.array([1.5, 0.0, 1.5]); f = 1000.0
    serie = [(f"A{k:02d}", (1.5 + rng.uniform(-0.15, 0.15), -5.8 + rng.uniform(-0.1, 0.1), 1.4 + rng.uniform(-0.05, 0.05))) for k in range(14)]   # eine Serie, ein Standort (< 0,08 x Abstand)
    for name, C in serie + [("B", (5.0, -8.5, 1.6))]:                                                                                          # anderer Standort, weiter weg -> groeber -> Rang 15
        C = np.array(C); R = blick(C, ziel); b = np.clip(foto(T, u, z, c, C, R, f) + rng.normal(0, 4, (900, 900, 3)), 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(fd, name + ".jpg"), b, [cv2.IMWRITE_JPEG_QUALITY, 92])
        json.dump(dict(kamera=dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=(-R @ C).tolist(), f_px=f, cx=450.0, cy=450.0, k1=0.0)), open(os.path.join(mp, f"K-{name}.json"), "w"))
    np.savez_compressed(os.path.join(od, "rel.npz"), rel=np.zeros((60, 60), np.float32), px=0.05, u0=0.0, z0=0.0, a=np.array([0.0, 0.0]), t=np.array([1.0, 0.0]), n=np.array([0.0, -1.0]),
                        trend_je_m=np.array([0.0, 0.0]), ebene_abstand_m=0.0, putz_niveau_m=0.0)
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "steine_aus_foto.py"), os.path.join(od, "rel.npz"), os.path.join(d, "aus.npz"), "-", "0", "-", "--foto", "auto", "--objekt", os.path.join(od, "objekt.json"),
                        "--feld", "0.1", "2.9", "0.1", "2.9", "--px", "0.03", "--nah", "0", "--streng"], capture_output=True, text=True); o = r.stdout + r.stderr; fe = []
    fe += [] if "Gegenfoto B:" in o else ["Gegenfoto nicht B (anderer Standort jenseits der 12 feinsten Fotos nie geprueft): " + " | ".join(l for l in o.splitlines() if "Gegenfoto" in l or l.startswith("STRENG"))]
    fe += [] if r.returncode == 0 and os.path.exists(os.path.join(d, "aus.npz")) and int(np.load(os.path.join(d, "aus.npz"))["steine"]) >= 20 else [f"keine Steine (rc {r.returncode}): " + (o.strip().splitlines() or ["keine Ausgabe"])[-1][:200]]
    if fe or os.environ.get("TEST_ZEIGEN"): print(o)
    shutil.rmtree(d, ignore_errors=True)
    print("\n".join("FEHLER " + x for x in fe) if fe else "steine_aus_foto Fotowahl je Standort ok"); return 1 if fe else 0


if __name__ == "__main__":
    sys.exit(main())
