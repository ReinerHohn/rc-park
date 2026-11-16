#!/usr/bin/env python3
"""fassade_zylinder.py <objekt.json> <aus.png> --achse x y --radius r --z z0 z1 [--fotos a,b|auto] [--stl a.stl,...] [--zelle 0.01] - ABWICKLUNG eines runden Bauteils als Fassadenbild.

Nutzer 16.11.2026 (Treppenturm Schwabentor: Fensterchen fehlten; "das ist wichtig, gerade so fuer Schloesser"): alle Fassadenwerkzeuge kannten nur ebene Waende.
Hier wird die Mantelflaeche eines senkrechten Zylinders (Rundturm, Erker, Apsis) abgewickelt: Bildspalte = Bogenlaenge (Azimut x Radius), Bildzeile = Hoehe, 1 cm je Pixel.
Je Zelle das Foto mit dem steilsten Blick auf die Flaeche (cos zwischen Flaechennormale und Blickrichtung), nur wenn die Zelle dort SICHTBAR ist (Tiefenbild des Modells, --stl)
und cos >= 0,35. Fotos: Liste oder 'auto' (alle vertrauenswuerdigen Messkameras im Umkreis, beste 8 nach Aufloesung).
Ausgabe: aus.png (Abwicklung, schwarz = von keinem Foto gesehen), aus.json (achse, radius, az0 = Azimut der linken Bildkante in Grad, Drehsinn, z1 = Oberkante, zelle, fotos, anteil gesehen),
aus_quelle.png (welches Foto je Zelle). Punkt zurueckrechnen: az = az0 + spalte * zelle / radius (rad); x = ax + r cos(az), y = ay + r sin(az); z = z1 - zeile * zelle.
Danach: Fenster/Schlitze im Bild suchen (dunkle schmale Rechtecke) oder klicken und mit tools/zylinder_mass.py gegenpruefen; Quader ueber eine Wand-Hilfsebene noch NICHT (steine_aus_foto.py kennt nur Ebenen).
Grenzen: nur der Mantel (keine Haube); Radius/Achse muessen stimmen (aus dem Kreisausgleich); Rueckseiten ohne Foto bleiben schwarz - das ist dann ein Fall fuer tools/foto_auftrag.py.
"""
import sys, os, json, glob, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fassade_ein_foto as FE


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("aus"); ap.add_argument("--achse", nargs=2, type=float, required=True); ap.add_argument("--radius", type=float, required=True); ap.add_argument("--z", nargs=2, type=float, required=True)
    ap.add_argument("--fotos", default="auto"); ap.add_argument("--stl"); ap.add_argument("--zelle", type=float, default=0.01); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll"); mm = None; rk = None
    if a.stl:
        import trimesh, render_kern as rk
        ms = [trimesh.load(q) for q in a.stl.split(",")]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    ax = np.array(a.achse); r = a.radius; c = a.zelle; nu = int(round(2 * np.pi * r / c)); nz = int(round((a.z[1] - a.z[0]) / c)); jj, ii = np.meshgrid(np.arange(nu), np.arange(nz)); az = (jj + 0.5) * c / r - np.pi; z = a.z[1] - (ii + 0.5) * c
    N = np.stack([np.cos(az), np.sin(az), np.zeros_like(az)], -1).reshape(-1, 3); X = np.stack([ax[0] + r * np.cos(az), ax[1] + r * np.sin(az), z], -1).reshape(-1, 3); Pm = np.array([ax[0], ax[1], 0.5 * (a.z[0] + a.z[1])])
    if a.fotos == "auto":
        kand = []
        for kf in glob.glob(os.path.join(mp, "K-*.json")):
            n = os.path.basename(kf)[2:-5]; K = FE.kamera(kf)
            if K is None or n.startswith("video") or (n.startswith(("dl_", "neu__")) and not K.get("vertrauen")) or not glob.glob(os.path.join(fd, n + ".*")): continue
            R = cv2.Rodrigues(np.array(K["rvec"]))[0]; C = -R.T @ np.array(K["t"]); dist = np.linalg.norm(C - Pm); p = R @ Pm + np.array(K["t"])
            if dist > 150 or dist < 3 or p[2] <= 0 or not (0 < K["f_px"] * p[0] / p[2] + K["cx"] < 2 * K["cx"] and 0 < K["f_px"] * p[1] / p[2] + K["cy"] < 2 * K["cy"]): continue
            kand.append((dist / K["f_px"], n))
        kand.sort(); namen = []; sektor = {}
        for mpp, n in kand:                                               # hoechstens 3 Fotos je 45-Grad-Sektor des Standorts, damit alle Seiten vorkommen
            K = FE.kamera(os.path.join(mp, "K-" + n + ".json")); R = cv2.Rodrigues(np.array(K["rvec"]))[0]; C = -R.T @ np.array(K["t"]); s_ = int((np.degrees(np.arctan2(C[1] - ax[1], C[0] - ax[0])) + 180) // 45)
            if sektor.get(s_, 0) < 3: sektor[s_] = sektor.get(s_, 0) + 1; namen.append(n)
        namen = namen[:14]
    else: namen = a.fotos.split(",")
    bild = np.zeros((nz * nu, 3), np.uint8); best = np.full(nz * nu, 0.35, np.float32); quelle = np.full(nz * nu, -1, np.int16); genutzt = []
    for qi, n in enumerate(namen):
        K = FE.kamera(os.path.join(mp, "K-" + n + ".json")); im = cv2.imread(glob.glob(os.path.join(fd, n + ".*"))[0]); R = cv2.Rodrigues(np.array(K["rvec"]))[0]; C = -R.T @ np.array(K["t"])
        v = C - X; cw = (v * N).sum(1) / np.linalg.norm(v, axis=1); kandz = cw > best
        if kandz.sum() < 500: continue
        ok, mx, my, zc = FE.sichtbar(mm, K, X[kandz], rk, tol=0.25); idx = np.flatnonzero(kandz)[ok]
        if len(idx) < 500: continue
        m_ = len(idx); br = 4096; pad = (-m_) % br; fx_ = np.r_[mx[ok], np.zeros(pad)].astype(np.float32).reshape(-1, br); fy_ = np.r_[my[ok], np.zeros(pad)].astype(np.float32).reshape(-1, br)      # remap vertraegt keine Zeile > 32767 Pixel
        farbe = cv2.remap(im, fx_, fy_, cv2.INTER_LINEAR).reshape(-1, 3)[:m_]; bild[idx] = farbe; best[idx] = cw[idx]; quelle[idx] = qi; genutzt.append(n); print(f"  {n[-40:]:40s} {len(idx) * c * c:6.1f} m2 uebernommen")
    bild = bild.reshape(nz, nu, 3); quelle = quelle.reshape(nz, nu); cv2.imwrite(a.aus, bild); pal = np.array([[60, 60, 60]] + [list(cv2.cvtColor(np.uint8([[[int(h_), 200, 230]]]), cv2.COLOR_HSV2BGR)[0, 0]) for h_ in np.linspace(0, 170, max(len(namen), 1))], np.uint8)
    cv2.imwrite(os.path.splitext(a.aus)[0] + "_quelle.png", cv2.resize(pal[quelle + 1], None, fx=0.25, fy=0.25, interpolation=cv2.INTER_NEAREST))
    json.dump(dict(achse=a.achse, radius=r, az0_grad=-180.0, drehsinn="az waechst nach rechts im Bild (mathematisch positiv, +x -> +y)", z1=a.z[1], z0=a.z[0], zelle=c, fotos=genutzt, anteil_gesehen=float((quelle >= 0).mean())), open(os.path.splitext(a.aus)[0] + ".json", "w"), indent=1)
    print(f"{a.aus}: Abwicklung {nu}x{nz} Zellen ({2 * np.pi * r:.2f} m Umfang x {a.z[1] - a.z[0]:.1f} m), {100 * (quelle >= 0).mean():.0f} % gesehen aus {len(genutzt)} Fotos")


if __name__ == "__main__":
    sys.exit(main())
