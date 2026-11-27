#!/usr/bin/env python3
"""wolken_dichte_bild.py - Kontrollbild zur Wolkenvereinigung (27.11.2026): je Wand Punktdichte in der Wandansicht (Laenge x Hoehe) fuer jede Quelle und VEREINT,
dazu Draufsicht (Dichte) und Herkunftsbild (welche Quelle je Pixel gewonnen hat). Nur Anzeige - Urteil steht in vereint.json (Zonen, rot).

  tools/py tools/wolken_dichte_bild.py --objekt modelle/<obj>/objekt.json <vereint_ordner> [--aus <bild.jpg>] [--px 0.25]

Liest <ordner>/vereint.json (Zonen = Wandebenen, Quellen, Rahmen), <ordner>/punkte_modell.npy + vereint_modell.ply.quellen.npy, die Quellen selbst blockweise.
Farbskala: log10(Punkte je Pixel), gleiche Skala fuer alle Felder einer Zeile. Weisse Linie = Hoehenband der Zonenzaehlung.
Verwandt: tools/wolke_vereinigen.py (erzeugt den Ordner), tools/dichte_diagnose.py (Zellen-Urteil FOTO/RECHEN). Vorlaeufer: keiner (Dichte je Quelle nie nebeneinander gezeigt).
"""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_vereinigen as WV  # noqa: E402


def raster(M, Z, px, ext):
    """Histogramm einer Wand in (Laenge, Hoehe) fuer Punkte im Streifen der Zone Z (Wandansicht von aussen)."""
    if Z["art"] != "wand": return None
    d = M[:, Z["achse"]] - Z["ebene"]; m = np.abs(d) <= Z["halb"]; q = M[m, 1 - Z["achse"]]; z = M[m, 2]
    H, _, _ = np.histogram2d(z, q, bins=[np.arange(ext[2], ext[3] + px, px), np.arange(ext[0], ext[1] + px, px)]); return H[::-1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--objekt", required=True); ap.add_argument("--aus"); ap.add_argument("--px", type=float, default=0.25)
    ap.add_argument("--z", type=float, nargs=2, default=[0.0, 52.0]); a = ap.parse_args()
    import cv2
    B = json.load(open(os.path.join(a.ordner, "vereint.json"))); zon = [Z for Z in B["zonen"] if Z["art"] == "wand"]; namen = [q["name"] for q in B["quellen"]]
    reg = {q["name"]: q for q in WV.register_lesen(a.objekt)["quellen"]}; zeige = [n for n in namen if n in reg and n != "kette"]   # 'kette' ist im Schwabentor Teil von hauptnetz_alles
    felder = {}                                                                     # name -> Liste Punkte (Modell), nur Streifen +-0,5 m um die Waende + Draufsicht-Stichprobe
    def sammeln(name, it):
        S = []; D = []
        for M in it:
            keep = np.zeros(len(M), bool)
            for Z in zon: keep |= np.abs(M[:, Z["achse"]] - Z["ebene"]) <= Z["halb"]
            S.append(M[keep]); D.append(M[::5])
        felder[name] = (np.concatenate(S), np.concatenate(D))
    for n in zeige:
        q = reg[n]; L = WV.Quelle(WV._pfad(q["pfad"])); A, b = WV.rahmen_lesen(q.get("rahmen", "modell"))
        sammeln(n, (L.block(i, min(L.n, i + 2_000_000))[0] @ A.T + b for i in range(0, L.n, 2_000_000)))
    PM = np.load(os.path.join(a.ordner, "punkte_modell.npy"), mmap_mode="r"); qn = np.load(os.path.join(a.ordner, "vereint_modell.ply.quellen.npy"))
    sammeln("VEREINT", (np.asarray(PM[i:i + 2_000_000]) for i in range(0, len(PM), 2_000_000)))
    spalten = zeige + ["VEREINT"]; px = a.px; kacheln = []
    for Z in zon:
        ext = (Z["a"] - 0.5, Z["b"] + 0.5, a.z[0], a.z[1]); Hs = [raster(felder[n][0], Z, px, ext) for n in spalten]; vmax = max(np.log10(1 + H).max() for H in Hs) or 1
        zeile = []
        for n, H in zip(spalten, Hs):
            if Z["vz"] < 0: H = H[:, ::-1]                                          # von aussen gesehen
            g = (np.log10(1 + H) / vmax * 255).astype(np.uint8); im = cv2.applyColorMap(g, cv2.COLORMAP_INFERNO); im[H == 0] = (40, 40, 40)
            im = cv2.resize(im, (im.shape[1] * 6, im.shape[0] * 6), interpolation=cv2.INTER_NEAREST)
            for zz in Z["z"]: y = int((a.z[1] - zz) / px * 6); cv2.line(im, (0, y), (im.shape[1], y), (255, 255, 255), 1)
            cnt = B["zonen_zahlen"].get(n, B["zonen_zahlen"]["VEREINT"] if n == "VEREINT" else {}).get(Z["name"], 0)
            kopf = np.full((44, im.shape[1], 3), 255, np.uint8); cv2.putText(kopf, f"{Z['name']} {n}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            cv2.putText(kopf, f"Zone {cnt:,}".replace(",", " "), (4, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 160), 1); zeile.append(np.vstack([kopf, im]))
            zeile.append(np.full((zeile[-1].shape[0], 8, 3), 255, np.uint8))
        kacheln.append(np.hstack(zeile))
    w = max(k.shape[1] for k in kacheln); bild = np.vstack([np.pad(k, ((0, 8), (0, w - k.shape[1]), (0, 0)), constant_values=255) for k in kacheln])
    # Draufsicht: Dichte je Quelle + Herkunft
    ext = (-30, 30, -40, 30); gx = np.arange(ext[0], ext[1] + 0.25, 0.25); gy = np.arange(ext[2], ext[3] + 0.25, 0.25); dr = []
    for n in spalten:
        D = felder[n][1]; H, _, _ = np.histogram2d(D[:, 1], D[:, 0], bins=[gy, gx]); g = (np.log10(1 + H) / max(np.log10(1 + H).max(), 1) * 255).astype(np.uint8)
        im = cv2.applyColorMap(g[::-1], cv2.COLORMAP_INFERNO); im[H[::-1] == 0] = (40, 40, 40); im = cv2.resize(im, (im.shape[1] * 2, im.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
        k = np.full((24, im.shape[1], 3), 255, np.uint8); cv2.putText(k, f"Draufsicht {n} (x rechts = Nord, y oben = West)", (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1); dr.append(np.vstack([k, im]))
    farben = [(200, 200, 200), (60, 60, 255), (60, 200, 60), (255, 120, 40), (40, 200, 255)]; Ds = np.asarray(PM[::5]); qs = qn[::5]; im = np.full((len(gy) - 1, len(gx) - 1, 3), 40, np.uint8)
    for i in range(len(namen)):
        m = qs == i
        if not m.any(): continue
        H, _, _ = np.histogram2d(Ds[m, 1], Ds[m, 0], bins=[gy, gx]); im[H > 0] = farben[i % len(farben)]
    im = cv2.resize(im[::-1], (im.shape[1] * 2, im.shape[0] * 2), interpolation=cv2.INTER_NEAREST); k = np.full((24, im.shape[1], 3), 255, np.uint8)
    cv2.putText(k, "Herkunft: " + "  ".join(f"{n}" for n in namen), (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    for i, n in enumerate(namen): cv2.rectangle(k, (4 + 9 * len("Herkunft: ") + sum(9 * (len(x) + 2) for x in namen[:i]) - 4, 4), (4 + 9 * len("Herkunft: ") + sum(9 * (len(x) + 2) for x in namen[:i]) - 1, 20), farben[i % len(farben)], -1)
    dr.append(np.vstack([k, im])); d2 = np.hstack([np.pad(x, ((0, 0), (0, 6), (0, 0)), constant_values=255) for x in dr])
    w = max(bild.shape[1], d2.shape[1]); bild = np.vstack([np.pad(bild, ((0, 10), (0, w - bild.shape[1]), (0, 0)), constant_values=255), np.pad(d2, ((0, 0), (0, w - d2.shape[1]), (0, 0)), constant_values=255)])
    aus = a.aus or os.path.join(a.ordner, "dichte_je_wand.jpg"); cv2.imwrite(aus, bild, [cv2.IMWRITE_JPEG_QUALITY, 85]); print("BILD", aus, bild.shape); return 0


if __name__ == "__main__":
    sys.exit(main())
