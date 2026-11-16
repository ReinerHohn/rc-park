#!/usr/bin/env python3
"""fassade_ein_foto.py <fassaden.json> <nr> <objekt.json> <FOTO|auto> <aus.png> [--stl a.stl,b.stl] [--z z0 z1] [--u u0 u1] - entzerrtes Fassadenbild einer Wand aus EINEM kalibrierten Foto.

Fuer Waende, die das Mehrfoto-Fassadenbild nicht oder nur grob zeigt (Quellen-Blindheit, hohe Zonen). Nutzer 16.11.2026: "Nein, nicht spiegeln ... Fotos suchen";
"Hast du das generalisiert?" -> FOTO = auto waehlt das beste Foto selbst, --stl blendet Verdecktes aus.
  auto:  alle Messkameras (K-*.json), denen man trauen kann (Buendelkameras eigener/Commons-Fotos, nachgezogene mit 'vertrauen'; KEINE Videobilder, keine ungeprueften Downloads),
         die die Wand von vorn sehen. Je Kandidat (die 12 mit der besten rechnerischen Aufloesung): Tiefenbild des Modells aus dieser Kamera -> Anteil der Wandzellen,
         die wirklich SICHTBAR sind (nicht hinter Nachbarhaus/Dach), und Aufloesung dort. Wertung = sichtbare Flaeche / Meter je Pixel. Das beste gewinnt; Rangliste wird gedruckt.
  --stl: Modell-STL(s) fuer die Verdeckungspruefung (eigenes Objekt + Nachbarn im selben Rahmen). Verdeckte Zellen werden schwarz (= "keine Daten" fuer steine_aus_foto.py).
         Ohne --stl keine Verdeckungspruefung (wie die erste Fassung: Nachbardach musste von Hand per --ohne ausgenommen werden).
  --z/--u: nur dieser Wandbereich zaehlt fuer die Wahl (z. B. Zone ueber dem Gesims).
Ablauf fuer eine schlecht belegte Wand: (1) tools/seiten_luecken.py --download --holen (Fotos holen, registrieren, Kameras nachziehen), (2) dieses Werkzeug mit auto,
(3) relief_einsatz.py - (leeres Relief, falls kein Netz) -> relief_putz.py -> steine_aus_foto.py; Fenster mit foto_mass.py auf der Wandebene.
Lehre 16.11.: dasselbe Motiv liegt oft mehrfach vor (Flickr 1024 px, Commons-Original 3840 px) - auto nimmt von selbst das schaerfste.
"""
import sys, os, json, glob, argparse, numpy as np, cv2


def kamera(kf):
    k = json.load(open(kf)).get("kamera"); return k if isinstance(k, dict) and "rvec" in k and "cx" in k else None


def sichtbar(mm, K, X, rk, tol=0.35):
    """je 3D-Punkt: im Bild UND nicht verdeckt (Tiefenbild des Modells aus der Kamera, GPU). Liefert (maske, mx, my, tiefe)."""
    R = cv2.Rodrigues(np.array(K["rvec"]))[0]; t = np.array(K["t"]); p = X @ R.T + t; x = p[:, 0] / p[:, 2]; y = p[:, 1] / p[:, 2]; f_ = 1 + float(K.get("k1") or 0) * (x * x + y * y)
    mx = K["f_px"] * x * f_ + K["cx"]; my = K["f_px"] * y * f_ + K["cy"]; W, H = 2 * K["cx"], 2 * K["cy"]; ok = (p[:, 2] > 0.5) & (mx >= 0) & (mx < W - 1) & (my >= 0) & (my < H - 1)
    if mm is not None and ok.any():
        s = min(1.0, 2000.0 / max(W, H)); Wr, Hr = int(W * s), int(H * s); tiefe = np.asarray(rk.dreiecke_rastern(mm, R, t, K["f_px"] * s, K["cx"] * s, K["cy"] * s, Wr, Hr)[0])
        ui = np.clip((mx * s).astype(int), 0, Wr - 1); vi = np.clip((my * s).astype(int), 0, Hr - 1); d = tiefe[vi, ui]; ok &= (d <= 0) | (p[:, 2] <= d + tol) if False else ((p[:, 2] <= d + tol) | ~np.isfinite(d) | (d <= 0))
    return ok, mx, my, p[:, 2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("fassaden"); ap.add_argument("nr", type=int); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("aus"); ap.add_argument("--stl"); ap.add_argument("--z", nargs=2, type=float); ap.add_argument("--u", nargs=2, type=float); ap.add_argument("--rand", type=float, default=0.3, help="Sicherheitsrand (m) um verdeckte Bereiche"); a = ap.parse_args()
    F = json.load(open(a.fassaden))["fassaden"][a.nr]; R = F["raster"]; o = np.array(F["o"]); d = np.array(F["d"]); nv = np.array([F["n"][0], F["n"][1], 0.0]); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll")
    mm = None; rk = None
    if a.stl:
        import trimesh; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import render_kern as rk
        ms = [trimesh.load(q) for q in a.stl.split(",")]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    foto = a.foto
    if foto == "auto":
        uu = np.arange((a.u or F["u"])[0], (a.u or F["u"])[1], 0.25); zz = np.arange((a.z or F["z"])[0], (a.z or F["z"])[1], 0.25); G = np.array([[o[0] + u_ * d[0], o[1] + u_ * d[1], z_] for u_ in uu for z_ in zz]); Pm = G.mean(0); kand = []
        for kf in glob.glob(os.path.join(mp, "K-*.json")):
            n = os.path.basename(kf)[2:-5]; K = kamera(kf)
            if K is None or n.startswith("video") or (n.startswith(("dl_", "neu__")) and not K.get("vertrauen")) or not glob.glob(os.path.join(fd, n + ".*")): continue
            Rm = cv2.Rodrigues(np.array(K["rvec"]))[0]; C = -Rm.T @ np.array(K["t"]); v = C - Pm; dist = np.linalg.norm(v); cw = float(v @ nv / dist)
            if cw < 0.3 or dist > 250: continue
            kand.append((dist / (K["f_px"] * cw), n, K))
        kand.sort(key=lambda q: q[0]); rang = []
        for mpp, n, K in kand[:12]:
            ok, mx, my, zc = sichtbar(mm, K, G, rk); rang.append((float(ok.mean()) / mpp, n, float(ok.mean()), mpp))
        rang.sort(key=lambda q: -q[0])
        if not rang or rang[0][2] < 0.1: print("kein vertrauenswuerdiges Foto sieht diesen Wandbereich"); return 3
        for w, n, s_, mpp in rang[:6]: print(f"  {n[-44:]:44s} sichtbar {s_ * 100:3.0f} %, {mpp * 100:.1f} cm/px")
        foto = rang[0][1]
    kf = [f for f in glob.glob(os.path.join(mp, "K-*.json")) if foto in os.path.basename(f)][0]; K = kamera(kf); im = cv2.imread([f for f in glob.glob(os.path.join(fd, "*")) if foto in os.path.basename(f)][0])
    jj, ii = np.meshgrid(np.arange(R["nu"]), np.arange(R["nz"])); u = R["u0"] + (jj + 0.5) * R["zelle"]; z = R["z1"] - (ii + 0.5) * R["zelle"]; X = np.stack([o[0] + u * d[0], o[1] + u * d[1], z], -1).reshape(-1, 3)
    ok, mx, my, zc = sichtbar(mm, K, X, rk)
    if a.stl and a.rand > 0: ok = cv2.erode(ok.reshape(u.shape).astype(np.uint8), np.ones((2 * int(a.rand / R['zelle']) + 1,) * 2, np.uint8)).astype(bool).ravel()   # Rand der Verdeckung meiden: das echte Nachbardach ist etwas groesser als das Modell
    bild = cv2.remap(im, mx.astype(np.float32).reshape(u.shape), my.astype(np.float32).reshape(u.shape), cv2.INTER_LINEAR, borderValue=(0, 0, 0)); bild[~ok.reshape(u.shape)] = 0; cv2.imwrite(a.aus, bild)
    json.dump(dict(foto=foto, fassade=a.nr, verdeckung=bool(a.stl), anteil_daten=float(ok.mean())), open(os.path.splitext(a.aus)[0] + ".json", "w"), indent=1)
    print(f"{a.aus}: Foto {foto[-40:]}, {R['nu']}x{R['nz']} Zellen a {R['zelle'] * 100:.0f} cm, Aufloesung an der Wand ~{np.median(zc[ok]) / K['f_px'] * 100:.1f} cm/px, {100 * ok.mean():.0f} % mit Daten" + (" (Verdecktes ausgeblendet)" if a.stl else " (ohne Verdeckungspruefung)"))


if __name__ == "__main__":
    sys.exit(main())
