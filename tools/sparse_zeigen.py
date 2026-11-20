"""sparse_zeigen.py - ein COLMAP-Sparse-Modell (Kameramodell) als Bild und als 3D-HTML zeigen. Allgemein, jedes Modell (images.bin + points3D.bin).

Zweck (Nutzer 20.11.2026: "zeig mir das Kameramodell, sobald es fertig ist"): direkt nach dem Mapper sehen, WO die Kameras stehen und welche
Seiten des Objekts Punkte haben - vor Ausrichtung und dichter Wolke. Das Modell ist dann noch NICHT ausgerichtet (kein Massstab, kein Norden):
die Hochachse wird aus den Kameras geschaetzt (Mittel der Bild-Unten-Achsen), Einheiten sind Modell-Einheiten.
Aufruf: tools/py tools/sparse_zeigen.py <sparse-ordner> --png bild.png [--html seite.html] [--titel "..."] [--max-punkte 150000]
Bild: links Draufsicht, rechts Seitenansicht; Punkte in Fotofarbe, Kameras farbig nach Herkunft (eigene Fotos / Videobilder / Netz).
HTML: selbstenthaltene three.js-Seite (Punkte + Kameras, drehen/zoomen), Daten eingebettet.
"""
import argparse, base64, json, os, struct
import numpy as np


def lies_bilder(p):
    """-> Namen, Kamerazentren (n,3), Blickrichtungen (n,3), Unten-Achsen (n,3), Rechts-Achsen (n,3). Format wie tools/kamera_abdeckung.py."""
    namen, C, V, U, Rt = [], [], [], [], []
    with open(os.path.join(p, "images.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            f.read(4); w, x, y, z = struct.unpack("<4d", f.read(32)); t = np.array(struct.unpack("<3d", f.read(24))); f.read(4)
            b = b""
            while True:
                c = f.read(1)
                if c == b"\x00": break
                b += c
            k = struct.unpack("<Q", f.read(8))[0]; f.seek(24 * k, 1)
            R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                          [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                          [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
            namen.append(b.decode("utf-8", "replace")); C.append(-R.T @ t); V.append(R.T @ np.array([0, 0, 1.0])); U.append(R.T @ np.array([0, 1.0, 0])); Rt.append(R.T @ np.array([1.0, 0, 0]))
    return namen, np.array(C), np.array(V), np.array(U), np.array(Rt)


def lies_punkte(p):
    """-> xyz (n,3), rgb (n,3 uint8), Spurlaenge (n,)."""
    d = open(os.path.join(p, "points3D.bin"), "rb").read(); n = struct.unpack_from("<Q", d, 0)[0]; o = 8
    X = np.empty((n, 3)); F = np.empty((n, 3), np.uint8); S = np.empty(n, np.int64)
    for i in range(n):
        X[i] = struct.unpack_from("<3d", d, o + 8); F[i] = struct.unpack_from("<3B", d, o + 32); k = struct.unpack_from("<Q", d, o + 43)[0]; S[i] = k; o += 51 + 8 * k
    return X, F, S


def herkunft(name):
    """Gruppe eines Bildes aus dem Dateinamen der Kette (tools/fotos_sammeln.py): Videobild, Netzfoto oder eigenes Foto."""
    n = name.lower()
    if "__vf_" in n or "video_frames" in n: return "Videobilder"
    if any(k in n for k in ("commons", "netz", "openverse", "mapillary", "wikimedia", "flickr")): return "Netzfotos"
    return "eigene Fotos"


def lot_rahmen(C, U, Rt):
    """Hochachse = Richtung, die zu den Bild-Rechts-Achsen aller Kameras am senkrechtesten steht (kleinster Eigenvektor von sum r r^T): die Rechts-Achse
    bleibt beim Hoch-/Runterschauen waagrecht, die Unten-Achse nicht (20.11.2026: Mittel der Unten-Achsen kippte das Martinstor-Modell, weil fast alle
    Kameras aus EINER Richtung nach oben schauen). Vorzeichen aus den Unten-Achsen. e1,e2 spannen den Boden auf (e1 = Hauptrichtung der Kameras)."""
    w, v = np.linalg.eigh(Rt.T @ Rt); up = v[:, 0]; up = up if up @ (-U.mean(0)) > 0 else -up
    Cz = C - C.mean(0); Cb = Cz - np.outer(Cz @ up, up)
    _, _, vt = np.linalg.svd(Cb, full_matrices=False); e1 = vt[0] - (vt[0] @ up) * up; e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1)
    return up, e1, e2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("--png"); ap.add_argument("--html"); ap.add_argument("--titel", default="")
    ap.add_argument("--max-punkte", type=int, default=150000); a = ap.parse_args()
    namen, C, V, U, Rt = lies_bilder(a.sparse); X, F, S = lies_punkte(a.sparse)
    up, e1, e2 = lot_rahmen(C, U, Rt); m = np.median(C, 0)
    def lokal(P): P = P - m; return np.stack([P @ e1, P @ e2, P @ up], 1)
    Cl, Xl = lokal(C), lokal(X); Vl = np.stack([V @ e1, V @ e2, V @ up], 1)
    r = np.percentile(np.linalg.norm(Cl[:, :2], axis=1), 95) * 2.2 + 1e-9                      # Ausschnitt: Kamerakranz + Rand
    ok = (np.abs(Xl[:, 0]) < r) & (np.abs(Xl[:, 1]) < r) & (S >= 3); Xl, F = Xl[ok], F[ok]
    lo, hi = np.percentile(Xl[:, 2], [1, 99.5]); ok = (Xl[:, 2] > lo - 0.1 * (hi - lo)) & (Xl[:, 2] < hi + 0.1 * (hi - lo)); Xl, F = Xl[ok], F[ok]
    if len(Xl) > a.max_punkte: i = np.random.default_rng(0).choice(len(Xl), a.max_punkte, replace=False); Xl, F = Xl[i], F[i]
    gr = [herkunft(n) for n in namen]; farbe = {"eigene Fotos": "#d62728", "Videobilder": "#ff9f1c", "Netzfotos": "#1f77b4"}
    zahl = {g: gr.count(g) for g in farbe if gr.count(g)}
    print(f"Modell: {len(namen)} Kameras ({', '.join(f'{v} {k}' for k, v in zahl.items())}), {len(X)} Punkte, gezeigt {len(Xl)}")
    if a.png:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(18, 9), facecolor="#111"); L = r * 0.06
        for k, (i, j, t) in enumerate([(0, 1, "Draufsicht"), (0, 2, "Seitenansicht")]):
            A = ax[k]; A.set_facecolor("#111"); o = np.argsort(Xl[:, 2 if k == 0 else 1])
            A.scatter(Xl[o, i], Xl[o, j], c=F[o] / 255.0, s=0.6, linewidths=0)
            for g, f in farbe.items():
                w = np.array([x == g for x in gr])
                if not w.any(): continue
                A.plot(np.stack([Cl[w, i], Cl[w, i] + L * Vl[w, i]]), np.stack([Cl[w, j], Cl[w, j] + L * Vl[w, j]]), color=f, lw=0.5, alpha=0.6)
                A.scatter(Cl[w, i], Cl[w, j], c=f, s=9, label=f"{g} ({w.sum()})", zorder=5, edgecolors="none")
            A.set_aspect("equal"); A.set_xlim(-r, r); A.set_ylim((-r, r) if k == 0 else (lo - 0.15 * (hi - lo), max(hi + 0.15 * (hi - lo), lo + 0.9 * r)))
            A.set_title(t, color="w", fontsize=15); A.tick_params(colors="#888"); [s.set_color("#444") for s in A.spines.values()]
        ax[0].legend(loc="upper right", facecolor="#222", labelcolor="w", fontsize=11, markerscale=2)
        fig.suptitle((a.titel + " - " if a.titel else "") + f"{len(namen)} Kameras, {len(X) // 1000} Tsd. Punkte (nicht ausgerichtet, Modell-Einheiten)", color="w", fontsize=16)
        fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(a.png, dpi=110, facecolor="#111"); print("Bild:", a.png)
    if a.html:
        s = 10.0 / r; P = (Xl * s).astype(np.float32); K = (Cl * s).astype(np.float32); KV = Vl.astype(np.float32)
        kf = np.array([[int(farbe[g][q:q + 2], 16) for q in (1, 3, 5)] for g in gr], np.uint8)
        b = lambda x: base64.b64encode(np.ascontiguousarray(x).tobytes()).decode()
        vorl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sparse_zeigen_vorlage.html"), encoding="utf-8").read()
        daten = dict(titel=a.titel or "Kameramodell", n_kam=len(namen), n_pkt=int(len(X)), gruppen=zahl, farben=farbe, P=b(P), F=b(F), K=b(K), KV=b(KV), KF=b(kf))
        open(a.html, "w", encoding="utf-8").write(vorl.replace("/*DATEN*/null", json.dumps(daten))); print("HTML:", a.html, f"({os.path.getsize(a.html) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
