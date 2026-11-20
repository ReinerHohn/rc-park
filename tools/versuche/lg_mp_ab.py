"""lg_mp_ab.py - A/B 20.11.2026: ALIKED + LightGlue laufen in der Kette mit Standardwerten (float32, kein cudnn.benchmark).
Messung: Zeit je Bild (Merkmale) und je Paar (Zuordnung) fuer (A) Standard, (B) cudnn.benchmark, (C) gemischte Genauigkeit (LightGlue mp=True +
autocast bei ALIKED); dazu Trefferzahl je Paar und Uebereinstimmung der Zuordnungen mit (A). Nur Messung, aendert nichts an der Kette.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/versuche/lg_mp_ab.py <bildordner> [--n 24] [--resize 1024] [--kp 2048]"""
import sys, os, time, argparse, glob
import torch
from lightglue import LightGlue, ALIKED
from lightglue.utils import load_image, rbd
ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--n", type=int, default=24); ap.add_argument("--resize", type=int, default=1024); ap.add_argument("--kp", type=int, default=2048); a = ap.parse_args()
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(0.35)
namen = sorted(f for f in glob.glob(os.path.join(a.ordner, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png")) and "__vf_" not in f)[:a.n]
bilder = [load_image(f) for f in namen]; paare = [(i, j) for i in range(len(bilder)) for j in range(i + 1, min(i + 4, len(bilder)))]
def lauf(name, mp, bench):
    torch.backends.cudnn.benchmark = bench
    ext = ALIKED(max_num_keypoints=a.kp).eval().to(dev); m = LightGlue(features="aliked", mp=mp).eval().to(dev)
    def merk():
        out = []
        for b in bilder:
            with torch.inference_mode(), torch.autocast("cuda", enabled=mp): out.append(ext.extract(b.to(dev), resize=a.resize))
        torch.cuda.synchronize(); return out
    merk(); t = time.time(); F = merk(); tm = (time.time() - t) / len(bilder)
    F = [{k: (v.float() if v.is_floating_point() else v) for k, v in f.items()} for f in F]
    def zu():
        out = []
        for i, j in paare:
            with torch.inference_mode(): out.append(rbd(m({"image0": F[i], "image1": F[j]}))["matches"].cpu())
        torch.cuda.synchronize(); return out
    zu(); t = time.time(); Z = zu(); tz = (time.time() - t) / len(paare)
    print(f"{name:28s} Merkmale {tm*1000:6.1f} ms/Bild   Zuordnung {tz*1000:6.1f} ms/Paar   Treffer/Paar {sum(len(z) for z in Z)/len(Z):7.1f}   VRAM {torch.cuda.max_memory_allocated()/2**20:.0f} MiB", flush=True)
    return Z
print(f"{len(bilder)} Bilder, {len(paare)} Paare, resize {a.resize}, {a.kp} Punkte, torch {torch.__version__}")
A = lauf("A Standard (float32)", False, False); B = lauf("B cudnn.benchmark", False, True); C = lauf("C gemischt (fp16) + bench", True, True)
def gleich(X, Y):
    g = n = 0
    for x, y in zip(X, Y):
        sx = set(map(tuple, x.tolist())); sy = set(map(tuple, y.tolist())); g += len(sx & sy); n += len(sx)
    return 100.0 * g / max(n, 1)
print(f"Uebereinstimmung der Zuordnungen mit A: B {gleich(A, B):.1f} %, C {gleich(A, C):.1f} %  (Hinweis: C nutzt eigene fp16-Merkmale, Abweichung = Merkmale + Zuordnung)")
