#!/usr/bin/env python3
"""sfm_draufsicht.py <sparse/0> <ausgabe.png> [--nah 3] - Draufsicht eines Sparse-Modells zum ANSEHEN (Regel: Zahlen allein gelten nicht).
Ebene = Hauptebene durch den Kamerakern (75 % naechste Kameras), Punkte grau, Kameras farbig je Gruppe (Namenspraefix vor '__', Videoclips zusammen als 'video'),
Blickrichtung als kurzer Strich. Zweites Bild: Seitenansicht (Hoehe ueber der Kameraebene) - zeigt 'Kameras in der Luft'. --nah: Ausschnitt in Vielfachen des Kamera-Kernradius.
Liest images.bin/points3D.bin direkt (kein pycolmap) -> laeuft mit /media/oem/scan/venv-seg/bin/python -I (matplotlib)."""
import sys, os, struct, argparse
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt


def bilder(p):
    """[(name, Standort, Blickrichtung in Weltkoordinaten)] aus images.bin (COLMAP-Binaerformat, auch 4.x)."""
    out = []
    with open(os.path.join(p, "images.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            f.read(4); q = struct.unpack("<4d", f.read(32)); t = struct.unpack("<3d", f.read(24)); f.read(4); name = b""
            while True:
                ch = f.read(1)
                if ch == b"\x00": break
                name += ch
            k = struct.unpack("<Q", f.read(8))[0]; f.read(24 * k)
            w, x, y, z = q
            R = np.array([[1 - 2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1 - 2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1 - 2*(x*x+y*y)]])
            out.append((name.decode("utf-8", "replace"), -R.T @ np.array(t), R.T @ np.array([0, 0, 1.0])))
    return out


def punkte(p):
    with open(os.path.join(p, "points3D.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]; pts = []
        for _ in range(n):
            f.read(8); pts.append(struct.unpack("<3d", f.read(24))); f.read(3 + 8); tl = struct.unpack("<Q", f.read(8))[0]; f.read(8 * tl)
    return np.array(pts)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("png"); ap.add_argument("--nah", type=float, default=3.0); a = ap.parse_args()
    B = bilder(a.sparse); P = np.array([b[1] for b in B]); Bl = np.array([b[2] for b in B]); pts = punkte(a.sparse)
    d = np.linalg.norm(P - np.median(P, 0), axis=1); kern = d <= np.percentile(d, 75); m = P[kern].mean(0); _, _, Vt = np.linalg.svd(P[kern] - m, full_matrices=False)
    X = (P - m) @ Vt.T; Bz = Bl @ Vt.T; rad = np.percentile(np.linalg.norm(X[kern, :2], axis=1), 90) * a.nah; Xp = (pts - m) @ Vt.T
    grp = ["video" if "__vf_" in os.path.basename(b[0]) else os.path.basename(b[0]).split("__")[0] for b in B]; farben = dict(zip(sorted(set(grp)), plt.cm.tab10.colors))
    fig, ax = plt.subplots(1, 2, figsize=(16, 8))
    for k, (i, j, titel) in enumerate(((0, 1, "Draufsicht (Kameraebene)"), (0, 2, "Seitenansicht (Hoehe ueber Kameraebene)"))):
        ok = (np.abs(Xp[:, i]) < rad) & (np.abs(Xp[:, j]) < rad); ax[k].scatter(Xp[ok, i], Xp[ok, j], s=0.3, c="0.6", alpha=0.4)
        for g in farben:
            s = np.array([x == g for x in grp]); ax[k].scatter(X[s, i], X[s, j], s=9, color=farben[g], label=f"{g} ({s.sum()})")
        L = rad * 0.03
        for q in range(len(X)): ax[k].plot([X[q, i], X[q, i] + L * Bz[q, i]], [X[q, j], X[q, j] + L * Bz[q, j]], color="k", lw=0.3, alpha=0.5)
        ax[k].set_xlim(-rad, rad); ax[k].set_ylim(-rad, rad); ax[k].set_aspect("equal"); ax[k].set_title(titel); ax[k].grid(alpha=0.3)
    ax[0].legend(fontsize=7, loc="upper left"); n_aus = int((np.abs(X[:, :2]) > rad).any(1).sum())
    fig.suptitle(f"{a.sparse}  |  {len(B)} Kameras, {len(pts)} Punkte, {n_aus} Kameras ausserhalb des Ausschnitts (Kernradius x {a.nah})", fontsize=10)
    fig.tight_layout(); fig.savefig(a.png, dpi=110); print("geschrieben", a.png, "| Kameras ausserhalb:", n_aus)


if __name__ == "__main__": main()
