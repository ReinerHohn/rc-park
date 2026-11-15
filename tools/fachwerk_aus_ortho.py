#!/usr/bin/env python3
"""fachwerk_aus_ortho.py <ortho-ordner> <aus-ordner> ID [ID ...] [--px 0.025] [--hoehe 0.035] [--v 0.42] - Fachwerkbalken einer Geschossflaeche als flaches Relief aus dem MEHRFOTO-Fassadenbild.

Balken = dunkles Holz auf hellem Putz. Quelle ist das ueber 10-12 Fotos gemittelte Ortho (fassade_ortho.py, Median der besten Fotos je Zelle) - nicht ein Einzelfoto;
Passanten, Draehte und Schatten einzelner Fotos sind dort schon heraus. Schwelle auf die Helligkeit (V < --v), kleine Flecken weg, Fensterflaechen (fenster.json) ausgespart,
Rand des Bildes (keine Fotodaten) = kein Balken. Ausgabe je ID <aus>/fachwerk_<ID>.npz im Format von relief_einsatz.py (rel = --hoehe auf Balken, sonst 0; Ebene = Fassadenebene
o, d, n aus fassaden.json) + .jpg (Balken rot ueber dem Ortho) zum ANSEHEN. Im Generator: relief_einsatz.koerper(npz, tiefe=0.05, rand_auslauf=False) VOR dem Ausschneiden der Fenster.
Abweichung von der Regel 'linienhafte Features nur per Kanten-Sweep': hier Farbschwelle, aber auf dem Mehrfoto-Median bei sehr hohem Kontrast (schwarz/weiss) - als ANNAHME belegen.
"""
import sys, os, json, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ortho"); ap.add_argument("aus"); ap.add_argument("ids", nargs="+"); ap.add_argument("--px", type=float, default=0.025); ap.add_argument("--hoehe", type=float, default=0.035); ap.add_argument("--v", type=float, default=0.42); a = ap.parse_args()
    FA = {F.get("id") or F.get("id_vorbau"): F for F in json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]}; fj = os.path.join(a.ortho, "fenster.json"); FE = json.load(open(fj)) if os.path.exists(fj) else {}; os.makedirs(a.aus, exist_ok=True)
    for fid in a.ids:
        F = FA[fid]; im = cv2.imread(os.path.join(a.ortho, f"ortho_{fid}.png")); r = F["raster"]; zl = r["zelle"]; H0, W0 = im.shape[:2]; leer = im.sum(2) == 0; V = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)[..., 2].astype(np.float32) / 255.0
        holz = (V < a.v) & ~cv2.dilate(leer.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        for w in FE.get(fid, {}).get("fenster", []):
            x0, x1 = int((w["u0"] - r["u0"]) / zl), int((w["u1"] - r["u0"]) / zl); y0, y1 = int((r["z1"] - w["z1"]) / zl), int((r["z1"] - w["z0"]) / zl); holz[max(y0, 0):y1, max(x0, 0):x1] = False
        k = max(1, int(round(a.px / zl))); px = zl * k; H, W = H0 // k, W0 // k; m = holz[H0 - H * k:, :W * k].reshape(H, k, W, k).mean((1, 3)) >= 0.5
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)); n_, lab, st, _ = cv2.connectedComponentsWithStats(m, 8); m = np.isin(lab, 1 + np.flatnonzero(st[1:, 4] * px * px >= 0.05))
        rel = np.where(m, a.hoehe, 0.0).astype(np.float32); u0 = r["u0"]; z0 = r["z1"] - H0 * zl
        np.savez_compressed(os.path.join(a.aus, f"fachwerk_{fid}.npz"), rel=rel, a=np.array(F["o"]), t=np.array(F["d"]), n=np.array(F["n"]), u0=u0, z0=z0, px=px, lochanteil=0.0, hub_p5_p95=a.hoehe, ebene_abstand_m=0.0, trend_je_m=np.zeros(2), balken_anteil=float(m.mean()))
        vis = cv2.resize(im[H0 - H * k:, :W * k], (W, H), interpolation=cv2.INTER_AREA); vis[m] = (0.4 * vis[m] + 0.6 * np.array([0, 0, 255])).astype(np.uint8); cv2.imwrite(os.path.join(a.aus, f"fachwerk_{fid}.jpg"), vis)
        print(f"{fid}: {W}x{H} Zellen a {px*100:.1f} cm, Balkenanteil {m.mean()*100:.0f} %, u {u0:.2f}..{u0 + W * px:.2f}, z {z0:.2f}..{z0 + H * px:.2f}")


if __name__ == "__main__":
    sys.exit(main())
